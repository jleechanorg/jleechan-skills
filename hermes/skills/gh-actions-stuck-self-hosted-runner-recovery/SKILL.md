---
name: gh-actions-stuck-self-hosted-runner-recovery
version: 1.0.0
description: Recover from a stuck self-hosted Actions runner when jobs hang with no logs retrievable. Use when a job runs to its timeout with `actions/jobs/<id>/logs` returning 404 BlobNotFound, when the same matrix leg fails on consecutive GH Actions runs against the same commit (no log retrievable either time), or when the user reports "CI stuck, can't see logs".
changelog:
  - "1.0.0 (2026-07-14) initial — PR #8290 verified recipe (worktree w8290, head aff95f87e, quarantine-reset via workflow 273070459 cleared the stuck runner within one re-trigger cycle)"
---

# Stuck Self-Hosted Runner Recovery (v1.0.0, verified 2026-07-14 PR #8290)

When a self-hosted runner silently dies mid-job (OOM, disk full, network blip), the job times out, and the log blob on Azure is `BlobNotFound` — even when fetched via `actions/jobs/<id>/logs`. This is fundamentally different from a real test failure (which has logs). The pattern is recognisable from the symptom combination below.

## Symptom combination (all three required for confident diagnosis)

1. **Job timeout reached**: `conclusion=failure` with `completed_at - started_at ≈ timeout-minutes` of the workflow's `timeout-minutes:` setting (e.g. 16m15s for a 25-min timeout on `Directory tests (core-tests)`).
2. **Log retrieval returns 404**: `curl -fsSL https://api.github.com/repos/<OWNER>/<REPO>/actions/jobs/<JOB_ID>/logs` (followed through to `productionresultssa19.blob.core.windows.net`) returns `<?xml version="1.0" encoding="utf-8"?><Error><Code>BlobNotFound</Code>`. The `gh run view --log-failed` CLI also returns `log not found: <id>`.
3. **Recurrence on re-trigger**: the same matrix leg fails again on a fresh `workflow_dispatch` against the same head SHA. Single occurrence could be a one-off; twice is the deploy-infra trap.

When all three hold, it's a stuck self-hosted runner, NOT a code defect. **Do not chase the named commit**. Local reproduction (against the PR HEAD worktree) will be clean; that's the smoking gun.

## Recipe (5 steps, ~5 min wall-clock)

### Step 1 — Confirm with local reproduction

```bash
WT=$HOME/.worktrees/<branch>          # or /path/to/worktree-w<N>
cd "$WT"
export PYTHONPATH="$PWD:$PWD/testing_utils:$PWD/mvp_site:$PWD/automation"
export VIRTUAL_ENV="$PWD/venv"                  # OR point to a shared venv
export TESTING=true TESTING_AUTH_BYPASS=true MOCK_SERVICES_MODE=true FAST_TESTS=1
export GEMINI_API_KEY=test CEREBRAS_API_KEY=test OPENROUTER_API_KEY=test TEST_GEMINI_API_KEY=test
export GOOGLE_APPLICATION_CREDENTIALS=/dev/null WORLDAI_GOOGLE_APPLICATION_CREDENTIALS=/dev/null
export WORLDAI_DEV_MODE=true ENABLE_SEMANTIC_ROUTING=false
export GITHUB_ACTIONS=true TEST_MAX_WORKERS=2
# Map test-group → test-dirs via the repo's scripts/ci-detect-changes.sh (e.g. core-tests → "tests")
"$VENV/bin/python" -m pytest <test-dirs> -q --no-header --tb=line --timeout=60
```

If local passes in seconds/minutes while CI ran to timeout with no logs → confirmed infra, proceed to Step 2. If local FAILS, the code IS the bug — pivot to a code fix, not infra recovery.

### Step 2 — Trigger the runner quarantine-reset workflow

Many `jleechanorg/*` repos ship a `runner-checkout-lint` workflow that has the side effect of draining stuck self-hosted runners (id `273070459` on `$GITHUB_REPOSITORY`, workflow name `Runner Quarantine Reset`). It does not require inputs:

```bash
gh workflow run 273070459 --repo <OWNER>/<REPO>
```

This forces the runner pool to re-evaluate health scores and drain any runner scoring below threshold. It typically completes in <2 min.

### Step 3 — Re-trigger the failed workflows

