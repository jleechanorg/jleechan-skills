# ci-queue-trim — review-fix RESULTS

Branch: `codex/ci-queue-throughput-20261003`
Prior head: `db6e579` (round 4 review; superseded earlier `9671d11`).
New head: see `git rev-parse HEAD`.

This iteration addresses every P0 / P1 / P2 raised at the round-4
review, plus the cleanup at the round-5 review.

## Round-4 fixes

### `--allow-workflow` inverted to a positive allowlist

**Before**: `--allow-workflow PATH` *protected* PATH from cancellation
(extended a hard-coded safe-default set of `release.yml`, `deploy.yml`,
`publish.yml`, `tag-release.yml`).

**Now**: `--allow-workflow PATH` *enables* cancellation for PATH. The
default is an empty allowlist, which keeps every workflow — i.e. **no
workflow is cancellable out of the box**. Operators must explicitly
enumerate the exact normalized paths they consider safe to cancel.

A separate `--protect-workflow PATH` flag provides explicit protection,
independent of `--allow-workflow`. The two flags are independent.

Regressions:
- `TestNewReviewCoverage::test_arbitrary_deploy_path_kept_absent_allow`
  proves a deploy-style path stays KEEP absent `--allow-workflow`.
- `TestNewReviewCoverage::test_allowed_ci_path_cancels` proves adding
  the run's path to `--allow-workflow` makes it cancel.
- `TestNewReviewCoverage::test_allow_does_not_protect` proves
  `--allow-workflow` does NOT add protection (the dedicated
  `--protect-workflow` does).

### `--superseded-only` cancels ONLY `superseded=True`

**Before**: in `--superseded-only` mode, MERGED/CLOSED PRs whose head
still matched the run were cancelled, including for
`pull_request_target` runs.

**Now**: `--superseded-only` cancels only runs whose `head_sha` is
strictly behind the PR/branch current head (`superseded=True`). Terminal
matching heads on MERGED/CLOSED PRs KEEP. `pull_request_target` runs
(base-side) KEEP unconditionally in this mode.

Dormancy-based cancellation (current head advanced beyond the run's
`head_sha`) is preserved as a separate signal in the default mode and
flows through the same classifier path; in `--superseded-only` mode
that path is the only path that cancels.

Regression:
`TestNewReviewCoverage::test_terminal_current_sha_kept_superseded_only`
proves terminal matching heads KEEP for both `pull_request_target` and
`pull_request`, while superseded=True still cancels.

### Fresh-response validation at mutation time

`cancel_with_per_item_refresh` now refuses to cancel on any incomplete
fresh re-fetch. The candidate is **kept** (not cancelled) if:

- `data.id` does NOT equal the requested `run_id` (mismatched id).
- Any required field is missing (`event`, `head_branch`, `head_sha`,
  `path`, `pull_requests[]`, `repository`).
- `repository.{id, full_name, name}` is missing.
- `pull_requests[]` does not match the original candidate's PR
  identity (by stable numeric `repo.id`).

The cancel decision uses the **same pure `classify_run`** the audit
used — there is no separate duplicate decision logic after the
classifier. Dormancy-based cancellation propagates through the same
classifier path at mutation time; previously this was silently dropped
by separate logic.

Regressions:
- `TestNewReviewCoverage::test_malformed_fresh_response_no_cancel`
- `TestNewReviewCoverage::test_missing_repo_identity_no_cancel`
- `TestNewReviewCoverage::test_id_mismatch_in_fresh_response_no_cancel`
- `TestNewReviewCoverage::test_dormant_current_head_cancels_at_mutation`

### `_collect_inputs` requires exactly-one PR + numeric repo.id identity

**Before**: `_collect_inputs` accepted multiple PR associations and
chose the first. Identity was matched by `full_name` only. A regex-
based `_strip_ref` failed on refs containing slashes.

**Now**:
- 0 or >1 PR associations ⇒ UNKNOWN, `audit_incomplete=True`.
- Identity is verified by stable numeric `repo.id` (live
  `actions/runs/{id}.pull_requests[].head.repo` is `{id, name, url}` —
  no `full_name`).
- `_strip_ref` uses `partition('@')[0]` and works on
  `.github/workflows/release.yml@refs/heads/feature/x`.

Regressions:
- `TestNewReviewCoverage::test_exactly_one_pr_association_required_zero_or_many_yields_unknown`
- `TestNewReviewCoverage::test_live_shaped_pull_request_identity_red_and_green`
- `TestNewReviewCoverage::test_strip_ref_handles_slash_in_ref`

## Round-6 regression fix — immutable committer timestamp

The root live dryrun revealed that `fetch_pr_record` was substituting
`head.repo.pushed_at` (which bumps on every repo push, including
unrelated branches) and `PR.updated_at` (which bumps on every bot
comment) for the actual head-commit committer timestamp. All unrelated
candidates showed `1.1m` head-commit age because the repository push
shared one `pushed_at`. The original installed tool already fetched the
real committer date — restored.

