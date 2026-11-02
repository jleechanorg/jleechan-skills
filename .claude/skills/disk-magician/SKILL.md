---
name: disk-magician
description: Use when diagnosing disk capacity or growth and when previewing or executing repository-gated cache, scratch, temp, or worktree cleanup.
---

# Disk Magician — Fast-Path Triage & Parallel Cleanup Skill

Use `diskm` (`./disk_magician.sh` / `disk-magician`) to diagnose disk capacity, compare against the 7d/30d floor, and execute safety-gated cleanups without stalling on 15-minute `du` walks.

## Phase 0 — `<10s` Zero-`du` Triage (Always Run First in Parallel)

Never start with a 15-minute `diskm audit` whole-disk `du` scan when asked to check or clean disk space. Run these 4 instant commands in parallel (`<10s` total):

```bash
df -h / 2>/dev/null; diskm volume status scratch 2>/dev/null | head -5
diskm check-launchd-fleet
diskm reclaim-ledger --read-existing
diskm history growth-top10 --days 7
```

Only run the full `diskm audit` (`scripts/disk_root_cause_audit.py`) when the pre-computed ledger/snapshots are missing or stale (`>48h`).

## Phase 1 — Parallel `flash` Subagent Cleanup Lanes (High-Yield Order)

For large reclaims (`50–300+ GiB`), do not run all 22 categories serially in one foreground shell (and never run `cleanup_dev_caches.sh` first, as its `~/Library/Caches` walk holds `.owner-mutation.reuse-lock`). Dispatch **parallel `flash` subagents** across these non-contending lanes:

1. **Lane A — Dedicated Scratch Volume (`20–150+ GiB`)**:
   ```bash
   diskm scratch-prune --clean
   ```
   *(Enforces 48h floor, live-PID, active C14 lease, and 64 MiB `.diskm-ballast` reserve; supports `--min-hours 12` with explicit user approval).*
2. **Lane B — Git Worktree Slimming, Deps & Dormant Worktrees (`30–180+ GiB`, run in order)**:
   ```bash
   WORKTREE_APPROVED=1 diskm slim-worktrees --clean
   WORKTREE_APPROVED=1 diskm cleanup-worktree-deps --clean
   WORKTREE_APPROVED=1 diskm cleanup-worktrees --clean
   WORKTREE_APPROVED=1 diskm cleanup-worktree-venvs --clean
   ```
   *(Shard `cleanup-worktrees --clean` across `--repos <repo>` in parallel when `>200` worktrees exist).*
3. **Lane C — Containers, Xcode, Browser Clones & Cloud Caches (`20–80+ GiB`)**:
   ```bash
   diskm cleanup-colima --clean
   diskm cleanup-xcode --clean
   diskm prune-aside-sessions --clean
   CODE_SIGN_CLONES_APPROVED=1 diskm cleanup-code-sign-clones --clean
   FILEPROVIDER_EVICT_APPROVED=1 diskm evict-fileprovider --clean
   ```
4. **Lane D — Agent State Compaction, SQLite Vacuum & Temp (`5–20 GiB`)**:
   ```bash
   diskm vacuum-hermes-state --clean
   diskm cleanup-codex-db --clean
   diskm cleanup-antigravity-brain --clean
   diskm cleanup-tmp --clean
   diskm cleanup-dev-caches --clean
   ```

Or run the unified 6-tier routine stack via:
```bash
./disk_magician.sh clean
```

## Phase 2 — Silent-Preservation Diagnostic Rule

Never report *"canonical stack is exhausted"* while free space remains below target. If a cleaner exits `0` with `0 B` reclaimed, inspect its skip breakdown (`kept:lease-busy`, `ao-owned-or-unknown`, `kept:admin-unknown`, `kept:recent-activity`, `dirty-or-untracked`) and verify `~/.disk_magician_state/worktree_leases/.owner-mutation.reuse-lock` is not wedged.

## Safety Constraints & Guardrails
- **Recency floors:** `cleanup_worktrees.sh` and `cleanup_worktree_deps.sh` enforce a 3-day floor (`worktree_min_stale_days`, or `DISK_MAGICIAN_WORKTREE_FLOOR_HOURS>=12` when explicitly approved); `slim_worktree_checkouts.sh` and `cleanup_worktree_venvs.sh` enforce a 7-day floor (`--min-hours 12` for `slim-worktrees` when explicitly approved); `scratch-prune` enforces a 48-hour floor (`--min-hours 12` when explicitly approved).
- **Never-delete list:** Do not delete `~/.codex/sessions*`, `~/.codex/state*.sqlite`, `~/.codex/log`, or `~/.claude/projects`. Always route deletions through `diskm` / `disk_magician.sh`.
