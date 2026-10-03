---
name: ci-queue-trim
description: >
  Audit and trim queued GitHub Actions CI workflow runs for dormant,
  superseded, or merged PRs. Verifies run.headSha vs the current PR/branch
  head to detect obsolete queued pushes, applies event-specific semantics
  (pull_request/push vs merge_group vs unknown), and re-validates the
  candidate fingerprint immediately before any cancellation. Workflow
  importance is decided by an explicit configured allowlist, never by
  fuzzy substring heuristics. Includes Colima socket and host disk health
  preflights.
type: skill
scope: global
owner: $USER
version: 1.1.0
triggers:
  - "ci queue trim"
  - "trim ci queue"
  - "cancel dormant ci runs"
  - "clean up ci queue"
  - "trim queued jobs"
  - "ci backlog cleanup"
  - "pr inactivity trim"
allowed-tools:
  - Bash
  - Read
  - Write
---

# /ci-queue-trim — CI Queue Inactivity Triage & Trimming

Use this skill when GitHub Actions self-hosted or cloud runner queues become backlogged with queued runs from stale, dormant, already-merged, or already-superseded pull requests.

## The Three Pitfalls Resolved at Audit Time

### 1. Deceptive `PR.updatedAt` (bots touch it constantly)
When filtering PRs by activity, `PR.updatedAt` is **fundamentally deceptive**:
- Automated bots (merge queues, label synchronizers, automated status comments,
  rebase checks) constantly touch `updatedAt`.
- A PR whose code has not been touched in 10–30 days frequently shows
  `updatedAt` of "2 minutes ago".
- The script uses the head commit's **committer date** as the source of
  truth. Note: `committedDate` is the **author's commit timestamp**, which
  precedes the push — it is NOT the push time. Push time can be obtained
  from the run's `created_at` or by comparing run.headSha against the PR
  current head SHA.
- If no commit could be resolved within the inactivity window
  (default: 2 hours), the run is kept with `audit_incomplete=True`. The run's
  age is never substituted for the head-commit age.

### 2. Superseded runs (`run.headSha` ≠ PR/branch current head)
A run can be queued against an older SHA even though the PR has since been
pushed to a newer one. Comparing `run.headSha` to the PR's current
`head.sha` (or, for push events, to the branch HEAD SHA) catches these
without false-positive dormancy cancellations.
- For `pull_request` / `pull_request_target` events: the comparison ref is
  `PR.head.sha`, the **merge ref inside the base repo**. For fork PRs the
  run's recorded head SHA may be a fork SHA and is NOT comparable directly;
  the script compares it against the base repo's PR.head.sha.
- For `push` events: the comparison ref is the branch HEAD SHA.
- For `merge_group` and any unsupported event: the generic stale-head
  comparison is **never applied** — these events are kept (or, if the PR is
  already MERGED/CLOSED, cancelled as orphans).

### 3. Lookup failures (PR / commit / run detail unknown)
If the audit cannot verify the PR head, the head commit date, or the run
metadata, the run is kept with `audit_incomplete=True` and the cancellation
list is filtered by `refresh_before_cancel` immediately before mutation.
The tool never substitutes the run's age for a missing head-commit age.

## Protected Branches and Workflows

- **Protected branches** (never cancelled automatically):
  `main`, `master`, `production`, `staging`, `release`, `deploy`.
- **Protected workflows** (never cancelled automatically) are decided by an
  **explicit configured allowlist** at the top of the script
  (`PROTECTED_WORKFLOWS`). A workflow whose name merely contains a keyword
  such as "deploy" or "reusable" is **not** implicitly protected — populate
  the allowlist with the exact workflow filename or display name.
- Reusable workflows invoked via `workflow_call` are protected by **event
  semantics**, not by fuzzy name matching.

---

## Tooling & Command Syntax

The skill includes a pre-built, standalone Python helper at:
`/Users/jleechan/.claude/skills/ci-queue-trim/scripts/ci_queue_trim.py`

### 1. Dry-Run Audit (Default)
Inspects the queue, maps each run to its PR, evaluates supersede + dormancy,
and flags cancel candidates:
```bash
python3 ~/.claude/skills/ci-queue-trim/scripts/ci_queue_trim.py
```

### 2. Execute Cancellations
Cancels superseded or orphaned (MERGED/CLOSED PR) queued runs after
`rebalancing_before_cancel` validates each candidate's fingerprint:
```bash
python3 ~/.claude/skills/ci-queue-trim/scripts/ci_queue_trim.py --cancel
```

