#!/usr/bin/env bash
# Offline checks for bin/self_goal.py: host detection and transcript goal-state parsing.
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
tmp="$(mktemp -d)"
fail() { echo "FAIL: $*" >&2; exit 1; }

h() { env -i PATH="$PATH" "$@" python3 "$here/bin/self_goal.py" host; }
[ "$(h CMUX_SURFACE_ID=x TMUX=a TMUX_PANE=%1)" = cmux ] || fail cmux
[ "$(h TMUX=a TMUX_PANE=%1)" = tmux ] || fail tmux
[ "$(h TERM_PROGRAM=WarpTerminal)" = warp ] || fail warp
[ "$(h)" = none ] || fail none

state() {
  printf '%s\n' "$@" > "$tmp/s.jsonl"
  python3 -I -c 'import sys; sys.path.insert(0, sys.argv[1]); import pathlib, self_goal as g; print("\t".join(g.goal_state(pathlib.Path(sys.argv[2]))))' "$here/bin" "$tmp/s.jsonl"
}
set_='{"attachment":{"type":"goal_status","met":false,"sentinel":true,"condition":"c1"}}'
done_='{"attachment":{"type":"goal_status","met":true,"condition":"c1","reason":"r"}}'
bad_='{"attachment":{"type":"goal_status","met":false,"failed":true,"condition":"c1"}}'
clr_='{"type":"user","message":{"content":"<local-command-stdout>Goal cleared: c1</local-command-stdout>"}}'
clrs_='{"attachment":{"type":"goal_status","met":true,"sentinel":true,"condition":"c1"}}'
[ "$(state '{}')" = $'none\t' ] || fail none-state
[ "$(state "$set_")" = $'active\tc1' ] || fail active
[ "$(state "$set_" "$done_")" = $'achieved\tc1' ] || fail achieved
[ "$(state "$set_" "$bad_")" = $'failed\tc1' ] || fail failed
[ "$(state "$set_" "$clrs_" "$clr_")" = $'cleared\tc1' ] || fail cleared
python3 -I "$here/tests/test_self_goal.py"
echo "ok"
