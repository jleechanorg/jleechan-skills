#!/usr/bin/env bash
# install-instinct-ping-launchd.sh — install and bootstrap the instinct-ping agent.
#
# Follows .claude/skills/launchd/SKILL.md:
# 1. Render @HOME@ placeholders        2. plutil -lint the rendered plist
# 3. bootout any existing registration 4. install into ~/Library/LaunchAgents
# 5. bootstrap into gui/$(id -u)       6. verify the registration
set -euo pipefail

LABEL="ai.jleechan.instinct-ping"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATE="$REPO_DIR/launchd/${LABEL}.plist"
WRAPPER_SRC="$REPO_DIR/scripts/instinct-ping.sh"
WRAPPER_DST="$HOME/.local/bin/instinct-ping.sh"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
PLIST_DEST="$LAUNCH_AGENTS_DIR/${LABEL}.plist"
UID_NUM="$(/usr/bin/id -u)"

[[ -f "$TEMPLATE" ]] || { echo "ERROR: template missing at $TEMPLATE" >&2; exit 1; }
[[ -f "$WRAPPER_SRC" ]] || { echo "ERROR: wrapper missing at $WRAPPER_SRC" >&2; exit 1; }

# Refuse installation before creating or replacing any launchd files unless the
# scheduled job has a complete machine-local task and recipient configuration.
"$WRAPPER_SRC" validate-config || {
  echo "ERROR: configure $HOME/.config/instinct-ping/config.json before installation" >&2
  exit 1
}

mkdir -p "$LAUNCH_AGENTS_DIR" "$HOME/.local/bin" "$HOME/.local/state/instinct-ping"

# The wrapper is sourced from this repo and copied into place, so the installed
# job always runs the committed version. Never hand-edit the installed copy.
install -m 0755 "$WRAPPER_SRC" "$WRAPPER_DST"

TMP_PLIST="$(mktemp "${TMPDIR:-/tmp}/instinct-ping-plist.XXXXXX")"
trap 'rm -f "$TMP_PLIST"' EXIT
sed "s|@HOME@|$HOME|g" "$TEMPLATE" > "$TMP_PLIST"

/usr/bin/plutil -lint "$TMP_PLIST" >/dev/null || { echo "ERROR: rendered plist failed plutil -lint" >&2; exit 1; }
/usr/bin/install -m 0644 "$TMP_PLIST" "$PLIST_DEST"

/bin/launchctl bootout "gui/${UID_NUM}/${LABEL}" 2>/dev/null || true
/bin/launchctl bootstrap "gui/${UID_NUM}" "$PLIST_DEST"
/bin/launchctl enable "gui/${UID_NUM}/${LABEL}" 2>/dev/null || true

if /bin/launchctl print "gui/${UID_NUM}/${LABEL}" >/dev/null 2>&1; then
  echo "installed and bootstrapped: ${LABEL}"
  echo "  plist:   $PLIST_DEST"
  echo "  wrapper: $WRAPPER_DST"
  echo "  interval: 1200s (20 min)"
  echo "  state:   $HOME/.local/state/instinct-ping/"
  echo
  echo "operate:  $WRAPPER_DST status|done|reset"
else
  echo "ERROR: ${LABEL} failed to bootstrap" >&2
  exit 1
fi
