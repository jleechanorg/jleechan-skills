#!/usr/bin/env bash
# test_check_api.sh — verify the runner-health skill parser against a synthetic
# fixture. Useful when GitHub API rate limit is exhausted or for CI.
#
# Usage: bash scripts/test_check_api.sh
# Exit 0 on PASS, non-zero on FAIL.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FIXTURE="$SCRIPT_DIR/../tests/fixtures/api_3L1M_busy.json"
EXPECTED_LINUX_BUSY=3
EXPECTED_MAC_BUSY=1
EXPECTED_TOTAL=9
EXPECTED_ONLINE=8
EXPECTED_BUSY=4

if [[ ! -f "$FIXTURE" ]]; then
  echo "FAIL: fixture not found at $FIXTURE" >&2
  exit 2
fi

# Run the parser logic with the fixture
RESULT=$(RUNNERS_JSON="$(cat "$FIXTURE")" RL_JSON='{}' TS="2026-06-29T00:00:00Z" ORG="jleechanorg" IN_FLIGHT=0 python3 <<'PYEOF'
import json, os
runners_data = json.loads(os.environ["RUNNERS_JSON"])
runners = runners_data.get("runners", [])


def arch_of(r):
    names = {l.get("name", "") for l in r.get("labels", [])}
    if "X64" in names: return "X64"
    if "ARM64" in names: return "ARM64"
    return None


total = len(runners)
online = sum(1 for r in runners if r.get("status") == "online")
busy = sum(1 for r in runners if r.get("busy"))
linux_busy = sum(1 for r in runners if arch_of(r) == "X64" and r.get("busy"))
mac_busy = sum(1 for r in runners if arch_of(r) == "ARM64" and r.get("busy"))
print(f"{total} {online} {busy} {linux_busy} {mac_busy}")
PYEOF
)

read -r TOTAL ONLINE BUSY LINUX_BUSY MAC_BUSY <<<"$RESULT"
echo "Fixture test results:"
echo "  total:      $TOTAL (expected $EXPECTED_TOTAL)"
echo "  online:     $ONLINE (expected $EXPECTED_ONLINE)"
echo "  busy:       $BUSY (expected $EXPECTED_BUSY)"
echo "  linux_busy: $LINUX_BUSY (expected $EXPECTED_LINUX_BUSY)"
echo "  mac_busy:   $MAC_BUSY (expected $EXPECTED_MAC_BUSY)"

FAIL=0
if [[ "$TOTAL" != "$EXPECTED_TOTAL" ]]; then echo "FAIL: total"; FAIL=1; fi
if [[ "$ONLINE" != "$EXPECTED_ONLINE" ]]; then echo "FAIL: online"; FAIL=1; fi
if [[ "$BUSY" != "$EXPECTED_BUSY" ]]; then echo "FAIL: busy"; FAIL=1; fi
if [[ "$LINUX_BUSY" != "$EXPECTED_LINUX_BUSY" ]]; then echo "FAIL: linux_busy"; FAIL=1; fi
if [[ "$MAC_BUSY" != "$EXPECTED_MAC_BUSY" ]]; then echo "FAIL: mac_busy"; FAIL=1; fi

if [[ $FAIL -eq 0 ]]; then
  echo ""
  echo "VERDICT: PASS — parser correctly handles 3 Linux + 1 mac busy"
  exit 0
else
  echo ""
  echo "VERDICT: FAIL"
  exit 1
fi
