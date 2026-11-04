#!/usr/bin/env bash
# test_check_session_conflict.sh — verify check_session_conflict.sh classifies
# GitHub-offline runners correctly against fake gh/docker/ssh binaries.
#
# Ported test strategy from closed PR #8033's test_ubuntu_runner_health.sh
# (fake CLI binaries on PATH, no real gh/docker/ssh, no sudo). See bead rev-ws17d.
#
# Usage: bash scripts/test_check_session_conflict.sh
# Exit 0 on PASS, non-zero on FAIL.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$SCRIPT_DIR/check_session_conflict.sh"
PARSER="$SCRIPT_DIR/parse_fields.py"

TESTDIR=$(mktemp -d)
trap 'rm -rf "$TESTDIR"' EXIT
FAKEBIN="$TESTDIR/bin"
mkdir -p "$FAKEBIN"

cat > "$FAKEBIN/gh" <<'EOF'
#!/usr/bin/env bash
case "${FAKE_GH_MODE:-online}" in
  fail)
    echo "api unavailable" >&2
    exit 1
    ;;
  fail_empty)
    exit 1
    ;;
  mac_offline)
    printf 'ez-mac-runner-c-3\n'
    ;;
  mac_offline_with_stderr)
    echo "notice: paging through runners" >&2
    printf 'ez-mac-runner-c-3\n'
    ;;
  linux_offline)
    printf 'ez-runner-c-5\n'
    ;;
  mixed_offline)
    printf 'ez-mac-runner-c-3\nez-runner-c-5\n'
    ;;
  canary_offline)
    printf 'ez-canary-runner-b-1\n'
    ;;
  malicious_offline)
    printf 'ez-runner-c-5;touch %s\n' "$PWNED_FILE"
    ;;
  leading_dash_offline)
    printf -- '-ez-runner-c-5\n'
    ;;
  *)
    ;;
esac
EOF
chmod +x "$FAKEBIN/gh"

cat > "$FAKEBIN/docker" <<'EOF'
#!/usr/bin/env bash
case "$1:${FAKE_DOCKER_MODE:-running}" in
  inspect:running)
    echo running
    ;;
  inspect:exited)
    echo exited
    ;;
  inspect:missing|inspect:unavailable)
    exit 1
    ;;
  info:unavailable)
    exit 1
    ;;
  info:*)
    exit 0
    ;;
  *)
    exit 1
    ;;
esac
EOF
chmod +x "$FAKEBIN/docker"

cat > "$FAKEBIN/ssh" <<'EOF'
#!/usr/bin/env bash
printf 'called\n' >> "$FAKE_SSH_LOG"
if [[ "${FAKE_SSH_RC:-0}" != "0" ]]; then
  exit "${FAKE_SSH_RC}"
fi
case "${FAKE_SSH_MODE:-running}" in
  running) echo running ;;
  missing) echo missing ;;
  exited)  echo exited ;;
  *)       echo "$FAKE_SSH_MODE" ;;
esac
EOF
chmod +x "$FAKEBIN/ssh"

PATH="$FAKEBIN:$PATH"
export PATH
SSH_TIMEOUT=1
JEFF_UBUNTU_TIMEOUT=1
JEFF_UBUNTU_HOST=jeff-ubuntu
export SSH_TIMEOUT JEFF_UBUNTU_TIMEOUT JEFF_UBUNTU_HOST
FAKE_SSH_LOG="$TESTDIR/ssh.log"
PWNED_FILE="$TESTDIR/pwned"
export FAKE_SSH_LOG PWNED_FILE

FAIL=0

check_field() {
  # check_field <json> <python-expr-on-d> <expected> <label>
  local json="$1" expr="$2" expected="$3" label="$4"
  local actual
  actual="$(python3 -c "import json,sys; d=json.loads(sys.argv[1]); print($expr)" "$json")"
  if [[ "$actual" == "$expected" ]]; then
    echo "PASS: $label ($actual)"
  else
    echo "FAIL: $label — expected '$expected', got '$actual'"
    FAIL=1
  fi
}

check_equals() {
  local actual="$1" expected="$2" label="$3"
  if [[ "$actual" == "$expected" ]]; then
    echo "PASS: $label ($actual)"
  else
    echo "FAIL: $label — expected '$expected', got '$actual'"
    FAIL=1
  fi
}

echo "=== Scenario 1: no offline runners ==="
OUT="$(FAKE_GH_MODE=online bash "$SCRIPT")"
RC=$?
if [[ $RC -eq 0 ]]; then echo "PASS: exit 0"; else echo "FAIL: expected exit 0, got $RC"; FAIL=1; fi
check_field "$OUT" "d['offline_count']" "0" "offline_count is 0"
check_field "$OUT" "d['session_conflicts']" "[]" "no session conflicts"

