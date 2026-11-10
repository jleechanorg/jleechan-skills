#!/usr/bin/env bash
# instinct-ping: every 20 min (launchd, ai.jleechan.instinct-ping), ask Instinct on
# iMessage for a bounded verdict on the in-flight task and stop when it lands.
#
# Design:
#  - Never guesses delivery. `imsg-bridge.sh send` re-reads chat.db and binds its
#    confirmation to the exact text it sent; only that is exit 0.
#  - Idempotent + non-spamming: one message per tick, attempt number in the body,
#    and it stops as soon as a verdict reply or a DONE marker appears.
#  - All transport goes through the /instinct SKILL's own CLI, so there is ONE
#    transport policy for /instinct, launchd and a remote caller: iMessage first,
#    WhatsApp fallback (see ~/.claude/skills/instinct/SKILL.md § Transport chain).
#    WhatsApp Web never worked here — the device was never linked, so every tick
#    logged "signed out" and delivered nothing. iMessage is already signed in as
#    the user and needs no browser, profile lock, or QR.
#
# TCC REALITY: a launchd process has no Full Disk Access and cannot open
# ~/Library/Messages/chat.db ("authorization denied"). `send` and `probe` are
# unaffected because neither needs the DB; `read` does and is therefore not used
# here — replies are collected from a GUI-session shell instead.
#
# Usage:
#   instinct-ping.sh            # one tick (this is what launchd runs)
#   instinct-ping.sh status     # print state, send nothing
#   instinct-ping.sh done       # mark the task complete; future ticks exit immediately
#   instinct-ping.sh reset      # clear DONE/state and start a new attempt sequence
#   INSTINCT_PING_DRY_RUN=1 instinct-ping.sh   # render the message, send nothing
set -uo pipefail
export PATH="$HOME/.local/bin:$HOME/.nvm/versions/node/v22.22.0/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

NODE="$HOME/.nvm/versions/node/v22.22.0/bin/node"
CLI="$HOME/.claude/skills/instinct/scripts/instinct.mjs"
# Resolved by HANDLE, never by name: two buddies are named "Instinct", so a name
# lookup is ambiguous and could post to the dead SMS thread (+16506654254).
CONTACT_HANDLE="${INSTINCT_IMSG_CONTACT:-+16282909722}"
STATE_DIR="$HOME/.local/state/instinct-ping"
STATE="$STATE_DIR/state.json"
DONE="$STATE_DIR/DONE"
DRY="${INSTINCT_PING_DRY_RUN:-0}"

# The task under watch. Keep this the single source of truth: the ping body is
# generated from here so a resumed task does not need a script edit per round.
TASK_TITLE="${INSTINCT_PING_TASK:-P0 ordinary-XP omission (rev-1pwpa.2.6.18)}"
TASK_REPO="${INSTINCT_PING_REPO:-jleechanorg/worldarchitect.ai}"
TASK_PR="${INSTINCT_PING_PR:-11274}"
TASK_ASK="${INSTINCT_PING_ASK:-independent source review of the P0 eligibility-floor prompt change plus a verdict on whether a positive-XP floor can regress the routine/unresolved/already-paid zero-award cases}"

mkdir -p "$STATE_DIR"
exec 9>"$STATE_DIR/lock"
if ! /usr/bin/flock -n 9 2>/dev/null; then
  # flock is not present on stock macOS; fall back to a pidfile guard below.
  if [ -f "$STATE_DIR/pid" ] && kill -0 "$(cat "$STATE_DIR/pid" 2>/dev/null)" 2>/dev/null; then
    echo "instinct-ping: another tick is running (pid $(cat "$STATE_DIR/pid")); skipping"
    exit 0
  fi
fi
echo $$ > "$STATE_DIR/pid"
trap 'rm -f "$STATE_DIR/pid"' EXIT

now() { date -u +%Y-%m-%dT%H:%M:%SZ; }
log() { printf '%s %s\n' "$(now)" "$*" >> "$STATE_DIR/events.log"; }

state_get() {  # state_get <key> <default>
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

state_put() {  # state_put <key> <value>
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
    state_put attempts 0
    log "state reset"
    echo "instinct-ping: state reset"
    exit 0 ;;
  status)
    if [ -f "$DONE" ]; then echo "status: DONE"; else echo "status: $(state_get status unknown)"; fi
    echo "attempts: $(state_get attempts 0)"
    echo "last_probe: $(state_get last_probe never)"
    echo "last_send: $(state_get last_send never)"
    echo "last_blocker: $(state_get last_blocker none)"
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
if [ ! -x "$NODE" ] || [ ! -f "$CLI" ]; then
  state_put status blocked
  state_put last_blocker "node or instinct.mjs missing"
  log "BLOCKED: node=$NODE cli=$CLI missing"
  exit 0
fi

# ---- 1. Probe the transport chain (iMessage, then WhatsApp).
PROBE_OUT=$(INSTINCT_IMSG_CONTACT="$CONTACT_HANDLE" timeout 180 "$NODE" "$CLI" probe 2>&1)
PROBE_RC=$?
state_put last_probe "$(now)"
if [ "$PROBE_RC" -ne 0 ]; then
  state_put status signed_out
  state_put last_blocker "no_transport_available (probe rc=$PROBE_RC)"
  # Only log the transition once per streak so the log stays readable.
  prev=$(state_get last_blocker "")
  case "$prev" in
    no_transport_available*) log "still unavailable: $PROBE_OUT" ;;
    *) log "BLOCKED no transport available (probe rc=$PROBE_RC): $PROBE_OUT" ;;
  esac
  echo "instinct-ping: no usable transport; nothing sent. Check Messages.app / the WhatsApp link:"
  echo "  INSTINCT_IMSG_CONTACT=$CONTACT_HANDLE $NODE $CLI probe"
  exit 0
