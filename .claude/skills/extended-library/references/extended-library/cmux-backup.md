# /cmux-backup

Backup all cmux workspaces, surfaces, and their current working directories via the socket API.

## What it does

Runs `~/.claude/scripts/cmux-backup.sh` which:
1. Queries `workspace.list` for all workspaces
2. Queries `sidebar_state` per workspace for shell-reported CWD + git branch
3. Queries `surface.list` per workspace for all surface tabs
4. Parses directory from terminal titles as fallback CWD source
5. Writes `~/.cmux-backups/cmux-backup-<timestamp>.json`
6. Prints a summary table

## Usage

```
/cmux-backup
```

The Claude agent should run:
```bash
~/.claude/scripts/cmux-backup.sh
```

Print the summary table output to the user and report the output file path.
