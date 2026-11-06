#!/usr/bin/env bash
# Talk to the user's ChatGPT "dot" assistant via local headless Chrome and dedicated account profiles.
# Canonical CLI usage, environment variables, draft handling, and exit codes live in SKILL.md.
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"

NEW_ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --account|-a) DOT_ACCOUNT="$2"; shift 2 ;;
    --account=*) DOT_ACCOUNT="${1#*=}"; shift 1 ;;
    --url|-u) DOT_URL="$2"; shift 2 ;;
    --url=*) DOT_URL="${1#*=}"; shift 1 ;;
    *) NEW_ARGS+=("$1"); shift 1 ;;
  esac
done
set -- ${NEW_ARGS[@]+"${NEW_ARGS[@]}"}

if [[ "${1:-}" == "existing-profile-only" || "${1:-}" == "probe" || "${DOT_PREPARED:-0}" == "1" || "${1:-}" == "send-prepared" ]]; then
  export DOT_NO_REMOTE=1
fi
PROFILE_RESOLVER_MODE="resolve-profile"
[[ "${1:-}" == "probe" ]] && PROFILE_RESOLVER_MODE="resolve-profile-existing"

if [[ -n "${DOT_NODE:-}" ]]; then NODE="$DOT_NODE"
elif [[ -x "$HOME/.nvm/versions/node/v22.22.0/bin/node" ]]; then NODE="$HOME/.nvm/versions/node/v22.22.0/bin/node"
elif command -v node >/dev/null 2>&1; then NODE="$(command -v node)"
elif [[ -d "$HOME/.nvm/versions/node" ]]; then NODE="$(ls -1d "$HOME/.nvm/versions/node"/v* 2>/dev/null | tail -1)/bin/node"
else NODE="/usr/local/bin/node"
fi
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

CONFIG_FILE="${DOT_CONFIG_FILE:-$HOME/.config/dot/config.json}"
ACCOUNT="${DOT_ACCOUNT:-}"
if [[ -z "$ACCOUNT" && -f "$CONFIG_FILE" ]]; then
  ACCOUNT=$("$NODE" -e 'try { process.stdout.write(JSON.parse(require("fs").readFileSync(process.argv[1], "utf8")).default_account || ""); } catch {}' "$CONFIG_FILE" 2>/dev/null || true)
fi
ACCOUNT="${ACCOUNT:-default}"

PROFILE_DIR=""
PROFILE_DIRECTORY=""
RESOLVED_URL=""
if [[ -x "$NODE" && -f "$HERE/dot_chrome.mjs" ]]; then
  if ! PROFILE_INFO=$(DOT_ACCOUNT="$ACCOUNT" DOT_CONFIG_FILE="$CONFIG_FILE" DOT_URL="${DOT_URL:-}" DOT_CHROME_USER_DATA="${DOT_CHROME_USER_DATA:-}" "$NODE" "$HERE/dot_chrome.mjs" "$PROFILE_RESOLVER_MODE" 2>&1); then
    echo "$PROFILE_INFO" >&2; exit 2
  fi
  if [[ -n "$PROFILE_INFO" ]]; then
    PROFILE_DIR=$("$NODE" -e 'try { process.stdout.write(JSON.parse(process.argv[1]).profileDir || ""); } catch {}' "$PROFILE_INFO" 2>/dev/null || true)
    PROFILE_DIRECTORY=$("$NODE" -e 'try { process.stdout.write(JSON.parse(process.argv[1]).profileDirectory || ""); } catch {}' "$PROFILE_INFO" 2>/dev/null || true)
    RESOLVED_URL=$("$NODE" -e 'try { process.stdout.write(JSON.parse(process.argv[1]).url || ""); } catch {}' "$PROFILE_INFO" 2>/dev/null || true)
  fi
fi

if [[ -n "$PROFILE_DIR" ]]; then
  DOT_CHROME_USER_DATA="$PROFILE_DIR"
