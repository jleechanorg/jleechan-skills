---
name: ao-spawn-gate
description: Pre-spawn checklist for Agent Orchestrator worker dispatch.
---

# ao-spawn-gate

Pre-spawn checklist for AO worker dispatch. Run this before approving any new worker spawn.

## Required checks (in order)

1. **GitHub rate limits**

```bash
gh api rate_limit
```

2. **Active tmux session count**

```bash
tmux list-sessions | wc -l
```

3. **Available context check** (avoid spawning if there is no actionable context)

```bash
# Verify there is a concrete task / PR / issue context
~/bin/ao status --project agent-orchestrator
~/bin/ao session ls
```

## Thresholds / gate rules

- If `graphql.remaining < 200` → **BLOCK spawn**. Warn user and use REST fallback for urgent operations.
- If `graphql.remaining < 100` → **REST fallback exclusively** (no GraphQL calls).
- If `core.remaining < 500` → **defer non-critical reads/polls**.
- If active AO workers are at/over the cap in `~/.claude/skills/ao-spawn-safety/SKILL.md` (currently 30) → **BLOCK spawn** until capacity drops. Count workers via `ao session ls`, not raw `tmux list-sessions` — the raw tmux count includes orchestrator and non-AO panes, and a stale `>15` tmux threshold here used to block spawns well below the real worker cap.
- If no concrete task context (no issue/PR/objective) → **BLOCK spawn** and request context.

## REST fallback commands

```bash
# Create PR
gh api repos/jleechanorg/agent-orchestrator-ts/pulls --method POST \
  -f title='[agento] ...' -f head='branch-name' -f base='main' -f body='...'

# Comment on PR
gh api repos/jleechanorg/agent-orchestrator-ts/issues/<PR_NUMBER>/comments --method POST \
  -f body='...'

# Get PR details
gh api repos/jleechanorg/agent-orchestrator-ts/pulls/<PR_NUMBER>
```

## Approval output format

When approving spawn, include:
- graphql.remaining
- core.remaining
- active tmux session count
- task context source (PR/issue/session)
- go/no-go decision

If blocked, include the exact blocker and retry trigger.
