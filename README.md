# repo-docs

A framework for repository instruction files, and a skill that applies it.

The root `AGENTS.md` is the hub: it always loads and holds what the repo is, the
commands, the hard constraints, and an index of spokes. A spoke is any file the hub
points to, read only when its condition is met. An adapter is a `CLAUDE.md` whose only
content is `@AGENTS.md`, used only where Claude Code cannot read `AGENTS.md` directly or
someone needs a `CLAUDE.local.md`.

The principle behind it: put information at the narrowest scope where it stays
authoritative, and load it only when the task needs it.

## Status

The first release ships the skill and one hook; an optional check follows in a later
release. The skill loads when a task matches it, or when you call it with `/repo-docs`.
The hook runs when the agent runs `git commit` in a session and reminds it to audit. It
never blocks the commit, and it does not run on a commit made outside a session.

## Install

This repository is its own plugin marketplace for Claude Code and Codex.

Claude Code, inside a session:

```
/plugin marketplace add vibecodedapps-official/repo-docs
/plugin install repo-docs@repo-docs
```

Codex:

```
codex plugin marketplace add vibecodedapps-official/repo-docs
codex plugin add repo-docs@repo-docs
```

Codex runs a plugin hook only after you trust it. Run `/hooks` in a session to trust it.

## License

Apache 2.0. See `LICENSE`.
