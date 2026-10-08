#!/usr/bin/env bash
# Talk to the user's ChatGPT "dot" assistant.
# Platform-aware architecture:
#   - macOS & Linux: local headless Chrome with multi-account routing. Cross-host SSH fallback to Mac when local Chrome is unavailable.
# Usage: dot.sh [--account <name>] [--url <url>] read [chars]        print tail of conversation (default 5000 chars)
#        dot.sh [--account <name>] [--url <url>] send <message-file> send file contents; while composer holds peer draft,
#                                                                    retry every DOT_RETRY_SECS (60) up to DOT_WAIT_SECS (1800)
#        dot.sh [--account <name>] [--url <url>] send-once <file>    single attempt, no retry
#        dot.sh [--account <name>] login|auth                        launch visible Chrome window on account profile for manual sign-in
# DOT_ACCOUNT selects account (configured in ~/.config/dot/config.json or custom identifier).
# DOT_ALLOW_REMOTE: set to 0 to disable remote fallback (default: enabled on non-Darwin if remote_host configured). Set to 1 to forward immediately.
# DOT_BACKEND=chrome forces backend. DOT_DRY_RUN=1 (chrome send): type, verify, clear, never send.
# Exit codes: 0 ok, 2 usage/error, 3 composer still busy after the wait, 4 send not verified, 5 usage limit reached.
set -euo pipefail

# Ensure standard user and Homebrew binary paths are in PATH
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"

# Parse optional --account / -a / --url / -u flags from arguments
NEW_ARGS=()
URL_EXPLICIT=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --account|-a)
      DOT_ACCOUNT="$2"
      shift 2
      ;;
    --account=*)
      DOT_ACCOUNT="${1#*=}"
      shift 1
      ;;
    --url|-u)
      DOT_URL="$2"
      URL_EXPLICIT=1
      shift 2
      ;;
    --url=*)
      DOT_URL="${1#*=}"
      URL_EXPLICIT=1
      shift 1
      ;;
    *)
      NEW_ARGS+=("$1")
      shift 1
      ;;
  esac
done
set -- ${NEW_ARGS[@]+"${NEW_ARGS[@]}"}

# Resolve Node runtime before any inline node invocations
if [[ -n "${DOT_NODE:-}" ]]; then
  NODE="$DOT_NODE"
elif [[ -x "$HOME/.nvm/versions/node/v22.22.0/bin/node" ]]; then
  NODE="$HOME/.nvm/versions/node/v22.22.0/bin/node"
elif command -v node >/dev/null 2>&1; then
  NODE="$(command -v node)"
elif [[ -d "$HOME/.nvm/versions/node" ]]; then
  NODE="$(ls -1d "$HOME/.nvm/versions/node"/v* 2>/dev/null | tail -1)/bin/node"
else
  NODE="/usr/local/bin/node"
fi
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

CONFIG_FILE="${DOT_CONFIG_FILE:-$HOME/.config/dot/config.json}"
ACCOUNT="${DOT_ACCOUNT:-}"

