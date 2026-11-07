#!/usr/bin/env bash
# test_local_resolution.sh — verify local.sh resolves the product repository in
# the documented order: PROJECT_ROOT wins, then its accepted REPO_ROOT alias,
# then the current git worktree. An unusable selected root fails closed instead
# of silently running somewhere else.
# See docs/portability-env-vars.md ("PROJECT_ROOT / REPO_ROOT").
#
# Usage: bash <skill-dir>/test_local_resolution.sh
# Exit 0 on PASS, non-zero on FAIL.
set -uo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCAL_SH="$SKILL_DIR/local.sh"
FAIL=0

WORK="$(mktemp -d)"
WORK="$(cd "$WORK" && pwd -P)"
trap 'rm -rf "$WORK"' EXIT

make_repo() {
  # make_repo <dir> — minimal product checkout the runner can exec in.
  mkdir -p "$1/testing_mcp/core"
  cat > "$1/testing_mcp/core/test_level_up_organic.py" <<'EOF'
import os, sys
print("CWD=%s" % os.getcwd())
print("ARGS=%s" % " ".join(sys.argv[1:]))
EOF
}

REPO_A="$WORK/repo-a"
REPO_B="$WORK/repo-b"
REPO_C="$WORK/repo-c"
ELSEWHERE="$WORK/elsewhere"
make_repo "$REPO_A"
make_repo "$REPO_B"
make_repo "$REPO_C"
mkdir -p "$ELSEWHERE"
( cd "$REPO_C" && git init -q . ) >/dev/null 2>&1

run_local() {
  # run_local <cwd> [VAR=value ...] — runs local.sh with PROJECT_ROOT and the
  # REPO_ROOT alias scrubbed first, so each case controls resolution itself.
  local cwd="$1"
  shift
  ( cd "$cwd" && env -u PROJECT_ROOT -u REPO_ROOT "$@" bash "$LOCAL_SH" ) 2>&1
}

check_rc() {
  local rc="$1" expected="$2" label="$3"
  if [[ "$rc" -eq "$expected" ]]; then
    echo "PASS: $label (exit $rc)"
  else
    echo "FAIL: $label — expected exit $expected, got $rc"
    FAIL=1
  fi
}

check_contains() {
  local out="$1" needle="$2" label="$3"
  case "$out" in
    *"$needle"*) echo "PASS: $label" ;;
    *) echo "FAIL: $label — missing '$needle' in: $out"; FAIL=1 ;;
  esac
}

echo "=== Case 1: PROJECT_ROOT wins over the REPO_ROOT alias and the cwd ==="
OUT="$(run_local "$ELSEWHERE" "PROJECT_ROOT=$REPO_A" "REPO_ROOT=$REPO_B")"
RC=$?
check_rc "$RC" 0 "runner exits 0"
check_contains "$OUT" "CWD=$REPO_A" "ran in PROJECT_ROOT"

echo ""
echo "=== Case 2: REPO_ROOT is the fallback alias when PROJECT_ROOT is unset ==="
OUT="$(run_local "$ELSEWHERE" "REPO_ROOT=$REPO_B")"
RC=$?
check_rc "$RC" 0 "runner exits 0"
check_contains "$OUT" "CWD=$REPO_B" "ran in REPO_ROOT"

echo ""
echo "=== Case 3: verified cwd is the last resort ==="
OUT="$(run_local "$REPO_C")"
RC=$?
check_rc "$RC" 0 "runner exits 0"
check_contains "$OUT" "CWD=$REPO_C" "ran in the cwd worktree"

echo ""
echo "=== Case 4: an unusable PROJECT_ROOT fails closed, it does not fall through ==="
OUT="$(run_local "$ELSEWHERE" "PROJECT_ROOT=$WORK/does-not-exist" "REPO_ROOT=$REPO_B")"
RC=$?
check_rc "$RC" 2 "exits 2 on an unusable selected root"
check_contains "$OUT" "PROJECT_ROOT not configured" "error names PROJECT_ROOT"
case "$OUT" in
  *"CWD="*) echo "FAIL: runner executed in a fallback repo"; FAIL=1 ;;
  *) echo "PASS: runner refused to execute" ;;
esac

echo ""
echo "=== Case 5: no root and no worktree fails closed with instruction ==="
OUT="$(run_local "$ELSEWHERE")"
RC=$?
check_rc "$RC" 2 "exits 2 with nothing to resolve"
check_contains "$OUT" "PROJECT_ROOT not configured" "error names PROJECT_ROOT"

echo ""
if [[ $FAIL -eq 0 ]]; then
  echo "VERDICT: PASS — PROJECT_ROOT > REPO_ROOT > verified cwd, invalid root fails closed"
  exit 0
else
  echo "VERDICT: FAIL"
  exit 1
fi
