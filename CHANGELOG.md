# Changelog

All notable changes to repo-docs. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Changed

- Every git call in the checker is bounded by a 10 second timeout. On expiry
  the `stale` check is skipped, so a slow or hung filesystem cannot stall the
  session-start hook.
- The GitHub Actions snippet in the README fetches the checker from a release
  tag instead of `main`.
- The Codex install instructions moved from the README to `docs/codex.md`.

### Added

- This changelog.

## [0.1.1] - 2026-09-17

Patch release. Pin to this tag rather than tracking `main`.

### Fixed

- A `CLAUDE.md` symlink to a missing `AGENTS.md` is now reported as a
  dangling import on Python 3.9 for Windows. `Path.resolve()` there returns
  the link itself when the target is missing; the checker reads the link with
  `os.readlink` instead. Found by the first Windows CI run. See
  [#9](https://github.com/vibecodedapps-official/repo-docs/pull/9).

### Changed

- Windows: the Claude Code hook was verified on 2026-09-17. It runs under
  Git Bash and fails only when `python3` resolves to the Microsoft Store
  stub; the README documents the workaround. Closes
  [#7](https://github.com/vibecodedapps-official/repo-docs/issues/7).
- CI now runs the suite on Windows for Python 3.9 and 3.13.

## [0.1.0] - 2026-09-17

First tagged release.

### Added

- Five mechanical checks: `bridge`, `rival`, `size`, `link`, `stale`.
  Standard library only, read-only, Python 3.9+.
- Claude Code plugin with a `SessionStart` hook, Codex plugin and hook, and
  a plain skill install.
- Hardened against the adversarial review of 2026-09-17: special files,
  unreadable files, quoted fix commands, import target validation,
  CommonMark-aware link parsing, and a link scan of `docs/**.md`. See
  [#6](https://github.com/vibecodedapps-official/repo-docs/pull/6).

[Unreleased]: https://github.com/vibecodedapps-official/repo-docs/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/vibecodedapps-official/repo-docs/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/vibecodedapps-official/repo-docs/releases/tag/v0.1.0
