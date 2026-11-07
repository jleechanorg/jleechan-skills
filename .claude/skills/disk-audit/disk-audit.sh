#!/usr/bin/env bash
# disk-audit — wrapper for disk_audit.sh from your user-scope checkout
# Usage: disk-audit [args]
# Requires USER_SCOPE_ROOT (the checkout that provides scripts/disk_audit.sh).
# Defaults to --clean --dry-run if no args given

if [ -z "${USER_SCOPE_ROOT:-}" ]; then
    echo "USER_SCOPE_ROOT not configured: checkout that provides scripts/disk_audit.sh. Example: export USER_SCOPE_ROOT=\$HOME/src/user_scope" >&2
    exit 2
fi
SCRIPT="$USER_SCOPE_ROOT/scripts/disk_audit.sh"
if [ ! -x "$SCRIPT" ]; then
    echo "disk-audit: $SCRIPT not found or not executable (check USER_SCOPE_ROOT)" >&2
    exit 2
fi

if [ $# -eq 0 ]; then
    exec "$SCRIPT" --clean --dry-run
else
    exec "$SCRIPT" "$@"
fi