echo ""
echo "=== Scenario 2: mac runner offline, container Up (SESSION CONFLICT) ==="
OUT="$(FAKE_GH_MODE=mac_offline FAKE_DOCKER_MODE=running bash "$SCRIPT")"
RC=$?
if [[ $RC -eq 0 ]]; then echo "PASS: exit 0"; else echo "FAIL: expected exit 0, got $RC"; FAIL=1; fi
check_field "$OUT" "d['session_conflicts']" "['ez-mac-runner-c-3']" "mac runner flagged as session_conflict"
check_field "$OUT" "d['runner_offline']" "[]" "not miscategorized as runner_offline"

echo ""
echo "=== Scenario 3: mac runner offline, container missing (ordinary runner_offline) ==="
OUT="$(FAKE_GH_MODE=mac_offline FAKE_DOCKER_MODE=missing bash "$SCRIPT")"
RC=$?
if [[ $RC -eq 0 ]]; then echo "PASS: exit 0"; else echo "FAIL: expected exit 0, got $RC"; FAIL=1; fi
check_field "$OUT" "d['runner_offline']" "['ez-mac-runner-c-3']" "mac runner flagged as runner_offline (not a conflict)"
check_field "$OUT" "d['session_conflicts']" "[]" "no false-positive session conflict"

echo ""
echo "=== Scenario 3b: mac runner offline, local Docker daemon unreachable ==="
OUT="$(FAKE_GH_MODE=mac_offline FAKE_DOCKER_MODE=unavailable bash "$SCRIPT")"
RC=$?
if [[ $RC -eq 0 ]]; then echo "PASS: exit 0"; else echo "FAIL: expected exit 0, got $RC"; FAIL=1; fi
check_field "$OUT" "d['docker_unavailable']" "['ez-mac-runner-c-3']" "mac runner flagged docker_unavailable when daemon down"
check_field "$OUT" "d['runner_offline']" "[]" "not miscategorized as runner_offline"

echo ""
echo "=== Scenario 3c: gh success stderr is not parsed as runner name ==="
OUT="$(FAKE_GH_MODE=mac_offline_with_stderr FAKE_DOCKER_MODE=running bash "$SCRIPT")"
RC=$?
if [[ $RC -eq 0 ]]; then echo "PASS: exit 0"; else echo "FAIL: expected exit 0, got $RC"; FAIL=1; fi
check_field "$OUT" "d['session_conflicts']" "['ez-mac-runner-c-3']" "stdout runner still classified"
check_field "$OUT" "d['offline_count']" "1" "stderr line excluded from offline_count"

echo ""
echo "=== Scenario 4: Linux runner offline, container Up via SSH (SESSION CONFLICT) ==="
OUT="$(FAKE_GH_MODE=linux_offline FAKE_SSH_MODE=running bash "$SCRIPT")"
RC=$?
if [[ $RC -eq 0 ]]; then echo "PASS: exit 0"; else echo "FAIL: expected exit 0, got $RC"; FAIL=1; fi
check_field "$OUT" "d['session_conflicts']" "['ez-runner-c-5']" "Linux runner flagged as session_conflict via SSH"

echo ""
echo "=== Scenario 5: Linux runner offline, jeff-ubuntu unreachable over SSH ==="
OUT="$(FAKE_GH_MODE=linux_offline FAKE_SSH_RC=255 bash "$SCRIPT")"
RC=$?
if [[ $RC -eq 0 ]]; then echo "PASS: exit 0"; else echo "FAIL: expected exit 0, got $RC"; FAIL=1; fi
check_field "$OUT" "d['ssh_unreachable']" "['ez-runner-c-5']" "Linux runner flagged ssh_unreachable when SSH fails"

echo ""
echo "=== Scenario 6: mixed fleet, both offline and both session conflicts ==="
OUT="$(FAKE_GH_MODE=mixed_offline FAKE_DOCKER_MODE=running FAKE_SSH_MODE=running bash "$SCRIPT")"
RC=$?
if [[ $RC -eq 0 ]]; then echo "PASS: exit 0"; else echo "FAIL: expected exit 0, got $RC"; FAIL=1; fi
check_field "$OUT" "sorted(d['session_conflicts'])" "['ez-mac-runner-c-3', 'ez-runner-c-5']" "both fleets flagged as session_conflict"
check_field "$OUT" "d['offline_count']" "2" "offline_count reflects both runners"

echo ""
echo "=== Scenario 7: canary-runner variant routed to Linux/SSH fleet (SESSION CONFLICT) ==="
OUT="$(FAKE_GH_MODE=canary_offline FAKE_SSH_MODE=running bash "$SCRIPT")"
RC=$?
if [[ $RC -eq 0 ]]; then echo "PASS: exit 0"; else echo "FAIL: expected exit 0, got $RC"; FAIL=1; fi
check_field "$OUT" "d['session_conflicts']" "['ez-canary-runner-b-1']" "ez-canary-runner-* routed via SSH (not local docker) and flagged"

echo ""
echo "=== Scenario 8: gh api unavailable ==="
OUT="$(FAKE_GH_MODE=fail bash "$SCRIPT")"
RC=$?
if [[ $RC -ne 0 ]]; then echo "PASS: exit non-zero on gh failure"; else echo "FAIL: expected non-zero exit"; FAIL=1; fi
check_field "$OUT" "d['error'] is not None" "True" "error field set on gh api failure"

