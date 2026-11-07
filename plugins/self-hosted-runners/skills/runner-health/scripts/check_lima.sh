#!/usr/bin/env bash
# check_lima.sh — Lima VM state (local colima + any remote instances)
# Outputs JSON to stdout, exit 0 on success, non-zero on hard error.
set -uo pipefail

TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

if ! command -v limactl >/dev/null 2>&1; then
  echo '{"timestamp":"'$TS'","error":"limactl not installed","instances":[]}'
  exit 127
fi

# Try JSON output first
RAW_JSON=$(limactl list --json 2>/dev/null || echo '[]')
if [[ "$RAW_JSON" == "[]" || -z "$RAW_JSON" ]]; then
  # Fallback to text output
  TEXT=$(limactl list 2>/dev/null || echo "")
  if [[ -z "$TEXT" ]]; then
    echo '{"timestamp":"'$TS'","error":"limactl list returned empty","instances":[]}'
    exit 2
  fi
  # Convert text to JSON (skip header, parse rows)
  RAW_JSON=$(echo "$TEXT" | tail -n +2 | python3 -c '
import json, sys, re
out = []
for line in sys.stdin:
    line = line.rstrip()
    if not line.strip():
        continue
    parts = re.split(r"\s+", line.strip(), maxsplit=5)
    if len(parts) < 6:
        continue
    name, status, ssh, cpus, memory, disk = parts[0], parts[1], parts[2], parts[3], parts[4], parts[5]
    out.append({"name": name, "status": status, "ssh": ssh, "cpus": cpus, "memory": memory, "disk": disk})
print(json.dumps(out))
' 2>/dev/null || echo '[]')
fi

# Validate JSON
if ! echo "$RAW_JSON" | python3 -c 'import json,sys; json.load(sys.stdin)' >/dev/null 2>&1; then
  echo '{"timestamp":"'$TS'","error":"limactl output not valid JSON","instances":[]}'
  exit 3
fi

# Trim to just the fields we care about (avoid dumping full config with images, mounts, etc.)
# limactl --json can return EITHER a list of instances OR a single instance dict — handle both
INSTANCES_JSON=$(echo "$RAW_JSON" | python3 -c '
import json, sys
data = json.load(sys.stdin)
# Normalize to list
if isinstance(data, dict):
    instances = [data]
elif isinstance(data, list):
    instances = data
else:
    instances = []
out = []
for inst in instances:
    if not isinstance(inst, dict):
        continue
    out.append({
        "name": inst.get("name", "?"),
        "status": inst.get("status", "?"),
        "cpus": inst.get("cpus", "?"),
        "memory": inst.get("memory", "?"),
        "disk": inst.get("disk", "?"),
        "sshAddress": inst.get("sshAddress", "?")
    })
print(json.dumps(out))
' 2>/dev/null || echo '[]')

# Wrap with timestamp
echo "{\"timestamp\":\"$TS\",\"error\":null,\"instances\":$INSTANCES_JSON}"
exit 0
