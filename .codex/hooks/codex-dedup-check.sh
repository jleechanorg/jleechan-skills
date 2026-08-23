#!/usr/bin/env bash
# codex-dedup-check.sh — Helper script to check for in-flight Codex threads
# Usage: ~/.codex/hooks/codex-dedup-check.sh "<keyword_or_query>" [window_seconds]
# Exit code: 0 if duplicate thread IS in-flight (steer existing), 1 if clear (safe to spawn).

KEYWORD="$1"
WINDOW="${2:-1800}"
DB_PATH="$HOME/.codex/state_5.sqlite"

if [ -z "$KEYWORD" ]; then
  echo "Usage: codex-dedup-check.sh \"<keyword>\" [window_seconds]"
  exit 1
fi

if [ ! -f "$DB_PATH" ]; then
  # No DB found, clear to spawn
  exit 1
fi

COUNT=$(sqlite3 "$DB_PATH" \
  "SELECT COUNT(*) FROM threads
   WHERE first_user_message LIKE '%${KEYWORD}%'
     AND tokens_used = 0
     AND created_at_ms > (unixepoch('now') - ${WINDOW}) * 1000;" 2>/dev/null || echo "0")

if [ "$COUNT" -gt 0 ]; then
  echo "⚠️ DEDUP ALERT: $COUNT thread(s) already in-flight for keyword '$KEYWORD' in the last ${WINDOW}s."
  echo "Action: Steer the existing in-flight thread instead of spawning a new duplicate."
  exit 0
else
  echo "✅ DEDUP CLEAR: No active in-flight threads found for keyword '$KEYWORD' in the last ${WINDOW}s."
  exit 1
fi