`fetch_pr_record` now:
- Calls `GET repos/{head.repo.full_name}/commits/{head.sha}` and
  extracts `commit.committer.date` as `head_commit_date`.
- Leaves `head_commit_date` absent if that endpoint fails (never
  substitutes `pushed_at`, `updated_at`, or run age).
- Stores `updated_at` separately on the PR record for reporting only
  (the `pr_updated_age` audit row field).

In normal mode, an absent `head_commit_date` → KEEP incomplete — the
classifier cannot trust a committer timestamp it cannot verify. In
`--superseded-only` mode, the supersede signal alone cancels; the
committer timestamp is not required.

Regressions:
- `TestNewReviewCoverage::test_old_head_uses_real_committer_date_not_pr_or_repo_activity`
  proves recent `updated_at` AND recent `head.repo.pushed_at` do NOT
  inflate the head-commit age. The actual committer date wins.
- `TestNewReviewCoverage::test_commits_lookup_failure_unknown_keep_in_normal_mode`
  proves an absent committer timestamp yields KEEP incomplete, never
  a substituted dormancy cancel.
- `TestNewReviewCoverage::test_superseded_only_operates_without_committer_timestamp`
  proves `--superseded-only` cancels on the supersede signal alone
  even without a committer timestamp.

The exact PR-number identity guard from round-5 (number must match
the requested `pr_number`) is preserved.

## Round-5 cleanup

- Removed unused `_build_row` helper.
- Removed unused `FIXED_NOW_FALLBACK` constant with a hardcoded
  `2026-01-15` timestamp (used as a placeholder elsewhere).
- Removed unused `run_cmd_fn` parameter from
  `cancel_with_per_item_refresh`; tests use
  `mock.patch.object(ci_queue_trim, "run_cmd", ...)` directly.
- Strict `data.id == requested run_id` equality on the fresh re-fetch
  (no longer accepts any truthy `data.get("id")`).

## Carried forward from prior round

- **P0 — Fork-A-branch binds fork-B PR**: PR association uses only
  `actions/runs/{id}.pull_requests`. No branch-name guessing.
- **P1 — Head SHA / merge ref semantics**: `PR.head.sha` is the head
  branch tip; `merge_commit_sha` is separate and is never used for
  supersede comparison.
- **P1 — `pull_request_target` uses base-side semantics**: tip advance
  on the PR is NOT a supersede signal; only MERGED/CLOSED cancels.
- **P1 — fetch failure ⇒ KEEP incomplete**: `metadata_complete=False` is
  propagated through the classifier and never reaches the CANCEL
  branch. `get_queued_runs` returns `None` on failure.
- **P1 — Per-item pre-cancellation refresh**: per-item re-fetch +
  re-classify right before each `gh run cancel`. State changes
  between candidates drop the later candidate.

## Test results

```
$ python3 -m pytest .claude/skills/ci-queue-trim/tests/test_ci_queue_trim.py -v
============================== 30 passed in 0.07s ==============================
```

Coverage map:

| Scenario | Tests |
|---|---|
| Classifier semantics (pull_request, pull_request_target, push, merge_group, unknown) | 6 |
| PR association (two forks same branch, missing association, push vs branch, exactly-one, identity red/green) | 5 |
| API failure handling (detail fetch, queue fetch) | 2 |
| Per-item refresh (real gh cancel IDs, state advance, fresh-id mismatch, malformed fresh, missing repo identity) | 5 |
| Workflow protection (allow, protect, default deploy, default release) | 5 |
| Round-4 review coverage (allow semantics, superseded-only, dormancy, _strip_ref, exactly-one) | 11 |
| Backwards-compatibility row shape | 1 |

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

## Final contract correction — 2026-10-04 review follow-up

This section supersedes contradictory current-behavior claims above; earlier
round reports and their historical test counts remain intact.

- Every mode requires proven supersession and explicit workflow opt-in.
  Commit age and MERGED/CLOSED state alone never authorize cancellation.
  Current-head work stays queued; pull_request_target always stays queued.
- --superseded-only is a compatibility flag. Both modes can establish
  supersession without a commit timestamp; missing age is reporting-only.
  --max-age-hours is a report threshold, passed through audit and refresh.
- --dry-run overrides --cancel. Queue-fetch failure returns nonzero.
- Before mutation the fresh run ID must equal the requested ID; event,
  head_sha and path are nonempty and status is queued. Repository identity
  requires id or full_name, and a supplied full_name must match the target.
  PR runs additionally require exactly one association, exact PR number,
  matching nonempty head.repo.id, and equal nonempty IDs across association
  base.repo, run.repository, and fetched PR base.repo. Push runs require a
  branch-head lookup. repository.name is not required.
- PR number plus base repository establishes PR identity. A head ref is not
  an alternative identity; the historical association head SHA must not be
  required to equal the current PR tip, because supersession changes it.
