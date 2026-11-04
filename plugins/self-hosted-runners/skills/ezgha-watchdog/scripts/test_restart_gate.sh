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
# Usage: bash .claude/skills/ezgha-watchdog/scripts/test_restart_gate.sh
# Exit 0 on PASS, non-zero on FAIL.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WATCHDOG="$SCRIPT_DIR/ezgha-fleet-watchdog.sh"
FAIL=0

setup_env() {
  local test_home="$1"
  mkdir -p "$test_home/.config/ezgha" "$test_home/bin"
  printf '[runner]\ncount = 6\n' > "$test_home/.config/ezgha/config.toml"

  # Fake ezgha binary — always reports below-target (3 < 6).
  cat > "$test_home/bin/ezgha" <<'EOF'
#!/usr/bin/env bash
echo "managed containers: 3"
EOF
  chmod +x "$test_home/bin/ezgha"

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

run_to_threshold() {
  # HYSTERESIS_THRESHOLD is 2 (fires on the 3rd consecutive below-target
  # sample), so 3 invocations are needed to cross it.
  local test_home="$1"
  local allow_restart="${2:-}"
  for _ in 1 2 3; do
    HOME="$test_home" \
      PATH="$test_home/bin:$PATH" \
      EZGHA_BIN="$test_home/bin/ezgha" \
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
if [[ $FAIL -eq 0 ]]; then
  echo "VERDICT: PASS — restart is fail-closed by default, opt-in works"
  exit 0
else
  echo "VERDICT: FAIL"
  exit 1
fi
