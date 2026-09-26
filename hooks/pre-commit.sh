#!/bin/sh
# PreToolUse hook for Bash. When the command runs `git commit` in a repo that tracks an
# AGENTS.md or CLAUDE.md, add a reminder to run the repo-docs audit. Reads stdin and the
# git index of the working directory, never blocks the command, never writes a file.
# The event is JSON: an escaped newline ends a command, an escaped tab is a space, and
# escaped quotes are dropped, so the only `"` left ends the command string.
sed 's/\\n/;/g; s/\\t/ /g; s/\\"//g' |
  grep -Eq '(^|[^[:alnum:]_.-])git([[:space:]]+[^[:space:];&|"]+)*[[:space:]]+commit([[:space:];&|"]|$)' ||
  exit 0
# The index sees a nested file and a file staged for this commit. The hook cannot tell
# whether the user asked for a first instruction file; the skill triggers on that case.
[ -n "$(git ls-files -- AGENTS.md '*/AGENTS.md' CLAUDE.md '*/CLAUDE.md' 2>/dev/null)" ] || exit 0
cat <<'JSON'
{"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":"repo-docs: this command commits, and the commit goes ahead. Unless you already ran the repo-docs audit on these changes, run it once the commit finishes and report what it finds; fix errors in a follow-up change."}}
JSON
