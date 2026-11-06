---
name: pr-cleanup-replay
version: 1.7.0
description: |
  Recipe for cleaning up an already-polluted PR — one whose branch was created from
  the wrong base (or merged another PR's full history) and now carries unrelated commits.
  Produces a fresh branch from origin/main, cherry-picks only the load-bearing diff, and
  force-pushes the clean replay in place (same PR number) OR opens a new PR when in-place
  is unsafe. v1.7.0 — Phase -0.5 writable-remote base selection: branching from
  origin/main (read-only upstream) and pushing to fork (writable, 6000+ commits ahead)
  creates a 600k-line polluted PR. Recipe: verify `gh api .../permissions.push` per
  remote, base on the writable remote's main, port upstream patches to the fork's
  refactored code. Verified jleechanorg/hermes-agent PR #3 polluted → PR #4 clean.
  Triggered by SOUL.md `## COMMIT: pr-clean-branch-from-main-no-history-bloat`.
tags: ["pr-cleanup", "replay", "origin-main", "git-merge-vs-cherry-pick", "harness-fix", "pre-push-hook", "force-push-in-place", "agent-drift"]
category: workflow
triggers:
  - "clean up this PR"
  - "replay this PR"
  - "fix PR scope"
  - "this PR has too many commits"
  - "branch is bloated"
  - "rewrite this PR cleanly"
  - "minimal diff replay"
  - "pr-cleanup-replay"
  - "polluted PR"
  - "PR has unrelated history"
  - "branch from origin main"
  - "pre-push hook not blocking"
  - "gitleaks didn't catch this"
  - "backup folder in public repo"
  - "home dir leaked to github"
  - "close this PR if superseded"
  - "integrate into the new PR"
  - "stack this on the V1 branch"
  - "supersede this PR"
  - "force-push clean replay"
  - "AO worker added drift files"
  - "PR has files that don't match the title"
  - "agent polluted the PR"
  - "value retune"
  - "change the cap to X"
  - "tweak the threshold to Y"
  - "I'll decide later"
  - "stale replay target"
  - "replay target is below main"
  - "origin/main advanced"
  - "PR is mergeable=CONFLICTING but CI passes"
  - "mergeable_state dirty but checks succeed"
  - "should I rebase to current main"
  - "PR shows 600k lines / 4000 files"
  - "PR diff includes hundreds of files I didn't touch"
  - "PR diff includes AGENTS.md / workflows / configs unrelated to my fix"
  - "fork and upstream diverged"
  - "what is the writable remote"
  - "which remote can I push to"
  - "should I branch from origin or fork"
  - "gh api permissions.push"
  - "port upstream patch to fork"
  - "file doesn't exist in fork but exists in upstream"
allowed-tools:
  - Bash
  - Read
  - Edit
context: inline
---

# PR Cleanup Replay — surgical replay of a polluted PR

When an agent discovers (or is told) that a PR is bloated — i.e. its branch carries
commits unrelated to its stated scope, or its diff is >2x the load-bearing fix —
follow this recipe to produce a clean minimal-diff replay.

## Phase -2 — patch-as-port: external patch targets a different module split

The most common cause of "`git apply --check` says the patch doesn't apply" is that the patch was generated against a *different* repo (or an older commit of the same repo) whose file layout doesn't match the target. The `git apply --check` recipe in the GUIDE — `sed -e 's|snap_factory/engine.py|dark_factory/engine.py|g' | git apply --check` — only works when the upstream package is renamed verbatim. When the upstream has been **refactored** (e.g. `snap_factory/engine.py` 1932-line class → `runner/handler_codergen.py::_codergen` + `runner/handler_verdict.py`), a sed pass alone is insufficient — the symbols land in different modules.

```bash
# 1. ALWAYS run git apply --check from inside the target repo:
cd <target-repo>
git apply --check /path/to/external.patch
# Errors:
#   "error: snap_factory/engine.py: No such file or directory"
#       → patch targets a file that doesn't exist in this repo.
#         Confirm whether the module was renamed, refactored, or never existed.
#   "error: patch failed: tests/test_engine.py:2738"
#       → patch targets a real file but the line context is stale.
#         The symbol may have moved to a different module.

# 2. Build a symbol-mapping table BEFORE writing code:
#   For each hunk header (`diff --git a/<path> b/<path>`):
#   - Does the file exist in the target repo at the expected path?
#   - If not, where is that symbol implemented in the target?
#   - For each function/class insertion (look for `@@ -<line>,<count> +<line>,<count> @@ def <name>`):
#     - Does `<name>` exist in the target repo? `git grep -n '<name>' HEAD`
#     - If yes, where? Add the new code adjacent to the existing definition.
#     - If no, this is a net-new function — which upstream module should host it?
#   - For each modified test or fixture:
#     - Does the test class still exist? `git grep -n 'class <name>' HEAD`
#     - If yes, add new test methods; do NOT create a parallel test file.
```

**Why this discipline matters (verified 2026-07-20):** A 33 KB `infra03q-inpipeline-receipt.patch` from `snap_factory` HEAD targeted `snap_factory/engine.py` with functions `_run_llm`, `_finalize_review_status`, `_reproduction_receipt_gaps`, `_is_review_node`. None of those symbols exist in the upstream `jleechanorg/dark-factory` repo (which has a `runner/engine.py` re-export shim, `runner/handler_codergen.py::_codergen` for the LLM dispatch, and a totally different module split after PR #77). The agent's default — `git apply --stat` (which only counts hunks without verifying they apply) — would have said "OK" while the actual `git apply --check` failed on both the missing file and a context drift. The fix is NOT a sed pass; it's a per-symbol port with an explicit destination table. See `references/patch-as-port-symbol-mapping-2026-07-20.md` for the full table from this incident (5 net-new symbols, 1 net-new test file, 1 net-new doc, 1 fixture fix; landing targets: `runner/handler_verdict.py`, `runner/handler_codergen.py::_codergen::_finalize`, `tests/test_review_reproduction_receipt.py`, `tests/test_engine.py::TestLLMNodeDispatch`, `docs/ungameable-cold-gate.md`).

**Three operational rules:**

1. **Always `git apply --check` from inside the target repo** (not from `$HOME` or another parent where missing-file errors are silently suppressed as warnings and a green stat-check hides a red apply-check).
2. **Build the symbol-mapping table before writing any code.** Each `def <name>(...)` line in the patch → row in the table with (a) target file:line, (b) what the new function does, (c) what existing upstream function it parallels (or "net-new — no upstream equivalent").
3. **Surface the symbol-mapping table to the user** before opening the PR. The user explicitly said "if you understand the goals" when approving this kind of port — and they can't verify the port without seeing the table.

## Phase -0.5 — Writable-remote base selection (don't branch from a remote you can't push to)

The most common cause of "the PR is 600k lines / 4000 files" pollution in fork setups is **branching from the upstream remote and pushing to the fork remote**. The two remotes point at the same repo name but **different refs with different histories**:

- `origin` = `NousResearch/<repo>.git` (or other upstream) — read-only from your `gh auth` user; you have **no push permission**.
- `fork` (or `github`) = `<your-org>/<repo>.git` — writable fork, often **6,000+ commits ahead of `origin/main`** because the fork has accumulated local-only work.
- `upstream` (sometimes) = a separate writable remote the maintainer controls.

When you `git worktree add -b fix/x origin/main` and `git push <writable-remote> HEAD:refs/heads/fix/x`, the PR is created against the writable remote's `main` (not `origin/main`). The diff is therefore **writable-remote/main vs your-branch** — which on a 6,000-commit-ahead fork shows the entire fork divergence as "polluted PR diff". Result: a PR with +600k/-90k/4,000 files claiming to "fix Python 3.14".

**Mandatory pre-flight recipe (run BEFORE `git worktree add`):**

```bash
# 1. List all remotes and their URLs
git -C <repo> remote -v
# Identify: origin (upstream), fork (your writable fork), and any others.

# 2. Verify WRITE permission to each candidate remote
for r in origin fork; do
  echo "=== $r ==="
  gh api "repos/$(git remote get-url $r | sed -E 's#.*github.com[:/](.*?)/(.+)\.git#\1/\2#')" --jq '.permissions.push // .permissions.admin'
done
# Expected: origin=false, fork=true

# 3. Compare fork/main vs origin/main — if divergence is large, base MUST be fork/main
git fetch origin fork --quiet 2>/dev/null
DIVERGENCE=$(git -C <repo> rev-list --left-right --count origin/main...fork/main)
echo "origin/main vs fork/main: ${DIVERGENCE}"
# Expected on jleechanorg/hermes-agent: "6705\t0" or similar (fork AHEAD of upstream)

# 4. If fork is >100 commits ahead of origin, ALWAYS base new branches on fork/main:
git -C <repo> worktree add -b fix/<topic> /tmp/<repo>-wt <WRITABLE-FORK>/main
# NOT origin/main — even if the upstream patch lives there.
```

**The patch-porting adjustment (when the upstream fix lives on origin/main but you must push to fork):**

Upstream's `tools/daemon_pool.py` may not exist on fork/main (the fork refactored to `tools/async_delegation.py`). You cannot `git apply` the upstream patch verbatim — the file paths diverge. Two recipes:

```bash
# Recipe A — Cherry-pick the upstream commit; resolve file-move conflicts manually
git -C <repo> fetch origin <upstream-branch>
git -C <fork-wt> cherry-pick <upstream-sha>
# Expect: "CONFLICT (modify/delete): tools/daemon_pool.py deleted in HEAD"
# Resolution: read upstream's patch, identify the SYMBOL it modifies (e.g.
# `_adjust_thread_count` in `DaemonThreadPoolExecutor`), find the fork's
# equivalent location via `git grep -n 'class.*DaemonThreadPoolExecutor\|def _adjust_thread_count' fork/main`,
# apply the patch content there via patch / write_file.

# Recipe B — Inspect both versions, port the fix conceptually
git show origin/main:tools/daemon_pool.py > /tmp/upstream-pool.py
git show fork/main:tools/async_delegation.py | grep -n '_adjust_thread_count\|_DaemonThreadPoolExecutor'
# Write a NEW patch that matches the fork's code structure, with the same logic.
```

**Verified case 2026-07-24, jleechanorg/hermes-agent Python 3.14 `_initializer` fix:**

- Branched from `origin/main` (NousResearch upstream, read-only). Pushed to `fork` (jleechanorg, writable).
- Resulting PR #3: +600,146 / -93,707 / 3,930 files — the entire fork divergence appeared as "unrelated diff".
- Closed PR #3.
- Rebased on `fork/main`, ported the patch from `tools/daemon_pool.py` (upstream) to `tools/async_delegation.py::_DaemonThreadPoolExecutor` (fork inlined the class).
- New PR #4: +25/-6 / 1 file (`be0a896ba` on `fix/daemon-pool-py314`). Clean.

**Diagnostic symptom:** the PR shows >1000-line additions in dozens of unrelated files (configs, workflows, AGENTS.md, .dockerignore, etc.). That is **not** pollution from agent drift — it is **wrong-base-branch pollution** from a remote-ownership mistake. The recovery is rebase onto the writable remote's main, NOT Phase 1/3.5 cleanup-replay.

**Cross-link:** SOUL.md `## COMMIT: pr-clean-branch-from-main-no-history-bloat` covers the principle; this Phase -0.5 is the operational recipe for the fork-vs-upstream variant.

## Phase -1 — Prevention (don't push onto someone else's PR head in the first place)

The most common cause of a "polluted PR" is pushing new commits onto an existing
PR's head branch that the agent does not own. Before `git push origin HEAD:refs/heads/<branch>`:

```bash
# 1. Does the target branch belong to me?
gh pr view <N> --json headRefName,author | jq '.author.login + " owns " + .headRefName'
# If author.login != current gh auth user AND headRefName starts with
# feat/..., fix/..., chore/..., docs/... → STOP, branch from origin/main instead.

# 2. If pushing to a remote branch that already has a non-trivial diff vs origin/main,
#    check the diff stat first.
git -C <repo> diff --shortstat origin/main..HEAD
# > 1000 lines OR > 50 files OR 'Merge remote-tracking branch' commits in the log
#   → the branch is shared; do NOT push onto it.

# 3. Force-of-habit reminder: "an open PR that touches this code" is a SIGNAL,
#    not an INVITATION to push onto its head branch. The default action is
#    "branch from origin/main, open a new PR".
```

**2026-07-14 incident class — happens twice in one day.** Same root cause, two
repos, two open PRs:

- $GITHUB_REPOSITORY PR #8401 (head `feat/fix-xp-overflow-no-level-up-7931-full-brief-at-tmp-wa-task-i`,
  +670k/-24k baseline) → polluted with 22 commits → closed in favor of PR #8403.
- jleechanorg/claude-commands PR #321 (head `fix/real-claude-team-tmux`,
  +670k/-24k / 3001 files) → polluted with 2 commits (this skill's origin
  incident) → reverted head back to `286311a97` via `git push --force-with-lease`,
  clean replay at PR #329.

