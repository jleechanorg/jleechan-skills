#!/usr/bin/env bash
# imsg-bridge.sh — mechanical iMessage I/O for the /instinct transport.
#
# Verbs: probe | read | send | whoami
# Exit codes match instinct.mjs so callers keep one contract:
#   0 ok, 2 bad usage, 3 missing dependency, 4 not signed in / unreadable DB,
#   5 contact not found, 6 delivery NOT confirmed.
#
# WHY THIS EXISTS: WhatsApp Web needs a linked device, a browser profile lock, a
# desktop UA (WhatsApp serves an "update Chrome" wall to a headless UA) and a
# hydration-aware probe. iMessage needs none of that: Messages.app and imagent are
# already running and signed in as the user, a send does not steal focus, and it
# works from a scheduler or over SSH.
#
# WHAT IT DOES NOT DO: it never claims delivery it did not observe. `send` writes
# the row, then reads the message store back and compares the stored text to
# exactly what was sent; only that is exit 0.
#
# Every machine-specific value comes from the environment (see
# docs/portability-env-vars.md). Nothing personal is hardcoded here.

set -uo pipefail

# The contact is resolved by HANDLE, never by display name: display names can be
# duplicated in a contact store (two different "Assistant" entries on different
# services is a common shape), and a name lookup can silently pick the stale one.
CONTACT_HANDLE="${IMSG_CONTACT_HANDLE:-}"
DB="${IMSG_CHAT_DB:-$HOME/Library/Messages/chat.db}"

VERB="${1:-whoami}"; shift || true
LIMIT=10
FILE=""
THEIRS_ONLY=0
SINCE_ROWID=0
DB_OVERRIDE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --limit) LIMIT="${2:-10}"; shift 2 ;;
    --file) FILE="${2:-}"; shift 2 ;;
    --db) DB_OVERRIDE="${2:-}"; shift 2 ;;
    --contact-handle) CONTACT_HANDLE="${2:-}"; shift 2 ;;
    # --theirs restricts read to messages the CONTACT sent. Required for any
    # caller that greps for a reply: matching our own outgoing text is a false
    # positive waiting to happen (a prompt that says "reply VERDICT: PASS|FAIL"
    # matches itself the moment it is read back).
    --theirs) THEIRS_ONLY=1; shift ;;
    # --since ROWID: only rows newer than this, so a stale message cannot satisfy
    # a check for a fresh reply.
    --since) SINCE_ROWID="${2:-0}"; shift 2 ;;
    *) echo "imsg-bridge: unknown arg '$1'" >&2; exit 2 ;;
  esac
done
[ -n "$DB_OVERRIDE" ] && DB="$DB_OVERRIDE"

die() { echo "imsg-bridge: $1" >&2; exit "${2:-2}"; }
have() { command -v "$1" >/dev/null 2>&1; }
now() { date -u '+%Y-%m-%dT%H:%M:%SZ'; }

[ "$(uname -s)" = "Darwin" ] || die "iMessage is macOS-only (got $(uname -s))" 3
have /usr/bin/sqlite3 || die "sqlite3 not found" 3
have /usr/bin/osascript || die "osascript not found" 3

db_readable() { /usr/bin/sqlite3 "$DB" 'select 1 from message limit 1;' >/dev/null 2>&1; }

require_contact() {
  [ -n "$CONTACT_HANDLE" ] || die "no contact configured; export IMSG_CONTACT_HANDLE (E.164 phone or Apple ID email), or pass --contact-handle" 5
}

