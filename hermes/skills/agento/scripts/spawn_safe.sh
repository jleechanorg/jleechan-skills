#!/bin/bash
# Safe per-project sequential AO spawn wrapper for cross-repo /af drive bursts.
# Verified 2026-07-08 driving 49 PRs across 7 repos.
#
# Usage: ./spawn_safe.sh <project> "<space-separated PR numbers>"
# Example: ./spawn_safe.sh jleechanclaw "754 753 752 751"

set +e  # don't fail-exit on per-PR errors; keep iterating

PROJECT="${1:?project required (e.g., jleechanclaw)}"
PRS="${2:?space-separated PR list required}"

# Required env for safe spawning (verified working 2026-07-08)
export HOME="$HOME"
export PATH="$HOME/.local/bin:$HOME/.bun/bin:/opt/homebrew/bin:/usr/bin:/bin"
unset GH_TOKEN GITHUB_TOKEN AO_BOT_GH_TOKEN
export AO_MAX_CONCURRENT_SESSIONS=80

echo "[$PROJECT] gh auth check:"
gh auth status 2>&1 | head -2

for pr in $PRS; do
  echo "[$PROJECT] starting PR #$pr at $(date +%H:%M:%S)"
  ~/bin/ao spawn -p "$PROJECT" --claim-pr "$pr" \
    "drive PR #$pr to /green + /er — push to existing branch only, do not open new PR, do not merge" \
    2>&1 | tail -3
  echo "[$PROJECT] PR #$pr done at $(date +%H:%M:%S)"
  sleep 5
done
echo "[$PROJECT] ALL DONE at $(date +%H:%M:%S)"
