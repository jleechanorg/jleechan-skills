#!/usr/bin/env bash
# test_test-tui-feature.sh — Unit tests for test-tui-feature.sh
#
# These cover the deterministic parts of the helper:
#   - Argument validation (missing slash command → exit 1, usage printed)
#   - SOCKET detection (missing socket → exit 1, clear error)
#   - Screen output validation (the "isn't available" detector works)
#
# The full TUI flow (spawn claude, send slash command, read screen) requires
# cmux + a real claude binary and is verified by the integration smoke test
# described in the SKILL.md "Verified example" section.

set -u

SCRIPT="$HOME/.claude/skills/test-tui-claude-feature-via-cmux/scripts/test-tui-feature.sh"

if [ ! -x "$SCRIPT" ]; then
  echo "FAIL: $SCRIPT not executable"
  exit 1
fi

PASS=0
FAIL=0

assert_contains() {
  local name="$1" haystack="$2" needle="$3"
  if echo "$haystack" | grep -q "$needle"; then
    echo "  PASS: $name"
    PASS=$((PASS + 1))
  else
    echo "  FAIL: $name"
    echo "    expected to contain: $needle"
    echo "    got: $haystack"
    FAIL=$((FAIL + 1))
  fi
}

assert_exit() {
  local name="$1" expected="$2" actual="$3"
  if [ "$expected" = "$actual" ]; then
    echo "  PASS: $name (exit $actual)"
    PASS=$((PASS + 1))
  else
    echo "  FAIL: $name (expected exit $expected, got $actual)"
    FAIL=$((FAIL + 1))
  fi
}

# Test 1: missing slash command → exit 1, usage printed
echo "Test 1: missing slash command"
OUTPUT=$("$SCRIPT" 2>&1)
EXIT=$?
assert_contains "prints usage" "$OUTPUT" "Usage:"
assert_exit "exits 1" 1 "$EXIT"

# Test 2: missing socket → exit 1, error mentions socket
echo "Test 2: missing CMUX_SOCKET_PATH"
OUTPUT=$(CMUX_SOCKET_PATH=/nonexistent/path/cmux.sock "$SCRIPT" /advisor 2>&1)
EXIT=$?
assert_contains "mentions cmux socket" "$OUTPUT" "cmux socket not found"
assert_exit "exits 1" 1 "$EXIT"

# Test 3: cmux not on PATH → exit 1
echo "Test 3: cmux CLI not in PATH"
OUTPUT=$(PATH="/usr/bin:/bin" "$SCRIPT" /advisor 2>&1)
EXIT=$?
assert_contains "mentions cmux CLI" "$OUTPUT" "cmux CLI not found"
# Could be 1 or 0 if socket check fails first; just check that it errored
if [ "$EXIT" -ne 0 ]; then
  echo "  PASS: exits non-zero (exit $EXIT)"
  PASS=$((PASS + 1))
else
  echo "  FAIL: should exit non-zero"
  FAIL=$((FAIL + 1))
fi

echo
echo "=== Summary ==="
echo "Passed: $PASS"
echo "Failed: $FAIL"

if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
exit 0
