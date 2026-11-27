#!/usr/bin/env bash
# Focused regression checks for runner host probing and missing org config.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TESTDIR="$(mktemp -d)"
trap 'rm -rf "$TESTDIR"' EXIT
FAKEBIN="$TESTDIR/bin"
mkdir -p "$FAKEBIN"

cat > "$FAKEBIN/ssh" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$@" > "$FAKE_SSH_ARGS"
if [[ "${FAKE_SSH_MODE:-fail}" == fail ]]; then
  printf 'Could not resolve hostname $(touch %s) '\''quoted'\''\n' "$FAKE_PWNED" >&2
  exit 255
fi
cat <<'OUTPUT'
===HOST_OK===
up 1 day
===LOAD===
0.25 0.10 0.05
===DISK===
/dev/root 1T 100G 900G 10% /home
===MEM===
Mem: 16G 4G 1G 0G 0G 12G
===DOCKER===
3
===DOCKER_RESTARTING===
0
OUTPUT
EOF
chmod +x "$FAKEBIN/ssh"
export PATH="$FAKEBIN:$PATH"
export FAKE_SSH_ARGS="$TESTDIR/ssh-args" FAKE_PWNED="$TESTDIR/pwned"

FAIL=0
OUT="$(RUNNER_HOST='host$(touch /tmp/never)' bash "$SCRIPT_DIR/check_runner_host.sh" 2>&1)"
if python3 -c 'import json,sys; d=json.loads(sys.argv[1]); assert d["reachable"] is False; assert "$(touch" in d["host"]; assert "quoted" in d["raw"]' "$OUT"; then
  echo "PASS: SSH failure values are encoded as JSON data"
else
  echo "FAIL: SSH failure JSON"
  FAIL=1
fi
if grep -q 'StrictHostKeyChecking=no' "$FAKE_SSH_ARGS"; then
  echo "FAIL: SSH host-key checking was disabled"
  FAIL=1
else
  echo "PASS: SSH host-key checking uses the configured default"
fi
if [[ -e "$FAKE_PWNED" ]]; then
  echo "FAIL: SSH failure text executed as shell code"
  FAIL=1
else
  echo "PASS: SSH failure text remained data"
fi

OUT="$(FAKE_SSH_MODE=success RUNNER_HOST=example-host RUNNER_HOST_DOCKER_SOCK='unix:///tmp/socket path' bash "$SCRIPT_DIR/check_runner_host.sh")"
if python3 -c 'import json,sys; d=json.loads(sys.argv[1]); assert d["reachable"] is True; assert d["host"] == "example-host"; assert d["docker_containers"] == 3; assert d["docker_restarting"] == 0' "$OUT"; then
  echo "PASS: successful probe JSON parses and retains numeric fields"
else
  echo "FAIL: successful probe JSON"
  FAIL=1
fi
if grep -q 'StrictHostKeyChecking=no' "$FAKE_SSH_ARGS"; then
  echo "FAIL: SSH host-key checking disabled on successful probe"
  FAIL=1
else
  echo "PASS: successful probe keeps SSH host-key verification"
fi

for script in check_api.sh check_session_conflict.sh; do
  set +e
  OUT="$(env -i PATH="$PATH" bash "$SCRIPT_DIR/$script" 2>&1)"
  RC=$?
  set -e
  if [[ "$RC" -eq 2 ]] && python3 -c 'import json,sys; assert json.loads(sys.argv[1])["org"] is None' "$OUT"; then
    echo "PASS: $script reports missing org configuration"
  else
    echo "FAIL: $script missing-org diagnostic (exit $RC)"
    FAIL=1
  fi
done

exit "$FAIL"
