# Judgement checks

The checker script only measures bytes, bridges, links, and staleness by commit count.
These four checks need a reader. Apply them by hand in audit or maintain mode.

## Stale facts contradicted by the code

Look at every factual claim in a scanned `AGENTS.md` or `CLAUDE.md`: a command, a file
path, a behavior, a default value. Open the code, config, or script it describes. If the
claim no longer matches what you find, that is a finding. Severity is **error** if
following the claim would break a command or point at a file that moved; otherwise
**warning**.

## Duplication between a parent and a nested AGENTS.md

Look at a nested `AGENTS.md` next to its closest ancestor `AGENTS.md`. If a rule appears
in both with the same meaning, that is a finding: **warning**. Delete the nested copy
unless it genuinely differs at that scope; the root file already loads every session.

## A rule sitting at the wrong scope

Look at each rule in root `AGENTS.md` and ask which tasks it governs, not which path it
names. A rule that governs every commit stays in root even if it names one directory:
"Before committing any change, run `scripts/check.py`" governs every commit, so moving
it to `scripts/AGENTS.md` would make it load only for tasks that touch `scripts/`, which
is almost never. Only move a rule when the tasks it governs are themselves confined to
one subdirectory. That is a finding: **info**. Recommend moving it to that
subdirectory's `AGENTS.md`, with a bridge.

## A doc nothing routes to

Look at every file under `docs/**.md`. Search `AGENTS.md`, `CLAUDE.md`, and `README.md`
for a link to it. If nothing links to it, that is a finding: **info**. An unreachable doc
costs upkeep for no read.

## Maintain-mode safeguards

- Adopt existing file locations before proposing to move anything. A pointer added to a
  file where it already lives beats a move.
- Never rewrite dated or historical entries. Append a correction instead.
- Repair inbound links in the same change that moves content.
- Run the checker before and after; report both results.
- Size findings are advisory. Never delete a real constraint to make a number go down.
- Upgrading repo-docs never requires reorganizing an adopted repo's files.
