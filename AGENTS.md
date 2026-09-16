# AGENTS.md

repo-docs is a portable agent skill that keeps a repository's `AGENTS.md`,
`CLAUDE.md`, and `docs/` correct and progressively disclosed.

## Tests

```
python3 -m unittest discover -s tests -t .
```

The suite uses only the standard library, so a clone can run it with no installed packages.

## Hard constraints on contributions

- The checker (`skills/repo-docs/scripts/repo_docs_check.py`) and the test
  suite are Python 3.9+, standard library only. No third-party imports. No
  network calls. The checker never writes or edits a file.
- The five checks are frozen: `bridge`, `rival`, `size`, `link`, `stale`. Do
  not add a sixth check. If a check cannot stay reliable, remove it rather
  than adding exceptions.
- `skills/repo-docs/SKILL.md` stays at or under 120 lines.
  `skills/repo-docs/references/placement.md` and
  `skills/repo-docs/references/checks.md` each stay at or under 90 lines.
- Severity has exactly three levels: `error`, `warning`, `info`. Do not
  invent new severity vocabulary.

## Where to look

- `README.md` for what this is, install, usage, and the checker's CLI.
- `skills/repo-docs/SKILL.md` for the modes and the structure contract this
  repo enforces on itself.
