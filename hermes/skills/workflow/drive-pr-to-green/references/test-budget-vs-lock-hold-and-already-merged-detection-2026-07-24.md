# Test-budget-vs-lock-hold fix + already-merged-by-automation detection

Verified 2026-07-24, $GITHUB_REPOSITORY PRs [#8462](https://github.com/$GITHUB_REPOSITORY/pull/8462) + [#8544](https://github.com/$GITHUB_REPOSITORY/pull/8544). Two distinct failure modes that v2.5.0–v2.5.10 did not cover; both surfaced in the same session.

## (a) Test-budget-vs-lock-hold failure pattern

**Symptom.** CI core-mvp-3 reports `test_bq_logging_schema_migration.py::test_startup_schema_migration_uses_shared_migration_lock` FAILED with `assert []` on `inserted_rows`. The PR's production code tightened `_PAYLOADS_SCHEMA_RETRY_BUDGET_S` to 0.5s so a degraded replica cannot hold a request-path insert for longer. The test holds `_migration_lock` for **5 seconds** (`release_migration.wait(timeout=5.0)`) to verify the request path *truly* blocks on the lock. After 0.5s, the request-path writer's `_lock_before_deadline(retry_deadline)` returns `not acquired`, the writer logs "wall-clock budget exceeded", and falls back to disk-mirror (no BQ insert). The test then asserts `inserted_rows` and fails.

**Same-test-name-rule check (verified locally in a clean worktree at PR head):**

1. **Same test name:** `$PROJECT_ROOT/tests/test_bq_logging_schema_migration.py::test_startup_schema_migration_uses_shared_migration_lock` — same name on both branches.
2. **Same assertion:** `assert inserted_rows` — same line.
3. **Same file at the same commit:** `$PROJECT_ROOT/tests/test_bq_logging_schema_migration.py` exists on both `origin/main` and PR head; this particular test was added in the PR.
4. **Explicit same-SHA reproduction on `origin/main` HEAD:** `python3 -m pytest $PROJECT_ROOT/tests/test_bq_logging_schema_migration.py::test_startup_schema_migration_uses_shared_migration_lock` on a `git checkout origin/main -- <files>` worktree → **3/3 PASS in 0.34s, 0.37s, 0.42s** (the test only takes 0.4s because the lock-acquire path is fast in isolation). On the PR head (clean worktree, before any fix) → **3/3 FAIL in 2.92s, 3.40s, 3.54s**. Real PR regression.

**Fix (verified on PR #8462, commit `e2253af7e1`):** monkeypatch the budget wider IN THE TEST only. Production code keeps the 0.5s budget; the test widens it to a value that comfortably exceeds the 5s lock hold so the test can verify what it was designed to verify.

```python
def test_startup_schema_migration_uses_shared_migration_lock(  # noqa: PLR0915
    monkeypatch,
):
    real_lock = threading.Lock()
    monkeypatch.setattr(bq_logging, "_migration_lock", real_lock)
    # ... other monkeypatches ...

    # The shared retry budget defaults to 0.5s so a degraded replica cannot
    # hold a request-path insert for longer; this test deliberately holds the
    # migration lock for up to 5s to verify the request path *truly* blocks
    # on it, so we widen the budget to comfortably exceed that 5s wait.
    monkeypatch.setattr(bq_logging, "_PAYLOADS_SCHEMA_RETRY_BUDGET_S", 10.0)

    # ... test body unchanged ...
    assert release_migration.wait(timeout=5.0), "migration release timed out"
    # ... rest of the test ...
```

**Why this is the right fix, not a budget relaxation.** The 0.5s production budget is a real correctness invariant (a degraded replica cannot hold a request-path insert for >0.5s). Relaxing it to 5s to satisfy one test would silently weaken production behavior. Widening the budget in the test preserves the invariant AND lets the test verify the lock semantics the test was written to verify. The pattern generalizes: any test that holds a shared resource longer than a new production timeout/budget needs the budget widened in the test, not loosened in production.

**Generalization recipe (any timeout/budget + lock-hold test combination):**

1. Identify the new production budget/timed-out value introduced by the PR (grep for `_TIMEOUT = \|_BUDGET = \|_LIMIT = \|_DEADLINE = ` in the diff).
2. Identify any test in the diff that holds a shared resource for longer than that budget.
3. Add `monkeypatch.setattr(<module>, "<CONSTANT>", <value comfortably above test's resource hold>)` to the test setup. Document the value choice in a comment.
4. Local verification: `python3 -m pytest <test> 3>&1` should be 3/3 pass on the PR head.
5. Same-test-name-rule check on `origin/main`: `git checkout origin/main -- <test file> && python3 -m pytest <test>` — should be 3/3 pass (proving the test was always passing before the budget regression).

**Don't fall into:** "The test is flaky, just re-run" — this dismisses a real PR regression. The test is deterministic; the failure is reproducible. The PR introduced the budget that broke the test.

**Don't fall into:** "Loosen the production budget to make the test pass" — this silently weakens production. The budget is a real invariant; the test should widen the budget, not production.

## (b) Already-merged-by-automation detection during rebase-onto-new-main

**Symptom.** Mid-session, after rebase-onto-new-main for PR #8544 (PR was 7 commits behind main, missing the new `scripts/tests/test_local_sh_agy_no_optout.sh` referenced by `.github/workflows/test.yml`), the rebase produced multiple conflicts in `$PROJECT_ROOT/world_logic.py` and `$PROJECT_ROOT/tests/test_godmode_directive_lifecycle_events.py`. While I was resolving the conflicts, the `git diff origin/main...HEAD --stat` returned **empty** — meaning the PR's commits had zero net effect vs the new main HEAD.

**Detection recipe (5 seconds):**

```bash
# 1. After rebase (or any time you're about to push a PR's branch):
git diff origin/main...HEAD --stat

# 2. If empty (or near-empty — only the docs/loc-baseline commit):
gh api repos/OWNER/REPO/pulls/N --jq '{state, merged, merged_at, merged_by: .merged_by.login, merge_commit_sha, title}'

# 3. If .merged == true:
#    - STOP. The PR was already merged by an automated actor while you were preparing the rebase.
#    - Verify the merge commit is in main history:
gh api repos/OWNER/REPO/compare/<main_head>...<pr_merge_sha> --jq '{status, ahead_by, behind_by}'
#    - .status == "identical" → PR's merge commit IS main HEAD
#    - .status == "behind" → PR's merge commit is in main but main has moved on (other merges after)
#    - .status == "ahead" → PR has commits not in main (would be impossible if .merged == true)
# 4. PIVOT: do NOT keep iterating on the rebase, do NOT push a no-op:
git -C <worktree> rebase --abort
#    - Post the merge commit SHA + auto-merger's identity
#    - Note the auto-merger (e.g. "merged by jleechan2015 at 2026-07-24T13:18:33Z, commit 8072a1ca30")
#    - The PR's stale branch will keep spinning CI on a closed PR's HEAD SHA — that's harmless
#      but wasteful; consider `git push origin --delete <branch>` after the rebase aborts
```

**Why this happens.** The $GITHUB_REPOSITORY repo runs multiple automated agents (dark-factory, AO drive loops, merge-bots) all using the `jleechan2015` identity. While a human-driven drive is preparing a rebase + conflict resolution, a parallel automated actor can land the PR's commits via a different path (e.g. a fresh cherry-pick from `origin/main`, a sister drive loop, or a direct squash-merge of the PR head). The rebase continues; the conflict resolution completes; the push lands a no-op commit that immediately gets rejected as non-fast-forward (or worse, lands a competing resolution that clobbers the auto-merge).

**Verified on PR #8544:**

- Pre-rebase: PR #8544 head `f7ba7cdf5f`, base `530f34e9cb` (1 commit behind main).
- During rebase (after `git fetch origin main` + `git rebase origin/main` + conflict resolution): `git diff origin/main...HEAD --stat` returned empty.
- `gh api repos/$GITHUB_REPOSITORY/pulls/8544` → `{"merged":true,"merged_at":"2026-07-24T13:18:33Z","merged_by":"jleechan2015","merge_commit_sha":"8072a1ca30dc573be7406c57a41727b0b2049725"}`.
- `git log --oneline -5` on the worktree showed `8072a1ca30 fix(bq): preserve God Mode lifecycle telemetry integrity (#8544)` was already in main.
- Pivoted: aborted the rebase, dropped the rebase worktree (`git worktree remove --force /tmp/wa-pr-8544`), verified both PRs are merged (PR #8462 via my `gh pr merge` at `c710675db6`, PR #8544 via the auto-merge at `8072a1ca30`), posted the final summary with both merge commit SHAs.

**Companion pattern to v2.5.10(b) "race-with-AO-worker on PR head".** v2.5.10 detected the race when an automated actor pushed to the same branch the agent was preparing to push. v2.5.11 detects the symmetric case: the automated actor pushed AND merged the branch, and the agent is preparing to push a no-op rebase. Both are "the work was done while I was preparing it" patterns. The difference: v2.5.10 is detectable at push time (`git ls-remote` shows a non-ancestor remote HEAD); v2.5.11 is detectable at diff time (`git diff origin/main...HEAD --stat` is empty).

**Don't fall into:** "Push anyway and see what happens." Force-pushing a rebase onto a branch whose HEAD is now in main history produces a non-fast-forward warning — and even with `--force-with-lease`, you may clobber the auto-merge's actual resolution (if the agent's resolution differs in any non-trivial way). Always diff first, then decide.

**Don't fall into:** "Finish the conflict resolution to be safe, then push." If the diff is empty, the conflict resolution is irrelevant — the PR's content is already in main. Resolution effort is wasted. Abort and post the merge commit.

## Session-level recipe (combined, in drive order)

1. **For each PR in the drive list**, run the v2.5.6 pre-flight (`mergeable_state`, `draft`, head SHA, commit statuses, check-runs). Flag any "already merged" candidate early.
2. **For each PR that's NOT already merged**, run the v2.5.6 budget-vs-test-isolation check: identify the PR's new budgets/timeouts, identify tests in the diff that hold shared resources longer than those budgets, widen the budgets in the tests.
3. **For each PR that's already behind main** (per pre-flight), run the v2.5.10 merge-main resolution recipe. After `git rebase origin/main` resolves, run `git diff origin/main...HEAD --stat`. If empty, the v2.5.11 already-merged detection has fired — abort, post the merge commit, move on.
4. **For each PR that surfaces a test-budget-vs-lock-hold failure**, apply the v2.5.11(a) monkeypatch pattern. Don't rebase, don't re-run, don't dismiss as flake. Fix the test.
5. **For each PR that surfaces a CI infra flake** (timeout, connection-reset, pydantic schema gather), apply the same-test-name-rule on a clean worktree. If the test passes locally on `origin/main` AND on the PR, dismiss as infra flake and re-run the failing job.
6. **For each PR that reaches 7-green on its current head**, run `gh pr merge --squash` (or whatever the repo convention is) and verify the merge commit via `gh api repos/OWNER/REPO/pulls/N --jq '.merge_commit_sha'`.

**The session ended with both PRs merged:**

| PR | Title | Merged by | Merge commit |
|---|---|---|---|
| [#8462](https://github.com/$GITHUB_REPOSITORY/pull/8462) | `fix(bq): cold-replica silent-drop of all 12 gated llm_payloads columns` | jleechan2015 (agent) at 2026-07-24T13:39:38Z | `c710675db635ddf3b39d0140875bffbe1fb74334` (now `main`) |
| [#8544](https://github.com/$GITHUB_REPOSITORY/pull/8544) | `fix(bq): preserve God Mode lifecycle telemetry integrity` | jleechan2015 (auto-merger) at 2026-07-24T13:18:33Z | `8072a1ca30dc573be7406c57a41727b0b2049725` (in main history, 1 commit behind new main) |

## Skills / references consumed

- `same-test-name-rule` (skill) — four-check dismissal gate for the `test_intent_classifier` 180s timeout and the `test_copy_campaign` pydantic schema gather CI flake
- `pr-cleanup-replay` (skill) — the "branch from `origin/main`" pattern, the `--force-with-lease` push, the "diff against current main" sanity check
- `pr-description-validator-gate6b-2026-07-15` (reference) — `pr_description_gate.py --body-file` local verifier before pushing the canonical `**Evidence**: <url> (head <sha>)` PR body line
- `codex-docker-workdir-path-resolution-2026-07-24` (reference) — the pattern of "agent's first PR-introduced budget can silently break existing tests; widen the test, not production"