Both incidents have the same anti-pattern: the agent saw an open PR whose topic
overlapped the task, picked that PR's head branch as the push target, and never
asked "does this branch belong to me?". User feedback both times was the same
flavor of "this isn't a clean PR from origin/main, why do you keep screwing
this up?" — confirming the preventive gate belongs here, not buried in a
SOUL.md `## COMMIT:` that future agents may not surface.

## Phase 0 — Confirm the diagnosis

Run these checks BEFORE doing anything:

```bash
# 1. Diff vs origin/main (what is the scope?)
git diff --shortstat origin/main...HEAD
# Expect: a few files, <1000 lines for non-docs PRs

# 2. Commits vs origin/main (are they all related to the PR?)
git log --oneline origin/main..HEAD
# Watch for: "Merge remote-tracking branch", "[fixpr ...]", "fix(beads)",
# "chore(deps):", or any commit whose message does not match the PR title/body

# 3. Is the target file change load-bearing?
git diff origin/main...HEAD -- <load_bearing_path> | head -50
# Verify the file change matches what the PR claims to fix
```

If any of these fails (diff too big, unrelated commits, change does not match the
stated bug), the PR is polluted. Proceed to Phase 1.

## Phase 1 — Identify the load-bearing diff

Two strategies:

**Strategy A — Cherry-pick individual commits.** Use when the PR's history contains
3-5 distinct commits whose messages match the PR scope, plus noise (merge commits,
beads drift, CI fixes).

```bash
# Identify the load-bearing commits (skip merge/auto/CI/beads commits)
git log --oneline origin/main..HEAD --no-merges --grep='^fix' --grep='^feat' --grep='^chore(level-up)'
# Note the SHAs in chronological order

# Open a fresh worktree from origin/main
git worktree add -b fix/<topic>-replay /tmp/wt-<topic> origin/main

# Cherry-pick load-bearing commits only
cd /tmp/wt-<topic>
git cherry-pick -x <sha1> <sha2> <sha3>
# Resolve any conflicts; if a conflict is structural (different file shapes),
# skip it and apply the change manually via patch.
```

**Strategy B — Extract the file diff directly.** Use when the PR's history is
entirely noise (only merge commits + beads drift) but the file-level diff IS the fix.

```bash
# Identify the load-bearing files
git diff --name-only origin/main...HEAD

# In a fresh worktree from origin/main:
cd /tmp/wt-<topic>
git show origin/<polluted-branch> -- <file1> <file2> > /tmp/load_bearing.patch
git apply /tmp/load_bearing.patch
# Verify the patch applies cleanly; resolve any fuzz/rejects manually.
```

**Strategy B Variant — Surgical 2-hunk `patch` apply when main has overlapping changes.**
The naive `git checkout origin/<branch> -- <file>` is unsafe when `origin/main`
has accumulated edits in the same files since the PR was created — the
whole-file checkout silently reverts main's improvements (verified on PR #8139
replay → PR #8561, 2026-07-24: `app.js` checkout reverted 554 lines of
main-side route-handling / draft-persistence code that landed after 8139 was
first opened).

Use this recipe when `git diff origin/main...HEAD -- <file>` shows main-side
edits in the file:

```bash
# 1. Compute the file-level diff against main
git diff origin/main...HEAD -- <file> > /tmp/file.patch
wc -l /tmp/file.patch

# 2. Try git apply (will likely fail with "patch does not apply")
cd /tmp/wt-<topic>
git apply --check /tmp/file.patch
# Expect: "patch failed: <file>:<line>" — the hunk context is stale

# 3. Inspect the patch — extract ONLY the hunks that match the load-bearing change
diff <(git show origin/main:<file>) <(git show origin/<polluted-branch>:<file>) > /tmp/full-file-diff.txt
# Identify the 2-3 hunks that are the actual feature (e.g. the wizard scroll
# indicator integration), not hunks reverting main-side changes.

# 4. Write a CUSTOM patch file with only the load-bearing hunks, then apply
patch -p1 --dry-run < /tmp/load_bearing-only.patch
patch -p1 < /tmp/load_bearing-only.patch

# 5. Verify the result
git diff origin/main -- <file>
# Expect: ONLY the wizard-specific hunks. NOT a wholesale reversion of main.
```

