#!/bin/sh
# Copy the version in .claude-plugin/plugin.json into the other two manifests, then
# fail if any manifest is missing or any "version" key differs from it.
CDPATH= cd -- "$(dirname -- "$0")/.." || exit 1
src=.claude-plugin/plugin.json
copies=".claude-plugin/marketplace.json .codex-plugin/plugin.json"
fail() { echo "sync-version: $*" >&2; exit 1; }
for f in $src $copies; do [ -f "$f" ] || fail "missing $f"; done
v=$(sed -n 's/.*"version": *"\([^"]*\)".*/\1/p' "$src" | head -n 1)
case $v in ""|*[!0-9A-Za-z.+-]*) fail "no valid version in $src: '$v'" ;; esac
for f in $copies; do
  c=$(sed "s/\(\"version\": *\"\)[^\"]*\"/\1$v\"/g" "$f") || fail "cannot read $f"
  [ "$c" = "$(cat "$f")" ] || printf '%s\n' "$c" > "$f" || fail "cannot write $f"
done
for f in $src $copies; do
  got=$(sed -n 's/.*"version": *"\([^"]*\)".*/\1/p' "$f" | sort -u | paste -sd, -)
  [ -n "$got" ] || fail "$f has no \"version\": \"...\" key"
  [ "$got" = "$v" ] || fail "$f has version '$got', expected '$v'"
done
