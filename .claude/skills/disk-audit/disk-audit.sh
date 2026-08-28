#!/usr/bin/env bash
# disk-audit — wrapper for disk_audit.sh
# Usage: disk-audit [args]
# Defaults to --clean --dry-run if no args given

SCRIPT="$HOME/projects_other/user_scope/scripts/disk_audit.sh"

if [ $# -eq 0 ]; then
    exec "$SCRIPT" --clean --dry-run
else
    exec "$SCRIPT" "$@"
fi