#!/usr/bin/env bash
# Runner for the PRW metrics job: PATH, single-instance lock, run the script, log. Arguments pass through.
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATE_DIR="${PRW_METRICS_STATE_DIR:-$HOME/.local/share/prw-metrics-slim}"
mkdir -p "$STATE_DIR"

# Kernel-held advisory lock: released automatically when this process exits.
exec 9>>"$STATE_DIR/run.lock"
if ! python3 -c 'import fcntl; fcntl.flock(9, fcntl.LOCK_EX | fcntl.LOCK_NB)' 2>/dev/null; then
  echo "$(date -u +%FT%TZ) another prw-metrics run holds the lock; exiting"
  exit 0
fi

echo "$(date -u +%FT%TZ) prw-metrics start"
status=0
python3 "$SCRIPT_DIR/prw_metrics.py" "$@" || status=$?
echo "$(date -u +%FT%TZ) prw-metrics exit $status"
exit "$status"
