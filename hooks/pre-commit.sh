#!/bin/sh
# PreToolUse hook for Bash. When the command runs `git commit`, add a reminder to run the
# repo-docs audit. Reads only stdin, never blocks the command, never writes a file.
# The event is JSON: an escaped newline ends a command, an escaped tab is a space, and
# escaped quotes are dropped, so the only `"` left ends the command string.
sed 's/\\n/;/g; s/\\t/ /g; s/\\"//g' |
  grep -Eq '(^|[^[:alnum:]_.-])git([[:space:]]+[^[:space:];&|"]+)*[[:space:]]+commit([[:space:];&|"]|$)' ||
  exit 0
cat <<'JSON'
{"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":"repo-docs: this command commits, and the commit goes ahead. Unless you already ran the repo-docs audit on these changes, run it once the commit finishes and report what it finds; fix errors in a follow-up change. Skip it when the repo has no AGENTS.md or CLAUDE.md and the user has not asked for one."}}
JSON
