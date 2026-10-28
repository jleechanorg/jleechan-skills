#!/usr/bin/env bash
# Canonical single-source-of-truth resolver for agent scratch/temp directories.
# Resolves the provisioned diskm Scratch volume via `diskm volume path scratch`
# (or ~/.config/disk-magician/config.json), falling back to /tmp only when no
# Scratch volume is configured on the host.
#
# Usage:
#   diskm scratch-dir            # prints scratch root (e.g. /Volumes/diskm-scratch, ~/Scratch, or /tmp)
#   diskm scratch-dir <subpath>  # mkdir -p <scratch-root>/<subpath> and prints it

set -euo pipefail

resolve_scratch_root() {
  local root="${DISKM_SCRATCH:-}"
  if [ -n "$root" ] && [ -d "$root" ] && [ -w "$root" ]; then
    printf '%s\n' "$root"
    return 0
  fi

  root=""
  local script_dir diskm_bin
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  diskm_bin="${DISK_MAGICIAN_DISKM_BIN:-}"
  if [ -n "$diskm_bin" ] && [ -x "$diskm_bin" ]; then
    root="$("$diskm_bin" volume path scratch 2>/dev/null || true)"
  elif [ -x "$script_dir/../disk_magician.sh" ]; then
    root="$("$script_dir/../disk_magician.sh" volume path scratch 2>/dev/null || true)"
  elif command -v diskm >/dev/null 2>&1; then
    root="$(diskm volume path scratch 2>/dev/null || true)"
  elif command -v disk-magician >/dev/null 2>&1; then
    root="$(disk-magician volume path scratch 2>/dev/null || true)"
  elif [ -x "${HOME}/.local/bin/diskm" ]; then
    root="$("${HOME}/.local/bin/diskm" volume path scratch 2>/dev/null || true)"
  elif [ -x "${HOME}/.local/bin/disk-magician" ]; then
    root="$("${HOME}/.local/bin/disk-magician" volume path scratch 2>/dev/null || true)"
  fi

  if [ -z "$root" ]; then
    local cfg="${DISK_MAGICIAN_CONFIG:-${HOME}/.config/disk-magician/config.json}"
    if [ -f "$cfg" ] && command -v jq >/dev/null 2>&1; then
      root="$(jq -r '.volumes.classes.scratch.mountpoint // .volumes.scratch.mountpoint // empty' "$cfg" 2>/dev/null || true)"
    fi
  fi

  if [ -n "$root" ] && [ -d "$root" ] && [ -w "$root" ]; then
    printf '%s\n' "$root"
    return 0
  fi

  if [ -z "${DISK_MAGICIAN_DISKM_BIN:-}" ] && [ -z "${DISK_MAGICIAN_CONFIG:-}" ]; then
    for candidate in "/Volumes/diskm-scratch" "${HOME}/Scratch"; do
      if [ -d "$candidate" ] && [ -w "$candidate" ]; then
        printf '%s\n' "$candidate"
        return 0
      fi
    done
  fi

  printf '/tmp\n'
}

SCRATCH_ROOT="$(resolve_scratch_root)"

if [ "$#" -gt 0 ]; then
  if [ -z "${1:-}" ]; then
    echo "scratch-dir: invalid subpath: (empty)" >&2
    exit 2
  fi
  SUBPATH="${1#/}"
  case "$SUBPATH" in
    ""|*..*)
      echo "scratch-dir: invalid subpath: $1" >&2
      exit 2
      ;;
  esac
  TARGET="${SCRATCH_ROOT%/}/${SUBPATH}"
  mkdir -p "$TARGET"
  printf '%s\n' "$TARGET"
else
  printf '%s\n' "$SCRATCH_ROOT"
fi
