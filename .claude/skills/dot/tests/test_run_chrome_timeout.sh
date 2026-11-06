#!/usr/bin/env bash
# Regression test: run_chrome's wall-clock bound must kill the whole process
# group (node wrapper + browser descendants), never only the direct child.
# A surviving browser against its live profile corrupts the session cookie
# store (the 2026-10-10 17:00 PDT worldarchitect login loss).
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOT_SH="$SCRIPT_DIR/../scripts/dot.sh"

FIXTURE="$(mktemp -d /tmp/dot-rg-fixture.XXXXXX)"
trap 'kill -KILL -- -${TEST_JOB_PID:-0} 2>/dev/null; rm -rf "$FIXTURE"' EXIT

# Fixture: real dot.sh + fake node + stub dot_chrome.mjs + minimal config.
cp "$DOT_SH" "$FIXTURE/dot.sh"
: > "$FIXTURE/dot_chrome.mjs"
echo '{"default_account":"testacct","accounts":{"testacct":{"url":"https://chatgpt.com/"}}}' > "$FIXTURE/config.json"

cat > "$FIXTURE/node" <<'EOF'
#!/usr/bin/env bash
# Fake node: stub resolver/eval calls; emulate a hung browser wrapper
# (spawn a long-lived descendant like Chrome, then hang).
if [[ "${2:-}" == "resolve-profile" || "${2:-}" == "resolve-profile-existing" ]]; then
  echo '{"profileDir":"","profileDirectory":"","url":"https://chatgpt.com/"}'
  exit 0
fi
if [[ "${1:-}" == "-e" ]]; then
  exit 0
fi
sleep 600 &
echo $! > "$FAKE_BROWSER_PID_FILE"
exec sleep 600
EOF
chmod +x "$FIXTURE/node"

FAKE_BROWSER_PID_FILE="$FIXTURE/browser.pid"
export FAKE_BROWSER_PID_FILE
timed_out_by_test="$FIXTURE/test_kill_marker"

start=$(python3 -c 'import time; print(time.monotonic())')
set -m
DOT_ACCOUNT=testacct DOT_NODE="$FIXTURE/node" DOT_CONFIG_FILE="$FIXTURE/config.json" \
  DOT_CHROME_TIMEOUT_SECS=2 DOT_CHROME_KILL_GRACE_SECS=2 \
  bash "$FIXTURE/dot.sh" read 100 >"$FIXTURE/stdout" 2>"$FIXTURE/stderr" &
TEST_JOB_PID=$!
set +m
( sleep 15; touch "$timed_out_by_test"; kill -KILL -- -"$TEST_JOB_PID" 2>/dev/null ) &
TEST_WATCHDOG=$!

wait "$TEST_JOB_PID"; rc=$?
kill "$TEST_WATCHDOG" 2>/dev/null || true
wait "$TEST_WATCHDOG" 2>/dev/null || true
elapsed=$(python3 -c "import time; print(f'{time.monotonic() - $start:.1f}')")

fails=0
if [[ -e "$timed_out_by_test" ]]; then
  echo "FAIL: dot.sh read did not return within 15s; wall-clock bound not enforced (or not configurable via DOT_CHROME_TIMEOUT_SECS)"
  fails=1
fi
if ! grep -q "DOT_CHROME_UNAVAILABLE: timeout" "$FIXTURE/stderr" 2>/dev/null; then
  echo "FAIL: expected 'DOT_CHROME_UNAVAILABLE: timeout' on stderr; stderr was:"
  sed -n '1,3p' "$FIXTURE/stderr"
  fails=1
fi
if [[ "$rc" != "2" ]]; then
  echo "FAIL: expected exit code 2 (timeout path), got $rc"
  fails=1
fi
browser_pid="$(cat "$FAKE_BROWSER_PID_FILE" 2>/dev/null || true)"
if [[ -n "$browser_pid" ]] && kill -0 "$browser_pid" 2>/dev/null; then
  echo "FAIL: browser descendant (pid $browser_pid) survived the timeout kill -- orphaned against its profile"
  kill -KILL "$browser_pid" 2>/dev/null
  fails=1
fi

if [[ "$fails" == 0 ]]; then
  echo "PASS: timeout returned in ${elapsed}s with rc=$rc; browser descendant dead"
  exit 0
fi
exit 1
