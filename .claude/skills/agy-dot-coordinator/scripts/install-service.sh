#!/usr/bin/env bash
# .claude/skills/agy-dot-coordinator/scripts/install-service.sh
# Cross-platform service installer for ai.gemini.agy-dot-coordinator
# Auto-detects macOS (launchd) vs Linux (systemd user timer)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OS="$(uname -s)"

case "$OS" in
  Darwin)
    echo "Detected macOS. Installing via launchd..."
    exec /bin/bash "$SCRIPT_DIR/install-launchagent.sh" "$@"
    ;;
  Linux)
    echo "Detected Linux. Installing via systemd user timer..."
    exec /bin/bash "$SCRIPT_DIR/install-systemd.sh" "$@"
    ;;
  *)
    echo "Unsupported operating system: $OS" >&2
    exit 1
    ;;
esac
