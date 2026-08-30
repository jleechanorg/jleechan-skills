# /cmux-restore

Restore cmux workspaces from a backup created by `/cmux-backup`.

## Flags

| Flag | Effect |
|---|---|
| (none) | Restore from most recent backup in `~/.cmux-backups/` |
| `--backup <file>` | Restore from a specific backup JSON file |
| `--dry-run` | Show what would be created/skipped, no changes |
| `--list` | List available backup files |

## Behavior

- Skips workspaces that already exist by title (safe to re-run)
- Creates missing workspaces with `workspace.create` + `current_directory`
- Sends `cd <cwd>` to each new surface via `surface.send_text` (cross-workspace)
- Restores multiple surfaces per workspace if backup captured them
- Never calls `select_workspace` — headless, non-disruptive

## Usage

Run the appropriate shell command based on flags provided by the user:

```bash
~/.claude/scripts/cmux-restore.sh                          # most recent backup
~/.claude/scripts/cmux-restore.sh --list                   # list backups
~/.claude/scripts/cmux-restore.sh --dry-run                # preview
~/.claude/scripts/cmux-restore.sh --backup <file>          # specific file
```
