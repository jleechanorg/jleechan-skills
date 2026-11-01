---
name: ao-lifecycle-triage
description: Triage AO lifecycle backfill claim failures and ghost worktree fetch errors.
---

# AO Lifecycle Backfill Claim Failure Triage

This is a read-only diagnosis by default. Preserve the current checkout,
branch, worktree, and any uncommitted data. Never run `git reset --hard`,
`git clean`, or `git worktree remove --force` as an automatic repair. Resolve
the exact target and inspect its status before any authorized cleanup; use the
approved `diskm worktree-new` path when an isolated checkout is needed.

## When to use
When `lifecycle.backfill.claim_failed` errors appear in the lifecycle-worker log with:
`fatal: refusing to fetch into branch 'refs/heads/BRANCH' checked out at 'PATH'`

## Two distinct root causes (same error surface)

### Cause A: Main repo on wrong branch
**Symptom**: `checked out at '$HOME/project_agento/agent-orchestrator-ts'`
**Diagnosis**: `git -C $HOME/project_agento/agent-orchestrator-ts branch --show-current`
**Safe recovery**:
```bash
git -C "$HOME/project_agento/agent-orchestrator-ts" branch --show-current
git -C "$HOME/project_agento/agent-orchestrator-ts" status --short
git -C "$HOME/project_agento/agent-orchestrator-ts" worktree list --porcelain
```
Do not switch branches or pull in the active main checkout automatically. If it
is dirty or another worker owns it, preserve it and continue diagnosis through
an approved isolated worktree.

### Cause B: Ghost worktrees (dead AO worktrees with branches still checked out)
**Symptom**: `checked out at '$HOME/.worktrees/agent-orchestrator/ao-NNN'`
**Diagnosis**: `git worktree list | grep ao-NNN` — if present with no live tmux session, it's a ghost
**Safe recovery**:
```bash
ao session ls
git -C "$HOME/projects/agent-orchestrator" worktree list --porcelain
git -C "$HOME/.worktrees/agent-orchestrator/ao-NNN" status --short
```
Confirm the session/process owner and inspect the exact worktree before any
cleanup. A missing tmux session alone does not prove that the checkout is safe
to remove. Do not use `--force`; if it contains changes, preserve them and
report the exact blocker. Any deletion requires separate explicit
authorization.

## Triage order (always check A first)

1. Look at the path in the error: if it's the main repo path → Cause A
2. If it's `~/.worktrees/...` → Cause B
3. If backfill is aborted (`claim_failed_abort` after 3 consecutive failures), check both

## Prevention

- `sweepOrphanWorktrees` in lifecycle-worker.ts runs every 5min (orphan TTL: 6h)
- Agents should leave unrelated checkouts untouched; AO lifecycle cleanup must preserve task work and use the approved worktree path

## Harness note

Ghost worktree accumulation cleaned manually twice in the same session on 2026-03-24 — this is the harness-level fix. If seeing this pattern again, the `orphanTtlMs` may need reduction.
