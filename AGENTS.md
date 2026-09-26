# AGENTS.md

repo-docs is a portable agent skill that keeps a repository's instruction files
correct and progressively disclosed. The framework and its names (hub, spoke, adapter)
are the product, and a check is a later, optional add-on.

## Commands

There is no build and no automated check yet; the optional check ships in a later
release. Run `sh scripts/sync-version.sh` after changing the version or any manifest. It
copies the version from `.claude-plugin/plugin.json` into the other two manifests, prints
nothing on success, and fails if a manifest is missing or any `version` key differs.
To release, edit `version` in `.claude-plugin/plugin.json`, run the script, commit, tag
`vX.Y.Z`, push the tag, and write release notes on GitHub. There is no changelog file.
After changing `hooks/pre-commit.sh`, pipe it a sample event, such as
`printf '{"tool_input":{"command":"git commit"}}' | sh hooks/pre-commit.sh`; a commit
prints one line of JSON, and any other command prints nothing.

## Hard constraints

- No markdown parser, anywhere. A path is verified with a `sed` or `awk` line scan and
  `test -e`, or not at all.
- Any script is POSIX `sh`, standard tools only, and never reads git history.
  `sync-version.sh` writes only the two copied manifests. The check, when it ships, never
  writes a file, and its test writes only under its own `mktemp -d` directory.
- One `AGENTS.md` is canonical at every scope. A `CLAUDE.md` is exactly the one line
  `@AGENTS.md`, and this repo has none.
- One hook, `hooks/pre-commit.sh`, runs before each `Bash` tool call on Claude Code and
  Codex. When the command runs `git commit`, it adds a reminder to run the audit; it
  never blocks the command, reads only stdin, and never writes a file. No other hook.
- One authoritative version, in `.claude-plugin/plugin.json`. The other two manifests,
  `.claude-plugin/marketplace.json` and `.codex-plugin/plugin.json`, hold copies that
  `sync-version.sh` writes and verifies equal.
- `skills/repo-docs/SKILL.md` stays at or under 120 lines, and each file under
  `skills/repo-docs/references/` at or under 90. A platform's version numbers, byte and
  hop limits, line-count guidance, and URLs live only in
  `skills/repo-docs/references/platforms.md`; every other file states the behavior in
  words and points there.
- `README.md` stays shorter, in lines, than `placement.md` and `spokes.md` together.
- Commit subjects and release notes render on GitHub, so put a bare `@token` in
  backticks. GitHub links it to whatever account owns that name.

## Spokes

- skills/repo-docs/SKILL.md: the skill itself, with the principle, the hub and spoke model, what each platform loads, the four hub sections, and the two modes. Read before changing any file under skills/.
- skills/repo-docs/references/spokes.md: the pointer grammar, adapter policy, judgment checks, maintain-mode safeguards, and modes and severity. Read before writing or reviewing skill content.
- skills/repo-docs/references/placement.md: the placement rule. Read before editing it or deciding where a piece of skill content belongs.
- skills/repo-docs/references/platforms.md: each platform fact the skill relies on, with its source and the date it was checked. Read before relying on or changing a platform behavior, or when a platform changes.
