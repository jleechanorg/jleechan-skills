#!/usr/bin/env bash
# .claude/skills/agy-dot-coordinator/scripts/install-systemd.sh
# Canonical installer for ai.gemini.agy-dot-coordinator systemd user service + timer
set -euo pipefail

UNIT_NAME="ai.gemini.agy-dot-coordinator"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_TEMPLATE="$SCRIPT_DIR/../systemd/${UNIT_NAME}.service"
TIMER_TEMPLATE="$SCRIPT_DIR/../systemd/${UNIT_NAME}.timer"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"

echo "=== Installing $UNIT_NAME systemd user service and timer ==="

if [[ ! -f "$SERVICE_TEMPLATE" || ! -f "$TIMER_TEMPLATE" ]]; then
  echo "ERROR: Unit templates missing from $SCRIPT_DIR/../systemd" >&2
  exit 1
fi

chmod +x "$SCRIPT_DIR/agy-dot-coordinator-wrapper.sh"
chmod +x "$SCRIPT_DIR/agy-dot-coordinator-worker.sh"

mkdir -p "$SYSTEMD_USER_DIR"

echo "Disabling existing units..."
systemctl --user disable --now "${UNIT_NAME}.timer" 2>/dev/null || true
systemctl --user stop "${UNIT_NAME}.service" 2>/dev/null || true

echo "Copying unit files to $SYSTEMD_USER_DIR..."
sed "s|@HOME@|$HOME|g" "$SERVICE_TEMPLATE" > "$SYSTEMD_USER_DIR/${UNIT_NAME}.service"
sed "s|@HOME@|$HOME|g" "$TIMER_TEMPLATE" > "$SYSTEMD_USER_DIR/${UNIT_NAME}.timer"

echo "Reloading systemd user daemon..."
systemctl --user daemon-reload

echo "Enabling and starting timer..."
systemctl --user enable --now "${UNIT_NAME}.timer"

echo "Verifying timer status..."
systemctl --user list-timers "${UNIT_NAME}.timer"

echo "=== Systemd Installation Complete ==="
