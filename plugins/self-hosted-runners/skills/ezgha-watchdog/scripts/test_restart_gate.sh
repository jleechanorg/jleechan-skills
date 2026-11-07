#!/usr/bin/env bash
# test_restart_gate.sh — verify ezgha-fleet-watchdog.sh does NOT execute a
# live restart (launchctl kickstart) by default, matching SKILL.md's stated
# "restart-only remediation is UNAVAILABLE (fail-closed)" policy, and DOES
# restart when the operator explicitly opts in via
# EZGHA_WATCHDOG_ALLOW_RESTART=1.
#
# Real bug this guards against: the deployed watchdog script called
# `launchctl kickstart -k` / `systemctl restart ezgha` unconditionally once
# past the hysteresis threshold, with no way to disable it short of
# `--dry-run` (which also changes the normal host-readiness path) —
# contradicting the doc's fail-closed policy. Found by a real
# /advice pass on PR #8393, 2026-07-16.
#
# Usage: bash <skill-dir>/scripts/test_restart_gate.sh
# Exit 0 on PASS, non-zero on FAIL.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WATCHDOG="$SCRIPT_DIR/ezgha-fleet-watchdog.sh"
FAIL=0

setup_env() {
  local test_home="$1" managed="${2:-3}"
  mkdir -p "$test_home/.config/ezgha" "$test_home/bin"
  printf '[runner]\ncount = 6\n' > "$test_home/.config/ezgha/config.toml"

  # Fake ezgha binary — reports $managed managed containers (default 3 < 6,
  # i.e. below target).
  cat > "$test_home/bin/ezgha" <<EOF
#!/usr/bin/env bash
echo "managed containers: $managed"
EOF
  chmod +x "$test_home/bin/ezgha"

  # Minimal python3 stand-in for the two reads the watchdog performs. Keeps the
  # harness independent of the host Python version (tomllib needs >= 3.11).
  cat > "$test_home/bin/python3" <<'EOF'
#!/usr/bin/env bash
input="$(cat)"
case "$input" in
  *'"name"'*)
    # colima list --json -> default profile status
    printf 'Running\n'
    ;;
  *'[runner]'*)
    printf '%s\n' "$input" | sed -n 's/^[[:space:]]*count[[:space:]]*=[[:space:]]*\([0-9][0-9]*\).*/\1/p'
    ;;
esac
EOF
  chmod +x "$test_home/bin/python3"

  # Fake ssh — never touches the real network. Serves the two remote reads the
  # Linux host check performs.
  cat > "$test_home/bin/ssh" <<'EOF'
#!/usr/bin/env bash
case "$*" in
  *"cat ~/.config/ezgha/config.toml"*)
    printf '[runner]\ncount = %s\n' "${FAKE_SSH_COUNT:-1}"
    ;;
  *"ezgha status"*)
    # The remote command already greps out the count; emit the bare number.
    printf '%s\n' "${FAKE_SSH_MANAGED:-1}"
    ;;
  *)
    echo "unexpected ssh invocation: $*" >&2
    exit 99
    ;;
esac
EOF
  chmod +x "$test_home/bin/ssh"

  # Fake colima — model the default profile as Running and fail closed if
  # the watchdog unexpectedly attempts to mutate the host during this test.
  cat > "$test_home/bin/colima" <<'EOF'
#!/usr/bin/env bash
if [[ "${1:-}" == "list" && "${2:-}" == "--json" ]]; then
  echo '{"name":"default","status":"Running"}'
  exit 0
fi
if [[ "${1:-}" == "start" ]]; then
  echo "FAIL: test fixture forbids colima start" >&2
  exit 97
fi
echo "FAIL: unexpected colima invocation: $*" >&2
exit 98
EOF
  chmod +x "$test_home/bin/colima"

  # Fake launchctl — records invocation instead of touching the real
  # supervisor. This is the action under test.
  cat > "$test_home/bin/launchctl" <<EOF
#!/usr/bin/env bash
echo "\$@" >> "$test_home/launchctl_invocations.log"
EOF
  chmod +x "$test_home/bin/launchctl"
}

run_watchdog() {
  # run_watchdog <home> <allow_restart> [args...] — prints combined output.
  local test_home="$1" allow_restart="${2:-}"
  shift 2
  HOME="$test_home" \
    PATH="$test_home/bin:$PATH" \
    EZGHA_BIN="$test_home/bin/ezgha" \
    RUNNER_LAUNCHD_LABEL="example.ezgha" \
    RUNNER_HOST="${CASE_RUNNER_HOST:-}" \
    EZGHA_WATCHDOG_STATE_DIR="$test_home/state" \
    EZGHA_WATCHDOG_ALLOW_RESTART="$allow_restart" \
    bash "$WATCHDOG" "$@" 2>&1
}

run_to_threshold() {
  # HYSTERESIS_THRESHOLD is 2 (fires on the 3rd consecutive below-target
  # sample), so 3 invocations are needed to cross it.
  local test_home="$1"
  local allow_restart="${2:-}"
  for _ in 1 2 3; do
    HOME="$test_home" \
      PATH="$test_home/bin:$PATH" \
      EZGHA_BIN="$test_home/bin/ezgha" \
      RUNNER_LAUNCHD_LABEL="example.ezgha" \
      EZGHA_WATCHDOG_STATE_DIR="$test_home/state" \
      EZGHA_WATCHDOG_ALLOW_RESTART="$allow_restart" \
      bash "$WATCHDOG" --host mac >/dev/null 2>&1
  done
}