fi
[[ -n "$RESOLVED_URL" && -z "${DOT_URL:-}" ]] && DOT_URL="$RESOLVED_URL"
DOT_URL="${DOT_URL:-https://chatgpt.com/}"

case "${DOT_BACKEND:-auto}" in
  ""|auto|chrome) BACKEND="chrome" ;;
  *) echo "dot.sh: DOT_BACKEND must be chrome or auto" >&2; exit 2 ;;
esac

if [[ -d "$HOME/.npm-global/lib/node_modules" ]]; then
  EXTRA_NODE_PATH="$HOME/.npm-global/lib/node_modules:${NODE_PATH:-}"
elif [[ -d "$(dirname "$NODE")/../lib/node_modules" ]]; then
  EXTRA_NODE_PATH="$(dirname "$NODE")/../lib/node_modules:${NODE_PATH:-}"
else
  EXTRA_NODE_PATH="${NODE_PATH:-}"
fi

URL_HOST=$("$NODE" -e 'try { process.stdout.write(new URL(process.argv[1]).host || ""); } catch { process.stdout.write(process.argv[1] || ""); }' "$DOT_URL" 2>/dev/null || echo "$DOT_URL")
if [[ "${1:-}" != "existing-profile-only" && "${DOT_PREPARED:-0}" != "1" && "${1:-}" != "send-prepared" ]]; then
  echo "dot.sh: account=$ACCOUNT backend=$BACKEND url=$URL_HOST dir=${DOT_CHROME_USER_DATA:-~/.config/dot-headless-chrome-${ACCOUNT}}" >&2
fi

check_foreign_binary() {
  local bin="${1:-${DOT_CHROME_BIN:-}}"
  if [[ "${DOT_ENFORCE_SYSTEM_CHROME:-0}" == "1" ]] && ! is_system_chrome "$bin" && [[ "${DOT_ALLOW_FOREIGN_BINARY:-0}" != "1" ]]; then
    return 1
  fi
  return 0
}

run_chrome() {
  CHROME_OUT=""
  if [[ ! -x "$NODE" || ! -f "$HERE/dot_chrome.mjs" ]]; then CHROME_OUT="DOT_CHROME_UNAVAILABLE: node or dot_chrome.mjs missing"; return 10; fi
  if ! check_foreign_binary "${DOT_CHROME_BIN:-}"; then
    CHROME_OUT="DOT_CHROME_UNAVAILABLE: refusing non-system Chrome binary '${DOT_CHROME_BIN:-}' (foreign binaries evict Keychain-encrypted session cookies; set DOT_ALLOW_FOREIGN_BINARY=1 only to override deliberately)"
    return 10
  fi
  if ! profile_disk_ok "${DOT_CHROME_USER_DATA:-}"; then
    CHROME_OUT="DOT_CHROME_UNAVAILABLE: low disk"; return 10
  fi
  local rc=0 runner=()
  if [[ "$(uname -s)" == "Linux" ]]; then
    export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=/run/user/$(id -u)/bus}"
    export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
    command -v xvfb-run >/dev/null 2>&1 && runner=(xvfb-run -a)
  fi
  local budget="${DOT_CHROME_TIMEOUT_SECS:-130}" grace="${DOT_CHROME_KILL_GRACE_SECS:-10}"
  local out_file timed_out_file
  out_file="$(mktemp "${TMPDIR:-/tmp}/dot-chrome-out.XXXXXX")"
  timed_out_file="$(mktemp "${TMPDIR:-/tmp}/dot-chrome-timedout.XXXXXX")"
  rm -f "$timed_out_file"
  set -m
  DOT_ACCOUNT="$ACCOUNT" DOT_URL="$DOT_URL" DOT_CHROME_USER_DATA="${DOT_CHROME_USER_DATA:-}" \
    DOT_CLEAR_DRAFT="${DOT_CLEAR_DRAFT:-}" NODE_PATH="$EXTRA_NODE_PATH" \
    ${runner[@]+"${runner[@]}"} "$NODE" "$HERE/dot_chrome.mjs" "$@" >"$out_file" 2>/dev/null &
  local pid=$!
  (
    sleep "$budget" 2>/dev/null
    touch "$timed_out_file" 2>/dev/null
    kill -TERM -- -"$pid" 2>/dev/null || true
    sleep "$grace" 2>/dev/null
    kill -KILL -- -"$pid" 2>/dev/null || true
  ) &
  local watchdog=$!
  wait "$pid" || rc=$?
  if kill -TERM -- -"$pid" 2>/dev/null; then
    sleep "${DOT_CHROME_TEARDOWN_GRACE_SECS:-1}" 2>/dev/null
    kill -KILL -- -"$pid" 2>/dev/null || true
  fi
  set +m
  kill -TERM -- -"$watchdog" 2>/dev/null || true
  wait "$watchdog" 2>/dev/null || true
  CHROME_OUT="$(cat "$out_file")"
  local timed_out=0
  [[ -e "$timed_out_file" ]] && timed_out=1
  rm -f "$out_file" "$timed_out_file"
  [[ "$timed_out" -eq 1 ]] && return 124
  return "$rc"
}

