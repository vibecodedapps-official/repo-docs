# repo-docs

repo-docs is a portable agent skill that keeps a repository's instruction
files correct and progressively disclosed. It ships two ways: as a Claude
Code plugin, so its session hook installs itself, and as a plain skill, so
Codex and other agents can use the same methodology.

The core principle, unchanged wherever it is quoted:

> Put information at the narrowest scope where it stays authoritative, and
> load it only when the task needs it.

## The problem

Instruction files start small and useful. Left alone, they grow. A root
`AGENTS.md` picks up rules that only apply to one package, notes that
duplicate what the code already shows, and paragraphs nobody has reread in
months. All of it loads into every session, on every task, whether the task
needs it or not. Meanwhile rules that should be visible everywhere end up
buried in a subdirectory nobody bridges, or the reverse: a rule that only
applies to one subtree sits in the root file and loads for work that never
touches that subtree. repo-docs exists to catch both failure modes, not to
promise a tidier repo.

## The structure contract

| Path | Owns | When it loads |
|---|---|---|
| `AGENTS.md` (root) | repo-wide commands, hard constraints, pointers | always |
| `CLAUDE.md` (root) | nothing of its own; `@AGENTS.md` first line | always |
| `<dir>/AGENTS.md` | rules that apply only under `<dir>` | with its bridge |
| `<dir>/CLAUDE.md` | nothing of its own; `@AGENTS.md` first line | when Claude reads a file in `<dir>` |
| `docs/**.md` | long-form architecture, workflows, runbooks | when linked and needed |
| `README.md` | humans: what it is, install, usage | not auto-loaded; read when relevant |

`AGENTS.md` is canonical. `CLAUDE.md` is a bridge, never a second source of
truth. A `CLAUDE.md` may add Claude-only lines after the import, but it must
not restate what `AGENTS.md` already says.

## Why the CLAUDE.md bridge exists

Claude Code never reads `AGENTS.md`. There is no setting that changes this.
It does discover `CLAUDE.md` in subdirectories of the working directory, and
it loads each one lazily, only when it reads a file in that subdirectory. A
`CLAUDE.md` whose entire content is the single line `@AGENTS.md` expands
that import at load time, so it pulls in the sibling `AGENTS.md`. On Unix,
`ln -s AGENTS.md CLAUDE.md` does the same thing.

The consequence: a nested `AGENTS.md` with no sibling `CLAUDE.md` bridge is
invisible to Claude Code. Moving a rule out of the root file without adding
that bridge deletes the rule from every Claude session that touches that
subtree. This is also the progressive disclosure mechanism: the root bridge
loads on every session, and nested bridges load only when Claude actually
works in that part of the tree.

Source: https://code.claude.com/docs/en/memory

## Install

### Claude Code

This repository acts as its own plugin marketplace: it carries a
`.claude-plugin/marketplace.json` alongside `plugin.json`, so the install is
persistent instead of something you have to remember to re-invoke every
session. Inside a Claude Code session, run:

```
/plugin marketplace add vibecodedapps-official/repo-docs
/plugin install repo-docs@repo-docs
```

To install from a clone instead, point the first command at the directory:

```
/plugin marketplace add /path/to/repo-docs
/plugin install repo-docs@repo-docs
```

The `SessionStart` hook is then live in every future session, in any
project, with no flag and no `settings.json` editing. This is the
recommended path.

For one-off testing without installing anything, start Claude Code with the
`--plugin-dir` flag instead:

```
claude --plugin-dir /path/to/repo-docs
```

This loads the plugin, hook included, only for that one session; you would
need to pass the flag again every time you start Claude Code. It is meant
for trying repo-docs out or developing against a local checkout, not for
everyday use.

### Codex and other agents

```
npx skills add ./skills/repo-docs
```

This installs the skill without the hook. Codex has no session-hook
equivalent, so run the checker from the repo's own checks or from CI
instead. See the GitHub Actions snippet below.

## Usage

repo-docs runs in one of two modes:

- **audit**: read only. Runs the checker, adds judgement findings on top of
  it, and reports. Changes nothing.
- **maintain**: applies documentation changes, including first-time setup
  for a repo that has no instruction files yet. Missing files are an input
  condition for maintain mode, not a separate mode of their own.

## The checker

```
repo_docs_check.py [ROOT] [--json] [--hook] [--stale-threshold N]
```

- `ROOT` defaults to the current working directory.
- `--json` prints one JSON object to stdout and nothing else.
- `--hook` prints a Claude Code `SessionStart` hook payload and always
  exits 0.
- `--stale-threshold N` overrides the staleness threshold. Default is 20.

Exit codes:

- `0`: no `error` findings. This can still mean there are `warning` or
  `info` findings; only `error` findings affect the exit code.
- `1`: at least one `error` finding.
- `2`: usage error, or the checker itself failed.

## The five checks

1. `bridge` (error): every directory with an `AGENTS.md` must have a
   `CLAUDE.md` that symlinks to it or whose first non-blank line is exactly
   `@AGENTS.md`.
2. `rival` (warning): a `CLAUDE.md` over 300 bytes with no sibling
   `AGENTS.md` is acting as an independent instruction file.
3. `size` (info above 2000 bytes, warning above 6000 bytes): byte size of
   each `AGENTS.md`, measured as UTF-8 bytes on disk.
4. `link` (error): a markdown inline link inside a scanned file whose
   local-file target does not exist on disk.
5. `stale` (info): the instruction files have not changed in longer than
   the staleness threshold, measured in commits touching other files.

## What repo-docs deliberately does not check

These checks were cut from the MVP, all for the same reason: they produce
false positives. A checker that cries wolf gets switched off, which defeats
the point of running one at all.

- Commands cited in `AGENTS.md` against `package.json`, `Makefile`, or
  `justfile` scripts.
- Duplicated lines between a parent and a nested `AGENTS.md`.
- Orphaned files under `docs/` that nothing links to.
- Paths written in backticked inline code.
- Environment variable names.
- Numeric limits other than the byte budgets above.
- External links.
- Frontmatter dates.

These are judgement calls, not mechanical ones. repo-docs leaves them to the
skill's audit and maintain modes, where a person or an agent can read the
surrounding context before flagging something.

One more limit worth knowing: the checker does not follow directory
symlinks, so instruction files inside a symlinked directory go unscanned.
This avoids infinite traversal through a symlink cycle and avoids reporting
findings about files outside the repository. Run the checker against the
real location of a linked directory as its own `ROOT` to cover it.

## A note on the byte budgets

The size thresholds are editorial defaults, not measured optima. Nobody ran
an experiment to find the exact byte count where an `AGENTS.md` stops
paying for itself. If a real constraint pushes a file over a budget, keep
the constraint. Never delete a necessary rule just to make a size finding
go away.

## GitHub Actions

This snippet is for repos that want the mechanical checks enforced on pull
requests without installing the plugin.

```yaml
name: repo-docs
on: pull_request
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - run: |
          curl -fsSL -o repo_docs_check.py \
            https://raw.githubusercontent.com/vibecodedapps-official/repo-docs/main/skills/repo-docs/scripts/repo_docs_check.py
          python3 repo_docs_check.py .
```

The checker is one file with no dependencies beyond the standard library, so
you can also copy `skills/repo-docs/scripts/repo_docs_check.py` into your own
repository and run it directly. Vendoring it pins the version you reviewed and
removes the network call, which matters if your runners have no outbound
access.

The `fetch-depth: 0` setting is there because the staleness check reads
commit history, and the default shallow clone has none to read.
