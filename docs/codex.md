# Codex install

Codex supports native `SessionStart` hooks. Install the skill from a clone
for agent-led audits and maintenance:

```
npx skills add ./skills/repo-docs
```

The automatic hook only needs the checker script; skill installation is
independent. Add this hook to `~/.codex/hooks.json` for all projects, or to
`<repo>/.codex/hooks.json` for one trusted project. Merge it into any existing
hooks rather than replacing them. Replace the script path with the absolute
path to your clone or installed skill:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 /absolute/path/to/repo-docs/skills/repo-docs/scripts/repo_docs_check.py . --hook"
          }
        ]
      }
    ]
  }
}
```

Quote the script path inside the command if it contains spaces. The command
uses POSIX shell syntax; see the Windows note in the [README](../README.md).

Open `/hooks` in Codex to review and trust the hook, then start a new session.
New or changed hook definitions are skipped until trusted. The checker runs
in the session's working directory; start Codex at the repository root to
scan the whole repository. Findings become context for the agent; the hook
does not edit files or force a full audit or maintain pass.

For plugin distribution, `.codex-plugin/plugin.json` bundles the same skill
and automatically discovered `hooks/hooks.json`. Codex supplies
`CLAUDE_PLUGIN_ROOT` for compatibility; the shared command uses the session's
working directory when `CLAUDE_PROJECT_DIR` is unset. Installed plugin hooks
also require review and trust through `/hooks`.

Source: [Codex hooks](https://learn.chatgpt.com/docs/hooks).