get_next_account() {
  local current="$1"
  [[ -f "$CONFIG_FILE" ]] || return 1
  "$NODE" -e '
    try {
      const cfg = JSON.parse(require("fs").readFileSync(process.argv[1], "utf8"));
      const rot = cfg.rotation || Object.keys(cfg.accounts || {});
      const cur = process.argv[2].toLowerCase();
      const curKey = (cfg.aliases && cfg.aliases[cur]) || cur;
      let idx = rot.findIndex(a => a.toLowerCase() === curKey);
      if (idx === -1) idx = rot.findIndex(a => cur.includes(a.toLowerCase()) || a.toLowerCase().includes(cur));
      if (rot.length > 1) process.stdout.write(rot[(idx === -1) ? 0 : (idx + 1) % rot.length]);
    } catch {}
  ' "$CONFIG_FILE" "$current" 2>/dev/null
}

rotate_account_if_needed() {
  local output="$1" action="$2"; shift 2
  [[ "$output" == *"DOT_SENT_VERIFIED"* ]] && return 0
  if [[ "${DOT_ROTATE_ON_LIMIT:-1}" == "1" && "$output" == *"DOT_USAGE_LIMIT_REACHED"* ]]; then
    local next_acc rotated="${DOT_ROTATED_ACCOUNTS:-}"
    next_acc="$(get_next_account "$ACCOUNT")"
    if [[ -n "$next_acc" && "$next_acc" != "$ACCOUNT" ]] && ! echo ",$rotated," | grep -q ",$next_acc,"; then
      echo "dot.sh: account '$ACCOUNT' hit usage limit; rotating to '$next_acc'..." >&2
      exec env -u DOT_CHROME_USER_DATA -u DOT_URL -u DOT_PROFILE_DIRECTORY DOT_ROTATED_ACCOUNTS="${rotated:+$rotated,}$ACCOUNT" DOT_ACCOUNT="$next_acc" "$BASH" "${BASH_SOURCE[0]}" "$action" "$@"
    fi
  fi
}

profile_disk_ok() {
  local dir="${1:-${DOT_CHROME_USER_DATA:-}}" min_mb="${DOT_MIN_FREE_MB:-512}" free_kb
  [[ -z "$dir" ]] && return 0
  free_kb="$(df -k "$dir" 2>/dev/null | awk 'NR==2 {print $4}')"
  [[ -z "$free_kb" || ! "$free_kb" =~ ^[0-9]+$ ]] && return 0
  if (( free_kb < min_mb * 1024 )); then
    echo "dot.sh: refusing to launch Chrome: only ${free_kb}KB free under $dir (floor ${min_mb}MB). A full disk corrupts the cookie store." >&2
    return 1
  fi
  return 0
}

profile_cookies_db() {
  echo "${DOT_CHROME_USER_DATA:-}/${PROFILE_DIRECTORY:-Default}/Cookies"
}