echo ""
echo "=== Scenario 9: detector error blocks healthy GREEN verdict ==="
API_JSON='{"runners":{"online":22,"busy":22,"by_arch":{"linux_x64":{"online":16,"busy":16},"mac_arm64":{"online":6,"busy":6}}}}'
DOCKER_JSON='{"error":null,"containers":{"restarting":0}}'
JEFF_JSON='{"reachable":true}'
SESSION_CONFLICT_JSON='{"error":"api unavailable","session_conflicts":[]}'
OUT="$(python3 "$PARSER" verdict "$API_JSON" "$DOCKER_JSON" "$JEFF_JSON" "$SESSION_CONFLICT_JSON")"
check_equals "${OUT%%|*}" "AMBER" "session-conflict detector error is not GREEN"
case "$OUT" in
  *"Session-conflict check unavailable"*) echo "PASS: verdict names detector error" ;;
  *) echo "FAIL: verdict should name detector error, got '$OUT'"; FAIL=1 ;;
esac

echo ""
echo "=== Scenario 10: malicious runner name fails closed before SSH ==="
: > "$FAKE_SSH_LOG"
OUT="$(FAKE_GH_MODE=malicious_offline bash "$SCRIPT")"
RC=$?
if [[ $RC -eq 0 ]]; then echo "PASS: exit 0 with classified rejection"; else echo "FAIL: expected exit 0, got $RC"; FAIL=1; fi
check_field "$OUT" "d['invalid_names']" "['ez-runner-c-5;touch $PWNED_FILE']" "metacharacter-bearing name rejected"
if [[ ! -s "$FAKE_SSH_LOG" ]]; then echo "PASS: SSH was not invoked"; else echo "FAIL: rejected name reached SSH"; FAIL=1; fi
if [[ ! -e "$PWNED_FILE" ]]; then echo "PASS: injection canary absent"; else echo "FAIL: injection canary created"; FAIL=1; fi
LINE="$(python3 "$PARSER" session_conflict "$OUT")"
case "$LINE" in
  *"invalid runner name"*) echo "PASS: console line names rejected metadata" ;;
  *) echo "FAIL: console line hides rejected metadata: '$LINE'"; FAIL=1 ;;
esac
OUT="$(python3 "$PARSER" verdict "$API_JSON" "$DOCKER_JSON" "$JEFF_JSON" "$OUT")"
check_equals "${OUT%%|*}" "AMBER" "invalid runner metadata cannot produce GREEN"
case "$OUT" in
  *"invalid runner name"*) echo "PASS: verdict names invalid metadata" ;;
  *) echo "FAIL: verdict should name invalid metadata, got '$OUT'"; FAIL=1 ;;
esac

echo ""
echo "=== Scenario 11: empty gh stderr and unverified runners fail closed ==="
OUT="$(FAKE_GH_MODE=fail_empty bash "$SCRIPT")"
RC=$?
if [[ $RC -ne 0 ]]; then echo "PASS: empty-stderr gh failure exits non-zero"; else echo "FAIL: expected non-zero exit"; FAIL=1; fi
check_field "$OUT" "bool(d['error'])" "True" "empty gh stderr receives deterministic error"

OUT="$(FAKE_GH_MODE=linux_offline FAKE_SSH_RC=255 bash "$SCRIPT")"
LINE="$(python3 "$PARSER" session_conflict "$OUT")"
case "$LINE" in
  *"unverified"*) echo "PASS: console line identifies unverified runner" ;;
  *) echo "FAIL: console line falsely classifies unverified runner: '$LINE'"; FAIL=1 ;;
esac
OUT="$(python3 "$PARSER" verdict "$API_JSON" "$DOCKER_JSON" "$JEFF_JSON" "$OUT")"
check_equals "${OUT%%|*}" "AMBER" "unverified runner cannot produce GREEN"
case "$OUT" in
  *"could not inspect"*) echo "PASS: verdict names inspection gap" ;;
  *) echo "FAIL: verdict should name inspection gap, got '$OUT'"; FAIL=1 ;;
esac

echo ""
echo "=== Scenario 12: leading-dash runner name fails closed before SSH ==="
: > "$FAKE_SSH_LOG"
OUT="$(FAKE_GH_MODE=leading_dash_offline bash "$SCRIPT")"
RC=$?
if [[ $RC -eq 0 ]]; then echo "PASS: exit 0 with classified rejection"; else echo "FAIL: expected exit 0, got $RC"; FAIL=1; fi
check_field "$OUT" "d['invalid_names']" "['-ez-runner-c-5']" "leading-dash name rejected (argument-injection shape)"
if [[ ! -s "$FAKE_SSH_LOG" ]]; then echo "PASS: SSH was not invoked"; else echo "FAIL: rejected name reached SSH"; FAIL=1; fi

echo ""
if [[ $FAIL -eq 0 ]]; then
  echo "VERDICT: PASS — all session-conflict scenarios classified correctly"
  exit 0
else
  echo "VERDICT: FAIL"
  exit 1
fi
