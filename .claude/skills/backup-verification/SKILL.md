---
name: backup-verification
description: Use whenever asked whether "the backup" is working, or after invoking scripts/backup-home.sh or any multi-target backup script, or when detecting config drift, missing files in repo, rsync failures, or /green-style verdicts that depend on backup state. Mandates per-target verification rather than trusting the script's overall exit status.
---

# Backup Verification

## Rule
After ANY invocation of a multi-target backup script (git + dropbox, git + s3, etc.), do NOT trust the script's overall exit status as proof of backup health. ALWAYS independently verify each target. This applies to:

- After every invocation of `scripts/backup-home.sh` (user-scope repo)
- After every launchd `org.$USER.user-scope-backup` tick (every 2 h, scheduled)
- Before any report, claim, or PR whose correctness depends on backup state
- When answering "is the backup working?" in any form
- When debugging missing files in `backup/<host>/...`
- When `/green` verdicts depend on backup freshness

## Required checks (in order)

1. **Read the report file** at the canonical path:
   - `~/Library/Logs/home-backup.latest.report.txt`
   - The launchd log also streams per-tick output: `~/Library/Logs/user-scope-backup.launchd.log`

2. **Parse BOTH per-target result lines independently**:
   - `result_git=SUCCESS | PARTIAL | FAILED | TIMEOUT | SKIP`
   - `result_dropbox=SUCCESS | PARTIAL | FAILED | TIMEOUT | SKIP [reason=...]`

3. **Parse per-item statuses from the `item|` lines** (newer convention; emitted by `run_rsync_copy`):
   - Each row: `item|<target>|<src>|<dst>|<status>|<bytes>|<elapsed_s>|<exit>`
   - Status values: `OK`, `TIMEOUT`, `FAILED`, `SKIP` (no source on disk)

4. **Treat as failed**:
   - `result_dropbox=TIMEOUT | FAILED | PARTIAL | SKIP` → dropbox is degraded; the git side is unaffected (see `scripts/backup-home.sh` lines 946-957 for the "git is authoritative, dropbox is convenience mirror" design comment).
   - Exit code 0 + `result_dropbox=TIMEOUT` is the silent-degradation class (legacy 2026-07-27 → 2026-07-29 wedge window — that bug is fixed in commit `70940f08b`-derived change-set, but the script now exits non-zero on PARTIAL as a structural guarantee).
   - Exit code 1 + `result_dropbox=PARTIAL` is the expected degraded signal; verify the persistent log `~/Library/Logs/backup-home-alerts.log` and the macOS notification.

5. **Surface BOTH targets to the user explicitly** — do not summarize the run as "backup worked" or "backup failed" without naming both targets.

## Per-source timeout ceilings (codifies scripts/backup-home.sh)

| Class | Wall-clock | Rsync | Examples |
|---|---|---|---|
| `small` | 60 s | single file `<1 GiB` | codex_history, claude_history, configs, bashrc |
| `medium` | 300 s | 1–5 GiB or normal directory | codex_archived_sessions, memory, cursor/chats |
| `large_dir` | 2400 s | `>5 GiB` or high-file-count (millions of jsonl/sqlite) | codex_sessions, claude_sessions, claude/projects, mcp_daemon |

Override per-row via `_PER_SOURCE_TIMEOUT_OVERRIDES` associative array in `scripts/backup-home.sh`.

## Failure modes this prevents

- **Silent green**: `git push` succeeds (commit `1e1df25d2 → 7eb57a0f9 → 70940f08b`) while dropbox is wedged for hours. The 2026-07-27 → 2026-07-29 launchd log shows `result_dropbox=TIMEOUT` on 10+ consecutive ticks with the script's exit 0 — exactly this class.
- **Stale process trust**: `gtimeout --kill-after` keeps the per-source timeout honest, but if the per-source timeout is dropped or falls back to bash builtin `timeout`, the openrsync orphan cascade wedges the next 2-h tick. Always probe `gtimeout --version` and verify ≥ `9.0` before relying on the wrapper.
- **Disk wedge**: at `>=95%` used on `/System/Volumes/Data`, the macOS CloudStorage FileProvider returns `Interrupted system call` on every stat/read. The script's pre-run `df` check (added 2026-07-29) writes `result_dropbox=SKIP reason=DISK_PRESSURE` and skips; verify that, don't try to retry the source list.

## When NOT to use this skill

- If the user is asking about a non-`backup-home` script (e.g. worldarchitect deploys), do not mechanically apply this — adapt to that script's per-target report format.
- If the report file genuinely doesn't exist or is truncated mid-write (very rare; would indicate a launchd SIGKILL during finalize_backup_report), say so explicitly and route to manual investigation rather than guessing.

## Companion files

- Script: `$HOME/projects/user_scope/scripts/backup-home.sh`
- Schedule: `~/Library/LaunchAgents/org.$USER.user-scope-backup.plist`
- Plist template: `$HOME/projects/user_scope/dotfiles/launchd/org.$USER.user-scope-backup.plist`
- Companion cleanup job: `~/Library/LaunchAgents/org.$USER.backup-dropbox-orphan-cleanup.plist` (template in same dir)
- Persistent log: `~/Library/Logs/backup-home-status.log`
- Per-target report: `~/Library/Logs/home-backup.latest.report.txt`
- Alerts: `~/Library/Logs/backup-home-alerts.log`
