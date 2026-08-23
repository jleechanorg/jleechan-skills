#!/usr/bin/env bash
# disk-audit — disk usage analysis + cleanup preview
#
# Usage:
#   disk-audit              # dry-run preview (default)
#   disk-audit --clean      # interactive cleanup (asks before each deletion)
#   disk-audit --clean-all  # aggressive cleanup including Docker prune
#
# Default (no args): runs --clean --dry-run — shows what would be deleted, deletes nothing
#
# Always: never suggest ~/.codex/sessions_archive/ as a cleanup target

SCRIPT="$HOME/projects_other/user_scope/scripts/disk_audit.sh"
exec "$SCRIPT" "$@"