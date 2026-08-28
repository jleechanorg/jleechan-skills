#!/usr/bin/env bash
# Copy this directory to profiles/<your-name>/ and implement hops.
set -euo pipefail
ID=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --id) ID="$2"; shift 2 ;;
    *) echo "Unknown: $1" >&2; exit 2 ;;
  esac
done
now_utc="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
worst="GREEN"
echo "# /callpath — ${now_utc} — verdict=${worst}"
echo "correlation: ${ID:-<unset>}"
echo ""
echo "## Hops"
echo "  entry                SKIP  [client] implement: how work enters"
echo "  service-a            SKIP  [api] implement: health/log/session probe"
echo "  service-b            SKIP  [worker] implement: queue depth / last job"
echo ""
echo "Copy profiles/_template → profiles/<name> and replace SKIP with real probes."
