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

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLIST_TEMPLATE="${1:-$REPO_DIR/launchd/com.jleechan.prw-metrics.plist.template}"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
UID_NUM="$(/usr/bin/id -u)"

if [[ ! -f "$PLIST_TEMPLATE" ]]; then
  echo "ERROR: Plist template not found at $PLIST_TEMPLATE" >&2
  exit 1
fi

TEMP_PLIST="$(mktemp "${TMPDIR:-/tmp}/prw-metrics-plist.XXXXXX")"
trap 'rm -f "$TEMP_PLIST"' EXIT

echo "Rendering $PLIST_TEMPLATE -> $TEMP_PLIST ..."
LABEL="$(python3 - "$PLIST_TEMPLATE" "$TEMP_PLIST" "$HOME" "$REPO_DIR" <<'PY'
import plistlib, sys
tpl_path, dest_path, home_val, repo_val = sys.argv[1:5]
with open(tpl_path, "rb") as f:
    data = plistlib.load(f)
if not isinstance(data, dict) or not data.get("Label") or not isinstance(data.get("Label"), str):
    sys.exit(1)
def replace_tokens(obj):
    if isinstance(obj, str):
        return obj.replace("@HOME@", home_val).replace("@REPO_ROOT@", repo_val)
    if isinstance(obj, list):
        return [replace_tokens(x) for x in obj]
    if isinstance(obj, dict):
        return {k: replace_tokens(v) for k, v in obj.items()}
    return obj
rendered = replace_tokens(data)
with open(dest_path, "wb") as f:
    plistlib.dump(rendered, f, sort_keys=False)
print(rendered["Label"])
PY
)" || {
    echo "ERROR: Could not parse Label or render plist from $PLIST_TEMPLATE" >&2
    exit 1
}

PLIST_DEST="$LAUNCH_AGENTS_DIR/${LABEL}.plist"

mkdir -p "$LAUNCH_AGENTS_DIR"
mkdir -p "$HOME/Library/Logs"

if [[ -x /usr/bin/plutil ]]; then
  echo "Validating plist with plutil -lint ..."
  /usr/bin/plutil -lint "$TEMP_PLIST"
fi

cp "$TEMP_PLIST" "$PLIST_DEST"
chmod 644 "$PLIST_DEST"

echo "Booting out previous registration (if any) ..."
/bin/launchctl bootout "gui/${UID_NUM}/${LABEL}" 2>/dev/null || true

echo "Bootstrapping ${LABEL} into gui/${UID_NUM} ..."
/bin/launchctl bootstrap "gui/${UID_NUM}" "$PLIST_DEST"

echo "Verifying service registration ..."
if /bin/launchctl print "gui/${UID_NUM}/${LABEL}" >/dev/null 2>&1; then
  echo "SUCCESS: $LABEL is registered with launchd (verified via launchctl print)"
else
  echo "ERROR: Failed to verify service registration for $LABEL" >&2
  exit 1
fi
