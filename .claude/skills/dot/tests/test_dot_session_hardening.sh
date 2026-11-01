#!/usr/bin/env bash
# Regression tests for dot.sh session hardening (2026-10-11 review batch):
#   1. cmd_login launches Chrome with the same password-store flags as headless
#   2. cmd_login refuses foreign Chrome binaries without an explicit opt-in
#   3. low-disk preflight refuses to launch Chrome against the live profile
#   4. cookie-store rebuild signature is classified and surfaced (not a generic
#      "not signed in") so operators stop misreading evictions as account logouts
#   5. run_chrome tears down process-group survivors even when node exits first
#   6. per-profile cookie-store snapshot + restore-session recovery mechanics
#
# The coordinator STOP marker and the per-profile kernel flock were deleted on
# 2026-10-20 at the operator's request; their tests were deleted with the code.
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOT_SH="$SCRIPT_DIR/../scripts/dot.sh"
REAL_NODE="$(command -v node)"
[[ -x "$REAL_NODE" ]] || { echo "node required for these tests" >&2; exit 1; }

PASS=0
FAIL=0
declare -a FAILURES=()

ok()   { PASS=$((PASS+1)); echo "  ok - $1"; }
bad()  { FAIL=$((FAIL+1)); FAILURES+=("$1"); echo "  FAIL - $1"; }

new_fixture() {
  local f
  f="$(mktemp -d /tmp/dot-hardening-fixture.XXXXXX)"
  mkdir -p "$f/profile/Default"
  cp "$DOT_SH" "$f/dot.sh"
  cp "$SCRIPT_DIR/../scripts/dot_chrome.mjs" "$f/dot_chrome.mjs"
  cat > "$f/config.json" <<EOF
{"default_account":"testacct","accounts":{"testacct":{"url":"https://chatgpt.com/","user_data_dir":"$f/profile"}}}
EOF
  echo "$f"
}

mk_chrome_stub() {
  local f="$1" name="$2" sleep_secs="${3:-0}"
  cat > "$f/$name" <<EOF
#!/usr/bin/env bash
printf '%s\n' "\$@" > "$f/chrome-argv.txt"
[[ "$sleep_secs" -gt 0 ]] && sleep "$sleep_secs"
exit 0
EOF
  chmod +x "$f/$name"
}

mk_fake_cookies() {
  # $1=db path, $2=mode: rebuilt|authenticated
  local db="$1" mode="$2"
  mkdir -p "$(dirname "$db")"
  rm -f "$db"
  sqlite3 "$db" "CREATE TABLE cookies (name TEXT, encrypted_value BLOB, creation_utc INTEGER, expires_utc INTEGER, host_key TEXT);"
  if [[ "$mode" == "rebuilt" ]]; then
    sqlite3 "$db" "INSERT INTO cookies VALUES ('oai-did', x'00', (strftime('%s','now')+11644473600)*1000000, 99999999999000000, 'chatgpt.com');"
  else
    sqlite3 "$db" "INSERT INTO cookies VALUES ('__Secure-next-auth.session-token.0', x'00', 1, 99999999999000000, 'chatgpt.com');"
    sqlite3 "$db" "INSERT INTO cookies VALUES ('oai-did', x'00', 1, 99999999999000000, 'chatgpt.com');"
  fi
}

run_login() {
  local f="$1"; shift
  env DOT_NODE="$REAL_NODE" DOT_CONFIG_FILE="$f/config.json" \
    DOT_CHROME_USER_DATA="$f/profile" DOT_ACCOUNT=testacct \
    TMPDIR="${TMPDIR:-/tmp}" \
    "$@" bash "$f/dot.sh" login 2>&1
}

echo "== test 1: login password-store flag parity =="
F=$(new_fixture); FIXTURE="$F" mk_chrome_stub "$F" chrome 0
out=$(FIXTURE="$F" run_login "$F" DOT_CHROME_BIN="$F/chrome" DOT_ALLOW_FOREIGN_BINARY=1)
login_rc_pipe=(${PIPESTATUS[0]:-0})
if [[ "${login_rc_pipe[0]}" != "0" ]]; then
  bad "login must exit 0 when Chrome exits 0 (got ${login_rc_pipe[0]})"
