#!/usr/bin/env bash
# Ask Instinct for a bounded verdict on one explicitly configured task.
# Every tick reads replies before sending and fails closed when reads are unavailable.
# An uncertain send is held until the operator resolves it with done or reset.
set -uo pipefail
export PATH="$HOME/.local/bin:$HOME/.nvm/versions/node/v22.22.0/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

NODE="$HOME/.nvm/versions/node/v22.22.0/bin/node"
CLI="$HOME/.claude/skills/instinct/scripts/instinct.mjs"
CONFIG_FILE="$HOME/.config/instinct-ping/config.json"

config_validate() {
  /usr/bin/python3 -c 'import json,sys
fields=("contact","task","repo","pr","ask")
try:
    with open(sys.argv[1], encoding="utf-8") as f: config=json.load(f)
    if not isinstance(config, dict): raise ValueError("top level must be an object")
    for field in fields:
        value=config.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(field + " must be a non-empty string")
except (OSError, ValueError, json.JSONDecodeError) as exc:
    print("invalid instinct-ping config: " + str(exc), file=sys.stderr)
    sys.exit(1)' "$CONFIG_FILE"
}

config_get() {
  /usr/bin/python3 -c 'import json,sys
with open(sys.argv[1], encoding="utf-8") as f: config=json.load(f)
print(config[sys.argv[2]], end="")' "$CONFIG_FILE" "$1"
}

CONFIG_CONTACT=""
CONFIG_TASK=""
CONFIG_REPO=""
CONFIG_PR=""
CONFIG_ASK=""
if [ -f "$CONFIG_FILE" ]; then
  if ! config_validate; then exit 2; fi
  CONFIG_CONTACT=$(config_get contact)
  CONFIG_TASK=$(config_get task)
  CONFIG_REPO=$(config_get repo)
  CONFIG_PR=$(config_get pr)
  CONFIG_ASK=$(config_get ask)
fi

case "${1:-tick}" in
  validate-config)
    if [ ! -f "$CONFIG_FILE" ]; then
      echo "instinct-ping: persistent config is missing: $CONFIG_FILE" >&2
      exit 2
    fi
    config_validate || exit 2
    echo "instinct-ping: persistent config is valid"
    exit 0 ;;
esac

CONTACT_HANDLE="${INSTINCT_IMSG_CONTACT:-$CONFIG_CONTACT}"
STATE_DIR="$HOME/.local/state/instinct-ping"
STATE="$STATE_DIR/state.json"
DONE="$STATE_DIR/DONE"
DRY="${INSTINCT_PING_DRY_RUN:-0}"
TASK_TITLE="${INSTINCT_PING_TASK:-$CONFIG_TASK}"
TASK_REPO="${INSTINCT_PING_REPO:-$CONFIG_REPO}"
TASK_PR="${INSTINCT_PING_PR:-$CONFIG_PR}"
TASK_ASK="${INSTINCT_PING_ASK:-$CONFIG_ASK}"

mkdir -p "$STATE_DIR"
exec 9>"$STATE_DIR/lock"
if ! /usr/bin/flock -n 9 2>/dev/null; then
  # flock is unavailable on stock macOS; use a pidfile guard there.
  if [ -f "$STATE_DIR/pid" ] && kill -0 "$(cat "$STATE_DIR/pid" 2>/dev/null)" 2>/dev/null; then
    echo "instinct-ping: another tick is running (pid $(cat "$STATE_DIR/pid")); skipping"
    exit 0
  fi
fi
echo $$ > "$STATE_DIR/pid"
trap 'rm -f "$STATE_DIR/pid"' EXIT

now() { date -u +%Y-%m-%dT%H:%M:%SZ; }
log() { printf '%s %s\n' "$(now)" "$*" >> "$STATE_DIR/events.log"; }

state_get() {
  if [ -f "$STATE" ]; then
    /usr/bin/python3 -c 'import json,sys
try: d=json.load(open(sys.argv[1]))
except Exception: d={}
v=d.get(sys.argv[2])
print(sys.argv[3] if v in (None,"") else v)' "$STATE" "$1" "${2:-}"
  else
    printf '%s' "${2:-}"
  fi
}

state_put() {
  /usr/bin/python3 -c 'import json,sys,os
p,k,v=sys.argv[1:4]
try: d=json.load(open(p))
except Exception: d={}
d[k]=v
d["updated_at"]=sys.argv[4]
os.makedirs(os.path.dirname(p),exist_ok=True)
json.dump(d,open(p,"w"),indent=2,sort_keys=True)' "$STATE" "$1" "$2" "$(now)"
}

