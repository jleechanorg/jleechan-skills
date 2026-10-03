# ci-queue-trim — review-fix RESULTS

Branch: `codex/ci-queue-throughput-20261003`
Prior head: `9671d11` (the version the reviewer flagged).
New head: see `git rev-parse HEAD`.

This iteration addresses every P0 / P1 / P2 raised at `9671d11`.

## P0 — Fork-A-branch binds fork-B PR

**Before**: bulk `branch_to_pr` was keyed by `head.ref`, so two forks
pushing a branch named `feature/x` could cross-bind each other's PR.

**Now**: PR association is the single source of truth
`actions/runs/{id}.pull_requests` (the authoritative pointer). The audit
follows ONLY the PRs the run detail explicitly associates with that run;
no branch-name guessing. Fork PRs use `PR.head.sha` (the head branch tip,
NOT the merge ref) for the comparison ref. Push events never search for a
PR at all. Ambiguous or missing association → KEEP UNKNOWN with
`audit_incomplete=True`.

Regression: `TestPRAssociation::test_two_forks_same_branch_identity_does_not_cross_bind`
plus `test_fork_pr_with_unknown_association_is_kept_unknown` and
`test_push_event_does_not_bind_arbitrary_pr_via_branch`.

## P1 — Head SHA / merge ref semantics

`PR.head.sha` is the head branch tip, NOT the merge ref. `merge_commit_sha`
is a separate field and must not be used for supersede comparison. Code now
compares `run.head_sha` to `PR.head.sha` for `pull_request` and to branch
HEAD for `push`. Doc corrected.

Regression: `TestClassifierSemantics::test_pull_request_supersede_uses_pr_head_sha_tip_not_merge_ref`.

## P1 — `pull_request_target` uses base-side semantics

`pull_request_target` runs execute on the BASE branch SHA. A tip advance
on the PR is NOT a proven supersede signal. Only MERGED/CLOSED cancels;
otherwise KEEP.

Regression: `TestClassifierSemantics::test_pull_request_target_keeps_unless_proven`.

## P1 — fetch_run_details / queue fetch failure → KEEP

Previously, `fetch_run_details` failure could still produce a CANCEL via
fallback to queued-list fields, and a failed queue fetch was silently
turned into an empty success.

**Now**:
- `fetch_run_details` failure sets `metadata_complete=False` → the
  classifier returns KEEP with `audit_incomplete=True` before any CANCEL
  branch is reached.
- `get_queued_runs` returns `None` on failure; `audit_queue` reports
  `stats["queue_fetch_failed"]=True` and never produces CANCEL verdicts.

Regression: `TestAPIFailureHandling::test_run_detail_fetch_failure_marks_incomplete_and_keeps`
and `test_queue_fetch_failure_does_not_become_healthy_empty`.

## P1 — Per-item pre-cancellation refresh

Previously, `refresh_before_cancel` batch-fetched all candidates and then
cancelled in a separate pass, racing on the gate.

**Now**: `cancel_with_per_item_refresh` re-fetches the run AND its exact
PR (or branch HEAD) immediately before that single mutation. The candidate
is cancelled iff the freshly-re-fetched classifier still says CANCEL. The
function calls the SAME pure `classify_run` that `audit_queue` uses.

Regression: `TestPerItemRefresh::test_state_advance_between_first_and_second_cancel_drops_later`
proves a state change between two cancels drops the second candidate.

Regression: `TestPerItemRefresh::test_real_eligible_cancellation_executes_gh_cancel_with_exact_id`
proves `gh run cancel <id>` receives exactly the eligible IDs and nothing
else.

## P2 — Workflow protection defaults + `--allow-workflow`

**Before**: `PROTECTED_WORKFLOWS` was an empty set, so arbitrary
deploy/release workflows could be cancelled out of the box.

**Now**: `DEFAULT_PROTECTED_WORKFLOWS = {release.yml, deploy.yml,
publish.yml, tag-release.yml}`. The `@<ref>` suffix on a workflow path
(e.g. `release.yml@main`, `deploy.yml@v2`) is stripped before matching.
Operators add additional paths with `--allow-workflow PATH` (repeatable).

Regressions:
- `TestWorkflowProtection::test_release_yml_at_main_is_protected_by_default`
- `TestWorkflowProtection::test_deploy_yml_at_ref_is_protected_by_default`
- `TestWorkflowProtection::test_allow_workflow_cli_flag_extends_protection`
- `TestWorkflowProtection::test_protected_branch_main_preserved`

## P2 — `committedDate` ≠ push time

Doc and the code now state explicitly: `committedDate` is the author's
commit timestamp, which precedes the push. Push time is later and is
reflected by comparing `run.head_sha` against the PR/branch current head.

## Corrected / removed claims from the prior RESULTS.md

- Dropped: "PR.head.sha is the **merge ref** inside the base repo" — that
  was incorrect. It is the head branch tip; `merge_commit_sha` is separate.
- Dropped: the fork test asserting SCENEWAL of a fork-PR run on a
  different fork head — replaced by the no-cross-bind test.
- Updated: supersede comparison is now `run.head_sha` vs `PR.head.sha`
  (head branch tip) for `pull_request`, and `run.head_sha` vs branch HEAD
  for `push`.
- Updated: `pull_request_target` now KEEPs unless MERGED/CLOSED
  (base-side semantics).
- Updated: `PROTECTED_WORKFLOWS` is non-empty by default and contains
  the safe release / deploy allowlist.

## Test results

```
$ python3 -m pytest .claude/skills/ci-queue-trim/tests/test_ci_queue_trim.py -v
============================== 18 passed in 0.06s ==============================
```

Coverage map:

| Scenario | Tests |
|---|---|
| Classifier semantics (pull_request, pull_request_target, push, merge_group, unknown) | 6 |
| PR association (two forks same branch, missing association, push vs branch) | 3 |
| API failure handling (detail fetch, queue fetch) | 2 |
| Per-item refresh (real gh cancel IDs, state advance) | 2 |
| Workflow protection (release.yml@main, deploy.yml@v2, --allow-workflow, protected branch) | 4 |
| Backwards-compatibility row shape | 1 |

## Code size

Script: `849` lines (down from `957`). The `classify_run` function is a
single pure classifier reused by `audit_queue` and
`cancel_with_per_item_refresh`. Tests: `613` lines.

## Operator safety constraints observed

- No live cancellations executed.
- No installed-file changes (`~/.claude/...`).
- No `.env` / secrets reads.
- No `git add -A`.
- No merges or force pushes.
- Commit on the existing `codex/ci-queue-throughput-20261003` branch;
  push (non-force) after this commit.

## Out-of-scope follow-ups

- Live deploy / canary run on `jleechanorg/worldarchitect.ai` from Linux
  and Mac (root to perform after the seed lands).
- Populate additional `--allow-workflow` entries with the operator's
  known safe test / check / lint paths.