```bash
WF_DIR_TESTS=171905509    # WorldArchitect Tests (Directory-Based) on $GITHUB_REPOSITORY
WF_GREEN_GATE=259332740
WF_EVIDENCE_GATE=256612708

# Re-trigger with explicit head SHA so the run is bound to the current PR state
gh workflow run $WF_DIR_TESTS --repo <OWNER>/<REPO> --ref <branch>
gh workflow run $WF_GREEN_GATE --repo <OWNER>/<REPO> --ref <branch> \
  -f pr_number=<N> -f head_sha=<40-char SHA>
gh workflow run $WF_EVIDENCE_GATE --repo <OWNER>/<REPO> --ref <branch> \
  -f pr_sha=<40-char SHA>
```

For other repos, look up workflow IDs via `gh workflow list --repo <OWNER>/<REPO> --json id,name`.

### Step 4 — Wait one job-pickup cycle (5-10 min)

The runner that picks up the new job is a DIFFERENT runner than the one that died. Self-hosted runners are round-robined; after the quarantine-reset, the dead runner is offline and the pool size shrinks by 1. Expect ~5-10 min for the new job to be picked up + complete.

### Step 5 — Verify the new run PASSED

```bash
gh api repos/<OWNER>/<REPO>/commits/<HEAD_SHA>/check-runs | \
  jq -r '.check_runs[] | "\(.name) \(.conclusion)"' | sort -u
```

If the previously-failing matrix leg now shows `success`, the recovery succeeded. If it still fails the same way, the runner pool has a deeper issue — escalate via `br create` bead (type=chore, priority=1) with provenance: run IDs, log-404 evidence, local-reproduce proof.

## Pitfalls

1. **Banned — chasing the named commit through re-trigger loops without confirming local reproduction**. Each wasted re-trigger costs ~15 min of CI time. The 5-step recipe is gated on Step 1: local PASS + CI FAIL. Skip Step 1 and you're guessing.

2. **Banned — `gh run cancel` as the primary recovery**. `cancel` on a stuck runner is a band-aid (per `gh-actions-slow-runs` P6); the runner is already dead, the job is already gone. What you need is to drain the runner FROM the pool so the next job lands on a different runner. That's what `runner-checkout-lint` does.

3. **Banned — assuming one stuck-runner occurrence is a code bug**. Single occurrence is ambiguous. Wait for the second failure on the same commit before invoking the infra-recovery recipe. (Verified 2026-07-14 PR #8290: the FIRST core-tests failure could have been anything; the SECOND consecutive failure on `aff95f87e33` was the infra smoking gun.)

4. **Banned — invoking the recipe on GitHub-hosted runners**. GitHub-hosted runners don't have this failure mode (they're ephemeral and either succeed or fail with logs). The whole recipe is for self-hosted (`runs-on: ${{ fromJson(vars.SELF_HOSTED_RUNNER_LABELS || '["self-hosted"]') }}`) workflows.

## Verified provenance

- **2026-07-14 PR #8290** (`$GITHUB_REPOSITORY`, head `aff95f87e33`, worktree `w8290`):
  - First core-tests failure at 21:01:57Z, run 29367033991, job 87202451271 (16m15s, log BlobNotFound)
  - Local reproduction: `tests/test_*.py` (13 files) + `tests/scripts/test_*.py` (10 files) → **304 passed in 7.01s** in w8290
  - Second failure at 21:14:10Z, run 29367053540 (cascaded Green Gate FAIL)
  - Triggered `gh workflow run 273070459` at 21:32Z (Runner Quarantine Reset)
  - Re-triggered `WorldArchitect Tests (Directory-Based)` at 21:34:35Z, run 29370027514 → **success**
  - Re-triggered Green Gate at 21:34:33Z, run 29370026085 → in_progress at last check (expecting success)
  - Total recovery wall-clock: ~30 min from first FAIL to clean re-run completing.

## Cross-references

- `~/.hermes/skills/gh-actions-slow-runs/SKILL.md` — the umbrella skill. **P7** explicitly documents the "silent step-2 abort = self-hosted runner OOM/disconnect" pattern this recipe recovers from. P6 covers why `gh run cancel` is a band-aid.
- `~/.hermes/skills/workflow/drive-pr-to-green/SKILL.md` — the drive-to-green flow that this recipe slots into (post-merge, post-evidence-sync, mid-drive).
- `incident-proposal-current-evidence-gate` SOUL.md COMMIT — the rule that fires on "failure recurs on same commit for >1 GH Actions run" (= open a `br create` bead). This recipe is the IMPLEMENTATION of that rule.