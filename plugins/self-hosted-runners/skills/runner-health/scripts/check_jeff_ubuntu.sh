#!/usr/bin/env bash
# check_jeff_ubuntu.sh — ssh into jeff-ubuntu Lima VM (graceful on unreachable)
# Outputs JSON to stdout. exit 0 = success (even if host unreachable; JSON shows reachable=false).
# exit 1 = ssh not available, exit 2 = script bug.
set -uo pipefail

TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
HOST="${JEFF_UBUNTU_HOST:-jeff-ubuntu}"
SSH_TIMEOUT="${JEFF_UBUNTU_TIMEOUT:-5}"
IP_FALLBACK="${JEFF_UBUNTU_IP:-192.168.254.128}"
DOCKER_SOCK_PATH="${JEFF_UBUNTU_DOCKER_SOCK:-unix:///home/$USER/.lima/colima/sock/docker.sock}"

if ! command -v ssh >/dev/null 2>&1; then
  cat <<EOF
{"timestamp":"$TS","host":"$HOST","reachable":false,"error":"ssh not installed","uptime":null,"load1":null,"disk_free_gb":null,"memory_avail_gb":null,"docker_containers":null,"note":"install ssh or use a different probe"}
EOF
  exit 127
fi

# Try ssh with short timeout. Capture both stdout and exit code.
# If ssh fails (timeout, refused, etc.), parse the failure mode.
PROBE_OUTPUT=$(ssh -o ConnectTimeout="$SSH_TIMEOUT" -o StrictHostKeyChecking=no "$HOST" '
  echo "===HOST_OK==="
  uptime
  echo "===LOAD==="
  cat /proc/loadavg
  echo "===DISK==="
  df -h /home /tmp 2>/dev/null
  echo "===MEM==="
  free -h
  echo "===DOCKER==="
  DOCKER_HOST='"$DOCKER_SOCK_PATH"' docker ps --format "{{.Names}}\t{{.Status}}" 2>/dev/null | wc -l
  echo "===DOCKER_RESTARTING==="
  DOCKER_HOST='"$DOCKER_SOCK_PATH"' docker ps -a --format "{{.Status}}" 2>/dev/null | grep -c "Restarting" || true
' 2>&1)
SSH_RC=$?

if [[ $SSH_RC -ne 0 ]]; then
  # ssh failed. Distinguish timeout vs DNS vs refused.
  SSH_ERROR="unknown"
  if echo "$PROBE_OUTPUT" | grep -q "Operation timed out"; then
    SSH_ERROR="timeout (likely different wifi subnet — see note)"
  elif echo "$PROBE_OUTPUT" | grep -q "Could not resolve hostname"; then
    SSH_ERROR="dns_unresolvable"
  elif echo "$PROBE_OUTPUT" | grep -q "Connection refused"; then
    SSH_ERROR="refused (port 22 closed or host down)"
  fi

  # Try IP fallback if hostname failed
  if [[ "$SSH_ERROR" == "timeout" || "$SSH_ERROR" == "dns_unresolvable" ]]; then
    IP_OUTPUT=$(ssh -o ConnectTimeout="$SSH_TIMEOUT" -o StrictHostKeyChecking=no "$IP_FALLBACK" 'echo OK; uptime' 2>&1)
    IP_RC=$?
    if [[ $IP_RC -eq 0 ]]; then
      SSH_ERROR="$SSH_ERROR (but IP $IP_FALLBACK reachable — host is up, this network can't route)"
    fi
  fi

  # Build JSON via Python so all control chars are properly escaped
  RAW_PREVIEW=$(echo "$PROBE_OUTPUT" | head -c 200)
  python3 -c "
import json, sys
d = {
    'timestamp': '$TS',
    'host': '$HOST',
    'reachable': False,
    'ssh_error': '''$SSH_ERROR''',
    'raw': '''$RAW_PREVIEW''',
    'uptime': None,
    'load1': None,
    'disk_free_gb': None,
    'memory_avail_gb': None,
    'docker_containers': None,
    'note': 'Host may be up but on a different wifi/subnet. Check busy=true on Linux runners via gh api as ground truth.'
}
print(json.dumps(d, indent=None))
"
  exit 0
fi

# Parse the successful output
UPTIME=$(echo "$PROBE_OUTPUT" | sed -n '/===HOST_OK===/,/===LOAD===/p' | sed '1d' | head -1 | sed 's/^ *//')
LOAD1=$(echo "$PROBE_OUTPUT" | sed -n '/===LOAD===/,/===DISK===/p' | sed '1d' | head -1 | awk '{print $1}')
DISK_FREE_GB=$(echo "$PROBE_OUTPUT" | sed -n '/===DISK===/,/===MEM===/p' | sed '1d' | grep -E '^/home' | awk '{print $4}' | sed 's/G//')
MEM_AVAIL_GB=$(echo "$PROBE_OUTPUT" | sed -n '/===MEM===/,/===DOCKER===/p' | sed '1d' | grep -E 'Mem:' | awk '{print $7}' | awk '{print int($1/1024/1024)}')
DOCKER_TOTAL=$(echo "$PROBE_OUTPUT" | sed -n '/===DOCKER===/,$ p' | sed '1d' | head -1)
DOCKER_RESTARTING=$(echo "$PROBE_OUTPUT" | sed -n '/===DOCKER_RESTARTING===/,$ p' | sed '1d' | head -1)

# Build JSON via Python for proper escaping
python3 -c "
import json
d = {
    'timestamp': '$TS',
    'host': '$HOST',
    'reachable': True,
    'ssh_error': None,
    'uptime': '''$UPTIME''',
    'load1': '''$LOAD1''',
    'disk_free_gb': '$DISK_FREE_GB' if '$DISK_FREE_GB' else None,
    'memory_avail_gb': '$MEM_AVAIL_GB' if '$MEM_AVAIL_GB' else None,
    'docker_containers': $DOCKER_TOTAL if '$DOCKER_TOTAL' else None,
    'docker_restarting': $DOCKER_RESTARTING if '$DOCKER_RESTARTING' else 0,
    'note': None
}
print(json.dumps(d))
"
exit 0
