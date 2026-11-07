#!/usr/bin/env bash
# test_read_json_or_default.sh — regression test for the read_json_or_default()
# helper in runner-health.sh.
#
# Bug class: `${content:-{}}` is misparsed by bash and appends a spurious
# literal trailing `}` onto ANY non-empty $content, not just when the default
# `{}` fires. E.g. content='{"x":1}' -> `{"x":1}}` (corrupted, extra brace).
# Verified deterministic on both bash 5.3.3 and macOS bash 3.2.57.
# See bead rev-kdf7z / PR #8229 for the original regression report.
#
# Usage: bash scripts/test_read_json_or_default.sh
# Exit 0 on PASS, non-zero on FAIL.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNNER_HEALTH="$SCRIPT_DIR/runner-health.sh"
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

FAIL=0
pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1"; FAIL=1; }

# Extract just the read_json_or_default() function body from runner-health.sh
# and source it in isolation, so this test exercises the exact production
# implementation rather than a re-typed copy that could drift.
FUNC_FILE="$TMPDIR/func.sh"
awk '/^read_json_or_default\(\) \{/,/^\}/' "$RUNNER_HEALTH" > "$FUNC_FILE"
if [[ ! -s "$FUNC_FILE" ]]; then
  echo "FAIL: could not extract read_json_or_default() from $RUNNER_HEALTH" >&2
  exit 2
fi
# shellcheck source=/dev/null
source "$FUNC_FILE"

# --- Test 1: non-empty valid JSON must round-trip byte-for-byte ---
# This is exactly the case the ${content:-{}} bug corrupts (appends a
# spurious trailing '}').
INPUT='{"x":1,"y":[1,2]}'
echo -n "$INPUT" > "$TMPDIR/valid.json"
OUTPUT="$(read_json_or_default "$TMPDIR/valid.json")"
if [[ "$OUTPUT" == "$INPUT" ]]; then
  pass "non-empty JSON round-trips byte-for-byte (no extra brace)"
else
  fail "non-empty JSON corrupted: input=[$INPUT] output=[$OUTPUT]"
fi

# --- Test 2: empty file defaults to {} ---
: > "$TMPDIR/empty.json"
OUTPUT="$(read_json_or_default "$TMPDIR/empty.json")"
if [[ "$OUTPUT" == "{}" ]]; then
  pass "empty file defaults to {}"
else
  fail "empty file did not default to {}: output=[$OUTPUT]"
fi

# --- Test 3: missing file defaults to {} ---
OUTPUT="$(read_json_or_default "$TMPDIR/does_not_exist.json")"
if [[ "$OUTPUT" == "{}" ]]; then
  pass "missing file defaults to {}"
else
  fail "missing file did not default to {}: output=[$OUTPUT]"
fi

if [[ $FAIL -eq 0 ]]; then
  echo ""
  echo "VERDICT: PASS — read_json_or_default() does not corrupt valid JSON"
  exit 0
else
  echo ""
  echo "VERDICT: FAIL"
  exit 1
fi
