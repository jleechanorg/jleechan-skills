#!/usr/bin/env bash
# Thin adapter for Disk Magician's canonical Scratch resolver.
# Disk Magician owns configured-volume availability, admission, and no-Scratch
# fallback semantics; do not duplicate them in a skill helper.

set -euo pipefail

if [ -n "${DISK_MAGICIAN_DISKM_BIN:-}" ]; then
  if [ ! -x "$DISK_MAGICIAN_DISKM_BIN" ]; then
    echo "scratch-dir: configured Disk Magician CLI is unavailable" >&2
    exit 75
  fi
  exec "$DISK_MAGICIAN_DISKM_BIN" scratch-dir "$@"
fi

if command -v diskm >/dev/null 2>&1; then
  exec diskm scratch-dir "$@"
fi
if command -v disk-magician >/dev/null 2>&1; then
  exec disk-magician scratch-dir "$@"
fi

echo "scratch-dir: Disk Magician CLI is unavailable" >&2
exit 75