### 3. Superseded-Only Mode (Conservative)
Cancels runs whose head SHA is proven obsolete (newer push advanced the PR or
branch head). **Dormancy is ignored** — even ancient current-head runs are
kept. Recommended for first-time operators who want to apply only the
strictest proven-obsolete criterion:
```bash
python3 ~/.claude/skills/ci-queue-trim/scripts/ci_queue_trim.py \
    --superseded-only --cancel
```

### 4. Customize Threshold and Target Repo
Change the inactivity threshold (in hours) or target repository:
```bash
python3 ~/.claude/skills/ci-queue-trim/scripts/ci_queue_trim.py \
    --repo jleechanorg/worldarchitect.ai --max-age-hours 4 --cancel
```

### 5. Host & Colima Preflight (`--check-host`)
Checks local macOS host conditions that cause runner starvation or admission
lockouts:
```bash
python3 ~/.claude/skills/ci-queue-trim/scripts/ci_queue_trim.py --check-host
```
Checks:
- **Colima Sockets:** Verifies `~/.colima/_lima/_networks/user-v2/user-v2_fd.sock`
  exists and is backed by exactly 1 active `limactl usernet` process. Detects
  orphaned `usernet` PIDs that cause startup crashes (`dial unix
  user-v2_fd.sock: no such file or directory`).
- **Host Disk Space:** Checks `/System/Volumes/Data` against the 7.0 GB
  admission safety floor.

### 6. Structured JSON Output (`--json`)
Returns machine-readable JSON for scripting, subagents, or automated triage:
```bash
python3 ~/.claude/skills/ci-queue-trim/scripts/ci_queue_trim.py --json
```
Each row carries:
`run_id, name, branch, event, pr_number, pr_state, head_commit_age,
pr_updated_age, deceptive_delta, superseded, audit_incomplete, verdict,
reason`.

---

## Pre-Cancellation Refresh

Before any `gh run cancel` call, the script re-fetches each candidate's
fingerprint via `refresh_before_cancel`:

1. Re-fetch run metadata (`status`, `event`, `name`, `path`).
2. Drop the run if it is no longer `queued`, if its event shifted to
   `merge_group` / unknown, or if its workflow is now in
   `PROTECTED_WORKFLOWS`.
3. Re-fetch the PR (or branch HEAD for push events) and drop the run if the
   head SHA advanced to match the run's recorded head SHA (the supersede
   has resolved).

Runs that fail any of these checks are dropped before any mutation; the
report shows how many were dropped.

---

## Self-Healing & Remediation Recipes

### 1. Colima Sockets Stuck / Multiple `limactl usernet` PIDs
If `--check-host` reports orphaned `usernet` processes or missing sockets:
```bash
# 1. Inspect orphaned usernet processes
ps -Ao pid,command | grep '[l]imactl usernet'

# 2. Terminate orphaned PIDs (NEVER use killall)
kill -9 <PID_1> <PID_2>

# 3. Remove dead socket files
rm -f ~/.colima/_lima/_networks/user-v2/user-v2_*.sock

# 4. Restart Colima cleanly
colima start
```

### 2. Host Disk Floor Tripped (`free_disk_gb < 7.0`)
If host disk space is below 7.0 GB:
```bash
# 1. Find dead temporary repos in /private/tmp
ls -la /private/tmp/

# 2. Verify no active processes hold open file descriptors
lsof +D /private/tmp/<dir_name>

# 3. Clean up orphaned tmpdir
rm -rf /private/tmp/<dir_name>
```

### 3. Verify Self-Hosted Runner Capacity
After trimming stale runs, verify that the runner fleet is picking up active
jobs:
```bash
./doctor-runner
```
Expect **16/16 healthy** (6 Mac + 10 Linux runners executing or cycling).

### 4. Audit-Incomplete Runs
If a run is reported with `audit_incomplete=True`, the script could not
verify its PR/branch/commit at audit time. To investigate:
```bash
# Fetch the run detail directly to confirm event / status / workflow
gh api repos/<owner>/<repo>/actions/runs/<run_id>

# Verify the PR head SHA
gh api repos/<owner>/<repo>/pulls/<pr_number> | jq '.head.sha, .state'
```
Do **not** manually cancel an `audit_incomplete` run unless you have
independently confirmed the head SHA mismatch.