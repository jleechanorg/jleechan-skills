---
name: pr-babysit
description: Drive all open PRs toward /green (CI green + no merge conflicts) by fixing CI failures, and toward draft-phase quality readiness by resolving comments and running the smoke gate. CodeRabbit/Bugbot are optional advisory reviewers — surfaced for information, never a gate or a wait. Use when the user wants to nurse PRs to merge-readiness.
---

# /babysit — PR Green-Gate Babysitter

## Retained review integrations

The shared catalog preserves host-installed `/advice` and `/web-advice` integrations instead of installing them. Before invoking either, resolve its `../advice/SKILL.md` or `../web-advice/SKILL.md` relative to this package and read the existing skill. For a remote invocation, check the corresponding skill on the target host. If absent, report that integration as `UNAVAILABLE` and identify the missing package; do not invent a replacement runner, claim an approval, or treat a required gate as passed. Continue independent authorized work, but leave any dependent readiness or plan-approval gate unmet. Existing review quorum, external-disclosure authorization, and optional-review rules still apply.


## Purpose

Systematically drive all open PRs toward `/green` (CI green + no merge conflicts,
see `../pr-green-definition/SKILL.md`) plus draft-phase quality readiness
(`/es`, `/er`, `/advice`, evidence, comment resolution). For each PR:
1. Audit `/green` (gates 1-2 below) and the draft-phase quality checks (gates 5-6 below)
2. Fix any blocking failures
3. Optionally surface CodeRabbit/Bugbot feedback (gates 3-4) for information — never wait on or require them
4. Once all applicable blocking checks pass, run `/smoke` and report readiness; resolve merge authority through the shared size-tiered rule and the target repository's current contract

The retired Skeptic automation is not a current readiness gate. `/babysit`
reports readiness but never merges. Merge authorization follows the shared
size-tiered rule and the target repository's current contract.

**Note (2026-07-28):** `/green` itself is now ONLY gates 1-2 below (CI green + no
merge conflicts). Gates 5-6 (comment resolution, evidence) are draft-phase
quality gates that gate leaving DRAFT status, not `/green` — see
`../pr-green-definition/SKILL.md`. Gates 3-4 (CodeRabbit, Bugbot) are
**optional advisory reviewers** — babysit may surface their feedback for
information, but never waits on or requires them to consider a PR ready.

## Draft-Phase + `/green` Criteria

| # | Gate | Check | Counts toward `/green`? |
|---|------|-------|--------------------------|
| 1 | CI green | All GitHub Actions checks pass (no FAILURE conclusions) | Yes |
| 2 | No conflicts | `mergeable == "MERGEABLE"` | Yes |
| 3 | CR feedback | CodeRabbit latest review state | No — optional advisory, informational only |
| 4 | Bugbot feedback | cursor[bot] error-severity comments | No — optional advisory, informational only |
| 5 | Comments resolved | Zero unresolved non-nit inline review comments | No — draft-phase |
| 6 | Evidence pass | Evidence bundle exists or N/A justified | No — draft-phase |

## Execution Protocol

### Phase 1: Discover All Open PRs

```bash
gh pr list --state open --json number,title,headRefName,headRefOid,mergeable \
  --jq '.[] | "\(.number)|\(.title)|\(.headRefName)|\(.headRefOid[:12])|\(.mergeable)"'
```

### Phase 2: Audit Each PR (`/green` + Draft-Phase Check)

For each open PR, check all 6 gates:

```bash
# Gate 1: CI status
gh pr view <NUM> --json statusCheckRollup \
  --jq '[.statusCheckRollup[] | select(.conclusion == "FAILURE")] | length'

# Gate 2: Mergeable
gh pr view <NUM> --json mergeable --jq '.mergeable'

# Gate 3: CodeRabbit review
gh api repos/$GITHUB_REPOSITORY/pulls/<NUM>/reviews \
  --jq '[.[] | select(.user.login=="coderabbitai[bot]")] | last | .state'

# Gate 4: Bugbot errors
gh api repos/$GITHUB_REPOSITORY/pulls/<NUM>/comments \
  --jq '[.[] | select(.user.login=="cursor[bot]" and (.body | test("error";"i")))] | length'

# Gate 5: Unresolved comments
repo_with_owner=$(gh repo view --json nameWithOwner --jq '.nameWithOwner')
repo_owner=${repo_with_owner%%/*}
repo_name=${repo_with_owner#*/}
gh api graphql -f query='
  query($owner:String!, $name:String!, $pr:Int!) {
    repository(owner:$owner, name:$name) {
      pullRequest(number:$pr) {
        reviewThreads(first:100) {
          nodes { isResolved }
        }
      }
    }
  }
' -f owner="$repo_owner" -f name="$repo_name" -F pr=<NUM> \
  --jq '[.data.repository.pullRequest.reviewThreads.nodes[] | select(.isResolved==false)] | length'

# Gate 6: Evidence in PR body
gh pr view <NUM> --json body --jq '.body' | grep -i -E "evidence|gist|video|mp4|N/A"
```

