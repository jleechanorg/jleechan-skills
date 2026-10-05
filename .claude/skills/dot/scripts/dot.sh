#!/usr/bin/env bash
# Talk to the user's ChatGPT "dot" assistant.
# Platform-aware architecture:
#   - macOS: Aside or headless Chrome.
#   - Linux: Local headless Chrome or transparent SSH bridge to macOS host.
# Usage: dot.sh [--account <name>] [--url <url>] read [chars]        print tail of conversation (default 5000 chars)
#        dot.sh [--account <name>] [--url <url>] send <message-file> send file contents; while composer holds peer draft,
#                                                                    retry every DOT_RETRY_SECS (60) up to DOT_WAIT_SECS (1800)
#        dot.sh [--account <name>] [--url <url>] send-once <file>    single attempt, no retry
# DOT_ACCOUNT selects account (configured in ~/.config/dot/config.json or custom identifier).
# DOT_BACKEND=aside|chrome|auto forces one backend. DOT_DRY_RUN=1 (chrome send): type, verify, clear, never send.
# Exit codes: 0 ok, 2 usage/error, 3 composer still busy after the wait, 4 send not verified.
set -euo pipefail

# Parse optional --account / -a / --url / -u flags from arguments
NEW_ARGS=()
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
      shift 2
      ;;
    --url=*)
      DOT_URL="${1#*=}"
      shift 1
      ;;
    *)
      NEW_ARGS+=("$1")
      shift 1
      ;;
  esac
done
set -- "${NEW_ARGS[@]}"

CONFIG_FILE="${DOT_CONFIG_FILE:-$HOME/.config/dot/config.json}"
ACCOUNT="${DOT_ACCOUNT:-}"

