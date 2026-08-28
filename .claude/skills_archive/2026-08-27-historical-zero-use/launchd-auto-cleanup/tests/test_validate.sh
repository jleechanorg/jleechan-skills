#!/usr/bin/env bash
# test_validate.sh — Unit tests for validate-cleanup-script.sh
# Run: bash ~/.claude/skills/launchd-auto-cleanup/tests/test_validate.sh
set -euo pipefail

VALIDATOR="$(cd "$(dirname "$0")/.." && pwd)/validate-cleanup-script.sh"
TMPDIR_TEST="$(mktemp -d)"
PASS=0
FAIL=0

cleanup() {
  rm -rf "$TMPDIR_TEST"
}
trap cleanup EXIT

pass() {
  echo "  PASS: $1"
  ((PASS++)) || true
}

fail() {
  echo "  FAIL: $1"
  ((FAIL++)) || true
}

assert_exit0() {
  local desc="$1"
  local script="$2"
  if bash "$VALIDATOR" "$script" >/dev/null 2>&1; then
    pass "$desc"
  else
    fail "$desc — expected exit 0 (PASS), got non-zero"
    bash "$VALIDATOR" "$script" 2>&1 | sed 's/^/    /' || true
  fi
}

assert_exit1() {
  local desc="$1"
  local script="$2"
  if bash "$VALIDATOR" "$script" >/dev/null 2>&1; then
    fail "$desc — expected exit 1 (FAIL), got exit 0"
  else
    pass "$desc"
  fi
}

echo "=== validate-cleanup-script.sh tests ==="
echo ""

# -------------------------------------------------------
# Test 1: Good script — should pass all checks
# -------------------------------------------------------
echo "Test 1: Valid cleanup script passes all checks"
GOOD_SCRIPT="$TMPDIR_TEST/good_cleanup.sh"
cat > "$GOOD_SCRIPT" << 'EOF'
#!/usr/bin/env bash
set -euo pipefail

DRY_RUN=false
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true

TARGET_DIR="$HOME/.cache/testapp"
RETENTION_DAYS=30

if [[ ! -d "$TARGET_DIR" ]]; then
  echo "Target does not exist, skipping"
  exit 0
fi

mapfile -t CANDIDATES < <(
  /usr/bin/find "$TARGET_DIR" -maxdepth 1 -mindepth 1 -mtime +${RETENTION_DAYS}
)

