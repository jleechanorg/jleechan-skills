#!/usr/bin/env bash
# Install the slim PRW metrics launchd job under its own label (com.jleechan.prw-metrics-slim).
# Installing never loads or starts anything; only --activate enables and bootstraps the slim label.
# The old com.jleechan.prw-metrics label is never written, loaded or unloaded here.
#
# Usage: install-prw-metrics-launchd.sh --repos a/b,c/d --roadmap-remote URL [--roadmap-branch main]
#          [--usage-remote URL]
#          [--source-repo PATH] [--source-rev REV] [--dry-run] [--replace-slim] [--activate]
set -euo pipefail

LABEL="com.jleechan.prw-metrics-slim"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATE="$REPO_DIR/launchd/$LABEL.plist.template"
SOURCE_REPO="$REPO_DIR"
SOURCE_REV="origin/main"
REPOS="" REMOTE="" BRANCH="main" USAGE_REMOTE=""
DRY_RUN=0 REPLACE=0 ACTIVATE=0

die() { echo "ERROR: $*" >&2; exit 1; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repos) REPOS="${2:?}"; shift 2 ;;
    --roadmap-remote) REMOTE="${2:?}"; shift 2 ;;
    --roadmap-branch) BRANCH="${2:?}"; shift 2 ;;
    --usage-remote) USAGE_REMOTE="${2:?}"; shift 2 ;;
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

# Same rule as prw_metrics.embeds_credentials; both remotes land in a readable plist.
for pair in "--usage-remote=$USAGE_REMOTE" "--roadmap-remote=$REMOTE"; do
  [[ -n "${pair#*=}" ]] || continue
  if python3 - "${pair#*=}" <<'PY'
import re, sys
url = sys.argv[1]
m = re.match(r"^([A-Za-z][A-Za-z0-9+.-]*)://([^/]*)", url)
if not m:
    user = re.match(r"^([^@/]*)@", url)
    bad = bool(user and ":" in user.group(1))
elif "@" not in m.group(2):
    bad = False
else:
    user = m.group(2).rsplit("@", 1)[0]
    bad = ":" in user or m.group(1).lower().split("+")[-1] in ("http", "https")
sys.exit(0 if bad else 1)
PY
  then
    echo "ERROR: ${pair%%=*} must not embed credentials" >&2
    exit 2
  fi
done

SHA="$(git -C "$SOURCE_REPO" rev-parse --verify "${SOURCE_REV}^{commit}")" || die "cannot resolve $SOURCE_REV"
RELEASE_DIR="$HOME/.local/share/prw-metrics-slim/releases/$SHA"
PLIST_DEST="$HOME/Library/LaunchAgents/$LABEL.plist"
UID_NUM="$(/usr/bin/id -u)"

render() {
  python3 - "$TEMPLATE" "$HOME" "$RELEASE_DIR" "$REPOS" "$REMOTE" "$BRANCH" "$USAGE_REMOTE" <<'PY'
import plistlib, sys
tpl, home, release, repos, remote, branch, usage = sys.argv[1:8]
subs = {"@HOME@": home, "@RELEASE_DIR@": release, "@REPOS@": repos,
        "@ROADMAP_REMOTE@": remote, "@ROADMAP_BRANCH@": branch,
        "@USAGE_REMOTE@": usage}
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
    plist = fill(plistlib.load(f))
if not usage:  # optional: drop the flag and its value
    args = plist["ProgramArguments"]
    i = args.index("--usage-remote")
    del args[i:i + 2]
sys.stdout.buffer.write(plistlib.dumps(plist, sort_keys=False))
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

mkdir -p "$RELEASE_DIR" "$HOME/Library/Logs"
git -C "$SOURCE_REPO" archive "$SHA" scripts | tar -x -C "$RELEASE_DIR"
python3 "$RELEASE_DIR/scripts/prw_metrics.py" --help

# Stage the plist inside the release directory. It is copied into ~/Library/LaunchAgents only by
# --activate, because launchd loads everything in that folder at the next login.
STAGED="$RELEASE_DIR/$LABEL.plist"
render > "$STAGED.tmp"
if [[ -x /usr/bin/plutil ]]; then /usr/bin/plutil -lint "$STAGED.tmp" >/dev/null; fi
mv "$STAGED.tmp" "$STAGED"
chmod 644 "$STAGED"
echo "installed $LABEL at release $SHA (staged at $STAGED, not loaded)"

if [[ "$ACTIVATE" == 1 ]]; then
  [[ "$LOADED" == 0 ]] || launchctl bootout "gui/$UID_NUM/$LABEL"
  mkdir -p "$HOME/Library/LaunchAgents"
  cp "$STAGED" "$PLIST_DEST"
  launchctl enable "gui/$UID_NUM/$LABEL"
  launchctl bootstrap "gui/$UID_NUM" "$PLIST_DEST"
  echo "activated $LABEL"
fi
