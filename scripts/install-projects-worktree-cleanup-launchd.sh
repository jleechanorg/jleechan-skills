#!/usr/bin/env bash
# install-projects-worktree-cleanup-launchd.sh — Install and bootstrap worktree cleanup launchd agent.
#
# Follows the 6-step checklist in .claude/skills/launchd/SKILL.md:
# 1. Renders @HOME@ placeholders to $HOME
# 2. Bootouts any existing registration
# 3. Copies rendered plist to ~/Library/LaunchAgents/
# 4. Bootstraps into gui/$(id -u)

set -euo pipefail

LABEL="com.jleechan.cleanup-projects-worktrees"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLIST_TEMPLATE="$REPO_DIR/launchd/${LABEL}.plist"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
PLIST_DEST="$LAUNCH_AGENTS_DIR/${LABEL}.plist"
UID_NUM="$(/usr/bin/id -u)"

if [[ ! -f "$PLIST_TEMPLATE" ]]; then
  echo "ERROR: Plist template not found at $PLIST_TEMPLATE" >&2
  exit 1
fi

mkdir -p "$LAUNCH_AGENTS_DIR"

echo "Rendering $PLIST_TEMPLATE -> $PLIST_DEST ..."
sed "s|@HOME@|$HOME|g" "$PLIST_TEMPLATE" > "$PLIST_DEST"
chmod 644 "$PLIST_DEST"

echo "Booting out previous registration (if any) ..."
/bin/launchctl bootout "gui/${UID_NUM}/${LABEL}" 2>/dev/null || true

echo "Bootstrapping ${LABEL} into gui/${UID_NUM} ..."
/bin/launchctl bootstrap "gui/${UID_NUM}" "$PLIST_DEST"

echo "Verifying service registration ..."
if /bin/launchctl list | grep -q "$LABEL"; then
  echo "SUCCESS: $LABEL is registered with launchd"
else
  echo "WARNING: $LABEL not found in launchctl list output"
fi
