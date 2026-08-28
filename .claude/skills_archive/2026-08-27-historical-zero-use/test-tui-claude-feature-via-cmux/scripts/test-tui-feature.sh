#!/usr/bin/env bash
# test-tui-feature.sh — Spawn a Claude Code TUI session in cmux, send a slash
# command, read the result, and clean up. Use for testing TUI-only features
# (slash commands, dialogs, pickers, status indicators) that --print cannot
# exercise.
#
# Usage: test-tui-feature.sh <slash-command> [wait_seconds]
#   <slash-command>  e.g. "/advisor", "/config", "/model"
#   [wait_seconds]   optional, default 2 (how long to wait after sending the
#                    slash command before reading the screen)
#
# Exit codes:
#   0 — slash command sent, screen read returned non-empty
#   1 — cmux command failed or workspace not found
#   2 — slash command did not produce visible output within wait_seconds
#   3 — claude never reached the `❯` prompt within 30s
#
# Environment:
#   CMUX_SOCKET_PATH  — default /private/tmp/cmux-debug-may-18.sock
#   CLAUDE_CWD        — default $PWD (the directory claude should run in)

set -u

SLASH_CMD="${1:-}"
WAIT_SECONDS="${2:-2}"

if [ -z "$SLASH_CMD" ]; then
  echo "Usage: $0 <slash-command> [wait_seconds]" >&2
  echo "  e.g. $0 /advisor" >&2
  exit 1
fi

SOCKET="${CMUX_SOCKET_PATH:-/private/tmp/cmux-debug-may-18.sock}"
CWD="${CLAUDE_CWD:-$PWD}"

# Verify cmux is reachable
if [ ! -S "$SOCKET" ]; then
  echo "cmux socket not found at $SOCKET" >&2
  echo "  override with: CMUX_SOCKET_PATH=/path/to/cmux.sock" >&2
  exit 1
fi

# Verify cmux CLI is on PATH
if ! command -v cmux >/dev/null 2>&1; then
  echo "cmux CLI not found in PATH" >&2
  exit 1
fi

cleanup() {
  if [ -n "${WS:-}" ]; then
    cmux send-key --workspace "$WS" --surface "${SURF:-}" escape >/dev/null 2>&1 || true
    cmux close-workspace --workspace "$WS" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

echo ">>> Spawning claude in cmux workspace..."
WS_OUT=$(cmux new-workspace --cwd "$CWD" --command "claude" 2>&1)
WS=$(echo "$WS_OUT" | grep -oE 'workspace:[0-9]+' | head -1)
if [ -z "$WS" ]; then
  echo "Failed to create workspace: $WS_OUT" >&2
  exit 1
fi
echo "    workspace: $WS"

# Wait for the surface to appear
sleep 2
SURF=$(cmux list-pane-surfaces --workspace "$WS" 2>/dev/null | grep -oE 'surface:[0-9]+' | head -1)
if [ -z "$SURF" ]; then
  echo "No surface found in $WS" >&2
  exit 1
fi
echo "    surface: $SURF"

# Wait for claude to be ready (look for `❯` prompt)
echo ">>> Waiting for claude to be ready..."
READY=0
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
  SCREEN=$(cmux read-screen --workspace "$WS" --surface "$SURF" --scrollback --lines 50 2>/dev/null)
  if echo "$SCREEN" | grep -q "❯"; then
    READY=1
    break
  fi
  sleep 2
done
if [ "$READY" -ne 1 ]; then
  echo "claude did not reach `❯` prompt within 30s" >&2
  echo "  last screen:" >&2
  echo "$SCREEN" | tail -20 >&2
  exit 3
fi
echo "    ready (prompt visible)"

# Send the slash command + Enter
echo ">>> Sending: $SLASH_CMD"
cmux send --workspace "$WS" --surface "$SURF" "$SLASH_CMD" >/dev/null 2>&1
cmux send-key --workspace "$WS" --surface "$SURF" enter >/dev/null 2>&1

# Wait for the result to render
sleep "$WAIT_SECONDS"

# Read the screen
echo ">>> Screen after $SLASH_CMD:"
echo "---"
RESULT=$(cmux read-screen --workspace "$WS" --surface "$SURF" --scrollback --lines 50 2>/dev/null)
echo "$RESULT"
echo "---"

# Validate non-empty result
if [ -z "$RESULT" ] || [ "$(echo "$RESULT" | wc -l)" -lt 2 ]; then
  echo "Slash command produced no visible output" >&2
  exit 2
fi

# Check for the "isn't available in this environment" error — if we see it,
# something is wrong because we ARE in an interactive TUI session
if echo "$RESULT" | grep -q "isn't available in this environment"; then
  echo "ERROR: slash command returned non-interactive error despite being in TUI" >&2
  exit 2
fi

echo ">>> OK"
exit 0
