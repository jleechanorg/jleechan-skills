---
description: Run all crontab automation jobs and verify they worked
type: execution
execution_mode: immediate
---

## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**

## Overview
Parse `crontab -l` to find all `jleechanorg-pr-monitor` jobs and execute them with the same parameters, then verify success.

## CRITICAL: This command runs automation jobs - use with caution

**Jobs to run** (from crontab):
1. `jleechanorg-pr-monitor --max-prs 10` (every 2 hours - PR monitoring)
2. `jleechanorg-pr-monitor --fix-comment --cli-agent minimax --max-prs 3` (every hour at :45)
3. `jleechanorg-pr-monitor --comment-validation --max-prs 10` (every 30 min)
4. `jleechanorg-pr-monitor --codex-update --codex-task-limit 10` (every hour at :15)
5. `jleechanorg-pr-monitor --codex-api --codex-apply-and-push --codex-task-limit 10` (every hour at :30)
6. `jleechanorg-pr-monitor --fixpr --max-prs 10 --cli-agent minimax` (every 30 min)

## EXECUTION WORKFLOW

### Phase 1: Extract Jobs from Crontab

**Action Steps:**
1. Run: `crontab -l | grep jleechanorg-pr-monitor`
2. Parse each line to extract the full command (after the schedule)
3. Store commands for execution

### Phase 2: Run Each Job

**Action Steps:**
For each extracted command:
1. Display the command being run
2. Execute with timeout (300s max per job)
3. Capture output and exit code
4. Log result

### Phase 3: Verify Success

**Action Steps:**
1. Check exit codes for each job
2. Look for success indicators in output:
   - "Successfully processed PR"
   - "Monitoring cycle complete"
   - "No open PRs found"
3. Report any failures with details

## Reference: Cron Job Schedule

```
# [CRON-JOB-ID: pr-monitor] Run PR monitoring (comment-only mode) every 2 hours
0 */2 * * * jleechanorg-pr-monitor --max-prs 10

# [CRON-JOB-ID: fix-comment] Run fix-comment workflow with MiniMax every hour at :45
45 * * * * jleechanorg-pr-monitor --fix-comment --cli-agent minimax --max-prs 3

# [CRON-JOB-ID: comment-validation] Run comment validation workflow every 30 minutes
*/30 * * * * jleechanorg-pr-monitor --comment-validation --max-prs 10

# [CRON-JOB-ID: codex-update] Run Codex automation every hour at :15
15 * * * * jleechanorg-pr-monitor --codex-update --codex-task-limit 10

# [CRON-JOB-ID: codex-api] Run Codex API automation every hour at :30
30 * * * * jleechanorg-pr-monitor --codex-api --codex-apply-and-push --codex-task-limit 10

# [CRON-JOB-ID: fixpr] Run orchestrated PR fixes every 30 minutes
*/30 * * * * jleechanorg-pr-monitor --fixpr --max-prs 10 --cli-agent minimax
```

## Verification Checklist

- [ ] All jobs executed without crashes
- [ ] Exit codes captured
- [ ] Success/failure status reported for each job
- [ ] Any errors logged with details
