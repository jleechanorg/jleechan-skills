#!/usr/bin/env bash
set -euo pipefail

base_dir="$HOME/.codex/plugins/cache/openai-bundled/computer-use"
client=""

if [ -d "$base_dir" ]; then
  while IFS= read -r candidate; do
    if [ -x "$candidate" ]; then
      client="$candidate"
    fi
  done < <(
    find "$base_dir" \
      -path '*/Codex Computer Use.app/Contents/SharedSupport/SkyComputerUseClient.app/Contents/MacOS/SkyComputerUseClient' \
      -type f 2>/dev/null | sort -V
  )
fi

if [ -n "$client" ]; then
  exec "$client" "$@"
fi

# Notification delivery should never break a turn. If the bundled client moves
# again before config refreshes, fail closed as a no-op.
exit 0