if [[ -z "$ACCOUNT" && -f "$CONFIG_FILE" ]]; then
  ACCOUNT=$("$NODE" -e '
    try {
      const fs = require("fs");
      const cfg = JSON.parse(fs.readFileSync(process.argv[1], "utf8"));
      process.stdout.write(cfg.default_account || "");
    } catch {}
  ' "$CONFIG_FILE" 2>/dev/null || true)
fi
ACCOUNT="${ACCOUNT:-default}"

# Unify profile directory and URL resolution via dot_chrome.mjs resolve-profile
PROFILE_DIR=""
RESOLVED_URL=""
if [[ -x "$NODE" && -f "$HERE/dot_chrome.mjs" ]]; then
  PROFILE_INFO=$(DOT_ACCOUNT="$ACCOUNT" DOT_CONFIG_FILE="$CONFIG_FILE" DOT_URL="${DOT_URL:-}" DOT_CHROME_USER_DATA="${DOT_CHROME_USER_DATA:-}" "$NODE" "$HERE/dot_chrome.mjs" resolve-profile 2>/dev/null || true)
  if [[ -n "$PROFILE_INFO" ]]; then
    PROFILE_DIR=$("$NODE" -e 'try { process.stdout.write(JSON.parse(process.argv[1]).profileDir || ""); } catch {}' "$PROFILE_INFO" 2>/dev/null || true)
    RESOLVED_URL=$("$NODE" -e 'try { process.stdout.write(JSON.parse(process.argv[1]).url || ""); } catch {}' "$PROFILE_INFO" 2>/dev/null || true)
  fi
fi

if [[ -n "$PROFILE_DIR" ]]; then
  DOT_CHROME_USER_DATA="$PROFILE_DIR"
fi
if [[ -n "$RESOLVED_URL" && -z "${DOT_URL:-}" ]]; then
  DOT_URL="$RESOLVED_URL"
fi
DOT_URL="${DOT_URL:-https://chatgpt.com/}"

if [[ -z "${DOT_BACKEND:-}" || "${DOT_BACKEND:-}" == "auto" ]]; then
  BACKEND="chrome"
else
  BACKEND="$DOT_BACKEND"
fi

case "$BACKEND" in
  auto|chrome)
    BACKEND="chrome"
    ;;
  aside)
    echo "dot.sh: aside backend was retired; use chrome" >&2
    exit 2
    ;;
  *)
    echo "dot.sh: DOT_BACKEND must be chrome or auto" >&2
    exit 2
    ;;
esac