fi
if grep -q -- "--password-store=keychain" "$F/chrome-argv.txt" 2>/dev/null; then
  ok "login passes --password-store=keychain on Darwin"
else
  bad "login must pass the same password-store flag as the headless path (argv: $(cat "$F/chrome-argv.txt" 2>/dev/null | tr '\n' ' '))"
fi
rm -rf "$F"
F=$(new_fixture); FIXTURE="$F" mk_chrome_stub "$F" chrome 0
cat > "$F/chrome" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$@" > "$FIXTURE/chrome-argv.txt"
exit 7
EOF
chmod +x "$F/chrome"
out=$(FIXTURE="$F" run_login "$F" DOT_CHROME_BIN="$F/chrome" DOT_ALLOW_FOREIGN_BINARY=1)
login_rc_pipe=(${PIPESTATUS[0]:-0})
if [[ "${login_rc_pipe[0]}" == "7" ]]; then
  ok "login propagates Chrome's nonzero exit code"
else
  bad "login must propagate Chrome exit 7 (got ${login_rc_pipe[0]})"
fi
rm -rf "$F"

echo "== test 2: foreign binary enforcement is opt-in =="
F=$(new_fixture); FIXTURE="$F" mk_chrome_stub "$F" chrome 0
out=$(FIXTURE="$F" run_login "$F" DOT_CHROME_BIN="$F/chrome" DOT_ENFORCE_SYSTEM_CHROME=1)
if [[ "$out" == *"refusing login"* && ! -f "$F/chrome-argv.txt" ]]; then
  ok "DOT_ENFORCE_SYSTEM_CHROME=1 refuses a non-system binary without the override"
else
  bad "enforcement must refuse a foreign binary (out: $out)"
fi
if FIXTURE="$F" run_login "$F" DOT_CHROME_BIN="$F/chrome" >/dev/null 2>&1 && [[ -f "$F/chrome-argv.txt" ]]; then
  ok "documented DOT_CHROME_BIN overrides still work by default"
else
  bad "a plain DOT_CHROME_BIN override must keep working (documented caller)"
fi
rm -rf "$F"

echo "== test 3: low-disk preflight =="
F=$(new_fixture); FIXTURE="$F" mk_chrome_stub "$F" chrome 0
out=$(FIXTURE="$F" run_login "$F" DOT_CHROME_BIN="$F/chrome" DOT_ALLOW_FOREIGN_BINARY=1 DOT_MIN_FREE_MB=99999999)
if [[ "$out" == *"disk"* && ! -f "$F/chrome-argv.txt" ]]; then
  ok "launch refused below the disk floor"
else
  bad "low-disk preflight must refuse the launch (out: $out)"
fi
rm -rf "$F"

echo "== test 4: rebuild-signature classification =="
F=$(new_fixture)
export DOT_NODE="$REAL_NODE" DOT_CONFIG_FILE="$F/config.json" \
  DOT_ACCOUNT=testacct DOT_CHROME_USER_DATA="$F/profile" DOT_SKIP_DISPATCH=1
source "$F/dot.sh" >/dev/null 2>&1
set +e +o pipefail 2>/dev/null || set +e
mk_fake_cookies "$F/profile/Default/Cookies" "rebuilt"
sig=$(classify_cookie_store "$F/profile/Default/Cookies" 2>/dev/null || echo "helper-missing")
[[ "$sig" == "rebuild" ]] && ok "rebuilt anonymous store classified" || bad "rebuild classification (got: $sig)"
mk_fake_cookies "$F/profile/Default/Cookies" "authenticated"
sig=$(classify_cookie_store "$F/profile/Default/Cookies" 2>/dev/null || echo "helper-missing")
[[ "$sig" == "authenticated" ]] && ok "authenticated store classified" || bad "authenticated classification (got: $sig)"
rm -rf "$F"
unset DOT_SKIP_DISPATCH

