#!/usr/bin/env bash
set -euo pipefail

payload="${1:-}"
[ -n "$payload" ] || exit 0

event_type=""
if command -v jq >/dev/null 2>&1; then
  event_type="$(printf '%s' "$payload" | jq -r '.type // empty' 2>/dev/null || true)"
else
  event_type="$(python3 - "$payload" <<'PY' 2>/dev/null || true
import json
import sys

try:
    print((json.loads(sys.argv[1]) or {}).get("type", ""))
except Exception:
    print("")
PY
)"
fi

[ "$event_type" = "agent-turn-complete" ] || exit 0

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  exit 0
fi

root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
[ -n "$root" ] || exit 0

if [ -x "$root/.claude/hooks/git-header.sh" ]; then
  exec "$root/.claude/hooks/git-header.sh" --status-only
fi
if [ -x "$root/.codex/hooks/git-header.sh" ]; then
  exec "$root/.codex/hooks/git-header.sh"
fi
if [ -x "$HOME/.claude/hooks/git-header.sh" ]; then
  exec "$HOME/.claude/hooks/git-header.sh" --status-only
fi

exit 0
