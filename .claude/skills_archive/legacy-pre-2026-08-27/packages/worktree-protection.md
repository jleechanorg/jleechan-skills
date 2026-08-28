---
name: worktree-protection
description: Worktree safety rules — AO-managed vs human-created worktrees, prune ban, cleanup guard regex
type: policy
---

# Worktree Protection Rules

## AO-managed worktrees

Basename matching `^(ao|jc|wa|cc|ra|wc)-[0-9]+$` — may be removed by agents when the corresponding tmux session is dead.

Before removing an AO worktree, verify its tmux session is dead:
```bash
tmux has-session -t <session-name> 2>/dev/null  # must fail
```

## Human-created worktrees

Any name NOT matching the AO pattern (e.g., `worktree_worker5`, `review_api_prs`) — **OFF-LIMITS**. Only a human may remove them.

## Hard rules

- **NEVER run `git worktree prune`** — it indiscriminately removes all dead worktrees including human ones
- When writing cleanup scripts, ALWAYS guard:
  ```bash
  if [[ ! "$name" =~ ^(ao|jc|wa|cc|ra|wc)-[0-9]+$ ]]; then echo "SKIP: $name"; continue; fi
  ```
