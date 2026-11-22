#!/usr/bin/env bash
# Runner for the local usage collector: PATH, run prw_local_usage.py with the given arguments, log start/exit.
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "$(date -u +%FT%TZ) prw-local-usage start"
status=0
python3 "$SCRIPT_DIR/prw_local_usage.py" "$@" || status=$?
echo "$(date -u +%FT%TZ) prw-local-usage exit $status"
exit "$status"