classify_cookie_store() {
  local db="$1" tokens chatgpt
  [[ -z "$db" || ! -f "$db" ]] && { echo "absent"; return 0; }
  command -v sqlite3 >/dev/null 2>&1 || { echo "unknown"; return 0; }
  tokens="$(sqlite3 "file:$db?mode=ro" 'SELECT count(*) FROM cookies WHERE name LIKE "%session-token%";' 2>/dev/null)"
  chatgpt="$(sqlite3 "file:$db?mode=ro" 'SELECT count(*) FROM cookies WHERE host_key LIKE "%chatgpt.com";' 2>/dev/null)"
  [[ -z "$tokens" || -z "$chatgpt" ]] && { echo "unreadable"; return 0; }
  if (( tokens > 0 )); then echo "authenticated"
  elif (( chatgpt > 0 )); then echo "rebuild"
  else echo "absent"
  fi
}

snapshot_cookie_store() {
  local db="$1" tokens
  [[ "${DOT_SNAPSHOT:-1}" != "1" || -z "$db" || ! -f "$db" ]] && return 0
  command -v sqlite3 >/dev/null 2>&1 || return 0
  tokens="$(sqlite3 "file:$db?mode=ro" 'SELECT count(*) FROM cookies WHERE name LIKE "%session-token%";' 2>/dev/null)"
  [[ "$tokens" =~ ^[0-9]+$ ]] && (( tokens > 0 )) || return 0
  sqlite3 "$db" ".backup '$db.snapshot'" >/dev/null 2>&1 || true
}

is_system_chrome() {
  local bin="$1" sys
  [[ -z "$bin" ]] && return 0
  if [[ "$(uname -s)" == "Darwin" ]]; then
    [[ "$bin" == "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" ]]
  else
    sys="$(command -v google-chrome || command -v chromium-browser || command -v chromium || true)"
    [[ -n "$sys" && "$bin" == "$sys" ]]
  fi
}

emit_store_forensics() {
  if [[ "$(classify_cookie_store "$(profile_cookies_db)" 2>/dev/null)" == "rebuild" ]]; then
    echo "DOT_STORE_REBUILD: the profile's cookie store was rebuilt (client-side eviction — fresh anonymous cookies, zero session tokens). The account itself is likely still signed in server-side. Canonical recovery: dot.sh --account $ACCOUNT login (fresh independent sign-in). Never resync cookies from another browser profile (rotation race)." >&2
  fi
}

cmd_simple() {
  local action="$1" rc=0
  run_chrome "$action" || rc=$?
  [[ $rc -eq 124 ]] && { CHROME_OUT="DOT_CHROME_UNAVAILABLE: timeout"; rc=10; }
  [[ $rc -eq 10 ]] && { echo "$CHROME_OUT" >&2; exit 2; }
  echo "$CHROME_OUT"
  case "$CHROME_OUT" in
    *DOT_DRAFT_SUBMITTED*|*DOT_DRAFT_CLEARED*|*DOT_SUBMIT_NOTHING_TO_SEND*) ;;
    *DOT_DRAFT_CLEAR_FAILED*|*DOT_SUBMIT_UNVERIFIED*) echo "Draft action not verified; run 'dot.sh read' to check." >&2; exit 4 ;;
    *) echo "Draft action unrecognized; run 'dot.sh read' to check." >&2; exit 4 ;;
  esac
}

cmd_read() {
  local n="${1:-5000}" rc=0
  [[ "$n" =~ ^[0-9]+$ ]] || { echo "chars must be an integer" >&2; exit 2; }
  run_chrome read "$n" || rc=$?
  if [[ $rc -eq 0 ]]; then
    snapshot_cookie_store "$(profile_cookies_db)"
    echo "$CHROME_OUT"
  else
    [[ $rc -eq 124 ]] && { CHROME_OUT="DOT_CHROME_UNAVAILABLE: timeout"; rc=10; }
    [[ $rc -ne 10 ]] && { echo "$CHROME_OUT"; exit "$rc"; }
    echo "$CHROME_OUT" >&2; emit_store_forensics; exit 2
  fi
}

