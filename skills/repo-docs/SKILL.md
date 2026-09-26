---
name: repo-docs
description: Use when editing AGENTS.md, CLAUDE.md, or a spoke the hub indexes; when
  setting up a repo that has no instruction files or only a CLAUDE.md; when adding a
  spoke, an adapter, or a pointer; before a commit or pull request; or after a batch of
  feature work, to keep the hub and its spokes correct and progressively disclosed. Not
  for writing user-facing product docs, API references, or README content unrelated to
  agent instructions.
---

# repo-docs

## Principle

> Put information at the narrowest scope where it stays authoritative, and load it only
> when the task needs it.

## The model

- The **hub** is the root `AGENTS.md`. It is the canonical instruction file and always
  loads.
- A **spoke** is a file the hub points to. It loads only when its condition is met. A
  topic spoke is a long-form file that stays wherever the repo already keeps it and that
  the agent opens on demand. A directory spoke is a `<dir>/AGENTS.md` that holds only
  rules for tasks confined to `<dir>`.
- A **pointer** is one line in the hub's spoke index that names a spoke and says when to
  read it.
- An **adapter** is a `CLAUDE.md` whose whole content is the one line `@AGENTS.md`, in a
  regular file, never a symlink. It holds nothing of its own.

The default is no adapter. Claude Code reads `AGENTS.md` directly until a `CLAUDE.md`,
`.claude/CLAUDE.md`, or `CLAUDE.local.md` exists in or above the working directory, and
from then on reads `CLAUDE.md` files only. Adapters are therefore
all or nothing: none in the repo, or one beside every `AGENTS.md`.
Add them only when a session in use cannot read `AGENTS.md` directly or someone needs a
`CLAUDE.local.md`. Claude-only mechanics go in `.claude/rules/`, never in an adapter, and
`.claude/rules/` never holds a rule another agent must follow.

`README.md` is for humans. It is never a spoke and never holds a rule an agent needs.
`AGENTS.override.md` and `AGENTS.local.md` are not used; either one is a second source of
truth.

## What loads when

| File | Role | Claude Code, no adapters | Claude Code, with adapters | Codex |
|---|---|---|---|---|
| `AGENTS.md` (root) | hub | always | always | always |
| `CLAUDE.md` (root) | adapter | absent | always | never |
| `<path>` in the index | topic spoke | on pointer | on pointer | on pointer |
| `<dir>/AGENTS.md` | directory spoke | on read | on read | on start-in-dir |
| `<dir>/CLAUDE.md` | adapter | absent | on read | never |
| `README.md` | not a spoke | never | never | never |

- **always**: loads at session start.
- **absent**: the file does not exist in that setup.
- **on pointer**: loads when the agent follows the hub pointer.
- **on read**: loads when the agent reads a file under `<dir>`.
- **on start-in-dir**: loads only when the session starts inside `<dir>`.
- **never**: the platform does not load it as an instruction file.

On Codex, directory spokes are static, because the instruction chain is built once at
session start from the repo root down to the working directory, so every directory spoke
gets a hub pointer with the condition "Read before editing under `<dir>/`". Each cell
rests on a platform fact recorded, with its source, in `references/platforms.md`.

## The hub

The hub holds four sections and nothing else:

1. One or two sentences on what the repo is.
2. The commands: test, lint, build, and anything an agent runs to verify work.
3. The hard constraints that apply to every task.
4. The spoke index, under a `## Spokes` heading, one pointer per spoke:

```
## Spokes

- <path>: <what the spoke holds>. <when to read it>.
```

The path is bare and relative to the repo root: no backticks, no link, no leading `@`,
which would import the spoke at launch. Everything else is a spoke or is deleted under the
placement rule. A hub that has grown past these four sections is a finding.

## Modes

- **audit**: read only; apply the checks in `references/spokes.md`, report each as an
  error or a finding, and end with a session verification: start a fresh session at the
  repo root and confirm the hub actually loaded.
- **maintain**: applies changes, including first setup, a repo whose only instruction file
  is a `CLAUDE.md`, and a repo with symlinked instruction files or an adapter with content
  after the import, under the safeguards in `references/spokes.md`.

## Reference files

- Read `references/placement.md` when deciding where a piece of content belongs, or when
  cleaning up content that should be deleted outright.
- Read `references/spokes.md` when running audit or maintain mode, or when writing a
  pointer or an adapter, for the pointer grammar, the adapter policy, the judgment
  checks, the session verification, and the maintain-mode safeguards.
- Read `references/platforms.md` when a rule here seems not to match what a platform
  does, or before relying on a platform's loading behavior, for each fact with its source
  and the date it was checked.
