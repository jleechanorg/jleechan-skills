#!/usr/bin/env bash
# Compatibility entrypoint: stage only; activation is a separate owner action.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ "${1:-}" != "--render-only" ]]; then
  echo "Activation is not performed here. Use --render-only with --config and --output." >&2
  exit 2
fi
shift
exec python3 "$SCRIPT_DIR/render_native_schedule.py" --host linux "$@"
