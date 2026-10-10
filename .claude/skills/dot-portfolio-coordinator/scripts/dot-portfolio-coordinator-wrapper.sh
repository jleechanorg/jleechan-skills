#!/usr/bin/env bash
# Bound the finite controller; its private run lock owns concurrency.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_CLI="$SCRIPT_DIR/coordinator-portfolio.py"
DEADLINE_SECS=600
IS_OBSERVE=0
DURATION=43200
PREV_ARG=""
for arg in "$@"; do
  if [[ "$arg" == "observe" ]]; then IS_OBSERVE=1; fi
  if [[ "$PREV_ARG" == "--duration" ]]; then DURATION="$arg"; fi
  if [[ "$arg" == --duration=* ]]; then DURATION="${arg#--duration=}"; fi
  PREV_ARG="$arg"
done
if [[ ! "$DURATION" =~ ^[0-9]+$ ]] || (( DURATION < 1 || DURATION > 43200 )); then
  echo "Invalid finite duration" >&2
  exit 2
fi
if [[ "$IS_OBSERVE" -eq 1 ]]; then
  DEADLINE_SECS=$(( DURATION + 120 ))
fi
TIMEOUT_BIN="$(command -v timeout || command -v gtimeout || true)"
if [[ -z "$TIMEOUT_BIN" ]]; then
  echo "A bounded timeout executable is required" >&2
  exit 2
fi
exec "$TIMEOUT_BIN" --signal=TERM --kill-after=10 "$DEADLINE_SECS" python3 "$PYTHON_CLI" "$@"
