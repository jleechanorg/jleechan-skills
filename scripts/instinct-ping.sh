#!/usr/bin/env bash
# instinct-ping: every 20 min (launchd, ai.jleechan.instinct-ping), ask Instinct on
# WhatsApp for a bounded verdict on the in-flight task and stop when it lands.
#
# Design:
#  - Never guesses delivery. Probes the WhatsApp link first; when signed out it
#    records BLOCKED and exits 0 without claiming a send (a link is device-bound
#    and only the operator's phone can restore it).
#  - Idempotent + non-spamming: one message per tick, attempt number in the body,
#    and it stops as soon as a verdict reply or a DONE marker appears.
#  - All transport goes through the instinct skill's own CLI (instinct.mjs), which
#    owns the profile lock, the wrong-recipient guard, and clean shutdown.
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
STATE_DIR="$HOME/.local/state/instinct-ping"
STATE="$STATE_DIR/state.json"
DONE="$STATE_DIR/DONE"
CONTACT="${INSTINCT_CONTACT:-Instinct WhatsApp}"
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
if [ ! -x /Users/jleechan/.nvm/versions/node/v22.22.0/bin/node ] || [ ! -f "$CLI" ]; then
  state_put status blocked
  state_put last_blocker "node or instinct.mjs missing"
  log "BLOCKED: node=$NODE cli=$CLI missing"
  exit 0
fi

# ---- 1. Probe the link. A populated profile directory is not proof of a link.
PROBE_OUT=$(timeout 300 "$NODE" "$CLI" probe 2>&1)
PROBE_RC=$?
state_put last_probe "$(now)"
if [ "$PROBE_RC" -ne 0 ]; then
  state_put status signed_out
  state_put last_blocker "whatsapp_link_down (probe rc=$PROBE_RC)"
  # Only log the transition once per streak so the log stays readable.
  prev=$(state_get last_blocker "")
  case "$prev" in
    whatsapp_link_down*) log "still signed out: $PROBE_OUT" ;;
    *) log "BLOCKED signed out (probe rc=$PROBE_RC): $PROBE_OUT" ;;
  esac
  echo "instinct-ping: WhatsApp link is down; nothing sent. Restore with:"
  echo "  $NODE $CLI login      # scan the QR from the phone once"
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
  echo "instinct-ping DRY RUN — would send to '$CONTACT':"
  printf '%s\n' "$BODY"
  state_put attempts "$ATTEMPTS"
  state_put status dry_run
  log "dry run composed attempt=$ATTEMPTS"
  exit 0
fi

MSG_FILE=$(mktemp "${TMPDIR:-/tmp}/instinct_ping.XXXXXX")
printf '%s\n' "$BODY" > "$MSG_FILE"

# ---- 3. Send. `send` fails closed (exit 6) when delivery is not confirmed.
SEND_OUT=$(timeout 400 "$NODE" "$CLI" send --contact "$CONTACT" --file "$MSG_FILE" 2>&1)
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
READ_OUT=$(timeout 400 "$NODE" "$CLI" read --contact "$CONTACT" --limit 15 2>&1)
if printf '%s' "$READ_OUT" | grep -qiE '(^|[^A-Za-z])VERDICT:[[:space:]]*(PASS|FAIL|BLOCKED)'; then
  verdict=$(printf '%s' "$READ_OUT" | grep -oiE 'VERDICT:[[:space:]]*(PASS|FAIL|BLOCKED)' | tail -1)
  : > "$DONE"
  state_put status verdict_received
  state_put verdict "$verdict"
  log "verdict received: $verdict — marking DONE"
  echo "instinct-ping: $verdict received; marking DONE"
else
  echo "instinct-ping: ping #$ATTEMPTS sent; no verdict yet"
fi
exit 0