### Phase 3: Categorize PRs

Group PRs by the four blocking gates (1, 2, 5, 6) — gates 3-4 (CodeRabbit,
Bugbot) are informational only and never affect a PR's category:
- **RED** (2+ blocking gates failing): needs code fixes
- **YELLOW** (1 blocking gate failing): needs comment resolution or evidence
- **GREEN** (all 4 blocking checks passing — `/green` gates 1-2 plus draft-phase
  quality gates 5-6): run `/smoke`, then report readiness under the current
  merge-authorization rule

### Phase 4: Fix RED PRs

For each RED PR, use subagents (Agent tool, subagent_type: copilot-fixpr) to:
1. Read the Green Gate workflow log to identify the exact failing gate
2. Fix the root cause:
   - **CI test failures**: read test output, fix code, push
   - **Design Doc Gate**: add design doc reference to PR body
   - **Lint/type errors**: fix code, push
3. Dispatch agents in parallel — one per PR or group of related PRs

Common fixes:
- Test assertion mismatch after rebase → rebase onto `origin/main`
- Missing evidence → create evidence bundle or add N/A justification
- Stale review threads → resolve via GitHub API

CodeRabbit/Bugbot feedback (gates 3-4) can be read for useful signal, but
triggering or waiting on a re-review is never required to unblock a RED PR.

### Phase 5: Fix YELLOW PRs

For each YELLOW PR:
1. **Gate 5 (unresolved comments)**: Resolve review threads
2. **Gate 6 (no evidence)**: Add evidence or N/A to PR body
3. Optionally comment `@coderabbitai all good?` to refresh CR feedback — informational only, not required

### Phase 6: Run Smoke on GREEN PRs

For PRs at all 4 blocking checks (`/green` gates 1-2 plus draft-phase quality gates 5-6):

```bash
# Trigger Green Gate workflow if no recent run
gh workflow run green-gate.yml --ref <branch> -f pr_number=<NUM>

# Trigger smoke tests via PR comment
gh pr comment <NUM> --body "/smoke"
```

Once smoke passes, report the PR as `/green` plus draft-phase-quality-complete.
Babysit itself never merges. The session that owns any merge must follow the
shared size-tiered merge rule and the target repository's current contract.

### Phase 7: Report Final Status

Print a summary table:

```
PR #<N> — age: <Xh Ym> — status: <red|yellow|green|/green>
  Blocking gates: 1=✓ 2=✓ 5=✓ 6=✓ | Advisory (informational only): CR=✓ Bugbot=✓
  Action: /green; apply the shared merge-authorization rule
```

## PR Green Loop Protocol (MANDATORY)

- **Batch all fixes** into one commit, not one per finding
- **Push once** per batch of fixes
- **CodeRabbit/Bugbot: optional advisory reviewers** — read their feedback, take what's useful; never a gate, never a wait. Dismissing or ignoring their CHANGES_REQUESTED reviews is allowed; they never block a merge.

## Subagent Dispatch Strategy

- **Independent PRs**: Dispatch one agent per PR in parallel
- **Related PRs** (same feature area): Group under one agent
- **GREEN PRs**: One agent to trigger smoke on all, then report readiness

Agent type: `copilot-fixpr` for fixing, `general-purpose` for auditing/triggering

### Phase 8: Hold Loop — Stay Alive Until All PRs Merge or Are Reported Ready

After Phase 7, if any PRs are still open, **do not exit**. Schedule a wakeup to re-check:

```python
# In /loop mode (Claude Code interactive) — fires only when REPL is idle, never interrupts work
ScheduleWakeup(
    delaySeconds=180,   # 3 min — within 5-min cache window, catches Design Doc bot commits
    prompt="<<autonomous-loop-dynamic>>",
    reason="babysit hold: re-checking gate status after Design Doc bot commits"
)
```

On each wakeup iteration, run a **lightweight status sweep** (not a full audit):