# --- send ---------------------------------------------------------------------
do_send() {
  require_contact
  [ -n "$FILE" ] || die "send requires --file PATH" 2
  [ -f "$FILE" ] || die "message file not found: $FILE" 2
  local text; text="$(cat "$FILE")"
  [ -n "${text//[[:space:]]/}" ] || die "message file is empty" 2
  [ "${#text}" -le 4000 ] || die "message is ${#text} chars; keep under 4000" 2

  # Snapshot the high-water mark BEFORE sending so the read-back cannot pick up an
  # older identical message. If the store is unreadable (a scheduler process
  # usually has no Full Disk Access) we still send, but must report unconfirmed
  # rather than claim success.
  local can_read=0 before=0
  if db_readable; then
    can_read=1
    before=$(/usr/bin/sqlite3 "$DB" 'select coalesce(max(ROWID),0) from message;' 2>/dev/null)
  fi

  # argv-passed text: no shell interpolation, so quotes/$/backticks/newlines are
  # inert. NEVER interpolate "$text" into the AppleScript source.
  /usr/bin/osascript - "$CONTACT_HANDLE" "$text" <<'APPLESCRIPT'
on run argv
  set theHandle to item 1 of argv
  set theText to item 2 of argv
  tell application "Messages"
    send theText to buddy theHandle of service 1
  end tell
end run
APPLESCRIPT
  local rc=$?
  [ "$rc" -eq 0 ] || die "osascript send failed rc=$rc" 6

  [ "$can_read" -eq 1 ] || {
    echo "sent, delivery UNCONFIRMED (message store unreadable here; pass --db SNAPSHOT of it)" >&2
    exit 6
  }

  # Confirm by ROWID high-water mark, then bind to the stored text. is_delivered
  # lags the INSERT by a moment, so poll it instead of reporting a transient 0.
  local i newrow=""
  for i in 1 2 3 4 5 6 7 8 9 10; do
    sleep 1
    newrow=$(/usr/bin/sqlite3 "$DB" "select ROWID from message where ROWID > $before and is_from_me=1 order by ROWID desc limit 1;" 2>/dev/null)
    [ -n "$newrow" ] && break
  done
  [ -n "$newrow" ] || die "delivery NOT confirmed (no new outgoing row within 10s)" 6

  local stored
  stored=$(/usr/bin/sqlite3 "$DB" "select coalesce(text,'') from message where ROWID = $newrow;" 2>/dev/null)
  if [ "$stored" != "$text" ]; then
    die "row $newrow does not carry the sent text (got ${#stored} bytes); not claiming delivery" 6
  fi

  local delivered=0 j
  for j in 1 2 3 4 5; do
    delivered=$(/usr/bin/sqlite3 "$DB" "select coalesce(is_delivered,0) from message where ROWID = $newrow;" 2>/dev/null)
    [ "$delivered" = "1" ] && break
    sleep 1
  done
  echo "sent rowid=$newrow delivered=${delivered:-0}"
  exit 0
}

# --- read ---------------------------------------------------------------------
do_read() {
  require_contact
  # A scheduler-spawned caller has no Full Disk Access, so it must pass --db with a
  # snapshot taken by an interactive session.
  db_readable || die "message store unreadable; pass --db SNAPSHOT (taken by an interactive session)" 4
  local filt=""
  [ "$THEIRS_ONLY" -eq 1 ] && filt="$filt and m.is_from_me = 0"
  [ "${SINCE_ROWID:-0}" -gt 0 ] && filt="$filt and m.ROWID > $SINCE_ROWID"
  /usr/bin/sqlite3 -separator ' | ' "$DB" "
    select m.ROWID,
           case m.is_from_me when 1 then 'me' else 'them' end,
           datetime(m.date/1000000000+978307200,'unixepoch','localtime'),
           coalesce(nullif(m.text,''),'[no text: attachment/tapback]')
      from message m
      join chat_message_join cmj on cmj.message_id = m.ROWID
      join chat c on c.ROWID = cmj.chat_id
     where c.chat_identifier = '$CONTACT_HANDLE'$filt
     order by m.date desc limit $LIMIT;" 2>&1
}

# --- probe --------------------------------------------------------------------
do_probe() {
  require_contact
  # Signed in == the Messages daemon is running and the contact chat exists. No
  # browser, so no profile lock, no UA gate, no hydration race.
  pgrep -x imagent >/dev/null 2>&1 || die "imagent not running; Messages not signed in" 4
  if db_readable; then
    local n
    n=$(/usr/bin/sqlite3 "$DB" "select count(*) from chat where chat_identifier='$CONTACT_HANDLE';" 2>/dev/null)
    [ "${n:-0}" -gt 0 ] || die "contact $CONTACT_HANDLE not found in the message store" 5
    echo "{\"signed_in\":true,\"transport\":\"imessage\",\"contact\":\"$CONTACT_HANDLE\",\"chat_rows\":$n}"
  else
    # Scheduler context: imagent is proof enough, the store just is not readable.
    echo "{\"signed_in\":true,\"transport\":\"imessage\",\"contact\":\"$CONTACT_HANDLE\",\"db_readable\":false}"
  fi
  exit 0
}

case "$VERB" in
  send)   do_send ;;
  read)   do_read ;;
  probe)  do_probe ;;
  whoami)
    printf 'transport=imessage contact=%s db=%s\n' "${CONTACT_HANDLE:-<unset: export IMSG_CONTACT_HANDLE>}" "$DB"
    ;;
  *) die "unknown verb '$VERB'; use probe | read | send | whoami" 2 ;;
esac
