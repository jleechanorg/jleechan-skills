---
name: cmux-backup
description: Backup all cmux workspaces, surfaces, and their current working directories via the socket API. Produces a timestamped JSON snapshot at ~/.cmux-backups/.
metadata:
  type: skill
---

# cmux-backup

Snapshot all cmux workspaces + surfaces + per-workspace CWD/git state to
`~/.cmux-backups/<timestamp>.json` via the cmux Unix socket API.

## Invoke

```
/cmux-backup
```

Or manually:

```bash
~/.claude/scripts/cmux-backup.sh
```

## What it captures

| Field | Source |
|---|---|
| workspace id, title, index, selected | `workspace.list` JSON API |
| workspace current_directory | `workspace.list` `.current_directory` |
| workspace cwd (shell-reported) | `sidebar_state --tab=<ws_uuid>` → `cwd=` |
| workspace focused_cwd | `sidebar_state` → `focused_cwd=` |
| workspace git_branch | `sidebar_state` → `git_branch=` |
| workspace PR info | `sidebar_state` → `pr=`, `pr_label=` |
| surface id, title, type, pane_id | `surface.list` JSON API |

## Output format

```json
{
  "timestamp": "2026-05-18T12:34:56",
  "socket": "/Users/.../cmux.sock",
  "workspace_count": 26,
  "workspaces": [
    {
      "id": "8DAE7F5B-...",
      "title": "worktree_level_choices",
      "index": 0,
      "selected": false,
      "current_directory": "$HOME",
      "cwd": "$HOME/projects/worktree_level_choices",
      "focused_cwd": "$HOME/projects/worktree_level_choices",
      "git_branch": "feat/level-choices",
      "pr": "123",
      "surfaces": [
        {
          "id": "07A1ECD6-...",
          "title": "worktree_level_choices",
          "type": "terminal",
          "pane_id": "6FECF31A-..."
        }
      ]
    }
  ]
}
```

## Protocol used

```bash
SOCK="$CMUX_SOCKET"  # or ~/Library/Application Support/cmux/cmux.sock

# All workspaces
printf '{"method":"workspace.list","params":{}}\n' | nc -U "$SOCK"

# Surfaces per workspace
printf '{"method":"surface.list","params":{"workspace_id":"<uuid>"}}\n' | nc -U "$SOCK"

# CWD + git state per workspace
printf "sidebar_state --tab=<workspace_uuid>\n" | nc -U "$SOCK"
```

## Dev build sockets

```bash
# Find socket for a specific dev build:
cat ~/Library/Application\ Support/cmux/dev-may-18-last-socket-path
lsof -p $(pgrep -f "cmux DEV may-18") | grep -E "\.sock"

# Use CLI with dev build socket:
CMUX_SOCKET_PATH=/tmp/cmux-debug-may-18.sock cmux list-workspaces
CMUX_SOCKET_PATH=/tmp/cmux-debug-may-18.sock cmux tree
```

## Companion restore skill

`~/.claude/scripts/cmux-restore.sh [--backup <file>] [--dry-run] [--list]`

- Skips workspaces already present by title
- Creates missing ones with `workspace.create` + `surface.send_text` cd
- Headless — never calls `select_workspace`

## Rules

1. Never call `select_workspace` — read-only snapshot only.
2. Use `$CMUX_SOCKET` env var first; fall back to
   `~/Library/Application Support/cmux/cmux.sock`.
3. Write backup to `~/.cmux-backups/cmux-backup-<timestamp>.json`.
4. Print a summary table to stdout (workspace index, title, cwd, git branch).
