---
name: AO Session Monitor
description: Properly inspect AO worker tmux sessions to detect working vs idle state
---

# AO Session Monitor Skill

## How to check if an AO worker session is active

Claude Code renders the `❯` prompt at the bottom of the tmux pane **while the model is thinking above it**. Checking only the last 5-6 lines will produce false "idle" reports.

### Correct detection method

1. Capture at least 20 lines: `tmux capture-pane -t <session> -p -S -20`
2. Look for **Unicode activity indicators**: `✻ ✶ ✳ ✽ ✾` followed by an action word and duration
   - Examples: `✻ Cascading… (5m 34s · ↓ 3.0k tokens · thinking)`
   - Examples: `✶ Germinating… (2m 21s · ↓ 1.2k tokens · thought for 7s)`
3. Look for **tool use in progress**: `Bash(`, `Read(`, `Edit(`, `Write(`, `Grep(`, `Glob(`
4. Look for **"Running…"** — a Bash command is executing

### State classification

| Indicator | State | Meaning |
|---|---|---|
| `✻✶✳✽✾` + duration | **WORKING** | Model is thinking or executing tools |
| `Running…` or `timeout` | **WORKING** | Shell command in progress |
| `Baked for Xm` or `Sautéed for Xm` | **COMPLETED** | Finished, went idle |
| `❯` with no activity indicators in 20 lines | **IDLE** | Actually waiting for input |
| `Press up to edit queued messages` | **QUEUED** | Has pending message from lifecycle-worker |
| `+uncommitted` in status bar | **HAS WORK** | Edited files but hasn't committed/pushed |

### Common false positives

- **`❯` visible = idle**: WRONG. The prompt renders below the thinking indicator. Always check 20+ lines.
- **No `Bash` in last 6 lines = not working**: WRONG. The model may be in a long thinking phase between commands.
- **Session shows old output = dead**: WRONG. The model may be mid-thought. Check for activity indicators.

### Shell one-liner for monitoring

```bash
for s in $(tmux list-sessions 2>/dev/null | grep "ao-[0-9]" | cut -d: -f1); do
  name=${s##*-}
  last=$(tmux capture-pane -t "$s" -p -S -20 2>/dev/null)
  pr=$(echo "$last" | grep -oE "PR: #[0-9]+" | head -1)
  uc=""; echo "$last" | grep -q "uncommitted" && uc="+uc"
  activity=$(echo "$last" | grep -oE "[✻✶✳✽✾] [A-Za-z]+…[^)]*\)" | tail -1)
  if [ -n "$activity" ]; then
    echo "  $name: WORKING $pr $uc ($activity)"
  elif echo "$last" | grep -qE "Baked|Sautéed"; then
    echo "  $name: completed $pr"
  elif echo "$last" | grep -q "queued"; then
    echo "  $name: QUEUED $pr"
  else
    echo "  $name: idle $pr $uc"
  fi
done
```