cmd_send_once() {
  local file="${1:-}" out="" rc=0
  [[ -f "$file" && -s "$file" ]] || { echo "usage: dot.sh send <non-empty message-file>" >&2; exit 2; }
  if [[ "${DOT_PREPARED:-0}" == "1" ]]; then
    if ! check_foreign_binary "${DOT_CHROME_BIN:-}"; then
      echo "DOT_CHROME_UNAVAILABLE: refusing non-system Chrome binary '${DOT_CHROME_BIN:-}' (foreign binaries evict Keychain-encrypted session cookies; set DOT_ALLOW_FOREIGN_BINARY=1 only to override deliberately)" >&2
      exit 10
    fi
    profile_disk_ok "${DOT_CHROME_USER_DATA:-}" || exit 2
    DOT_ACCOUNT="$ACCOUNT" DOT_URL="$DOT_URL" DOT_CHROME_USER_DATA="${DOT_CHROME_USER_DATA:-}" DOT_CLEAR_DRAFT="${DOT_CLEAR_DRAFT:-}" DOT_PREPARED="1" DOT_NO_REMOTE="1" NODE_PATH="$EXTRA_NODE_PATH" \
      "$NODE" "$HERE/dot_chrome.mjs" send-prepared "$file"
    exit $?
  fi
  run_chrome send "$file" || rc=$?
  [[ $rc -eq 124 ]] && { CHROME_OUT="DOT_CHROME_UNAVAILABLE: timeout"; rc=10; }
  [[ $rc -ne 0 && $rc -ne 10 ]] && CHROME_OUT="DOT_SEND_UNVERIFIED chrome_rc=$rc"
  if [[ $rc -ne 10 ]]; then
    out="$CHROME_OUT"
    [[ "$out" == *DOT_SENT_VERIFIED* ]] && snapshot_cookie_store "$(profile_cookies_db)"
  else
    echo "$CHROME_OUT" >&2; emit_store_forensics; exit 2
  fi
  rotate_account_if_needed "$out" "${DOT_ACTION:-send-once}" "$file"
  echo "$out"
  case "$out" in
    *DOT_COMPOSER_MISMATCH*) echo "Composer text did not match the message after typing; nothing sent. Check with 'dot.sh read'." >&2; exit 4 ;;
    *DOT_DRAFT_PRESENT*) echo "Peer draft present (not sent). Per SKILL.md policy: wait up to 5 min, re-read with 'dot.sh read', then submit-draft (sensible message) or clear-draft (half-typed junk). Nothing sent." >&2; exit 3 ;;
    *DOT_USAGE_LIMIT_REACHED*) echo "ChatGPT usage limit reached: $out" >&2; exit 5 ;;
    *DOT_SENT_VERIFIED*|*DOT_DRYRUN_OK*) ;;
    *) echo "Send not verified in page text; run 'dot.sh read' to check." >&2; exit 4 ;;
  esac
}

cmd_send() {
  export DOT_ACTION="send"
  local deadline=$((SECONDS + ${DOT_WAIT_SECS:-1800})) rc=0
  while :; do
    (cmd_send_once "$@") && return 0 || rc=$?
    [[ $rc -eq 3 && $SECONDS -lt $deadline ]] || return "$rc"
    echo "dot.sh: composer busy; retrying in ${DOT_RETRY_SECS:-60}s" >&2
    sleep "${DOT_RETRY_SECS:-60}"
  done
}