# Print diagnostic invocation banner
URL_HOST=$("$NODE" -e '
  try {
    const u = new URL(process.argv[1]);
    process.stdout.write(u.host || "");
  } catch {
    process.stdout.write(process.argv[1] || "");
  }
' "$DOT_URL" 2>/dev/null || echo "$DOT_URL")
PROFILE_DIR_DISPLAY="${DOT_CHROME_USER_DATA:-~/.config/dot-headless-chrome-${ACCOUNT}}"
echo "dot.sh: account=$ACCOUNT backend=$BACKEND url=$URL_HOST dir=$PROFILE_DIR_DISPLAY" >&2

forward_to_mac() {
  if [[ $# -eq 0 ]]; then return 1; fi
  local action="$1"
  shift
  local REMOTE_HOST="${DOT_REMOTE_HOST:-}"
  if [[ -z "$REMOTE_HOST" && -f "$CONFIG_FILE" ]]; then
    REMOTE_HOST=$("$NODE" -e '
      try {
        const fs = require("fs");
        const cfg = JSON.parse(fs.readFileSync(process.argv[1], "utf8"));
        process.stdout.write(cfg.remote_host || "");
      } catch {}
    ' "$CONFIG_FILE" 2>/dev/null || true)
  fi
  if [[ -n "$REMOTE_HOST" ]]; then
    if [[ "$action" == "read" ]]; then
      local remote_cmd
      remote_cmd=$(python3 -c '
import shlex, sys
url_explicit = sys.argv[1] == "1"
envs = {}
if url_explicit and sys.argv[2]:
    envs["DOT_URL"] = sys.argv[2]
if sys.argv[3]:
    envs["DOT_ACCOUNT"] = sys.argv[3]
if sys.argv[4]:
    envs["DOT_BACKEND"] = sys.argv[4]
if sys.argv[5]:
    envs["DOT_CLEAR_DRAFT"] = sys.argv[5]
envs["DOT_NO_REMOTE"] = "1"
env_str = " ".join(f"{k}={shlex.quote(v)}" for k, v in envs.items())
args_str = " ".join(shlex.quote(a) for a in sys.argv[6:])
print(f"{env_str} ~/.claude/skills/dot/scripts/dot.sh {args_str}".strip())
' "$URL_EXPLICIT" "${DOT_URL:-}" "${DOT_ACCOUNT:-}" "${DOT_BACKEND:-}" "${DOT_CLEAR_DRAFT:-}" "$action" "$@")
      exec ssh "$REMOTE_HOST" "$remote_cmd"
    elif [[ "$action" == "send" || "$action" == "send-once" ]]; then
      local file="${1:-}"
      if [[ ! -f "$file" || ! -s "$file" ]]; then
        echo "dot.sh: message file missing or empty: $file" >&2
        exit 2
      fi
      local remote_tmp
      remote_tmp="$(ssh "$REMOTE_HOST" "mktemp /tmp/dot_remote_XXXXXX")"
      scp -q "$file" "$REMOTE_HOST:$remote_tmp"
      local remote_cmd
      remote_cmd=$(python3 -c '
import shlex, sys
url_explicit = sys.argv[1] == "1"
envs = {}
if url_explicit and sys.argv[2]:
    envs["DOT_URL"] = sys.argv[2]
if sys.argv[3]:
    envs["DOT_ACCOUNT"] = sys.argv[3]
if sys.argv[4]:
    envs["DOT_DRY_RUN"] = sys.argv[4]
if sys.argv[5]:
    envs["DOT_WAIT_SECS"] = sys.argv[5]
if sys.argv[6]:
    envs["DOT_RETRY_SECS"] = sys.argv[6]
if sys.argv[7]:
    envs["DOT_BACKEND"] = sys.argv[7]
if sys.argv[8]:
    envs["DOT_CLEAR_DRAFT"] = sys.argv[8]
envs["DOT_NO_REMOTE"] = "1"
env_str = " ".join(f"{k}={shlex.quote(v)}" for k, v in envs.items())
cmd = f"{env_str} ~/.claude/skills/dot/scripts/dot.sh {shlex.quote(sys.argv[9])} {shlex.quote(sys.argv[10])}; rc=$?; rm -f {shlex.quote(sys.argv[10])}; exit $rc"
print(cmd.strip())
' "$URL_EXPLICIT" "${DOT_URL:-}" "${DOT_ACCOUNT:-}" "${DOT_DRY_RUN:-}" "${DOT_WAIT_SECS:-}" "${DOT_RETRY_SECS:-}" "${DOT_BACKEND:-}" "${DOT_CLEAR_DRAFT:-}" "$action" "$remote_tmp")
      ssh -o ServerAliveInterval=30 -o ServerAliveCountMax=60 "$REMOTE_HOST" "$remote_cmd"
      exit $?
    fi
  fi
  return 1
}

# Cross-host Linux -> Mac forwarding when opted in
if [[ "$(uname -s)" != "Darwin" && "${DOT_ALLOW_REMOTE:-0}" == "1" && "${DOT_NO_REMOTE:-0}" != "1" ]]; then
  forward_to_mac "$@" || true
fi

# Headless Chrome backend. Sets CHROME_OUT; returns 0 if it produced a result, 10 if unavailable
# (nothing was sent), otherwise the script's own exit code.
run_chrome() {
  CHROME_OUT=""
  if [[ ! -x "$NODE" || ! -f "$HERE/dot_chrome.mjs" ]]; then CHROME_OUT="DOT_CHROME_UNAVAILABLE: node or dot_chrome.mjs missing"; return 10; fi
  local rc=0
  local extra_node_path
  if [[ -d "$HOME/.npm-global/lib/node_modules" ]]; then
    extra_node_path="$HOME/.npm-global/lib/node_modules:${NODE_PATH:-}"
  elif [[ -d "$(dirname "$NODE")/../lib/node_modules" ]]; then
    extra_node_path="$(dirname "$NODE")/../lib/node_modules:${NODE_PATH:-}"
  else
    extra_node_path="${NODE_PATH:-}"
  fi
  local runner=()
  if [[ "$(uname -s)" == "Linux" ]]; then
    export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=/run/user/$(id -u)/bus}"
    export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
    if command -v xvfb-run >/dev/null 2>&1; then
      runner=(xvfb-run -a)
    fi
  fi
  local timeout_cmd=()
  if command -v timeout >/dev/null 2>&1; then
    timeout_cmd=(timeout 130)
  elif command -v gtimeout >/dev/null 2>&1; then
    timeout_cmd=(gtimeout 130)
  fi
  CHROME_OUT="$(DOT_ACCOUNT="$ACCOUNT" DOT_URL="$DOT_URL" DOT_CHROME_USER_DATA="${DOT_CHROME_USER_DATA:-}" DOT_CLEAR_DRAFT="${DOT_CLEAR_DRAFT:-}" NODE_PATH="$extra_node_path" ${timeout_cmd[@]+"${timeout_cmd[@]}"} ${runner[@]+"${runner[@]}"} "$NODE" "$HERE/dot_chrome.mjs" "$@" 2>/dev/null)" || rc=$?
  return $rc
}

get_next_account() {
  local current="$1"
  if [[ ! -f "$CONFIG_FILE" ]]; then
    return 1
  fi
  "$NODE" -e '
    try {
      const fs = require("fs");
      const cfg = JSON.parse(fs.readFileSync(process.argv[1], "utf8"));
      const rot = cfg.rotation || Object.keys(cfg.accounts || {});
      const cur = process.argv[2].toLowerCase();
      const curKey = (cfg.aliases && cfg.aliases[cur]) || cur;
      let idx = rot.findIndex(a => a.toLowerCase() === curKey);
      if (idx === -1) {
        idx = rot.findIndex(a => cur.includes(a.toLowerCase()) || a.toLowerCase().includes(cur));
      }
      if (rot.length > 1) {
        const nextIdx = (idx === -1) ? 0 : (idx + 1) % rot.length;
        process.stdout.write(rot[nextIdx]);
      }
    } catch {}
  ' "$CONFIG_FILE" "$current" 2>/dev/null
}

rotate_account_if_needed() {
  local output="$1"
  local action="$2"
  shift 2
  # Never rotate on successful send
  if [[ "$output" == *"DOT_SENT_VERIFIED"* ]]; then
    return 0
  fi
  # Rotate strictly when dot_chrome.mjs detects genuine usage limit banners
  if [[ "${DOT_ROTATE_ON_LIMIT:-1}" == "1" && "$output" == *"DOT_USAGE_LIMIT_REACHED"* ]]; then
    local next_acc
    next_acc="$(get_next_account "$ACCOUNT")"
    local rotated="${DOT_ROTATED_ACCOUNTS:-}"
    if [[ -n "$next_acc" && "$next_acc" != "$ACCOUNT" ]] && ! echo ",$rotated," | grep -q ",$next_acc,"; then
      echo "dot.sh: account '$ACCOUNT' hit usage limit; rotating to '$next_acc'..." >&2
      exec env -u DOT_CHROME_USER_DATA -u DOT_URL DOT_ROTATED_ACCOUNTS="${rotated:+$rotated,}$ACCOUNT" DOT_ACCOUNT="$next_acc" "$BASH" "${BASH_SOURCE[0]}" "$action" "$@"
    fi
  fi
}

cmd_read() {
  local n="${1:-5000}"
  [[ "$n" =~ ^[0-9]+$ ]] || { echo "chars must be an integer" >&2; exit 2; }
  local out=""
  local rc=0
  run_chrome read "$n" || rc=$?
  if [[ $rc -eq 0 ]]; then
    out="$CHROME_OUT"
  else
    [[ $rc -eq 124 ]] && { CHROME_OUT="DOT_CHROME_UNAVAILABLE: timeout"; rc=10; }
    if [[ $rc -eq 10 && "$(uname -s)" != "Darwin" && "${DOT_NO_REMOTE:-0}" != "1" && "${DOT_ALLOW_REMOTE:-1}" != "0" ]]; then
      echo "dot.sh: local chrome unavailable ($CHROME_OUT); attempting remote fallback to Mac..." >&2
      if forward_to_mac read "$n"; then
        exit 0
      fi
    fi
    if [[ $rc -ne 10 ]]; then echo "$CHROME_OUT"; exit "$rc"; fi
    echo "$CHROME_OUT" >&2
    exit 2
  fi
  echo "$out"
}

cmd_send_once() {
  local file="${1:-}"
  [[ -f "$file" && -s "$file" ]] || { echo "usage: dot.sh send <non-empty message-file>" >&2; exit 2; }
  local out="" rc=0
  run_chrome send "$file" || rc=$?
  [[ $rc -ne 0 && $rc -ne 10 ]] && CHROME_OUT="DOT_SEND_UNVERIFIED chrome_rc=$rc"
  if [[ $rc -ne 10 ]]; then
    out="$CHROME_OUT"
  elif [[ "$(uname -s)" != "Darwin" && "${DOT_NO_REMOTE:-0}" != "1" && "${DOT_ALLOW_REMOTE:-1}" != "0" ]]; then
    echo "dot.sh: local chrome unavailable ($CHROME_OUT); attempting remote fallback to Mac..." >&2
    if forward_to_mac send-once "$file"; then
      exit 0
    fi
    echo "$CHROME_OUT" >&2
    exit 2
  else
    echo "$CHROME_OUT" >&2
    exit 2
  fi
  rotate_account_if_needed "$out" "${DOT_ACTION:-send-once}" "$file"
  echo "$out"
  case "$out" in
    *DOT_COMPOSER_MISMATCH*) echo "Composer text did not match the message after typing; nothing sent. Check with 'dot.sh read'." >&2; exit 4 ;;
    *DOT_DRAFT_PRESENT*) echo "Refusing to send: the dot composer holds an unsent draft (a peer session?). Not cleared. Retry later." >&2; exit 3 ;;
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

cmd_login() {
  local dir="${DOT_CHROME_USER_DATA:-}"
  if [[ -z "$dir" ]]; then
    dir="$HOME/.config/dot-headless-chrome-${ACCOUNT}"
  fi
  mkdir -p "$dir"
  local target_url="${DOT_URL:-https://chatgpt.com}"
  echo "dot.sh: launching visible Google Chrome for account '$ACCOUNT'" >&2
  echo "  Profile directory: $dir" >&2
  echo "  URL: $target_url" >&2
  echo "Sign in to ChatGPT in the Chrome window. When finished and the chat page loads, close Chrome." >&2

  local chrome_bin="${DOT_CHROME_BIN:-}"
  if [[ -z "$chrome_bin" ]]; then
    if [[ "$(uname -s)" == "Darwin" ]]; then
      chrome_bin="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    else
      chrome_bin="$(command -v google-chrome || command -v chromium-browser || command -v chromium || true)"
    fi
  fi
  if [[ ! -x "$chrome_bin" ]]; then
    echo "dot.sh: Google Chrome binary not found: $chrome_bin" >&2
    exit 2
  fi
  mkdir -p "$dir/Default"
  rm -f "$dir/Default/.auth_failed"
  touch "$dir/Default/.manual_login"
  "$chrome_bin" --user-data-dir="$dir" --no-first-run --no-default-browser-check "$target_url"
  mkdir -p "$dir/Default"
  rm -f "$dir/Default/.auth_failed"
  touch "$dir/Default/.manual_login"
}

case "${1:-}" in
  read) shift; cmd_read "$@" ;;
  send) shift; cmd_send "$@" ;;
  send-once) shift; cmd_send_once "$@" ;;
  login|auth) shift; cmd_login "$@" ;;
  *) echo "usage: dot.sh [--account <name>] [--url <url>] read [chars] | send|send-once <message-file> | login" >&2; exit 2 ;;
esac
