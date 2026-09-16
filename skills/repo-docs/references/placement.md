# Placement

Where a piece of content belongs, decided in one pass.

## The decision rule

Take one paragraph or rule at a time. Ask these questions in order and stop at the first
yes.

1. Does it apply everywhere in the repo, and is it short enough to read every session?
   Put it in root `AGENTS.md`.
2. Does it apply only under one directory? Put it in `<dir>/AGENTS.md`, and add or confirm
   the `CLAUDE.md` bridge in that same directory.
3. Is it long-form: architecture, a workflow, a runbook, background, or history? Put it in
   `docs/`, and add one pointer line to it from the `AGENTS.md` that would otherwise need
   it.
4. Is it for a human deciding whether to use or install the project, not for an agent
   doing a task? Put it in `README.md`.
5. If none of the above fit, it does not belong in an instruction file. See the delete
   list below.

Apply this per paragraph, not per file. A single `AGENTS.md` can send different
paragraphs to different destinations.

## Signs a rule is at the wrong scope

Scope is decided by which tasks the rule governs, never by where a path it mentions
happens to live. A rule that names one directory but governs every commit stays in the
root, because a nested `AGENTS.md` loads only when the agent reads a file in that
directory, and most tasks never will.

Counterexample: root `AGENTS.md` says "Before committing any change, run
`scripts/check.py`." That rule names a path under `scripts/`, but it governs every
commit, not just work under `scripts/`. Moving it to `scripts/AGENTS.md` makes it
invisible for a task that only touches `src/`. It stays in root.

Other signs:

- A rule repeated in a nested `AGENTS.md` word for word with the root file. Keep it at
  the narrower scope only if it truly differs there; otherwise delete the nested copy
  and rely on the root file loading always.
- A paragraph longer than a few sentences sitting inline in `AGENTS.md` when it explains
  why rather than states a constraint. That is `docs/` content; leave a pointer behind.

## Delete outright

This content earns nothing and should be removed, not relocated:

- Generic advice that applies to any codebase, such as "write clean code" or "add tests."
- Pasted file contents. Point at the file instead of copying it.
- Folder tours or directory listings. They go stale and the agent can read the tree.
- Stack or dependency versions with no version-specific behavior attached. If a version
  matters only because it's current, it will be wrong soon and costs nothing to look up.
- Anything cheaply discoverable from the code itself, such as a function's parameter
  list, a config file's keys, or a command that's just the contents of a script the agent
  can already read.

When in doubt between relocating and deleting, delete. A missing rule is a bug someone
will report. A wrong rule is a bug nobody notices until it causes damage.