case "${1:-tick}" in
  done)
    : > "$DONE"
    state_put status done
    log "DONE marker written"
    echo "instinct-ping: marked done; future ticks exit immediately"
    exit 0 ;;
  reset)
    rm -f "$DONE"
    state_put status reset
    state_put request_id ""
    state_put task_key ""
    state_put attempts 0
    state_put uncertain_send ""
    log "state reset; next tick creates a new request ID"
    echo "instinct-ping: reset; next tick starts a new request"
    exit 0 ;;
  status)
    if [ -f "$DONE" ]; then echo "status: DONE"; else echo "status: $(state_get status unknown)"; fi
    echo "request_id: $(state_get request_id none)"
    echo "attempts: $(state_get attempts 0)"
    echo "last_read: $(state_get last_read never)"
    echo "last_send: $(state_get last_send never)"
    echo "last_blocker: $(state_get last_blocker none)"
    echo "uncertain_send: $(state_get uncertain_send none)"
    echo "state_file: $STATE"
    echo "--- last 5 events"
    tail -5 "$STATE_DIR/events.log" 2>/dev/null
    exit 0 ;;
  tick) ;;
  *) echo "usage: $0 [tick|status|done|reset]" >&2; exit 2 ;;
esac

if [ -f "$DONE" ]; then
  log "tick skipped: DONE marker present"
  exit 0
fi
if [ -n "$(state_get uncertain_send "")" ]; then
  echo "instinct-ping: prior send outcome is uncertain; automatic sends held. Resolve with done or reset after checking the outcome."
  exit 0
fi
if [ ! -x "$NODE" ] || [ ! -f "$CLI" ]; then
  state_put status blocked
  state_put last_blocker "node or instinct.mjs missing"
  log "BLOCKED: node or instinct.mjs missing"
  echo "instinct-ping: node or instinct.mjs missing; nothing sent"
  exit 0
fi

if [ -z "$CONTACT_HANDLE" ] || [ -z "$TASK_TITLE" ] || [ -z "$TASK_REPO" ] || \
   [ -z "$TASK_PR" ] || [ -z "$TASK_ASK" ] || [ ! -d "$TASK_REPO" ]; then
  state_put status blocked
  state_put last_blocker "configuration required: recipient, task, PR, and reachable repository path"
  log "BLOCKED: task or recipient configuration missing, or repository path is unreachable"
  echo "instinct-ping: configuration required (INSTINCT_IMSG_CONTACT, INSTINCT_PING_TASK, INSTINCT_PING_REPO as a reachable local repository path, INSTINCT_PING_PR, INSTINCT_PING_ASK); nothing sent"
  exit 0
fi

TARGET_ROOT=$(git -C "$TASK_REPO" rev-parse --show-toplevel 2>/dev/null)
TARGET_BRANCH=$(git -C "$TASK_REPO" branch --show-current 2>/dev/null)
TARGET_COMMIT=$(git -C "$TASK_REPO" rev-parse HEAD 2>/dev/null)
TARGET_REMOTE=$(git -C "$TASK_REPO" config --get remote.origin.url 2>/dev/null)
if [ -z "$TARGET_ROOT" ] || [ -z "$TARGET_BRANCH" ] || [ -z "$TARGET_COMMIT" ]; then
  state_put status blocked
  state_put last_blocker "target repository branch or commit unavailable"
  log "BLOCKED: target repository branch or commit unavailable"
  echo "instinct-ping: target repository branch or commit unavailable; nothing sent"
  exit 0
fi
if [ -z "$TARGET_REMOTE" ]; then TARGET_REMOTE="$TARGET_ROOT"; fi

TASK_KEY=$(/usr/bin/python3 -c 'import hashlib,sys; print(hashlib.sha256("\0".join(sys.argv[1:]).encode()).hexdigest())' \
  "$TASK_TITLE" "$TARGET_REMOTE" "$TARGET_BRANCH" "$TARGET_COMMIT" "$TASK_PR" "$TASK_ASK")
REQUEST_ID=$(state_get request_id "")
SAVED_TASK_KEY=$(state_get task_key "")
if [ -n "$SAVED_TASK_KEY" ] && [ "$SAVED_TASK_KEY" != "$TASK_KEY" ]; then
  REQUEST_ID=""
fi
if [ -z "$REQUEST_ID" ]; then
  REQUEST_ID=$(/usr/bin/python3 -c 'import uuid; print(uuid.uuid4())')
  state_put request_id "$REQUEST_ID"
fi
state_put task_key "$TASK_KEY"

