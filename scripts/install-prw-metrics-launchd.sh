#!/usr/bin/env bash
# install-prw-metrics-launchd.sh — Install and bootstrap prw-metrics launchd agent (bd-yq6x).
#
# Follows the 6-step checklist in .claude/skills/launchd/SKILL.md:
# 1. Renders @HOME@ and @REPO_ROOT@ placeholders
# 2. Validates rendered plist with plutil -lint
# 3. Bootouts any existing registration
# 4. Installs rendered plist into ~/Library/LaunchAgents/
# 5. Bootstraps into gui/$(id -u)
# 6. Verifies registration with launchctl list / print

set -euo pipefail

LABEL="com.jleechan.prw-metrics"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLIST_TEMPLATE="$REPO_DIR/launchd/${LABEL}.plist.template"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
PLIST_DEST="$LAUNCH_AGENTS_DIR/${LABEL}.plist"
UID_NUM="$(/usr/bin/id -u)"

if [[ ! -f "$PLIST_TEMPLATE" ]]; then
  echo "ERROR: Plist template not found at $PLIST_TEMPLATE" >&2
  exit 1
fi

mkdir -p "$LAUNCH_AGENTS_DIR"
mkdir -p "$HOME/Library/Logs"

TEMP_PLIST="$(mktemp "${TMPDIR:-/tmp}/prw-metrics-plist.XXXXXX")"
trap 'rm -f "$TEMP_PLIST"' EXIT

echo "Rendering $PLIST_TEMPLATE -> $TEMP_PLIST ..."
sed -e "s|@HOME@|$HOME|g" -e "s|@REPO_ROOT@|$REPO_DIR|g" "$PLIST_TEMPLATE" > "$TEMP_PLIST"

echo "Validating plist with plutil -lint ..."
/usr/bin/plutil -lint "$TEMP_PLIST"

cp "$TEMP_PLIST" "$PLIST_DEST"
chmod 644 "$PLIST_DEST"

echo "Booting out previous registration (if any) ..."
/bin/launchctl bootout "gui/${UID_NUM}/${LABEL}" 2>/dev/null || true

echo "Bootstrapping ${LABEL} into gui/${UID_NUM} ..."
/bin/launchctl bootstrap "gui/${UID_NUM}" "$PLIST_DEST"

echo "Verifying service registration ..."
if /bin/launchctl list | grep -q "$LABEL"; then
  echo "SUCCESS: $LABEL is registered with launchd"
elif /bin/launchctl print "gui/${UID_NUM}/${LABEL}" >/dev/null 2>&1; then
  echo "SUCCESS: $LABEL is registered with launchd (verified via launchctl print)"
else
  echo "WARNING: $LABEL not found in launchctl list or print output"
fi