validate_login_profile() {
  local expected_dir="$1" expected_profile_directory="$2" profile_info profile_dir profile_directory
  if ! profile_info=$(DOT_ACCOUNT="$ACCOUNT" DOT_CONFIG_FILE="$CONFIG_FILE" DOT_URL="${DOT_URL:-}" DOT_CHROME_USER_DATA="$expected_dir" "$NODE" "$HERE/dot_chrome.mjs" resolve-profile 2>&1); then
    echo "$profile_info" >&2; return 1
  fi
  profile_dir=$("$NODE" -e 'try { process.stdout.write(JSON.parse(process.argv[1]).profileDir || ""); } catch {}' "$profile_info" 2>/dev/null || true)
  profile_directory=$("$NODE" -e 'try { process.stdout.write(JSON.parse(process.argv[1]).profileDirectory || ""); } catch {}' "$profile_info" 2>/dev/null || true)
  if [[ "$profile_dir" != "$expected_dir" || "$profile_directory" != "$expected_profile_directory" ]]; then
    echo "dot.sh: refusing login because the configured profile changed before launch" >&2; return 1
  fi
}

cmd_login() {
  local dir="${DOT_CHROME_USER_DATA:-}"
  [[ -n "$dir" ]] || { echo "dot.sh: refusing login because the dedicated account profile could not be resolved" >&2; exit 2; }
  validate_login_profile "$dir" "$PROFILE_DIRECTORY" || exit 2
  mkdir -p "$dir"
  local target_url="${DOT_URL:-https://chatgpt.com}" chrome_bin="${DOT_CHROME_BIN:-}"
  echo "dot.sh: launching visible Google Chrome for account '$ACCOUNT' (profile: $dir, url: $target_url). Sign in, wait for the chat page, then close Chrome." >&2
  if [[ -z "$chrome_bin" ]]; then
    if [[ "$(uname -s)" == "Darwin" ]]; then chrome_bin="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    else chrome_bin="$(command -v google-chrome || command -v chromium-browser || command -v chromium || true)"
    fi
  fi
  [[ -x "$chrome_bin" ]] || { echo "dot.sh: Google Chrome binary not found: $chrome_bin" >&2; exit 2; }
  if ! check_foreign_binary "$chrome_bin"; then
    echo "dot.sh: refusing login: '$chrome_bin' is not the system Google Chrome. Foreign binaries evict Keychain-encrypted session cookies. Set DOT_ALLOW_FOREIGN_BINARY=1 only if you deliberately accept that risk." >&2
    exit 2
  fi
  profile_disk_ok "$dir" || exit 2
  if ! validate_login_profile "$dir" "$PROFILE_DIRECTORY"; then
    exit 2
  fi
  local profile_args=() store_args=("--password-store=gnome-libsecret") chrome_rc=0
  [[ -n "$PROFILE_DIRECTORY" ]] && profile_args+=("--profile-directory=$PROFILE_DIRECTORY")
  [[ "$(uname -s)" == "Darwin" ]] && store_args=("--password-store=keychain")
  "$chrome_bin" --user-data-dir="$dir" --no-first-run "${profile_args[@]}" "${store_args[@]}" --no-default-browser-check "$target_url" || chrome_rc=$?
  exit "$chrome_rc"
}

cmd_existing_profile_only() {
  local rc=0
  run_chrome existing-profile-only || rc=$?
  if [[ $rc -ne 0 && $rc -ne 10 ]]; then
    echo "DOT_PROFILE_LAUNCH_RESULT {\"schema_version\":1,\"launch_state\":\"unavailable\",\"diagnostic\":\"transport_error\"}"
    exit "$rc"
  fi
  printf '%s\n' "$CHROME_OUT"
  exit "$rc"
}

cmd_probe() {
  local expected_digest="${1:-}" rc=0
  [[ "$expected_digest" =~ ^[a-f0-9]{64}$ ]] || { echo "usage: dot.sh [--account <name>] probe <expected-email-sha256>" >&2; exit 2; }
  run_chrome probe "$expected_digest" || rc=$?
  if [[ $rc -ne 0 || "$CHROME_OUT" != DOT_SESSION_PROBE\ * ]]; then
    echo "dot.sh: session probe transport unavailable" >&2; emit_store_forensics; exit 2
  fi
  [[ "$CHROME_OUT" == *'"status":"authenticated"'* ]] && snapshot_cookie_store "$(profile_cookies_db)"
  printf '%s\n' "$CHROME_OUT"
}

