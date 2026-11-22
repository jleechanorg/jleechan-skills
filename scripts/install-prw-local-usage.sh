#!/usr/bin/env bash
# Install the local usage collector as a pinned release plus a STAGED launchd plist (com.jleechan.prw-local-usage).
# Installing never loads or starts anything; only --activate copies the plist into ~/Library/LaunchAgents and
# enables/bootstraps it. The com.jleechan.prw-metrics* labels are never touched. The job runs hourly at :37.
# Linux and other hosts: nothing is installed automatically in v1. --print-crontab prints (never installs)
# an equivalent crontab line and a systemd user timer+service pair for you to review and install by hand.
#
# Usage: install-prw-local-usage.sh --roadmap-remote URL [--roadmap-branch main] [--machine LABEL]
#          [--source-repo PATH] [--source-rev REV] [--dry-run] [--replace] [--activate] [--print-crontab]
set -euo pipefail

LABEL="com.jleechan.prw-local-usage"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATE="$REPO_DIR/launchd/$LABEL.plist.template"
SOURCE_REPO="$REPO_DIR" SOURCE_REV="origin/main"
REMOTE="" BRANCH="main" MACHINE=""
DRY_RUN=0 REPLACE=0 ACTIVATE=0 PRINT_CRON=0

die() { echo "ERROR: $*" >&2; exit 1; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --roadmap-remote) REMOTE="${2:?}"; shift 2 ;;
    --roadmap-branch) BRANCH="${2:?}"; shift 2 ;;
    --machine) MACHINE="${2:?}"; shift 2 ;;
    --source-repo) SOURCE_REPO="${2:?}"; shift 2 ;;
    --source-rev) SOURCE_REV="${2:?}"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    --replace) REPLACE=1; shift ;;
    --activate) ACTIVATE=1; shift ;;
    --print-crontab) PRINT_CRON=1; shift ;;
    *) die "unknown argument: $1" ;;
  esac
done
[[ -n "$REMOTE" ]] || die "--roadmap-remote is required"
[[ -f "$TEMPLATE" ]] || die "template not found: $TEMPLATE"

# Same rule as prw_metrics.embeds_credentials.
if python3 - "$REMOTE" <<'PY'
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
  echo "ERROR: --roadmap-remote must not embed credentials" >&2
  exit 2
fi

SHA="$(git -C "$SOURCE_REPO" rev-parse --verify "${SOURCE_REV}^{commit}")" || die "cannot resolve $SOURCE_REV"
RELEASE_DIR="$HOME/.local/share/prw-local-usage/releases/$SHA"
PLIST_DEST="$HOME/Library/LaunchAgents/$LABEL.plist"
UID_NUM="$(/usr/bin/id -u)"
ARGS=(--publish-remote "$REMOTE" --publish-branch "$BRANCH")
[[ -z "$MACHINE" ]] || ARGS+=(--machine "$MACHINE")

if [[ "$PRINT_CRON" == 1 ]]; then
  WORDS=(/bin/bash "$RELEASE_DIR/scripts/run_prw_local_usage.sh" "${ARGS[@]}")
  CMD="" UNIT_CMD=""
  for w in "${WORDS[@]}"; do
    q="$(printf '%q' "$w")"; CMD+="${CMD:+ }${q//%/\\%}"  # cron turns an unescaped % into a newline
    # systemd words: double-quoted, with \ and " escaped, and % and $ doubled (specifiers / variable expansion)
    u="${w//\\/\\\\}"; u="${u//\"/\\\"}"; u="${u//%/%%}"; u="${u//\$/\$\$}"
    UNIT_CMD+="${UNIT_CMD:+ }\"$u\""
  done
  cat <<TXT
# crontab line (hourly at :37); install by hand with: crontab -e
37 * * * * PATH=/usr/local/bin:\$HOME/.local/bin:/usr/bin:/bin $CMD

# ~/.config/systemd/user/prw-local-usage.service
[Unit]
Description=PRW local usage collector
[Service]
Type=oneshot
Environment=PATH=/usr/local/bin:%h/.local/bin:/usr/bin:/bin
ExecStart=$UNIT_CMD

# ~/.config/systemd/user/prw-local-usage.timer
[Unit]
Description=Hourly PRW local usage collector
[Timer]
OnCalendar=*:37:00
Persistent=true
[Install]
WantedBy=timers.target
TXT
  exit 0
fi

render() {
  python3 - "$TEMPLATE" "$HOME" "$RELEASE_DIR" "$REMOTE" "$BRANCH" "$MACHINE" <<'PY'
import plistlib, sys
tpl, home, release, remote, branch, machine = sys.argv[1:7]
subs = {"@HOME@": home, "@RELEASE_DIR@": release, "@ROADMAP_REMOTE@": remote,
        "@ROADMAP_BRANCH@": branch, "@MACHINE@": machine}
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
if not machine:  # --machine is optional: drop the flag and its value
    args = plist["ProgramArguments"]
    i = args.index("--machine")
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
  [[ "$REPLACE" == 1 ]] || die "$LABEL is already loaded; pass --replace to reinstall"
else
  LOADED=0
fi

mkdir -p "$RELEASE_DIR" "$HOME/Library/Logs"
git -C "$SOURCE_REPO" archive "$SHA" scripts | tar -x -C "$RELEASE_DIR"

# Staged inside the release dir; launchd loads everything in ~/Library/LaunchAgents at login, so only --activate copies it.
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
