#!/usr/bin/env bash
# Non-destructive /web-advice browser transport diagnostic.
#
# This script probes `aside repl` first, then a clean Chrome/Chromium headless
# render when Aside is unavailable. The `aside-mcp` route must be probed
# through its MCP tool. It never invokes Aside inference, submits a prompt, or
# inspects browser cookies. Vendor authentication is qualified separately.

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
echo " /web-advice browser diagnostic — $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo " No prompt is submitted. Probe aside-mcp and vendor auth separately."
echo "==============================================================================="

if command -v aside >/dev/null 2>&1; then
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
else
  echo "Aside REPL browser: DOWN — aside CLI is not on PATH"
fi

chrome_bin=""
for candidate in google-chrome-stable google-chrome chromium chromium-browser; do
  if command -v "$candidate" >/dev/null 2>&1; then
    chrome_bin="$(command -v "$candidate")"
    break
  fi
done
if [ -z "$chrome_bin" ] && [ -x "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" ]; then
  chrome_bin="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
fi

if [ -z "$chrome_bin" ]; then
  echo "Chrome headless browser: DOWN — no Chrome/Chromium binary found"
  exit 1
fi

chrome_profile_dir="$(mktemp -d "${TMPDIR:-/tmp}/web-advice-chrome-smoke.XXXXXX")"
trap 'rm -rf -- "$chrome_profile_dir"' EXIT
chrome_out="$(
  run_with_timeout 15 "$chrome_bin" \
    --headless=new \
    --disable-gpu \
    --no-first-run \
    --no-default-browser-check \
    --user-data-dir="$chrome_profile_dir" \
    --dump-dom \
    https://example.com/ 2>/dev/null
)"
chrome_rc=$?

if printf '%s' "$chrome_out" | grep -q "Example Domain"; then
  echo "Chrome headless browser: UP — basic render succeeded (rc=${chrome_rc})"
  echo "Vendor authentication/composer proof is still required before /web-advice."
  exit 0
fi

echo "Chrome headless browser: DOWN — rc=${chrome_rc}, basic render failed"
exit 1
