---
name: ci-queue-trim
description: >
  Audit and trim queued GitHub Actions CI workflow runs for dormant or merged PRs.
  Solves the deceptive PR.updatedAt pitfall by evaluating actual head commit timestamps
  and checking PR merge state. Includes Colima socket and host disk health preflights.
type: skill
scope: global
owner: $USER
version: 1.0.0
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

Use this skill when GitHub Actions self-hosted or cloud runner queues become backlogged with queued runs from stale, dormant, or already-merged pull requests.

## The Core Pitfall: Naive `PR.updatedAt` vs `committedDate`

When filtering PRs by activity, querying GitHub API's `PR.updatedAt` is **fundamentally deceptive**:
- Automated bots (e.g. merge queues, label synchronizers, automated status comments, rebase checks) constantly update the `updatedAt` timestamp on pull requests.
- A PR whose code has not been touched in 10–18 days will frequently show an `updatedAt` of "2 minutes ago".
- **The Ground Truth Rule**: Always check `commits[-1].committedDate` (the author's actual code push timestamp) against the inactivity window (default: 2 hours). If no new code was pushed within the window, the PR is dormant and its queued CI runs should be cancelled to free up runner slots for active developers.
- **Orphaned Runs Rule**: Any queued run belonging to a PR with `state == "MERGED"` or `state == "CLOSED"` is an orphaned zombie and must be cancelled immediately.
- **Protected Branch Rule**: Runs on `main`, `master`, `production`, `staging`, or `release` branches are protected and never cancelled automatically.

---

## Tooling & Command Syntax

The skill includes a pre-built, standalone Python helper at:
`/Users/jleechan/.claude/skills/ci-queue-trim/scripts/ci_queue_trim.py`

### 1. Dry-Run Audit (Default)
Inspects the queue, maps each run to its PR, calculates head commit age vs `updatedAt`, and flags cancel candidates without cancelling anything:
```bash
python3 ~/.claude/skills/ci-queue-trim/scripts/ci_queue_trim.py
```

### 2. Execute Cancellations
Cancels all queued runs belonging to dormant PRs (>2h commit age) and merged/closed PRs:
```bash
python3 ~/.claude/skills/ci-queue-trim/scripts/ci_queue_trim.py --cancel
```

### 3. Customize Threshold and Target Repo
Change the inactivity threshold (in hours) or target repository:
```bash
python3 ~/.claude/skills/ci-queue-trim/scripts/ci_queue_trim.py --repo jleechanorg/worldarchitect.ai --max-age-hours 4 --cancel
```

### 4. Host & Colima Preflight (`--check-host`)
Checks local macOS host conditions that cause runner starvation or admission lockouts:
```bash
python3 ~/.claude/skills/ci-queue-trim/scripts/ci_queue_trim.py --check-host
```
Checks:
- **Colima Sockets:** Verifies `~/.colima/_lima/_networks/user-v2/user-v2_fd.sock` exists and is backed by exactly 1 active `limactl usernet` process. Detects orphaned `usernet` PIDs that cause startup crashes (`dial unix user-v2_fd.sock: no such file or directory`).
- **Host Disk Space:** Checks `/System/Volumes/Data` against the 7.0 GB admission safety floor.

### 5. Structured JSON Output (`--json`)
Returns machine-readable JSON for scripting, subagents, or automated triage:
```bash
python3 ~/.claude/skills/ci-queue-trim/scripts/ci_queue_trim.py --json
```

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
After trimming stale runs, verify that the runner fleet is picking up active jobs:
```bash
./doctor-runner
```
Expect **16/16 healthy** (6 Mac + 10 Linux runners executing or cycling).
