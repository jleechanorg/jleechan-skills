---
name: ao-session-monitor
description: Properly inspect AO worker tmux sessions to detect working vs idle state
---

# AO Session Monitor Skill

## How to check an AO worker session

The bottom of a Claude Code pane can show a prompt while the model is still
thinking or while older work is deep in scrollback. A short tail or status
indicator is never enough to classify the session.

1. Capture the full available history with `tmux capture-pane -t <session> -p -S -`.
   Read the full capture, then inspect the last 15 lines for current state.
2. For any idle, stalled, or blocked classification, capture again 20–30 seconds
   later to a different unique file under `/tmp`. If the screens differ, label
   the worker `WORKING` and stop classification.
3. Identical captures are not proof of idleness. Check for post-footer tool
   calls or assistant text, timer growth, and the worker process tree/CPU. For a
   `pi` pane, also check growth of the matching session JSONL. If full scrollback
   or a required independent process check is unavailable, report `UNVERIFIED`.
4. Treat activity indicators, queued-message text, completed footers, and
   uncommitted markers as clues inside the full capture, never as state on
   their own. They may describe earlier turns or quoted text.

The shared full-buffer requirement is in `~/.codex/AGENTS.md` § “Reading a
cmux terminal before deciding (full-buffer rule)”; cmux-specific capture and
steering mechanics are owned by `~/.claude/skills/cmux-steer/SKILL.md`.

Do not use a one-line grep/tail script to assign `IDLE`, `COMPLETED`, or
`BLOCKED`. Batch capture may collect candidates, but the full-history and
independent-process checks above determine the state.
