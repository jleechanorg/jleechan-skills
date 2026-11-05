---
name: worktree-protection
description: Verify exact worktree ownership, preserved state and cleanup authorization; names and missing sessions are not permission to remove work.
type: policy
---

# Worktree Protection Rules

## Verify ownership and authority

A basename pattern or missing tmux session is an inventory hint, not proof that
a worktree is abandoned or disposable. Resolve the exact registered path,
branch and owner; inspect dirty files, unpushed commits, active processes and
the owner's transcript before assessing cleanup. Preserve unrelated work and
the active worktree.

Removal requires existing authorization for that exact target under shared
destructive-action policy. Neither an AO-looking name nor a merged PR supplies
that authorization. Conversely, an explicitly authorized target does not need
an AO-style name. Use the owning cleanup procedure and prefer recoverable
operations; report what was removed and how it can be recovered.

## Hard rules

- **NEVER run `git worktree prune`** — it indiscriminately removes all dead worktrees including human ones
- Never use name matching as the cleanup safety gate or recursively remove a
  computed target. Follow the shared destructive-path guard.
- Create worktrees with `diskm worktree-new` under `~/.worktrees/<repo>/<name>`
  unless an explicit applicable allowlist permits another root.
