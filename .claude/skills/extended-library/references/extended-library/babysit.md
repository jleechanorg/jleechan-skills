---
description: Babysit — orchestration loop to monitor PRs, CI, and test evidence generation
type: orchestration
execution_mode: immediate
---

# /babysit

Alias to invoke the babysit orchestration and monitoring loop.

**Usage**: `/babysit [target PR, branch, or test suite]`

## Action

Execute these steps in order:

Read `.claude/skills/pr-babysit/SKILL.md` for the full protocol, `/green` + draft-phase criteria, and anti-patterns.

**Testing Gap Integration**: If at any point the target tests fail to produce compliant `/es` evidence bundles, immediately load and execute `.claude/commands/testing-gap-close.md` to identify and resolve the failure.

### Step 2: Discover All Open PRs

```bash
gh pr list --state open --json number,title,headRefName,headRefOid,mergeable \
  --jq '.[] | "\(.number)|\(.title)|\(.headRefName)|\(.headRefOid[:12])|\(.mergeable)"'
```

### Step 3: Audit `/green` + Draft-Phase Status for Each PR

For each PR, check `/green` (CI green + no merge conflicts) plus the draft-phase
quality checks (comments, evidence — see SKILL.md for exact commands). CodeRabbit
and Bugbot feedback is optional advisory — surface it for information, never gate
or wait on it. Categorize:
- **RED** (2+ blocking checks failing): needs code fixes → dispatch copilot-fixpr subagents
- **YELLOW** (1 blocking check failing): needs comment resolution or evidence → fix inline
- **GREEN** (`/green` passes + draft-phase quality checks all pass): merge-ready

### Step 4: Dispatch Subagents to Fix RED PRs

Use Agent tool with `subagent_type: copilot-fixpr`, one per PR (or group related PRs).
Run in parallel using `run_in_background: true`.

Each agent must:
1. Read the Green Gate log to find the exact failing gate
2. Fix the root cause (code, design doc, evidence, rebase)
3. Push the fix
4. Optionally comment `@coderabbitai all good?` to refresh CR feedback — informational only, not required

### Step 5: Fix YELLOW PRs Inline

- Gate 5: Resolve review threads via GitHub API
- Gate 6: Add evidence or N/A justification to PR body
- Gates 3-4 (CR/Bugbot): read feedback if useful, fix any real code issues it surfaces — never required to unblock

### Step 6: Trigger Smoke on GREEN PRs

```bash
# Trigger smoke
gh pr comment <NUM> --body "/smoke"

# Green Gate re-run (if no recent run)
gh workflow run green-gate.yml --ref <branch> -f pr_number=<NUM>
```

### Step 7: Report Final Status

Print a table for ALL open PRs:

```
PR #<N> — <title> — status: <RED|YELLOW|GREEN>
  Gates: 1=✓ 2=✓ 3=✗ 4=✓ 5=✓ 6=✓
  Action: <what was done or what's pending>
```

### Step 8: Hold Loop — Stay Alive Until All PRs Merge

After Step 7, if any PRs are still open:

**In `/loop` mode** (user ran `/loop /babysit`): call `ScheduleWakeup` so the next iteration fires while the REPL is idle — never during an active conversation.

```python
ScheduleWakeup(
    delaySeconds=180,  # 3 min — within cache window, catches Design Doc bot commits quickly
    prompt="<<autonomous-loop-dynamic>>",
    reason="babysit hold: re-checking stale gate status"
)
```

**In one-shot mode** (user ran just `/babysit`): set up a `CronCreate` job for the same re-check and tell the user it's running. Delete it with `CronDelete` once all PRs merge.

Each wakeup iteration runs only a **lightweight stale-status sweep** (see Phase 8 in SKILL.md) — not a full re-audit. Re-check `/green` + draft-phase status only when both are true:
- PR HEAD has moved since the last check (new commits pushed), and
- CI is fully settled (`ci_failures == 0` and `ci_pending == 0` from `statusCheckRollup`).

**Exit**: Stop scheduling when no open PRs remain.

## KEY RULES

- **PR Green Loop Protocol**: Batch fixes, push once.
- **CodeRabbit/Bugbot: optional advisory reviewers** — read their feedback, take what's useful; never a gate, never a wait. Dismissing their CHANGES_REQUESTED reviews is allowed.
- **Never merge** — no automated path merges; only explicit human "MERGE APPROVED" authorizes `gh pr merge`
- **`/green` verification**: `/green` = CI green + no merge conflicts only (see `.claude/skills/pr-green-definition.md`); CodeRabbit/Bugbot/comments/evidence are draft-phase quality gates, not part of `/green`. Must read the Green Gate gate-by-gate log for Gate 1, not just `gh pr checks`
- **Evidence required** for non-docs PRs touching `$PROJECT_ROOT/**`