# Read replies before any send. --theirs is required so our own request cannot
# satisfy the reply protocol.
READ_OUT=$(INSTINCT_TRANSPORT=imessage INSTINCT_IMSG_CONTACT="$CONTACT_HANDLE" \
  timeout 180 "$NODE" "$CLI" read --theirs --limit 15 2>&1)
READ_RC=$?
state_put last_read "$(now)"
if [ "$READ_RC" -ne 0 ]; then
  state_put status reply_read_blocked
  state_put last_blocker "reply read unavailable (rc=$READ_RC)"
  log "BLOCKED reply read (rc=$READ_RC): $(printf '%s' "$READ_OUT" | tail -3 | tr '\n' ' ')"
  echo "instinct-ping: reply read unavailable (rc=$READ_RC); nothing sent"
  printf '%s\n' "$READ_OUT" | tail -5
  exit 0
fi
state_put last_blocker none

# A verdict must share one line with the exact task token and one concrete value.
# Quoted protocol instructions such as PASS|FAIL|BLOCKED do not match this form.
verdict=""
while IFS= read -r line; do
  case "$line" in
    *"REQUEST_ID: $REQUEST_ID"*)
      if printf '%s\n' "$line" | grep -Eiq 'VERDICT: (PASS|FAIL|BLOCKED)([[:space:],.;:!?)]|$)'; then
        verdict=$(printf '%s\n' "$line" | grep -oiE 'VERDICT: (PASS|FAIL|BLOCKED)([[:space:],.;:!?)]|$)' | tail -1)
      fi
      ;;
  esac
done <<EOF
$READ_OUT
EOF

if [ -n "$verdict" ]; then
  : > "$DONE"
  state_put status verdict_received
  state_put verdict "$verdict"
  log "current request verdict received: $verdict — marking DONE"
  echo "instinct-ping: current request $REQUEST_ID verdict received; marking DONE"
  exit 0
fi

ATTEMPTS=$(( $(state_get attempts 0) + 1 ))
FIRST=$(state_get first_attempt "$(now)")
BODY=$(cat <<TXT
REQUEST_ID: $REQUEST_ID
PING #$ATTEMPTS — $TASK_TITLE
since: $FIRST
repo: $TARGET_REMOTE
branch: $TARGET_BRANCH
commit: $TARGET_COMMIT
PR: #$TASK_PR

ASK: $TASK_ASK

Reply on one line with REQUEST_ID: $REQUEST_ID followed by one concrete verdict:
VERDICT: PASS, VERDICT: FAIL, or VERDICT: BLOCKED, then file:line or missing evidence.
If you cannot read this exact branch and commit, say BLOCKED and name the access needed.
TXT
)

if [ "$DRY" = "1" ]; then
  echo "instinct-ping DRY RUN — would send to the configured peer:"
  printf '%s\n' "$BODY"
  state_put attempts "$ATTEMPTS"
  state_put status dry_run
  log "dry run composed attempt=$ATTEMPTS request=$REQUEST_ID"
  exit 0
fi

MSG_FILE=$(mktemp "${TMPDIR:-/tmp}/instinct_ping.XXXXXX")
printf '%s\n' "$BODY" > "$MSG_FILE"
SEND_OUT=$(INSTINCT_TRANSPORT=imessage INSTINCT_IMSG_CONTACT="$CONTACT_HANDLE" \
  timeout 400 "$NODE" "$CLI" send --file "$MSG_FILE" 2>&1)
SEND_RC=$?
rm -f "$MSG_FILE"

if [ "$SEND_RC" -ne 0 ]; then
  state_put status send_uncertain
  state_put last_blocker "send outcome uncertain (rc=$SEND_RC)"
  state_put uncertain_send "$REQUEST_ID"
  state_put attempts "$ATTEMPTS"
  log "SEND OUTCOME UNCERTAIN rc=$SEND_RC request=$REQUEST_ID: $(printf '%s' "$SEND_OUT" | tail -3 | tr '\n' ' ')"
  echo "instinct-ping: send outcome uncertain (rc=$SEND_RC); automatic sends held. Resolve with done or reset after checking the outcome."
  printf '%s\n' "$SEND_OUT" | tail -5
  exit 0
fi

state_put attempts "$ATTEMPTS"
state_put first_attempt "$FIRST"
state_put last_send "$(now)"
state_put last_blocker none
state_put status sent
log "sent attempt=$ATTEMPTS request=$REQUEST_ID"
echo "instinct-ping: request $REQUEST_ID sent for $TASK_REPO branch $TARGET_BRANCH at $TARGET_COMMIT"
exit 0
