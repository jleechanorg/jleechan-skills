#!/usr/bin/env bash
# Audit companion for path-deletion-guard.py.
#
# Reads the same stdin JSON payload and appends a record only when the guard
# itself returns a deny decision. Safe Bash calls remain completely unlogged.
#
# Exit 0 always — pure observability, never blocks.

set -uo pipefail

payload="$(cat 2>/dev/null || true)"
[ -n "$payload" ] || exit 0

GUARD="${HOME}/.codex/hooks/path-deletion-guard.py"
guard_output="$(printf '%s' "$payload" | python3 "$GUARD" 2>/dev/null)"
guard_exit=$?
[ "$guard_exit" -eq 2 ] || exit 0
printf '%s' "$guard_output" |
  jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null 2>&1 || exit 0

LOG_DIR="${CODEX_PATH_GUARD_LOG_DIR:-$HOME/.codex/log}"
LOG_FILE="$LOG_DIR/path-deletion-guard.log"
mkdir -p "$LOG_DIR" 2>/dev/null || true

ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
tool="$(printf '%s' "$payload" | jq -r '.tool_name // .name // "unknown"' 2>/dev/null || echo 'unknown')"
cmd="$(printf '%s' "$payload" | jq -r '
  (.tool_input.command // .tool_input.cmd // .input.command // .input.cmd // "")[:512]
' 2>/dev/null || echo '')"

printf '%s tool=%s cmd=%s\n' "$ts" "$tool" "$cmd" >> "$LOG_FILE" 2>/dev/null || true

exit 0
