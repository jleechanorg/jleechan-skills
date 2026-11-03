---
name: disk-magician
description: Use when measuring disk capacity or growth and previewing repository-gated cleanup.
---

# Disk Magician

Use `diskm` for disk measurements, growth ledgers, and repository-gated cleanup previews. Read the active command's `--help` for its current flags and approval gates; examples below are previews only.

## Choose the procedure

- A quick free-space check or plain “how much can I reclaim?” estimate belongs to [`disk-audit`](../disk-audit/SKILL.md). It starts with zero-`du` triage.
- A question about why space changed, what grew, or which bucket explains growth belongs to [`disk-root-cause`](../disk-root-cause/SKILL.md). That skill uses the existing ledger first and runs a full top-down audit only when its freshness or residual rules require one.
- A request to preview or perform a cleanup uses this skill and the current `diskm` cleanup command. A preview does not authorize deletion.

## Quick capacity triage

For a quick check or cleanup request, do not launch a whole-disk `du` audit first. Run the four read-only checks concurrently:

```bash
df -h /System/Volumes/Data /Volumes/diskm-scratch /System/Volumes/VM 2>/dev/null || df -h / ~/Scratch
diskm check-launchd-fleet
diskm reclaim-ledger --read-existing
diskm history growth-top10 --days 7
```

### Default forensic diagnosis (attribution only)

For attribution questions, follow `disk-root-cause`. Its first-use path begins with the checks above. Run the slower `diskm audit` only when the precomputed ledger or snapshots are missing or stale (`>48h`), or when an unaccounted residual needs a fresh top-down scan. Read the whole report before drilling down. Residual is an attribution gap, not backup size or reclaimable space without evidence.

## Preview cleanup lanes

Use the narrowest preview that answers the request. The unified `diskm clean --dry-run` preview includes the routine cache, temporary-file, container, Xcode, and worktree lanes.

- **Scratch volume:** `diskm scratch-prune --dry-run`. Inspect each candidate's C14 verdict, lease, live-process, open-file, and retention result.
- **Worktrees and dependencies:**
  ```bash
  diskm slim-worktrees --dry-run --min-age 7
  diskm cleanup-worktree-deps --dry-run --min-age 7
  diskm cleanup-worktrees --dry-run --min-age 7
  diskm cleanup-worktree-venvs --dry-run --min-age 7
  ```
  Preserve the owning repository's seven-day worktree floor; do not lower it with a command flag.
- **Containers, browser sessions, code-sign clones, and cloud files:**
  ```bash
  diskm cleanup-colima --dry-run
  diskm prune-aside-sessions --dry-run
  diskm cleanup-code-sign-clones --dry-run
  diskm evict-fileprovider --dry-run
  ```
  FileProvider eviction leaves cloud content in place and may rematerialize it on access; it is not a permanent deletion.
- **Agent state and temporary files:**
  ```bash
  diskm cleanup-codex-db --dry-run
  diskm cleanup-antigravity-brain --dry-run
  diskm cleanup-tmp --dry-run
  diskm cleanup-dev-caches --dry-run
  ```
  `diskm vacuum-hermes-state` previews by default; its `--apply` action has a separate command gate.

If a cleanup run reports `0 B` reclaimed or a preview shows no eligible targets, inspect its per-target skip reasons before concluding that the cleanup options are exhausted. Distinguish lease-busy, recent-activity, and admin-unknown keeps when the command reports them; check the lease holder before treating a lock as wedged.

## Approval and preservation

Every `--clean` or `--apply` action needs explicit user authorization for the exact target and must also satisfy the command's documented gate. An environment variable such as `WORKTREE_APPROVED=1` is not user approval; never include approval variables as inline command prefixes or runnable examples. Worktree deletion requires the explicit `WORKTREE APPROVED` confirmation, the `WORKTREE_APPROVED=1` gate, and the seven-day floor.

Never delete `~/.codex/sessions*`, `~/.codex/state*.sqlite`, `~/.codex/log`, or `~/.claude/projects` directly. Route cleanup through the owning `diskm` command so its safety filters and receipts apply.
