---
name: repo-docs
description: Use when editing AGENTS.md, CLAUDE.md, or files under docs/; when onboarding
  a repo that has no instruction files; before a commit or pull request; or after a batch
  of feature work, to keep instruction files correct and progressively disclosed. Not for
  writing user-facing product docs, API references, or README content unrelated to agent
  instructions.
---

# repo-docs

## Core principle

> Put information at the narrowest scope where it stays authoritative, and load it only
> when the task needs it.

## The structure contract

| Path | Owns | When it loads |
|---|---|---|
| `AGENTS.md` (root) | repo-wide commands, hard constraints, pointers | always |
| `CLAUDE.md` (root) | nothing of its own; `@AGENTS.md` first line | always |
| `<dir>/AGENTS.md` | rules that apply only under `<dir>` | with its bridge |
| `<dir>/CLAUDE.md` | nothing of its own; `@AGENTS.md` first line | when Claude reads a file in `<dir>` |
| `docs/**.md` | long-form architecture, workflows, runbooks | when linked and needed |
| `README.md` | humans: what it is, install, usage | not auto-loaded; read when relevant |

`AGENTS.md` is canonical. `CLAUDE.md` is a bridge, never a second source of truth. A
`CLAUDE.md` may add Claude-only lines after the import, but must not restate what
`AGENTS.md` already says.

## Platform facts (source: https://code.claude.com/docs/en/memory)

1. Claude Code never reads `AGENTS.md` directly. There is no setting that changes this.
2. Claude Code loads a directory's `CLAUDE.md` only when it reads a file in that
   directory. Nested loading is lazy.
3. `@path` imports in a `CLAUDE.md` expand when that `CLAUDE.md` loads. Relative paths
   resolve against the importing file's directory, not the project root. Max depth is
   four hops.
4. A `CLAUDE.md` containing only `@AGENTS.md` loads the sibling `AGENTS.md`. A symlink
   `CLAUDE.md -> AGENTS.md` does the same.

Consequence: a nested `AGENTS.md` with no sibling `CLAUDE.md` bridge is invisible to
Claude Code. Moving a rule out of the root without bridging it deletes that rule from
every Claude session.

## Modes

- **audit**: read only. Run the checker, add judgement findings from `checks.md`,
  report. Changes nothing.
- **maintain**: applies documentation changes, including first-time setup of a repo
  that has none. Missing files are an input condition, not a third mode. Follow the
  maintain-mode safeguards in `checks.md`.

## Running the checker

The script lives at `scripts/repo_docs_check.py` relative to this SKILL.md, not
relative to the repository you are checking. Resolve that path against this skill's own
directory and invoke it as an absolute path, then pass the target repository as `ROOT`:

```
python3 /absolute/path/to/skills/repo-docs/scripts/repo_docs_check.py ROOT [--json] [--hook] [--stale-threshold N]
```

Exit codes: `0` no error findings, `1` at least one error finding, `2` usage error or the
checker itself failed. Severities are `error`, `warning`, `info` only.

## Reference files

- Read `references/placement.md` when deciding where a piece of content belongs, or when
  cleaning up content that should be deleted outright.
- Read `references/checks.md` when running audit or maintain mode, for the judgement
  checks the script cannot make and the maintain-mode safeguards.
