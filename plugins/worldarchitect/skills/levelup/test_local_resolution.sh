#!/usr/bin/env bash
# Verify the portable command delegates to the selected product checkout.
set -uo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCAL_SH="$SKILL_DIR/local.sh"
FAIL=0
WORK="$(mktemp -d)"
WORK="$(cd "$WORK" && pwd -P)"
case "$WORK" in
  /tmp/tmp.*) ;;
  *) echo "Unexpected test scratch path: $WORK" >&2; exit 2 ;;
esac
trap 'python3 -c '"'"'import sys,shutil; p=sys.argv[1]; assert p.startswith("/tmp/tmp."); shutil.rmtree(p)'"'"' "$WORK"' EXIT

make_repo() {
  local skills_dir=".claude/skills" skill_name="levelup"
  mkdir -p "$1/testing_mcp/core" "$1/$skills_dir/$skill_name"
  : > "$1/testing_mcp/core/test_level_up_organic.py"
  cat > "$1/$skills_dir/$skill_name/levelup.sh" <<'EOF'
#!/usr/bin/env bash
printf 'CWD=%s\nMODEL=%s\n' "$PWD" "${TEST_DEFAULT_MODEL:-<unset>}"
printf 'ARG=<%s>\n' "$@"
EOF
  chmod +x "$1/$skills_dir/$skill_name/levelup.sh"
}

REPO_A="$WORK/repo-a"
REPO_B="$WORK/repo-b"
REPO_C="$WORK/repo-c"
ELSEWHERE="$WORK/elsewhere"
make_repo "$REPO_A"
make_repo "$REPO_B"
make_repo "$REPO_C"
mkdir -p "$ELSEWHERE"
git -C "$REPO_C" init -q

run_local() {
  local cwd="$1"
  shift
  (
    cd "$cwd"
    unset PROJECT_ROOT REPO_ROOT TEST_DEFAULT_MODEL
    for assignment in "$@"; do
      case "$assignment" in
        PROJECT_ROOT=*) PROJECT_ROOT="${assignment#PROJECT_ROOT=}"; export PROJECT_ROOT ;;
        REPO_ROOT=*) REPO_ROOT="${assignment#REPO_ROOT=}"; export REPO_ROOT ;;
        TEST_DEFAULT_MODEL=*) TEST_DEFAULT_MODEL="${assignment#TEST_DEFAULT_MODEL=}"; export TEST_DEFAULT_MODEL ;;
        *) echo "Unsupported test assignment: $assignment" >&2; return 2 ;;
      esac
    done
    bash "$LOCAL_SH" --daily-scenario crossing-299 "--work-name=local levelup"
  ) 2>&1
}

check() {
  local label="$1" expected="$2" output="$3"
  case "$output" in
    *"$expected"*) echo "PASS: $label" ;;
    *) echo "FAIL: $label"; FAIL=1 ;;
  esac
}

echo "=== PROJECT_ROOT wins over REPO_ROOT and cwd ==="
OUT="$(run_local "$ELSEWHERE" "PROJECT_ROOT=$REPO_A" "REPO_ROOT=$REPO_B" "TEST_DEFAULT_MODEL=deepseek/deepseek-v4.1-flash")"
check "selected project checkout" "CWD=$REPO_A" "$OUT"
check "DeepSeek environment is preserved" "MODEL=deepseek/deepseek-v4.1-flash" "$OUT"
check "daily scenario argument is passed" "ARG=<--daily-scenario>" "$OUT"
check "arguments with spaces remain intact" "ARG=<--work-name=local levelup>" "$OUT"

echo
echo "=== REPO_ROOT resolves when PROJECT_ROOT is unset ==="
OUT="$(run_local "$ELSEWHERE" "REPO_ROOT=$REPO_B")"
check "selected repo alias checkout" "CWD=$REPO_B" "$OUT"

echo
echo "=== git worktree is used as the final root fallback ==="
OUT="$(run_local "$REPO_C")"
check "selected current git worktree" "CWD=$REPO_C" "$OUT"

echo
echo "=== invalid selected root fails closed ==="
OUT="$(run_local "$ELSEWHERE" "PROJECT_ROOT=$WORK/missing-root" "REPO_ROOT=$REPO_B")"
RC=$?
[ "$RC" -eq 2 ] && check "invalid project root reports resolution error" "WorldArchitect checkout not found" "$OUT" || {
  echo "FAIL: invalid project root returned $RC"
  FAIL=1
}
case "$OUT" in *"CWD="*) echo "FAIL: fallback checkout ran"; FAIL=1 ;; esac

echo
echo "=== missing canonical entrypoint fails closed ==="
mkdir -p "$WORK/no-entrypoint/testing_mcp/core"
: > "$WORK/no-entrypoint/testing_mcp/core/test_level_up_organic.py"
OUT="$(run_local "$ELSEWHERE" "PROJECT_ROOT=$WORK/no-entrypoint")"
RC=$?
[ "$RC" -eq 2 ] && check "missing entrypoint reports resolution error" "WorldArchitect checkout not found" "$OUT" || {
  echo "FAIL: missing entrypoint returned $RC"
  FAIL=1
}
case "$OUT" in *"CWD="*) echo "FAIL: MCP test launched without canonical entrypoint"; FAIL=1 ;; esac

echo
if [ "$FAIL" -eq 0 ]; then
  echo "VERDICT: PASS - portable command delegates exact arguments to the selected WorldArchitect checkout"
  exit 0
fi
echo "VERDICT: FAIL"
exit 1
