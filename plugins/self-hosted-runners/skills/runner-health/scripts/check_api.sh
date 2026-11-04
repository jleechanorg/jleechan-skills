#!/usr/bin/env bash
# check_api.sh — GitHub API runner state check
# Outputs JSON to stdout, exit 0 on success, non-zero on hard error.
# Uses a SINGLE python invocation to avoid the multi-subprocess race
# condition that previously caused Linux/mac busy counts to be miscategorized.
set -uo pipefail

TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
ORG="${GH_ORG:-jleechanorg}"

if ! command -v gh >/dev/null 2>&1; then
  echo '{"timestamp":"'$TS'","host":"mac","org":"'$ORG'","error":"gh CLI not installed","runners":null,"rate_limit":null}' >&2
  exit 127
fi

# Single API call for runners
RUNNERS_JSON="$(gh api "orgs/${ORG}/actions/runners?per_page=100" 2>/dev/null || echo '[]')"
if [[ "$RUNNERS_JSON" == "[]" || -z "$RUNNERS_JSON" ]]; then
  echo '{"timestamp":"'$TS'","host":"mac","org":"'$ORG'","error":"gh api runners returned empty (auth issue or org mismatch)","runners":null,"rate_limit":null}' >&2
  exit 2
fi

# In-flight jobs (per-repo aggregate)
IN_FLIGHT=0
for repo in $GITHUB_REPOSITORY jleechanorg/jleechanclaw jleechanorg/agent-orchestrator; do
  N=$(gh api "repos/${repo}/actions/runs?status=in_progress&per_page=10" --jq '.total_count' 2>/dev/null || echo "0")
  IN_FLIGHT=$((IN_FLIGHT + N))
done

# Rate limit
RL_JSON="$(gh api rate_limit 2>/dev/null || echo '{}')"

# SINGLE python invocation via stdin pipe (NOT heredoc — heredoc consumes
# the script, not stdin). Use env vars to pass the JSONs.
RUNNERS_JSON="$RUNNERS_JSON" RL_JSON="$RL_JSON" TS="$TS" ORG="$ORG" IN_FLIGHT="$IN_FLIGHT" python3 <<'PYEOF'
import json
import os

runners_data = json.loads(os.environ["RUNNERS_JSON"])
rl_data = json.loads(os.environ.get("RL_JSON", "{}"))
ts = os.environ["TS"]
org = os.environ["ORG"]
in_flight = int(os.environ.get("IN_FLIGHT", "0"))

runners = runners_data.get("runners", [])


def arch_of(r):
    """Return 'X64', 'ARM64', or None based on label membership (exact match)."""
    names = {l.get("name", "") for l in r.get("labels", [])}
    if "X64" in names:
        return "X64"
    if "ARM64" in names:
        return "ARM64"
    return None


total = len(runners)
online = sum(1 for r in runners if r.get("status") == "online")
offline = sum(1 for r in runners if r.get("status") == "offline")
busy = sum(1 for r in runners if r.get("busy"))
linux_x64_total = sum(1 for r in runners if arch_of(r) == "X64")
linux_x64_online = sum(1 for r in runners if arch_of(r) == "X64" and r.get("status") == "online")
linux_x64_busy = sum(1 for r in runners if arch_of(r) == "X64" and r.get("busy"))
mac_arm64_total = sum(1 for r in runners if arch_of(r) == "ARM64")
mac_arm64_online = sum(1 for r in runners if arch_of(r) == "ARM64" and r.get("status") == "online")
mac_arm64_busy = sum(1 for r in runners if arch_of(r) == "ARM64" and r.get("busy"))

core = rl_data.get("resources", {}).get("core", {})
graph = rl_data.get("resources", {}).get("graphql", {})

out = {
    "timestamp": ts,
    "host": "mac",
    "org": org,
    "error": None,
    "runners": {
        "total": total,
        "online": online,
        "offline": offline,
        "busy": busy,
        "by_arch": {
            "linux_x64": {
                "total": linux_x64_total,
                "online": linux_x64_online,
                "busy": linux_x64_busy,
            },
            "mac_arm64": {
                "total": mac_arm64_total,
                "online": mac_arm64_online,
                "busy": mac_arm64_busy,
            },
        },
        "in_flight_jobs": in_flight,
    },
    "rate_limit": {
        "core_remaining": core.get("remaining", "?"),
        "core_limit": core.get("limit", "?"),
        "graphql_remaining": graph.get("remaining", "?"),
        "graphql_limit": graph.get("limit", "?"),
    },
}
print(json.dumps(out))
PYEOF
exit 0