**How to identify load-bearing hunks when the file is large:**
- Search for the function/method name that defines the feature (`grep -n
  'applyMobileScrollLock\|setupScrollIndicator\|teardownScrollIndicator' <file>`
  in the PR's version).
- The hunks that introduce/call these functions are the load-bearing ones.
- Hunks that REMOVE main-side code (e.g. deleting a route-handling block
  added to main after 8139) are the dangerous ones — exclude them.

**Symptom that flags this variant:** after `git checkout origin/<branch> -- <file>`,
`git diff origin/main -- <file>` shows >100 lines of deletions that don't look like
the feature (often `lastRouteFullPath`, `pendingStream`, `draftDebounceTimeout`,
or other main-side state that the PR's snapshot predates). Revert the checkout
and use the surgical patch approach instead.

## Phase 2 — Run tests in the fresh worktree

```bash
# Run the load-bearing test file (or full suite for the touched module)
pytest <test_path> -v
# Expect: ALL tests pass; no new failures introduced

# If a test that was passing on origin/main now fails, the cherry-pick missed a
# dependency or extracted the wrong diff. Go back to Phase 1.
```

## Phase 3 — Commit + push + open new PR + close old PR

```bash
cd /tmp/wt-<topic>

# Single clean commit on the fresh branch
git add -A
git commit -m '[<scope>] <one-line summary> (#<orig_issue>)' \
  -m '<multi-line description matching the PR body scope>'

# Push and create the new PR
git push -u origin fix/<topic>-replay
~/.hermes/scripts/gh-safe-publish pr create --base main --head fix/<topic>-replay \
  --title '<same title as the old PR>' \
  --body '<updated body, link the old PR + issue, explain the cleanup>'

# Close the polluted PR with a reference to the new one
gh pr close <old_pr_number> --comment "Closing in favor of clean replay #<new_pr_number>. \
  Original PR inadvertently pulled <N> unrelated commits (merge chains, beads drift, \
  CI fixes). The clean replay contains only the load-bearing fix in <M> files."
```

### Phase 3.5 — In-place force-push replay (same PR number, NOT close-and-reopen)

When the polluted branch was created by an **AO worker you can correct** (the agent is still alive or the branch is recoverable from `origin/<branch>`) AND the polluted PR is **already open with the correct title/base/issue link**, the right move is to **force-push the clean replay onto the same branch** so the existing PR's `headRefOid` updates in place. Do NOT close the old PR and open a new one.

**Why in-place beats close-and-reopen:**
- Preserves the PR number (issue auto-close link stays intact: `Closes #<N>`).
- Preserves any reviewer comments, CodeRabbit review state, and cursor[bot] bugbot history.
- Preserves the headRefName — anyone watching the branch via `gh pr list --head <branch>` keeps seeing it.
- Avoids the duplicate-PR risk (`always-pr-never-local-edit` v1.1.0 / v1.2.0 PR-topology pre-flight).

**Recipe:**

```bash
# 1. Identify the polluted HEAD (last commit on origin/<branch>)
BAD_SHA=$(git -C <repo> rev-parse origin/<branch>)

# 2. Identify the load-bearing files in the polluted commit
git -C <repo> show --name-only "$BAD_SHA"
# Pick the intended files only (no drift files like bq_logging.py, world_logic.py, roadmap/**, deleted unrelated tests).

# 3. Branch a fresh worktree from current origin/main (NOT from the polluted branch)
git -C <repo> worktree add -B <branch> /tmp/wt-<topic>-replay origin/main

# 4. Strategy B: extract the file-level diff from the polluted commit
cd /tmp/wt-<topic>-replay
git -C <repo> show "$BAD_SHA" -- <file1> <file2> ... | \
  git apply --include='<file1>' --include='<file2>' ...

# 5. Verify the staged diff matches ONLY the intended files
git -C <repo>/.worktrees/wt-<topic>-replay diff --name-only origin/main..HEAD
# Expect: exactly the 4 (or N) intended files. STOP if you see drift files.

# 6. Single clean commit
cd /tmp/wt-<topic>-replay
git add <intended-files-only>     # NEVER `git add -A` — pick paths explicitly
git commit -m "<scope>: <one-line summary>" \
  -m "Clean replay from origin/main." \
  -m "<multi-line description matching the polluted PR's body scope>"

# 7. Force-push (the prior bad SHA is being replaced; force-with-lease is mandatory)
git push --force-with-lease origin <branch>

# 8. Verify the same PR number now points at the clean replay HEAD
git -C <repo> rev-parse origin/<branch>
gh pr view <N> --json headRefOid,files --jq '{headRefOid, files:[.files[].path]}'
# Expect: headRefOid == local HEAD, files == the intended paths only.

# 9. Verify the local main checkout was NOT polluted
cd $HOME/projects/<main>
git status --short
# Expect: empty (the apply work happened in the worktree, not the main checkout)
```

**Why `--force-with-lease` and not `--force`:** force-with-lease refuses to overwrite if the remote moved between your fetch and your push. This protects against a sibling worker (AO, babysit cron, drive loop) pushing their own resolution in the meantime — same race-with-AO-worker guard as Phase 5.5.

**When to escalate to close-and-reopen instead:** if `gh pr view <N> --json files` after force-push shows ANY drift file persisting (rare — would mean your `git apply --include` whitelist didn't actually filter), close-and-reopen is the safer escape hatch. But verify the apply first; close-and-reopen is the LAST resort, not the default.

**Verified case 2026-07-23, $GITHUB_REPOSITORY PR #8541** (`feat/read-tmp-god-mode-generic-repro-20260723-ao-ta[REDACTED_OPENAI_KEY]`): AO worker `wa-3389` (MiniMax-M3 mid-tier) shipped a polluted commit `0c5a2b6a64` containing 9 files / +706 / −424 with 5 drift files (`$PROJECT_ROOT/bq_logging.py` +21, `$PROJECT_ROOT/world_logic.py` +92, `$PROJECT_ROOT/tests/test_godmode_directive_lifecycle_events.py` −332, `roadmap/README.md` −1, `roadmap/activity/2026-07-23.md` −33) alongside the 4 intended files. Force-pushed replay commit `0b0bc4ac73521c14b402d0c5dd1211730479a469` contained only the 4 intended files (+651 / −0). Same PR #8541, same branch, same issue-link, no close-and-reopen. PR diff after replay:
- `$PROJECT_ROOT/agent_prompts.py`
- `$PROJECT_ROOT/prompts/god_mode_instruction.md`
- `$PROJECT_ROOT/tests/test_god_mode_formula_registry_contract.py`
- `testing_mcp/test_god_mode_avatar_partition_contract_real_api.py`

The 5 drift files disappeared from `gh pr view 8541 --json files` immediately after the force-push. No new PR number needed; issue #8538's `Closes` link in the body stayed intact.

## Phase 5.5 — Resolve merge conflicts against fast-moving main (kept-history variant)

Distinct from cleanup-replay: the PR's history is intentional (5+ prior merge commits, each absorbing main at its current state), and you want to preserve that history while absorbing the next round of main. This is the **"merge-main into feature branch"** recipe used when the PR is already 80+ commits behind main and you cannot replay.

**When to use this phase (not Phase 1–4 cleanup, not Phase 5 supersede):**

- The PR has 3+ commits of substance that should NOT be replayed
- The PR's prior `Merge remote-tracking branch 'origin/main' into <branch>` commits are intentional (CI-retrigger commits, follow-up fixes, evidence-refresh commits)
- The PR is currently `mergeable: CONFLICTING, mergeStateStatus: DIRTY` against current `origin/main`
- Merging main into the feature branch produces 1-5 conflicts in different files
- You CAN push to the PR's branch (you are the PR author)

**Recipe:**

```bash
# 1. Verify the PR is yours (per SOUL.md `never-push-onto-someone-elses-pr-head`)
gh pr view <N> --repo <OWNER>/<REPO> --json author --jq .author.login  # expect YOUR gh auth user

# 2. Create a fresh worktree branched from origin/main (NOT from the PR's branch)
git worktree add -B <branch>-merge /tmp/<repo>-merge origin/main

# 3. Merge the PR branch INTO the new worktree
cd /tmp/<repo>-merge
git merge --no-ff origin/<branch> --no-edit
# Conflicts will appear here.

# 4. Inspect conflicts BEFORE resolving — pick the right strategy per file
git diff --name-only --diff-filter=U  # unmerged paths only
# For each conflicting file, choose:
#   (a) KEEP_HEAD            → main's version is the canonical truth
#   (b) KEEP_BRANCH          → PR's version is the canonical truth
#   (c) COMBINE               → both sides added value (the common case for prompt files)

# 5. After all conflicts resolved, commit the merge
git add <resolved-files>
git commit -m "Merge origin/main into <branch> (resolve PR #<N> conflict)

Resolved in <files>:
- <file1>: <one-line description of what was kept/added>
- <file2>: <one-line description>

Refs: PR #<N> / mergeStateStatus: DIRTY → CLEAN"

# 6. Push the merge commit (force-with-lease because the prior merge base moved)
git push origin HEAD:refs/heads/<branch> --force-with-lease

# 7. Verify the PR is mergeable
gh pr view <N> --json mergeable,mergeStateStatus,headRefOid
# Expect: mergeable="MERGEABLE", headRefOid=your-new-commit-sha
```

**Three reusable conflict-resolution patterns:**

**Pattern A — Info-comment collision in workflow files (`.github/workflows/*.yml`).** When both sides added informational comments about historical PR activity, keep the most recent main-side comment and append a new comment about this merge's specific delta. Bump any line-count / version ratchet values in the workflow YAML to absorb the merge's net file growth.

**Pattern B — Prompt contract hash conflict in `$PROJECT_ROOT/schemas/prompt_tool_contracts.json`.** Both sides modified the same `.md` prompt, so each side's `version` field is the sha256[:12] of their respective prompt bytes. The auto-merged `.md` file has a third, NEW sha256 (the combination). Resolution: take the auto-merged file's actual sha256.

```bash
NEW_SHA=$(sha256sum $PROJECT_ROOT/prompts/<name>.md | awk '{print $1}')
NEW_VERSION="${NEW_SHA:0:12}"
# patch the contracts.json to use $NEW_VERSION and full $NEW_SHA
```

**Pattern C — Helper-function vs inline structural merge in `$PROJECT_ROOT/llm_service.py` (or any module where main uses inline and the PR refactored to helpers).** Keep the PR's helper-based structure (the helpers exist in the PR's tree above the conflict). Add any main-side behavioral changes (e.g. a `core_memories` strip that landed on main after the PR was created) to the PR's helper function. This combines both sides' value.

**Anti-patterns (verified wasted 30+ minutes):**

- Picking one side verbatim and losing the other side's behavior. The PR's tree and main's tree each have unique value; structural-vs-inline conflicts require preserving both.
- Re-running `/es` capture to "fix" an Evidence Gate freshness failure caused by the merge. The freshness check is SHA-based, not behavioral. New merged HEAD = new required capture. The fix is structural (re-capture, label `(historical)` in PR body, or accept).

**Mandatory post-push verify loop (merge-conflict treadmill, verified PR #8292):** When the PR is 80+ commits behind `origin/main`, every successful `merge origin/main` resolution re-dirties within minutes — `origin/main` keeps moving while CI runs. After pushing your merge commit, do NOT assume victory:

```bash
# Watch for 5-15 minutes
for i in 1 2 3 4 5 6 7 8 9 10; do
  STATE=$(gh pr view <N> --json mergeStateStatus --jq .mergeStateStatus)
  echo "tick $i: mergeStateStatus=$STATE"
  [ "$STATE" = "CLEAN" ] && { echo "DONE"; break; }
  [ "$STATE" = "DIRTY" ] && { echo "RE-DIRTIED — re-merge against new main"; break; }
  sleep 30
done
```

If `mergeStateStatus` flips back to `DIRTY` during your CI wait, re-merge against the new main HEAD (Phase 5.5 round N+1). The treadmill continues until either (a) your PR merges, (b) main freezes for >1 hour, or (c) you stop and surface the structural problem to the user.

**Race-with-AO-worker guard (verified PR #8292):** While your CI runs, an automated AO worker / babysit cron / drive loop using the SAME credentials may push their own conflict-resolution commit. ALWAYS check the remote tip before pushing:

```bash
LOCAL_HEAD=$(git -C <worktree> rev-parse HEAD)
REMOTE_HEAD=$(git ls-remote origin <branch> | awk '{print $1}')

if [ "$LOCAL_HEAD" = "$REMOTE_HEAD" ]; then
  echo "REMOTE ALREADY HAS YOUR WORK — skip the push"
  exit 0
fi

if git merge-base --is-ancestor "$REMOTE_HEAD" "$LOCAL_HEAD"; then
  echo "Safe to push (your commit is ahead of remote)"
  git push origin HEAD:refs/heads/<branch> --force-with-lease
else
  echo "DIVERGENCE — remote is NOT your ancestor"
  echo "Common case: AO worker pushed an equivalent resolution. Inspect:"
  git diff "$LOCAL_HEAD" origin/<branch> --stat
  echo "If equivalent or better: let it stand, do NOT push your own"
fi
```

**Verified PR #8292 (2026-07-23):** PR `feat/provenance-narrow` had 132 commits (5 prior merge commits). During my 8-minute CI wait, an AO worker using `jleechan2015` credentials pushed `dc5fb6381652` with the identical conflict resolution strategy (helper-function refactor + `core_memories` strip + auto-merged hash). I discovered the race by `git ls-remote origin feat/provenance-narrow` BEFORE pushing my own. Letting AO's commit stand preserved the durable state and avoided a non-fast-forward force-with-lease.

**See also:**
- `references/rebase-fork-divergent-patch-anchor-2026-07-21.md` in `drive-pr-to-green` for the rebase variant of this technique
- `references/merge-conflict-treadmill-2026-07-23.md` in `drive-pr-to-green` for the post-push verify loop and the Evidence Gate freshness vs post-merge-main scope detail
- SOUL.md `push-pr-donot-stop-halfway` — durable state on the remote PR branch IS the deliverable
- SOUL.md `never-push-onto-someone-elses-pr-head` — verify PR author before any push
- `god-mode-generic-mechanic-handoff` §"Branching & clean-replay contract" — this skill is the umbrella Phase 3.5 in-place force-push recipe applied during the PR #8541 cycle (2026-07-23). The god-mode skill points here for the agent-drift recovery pattern.

## Phase 6 — Verify

```bash
# Confirm the new PR has minimal diff
gh pr view <new_pr_number> --json additions,deletions,changedFiles
# Expect: small numbers; 2-5 files typically

# Confirm the old PR is closed
gh pr view <old_pr_number> --json state
# Expect: "CLOSED"

# Confirm no orphaned branches
git branch --list 'fix/<topic>*' | head -5
```

## Pitfalls

- **Dev-server port-race diagnostic (added 2026-07-24, PR #8561):** When the
  evidence-capture flow boots a local Flask/dev server on the canonical port
  (8081 for your-project.com), check FIRST whether another worktree's stale
  server is already bound. The trap is silent: the port returns HTTP 200
  serving a different branch's JS, the capture script screenshots the wrong
  DOM, and the BEFORE/AFTER is comparing against pre-feature code without the
  reviewer ever knowing. The capture script ran fine, the screenshots were
  generated, the GIF was rendered — every layer passed — but the
  `applyMobileScrollLock` + `setupScrollIndicator` calls were never invoked
  because the served JS was 5 lines (404 page) instead of 2700 lines.

  ```bash
  # 1. Check whether the port is already bound
  lsof -nP -iTCP:8081 -sTCP:LISTEN
  # If a process IS already listening: check WHO owns it and WHICH repo it serves.

  # 2. After starting your server, verify the served JS contains the expected
  #    load-bearing functions (NOT just that the port returns 200):
  curl -s -m 5 "http://localhost:8081/frontend_v1/js/campaign-wizard.js" \
    | grep -cE "isMobileViewport|applyMobileScrollLock|wizard-scroll-indicator|setupScrollIndicator"
  # Expected (PR #8561): 15+ matches. If 0, the server is serving the wrong
  # branch — kill it and restart from your worktree.

  # 3. Verify the line count is reasonable
  curl -s -m 5 "http://localhost:8081/frontend_v1/js/campaign-wizard.js" | wc -l
  # Expected: >2000 lines for your-project.com's wizard module. <50 lines
  # means you're serving a 404 page.
  ```

  **Force-kill the stale listener if found:** `kill <pid> && sleep 1 && lsof
  -nP -iTCP:8081 -sTCP:LISTEN` to confirm the port is free. Then start your
  own server with `nohup python3.11 -m mvp_site.main serve > /tmp/server.log 2>&1 < /dev/null &`.

  **Also verify the static path:** the page HTML's `<script src=>` tags
  point to `/frontend_v1/js/...` (NOT `/static/js/...`). A naive curl to
  `/static/js/campaign-wizard.js` returns 404 even when the server is
  serving the right code on the right path.

- **Agent-drift detection (added 2026-07-23, PR #8541):** when an AO worker commits
  the PR, run `git diff --name-only origin/main..HEAD` BEFORE merging. If the diff
  includes files that DON'T match the PR title (e.g. `$PROJECT_ROOT/bq_logging.py`,
  `$PROJECT_ROOT/world_logic.py`, deleted unrelated tests, `roadmap/**`, `.claude/settings.json`),
  the worker bundled its own file edits into the commit. Do NOT merge. Apply Phase 3.5
  in-place force-push replay. Pre-push gate recipe:

  ```bash
  # After worker pushes but before any merge
  git -C <repo> fetch origin
  git -C <repo> diff --name-only origin/main..origin/<branch>
  # Expected: only the files named in the PR body scope.
  # If you see bq_logging.py / world_logic.py / roadmap/** / .claude/settings.json,
  # the worker drifted. Apply Phase 3.5 to replay cleanly.
  ```

  The trap is silent: `gh pr merge` would succeed (CI passes, the drift files are
  unrelated to tests), and the diff would land on main with 5+ files of untracked
  scope drift. The cost is paid on the NEXT PR's review cycle ("why does this PR
  touch `bq_logging.py`?") when a careful reviewer notices the unrelated files.

- **Cherry-pick conflicts that look structural** (whole-file mismatches) usually mean
  the target branch was rebased and the load-bearing commit was already partially
  applied. Check `git log --all --oneline --grep='<keyword>'` for prior art.
- **Do NOT delete the old branch immediately** — leave it for 24h in case CI/CR
  feedback needs to be cross-referenced. Cleanup cron will reap it.
- **Do NOT force-push to the old branch** — that would race with any in-flight
  CR or CI. Open a new branch instead.
- **Tests can pass on the polluted PR but fail on the clean replay** — this means
  the pollution was carrying a hidden test fix that needs to be a separate commit.
  Add it as a follow-up commit and link it in the PR body.

## Phase 5 — Supersede + Stack (the V1+V2 pattern, distinct from cleanup-replay)

This phase covers a different workflow than pollution cleanup: **closing a PR
because the work was logically superseded by a sibling PR on the same topic, then
opening a new PR that stacks cleanly on the prior layer's branch base** so the
diff is minimal and reviewable.

**When to use this phase (not Phase 1–4):**

- PR X carries Layer 1 (e.g. V1 spec, system-agnostic reference doc).
- PR Y (your PR) carries Layer 2 (e.g. V2 overlay on top of V1).
- PR X and PR Y both modify the same files, so PR Y's diff vs `main` shows both
  layers — reviewable but not minimal.
- The user wants a *single self-contained PR* with both layers stacked cleanly.

**Recipe:**

```bash
# 1. Close PR Y as superseded by PR X's branch (not by main).
#    Post a comment explaining the supersede + the new plan.
TOKEN=$(gh auth token)
curl -fsS -X POST -H "Authorization: token $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"body": "Closing as superseded. Layer 2 will land as an incremental
    improvement on top of <PR X URL>. New PR opens with both layers stacked
    cleanly on <PR X branch>."}' \
  "https://api.github.com/repos/<owner>/<repo>/issues/<Y>/comments"
curl -fsS -X PATCH -H "Authorization: token $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"state": "closed"}' \
  "https://api.github.com/repos/<owner>/<repo>/pulls/<Y>"

# 2. Fetch the prior layer's branch so the new branch can base on it.
#    The first `git fetch` will not auto-create origin/<branch> if the ref is
#    unusual — use the explicit refspec form to guarantee it lands.
cd <repo>
git fetch origin 'refs/heads/<X-branch>:refs/remotes/origin/<X-branch>'

# 3. Create the new worktree branched from <X-branch> (NOT from origin/main).
git worktree add -b <Y-plus-branch> ~/.worktrees/<X-Y-stacked> origin/<X-branch>

# 4. Copy your Layer 2 files into the new worktree.
cp ~/.worktrees/<Y-worktree>/<file1> ~/.worktrees/<X-Y-stacked>/<file1>
cp ~/.worktrees/<Y-worktree>/<file2> ~/.worktrees/<X-Y-stacked>/<file2>

# 5. If Layer 2 inserts new sections into a file that Layer 1 also modified,
#    re-apply your insert against the Layer 1 base (the file as it sits on
#    <X-branch>). Use patch with unique anchors.

# 6. Commit + push + open PR with base=main. The diff will be the COMBINED
#    V1+V2 stack, not just V2 — reviewable as a single self-contained unit.
cd ~/.worktrees/<X-Y-stacked>
git add -A
git commit -m "<Y-commit-message>"
git push -u origin <Y-plus-branch>

curl -fsS -X POST -H "Authorization: token $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "<Y-title>",
    "head": "<Y-plus-branch>",
    "base": "main",
    "body": "## V1+V2 self-contained\n\nThis PR stacks the V2 design on top of the V1 base ([PR #X](<X URL>)):\n\n- **V1 ([PR #X](<X URL>))** — <what V1 carries>\n- **V2 (this PR)** — <what V2 carries>\n\nSupersedes <Y-PR-URL>."
  }' \
  "https://api.github.com/repos/<owner>/<repo>/pulls"
```

**Why base=main (NOT base=<X-branch>):** PR reviewers need to see the combined
V1+V2 diff against the canonical target (main). Branching the PR from
<X-branch> would show ONLY the V2 delta — but the user wants one self-contained
PR for review. The trade-off: the diff is bigger, but the reviewer can verify
the full stack in one read.

**Why the explicit `refs/heads/<X>:refs/remotes/origin/<X>` refspec:** When
the prior PR's branch is local-only or just-pushed, `git fetch origin` may NOT
auto-create the remote-tracking ref. Without it, `git worktree add -b X origin/X`
fails with "fatal: not a valid object name: 'origin/X'". The explicit refspec
guarantees the ref is materialized locally.

**Verified 2026-07-21, $GITHUB_REPOSITORY:** PR #8487
(`feat/nocturne-v2-spec`, +503/-0) closed as superseded → PR #8488 opened
(`feat/god-mechanics-v2`, +974/-0, base=main) stacking V1 PR #8484 + V2
overlay cleanly. The combined PR contains both `god_mechanics_general.md` (V1)
+ `nocturne-v2-god-mechanics-design.md` (V2) + Section 9 in
`campaign_module_god_of_murder.md` — fully self-contained for review.

## Pre-push hook blind spots — TWO distinct bugs, both silent

A polluted PR is sometimes caused not by your merge strategy but by your pre-push
hook MISSING a class of leak. Both bugs produce silent failures that let forbidden
content reach origin:

1. **Gitleaks scans the wrong range on new branches** — see
   `references/gitleaks-pre-push-hook-bypass.md`. Hook falls back to
   `rev-list --max-parents=0 HEAD` when `remote_sha` is all-zeroes, scanning the
   entire repo history. The 4259 leaks observed on 2026-07-14 (claude-commands
   PR #329) were all from pre-existing commits, not the new one. Symptom: push
   blocked, but `gitleaks git --log-opts 'origin/main..HEAD'` from inside the
   worktree is clean. Fix: `git -c core.hooksPath= push` for that one push, OR
   patch the hook to use `git merge-base origin/HEAD local_sha`.

2. **Gitleaks doesn't scan path prefixes at all** — see
   `backup-folder-leak-purge` skill. Hook scans for secret patterns
   (`apiKey=`, `token:`, etc.) but never checks path prefixes like `backup/`,
   `snapshot/`, `secrets/`. A `backup/` folder containing your entire `~/` passes
   gitleaks cleanly because no secret regex matches. Verified 2026-07-15 against
   jleechanorg/claude-commands: 491 MiB / 6,820 files pushed to public repo before
   anyone noticed. **Fix:** add a path-prefix check to your pre-push hook that
   runs BEFORE the secret scan — they belong together, not as alternatives.

3. **Pre-push hook stdin field-order trap** — see
   `backup-folder-leak-purge/references/git-hooks-pre-push-stdin-format.md`.
   Per `git/githooks.adoc`: stdin is `<local-ref> SP <local-sha> SP <remote-ref> SP <remote-sha>`.
   Wrong order (`read -r local_sha local_ref remote_sha _`) makes the hook
   silently pass — the comparison `[[ $local_ref == refs/heads/main ]]` evaluates
   a SHA against a ref string and never matches. Run the 3-test harness in
   `backup-folder-leak-purge/scripts/verify-hook-blocks-backup-push.sh` on every
   new pre-push hook BEFORE declaring it done.

## Worked example — 2026-07-14 Visenya V8 stuck-lu

**Polluted PR:** [#8401](https://github.com/$GITHUB_REPOSITORY/pull/8401)
— 22 commits, 31 files, +1413/-629. Branched from `origin/feat/fix-xp-overflow-no-level-up-7931-full-brief-at-tmp-wa-task-i`
which itself had been rebased 8+ times.

**Diagnosis:** `git log --oneline origin/main..origin/fix/visenya-v8-stuck-lu-8400`
showed 19 of 22 commits were noise (`Merge remote-tracking branch`,
`fix(beads): resync issues.jsonl`, `[fixpr jleechan2015-automation-commit]`,
`Merge branch 'main' into feat/...`). The load-bearing commits were only 3:
- `21ccc605e2 fix(level-up): preserve rewards_pending.level_up_available in streaming path`
- `8bd3b9894d fix(level-up): gate streaming path threshold preservation on not level_up_complete`
- `93cc946509 fix(level-up): drop unpaired streaming level-up rewards`

**Clean replay PR:** [#8403](https://github.com/$GITHUB_REPOSITORY/pull/8403)
— 1 commit, 2 files, +597/-20. Cherry-picked the 3 load-bearing commits, resolved
the conflicts in `$PROJECT_ROOT/world_logic.py` (different from PR #7952's branch's
state), added a 4th surgical change for the `level_up_complete` guard, ported
`test_xp_overflow_level_up_ceremony.py`, added `TestCustomLevelCapXpOverflow`
with Visenya V8 fixtures.

**Result:** PR #8401 closed; PR #8403 ready for CI.

## Decision tree — Strategy A vs B

Use this to decide which strategy to apply before opening a worktree:

```
Polluted PR has:
├── 3-5 distinct commits whose messages match the PR scope (plus noise)
│   └── Strategy A (cherry-pick)
├── Entirely noise (only merge commits + beads drift) but file-level diff IS the fix
│   └── Strategy B (extract file diff)
└── Cherry-pick conflicts are structural (whole-file mismatches)
    └── PIVOT to Strategy B (this is the 2026-07-14 Visenya V8 case)
```

**Why the pivot works:** Strategy A fails when the target branch was rebased and the
load-bearing commit was already partially applied (the diff context is stale). Strategy B
extracts the file content directly, which is independent of commit ancestry. Both produce
the same end-state; the difference is whether commit messages are preserved (A) or not (B).

## Trigger phrases

- "clean up this PR"
- "replay this PR"
- "minimal diff replay"
- "fix PR scope"
- "branch is bloated"
- "this PR has too many commits"
- "rewrite this PR cleanly"
- "polluted PR"
- "PR has unrelated history"
- "branch from origin main"
- "pre-push hook not blocking"
- "gitleaks didn't catch this"
- "backup folder in public repo"
- "home dir leaked to github"

## Phase 3.7 — Value retune of an open PR (NOT pollution, NOT supersede)

Distinct from cleanup-replay (pollution) and Phase 5 (supersede+stack): **the user
explicitly wants a single value in an existing PR changed** (constant flap,
threshold flip, percentage change, etc.) WITHOUT polluting the original PR's
branch with unrelated drift that has accumulated since it was opened.

**Symptoms that indicate this pattern:**

- The user names a PR by number and gives a one-line override of one of its
  constants: "cap to 350k instead of 450k", "raise threshold from 5 to 7",
  "change TTL from 30d to 60d".
- The PR's head branch is not yours (different author, or owned by an automation
  cron, or was rebased) — `never-push-onto-someone-elses-pr-head` blocks
  Phase 3.5 in-place force-push.
- The PR's head branch has unrelated drift (worktree-script cleanup, CI workflow
  edits, .claude/settings.json) since its original creation — Phase 3.5 in-place
  replay would commit the drift alongside the retune.
- The retune is small enough (1 constant flap + 1 test class) that opening a new
  PR is clearer than replaying onto the old one.

**Recipe (verified 2026-07-23, $GITHUB_REPOSITORY PR #8537 450K → 350K
retune, branch `fix/8537-cap-350k`):**

```bash
# 1. ALWAYS read the existing PR body first to confirm the retune scope:
gh api /repos/<owner>/<repo>/pulls/<N> | python3 -m json.tool | head -200
# Identify: the load-bearing file(s), the constant(s) in question, and the test
# class that pins the value.

# 2. Branch a fresh worktree from origin/main (NOT from the PR's branch — the
#    existing branch carries drift):
git -C <repo> fetch origin
git -C <repo> worktree add -b fix/<PR>-<new-value> /tmp/wt-<PR>-<new-value> origin/main

# 3. Apply the retune surgically:
cd /tmp/wt-<PR>-<new-value>
# - If only a constant flap: edit the file directly with patch / write_file.
# - If test assertions reference the OLD value, retune the test numbers in the
#   same commit (e.g. 348_351 -> 348_000 for the 350K cap case).
# - Pin the new value with a regression test: `test_cap_value_is_<NEW>` to block
#   silent reverts.

# 4. Verify the diff is minimal (PR-clean-branch-from-main contract):
git -C /tmp/wt-<PR>-<new-value> diff --shortstat origin/main
git -C /tmp/wt-<PR>-<new-value> log --oneline origin/main..HEAD
# Expect: 1-3 files, <500 lines, single commit.

# 5. Commit + push the new branch ONLY. Do NOT auto-open the PR.
git -C /tmp/wt-<PR>-<new-value> add <surgical files>
git -C /tmp/wt-<PR>-<new-value> commit -m "fix(<scope>): <retune description> (clean replay of PR #<N>)"
git -C /tmp/wt-<PR>-<new-value> push -u origin fix/<PR>-<new-value>

# 6. PAUSE HERE. Tell the user the branch is pushed and ask whether to open a
#    new PR. The original PR stays open until the user decides to close it.
#    NEVER auto-open the new PR on a "value retune" — the user often has a
#    different default in mind (this exact case: user said "Hold on this I'll
#    decide later" mid-pipeline).
```

**Why push without auto-opening the PR:** A "value retune" is exactly the kind
of fork that the user wants to inspect before it becomes a PR. The existing
PR is the canonical artifact until the user says otherwise; pushing a new
branch is cheap, opening a new PR creates reviewer noise and (per SOUL.md
`scope-pivot-to-ao`) may cross the write/PR threshold the user did not
authorize. **Push the branch, surface it, wait for the user.**

**Difference from Phase 3.5 in-place force-push:** Phase 3.5 force-pushes
the clean replay onto the SAME PR's branch (same PR number preserved).
Phase 3.7 opens a NEW branch because (a) the existing branch is not yours
to push onto, OR (b) the existing branch has unrelated drift you'd carry
into the replay, OR (c) the user has not yet authorized a new PR.

**Difference from Phase 5 supersede+stack:** Phase 5 closes PR Y as
superseded by PR X (both layers stack cleanly in one self-contained PR).
Phase 3.7 does NOT close the original PR — the user may still want the
original 450K version, or may merge the 350K replay only after a comparison
review.

**Verified 2026-07-23, PR #8537 (450K → 350K retune).** User's mid-pipeline
"Hold on this I'll decide later" landed AFTER I'd already pushed the
clean-replay branch `fix/8537-cap-350k` (1 commit, +103/-1 across
`$PROJECT_ROOT/llm_service.py` constant + `$PROJECT_ROOT/tests/test_context_budgeting.py`
3-test regression suite). No PR was opened. The branch sat pushed waiting
for the user's verdict on whether 350K is the right cap, or whether to
revert to 450K, or to keep both as parameterizable. **Without the
"pause-before-open" rule, I would have auto-opened PR #8548 (or similar)
and forced the user to choose between closing it or merging it
out-of-band — a clear SOUL.md `no-confirmation-gate` and `scope-pivot-to-ao`
boundary violation.**

## Phase 3.8 — Stale-target replay check (origin/main advanced during the worker run)

Distinct from Phase 3.7 (value retune) and Phase 5 (supersede+stack): the replay target value
the user originally chose may have become **stale** because `origin/main` advanced between
the dispatch and the worker's push. The replay branch is then technically
clean-from-origin/main-at-dispatch-time, but the target value is already BELOW (or above) the
current main value — the replay is a no-op or a regression.

**Symptoms that indicate this pattern:**

- The replay branch is clean (2 files, < 500 lines, single commit), all CI green, `mergeable=CONFLICTING` (`mergeStateStatus: dirty`).
- The PR's diff is `300_000 → 350_000` in `$PROJECT_ROOT/llm_service.py`, but origin/main HEAD already has `400_000` in that exact line (because a sibling PR merged between dispatch and now).
- The `git log origin/main -- <target-file>` shows commits between the dispatch base and current HEAD that touched the same constant.
- The worker's branch base SHA is older than the most recent main commit (verify with `git fetch origin` then `git log --oneline origin/main -5` and compare to the branch's first-parent merge-base).

**Why this matters:** The replay is technically clean from origin/main at the worker's
branch base, but the value retune made **no semantic progress** relative to current main.
Merging it would **revert** a sibling PR's mainline change. The clean-from-main audit
(`git diff --shortstat origin/main..HEAD`) doesn't catch this because the branch's base
IS origin/main — the diff is just the worker's change. The stale-target check is a
**semantic** check on the diff's expected post-merge state, not a structural diff audit.

**Recipe (verified 2026-07-24, PR #8537 350K replay vs main #8555 400K):**

```bash
# 1. Identify the target value in the replay branch
cd /tmp/<replay-wt>
REPLAY_VALUE=$(grep -E 'DEFAULT_COMPACTION_TOKEN_LIMIT\s*=\s*[0-9_]+' $PROJECT_ROOT/llm_service.py)
echo "replay: $REPLAY_VALUE"

# 2. Identify the current value in origin/main
git fetch origin main
git show origin/main:$PROJECT_ROOT/llm_service.py | grep -E 'DEFAULT_COMPACTION_TOKEN_LIMIT\s*=\s*[0-9_]+'
# Output: DEFAULT_COMPACTION_TOKEN_LIMIT = 400_000

# 3. Compare. If replay target < current main value, the replay is stale.
#    (For "raise X" tasks, the symmetric check is replay target > current main.)

# 4. ALSO check the test file: the replay's regression test pins the
#    replay value. If the test classes reference the current main value,
#    the test was written against an old target and may not pin the new state.
git diff origin/main HEAD -- $PROJECT_ROOT/tests/<test_file>.py | grep -E "test.*[0-9]{3,}_000|cap_to_[0-9]+"
```

**If the replay target is stale:**

1. **Surface in the dispatcher's status reply** — the user originally chose the replay target
   to **override** the original PR's value. If the original PR's value is no longer on main
   (it was reverted to a different value by a sibling PR), the user's override premise has
   changed. Ask the user: "Replay target (350K) is now BELOW current main (400K — PR #8555
   merged between dispatch and now). Did you still want to override to 350K, or do you want
   to retarget the replay to 400K (current main, no-op change)?"

2. **Do NOT auto-rebase + retarget** — silently changing the replay target is a SOUL.md
   `no-confirmation-gate` violation. The user explicitly chose the target value; the
   fact that main moved is a SIGNAL to ask, not a license to change it.

3. **Do NOT auto-close the replay PR** — even if the replay is now a regression, the
   user may still want to merge it (e.g., to undo the sibling PR's change). Close only
   on explicit user direction.

**Three durable fixes the dispatcher should consider for FUTURE replays:**

1. **Pre-dispatch target-vs-main check** — at dispatch time, before spawning the worker,
   run `git show origin/main:<file> | grep <target-value-or-pattern>` and confirm the
   replay target is still meaningfully different from current main. If main already has
   the replay target, abort the dispatch and tell the user "replay target already on main,
   no work needed."

2. **Mid-run main-advance check** — for long-running workers (>30 min), add a Phase 0.5
   pre-flight at the worker's commit-and-push time: `git fetch origin main && git diff
   --shortstat origin/main..HEAD` AND `git log origin/main -- <target-file>` to confirm
   the target value hasn't been touched by a sibling PR. If it has, post a status update
   in the originating thread and ask the user before pushing.

3. **Sibling-PR-time-window-narrowed query** — if the user knows the dispatch's time
   window, narrow the sibling-PR check to `gh pr list --state merged --merged
   <dispatch-time>..NOW --search "<constant-name>"`. This avoids the false-positive of
   "PR #8555 merged 400K last week" when the dispatch was yesterday.

**Verified case 2026-07-24, $GITHUB_REPOSITORY PR #8537 350K replay:**

- User asked for 350K cap override of PR #8537's 450K value (2026-07-23, thread
  `C0AH3RY3DK6/1784866738.297949`, "I said a million times to get this to 350k max tokens
  get it done").
- PR #8555 ("reduce DEFAULT_COMPACTION_TOKEN_LIMIT 450k → 400k") merged to origin/main
  at `c5b759d974` between the user's message and the dispatch spawn.
- AO worker `worldarchitect-121` spawned at 2026-07-24T05:52Z, branched from origin/main
  at `5d14bb1013` (PR #8537 merge SHA), created PR #8556 with 350K retune. Branch is
  clean (2 files, +37/-120), all 22 CI checks PASS, CodeRabbit APPROVED, Bugbot NEUTRAL.
- However, `mergeable=CONFLICTING` because origin/main advanced to `c5b759d974` after
  the worker branched. Same file (`$PROJECT_ROOT/llm_service.py`) and same test file
  (`$PROJECT_ROOT/tests/test_context_budgeting.py`) modified by PR #8555.
- **Replay target value (350K) is now BELOW current main (400K).** The replay is a
  technical cleanup but a semantic regression if merged.
- The user's override premise (350K vs 450K) is no longer the right comparison; the
  right question is now "350K vs 400K" and the user has not been asked.

**Why this is a §"Stale-target" pitfall and not a Phase 3.5 (pollution) case:**

Phase 3.5 is for when the PR carries **unrelated diff** (drift files, merge commits,
beads.jsonl). The replay PR is clean — the only issue is the target value is wrong
**relative to current main**. The fix is NOT a force-push replay; the fix is a value
re-decision by the user, followed by a rebase + retune or a close-and-reopen.

**Why this is a §"Stale-target" pitfall and not a Phase 5 (supersede+stack) case:**

Phase 5 is for when the user's PR is logically superseded by a sibling PR (e.g., the
sibling PR is the canonical artifact). In this case, the user's replay PR is a
**rejection** of the original PR's value, not a sibling of any subsequent PR. The
sibling PR (#8555) is itself a downgrade of #8537, and the user's 350K is a further
downgrade. The user may want to (a) merge 350K anyway and downgrade #8555's 400K, or
(b) abandon 350K and accept 400K, or (c) re-raise to 500K. The three options
fundamentally diverge on user intent — auto-deciding is wrong.

**Cross-links:**

- `references/stale-replay-target-detection-2026-07-24.md` — the full evidence file:
  three sibling PRs (#8537 450K, #8555 400K, #8556 350K-replay), the dispatch time
  window, the `mergeable_state: dirty` even-when-CI-green signal, and the three-option
  decision matrix. (Authored after skill update.)
- PR babysit loops — the babysit should treat `mergeable_state:
  dirty` + `check-rollup.status: success` as a **stale-target signal**, not a CI failure.
  Post the three-option question to the originating thread; do NOT auto-nudge the worker.
- `dispatch-task` §"Pre-compute target-vs-main check" — the durable fix at dispatch time.

## Changelog
- **1.7.0 (2026-07-24):** Add Phase -0.5 — Writable-remote base selection. The fork-vs-upstream
  mistake: branching from `origin/main` (read-only upstream) and pushing to `fork`
  (writable fork) creates a 600k-line "polluted" PR because the fork is 6,000+ commits
  ahead. Recipe: `gh api repos/<path>/permissions.push` per remote, `git rev-list
  --left-right --count origin/main...fork/main` to measure divergence, base on the
  WRITABLE remote's main. When upstream's file structure diverged from the fork's
  (e.g. `tools/daemon_pool.py` upstream → inlined `tools/async_delegation.py`
  in fork), port the patch conceptually to the fork's symbol location via
  `git grep -n 'class.*DaemonThreadPoolExecutor\|def _adjust_thread_count'` then
  `patch` / `write_file` instead of `git apply`. Verified PR #3 → PR #4 cleanup
  on jleechanorg/hermes-agent (+600,146/-93,707/3,930 files polluted → +25/-6/1
  file clean). Diagnostic symptom: PR shows >1000-line additions in dozens of
  unrelated files (configs, workflows, AGENTS.md) — that is wrong-base-branch
  pollution, NOT agent drift; recovery is rebase-on-fork-main, NOT Phase 1/3.5
  cleanup-replay. Reference: `references/fork-vs-upstream-writable-base-2026-07-24.md`.
- **1.6.0 (2026-07-24):** Add Phase 1 Strategy B Variant — Surgical 2-hunk `patch` apply
  when `origin/main` has accumulated overlapping edits in the load-bearing files. The
  naive `git checkout origin/<branch> -- <file>` silently reverts main-side improvements
  (verified PR #8139 → PR #8561, 2026-07-24: `app.js` checkout reverted 554 lines of
  main-side route-handling/draft-persistence code that landed after 8139 was first opened).
  Recipe: compute `git diff origin/main...HEAD -- <file>`, identify hunks that match the
  load-bearing function calls (e.g. `applyMobileScrollLock`, `setupScrollIndicator`),
  exclude hunks that revert main-side state, write a custom patch file, apply with
  `patch -p1`. Also add Pitfalls: dev-server port-race diagnostic — verify served JS
  contains expected functions (e.g. `grep -cE 'applyMobileScrollLock|setupScrollIndicator'`)
  and reasonable line count (>2000 for your-project.com's wizard module), NOT just
  HTTP 200. The trap is silent: a stale server on port 8081 from another worktree serves
  5-line 404 pages that pass the capture script's every layer, generating screenshots
  against the wrong code. New reference `references/strategy-b-surgical-patch-port-race-2026-07-24.md`
  captures the full transcript.
- **1.5.0 (2026-07-24):** Add Phase 3.8 — Stale-target replay check. The replay target value
  the user chose at dispatch may be stale because `origin/main` advanced between dispatch
  and the worker's push. Verified on $GITHUB_REPOSITORY PR #8537 350K replay
  (PR #8556): worker branched from origin/main at `5d14bb1013` (PR #8537 merge SHA), but
  PR #8555 merged at `c5b759d974` between dispatch and push, advancing main to 400K. The
  350K replay is now BELOW current main. The replay is technically clean (all 22 CI checks
  PASS, CodeRabbit APPROVED), but `mergeable=CONFLICTING` (`mergeStateStatus: dirty`) AND
  the replay target is semantically stale. The fix is NOT a force-push replay; the fix is a
  user re-decision (rebase+retarget to 400K / keep 350K / re-raise). The dispatcher must
  surface the three-option question; do NOT auto-decide. Companion: pre-dispatch target-vs-main
  check (in `dispatch-task`), mid-run main-advance check (in the PR babysit loop),
  and sibling-PR-time-window-narrowed query (in `references/stale-replay-target-detection-2026-07-24.md`).
- **1.4.0 (2026-07-23):** Add Phase 3.7 — Value retune of an open PR (clean replay
- **1.4.0 (2026-07-23):** Add Phase 3.7 — Value retune of an open PR (clean replay
  of a single constant/value). Verified on $GITHUB_REPOSITORY PR #8537
  (450K → 350K retune, branch `fix/8537-cap-350k` pushed without auto-opening a PR).
  Distinct from Phase 3.5 (in-place force-push) and Phase 5 (supersede+stack).
  The defining trait: a one-line value change the user wants to evaluate against
  the original before committing to a new PR. **Push the branch, surface it, wait
  for the user — NEVER auto-open.** The "I'll decide later" mid-pipeline signal is
  a hard boundary; do not cross it.
- **1.3.0 (2026-07-23):** Add Phase 3.5 — In-place force-push replay (same PR number, NOT
  close-and-reopen). Verified on $GITHUB_REPOSITORY PR #8541 — AO worker
  shipped polluted commit `0c5a2b6a64` (9 files / +706 / −424 with 5 drift files);
  recipe applied via `git show <bad-sha> -- <four intended> | git apply --include=<each>`
  + `git push --force-with-lease origin <branch>`; clean replay HEAD
  `0b0bc4ac73521c14b402d0c5dd1211730479a469` (4 files / +651 / −0). Same PR, same
  branch, same issue link. The recipe (Strategy B file-level extraction) was already
  in Phase 1; what was missing was the in-place force-push variant of Phase 3.
  Default is now in-place force-push when the PR was already opened with the correct
  title/base/issue-link; close-and-reopen is the LAST resort escape hatch.
  Cross-linked from `god-mode-generic-mechanic-handoff` §"Branching & clean-replay
  contract" §4.
changelog:
  - "1.1.0 (2026-07-21) Add Phase 5 — Supersede + Stack (the V1+V2 pattern) covering the case where PR Y is logically superseded by PR X's branch (NOT polluted) and the user wants a single self-contained PR with both layers stacked cleanly. Recipe includes: closing PR Y via REST API with a comment, fetching the prior layer's branch with explicit refspec (`refs/heads/<X>:refs/remotes/origin/<X>`) because plain `git fetch` may not materialize the remote-tracking ref, creating the new worktree from `origin/<X-branch>` (NOT from origin/main), copying Layer 2 files, and opening the new PR with `base=main` so reviewers see the combined V1+V2 stack. Verified 2026-07-21 on $GITHUB_REPOSITORY PR #8487 (closed as superseded) → PR #8488 (V1+V2 self-contained, +974/-0). Distinct from cleanup-replay Phase 1-4 (which handles pollution). The key discriminator: superseded-by-design (Phase 5) vs polluted-by-mistake (Phase 1-4). Bumped version + added trigger phrase 'this PR is superseded by X' / 'close and stack on V1 branch' / 'integrate into the new PR'."
  - "1.0.2 (2026-07-15): Add \"Pre-push hook blind spots\" section covering
  TWO gitleaks failures (wrong-range on new branches + no-path-prefix checks)
  and the stdin field-order trap. Cross-link `backup-folder-leak-purge` skill.
  Bumped version + extended trigger phrases.
- **1.0.1 (2026-07-14):** Add tags + category + Decision tree (Strategy A vs B pivot
  rationale). Cross-link to harness-postmortem Phase 1.5c and
  `references/polluted-pr-cleanup-replay.md`. Originating incident: PR #8401 (Visenya V8
  stuck-lu) closed; clean replay at PR #8403 (2 files, +597/-20).
- **1.0.0 (2026-07-14):** Initial authoring.

## Related

- SOUL.md `## COMMIT: pr-clean-branch-from-main-no-history-bloat` (the trigger-based
- SOUL.md `## COMMIT: never-push-onto-someone-elses-pr-head` (Phase -1 prevention)
- SOUL.md `## COMMIT: push-pr-donot-stop-halfway` (durable state on the remote PR branch)
- `dispatch-task` Phase 0.5 PR-topology pre-flight — should grow a sibling
  "writable-remote check" gate: dispatchers should verify `gh api
  repos/<path>/permissions.push` per remote AND `git rev-list --left-right
  --count origin/main...fork/main` before `git worktree add -b fix/x`. The
  fork-vs-upstream pollution case (PR #3 → PR #4) shows the gap.
- `github-pr-workflow` — base-branch / fork-remotes interaction (the upstream
  skill on PR lifecycle; this skill operationalizes the "wrong base remote" recovery)
- `apply-supplied-patch-and-open-pr` — for the case where the patch is
  generated against one remote and must be applied to another (Phase -0.5's
  "port upstream patch to fork" recipe overlaps with this skill's path-rewrite
  recipe)
- `harness-postmortem` Phase 1.5c (parent meta-skill — classifies this as
  rule that fires this skill)
- `.cursor/rules/pr-branch-from-main.mdc` (the project-level rule this skill
  operationalizes)
- `harness-postmortem` Phase 1.5c (parent meta-skill — classifies this as
  `ta[REDACTED_OPENAI_KEY]` + `wrong-tool-discussed`, MAST FC1+FC3,
  ETCLOVG Tool+Verification)
- `harness-postmortem/references/polluted-pr-cleanup-replay.md` (the detection
  recipe + pre-push audit checklist)
- `backup-folder-leak-purge` (sister skill — the path-prefix leak variant that
  caused 2026-07-15's 491 MiB public-repo incident; this skill covers the
  gitleaks-side, that one covers the path-prefix side)
- `tests/test_pr_clean_branch_contract.py` (5 contract tests verifying the rule
  + skill structure)
