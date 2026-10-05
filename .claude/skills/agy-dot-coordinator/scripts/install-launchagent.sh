#!/usr/bin/env bash
# .claude/skills/agy-dot-coordinator/scripts/install-launchagent.sh
# Canonical installer for ai.gemini.agy-dot-coordinator LaunchAgent
set -euo pipefail

LABEL="ai.gemini.agy-dot-coordinator"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE="$SCRIPT_DIR/../launchd/${LABEL}.plist"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
PLIST_DST="$LAUNCH_AGENTS_DIR/${LABEL}.plist"
UID_NUM="$(/usr/bin/id -u)"

echo "=== Installing $LABEL LaunchAgent ==="

if [[ ! -f "$TEMPLATE" ]]; then
  echo "ERROR: Plist template missing: $TEMPLATE" >&2
  exit 1
fi

# Ensure scripts are executable
chmod +x "$SCRIPT_DIR/agy-dot-coordinator-wrapper.sh"
chmod +x "$SCRIPT_DIR/agy-dot-coordinator-worker.sh"

mkdir -p "$LAUNCH_AGENTS_DIR"
mkdir -p "$HOME/Library/Logs"

# 1. Render template replacing @HOME@ placeholder
echo "Rendering $TEMPLATE -> $PLIST_DST"
sed "s|@HOME@|$HOME|g" "$TEMPLATE" > "$PLIST_DST"

# 2. Clean bootout of existing service (canonical standard)
echo "Booting out existing registration (if any)..."
/bin/launchctl bootout "gui/$UID_NUM/$LABEL" 2>/dev/null || true

# Short settle
sleep 1

# 3. Bootstrap new plist
echo "Bootstrapping $PLIST_DST into gui/$UID_NUM..."
/bin/launchctl bootstrap "gui/$UID_NUM" "$PLIST_DST"

# 4. Verify status
echo "Verifying registration..."
if /bin/launchctl list | grep -q "$LABEL"; then
  echo "SUCCESS: $LABEL is registered."
  /bin/launchctl list | grep "$LABEL"
else
  echo "ERROR: $LABEL not found in launchctl list!" >&2
  exit 1
fi

echo "=== Installation Complete ==="
