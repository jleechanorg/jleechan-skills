#!/usr/bin/env bash
# .claude/skills/agy-dot-coordinator/scripts/agy-dot-coordinator-worker.sh
# Periodic worker invoking agy CLI to coordinate with ChatGPT dot assistant.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATE_DIR="$HOME/.local/state/ai.gemini.agy-dot-coordinator"
STATE_FILE="$STATE_DIR/state.json"
COOLDOWN_SECS=7200 # 2 hours debounce between reminders

if [[ -f "$SCRIPT_DIR/../../dot/scripts/dot.sh" ]]; then
  DOT_SCRIPT="$SCRIPT_DIR/../../dot/scripts/dot.sh"
elif [[ -f "$HOME/.claude/skills/dot/scripts/dot.sh" ]]; then
  DOT_SCRIPT="$HOME/.claude/skills/dot/scripts/dot.sh"
else
  DOT_SCRIPT="$HOME/.claude/skills/dot/scripts/dot.sh"
fi

mkdir -p "$STATE_DIR"

FORCE=0
DRY_RUN=0
STATUS_ONLY=0

for arg in "$@"; do
  case "$arg" in
    --force) FORCE=1 ;;
    --dry-run) DRY_RUN=1 ;;
    --status) STATUS_ONLY=1 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

# Helper to read state
read_last_sent() {
  if [[ -f "$STATE_FILE" ]]; then
    python3 -c 'import json, sys; s=json.load(open("'"$STATE_FILE"'")); print(s.get("last_sent_epoch", 0))' 2>/dev/null || echo 0
  else
    echo 0
  fi
}

write_state() {
  local epoch="$1"
  local status="$2"
  python3 -c '
import json, sys, time
data = {
    "last_sent_epoch": int(sys.argv[1]),
    "last_sent_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(sys.argv[1]))),
    "last_status": sys.argv[2]
}
with open("'"$STATE_FILE"'", "w") as f:
    json.dump(data, f, indent=2)
' "$epoch" "$status"
}

NOW=$(date +%s)
LAST_SENT=$(read_last_sent)
ELAPSED=$((NOW - LAST_SENT))

echo "=== agy-dot-coordinator tick at $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
echo "State file: $STATE_FILE (last sent ${ELAPSED}s ago, cooldown ${COOLDOWN_SECS}s)"

if [[ "$STATUS_ONLY" -eq 1 ]]; then
  echo "Elapsed: ${ELAPSED}s | Cooldown: ${COOLDOWN_SECS}s"
  exit 0
fi

# 1. Read dot state
echo "Checking dot state via $DOT_SCRIPT read 2000..."
DOT_TAIL=""
if ! DOT_TAIL=$(timeout 45 "$DOT_SCRIPT" read 2000 2>&1); then
  echo "WARNING: Failed to read dot state: $DOT_TAIL" >&2
  # Do not crash; record and exit 0 so launchd doesn't rapidly retry
  exit 0
fi

# Check if dot is actively thinking / working
IS_ACTIVE=0
if echo "$DOT_TAIL" | grep -qiE "Thinking|Working|Searching"; then
  IS_ACTIVE=1
  echo "Dot assistant appears to be actively working/searching/thinking."
fi

# Check gating
if [[ "$FORCE" -eq 0 ]]; then
  if [[ "$IS_ACTIVE" -eq 1 && "$ELAPSED" -lt "$COOLDOWN_SECS" ]]; then
    echo "Dot is actively working and cooldown (${ELAPSED}/${COOLDOWN_SECS}s) is active. Skipping check-in."
    exit 0
  fi

  if [[ "$ELAPSED" -lt "$COOLDOWN_SECS" ]]; then
    echo "Cooldown active (${ELAPSED}/${COOLDOWN_SECS}s elapsed). Skipping check-in."
    exit 0
  fi
fi

echo "Triggering agy coordinator prompt..."

PROMPT="You are the Antigravity (agy) coordinator.
Communicate with the ChatGPT coordinator (the dot) using the /dot skill.
Instructions:
1. Inspect what the dot is doing by reading its conversation with /dot.
2. Formulate and send a structured message starting with 'From Gemini (Antigravity Coordinator):':
   - Inquire what work is currently in flight and what the active priorities are.
   - Remind the dot to keep driving work forward in strict priority order using its cloud computer.
   - Remind the dot to set up the cloud computer environment with everything needed (repositories, tools, dependencies, and test harnesses) and to strictly prefer driving execution there.
3. Make sure the message is sent cleanly using dot.sh with DOT_WAIT_SECS=60 and report the verified result."

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[DRY-RUN] Would run agy -p with prompt:"
  echo "$PROMPT"
  exit 0
fi

# Set DOT_WAIT_SECS and DOT_RETRY_SECS in environment so child scripts don't hang
export DOT_WAIT_SECS=60
export DOT_RETRY_SECS=15

# Run agy with timeout
AGY_OUT=""
AGY_RC=0
AGY_OUT=$(timeout 360 agy -p "$PROMPT" --dangerously-skip-permissions --print-timeout 300s 2>&1) || AGY_RC=$?

echo "agy finished with exit code $AGY_RC"
echo "=== agy output ==="
echo "$AGY_OUT"
echo "=================="

if [[ "$AGY_RC" -eq 0 ]]; then
  write_state "$NOW" "SUCCESS"
  echo "Successfully completed dot check-in at $(date)."
else
  # Check if failure was just composer busy
  if echo "$AGY_OUT" | grep -qi "DOT_DRAFT_PRESENT"; then
    echo "Dot composer busy with peer draft; gracefully skipping this tick."
    write_state "$LAST_SENT" "SKIPPED_COMPOSER_BUSY"
  else
    echo "agy coordinator encountered an error or timeout (code $AGY_RC)."
    write_state "$LAST_SENT" "ERROR_RC_$AGY_RC"
  fi
fi

exit 0