echo "=== Case 1: default (no opt-in) must NOT restart ==="
TMP1="$(mktemp -d)"
setup_env "$TMP1"
run_to_threshold "$TMP1" ""
if [[ -f "$TMP1/launchctl_invocations.log" ]]; then
  echo "FAIL: launchctl was invoked without EZGHA_WATCHDOG_ALLOW_RESTART=1"
  cat "$TMP1/launchctl_invocations.log"
  FAIL=1
else
  echo "PASS: no restart fired by default (fail-closed)"
fi
rm -rf "$TMP1"

echo "=== Case 2: explicit opt-in (EZGHA_WATCHDOG_ALLOW_RESTART=1) MUST restart ==="
TMP2="$(mktemp -d)"
setup_env "$TMP2"
run_to_threshold "$TMP2" "1"
if [[ -f "$TMP2/launchctl_invocations.log" ]] && grep -q "kickstart" "$TMP2/launchctl_invocations.log"; then
  echo "PASS: restart fired with explicit opt-in"
else
  echo "FAIL: launchctl kickstart was NOT invoked even with EZGHA_WATCHDOG_ALLOW_RESTART=1"
  FAIL=1
fi
rm -rf "$TMP2"

echo ""
echo "=== Case 3: explicit --host linux with RUNNER_HOST unset is a config error ==="
TMP3="$(mktemp -d)"
setup_env "$TMP3"
OUT3="$(run_watchdog "$TMP3" "" --host linux)"
RC3=$?
if [[ $RC3 -eq 2 ]]; then echo "PASS: exit 2"; else echo "FAIL: expected exit 2, got $RC3"; FAIL=1; fi
case "$OUT3" in
  *"RUNNER_HOST not configured"*) echo "PASS: diagnostic names RUNNER_HOST" ;;
  *) echo "FAIL: missing RUNNER_HOST diagnostic: $OUT3"; FAIL=1 ;;
esac
case "$OUT3" in
  *"OK:"*) echo "FAIL: unconfigured host reported as OK"; FAIL=1 ;;
  *) echo "PASS: no healthy claim for the unconfigured host" ;;
esac
rm -rf "$TMP3"

echo ""
echo "=== Case 4: default both-host run without RUNNER_HOST is not healthy either ==="
TMP4="$(mktemp -d)"
setup_env "$TMP4"
OUT4="$(run_watchdog "$TMP4" "")"
RC4=$?
if [[ $RC4 -eq 2 ]]; then echo "PASS: exit 2"; else echo "FAIL: expected exit 2, got $RC4"; FAIL=1; fi
case "$OUT4" in
  *"OK:"*) echo "FAIL: summary claims healthy with an unconfigured host"; FAIL=1 ;;
  *) echo "PASS: no healthy summary" ;;
esac
case "$OUT4" in
  *"checked hosts (mac, linux)"*) echo "PASS: summary names both checked hosts" ;;
  *) echo "FAIL: summary does not name checked hosts: $OUT4"; FAIL=1 ;;
esac
rm -rf "$TMP4"

echo ""
echo "=== Case 5: --host mac at target names only the checked host, never 'both hosts' ==="
TMP5="$(mktemp -d)"
setup_env "$TMP5" 6
OUT5="$(run_watchdog "$TMP5" "" --host mac)"
RC5=$?
if [[ $RC5 -eq 0 ]]; then echo "PASS: exit 0"; else echo "FAIL: expected exit 0, got $RC5: $OUT5"; FAIL=1; fi
case "$OUT5" in
  *"checked host(s) at configured count: mac"*) echo "PASS: summary names mac" ;;
  *) echo "FAIL: missing per-host summary: $OUT5"; FAIL=1 ;;
esac
case "$OUT5" in
  *"both hosts"*) echo "FAIL: claims both hosts were checked"; FAIL=1 ;;
  *) echo "PASS: no unverified 'both hosts' claim" ;;
esac
rm -rf "$TMP5"

echo ""
echo "=== Case 6: --host linux with RUNNER_HOST set and at target stays healthy ==="
TMP6="$(mktemp -d)"
setup_env "$TMP6"
OUT6="$(CASE_RUNNER_HOST=fake-runner-host FAKE_SSH_COUNT=6 FAKE_SSH_MANAGED=6 run_watchdog "$TMP6" "" --host linux)"
RC6=$?
if [[ $RC6 -eq 0 ]]; then echo "PASS: exit 0"; else echo "FAIL: expected exit 0, got $RC6: $OUT6"; FAIL=1; fi
case "$OUT6" in
  *"configured=6, managed=6"*) echo "PASS: read remote state over the stubbed ssh" ;;
  *) echo "FAIL: did not read remote state: $OUT6"; FAIL=1 ;;
esac
case "$OUT6" in
  *"checked host(s) at configured count: linux"*) echo "PASS: summary names linux" ;;
  *) echo "FAIL: missing per-host summary: $OUT6"; FAIL=1 ;;
esac
rm -rf "$TMP6"

echo ""
if [[ $FAIL -eq 0 ]]; then
  echo "VERDICT: PASS — restart is fail-closed by default, opt-in works"
  exit 0
else
  echo "VERDICT: FAIL"
  exit 1
fi