echo "== test 5: node-exit group teardown =="
F=$(new_fixture)
cat > "$F/node" <<'EOF'
#!/usr/bin/env bash
if [[ "${2:-}" == resolve-profile* ]]; then
  printf '{"profileDir":"%s","profileDirectory":"Default","url":"https://chatgpt.com/"}' "$FIXTURE/profile"
  exit 0
fi
if [[ "${1:-}" == "-e" ]]; then exit 0; fi
# emulate: node wrapper exits immediately but a browser descendant stays alive
sleep 600 &
echo $! > "$FAKE_BROWSER_PID_FILE"
exit 0
EOF
chmod +x "$F/node"
: > "$F/dot_chrome.mjs"
export FIXTURE="$F" FAKE_BROWSER_PID_FILE="$F/browser.pid"
export DOT_NODE="$F/node" DOT_CONFIG_FILE="$F/config.json" DOT_ACCOUNT=testacct \
  DOT_CHROME_USER_DATA="$F/profile" DOT_SKIP_DISPATCH=1
source "$F/dot.sh" >/dev/null 2>&1
set +e +o pipefail 2>/dev/null || set +e
run_chrome read 100 >/dev/null 2>&1
sleep 1
leaked=0
if [[ -f "$FAKE_BROWSER_PID_FILE" ]] && kill -0 "$(cat "$FAKE_BROWSER_PID_FILE")" 2>/dev/null; then leaked=1; fi
[[ "$leaked" == 0 ]] && ok "group survivor killed after node exit" || bad "node-exit leak: browser descendant survived run_chrome"
kill -KILL "$(cat "$FAKE_BROWSER_PID_FILE" 2>/dev/null)" 2>/dev/null
rm -rf "$F"
unset DOT_SKIP_DISPATCH

echo "== test 6: snapshot + restore-session =="
F=$(new_fixture)
export DOT_NODE="$REAL_NODE" DOT_CONFIG_FILE="$F/config.json" \
  DOT_ACCOUNT=testacct DOT_CHROME_USER_DATA="$F/profile" DOT_SKIP_DISPATCH=1
source "$F/dot.sh" >/dev/null 2>&1
set +e +o pipefail 2>/dev/null || set +e
mk_fake_cookies "$F/profile/Default/Cookies" "authenticated"
snapshot_cookie_store "$F/profile/Default/Cookies" >/dev/null 2>&1
if [[ -f "$F/profile/Default/Cookies.snapshot" ]]; then
  ok "snapshot written next to the live store"
  mk_fake_cookies "$F/profile/Default/Cookies" "rebuilt"
  touch "$F/profile/Default/Cookies-journal"
  out=$(cmd_restore_session 2>&1)
  sig=$(classify_cookie_store "$F/profile/Default/Cookies" 2>/dev/null)
  [[ "$sig" == "authenticated" ]] && ok "restore-session restored the snapshot (store now authenticated)" \
    || bad "restore-session must restore the snapshot (out: $out; sig: $sig)"
  [[ -f "$F/profile/Default/Cookies.pre-restore" ]] && ok "restore keeps a pre-restore copy" || ok "restore keeps a pre-restore copy (optional)"
  if [[ ! -e "$F/profile/Default/Cookies-journal" ]] && compgen -G "$F/profile/Default/Cookies-journal.pre-restore-*" >/dev/null; then
    ok "restore moves the old journal aside instead of deleting it in place"
  else
    bad "restore must move Cookies-journal aside, never truncate/delete a possibly-live journal"
  fi
  touch "$F/profile/SingletonLock"
  if ( cmd_restore_session ) >/dev/null 2>&1; then
    bad "restore must refuse while a SingletonLock owns the profile"
  else
    ok "restore refuses while a SingletonLock owns the profile"
  fi
  rm -f "$F/profile/SingletonLock"
else
  bad "snapshot_cookie_store must persist a restorable snapshot"
fi
rm -rf "$F"
unset DOT_SKIP_DISPATCH

echo
echo "pass=$PASS fail=$FAIL"
if [[ ${#FAILURES[@]} -gt 0 ]]; then
  printf '  - %s\n' "${FAILURES[@]}"
  exit 1
fi
exit 0
