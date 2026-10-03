---
name: ci-queue-trim
description: >
  Audit and trim queued GitHub Actions CI workflow runs whose head SHA is
  obsolete or whose PR has landed. PR association comes from
  `actions/runs/{id}.pull_requests` (the only authoritative pointer);
  branch names that collide between forks MUST NOT cross-bind runs to a
  PR. Event semantics split pull_request from pull_request_target (the
  latter uses base-side SHA, so a tip advance is NOT a supersede signal)
  and merge_group / unknown events skip the generic stale-head comparison.
  Per-item re-validation right before each `gh run cancel` catches
  concurrent state advances. Workflow importance is decided by an explicit
  configured allowlist with safe release / deploy defaults, never by fuzzy
  substring heuristics.
type: skill
scope: global
owner: $USER
version: 1.2.0
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

Use this skill when GitHub Actions self-hosted or cloud runner queues become backlogged with queued runs whose head SHA is no longer current or whose PR has already landed.

## The Pitfalls Resolved at Audit Time

### 1. Deceptive `PR.updatedAt` (bots touch it constantly)
When filtering PRs by activity, `PR.updatedAt` is **fundamentally deceptive**:
- Automated bots (merge queues, label synchronizers, automated status
  comments, rebase checks) constantly touch `updatedAt`.
- A PR whose code has not been touched in 10–30 days frequently shows
  `updatedAt` of "2 minutes ago".
- The script uses the **immutable head-commit committer timestamp** as
  the source of truth — fetched from
  `GET repos/{head.repo.full_name}/commits/{head.sha}` via
  `commit.committer.date`. NEVER substituted with `pushed_at`,
  `updated_at`, or run age.
- `PR.updated_at` is reported separately for operator visibility only
  (the `pr_updated_age` field); it is NOT used for dormancy decisions.
- If the commits endpoint fails, the run is KEEP incomplete. The
  classifier cannot trust a committer timestamp it cannot verify.

### 2. Superseded runs (`run.head_sha` ≠ PR/branch current head)
A run can be queued against an older SHA even though the PR has since
advanced. The script compares `run.head_sha` against the current head SHA
to detect this without false-positive dormancy cancellations.

- `PR.head.sha` is the **head branch tip SHA** — NOT the merge ref.
  `merge_commit_sha` is a separate field and must NOT be used for
  supersede comparison.
- For `pull_request` events: comparison ref is `PR.head.sha`.
- For `pull_request_target`: base-side semantics. The run's `head_sha`
  is the BASE branch SHA, not the PR head SHA. Tip advances on the PR
  are NOT proven supersede — keep unless the PR is MERGED/CLOSED.
- For `push` events: comparison ref is the branch HEAD SHA.
- For `merge_group` and any unsupported event: never apply the generic
  stale-head comparison.

### 3. Lookup failure (PR / commit / run detail unknown)
If the audit cannot verify the PR head, the head commit date, or the run
detail, the run is kept with `audit_incomplete=True`. The tool NEVER
substitutes the run's age for a missing head-commit age.

A failed `gh run list` (queue fetch) is propagated as
`stats["queue_fetch_failed"]=True`, NOT silently turned into a healthy
empty success.

### 4. PR association — branch names that collide between forks
Branch-name lookup is **never** used to bind a run to a PR. The script
reads `actions/runs/{id}.pull_requests` (the only authoritative pointer).
Two forks pushing a branch named `feature/x` will not cross-bind the run
to the wrong PR.

- The audit requires **exactly one** PR association (0 or >1 ⇒ UNKNOWN,
  `audit_incomplete=True`). There is no "pick the first" fallback.
- Identity between the run's PR pointer and the fetched `pulls/{n}`
  record is verified by the stable **numeric `repo.id`**. The live
  shape of `actions/runs/{id}.pull_requests[].head.repo` is
  `{id, name, url}` (no `full_name`); requiring `full_name` would mark
  every real run unknown. The `pulls/{n}.head.repo` record carries
  `{id, full_name, name, ...}` — match by `id`.
- Absent or mismatched `repo.id` ⇒ UNKNOWN.

### 5. Per-item refresh before cancellation
Before every individual `gh run cancel`, the script re-fetches the run
record and the exact PR (or branch HEAD for push events), re-runs the
**same pure classifier** the audit used, and only cancels if the verdict
is still CANCEL. If state moved on between audit time and mutation
time, the candidate is dropped.

The fresh response is validated before any mutation:
- `data.id` MUST equal the requested `run_id` (mismatched id ⇒ drop,
  even if the rest looks valid).
- Required fields (`event`, `head_branch`, `head_sha`, `path`,
  `pull_requests[]`, `repository`) MUST be present.
- `repository.{id, full_name, name}` MUST be present.
- If any of the above is missing, the candidate is **kept** — the
  re-fetch is treated as incomplete and `gh run cancel` is NOT
  invoked.

Dormancy-based cancellation (current head advanced beyond the run's
`head_sha`) is preserved as a separate `superseded=True` signal and
flows through the same classifier path at mutation time. There is no
separate decision logic after the classifier.

## Protected Branches and Workflows

- **Protected branches** (never cancelled automatically):
  `main`, `master`, `production`, `staging`, `release`, `deploy`.
- **Workflow cancellation is opted-in via `--allow-workflow PATH`**
  (repeatable). The default is an empty allowlist, which keeps every
  workflow — i.e. **no workflow is cancellable out of the box**. Operators
  must explicitly enumerate the exact normalized workflow paths they
  consider safe to cancel.
- **Workflow protection is opt-in via `--protect-workflow PATH`** (repeatable).
  `--allow-workflow` enables cancellation; `--protect-workflow` protects
  even if the same path is in `--allow-workflow`. The two flags are
  independent.
