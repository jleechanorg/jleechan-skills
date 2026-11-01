---
name: ao-spawn-gate
description: Pre-spawn checklist for Agent Orchestrator worker dispatch.
---

# ao-spawn-gate

Pre-spawn checklist for AO worker dispatch. Run this before approving any new worker spawn.

## Required checks (in order)

1. **GitHub rate limits, when the task needs GitHub API calls**

```bash
gh api rate_limit
```

2. **Active AO worker count**

```bash
ao session ls
```

3. **Available context check** (avoid spawning if there is no actionable context)

```bash
# Verify there is a concrete task / PR / issue context
~/bin/ao status --project agent-orchestrator
~/bin/ao session ls
```

## Thresholds / gate rules

- Report GraphQL and REST/core quota values separately. A low GraphQL bucket
  does not block a spawn or unrelated work; choose REST only for an operation
  it supports and when its own bucket is available.
- Before calling GitHub/API work blocked, use the bounded REST/GraphQL fallback
  in `~/.claude/skills/github-cli-reference/SKILL.md` where the operation
  permits it. A REST fallback applies only to the specific operation; it does
  not authorize write operations or retry uncertain mutations.
- Apply the live AO worker and channel caps from
  `~/.claude/skills/ao-spawn-safety/SKILL.md`. Count workers from `ao session
  ls`, not tmux. At the cap, defer only the new AO spawn; do not run cleanup,
  kill sessions, or raise the cap automatically. Continue independent work.
- If the request provides no concrete authorized task context, do not spawn;
  report the missing context as the dependency.

## REST fallback commands

```bash
# Create PR — only when the current task explicitly authorizes PR creation.
# Resolve existing state before retrying an uncertain mutation.
gh api repos/jleechanorg/agent-orchestrator-ts/pulls --method POST \
  -f title='[agento] ...' -f head='branch-name' -f base='main' -f body='...'

# Comment on PR — only when the current task explicitly authorizes sending it.
gh api repos/jleechanorg/agent-orchestrator-ts/issues/<PR_NUMBER>/comments --method POST \
  -f body='...'

# Get PR details
gh api repos/jleechanorg/agent-orchestrator-ts/pulls/<PR_NUMBER>
```

## Approval output format

When reporting a spawn decision, include:
- the fresh AO worker count and applicable channel-policy result
- GraphQL and REST/core availability only when GitHub calls are needed
- task context source (PR/issue/session)
- go/no-go decision

If blocked, include the exact blocker and retry trigger.