fi

# ---- 2. Compose the ping (attempt number makes repeats informative, not noise).
ATTEMPTS=$(( $(state_get attempts 0) + 1 ))
FIRST=$(state_get first_attempt "$(now)")
BODY=$(cat <<TXT
PING #$ATTEMPTS — $TASK_TITLE
since: $FIRST
repo: $TASK_REPO

ASK: $TASK_ASK

Reply with: VERDICT: PASS|FAIL|BLOCKED, then the specific file:line or missing
evidence behind it, then whether the positive-XP floor can regress routine,
unresolved, or already-paid zero-award cases. If you cannot read the branch,
say BLOCKED and name what access you need — do not guess.

This is an automated reminder; reply in this chat and I will pick it up.
TXT
)

if [ "$DRY" = "1" ]; then
  echo "instinct-ping DRY RUN — would send to iMessage $CONTACT_HANDLE:"
  printf '%s\n' "$BODY"
  state_put attempts "$ATTEMPTS"
  state_put status dry_run
  log "dry run composed attempt=$ATTEMPTS"
  exit 0
fi

MSG_FILE=$(mktemp "${TMPDIR:-/tmp}/instinct_ping.XXXXXX")
printf '%s\n' "$BODY" > "$MSG_FILE"

# ---- 3. Send. `send` fails closed (exit 6) when delivery is not confirmed.
SEND_OUT=$(INSTINCT_IMSG_CONTACT="$CONTACT_HANDLE" timeout 400 "$NODE" "$CLI" send --file "$MSG_FILE" 2>&1)
SEND_RC=$?
rm -f "$MSG_FILE"

if [ "$SEND_RC" -ne 0 ]; then
  state_put status send_failed
  state_put last_blocker "send rc=$SEND_RC"
  state_put attempts "$ATTEMPTS"
  log "SEND FAILED rc=$SEND_RC: $(printf '%s' "$SEND_OUT" | tail -3 | tr '\n' ' ')"
  echo "instinct-ping: send not confirmed (rc=$SEND_RC)"
  printf '%s\n' "$SEND_OUT" | tail -5
  exit 0
fi

state_put attempts "$ATTEMPTS"
state_put last_send "$(now)"
state_put last_blocker none
state_put status sent
log "sent attempt=$ATTEMPTS"

# ---- 4. Look for a verdict in the reply and stop when one lands.
# This step NEEDS chat.db, and a launchd process has no Full Disk Access, so the
# read fails closed with exit 4 there. That is a known, logged limitation rather
# than a silent no-op: replies are collected from a GUI-session shell with
#   ~/.local/bin/imsg-bridge.sh read --theirs --limit 15
#
# --theirs is NOT optional. Our own ping body literally contains
# "VERDICT: PASS|FAIL|BLOCKED", so a read including outgoing rows matches the
# template we just sent and reports a verdict that does not exist. That bug fired
# in testing: it marked this job DONE seconds after sending PING #3.
READ_OUT=$(INSTINCT_IMSG_CONTACT="$CONTACT_HANDLE" timeout 180 "$NODE" "$CLI" read --theirs --limit 15 2>&1)
READ_RC=$?
if [ "$READ_RC" -eq 4 ]; then
  log "NOTE verdict check skipped: chat.db unreadable from launchd (no FDA); read from a GUI shell"
  echo "instinct-ping: ping #$ATTEMPTS sent; verdict check skipped here (launchd has no Full Disk Access)"
  exit 0
fi
# Strip the template before matching: a reply that quotes our own instruction is
# not a verdict. Then anchor on the token so prose mentioning the words is ignored.
verdict=$(printf '%s' "$READ_OUT" | sed 's/PASS|FAIL|BLOCKED//g' \
  | grep -oiE '(^|[[:space:]|])VERDICT:[[:space:]]*(PASS|FAIL|BLOCKED)' | tail -1)
if [ -n "$verdict" ]; then
  : > "$DONE"
  state_put status verdict_received
  state_put verdict "$verdict"
  log "verdict received: $verdict — marking DONE"
  echo "instinct-ping: $verdict received; marking DONE"
else
  echo "instinct-ping: ping #$ATTEMPTS sent; no verdict yet"
fi
exit 0
