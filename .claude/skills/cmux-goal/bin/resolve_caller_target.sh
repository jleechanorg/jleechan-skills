#!/usr/bin/env bash
# Print the invoking conversation's workspace and surface refs as TSV.
set -euo pipefail

CMUX_BIN="${CMUX_BIN:-cmux}"
"$CMUX_BIN" identify | python3 -c '
import json
import sys

payload = json.load(sys.stdin)
caller = payload.get("caller")
if not isinstance(caller, dict):
    raise SystemExit("cmux identify did not return a caller block")

workspace = caller.get("workspace_ref")
surface = caller.get("surface_ref")
if not all(isinstance(ref, str) and ref for ref in (workspace, surface)):
    raise SystemExit("cmux identify caller is missing workspace_ref or surface_ref")

print(f"{workspace}\t{surface}")
'
