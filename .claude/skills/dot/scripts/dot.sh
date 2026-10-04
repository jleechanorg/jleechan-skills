#!/usr/bin/env bash
# Talk to the user's ChatGPT "dot" assistant: headless Chrome first (dot_chrome.mjs), Aside (account u0) fallback.
# Usage: dot.sh read [chars]        print the tail of the conversation (default 5000 chars)
#        dot.sh send <message-file> send file contents; while the composer holds a peer's unsent
#                                   draft, retry every DOT_RETRY_SECS (60) up to DOT_WAIT_SECS (1800)
#        dot.sh send-once <file>    single attempt, no retry
# DOT_BACKEND=chrome|aside forces one backend (no fallback); default tries chrome, then aside only when
# chrome failed before sending anything (DOT_CHROME_UNAVAILABLE). DOT_DRY_RUN=1 (chrome send): type, verify, clear, never send.
# Exit codes: 0 ok, 2 usage/error, 3 composer still busy after the wait, 4 send not verified.
set -euo pipefail

# Transparent Linux -> Mac forwarding when Aside is not local
if [[ "$(uname -s)" != "Darwin" && "${DOT_BACKEND:-auto}" != "chrome" ]]; then
  REMOTE_HOST=""
  if ssh -q -o ConnectTimeout=2 macbook true 2>/dev/null; then
    REMOTE_HOST="macbook"
  elif ssh -q -o ConnectTimeout=2 macbook-ts true 2>/dev/null; then
    REMOTE_HOST="macbook-ts"
  fi
  if [[ -n "$REMOTE_HOST" ]]; then
    if [[ "${1:-}" == "read" ]]; then
      exec ssh "$REMOTE_HOST" "~/.claude/skills/dot/scripts/dot.sh" "$@"
    elif [[ "${1:-}" == "send" || "${1:-}" == "send-once" ]]; then
      file="${2:-}"
      if [[ -f "$file" ]]; then
        remote_tmp="/tmp/dot_remote_$(date +%s)_$$.txt"
        scp -q "$file" "$REMOTE_HOST:$remote_tmp"
        ssh "$REMOTE_HOST" "~/.claude/skills/dot/scripts/dot.sh $1 $remote_tmp; rm -f $remote_tmp"
        exit $?
      fi
    fi
  fi
fi

DOT_URL="${DOT_URL:-https://chatgpt.com/dots/01a0f819-a779-775c-9d48-8c6035034033}"
ACCOUNT="${DOT_ACCOUNT:-u0}"
SETTLE_MS="${DOT_SETTLE_MS:-7000}"

if [[ -z "${DOT_BACKEND:-}" ]]; then
  if [[ "$(uname -s)" == "Darwin" ]] && command -v aside >/dev/null 2>&1; then
    BACKEND="aside"
  else
    BACKEND="chrome"
  fi
else
  BACKEND="$DOT_BACKEND"
fi
case "$BACKEND" in auto|chrome|aside) ;; *) echo "dot.sh: DOT_BACKEND must be chrome|aside|auto" >&2; exit 2 ;; esac

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
  local node_lib="$(dirname "$NODE")/../lib/node_modules"
  local extra_node_path=""
  if [[ -d "$node_lib" ]]; then
    extra_node_path="$node_lib:${NODE_PATH:-}"
  else
    extra_node_path="${NODE_PATH:-}"
  fi
  CHROME_OUT="$(NODE_PATH="$extra_node_path" timeout 130 "$NODE" "$HERE/dot_chrome.mjs" "$@" 2>/dev/null)" || rc=$?
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
  if [[ "$BACKEND" != aside ]]; then
    local rc=0
    run_chrome read "$n" || rc=$?
    if [[ $rc -eq 0 ]]; then echo "$CHROME_OUT"; return 0; fi
    [[ $rc -eq 124 ]] && { CHROME_OUT="DOT_CHROME_UNAVAILABLE: timeout"; rc=10; }
    if [[ $rc -ne 10 ]]; then echo "$CHROME_OUT"; exit "$rc"; fi
    if [[ "$BACKEND" == chrome ]]; then echo "$CHROME_OUT" >&2; exit 2; fi
    echo "dot.sh: $CHROME_OUT; falling back to Aside" >&2
  fi
  run_repl "$(prelude)
const dotText = await dotPage.evaluate(() => document.body.innerText);
console.log(dotText.slice(-$n));"
}

cmd_send_once() {
  local file="${1:-}"
  [[ -f "$file" && -s "$file" ]] || { echo "usage: dot.sh send <non-empty message-file>" >&2; exit 2; }
  local msg_json
  msg_json="$(python3 -c 'import json,sys;print(json.dumps(open(sys.argv[1]).read().strip()))' "$file")"
  local out="" rc=0
  [[ "${DOT_DRY_RUN:-}" == 1 && "$BACKEND" == aside ]] && { echo "dot.sh: DOT_DRY_RUN needs the chrome backend" >&2; exit 2; }
  if [[ "$BACKEND" != aside ]]; then
    run_chrome send "$file" || rc=$?
    # Any chrome result other than "unavailable" may follow a click, so never re-send via Aside.
    [[ $rc -ne 0 && $rc -ne 10 ]] && CHROME_OUT="DOT_SEND_UNVERIFIED chrome_rc=$rc"
    if [[ $rc -ne 10 ]]; then out="$CHROME_OUT"
    elif [[ "$BACKEND" == chrome || "${DOT_DRY_RUN:-}" == 1 ]]; then echo "$CHROME_OUT" >&2; exit 2
    else echo "dot.sh: $CHROME_OUT; falling back to Aside" >&2; fi
  fi
  if [[ -z "$out" ]]; then
  out="$(run_repl "$(prelude)
const dotMsg = $msg_json;
const dotCount = (hay, needle) => hay.split(needle).length - 1;
// The composer renders newlines as paragraphs, so compare whitespace-normalized text.
const dotNorm = (t) => t.replace(/\s+/g, ' ').trim();
const dotReadComposer = () => dotPage.evaluate(() => (document.querySelector('[contenteditable=true]')||{}).innerText || '');
// ChatGPT restores a saved draft lazily on focus, so focus first, then inspect.
await dotPage.click('[contenteditable=true]');
await new Promise(r => setTimeout(r, 1500));
let dotComposer = (await dotReadComposer()).trim();
// Our own message left by an earlier interrupted send: clear and retype it.
const dotOwnLeftover = dotComposer !== '' && dotNorm(dotComposer) === dotNorm(dotMsg);
if (dotComposer !== '') {
  const body0 = await dotPage.evaluate(() => document.body.innerText);
  const key = dotComposer.slice(0, 80);
  // A draft whose text already appears outside the composer was already sent: stale, safe to clear.
  if (dotOwnLeftover || dotCount(body0, key) >= 2) {
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
    const key = dotMsg.split('\n')[0].slice(0, 80);
    const before = dotCount(await dotPage.evaluate(() => document.body.innerText), key);
    await dotPage.click('button[data-testid=send-button], button[aria-label*=Send]');
    await new Promise(r => setTimeout(r, 4000));
    const left = (await dotReadComposer()).trim();
    const afterBody = await dotPage.evaluate(() => document.body.innerText);
    // Sent = composer emptied and the text now appears in the conversation (not only the composer).
    console.log(left === '' && dotCount(afterBody, key) >= 1 && before >= 1 ? 'DOT_SENT_VERIFIED' : 'DOT_SEND_UNVERIFIED composer_left=' + left.length);
  }
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
  *) echo "usage: dot.sh read [chars] | send|send-once <message-file>" >&2; exit 2 ;;
esac
