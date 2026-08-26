#!/usr/bin/env bash
# Non-destructive /web-advice Aside REPL browser diagnostic.
#
# This script probes only the `aside repl` Playwright browser API. The
# `aside-mcp` route must be probed through its MCP tool because a shell script
# cannot inspect MCP tool availability. It never invokes Aside inference,
# opens a tab, submits a prompt, or inspects browser cookies.

set -uo pipefail

TIMEOUT_BIN="$(command -v timeout || command -v gtimeout || true)"

run_with_timeout() {
  local seconds="$1"
  shift
  if [ -n "$TIMEOUT_BIN" ]; then
    "$TIMEOUT_BIN" "$seconds" "$@"
  else
    "$@"
  fi
}

echo "==============================================================================="
echo " /web-advice Aside REPL browser diagnostic — $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo " No prompt is submitted and no tab is opened. Probe aside-mcp separately."
echo "==============================================================================="

if ! command -v aside >/dev/null 2>&1; then
  echo "Aside REPL browser: DOWN — aside CLI is not on PATH"
  exit 1
fi

aside_repl_out="$(
  run_with_timeout 15 aside repl \
    "console.log((await listBrowserTabs()).length)" 2>&1
)"
aside_repl_rc=$?
tab_count="$(printf '%s\n' "$aside_repl_out" | grep -oE '^[0-9]+$' | head -1)"

if [ "$aside_repl_rc" -eq 0 ] && [ -n "$tab_count" ]; then
  echo "Aside REPL browser: UP — ${tab_count} tab(s) visible"
  exit 0
fi

detail="$(printf '%s\n' "$aside_repl_out" | head -1)"
echo "Aside REPL browser: DOWN — rc=${aside_repl_rc}: ${detail}"
exit 1