```bash
# Re-check gate status for each open PR (no skeptic dispatch — nothing to re-dispatch,
# skeptic-cron.yml was removed repo-wide; see rev-p0cc4).
for pr in $(gh pr list --repo $GITHUB_REPOSITORY --state open --json number --jq '.[].number'); do
  fail=$(gh pr view $pr --repo $GITHUB_REPOSITORY --json statusCheckRollup \
    --jq '[.statusCheckRollup[] | select((.__typename=="StatusContext" and (.state=="FAILURE" or .state=="ERROR")) or (.__typename=="CheckRun" and (.conclusion//"" | ascii_upcase | (.=="FAILURE" or .=="ERROR" or .=="TIMED_OUT"))))] | length')
  pending=$(gh pr view $pr --repo $GITHUB_REPOSITORY --json statusCheckRollup \
    --jq '[.statusCheckRollup[] | select(.__typename=="CheckRun" and (.conclusion==null or .conclusion==""))] | length')
  mergeable=$(gh pr view $pr --repo $GITHUB_REPOSITORY --json mergeable --jq '.mergeable')
  if [[ "$fail" == "0" && "$pending" == "0" && "$mergeable" == "MERGEABLE" ]]; then
    echo "PR #$pr is /green and ready — report readiness; babysit never merges. Apply the shared merge-authorization rule."
  else
    echo "PR #$pr not ready yet (failures=$fail pending=$pending mergeable=$mergeable)"
  fi
done
```

**Exit condition**: Stop scheduling wakeups when `gh pr list --repo $GITHUB_REPOSITORY --state open --json number --jq 'length'` returns `0`, or when all remaining PRs are fully reported and ready under the current merge-authorization rule. Do not keep polling PRs that have already been reported ready.

**CronCreate alternative** (non-interactive / cron-based sessions):
```python
# Guard: create at most ONE cron job per babysit session. Check CronList first.
jobs = CronList()
babysit_jobs = [j for j in jobs if "babysit" in j.get("prompt", "").lower()]
if not babysit_jobs:
    job_id = CronCreate(
        cron="*/5 * * * *",  # every 5 minutes
        # Sweep-only prompt — do NOT use "/babysit" here (that runs full 6-phase audit).
        # This fires the Phase 8 status sweep: report which open PRs are /green and
        # Report readiness under the shared merge-authorization rule. No skeptic re-dispatch.
        prompt="Run /babysit Phase 8 status sweep only: for each open PR in $GITHUB_REPOSITORY, check /green (CI + no-conflicts) and draft-phase quality status, then report PRs ready under the shared merge-authorization rule. Babysit never merges. Skip full Phase 1-7 audit.",
        recurring=True
    )
```
Use CronCreate only when NOT in an interactive `/loop` session. Delete the job with CronDelete once all PRs merge. The guard above prevents duplicate cron jobs from accumulating across repeated babysit invocations.

**Key rule: never sleep-poll inline.** The wakeup fires while the REPL is idle — it cannot interrupt a user conversation or an in-progress tool call. This is safe to leave running.

## Evidence Monitoring Protocol

When babysitting active testing or evidence generation:

1. **Poll evidence traces**: Verify that the testing framework writes traces under the task's unique `/tmp/<repo>/evidence/...` directory, as specified by `~/.codex/AGENTS.md` § Workspace and method fidelity. Confirm `.jsonl` files are non-empty.
2. **Publish durable evidence**: When the workflow requires evidence to outlive the task, use the authorized gist or GCS publication process in `~/.claude/skills/evidence-standards/SKILL.md`. Never copy capture bundles into the source repository.
3. **Testing Gap Close Integration**: If evidence bundles fail to generate (empty `.jsonl` files, missing checksums, server timeout errors, or `EvidenceSignatureGuard` rejections), immediately invoke the `/testing-gap-close` skill to harden the server lifecycle and resolve the failure.
4. **Stop task-owned processes**: If a task-owned process hangs, verify its PID still belongs to the expected task and worktree, then follow that service's cleanup owner. For local development servers, use [local-dev-server](../local-dev-server/SKILL.md) § Stopping Servers. Never kill processes by port or name, signal an unverified process group, or use broad `pkill` fallbacks.

## Anti-Patterns (BANNED)

- Polling CI status in a sleep loop — check once
- Waiting for or requiring CodeRabbit/Bugbot before pushing or reporting a PR ready — they are optional advisory reviewers only
- Resolving review threads to trigger auto-approve
- Declaring `/green` without Green Gate log verification for gates 1-2
- Reporting a PR as "looking good" after checking only mergeable — always run statusCheckRollup check first
- Running `gh pr merge` from babysit — it reports readiness only; any merge follows the shared size-tiered rule and the target repository's current contract
- Calling `sleep` inline to wait for bots — use `ScheduleWakeup` instead
- Exiting babysit after Phase 7 while PRs are still failing/pending gates — keep working them; PRs that have reached `/green` plus draft-phase-quality-complete and been reported ready are a hold-and-surface case (Phase 8), not a "keep polling forever" case — babysit does not perform merges, and its monitoring ends when readiness has been reported