if [[ -z "$ACCOUNT" && -f "$CONFIG_FILE" ]]; then
  ACCOUNT=$(node -e '
    try {
      const fs = require("fs");
      const cfg = JSON.parse(fs.readFileSync(process.argv[1], "utf8"));
      process.stdout.write(cfg.default_account || "");
    } catch {}
  ' "$CONFIG_FILE" 2>/dev/null || true)
fi
ACCOUNT="${ACCOUNT:-default}"

# Resolve DOT_URL from config if not explicitly set
if [[ -z "${DOT_URL:-}" && -f "$CONFIG_FILE" ]]; then
  DOT_URL=$(node -e '
    try {
      const fs = require("fs");
      const cfg = JSON.parse(fs.readFileSync(process.argv[1], "utf8"));
      const acc = process.argv[2];
      const accKey = (cfg.aliases && cfg.aliases[acc.toLowerCase()]) || acc;
      const accCfg = (cfg.accounts && (cfg.accounts[accKey] || cfg.accounts[accKey.toLowerCase()])) || {};
      const url = accCfg.url || cfg.default_url || "";
      process.stdout.write(url);
    } catch {}
  ' "$CONFIG_FILE" "$ACCOUNT" 2>/dev/null || true)
fi
DOT_URL="${DOT_URL:-https://chatgpt.com/}"

if [[ -z "${DOT_BACKEND:-}" || "${DOT_BACKEND:-}" == "auto" ]]; then
  CONFIG_BACKEND=""
  if [[ -f "$CONFIG_FILE" ]]; then
    CONFIG_BACKEND=$(node -e '
      try {
        const fs = require("fs");
        const cfg = JSON.parse(fs.readFileSync(process.argv[1], "utf8"));
        const acc = process.argv[2];
        const accKey = (cfg.aliases && cfg.aliases[acc.toLowerCase()]) || acc;
        const accCfg = (cfg.accounts && (cfg.accounts[accKey] || cfg.accounts[accKey.toLowerCase()])) || {};
        process.stdout.write(accCfg.backend || "");
      } catch {}
    ' "$CONFIG_FILE" "$ACCOUNT" 2>/dev/null || true)
  fi

  if [[ -n "$CONFIG_BACKEND" ]]; then
    BACKEND="$CONFIG_BACKEND"
  elif [[ "$ACCOUNT" == "aside" || "$ACCOUNT" == "u0" ]]; then
    BACKEND="aside"
  else
    BACKEND="chrome"
  fi
else
  BACKEND="$DOT_BACKEND"
fi
case "$BACKEND" in auto|chrome|aside) ;; *) echo "dot.sh: DOT_BACKEND must be chrome|aside|auto" >&2; exit 2 ;; esac

# Transparent Linux -> Mac forwarding when Aside is not local
if [[ "$(uname -s)" != "Darwin" && "$BACKEND" != "chrome" ]]; then
  REMOTE_HOST="${DOT_REMOTE_HOST:-}"
  if [[ -z "$REMOTE_HOST" ]]; then
    if ssh -q -o BatchMode=yes -o ConnectTimeout=2 macbook true 2>/dev/null; then
      REMOTE_HOST="macbook"
    elif ssh -q -o BatchMode=yes -o ConnectTimeout=2 macbook-ts true 2>/dev/null; then
      REMOTE_HOST="macbook-ts"
    fi
  fi
  if [[ -n "$REMOTE_HOST" ]]; then
    if [[ "${1:-}" == "read" ]]; then
      remote_cmd=$(python3 -c '
import shlex, sys
envs = ["DOT_URL", "DOT_ACCOUNT", "DOT_BACKEND", "DOT_CLEAR_DRAFT"]
env_str = " ".join(f"{k}={shlex.quote(sys.argv[1+i])}" for i, k in enumerate(envs) if sys.argv[1+i])
args_str = " ".join(shlex.quote(a) for a in sys.argv[5:])
print(f"{env_str} ~/.claude/skills/dot/scripts/dot.sh {args_str}".strip())
' "${DOT_URL:-}" "${DOT_ACCOUNT:-}" "${DOT_BACKEND:-}" "${DOT_CLEAR_DRAFT:-}" "$@")
      exec ssh "$REMOTE_HOST" "$remote_cmd"
    elif [[ "${1:-}" == "send" || "${1:-}" == "send-once" ]]; then
      file="${2:-}"
      if [[ ! -f "$file" || ! -s "$file" ]]; then
        echo "dot.sh: message file missing or empty: $file" >&2
        exit 2
      fi
      remote_tmp="/tmp/dot_remote_$(date +%s)_$$.txt"
      scp -q "$file" "$REMOTE_HOST:$remote_tmp"
      remote_cmd=$(python3 -c '
import shlex, sys
envs = ["DOT_URL", "DOT_ACCOUNT", "DOT_DRY_RUN", "DOT_WAIT_SECS", "DOT_RETRY_SECS", "DOT_BACKEND", "DOT_CLEAR_DRAFT"]
env_str = " ".join(f"{k}={shlex.quote(sys.argv[1+i])}" for i, k in enumerate(envs) if sys.argv[1+i])
cmd = f"{env_str} ~/.claude/skills/dot/scripts/dot.sh {shlex.quote(sys.argv[8])} {shlex.quote(sys.argv[9])}; rc=$?; rm -f {shlex.quote(sys.argv[9])}; exit $rc"
print(cmd.strip())
' "${DOT_URL:-}" "${DOT_ACCOUNT:-}" "${DOT_DRY_RUN:-}" "${DOT_WAIT_SECS:-}" "${DOT_RETRY_SECS:-}" "${DOT_BACKEND:-}" "${DOT_CLEAR_DRAFT:-}" "$1" "$remote_tmp")
      ssh -o ServerAliveInterval=30 -o ServerAliveCountMax=60 "$REMOTE_HOST" "$remote_cmd"
      exit $?
    fi
  fi
fi

# Transparent Mac -> Linux forwarding when Chrome backend is requested over SSH
if [[ "$(uname -s)" == "Darwin" && "$BACKEND" == "chrome" && -z "${DOT_NO_REMOTE:-}" ]]; then
  REMOTE_LINUX="${DOT_REMOTE_LINUX:-}"
  if [[ -z "$REMOTE_LINUX" ]]; then
    if ssh -q -o BatchMode=yes -o ConnectTimeout=2 jeff-ubuntu true 2>/dev/null; then
      REMOTE_LINUX="jeff-ubuntu"
    elif ssh -q -o BatchMode=yes -o ConnectTimeout=2 jeff-ubuntu-ts true 2>/dev/null; then
      REMOTE_LINUX="jeff-ubuntu-ts"
    fi
  fi
  if [[ -n "$REMOTE_LINUX" ]]; then
    if [[ "${1:-}" == "read" ]]; then
      remote_cmd=$(python3 -c '
import shlex, sys
envs = ["DOT_URL", "DOT_ACCOUNT", "DOT_BACKEND", "DOT_CLEAR_DRAFT"]
env_str = " ".join(f"{k}={shlex.quote(sys.argv[1+i])}" for i, k in enumerate(envs) if sys.argv[1+i])
args_str = " ".join(shlex.quote(a) for a in sys.argv[5:])
print(f"{env_str} DOT_NO_REMOTE=1 ~/.claude/skills/dot/scripts/dot.sh {args_str}".strip())
' "${DOT_URL:-}" "${DOT_ACCOUNT:-}" "${DOT_BACKEND:-}" "${DOT_CLEAR_DRAFT:-}" "$@")
      exec ssh "$REMOTE_LINUX" "$remote_cmd"
    elif [[ "${1:-}" == "send" || "${1:-}" == "send-once" ]]; then
      file="${2:-}"
      if [[ ! -f "$file" || ! -s "$file" ]]; then
        echo "dot.sh: message file missing or empty: $file" >&2
        exit 2
      fi
      remote_tmp="/tmp/dot_remote_$(date +%s)_$$.txt"
      scp -q "$file" "$REMOTE_LINUX:$remote_tmp"
      remote_cmd=$(python3 -c '
import shlex, sys
envs = ["DOT_URL", "DOT_ACCOUNT", "DOT_DRY_RUN", "DOT_WAIT_SECS", "DOT_RETRY_SECS", "DOT_BACKEND", "DOT_CLEAR_DRAFT"]
env_str = " ".join(f"{k}={shlex.quote(sys.argv[1+i])}" for i, k in enumerate(envs) if sys.argv[1+i])
cmd = f"{env_str} DOT_NO_REMOTE=1 ~/.claude/skills/dot/scripts/dot.sh {shlex.quote(sys.argv[8])} {shlex.quote(sys.argv[9])}; rc=$?; rm -f {shlex.quote(sys.argv[9])}; exit $rc"
print(cmd.strip())
' "${DOT_URL:-}" "${DOT_ACCOUNT:-}" "${DOT_DRY_RUN:-}" "${DOT_WAIT_SECS:-}" "${DOT_RETRY_SECS:-}" "${DOT_BACKEND:-}" "${DOT_CLEAR_DRAFT:-}" "$1" "$remote_tmp")
      ssh -o ServerAliveInterval=30 -o ServerAliveCountMax=60 "$REMOTE_LINUX" "$remote_cmd"
      exit $?
    fi
  fi
fi

SETTLE_MS="${DOT_SETTLE_MS:-7000}"

if [[ -n "${DOT_NODE:-}" ]]; then
  NODE="$DOT_NODE"
elif command -v node >/dev/null 2>&1; then
  NODE="$(command -v node)"
elif [[ -d "$HOME/.nvm/versions/node" ]]; then
  NODE="$(ls -1d "$HOME/.nvm/versions/node"/v* 2>/dev/null | tail -1)/bin/node"
else
  NODE="/usr/local/bin/node"
fi
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

need_aside() { command -v aside >/dev/null 2>&1 || { echo "dot.sh: aside CLI not found on this host; the dot needs an Aside browser signed in to ChatGPT (run from the Mac, e.g. ssh to it)." >&2; exit 2; }; }

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
  CHROME_OUT="$(DOT_ACCOUNT="$ACCOUNT" DOT_URL="$DOT_URL" DOT_CLEAR_DRAFT="${DOT_CLEAR_DRAFT:-}" NODE_PATH="$extra_node_path" timeout 130 "$NODE" "$HERE/dot_chrome.mjs" "$@" 2>/dev/null)" || rc=$?
  return $rc
}

run_repl() { need_aside; timeout 100 aside repl --account "$ACCOUNT" "$1"; }

# Shared prelude: open a fresh tab (attachBrowserTab hangs on throttled tabs) and let it settle.
prelude() {
  cat <<JS
const dotPage = await openTab($(python3 -c 'import json,sys;print(json.dumps(sys.argv[1]))' "$DOT_URL"));
await new Promise(r => setTimeout(r, $SETTLE_MS));
JS
}

cmd_read() {
  local n="${1:-5000}"
  [[ "$n" =~ ^[0-9]+$ ]] || { echo "chars must be an integer" >&2; exit 2; }
  if [[ "$BACKEND" == "chrome" ]]; then
    local rc=0
    run_chrome read "$n" || rc=$?
    if [[ $rc -eq 0 ]]; then echo "$CHROME_OUT"; return 0; fi
    [[ $rc -eq 124 ]] && { CHROME_OUT="DOT_CHROME_UNAVAILABLE: timeout"; rc=10; }
    if [[ $rc -ne 10 ]]; then echo "$CHROME_OUT"; exit "$rc"; fi
    echo "$CHROME_OUT" >&2
    exit 2
  fi
  run_repl "$(prelude)
try {
  const dotText = await dotPage.evaluate(() => document.body.innerText);
  console.log(dotText.slice(-$n));
} finally {
  try { await dotPage.close(); } catch {}
}"
}

cmd_send_once() {
  local file="${1:-}"
  [[ -f "$file" && -s "$file" ]] || { echo "usage: dot.sh send <non-empty message-file>" >&2; exit 2; }
  local msg_json
  msg_json="$(python3 -c 'import json,sys;print(json.dumps(open(sys.argv[1]).read().strip()))' "$file")"
  local out="" rc=0
  [[ "${DOT_DRY_RUN:-}" == 1 && "$BACKEND" == aside ]] && { echo "dot.sh: DOT_DRY_RUN needs the chrome backend" >&2; exit 2; }
  if [[ "$BACKEND" == "chrome" ]]; then
    run_chrome send "$file" || rc=$?
    [[ $rc -ne 0 && $rc -ne 10 ]] && CHROME_OUT="DOT_SEND_UNVERIFIED chrome_rc=$rc"
    if [[ $rc -ne 10 ]]; then out="$CHROME_OUT"
    else echo "$CHROME_OUT" >&2; exit 2; fi
  fi
  if [[ -z "$out" ]]; then
  out="$(run_repl "$(prelude)
try {
  const dotMsg = $msg_json;
  const dotNorm = (t) => t.replace(/\\s+/g, ' ').trim();
  const stripReadReceipt = (t) => t.replace(/Read\\s+\\d{1,2}:\\d{2}\\s*(?:[AP]M)?/gi, '').replace(/\\s+/g, ' ').trim();
  const dotReadComposer = () => dotPage.evaluate(() => (document.querySelector('[contenteditable=true]')||{}).innerText || '');
  const dotGetUserMessages = () => dotPage.evaluate(() => Array.from(document.querySelectorAll('[data-message-author-role=user], article.self, article[class*=\"self\"]')).map(el => (el.innerText || '').replace(/\\s+/g, ' ').trim()));

  const matchesMsg = (m, target) => {
    if (!m || !target) return false;
    const sm = stripReadReceipt(m);
    const st = stripReadReceipt(target);
    return sm === st || sm.includes(st) || st.includes(sm) || (st.length > 40 && sm.includes(st.slice(0, 40)));
  };

  // ChatGPT restores a saved draft lazily on focus, so focus first, then inspect.
  await dotPage.click('[contenteditable=true]');
  await new Promise(r => setTimeout(r, 1500));
  let dotComposer = (await dotReadComposer()).trim();

  if (dotComposer !== '') {
    const normComposer = dotNorm(dotComposer);
    const userMessages = await dotGetUserMessages();
    const dotAlreadySent = userMessages.some(m => m !== '' && matchesMsg(m, normComposer));
    const dotOwnLeftover = normComposer !== '' && (normComposer === dotNorm(dotMsg) || matchesMsg(dotNorm(dotMsg), normComposer));
    if (process.env.DOT_CLEAR_DRAFT === '1' || dotOwnLeftover || dotAlreadySent) {
      await dotPage.keyboard.press('Meta+A');
      await dotPage.keyboard.press('Backspace');
      await new Promise(r => setTimeout(r, 800));
      dotComposer = (await dotReadComposer()).trim();
      console.log('DOT_STALE_DRAFT_CLEARED');
    }
  }
  if (dotComposer !== '') {
    console.log('DOT_DRAFT_PRESENT: ' + dotComposer.slice(0, 300));
  } else {
    await dotPage.keyboard.insertText(dotMsg);
    await new Promise(r => setTimeout(r, 800));
    const typed = (await dotReadComposer()).trim();
    if (dotNorm(typed) !== dotNorm(dotMsg)) {
      console.log('DOT_COMPOSER_MISMATCH: ' + typed.slice(0, 200));
    } else {
      const matchMsg = (m, needle) => {
        if (!m || !needle) return false;
        const sm = stripReadReceipt(m);
        const sn = stripReadReceipt(needle);
        return sm === sn || sm.includes(sn) || sn.includes(sm) || (sn.length > 40 && sm.includes(sn.slice(0, 40)));
      };
      const beforeMsgs = await dotGetUserMessages();
      const countMatches = (msgs, needle) => msgs.filter(m => matchMsg(m, needle)).length;
      const beforeCount = countMatches(beforeMsgs, dotNorm(dotMsg));
      await dotPage.click('button[data-testid=send-button], button[aria-label*=Send]');
      await new Promise(r => setTimeout(r, 4000));
      const left = (await dotReadComposer()).trim();
      const afterMsgs = await dotGetUserMessages();
      const afterCount = countMatches(afterMsgs, dotNorm(dotMsg));
      const sentVerified = left === '' && afterCount > beforeCount;
      console.log(sentVerified ? 'DOT_SENT_VERIFIED' : 'DOT_SEND_UNVERIFIED composer_left=' + left.length);
    }
  }
} finally {
  try { await dotPage.close(); } catch {}
}")"
  fi
  echo "$out"
  case "$out" in
    *DOT_COMPOSER_MISMATCH*) echo "Composer text did not match the message after typing; nothing sent. Check with 'dot.sh read'." >&2; exit 4 ;;
    *DOT_DRAFT_PRESENT*) echo "Refusing to send: the dot composer holds an unsent draft (a peer session?). Not cleared. Retry later." >&2; exit 3 ;;
    *DOT_SENT_VERIFIED*|*DOT_DRYRUN_OK*) ;;
    *) echo "Send not verified in page text; run 'dot.sh read' to check." >&2; exit 4 ;;
  esac
}

cmd_send() {
  local deadline=$((SECONDS + ${DOT_WAIT_SECS:-1800})) rc=0
  while :; do
    (cmd_send_once "$@") && return 0 || rc=$?
    [[ $rc -eq 3 && $SECONDS -lt $deadline ]] || return "$rc"
    echo "dot.sh: composer busy; retrying in ${DOT_RETRY_SECS:-60}s" >&2
    sleep "${DOT_RETRY_SECS:-60}"
  done
}

case "${1:-}" in
  read) shift; cmd_read "$@" ;;
  send) shift; cmd_send "$@" ;;
  send-once) shift; cmd_send_once "$@" ;;
  *) echo "usage: dot.sh [--account <name>] [--url <url>] read [chars] | send|send-once <message-file>" >&2; exit 2 ;;
esac
