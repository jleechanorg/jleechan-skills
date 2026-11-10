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
# One documented name (INSTINCT_IMSG_CONTACT, registered in the env-var
# registry). IMSG_CONTACT_HANDLE is accepted as a compatibility alias for direct
# bridge invocations. Neither silently wins over an explicit --contact-handle.
CONTACT_HANDLE="${INSTINCT_IMSG_CONTACT:-${IMSG_CONTACT_HANDLE:-}}"
DB="${IMSG_CHAT_DB:-$HOME/Library/Messages/chat.db}"

VERB="${1:-whoami}"; shift || true
LIMIT=10
FILE=""
THEIRS_ONLY=0
SINCE_ROWID=0
DB_OVERRIDE=""
# Every option that takes a value must actually receive one: `shift 2` on a
# trailing option would otherwise leave $1 unchanged and spin forever (errexit is
# intentionally off so failures can be reported with a specific exit code).
need_value() {
  [ $# -ge 2 ] || { echo "imsg-bridge: option $1 requires a value" >&2; exit 2; }
}
is_uint() { case "${1:-}" in ''|*[!0-9]*) return 1 ;; *) return 0 ;; esac; }

while [ $# -gt 0 ]; do
  case "$1" in
    --limit)
      need_value "$@"; LIMIT="$2"; shift 2
      is_uint "$LIMIT" || { echo "imsg-bridge: --limit must be a non-negative integer, got '$LIMIT'" >&2; exit 2; }
      ;;
    --file) need_value "$@"; FILE="$2"; shift 2 ;;
    --db) need_value "$@"; DB_OVERRIDE="$2"; shift 2 ;;
    --contact-handle) need_value "$@"; CONTACT_HANDLE="$2"; shift 2 ;;
    # --theirs restricts read to messages the CONTACT sent. Required for any
    # caller that greps for a reply: matching our own outgoing text is a false
    # positive waiting to happen (a prompt that says "reply VERDICT: PASS|FAIL"
    # matches itself the moment it is read back).
    --theirs) THEIRS_ONLY=1; shift ;;
    # --since ROWID: only rows newer than this, so a stale message cannot satisfy
    # a check for a fresh reply.
    --since)
      need_value "$@"; SINCE_ROWID="$2"; shift 2
      is_uint "$SINCE_ROWID" || { echo "imsg-bridge: --since must be a non-negative integer, got '$SINCE_ROWID'" >&2; exit 2; }
      ;;
    *) echo "imsg-bridge: unknown arg '$1'" >&2; exit 2 ;;
  esac
done
[ -n "$DB_OVERRIDE" ] && DB="$DB_OVERRIDE"

# The contact handle is interpolated into SQL. Validate it against the shapes a
# real handle can take (E.164 phone, or an Apple ID email) so a quote or comment
# sequence can never reach the query. Read-only access is also enforced via
# sqlite3 -readonly everywhere below, so even a bypassed quote cannot write.

die() { echo "imsg-bridge: $1" >&2; exit "${2:-2}"; }
have() { command -v "$1" >/dev/null 2>&1; }
now() { date -u '+%Y-%m-%dT%H:%M:%SZ'; }

[ "$(uname -s)" = "Darwin" ] || die "iMessage is macOS-only (got $(uname -s))" 3
have /usr/bin/sqlite3 || die "sqlite3 not found" 3
have /usr/bin/osascript || die "osascript not found" 3

# Always read the message store read-only: this process never needs to write it,
# and -readonly makes an injected or malformed statement incapable of mutation.
q() { /usr/bin/sqlite3 -readonly "$@"; }

db_readable() { q "$DB" 'select 1 from message limit 1;' >/dev/null 2>&1; }

# A real handle is an E.164-ish phone (optional +, 7-15 digits, optional spaces,
# dashes, dots, parens) or an Apple ID email. This is the only defence that
# matters for SQL text built from the handle, because sqlite3 has no parameter
# binding on the command line; -readonly is the second layer.
valid_handle() {
  case "$1" in
    '' ) return 1 ;;
    *\'*|*\"*|*\;*|*--*|*/*) return 1 ;;
  esac
  printf '%s' "$1" | grep -Eq '^\+?[0-9][0-9 ().-]{5,24}$|^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'
}

