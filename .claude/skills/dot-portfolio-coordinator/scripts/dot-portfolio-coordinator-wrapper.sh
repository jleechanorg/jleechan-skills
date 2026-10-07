#!/usr/bin/env bash
# dot-portfolio-coordinator-wrapper.sh
# Supervision wrapper with flock, shared deadline, and clean descendant process termination.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_CLI="$SCRIPT_DIR/coordinator-portfolio.py"
LOCKFILE="/tmp/ai.gemini.dot-portfolio-coordinator.lock"
DEADLINE_SECS=600

# Concurrency lease
exec 200>"$LOCKFILE"
if command -v flock >/dev/null 2>&1; then
  if ! flock -n 200; then
    echo "[dot-portfolio-coordinator] Another coordinator instance is active. Exiting."
    exit 0
  fi
fi

# Process group supervision and cleanup on interrupt / exit
CHILD_PID=""
cleanup() {
  if [[ -n "$CHILD_PID" ]] && kill -0 "$CHILD_PID" 2>/dev/null; then
    echo "[dot-portfolio-coordinator] Cleaning up child process tree ($CHILD_PID)..." >&2
    pkill -P "$CHILD_PID" 2>/dev/null || true
    kill -TERM "$CHILD_PID" 2>/dev/null || true
    sleep 1
    kill -KILL "$CHILD_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

# Run target CLI under timeout
if command -v timeout >/dev/null 2>&1; then
  timeout "$DEADLINE_SECS" python3 "$PYTHON_CLI" "$@" &
  CHILD_PID=$!
  wait "$CHILD_PID"
else
  python3 "$PYTHON_CLI" "$@" &
  CHILD_PID=$!
  wait "$CHILD_PID"
fi
