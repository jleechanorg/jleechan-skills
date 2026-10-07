#!/usr/bin/env bash
# dot-portfolio-coordinator-sender.sh
# Hardened, receipt-safe message delivery subcomponent delegating to Python sender worker.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/modules/sender.py" "$@"