- The `@<ref>` suffix on a workflow path (e.g.
  `release.yml@refs/heads/feature/x`, `deploy.yml@v2`) is stripped
  before matching via `partition('@')[0]` — refs containing slashes are
  preserved.
- Reusable workflows invoked via `workflow_call` are protected by
  **event semantics**, not by fuzzy name matching.

---

## Tooling & Command Syntax

The skill includes a pre-built, standalone Python helper. Resolve the
skill root via the standard Claude home convention and substitute in
the commands below:

```bash
"${CLAUDE_HOME:-$HOME/.claude}/skills/ci-queue-trim/scripts/ci_queue_trim.py"
```

This resolves the helper under the active Claude home on both Linux and macOS.

### 1. Dry-Run Audit (Default)
Inspects the queue, classifies each run via the pure classifier, and
prints cancel candidates without cancelling anything:
```bash
python3 ~/.claude/skills/ci-queue-trim/scripts/ci_queue_trim.py
```

### 2. Execute Cancellations
Each candidate is re-fetched and re-classified immediately before its
`gh run cancel` call:
```bash
python3 ~/.claude/skills/ci-queue-trim/scripts/ci_queue_trim.py --cancel
```

### 3. Superseded-Only Mode (Conservative)
Cancels ONLY runs whose head SHA is **proven obsolete** (`superseded=True`).
Terminal matching heads on `MERGED`/`CLOSED` PRs are KEPT.
`pull_request_target` runs (base-side) are KEPT unconditionally in this
mode — a tip advance on the PR is not a proven supersede. Dormancy-based
cancellations (current head advanced beyond the run's `head_sha`) are
disabled in this mode. Recommended for first-time operators who want
only the strictest proven-obsolete criterion:
```bash
python3 ~/.claude/skills/ci-queue-trim/scripts/ci_queue_trim.py \
    --superseded-only --cancel
```

### 4. Enable Cancellation for Specific Workflows
`--allow-workflow PATH` (repeatable) opts a workflow INTO cancellation.
Default is empty (no workflow cancellable). Use `--protect-workflow PATH`
to also keep a path safe even if it was added to the allowlist.
```bash
python3 ~/.claude/skills/ci-queue-trim/scripts/ci_queue_trim.py \
    --allow-workflow .github/workflows/ci.yml \
    --allow-workflow .github/workflows/lint.yml@v2 \
    --protect-workflow .github/workflows/ci.yml \
    --cancel
```

### 5. Customize Threshold and Target Repo
```bash
python3 ~/.claude/skills/ci-queue-trim/scripts/ci_queue_trim.py \
    --repo jleechanorg/worldarchitect.ai --max-age-hours 4 --cancel
```

### 6. Host & Colima Preflight (`--check-host`)
Checks local macOS host conditions that cause runner starvation or
admission lockouts:
```bash
python3 ~/.claude/skills/ci-queue-trim/scripts/ci_queue_trim.py --check-host
```
- **Colima Sockets:** Verifies `~/.colima/_lima/_networks/user-v2/user-v2_fd.sock`
  exists and is backed by exactly 1 active `limactl usernet` process.
- **Host Disk Space:** Checks `/System/Volumes/Data` against the 7.0 GB
  admission safety floor.

### 7. Structured JSON Output (`--json`)
Returns machine-readable JSON for scripting, subagents, or automated
triage:
```bash
python3 ~/.claude/skills/ci-queue-trim/scripts/ci_queue_trim.py --json
```
Each row carries:
`run_id, name, branch, event, pr_number, pr_state, head_commit_age,
pr_updated_age, deceptive_delta, superseded, audit_incomplete, verdict,
reason`. `head_commit_age` is the actual immutable committer-timestamp
age (the dormancy source of truth). `pr_updated_age` is the PR
`updated_at` age, reported for visibility only — not used for
decisions.

---

## Self-Healing & Remediation Recipes

### 1. Colima Sockets Stuck / Multiple `limactl usernet` PIDs
If `--check-host` reports orphaned `usernet` processes or missing sockets:
```bash
ps -Ao pid,command | grep '[l]imactl usernet'
kill -9 <PID_1> <PID_2>
rm -f ~/.colima/_lima/_networks/user-v2/user-v2_*.sock
colima start
```

### 2. Host Disk Floor Tripped (`free_disk_gb < 7.0`)
```bash
ls -la /private/tmp/
lsof +D /private/tmp/<dir_name>
rm -rf /private/tmp/<dir_name>
```

### 3. Verify Self-Hosted Runner Capacity
After trimming stale runs:
```bash
./doctor-runner
```
Expect **16/16 healthy** (6 Mac + 10 Linux runners executing or cycling).

### 4. Audit-Incomplete Runs
If a run is reported with `audit_incomplete=True`, the script could not
verify its PR/branch/commit at audit time. To investigate:
```bash
gh api repos/<owner>/<repo>/actions/runs/<run_id> | jq '.event, .head_sha, .pull_requests'
gh api repos/<owner>/<repo>/pulls/<pr_number> | jq '.head.sha, .state'
```
Do **not** manually cancel an `audit_incomplete` run unless you have
independently confirmed the head SHA mismatch.

---

## Architecture

The script is structured around one **pure classifier** (`classify_run`)
that consumes pre-fetched facts and returns a `Classification` namedtuple
(`verdict, superseded, audit_incomplete, reason, pr_state`):

- `audit_queue` fetches each run's record + the exact PR (via the run
  detail's `pull_requests` array) + the branch HEAD for push events,
  then calls `classify_run` once per run.
- `cancel_with_per_item_refresh` re-runs the same fetch + classifier
  pipeline per candidate immediately before each `gh run cancel`.

Because the same classifier is reused, audit-time verdicts and
pre-mutation verdicts cannot drift.