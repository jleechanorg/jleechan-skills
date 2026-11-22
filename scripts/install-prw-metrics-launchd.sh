#!/usr/bin/env bash
# Install the slim PRW metrics launchd job under its own label (com.jleechan.prw-metrics-slim).
# Installing never loads or starts anything; only --activate enables and bootstraps the slim label.
# The old com.jleechan.prw-metrics label is never written, loaded or unloaded here.
#
# Usage: install-prw-metrics-launchd.sh --repos a/b,c/d --roadmap-remote URL [--roadmap-branch main]
#          [--source-repo PATH] [--source-rev REV] [--dry-run] [--replace-slim] [--activate]
set -euo pipefail

LABEL="com.jleechan.prw-metrics-slim"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATE="$REPO_DIR/launchd/$LABEL.plist.template"
SOURCE_REPO="$REPO_DIR"
SOURCE_REV="origin/main"
REPOS="" REMOTE="" BRANCH="main"
DRY_RUN=0 REPLACE=0 ACTIVATE=0

die() { echo "ERROR: $*" >&2; exit 1; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repos) REPOS="${2:?}"; shift 2 ;;
    --roadmap-remote) REMOTE="${2:?}"; shift 2 ;;
    --roadmap-branch) BRANCH="${2:?}"; shift 2 ;;
    --source-repo) SOURCE_REPO="${2:?}"; shift 2 ;;
    --source-rev) SOURCE_REV="${2:?}"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    --replace-slim) REPLACE=1; shift ;;
    --activate) ACTIVATE=1; shift ;;
    *) die "unknown argument: $1" ;;
  esac
done
[[ -n "$REPOS" ]] || die "--repos is required"
[[ -n "$REMOTE" ]] || die "--roadmap-remote is required"
[[ -f "$TEMPLATE" ]] || die "template not found: $TEMPLATE"

SHA="$(git -C "$SOURCE_REPO" rev-parse --verify "${SOURCE_REV}^{commit}")" || die "cannot resolve $SOURCE_REV"
RELEASE_DIR="$HOME/.local/share/prw-metrics-slim/releases/$SHA"
PLIST_DEST="$HOME/Library/LaunchAgents/$LABEL.plist"
UID_NUM="$(/usr/bin/id -u)"

render() {
  python3 - "$TEMPLATE" "$HOME" "$RELEASE_DIR" "$REPOS" "$REMOTE" "$BRANCH" <<'PY'
import plistlib, sys
tpl, home, release, repos, remote, branch = sys.argv[1:7]
subs = {"@HOME@": home, "@RELEASE_DIR@": release, "@REPOS@": repos,
        "@ROADMAP_REMOTE@": remote, "@ROADMAP_BRANCH@": branch}
def fill(obj):
    if isinstance(obj, str):
        for key, val in subs.items():
            obj = obj.replace(key, val)
        return obj
    if isinstance(obj, list):
        return [fill(x) for x in obj]
    if isinstance(obj, dict):
        return {k: fill(v) for k, v in obj.items()}
    return obj
with open(tpl, "rb") as f:
    sys.stdout.buffer.write(plistlib.dumps(fill(plistlib.load(f)), sort_keys=False))
PY
}

if [[ "$DRY_RUN" == 1 ]]; then
  render
  exit 0
fi

if launchctl print "gui/$UID_NUM/$LABEL" >/dev/null 2>&1; then
  LOADED=1
  [[ "$REPLACE" == 1 ]] || die "$LABEL is already loaded; pass --replace-slim to reinstall"
else
  LOADED=0
fi

mkdir -p "$RELEASE_DIR" "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
git -C "$SOURCE_REPO" archive "$SHA" scripts | tar -x -C "$RELEASE_DIR"
python3 "$RELEASE_DIR/scripts/prw_metrics.py" --help

render > "$PLIST_DEST.tmp"
if [[ -x /usr/bin/plutil ]]; then /usr/bin/plutil -lint "$PLIST_DEST.tmp" >/dev/null; fi
mv "$PLIST_DEST.tmp" "$PLIST_DEST"
chmod 644 "$PLIST_DEST"
echo "installed $LABEL at release $SHA (not loaded)"

if [[ "$ACTIVATE" == 1 ]]; then
  [[ "$LOADED" == 0 ]] || launchctl bootout "gui/$UID_NUM/$LABEL"
  launchctl enable "gui/$UID_NUM/$LABEL"
  launchctl bootstrap "gui/$UID_NUM" "$PLIST_DEST"
  echo "activated $LABEL"
fi
