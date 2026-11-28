#!/usr/bin/env bash
# Runner for the local usage collector: PATH, single-instance lock, run prw_local_usage.py with the given arguments, log start/exit.
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/prw-local-usage"
mkdir -p "$STATE_DIR"

# Kernel-held advisory lock: released automatically when this process exits.
exec 9>>"$STATE_DIR/run.lock"
if ! python3 -c 'import fcntl; fcntl.flock(9, fcntl.LOCK_EX | fcntl.LOCK_NB)' 2>/dev/null; then
  echo "$(date -u +%FT%TZ) another prw-local-usage run holds the lock; exiting"
  exit 0
fi

echo "$(date -u +%FT%TZ) prw-local-usage start"
status=0
python3 "$SCRIPT_DIR/prw_local_usage.py" "$@" || status=$?
echo "$(date -u +%FT%TZ) prw-local-usage exit $status"
exit "$status"