require_contact() {
  [ -n "$CONTACT_HANDLE" ] || die "no contact configured; export INSTINCT_IMSG_CONTACT (E.164 phone or Apple ID email), or pass --contact-handle" 5
  valid_handle "$CONTACT_HANDLE" || die "contact handle '$CONTACT_HANDLE' is not a valid phone number or Apple ID email" 5
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
  #
  # The mark is taken over the WHOLE store on purpose (a concurrent row anywhere
  # raises it), but the confirmation below is filtered to THIS chat — otherwise an
  # unrelated outgoing message can masquerade as this send's receipt.
  local can_read=0 before=0
  if db_readable; then
    can_read=1
    before=$(q "$DB" 'select coalesce(max(ROWID),0) from message;' 2>/dev/null)
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
  # osascript itself failed. Distinguish "definitely not sent" (exit 6 with
  # sent=0) so the caller can safely fall back, from anything that might have
  # gone out (see below).
  [ "$rc" -eq 0 ] || die "osascript send failed rc=$rc (not sent)" 6

  [ "$can_read" -eq 1 ] || {
    # The message MAY have been submitted; a fallback transport would send it a
    # second time. Report a distinct "possibly sent, unverified" state.
    echo "sent=unverified: the message may have been delivered, but the store is unreadable here so it cannot be confirmed. NOT falling back (that would duplicate it)." >&2
    exit 9
  }

  # Confirm by ROWID high-water mark FILTERED TO THIS CHAT, then bind to the
  # stored text. is_delivered lags the INSERT, so poll rather than reporting a
  # transient 0 as final.
  local i newrow="" attempt
  for i in 1 2 3 4 5 6 7 8 9 10; do
    sleep 1
    newrow=$(q "$DB" "select m.ROWID from message m
        join chat_message_join cmj on cmj.message_id = m.ROWID
        join chat c on c.ROWID = cmj.chat_id
       where m.ROWID > $before and m.is_from_me = 1
         and c.chat_identifier = '$CONTACT_HANDLE'
       order by m.ROWID desc limit 1;" 2>/dev/null)
    [ -n "$newrow" ] && break
  done
  [ -n "$newrow" ] || die "sent=unverified: no outgoing row for this chat appeared within 10s; the message may still have been delivered. NOT falling back" 9

  local stored
  stored=$(q "$DB" "select coalesce(text,'') from message where ROWID = $newrow;" 2>/dev/null)
  if [ "$stored" != "$text" ]; then
    die "sent=unverified: row $newrow does not carry the sent text (got ${#stored} bytes); not claiming delivery. NOT falling back" 9
  fi

  # A row that exists but never reaches is_delivered=1 is a real failure, not a
  # success: report it instead of printing delivered=0 and exiting 0.
  local delivered=0 j
  for j in 1 2 3 4 5 6 7 8 9 10; do
    delivered=$(q "$DB" "select coalesce(is_delivered,0) from message where ROWID = $newrow;" 2>/dev/null)
    [ "$delivered" = "1" ] && break
    sleep 1
  done
  if [ "$delivered" != "1" ]; then
    die "row $newrow exists but is_delivered=$delivered after 10s; delivery NOT confirmed. NOT falling back (the row exists, so the peer may have it)" 9
  fi
  echo "sent rowid=$newrow delivered=1"
  exit 0
}

# --- read ---------------------------------------------------------------------
do_read() {
  require_contact
  # A scheduler-spawned caller has no Full Disk Access, so it must pass --db with a
  # snapshot taken by an interactive session.
  db_readable || die "message store unreadable; pass --db SNAPSHOT (taken by an interactive session)" 4

  # A missing conversation must be exit 5, not "0 rows, success": otherwise the
  # chain treats a wrong/unconfigured handle as a working transport with no
  # replies and never falls back.
  local chatexists
  chatexists=$(q "$DB" "select count(*) from chat where chat_identifier = '$CONTACT_HANDLE';" 2>/dev/null)
  [ "${chatexists:-0}" -gt 0 ] || die "contact $CONTACT_HANDLE not found in the message store" 5

  local filt=""
  [ "$THEIRS_ONLY" -eq 1 ] && filt="$filt and m.is_from_me = 0"
  [ "${SINCE_ROWID:-0}" -gt 0 ] && filt="$filt and m.ROWID > $SINCE_ROWID"
  q -separator ' | ' "$DB" "
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
    n=$(q "$DB" "select count(*) from chat where chat_identifier='$CONTACT_HANDLE';" 2>/dev/null)
    [ "${n:-0}" -gt 0 ] || die "contact $CONTACT_HANDLE not found in the message store" 5
    echo "{\"signed_in\":true,\"verified\":\"contact_chat_exists\",\"transport\":\"imessage\",\"contact\":\"$CONTACT_HANDLE\",\"chat_rows\":$n}"
  else
    # Scheduler context: the store is unreadable, so the contact CANNOT be
    # verified. Say so instead of reporting a bare signed_in:true that implies a
    # check we did not perform.
    echo "{\"signed_in\":true,\"verified\":\"imagent_only\",\"db_readable\":false,\"transport\":\"imessage\",\"contact\":\"$CONTACT_HANDLE\"}"
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