profile_is_idle() {
  local dir="$1"
  [[ -e "$dir/SingletonLock" ]] && return 1
  ! pgrep -f "user-data-dir=$dir" >/dev/null 2>&1
}

cmd_restore_session() {
  local dir="${DOT_CHROME_USER_DATA:-}"
  [[ -z "$dir" ]] && { echo "dot.sh: profile directory not resolved" >&2; exit 2; }
  local prof="${PROFILE_DIRECTORY:-Default}"
  local db="$dir/$prof/Cookies" snap="$dir/$prof/Cookies.snapshot"
  [[ -f "$snap" ]] || { echo "dot.sh: no session snapshot for this profile. Canonical recovery: dot.sh --account $ACCOUNT login" >&2; exit 2; }
  profile_is_idle "$dir" || { echo "dot.sh: a Chrome process or its SingletonLock owns this profile; close it before restoring" >&2; exit 2; }
  local ts tmp
  ts="$(date +%Y%m%d%H%M%S)"
  tmp="$db.restore-tmp.$$"
  cp "$snap" "$tmp" || { echo "dot.sh: could not stage the snapshot; nothing changed" >&2; exit 2; }
  chmod 600 "$tmp"
  # Re-check immediately before mutating: a launch during staging aborts with
  # nothing changed, so this path does not need the removed profile lock.
  profile_is_idle "$dir" || { rm -f "$tmp"; echo "dot.sh: a Chrome launch started during restore; aborted with nothing changed" >&2; exit 2; }
  if [[ -f "$db" ]]; then
    cp "$db" "$db.pre-restore" || { rm -f "$tmp"; echo "dot.sh: could not keep a pre-restore copy; nothing changed" >&2; exit 2; }
  fi
  # Move the old journal files aside rather than deleting them: a concurrent
  # reader keeps its own inode, and no stale journal is left at the path the
  # restored store is opened from.
  local ext failed=0
  for ext in journal wal shm; do
    if [[ -e "$db-$ext" ]]; then mv -f "$db-$ext" "$db-$ext.pre-restore-$ts" || failed=1; fi
  done
  if [[ "$failed" -eq 1 ]]; then
    rm -f "$tmp"
    echo "dot.sh: could not move a sidecar journal aside; aborted before touching the store (nothing changed)" >&2
    exit 2
  fi
  mv -f "$tmp" "$db" || { rm -f "$tmp"; echo "dot.sh: atomic swap failed; the previous store and $db.pre-restore are unchanged" >&2; exit 2; }
  chmod 600 "$db"
  profile_is_idle "$dir" || echo "dot.sh: WARNING a Chrome launch raced this restore, so it is not verified. Close Chrome and re-run, or use 'dot.sh --account $ACCOUNT login'." >&2
  echo "dot.sh: session snapshot restored atomically (pre-restore copy kept at $db.pre-restore). Verify with 'dot.sh --account $ACCOUNT read'; if not signed in, recover with 'dot.sh --account $ACCOUNT login' (never resync from another profile)." >&2
}

if [[ "${DOT_SKIP_DISPATCH:-0}" != "1" ]]; then
  case "${1:-}" in
    read) shift; cmd_read "$@" ;;
    submit-draft) shift; cmd_simple submit-draft ;;
    clear-draft) shift; cmd_simple clear-draft ;;
    probe) shift; cmd_probe "$@" ;;
    send) shift; cmd_send "$@" ;;
    send-once) shift; cmd_send_once "$@" ;;
    send-prepared) shift; export DOT_PREPARED=1; cmd_send_once "$@" ;;
    existing-profile-only) shift; cmd_existing_profile_only "$@" ;;
    restore-session) shift; cmd_restore_session "$@" ;;
    login|auth) shift; cmd_login "$@" ;;
    *) echo "usage: dot.sh [--account <name>] [--url <url>] read [chars] | submit-draft | clear-draft | probe <expected-email-sha256> | send|send-once|send-prepared <message-file> | existing-profile-only | restore-session | login" >&2; exit 2 ;;
  esac
fi
