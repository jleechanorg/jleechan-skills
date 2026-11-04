#!/usr/bin/env bash
# check_docker.sh — local Docker container state for mac-side runners + AO auxiliaries
# Outputs JSON to stdout, exit 0 on success, non-zero on hard error.
set -uo pipefail

TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

emit() {
  local err="$1" total="$2" up="$3" rest="$4" mac_up="$5" mac_total="$6" ao_rest="$7" ao_total="$8"
  cat <<EOF
{"timestamp":"$TS","error":$( [[ "$err" == "null" ]] && echo null || echo "\"$err\"" ),"daemon":$( [[ "$err" == "null" ]] && echo "\"up\"" || echo "\"down\"" ),"containers":{"total":$total,"up":$up,"restarting":$rest},"org_runners":{"up":$mac_up,"total":$mac_total},"ao_auxiliaries":{"restarting":$ao_rest,"total":$ao_total}}
EOF
}

if ! command -v docker >/dev/null 2>&1; then
  emit "docker CLI not installed" 0 0 0 0 0 0 0
  exit 127
fi

# Check docker daemon
if ! docker info >/dev/null 2>&1; then
  emit "docker daemon unreachable (is colima/docker desktop running?)" 0 0 0 0 0 0 0
  exit 2
fi

# Get container counts
TOTAL=$(docker ps -a --format '{{.Names}}' 2>/dev/null | wc -l | tr -d ' ')
UP=$(docker ps --format '{{.Names}}' 2>/dev/null | wc -l | tr -d ' ')
RESTARTING=$(docker ps -a --format '{{.Status}}' 2>/dev/null | grep -c "Restarting" || true)
MAC_UP=$(docker ps --format '{{.Names}}' 2>/dev/null | grep -cE "^org-runner-mac-" || true)
MAC_TOTAL=$(docker ps -a --format '{{.Names}}' 2>/dev/null | grep -cE "^org-runner-mac-" || true)
AO_RESTARTING=$(docker ps -a --format '{{.Names}}\t{{.Status}}' 2>/dev/null | grep -E "ao-runner-jleechanorg--" | grep -c "Restarting" || true)
AO_TOTAL=$(docker ps -a --format '{{.Names}}' 2>/dev/null | grep -cE "^ao-runner-jleechanorg--" || true)

emit "null" "$TOTAL" "$UP" "$RESTARTING" "$MAC_UP" "$MAC_TOTAL" "$AO_RESTARTING" "$AO_TOTAL"
exit 0