- --json emits exactly one stdout object (stats and runs). Human messages
  go to stderr in audit, cancellation, dry-run, host-check and error modes.
  Cancellation acceptance remains an asynchronous result reported on stderr.
- The old test_dormant_current_head_cancels_at_mutation name is superseded
  by test_obsolete_push_cancels_at_mutation; it tests obsolete push heads.

Linux verification at this final source state: 42 focused tests passed;
26 installer tests passed. The two new regression methods fail against the
preceding source with six base-identity assertion failures and ten JSON
parse errors, then pass with this correction. Commands:

```bash
python3 .claude/skills/ci-queue-trim/tests/test_ci_queue_trim.py
python3 -m unittest discover -s tests -p test_installer.py
```

Raw receipts: /tmp/runner-approval-20261004-queue/fix-round3-tests.txt,
fix-round3-installer.txt, and fix-round3-red.txt on Linux. No live
cancellation, installed-skill change, service change or runtime-config
change was performed by this review-fix lane.

## Final branch identity and portable guidance correction — 2026-10-04

Push branch lookup now encodes the complete branch name as one URL path
component and requires the returned branch name to match exactly. Missing
or mismatched names keep the run incomplete at both audit and refresh.
Regressions cover legal names containing #, percent escapes and slashes,
matching and superseded SHAs, and missing or wrong returned names.

Inspected every remaining API interpolation: repository paths use the
operator target or GitHub repository identity; run IDs and PR numbers come
from numeric API fields; commit lookups use the API head SHA and only supply
age reporting. No other endpoint inserts an arbitrary branch/ref name.

Removed exported process-kill, socket-glob deletion, recursive cleanup,
and service-start recipes. Host observations now lead only to read-only
diagnosis under the owning service/disk instructions. Runner verification
requires resolving the actual ez-gh-actions repository and its contract;
this portable package does not supply a relative doctor-runner command.

Linux focused suite: 43 tests pass. Installer suite: 26 tests pass.
Raw receipts: /tmp/runner-approval-20261004-queue/fix-round4-tests.txt,
fix-round4-installer.txt, fix-round4-red.txt and fix-round4-live-read.txt.
No live cancellations or runtime changes were made.

Nonblocking follow-ups retained from pair-4 review: cancellation failures
currently exit zero with acceptance totals on stderr; JSON contains audit
results rather than cancellation outcomes; queue limit truncation is not
reported; repository full-name comparison is case-sensitive and safely
skips mismatches; one missing-repository test also hits base-identity checks.
These observations are not claims that those follow-ups were implemented.


## 2026-10-04: run identity and ambiguous push namespace correction

The shared run fetch now rejects missing or mismatched response IDs and
missing/mismatched repository identity before both audit classification and
pre-cancellation refresh. It requires repository.id and an exact requested
repository.full_name. The duplicate mutation-only validation was removed.

Push runs now always remain KEEP with audit_incomplete=true. The retained
REST run metadata does not establish the original branch-versus-tag namespace;
a branch-name match or present-day tag absence cannot exclude a historical
tag push, including a deleted tag. Earlier push-cancellation statements and
branch-encoding evidence above are historical and superseded by this limitation.
The unused branch lookup was removed; neither audit nor refresh fetches refs
or tries PR association for push runs. Explicit PR supersession remains enabled.
Research provenance: /tmp/runner-opt-20261003/push-ref-research.md (parent review).

Regressions exercise actual audit and refresh with invalid run/repository
identity, current/stale push-looking records, same-name ref ambiguity, deleted
tag-looking names, protected main, and both compatibility modes. No live
cancellation, service, or runtime configuration change was performed.
Authentic pre-fix receipt: /tmp/runner-opt-20261003/queue-identity-namespace-red.log
(43 tests, 28 failing subcases). Final focused suite: 43 tests pass; installer suite: 26 tests pass.
Receipts: /tmp/runner-opt-20261003/queue-identity-namespace-green.log and
/tmp/runner-opt-20261003/queue-identity-namespace-installer.log.
git diff --check passes. These are isolated fixture tests, not live
cancellation proof or current-head production activation.


## Raw cancellation-input validation correction (2026-10-04)

Shared run fetching now validates raw identity and association structure
before normalization. Run IDs, PR numbers, and all run/association/fetched-PR
repository IDs must be positive JSON integers, excluding booleans and floats.
Required run strings include the branch, preventing missing detail metadata
from bypassing branch protection. PR events require exactly one raw, valid
association; malformed entries cannot shrink an ambiguous array to one.
Fetched PR identity and head SHA are validated at their input owner too.
Non-PR events do not normalize irrelevant PR associations; push runs remain
KEEP incomplete.

New offline audit-and-refresh regressions reproduced 68 assertion failures
and 36 parsing errors against the preceding implementation before the fix.
These fixtures prove deterministic input handling; no live cancellation,
deployment, or installed-skill activation is claimed.
