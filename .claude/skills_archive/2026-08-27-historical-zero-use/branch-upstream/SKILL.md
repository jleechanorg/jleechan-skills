---
name: branch-upstream
description: "Use when creating a new branch or entering a worktree. Sets upstream immediately via `git branch --set-upstream-to=origin/<branch>` after first checkout."
---

# Branch upstream tracking — always set after creation


After `git checkout -b` or entering a worktree: `git branch --set-upstream-to=origin/<branch> <branch>`. Don't wait for first push. Worktree branches never get upstream set automatically.