if [[ ${#CANDIDATES[@]} -eq 0 ]]; then
  echo "Nothing to clean"
  exit 0
fi

for item in "${CANDIDATES[@]}"; do
  echo "Would delete: $item"
done

if $DRY_RUN; then
  echo "DRY RUN — no deletions performed"
  exit 0
fi

for item in "${CANDIDATES[@]}"; do
  if [[ -e "$item" ]]; then
    /bin/rm -rf "$item"
    echo "Deleted: $item"
  fi
done

echo "Done"
EOF
chmod +x "$GOOD_SCRIPT"
assert_exit0 "Good script passes validation" "$GOOD_SCRIPT"

# -------------------------------------------------------
# Test 2: Missing --dry-run flag — should fail
# -------------------------------------------------------
echo ""
echo "Test 2: Script missing --dry-run fails"
NO_DRYRUN_SCRIPT="$TMPDIR_TEST/no_dryrun.sh"
cat > "$NO_DRYRUN_SCRIPT" << 'EOF'
#!/usr/bin/env bash
set -euo pipefail
TARGET="$HOME/.cache/testapp"
/bin/rm -rf "$TARGET"
echo "Done"
EOF
chmod +x "$NO_DRYRUN_SCRIPT"
assert_exit1 "Missing --dry-run fails" "$NO_DRYRUN_SCRIPT"

# -------------------------------------------------------
# Test 3: Hardcoded $HOME path — should fail
# -------------------------------------------------------
echo ""
echo "Test 3: Hardcoded /Users/ path fails"
HARDCODED_SCRIPT="$TMPDIR_TEST/hardcoded.sh"
cat > "$HARDCODED_SCRIPT" << 'EOF'
#!/usr/bin/env bash
set -euo pipefail

DRY_RUN=false
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true

TARGET_DIR="$HOME/.cache/testapp"
/usr/bin/find "$TARGET_DIR" -maxdepth 1

if $DRY_RUN; then
  exit 0
fi
/bin/rm -rf "$TARGET_DIR"
EOF
chmod +x "$HARDCODED_SCRIPT"
assert_exit1 "Hardcoded /Users/ path fails" "$HARDCODED_SCRIPT"

# -------------------------------------------------------
# Test 4: Missing set -euo pipefail — should fail
# -------------------------------------------------------
echo ""
echo "Test 4: Missing set -euo pipefail fails"
NO_SET_SCRIPT="$TMPDIR_TEST/no_set.sh"
cat > "$NO_SET_SCRIPT" << 'EOF'
#!/usr/bin/env bash
DRY_RUN=false
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true
TARGET="$HOME/.cache/testapp"
/usr/bin/find "$TARGET" -maxdepth 1
if $DRY_RUN; then exit 0; fi
/bin/rm -rf "$TARGET"
EOF
chmod +x "$NO_SET_SCRIPT"
assert_exit1 "Missing set -euo pipefail fails" "$NO_SET_SCRIPT"

# -------------------------------------------------------
# Test 5: Not executable — should fail
# -------------------------------------------------------
echo ""
echo "Test 5: Non-executable script fails"
NOT_EXEC_SCRIPT="$TMPDIR_TEST/not_exec.sh"
cat > "$NOT_EXEC_SCRIPT" << 'EOF'
#!/usr/bin/env bash
set -euo pipefail
DRY_RUN=false
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true
TARGET="$HOME/.cache/testapp"
/usr/bin/find "$TARGET" -maxdepth 1 -mtime +30
if $DRY_RUN; then exit 0; fi
/bin/rm -rf "$TARGET"
EOF
# Intentionally NOT chmod +x
assert_exit1 "Non-executable script fails" "$NOT_EXEC_SCRIPT"

# -------------------------------------------------------
# Test 6: Uses brew (non-system tool) — should fail
# -------------------------------------------------------
echo ""
echo "Test 6: Script using brew fails"
BREW_SCRIPT="$TMPDIR_TEST/uses_brew.sh"
cat > "$BREW_SCRIPT" << 'EOF'
#!/usr/bin/env bash
set -euo pipefail
DRY_RUN=false
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true
TARGET="$HOME/.cache/testapp"
brew cleanup --dry-run
if $DRY_RUN; then exit 0; fi
/bin/rm -rf "$TARGET"
EOF
chmod +x "$BREW_SCRIPT"
assert_exit1 "Script using brew fails" "$BREW_SCRIPT"

# -------------------------------------------------------
# Test 7: Missing script file — should fail with error
# -------------------------------------------------------
echo ""
echo "Test 7: Non-existent script path returns error"
if bash "$VALIDATOR" "/nonexistent/path/script.sh" >/dev/null 2>&1; then
  fail "Non-existent path — expected exit 1, got exit 0"
else
  pass "Non-existent path fails correctly"
fi

# -------------------------------------------------------
# Test 8: No argument — should fail with usage
# -------------------------------------------------------
echo ""
echo "Test 8: No argument prints usage"
if bash "$VALIDATOR" >/dev/null 2>&1; then
  fail "No argument — expected exit 1, got exit 0"
else
  pass "No argument fails with usage message"
fi

# -------------------------------------------------------
# Summary
# -------------------------------------------------------
echo ""
echo "==============================="
TOTAL=$((PASS + FAIL))
echo "Results: $PASS/$TOTAL passed"
if [[ $FAIL -gt 0 ]]; then
  echo "FAILURES: $FAIL"
  exit 1
else
  echo "All tests passed."
  exit 0
fi
