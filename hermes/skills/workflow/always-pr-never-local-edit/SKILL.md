---
name: always-pr-never-local-edit
version: 1.6.0
description: Never just make local edits and stop. Always create a GH issue + bead, dispatch via ao spawn for a PR, and skillify the pattern. Local exploration is fine; local edits without a PR are a process violation.
changelog:
  - "1.6.0 (2026-07-28): New section 'Dirty-checkout pre-flight — refuse to dispatch onto a dirty or conflicted worktree'. Before any claudem / ao / opencode / Codex dispatch, scan every candidate worktree + the main checkout for clean state. Dispatching onto a dirty worktree silently mixes your PR's commits with someone else's WIP; dispatching onto a conflicted worktree (`UU`/`AA`/`DD` rows in `git status --short`) makes the worker's first patch land on top of an unresolved merge. Verified 2026-07-28 on $GITHUB_REPOSITORY: the available main checkout had 3 modified `analysis/*` files + 2 modified `$PROJECT_ROOT/*.py` + multiple untracked files (dirty); the alternate checkout had unresolved `UU .claude/commands/code-standards.md` (conflicted). Both are no-go; correct move is `git worktree add -B <topic> <path> origin/main` for a fresh clean branch."
  - "1.5.0 (2026-07-18): New section 'Worktree-silent-edit trap — when the worktree has no ./venv/' covering the dual-CWD silent failure where `patch` or `cp` from the wrong CWD lands edits in the main checkout instead of the worktree, with NO error message. Verified on $GITHUB_REPOSITORY PR #8446 (2026-07-18, SHA 4524525569692db3e5a5b36a818a7248b65fae09): the prompt edits + test file landed in the main checkout (on branch `docs/bq-cost-spike-2026-07-08-findings`) instead of the worktree's `fix/aegon-rejoin-co-presence-8444` because the worktree had no `./venv/` and I `cd`'d to the main checkout to run `pytest`. Detection heuristic: after every `patch` on a worktree, run `git status --short` on BOTH the worktree AND the main checkout — the main checkout MUST be empty. Recovery recipe: `cp` the file to the worktree, `git checkout -- <file>` in the main checkout to revert, then verify with the dual-status check. Cross-references skill `repro` §'Git worktree pitfall → Worktree-silent-edit trap' and `references/prompt-fix-deliverable-shape-2026-07-18.md` §Pitfall 1."
  - "1.4.0 (2026-07-15): Two new sections. (a) 'Worktree test-import via Path.home() quirk' — when a test file imports the source via `Path.home() / '.hermes' / 'scripts' / '<watcher>.py'` instead of a worktree-relative path, pytest runs against the deployed prod copy and all new-wording tests fail with confusing substring errors. The 4-step temp-copy/restore work-around plus a detection heuristic. Verified on jleechanorg/jleechanclaw#781 (first test run had 4/11 failures, all false alarms). (b) 'Local git fetch auth-block work-around for jleechanclaw' — `git fetch origin main` fails with `Authentication failed` because the `origin` URL contains a truncated placeholder token (`x-access-token:ghp_yg....git`). `gh auth setup-git` alone doesn't fix it. The two-step fix: `git remote set-url origin https://github.com/jleechanorg/<repo>.git` + explicit `'$HOME/.local/bin/gh.real auth git-credential'` helper."
  - "1.3.0 (2026-07-14): New section 'Bidirectional command pointer pattern — user-scope vs repo-local' with the 5-rule user-scope contract, repo-local contract, recipe for authoring a new bidirectional command, and the verified case (jleechanorg/claude-commands PR #328 + $GITHUB_REPOSITORY PR #8402). Covers the cross-repo discipline when a slash command exists in BOTH ~/.claude/commands/<name>.md (user-scope, mounted from jleechanorg/claude-commands) AND <product-repo>/.claude/commands/<name>.md (repo-local)."
  - "1.2.0 (2026-07-13): Added 'Cross-repo pre-flight — find the right repo before opening the PR'. Recurring-alert pattern lesson from MCP Agent Mail `is_test IS NULL` watcher (jleechanclaw #774): the watcher script lives in jleechanorg/jleechanclaw, the BQ data lives in your-project.com — opening the PR in the wrong repo wastes a worktree. Recipe: trace the alert source to its origin repo before opening the PR."
  - "1.1.0 (2026-07-12): Added two new sections. (a) 'PR-topology pre-flight — iterate, don't proliferate': when handed a bug-fix task, check `gh pr list` for an existing PR covering the same issue BEFORE opening a new one; push improvements to the existing branch instead. Verified on merge_train #42 where PR #41 already covered the same fix. (b) 'Wind-down checkpoint — the WIP-pushed end-state': when the user signals immediate pause/restart, the right end-state is WIP commit + push to working branch + reply with branch/SHA/empty `git status --porcelain`. Do NOT merge, do NOT push to `main`, do NOT touch deploy surfaces."
---

# always-pr-never-local-edit

## Trigger
Any time you find yourself editing files locally (outside an ao worktree) without a PR in progress.

## Rule

**NEVER make local edits and stop.** Every change that modifies source must end with a PR. The workflow is:

1. **Investigate locally** — read files, search code, understand the problem. This is fine.
2. **Create GH issue + bead** — `gh issue create` + `br create`. Mandatory before any edits.
3. **Dispatch via `ao spawn`** — let the worker do the edits in its own worktree and create a PR.
4. **Skillify the pattern** — if you learned something reusable, create/update a skill.

### What counts as "local edits and stop"
- Editing files in the main checkout without pushing or creating a PR
- Making code changes in a session that ends without a PR URL
- Investigating, finding the fix, applying it locally, then telling the user "done" with no PR

### What's allowed locally
- Read-only exploration: `search_files`, `read_file`, `grep`, `git log`, `gh` queries
- Writing temporary files (scripts, tests) that you run and discard
- Creating issues, beads, cron jobs, memory entries

## Why

Local edits in the main checkout:
- Create drift between main and production
- Can't be reviewed or rolled back
- Get lost when the next checkout overwrites them
- Bypass CI and evidence standards

A PR is the minimum unit of done-ness. No PR = not done.

## Skillifying the pattern

When `/skillify` is requested, create a **general** skill — not one specific to the current project or file. Ask: "Would this pattern apply the same way in any repo?" If yes, make it general.

Examples:
- ✅ `always-pr-never-local-edit` — general workflow pattern
- ❌ `campaign-field-editability` — too specific to one project's one feature

If the pattern has reusable project-specific details (file paths, class names), put those in the GH issue or memory, not in the skill.

## Recovery
If you catch yourself making local edits:
1. Stop immediately
2. `git stash` or `git checkout -- .` to undo
3. Create the GH issue + bead
4. Dispatch via `ao spawn` with the full task description
5. Don't resume local edits

## PR-topology pre-flight — iterate, don't proliferate (added 2026-07-12)

Before opening a new PR for a known bug or issue, check whether an existing PR already covers it. If yes, **push your improvements to that branch instead of opening a parallel PR**. This is the "pr-quantity-control: iterate, don't proliferate" rule from `finish-the-job` v1.11.0 extended to the local-edit workflow.

**The trap:** when handed a bug-report-style task (e.g. "fix issue #42"), the natural Phase 2 instinct is "open a new PR against `origin/main`". If `gh pr list` reveals an already-open PR covering the same issue, pushing a parallel branch creates reviewer work, evidence-bundle conflicts, and merge-order race conditions.

**Recipe (run BEFORE `git worktree add -b <new>` or `gh pr create`):**

```bash
# 1. List open PRs matching the topic
gh pr list --repo <OWNER>/<REPO> --state open \
  --json number,title,headRefName,additions,changedFiles \
  --jq '.[] | "\(.number) [\(.state)] \(.headRefName) +\(.additions)/-\(.deletions) files=\(.changedFiles)"'

# 2. Verify the existing PR covers the issue
gh pr view <N> --repo <OWNER>/<REPO> --json body \
  --jq '.body' | grep -E "<issue-number|keywords>"
```

**Decision matrix:**

| Existing PR state | Action |
|---|---|
| 0 matches | Normal flow — open new PR from a fresh branch off `origin/main` |
| 1 match, covers the issue | Iterate on its branch: `git worktree add -b <topic>-improvements <path> origin/<existing-branch>`, push commits there, comment on the PR instead of opening a new one |
| 1 match, but unrelated (false positive) | Normal flow — open new PR |
| ≥2 matches | Load `dispatch-task` skill to triage which is canonical |

**Verified case 2026-07-12, jleechanorg/merge_train issue #42:** PR #41 (`fix/pretooluse-approve-decision`) was already open with the same bug fix — Codex-driven, CI green, CodeRabbit APPROVED, 5 days unmerged. The natural Phase 2 reflex was "open a new PR". The user pushed back: *"iterate on PR #41 — do NOT open a duplicate PR (pr-quantity-control: iterate, don't proliferate)"*. I created `work/pr41-improvements` branched off `origin/fix/pretooluse-approve-decision`, pushed improvements there. No duplicate PR; the existing PR gets the better fix on its existing branch.

## Push onto existing PR's headRefName from a separate worktree (added 2026-07-14)

When you don't own the existing PR (someone else authored it, or an automated worker has been pushing commits) and your task is "add these changes to that PR", the recipe is:

1. **Resolve the PR head branch** — `gh pr view <N> --repo <OWNER>/<REPO> --json headRefName,headRepository` (NEVER guess; the user might rename it).
2. **Create a worktree tracking that exact branch** — `git -C <REPO> worktree add -B <my-topic-branch> <WORKTREE_PATH> origin/<headRefName>`. Use `-B` (force-create) rather than `-b` (fail if exists) since the worktree is fresh.
3. **Commit on your topic branch** — `git -C <WT> add <paths>` (path-scoped, NEVER `git add -A` if there's any chance of foreign staged work) → `git -C <WT> commit -m "..."`.
4. **Push onto the PR head ref** — `git -C <WT> push origin HEAD:refs/heads/<headRefName>`. This adds your commit ON TOP of the existing PR's head, so the PR's UI shows it as a new commit and reviewers see it as part of the same PR — no parallel PR, no merge queue contention.
5. **Verify** — `git -C <WT> rev-parse origin/<headRefName>` returns your new SHA. Note: `gh pr view <N> --json head_sha` may show a stale SHA (the PR cache lags the push by ~30s); the local `git rev-parse origin/<headRefName>` is authoritative.

**The trap:** the natural instinct when you don't own a branch is `git worktree add -b <new> origin/main`, then `git push origin <new>`, then open a new PR. That creates the duplicate PR `finish-the-job` v1.11.0 + `always-pr-never-local-edit` v1.1.0 / v1.2.0 all warn against. The "push onto existing headRefName" pattern avoids the duplication entirely.

**Verified case 2026-07-14, jleechanorg/claude-commands PR #321:** PR #321 (`fix: launch real Sonnet Claude teams via tmux`, head `fix/real-claude-team-tmux`, owned by another actor with 670k LOC / 3001 files changed) already had the canonical surface for sidekick + swarm + test_real_claude_team_contract. A 5-minute checkpoint cadence contract was needed on the same files. The recipe: created `~/.worktrees/cc-pr321-checkpoint` tracking `origin/fix/real-claude-team-tmux` (NOT `origin/main`), committed the contract on `fix/sidekick-5min-checkpoint-pr321`, pushed with `git push origin HEAD:refs/heads/fix/real-claude-team-tmux`. The push landed: `286311a97..7c5031623` on `fix/real-claude-team-tmux`. Two commits (`7c5031623` initial + `1a43307a0` /advice Round 2 tightening) now sit on top of the existing PR's head. No parallel PR; reviewers see the contract changes as additional commits on PR #321.

**Anti-pattern:** `git worktree add -b docs/sidekick-5min-checkpoint origin/main` + opening a new PR. This creates the duplicate PR problem `always-pr-never-local-edit` v1.1.0 was designed to prevent.

## Worktree-silent-edit trap — when the worktree has no ./venv/ (added 2026-07-18)

When you create a fresh `git worktree add -b <branch> origin/main` for a PR, the worktree has the source files but **does NOT have `./venv/`** (the Python venv lives only in the main checkout). When you `cd` to the worktree to `patch` prompt files / write tests, you can't run `pytest` (no venv). The reflex: `cd $HOME/projects/<main>` to use the venv, then keep editing — except now your `patch` and `cp` commands write to the **main checkout**, not the worktree.

The trap: **there is NO error message.** `patch` succeeds (file exists in main checkout too), `pytest` runs (venv is in main checkout), tests pass (because the file is correct). The edits look correct in the test run, but they were applied on a different branch than the PR branch. The PR commits land on whatever branch the main checkout is on, not on the worktree's `fix/<topic>` branch.

**Detection heuristic (mandatory after every patch on a worktree):**

```bash
# After EVERY patch, run BOTH status commands:
cd $HOME/projects/wt-<topic>
git status --short          # MUST show the patched files
git rev-parse --abbrev-ref HEAD   # confirm branch is what you think

cd $HOME/projects/<main-checkout>
git status --short          # MUST be empty after a worktree-local edit
```

If the main checkout shows the file as modified, the patch landed in the wrong place.

**Recipe for staying in the worktree (when you need the venv):**

The worktree's tests can run with the main checkout's venv via absolute path:

```bash
cd $HOME/projects/wt-<topic>
# Use the main checkout's venv explicitly — patches still write to the worktree
/path/to/<main-checkout>/venv/bin/python -m pytest $PROJECT_ROOT/tests/<test>.py -v

# OR copy test file to the main checkout's tests dir, run, then revert
cp $PROJECT_ROOT/tests/<test>.py $HOME/projects/<main>/$PROJECT_ROOT/tests/<test>.py
TESTING_AUTH_BYPASS=true $HOME/projects/<main>/venv/bin/python -m pytest $PROJECT_ROOT/tests/<test>.py -v
# Verify, then revert the main checkout's tests dir (NOT the worktree's)
cd $HOME/projects/<main>
git checkout -- $PROJECT_ROOT/tests/<test>.py
```

The second pattern is safer because it leaves the test file under your natural test-discovery rootdir (the main checkout's `$PROJECT_ROOT/tests/`).

**Recovery if you've already shipped the edit to the wrong branch:**

```bash
# 1. Confirm the wrong-branch symptom
cd $HOME/projects/<main>
git status --short                # shows the file as modified here

# 2. Revert the main checkout (so it stays clean)
cd $HOME/projects/<main>
git checkout -- <file-path>

# 3. Copy the file to the worktree
cp <file-path> $HOME/projects/wt-<topic>/<file-path>

# 4. Verify the worktree now has it
cd $HOME/projects/wt-<topic>
git status --short                # MUST show <file> as modified

# 5. Verify the main checkout is clean
cd $HOME/projects/<main>
git status --short                # MUST be empty
```

**Verified case 2026-07-18, $GITHUB_REPOSITORY PR #8446:** the prompt edits (`$PROJECT_ROOT/prompts/planning_protocol.md` + `$PROJECT_ROOT/prompts/narrative_system_instruction.md`) and the new test file (`$PROJECT_ROOT/tests/test_planning_block_canonical_state_anchor_8444.py`) all landed in the main checkout first (no error). The main checkout was on branch `docs/bq-cost-spike-2026-07-08-findings`; the worktree was on `fix/aegon-rejoin-co-presence-8444`. Caught via `git status --short` on both directories. ~3 tool calls wasted. Without the dual-status check, the PR would have shipped on `docs/bq-cost-spike-2026-07-08-findings`, NOT on the intended `fix/aegon-rejoin-co-presence-8444` branch — and the PR number would have referenced a docs branch instead of the fix branch.

**Cross-reference:** skill `repro` §"Git worktree pitfall → Worktree-silent-edit trap" and `references/prompt-fix-deliverable-shape-2026-07-18.md` §"Pitfall 1 — Edits landed in the wrong checkout (silent failure)" for the full recipe and a parallel example.

## Bidirectional command pointer pattern — user-scope vs repo-local (added 2026-07-14)

When a slash command exists in BOTH `~/.claude/commands/<name>.md` (user-scope, mounted from `jleechanorg/claude-commands`) AND `<product-repo>/.claude/commands/<name>.md` (repo-local), the two files MUST form a **bidirectional pointer contract**:

**User-scope contract (lives in `~/.claude/commands/<name>.md`):**
1. Stays **project-agnostic** — no hardcoded paths to a specific product repo.
2. Documents that any repo-local `.claude/commands/<name>.md` MAY override specific lanes (e.g. add `/thermo` lane) but MUST inherit the 4 user-scope lanes (ponytail, ZFC, the applicable repository-local ZFC specialization, root-cause-first).
3. **Reciprocal pointer** — explicit "If a repo-local file exists at `<repo>/.claude/commands/<name>.md`, that file MUST also be loaded; load both."

**Repo-local contract (lives in `<product-repo>/.claude/commands/<name>.md`):**
1. **Top-of-file rule**: "MUST be loaded along with `~/.claude/commands/<name>.md`" as the first line after the YAML frontmatter.
2. Defines repo-specific behavior (e.g. `/thermo` lane, `/es` evidence rule) without forking the 4 user-scope lanes.
3. **Reciprocal pointer** back to `~/.claude/commands/<name>.md` documenting which lanes are added vs. inherited.

**Verified case 2026-07-14 (jleechanorg/claude-commands PR #328 + $GITHUB_REPOSITORY PR #8402):** the `/code-standards` command existed in both locations but the user-scope copy was worldarchitect-flavored (referenced the worldai repo as the canonical) and the worldai copy didn't have the reciprocal "load user-scope" rule. Both rewrites land in their respective repos via PR #328 and PR #8402.

**The trap:** writing one copy of the command and assuming it'll be loaded consistently across repos. Repo-local Claude agents load the user-scope command by default but DO NOT auto-load a sibling file at `<repo>/.claude/commands/<name>.md` unless the user-scope file (or the agent's harness) explicitly says "also load the repo-local counterpart."

**Recipe for authoring a new bidirectional command:**

1. **User-scope side first** (in `jleechanorg/claude-commands` worktree, branch off `origin/main`):
   - Write the project-agnostic command at `.claude/commands/<name>.md`.
   - Add a `## Bidirectional pointer contract` section that lists the 5 rules above.
   - Open PR against `jleechanorg/claude-commands`.
2. **Repo-local side** (in `<product-repo>` worktree, branch off `origin/main`):
   - Write the repo-specific overlay at `.claude/commands/<name>.md`.
   - Add the "MUST be loaded along with `~/.claude/commands/<name>.md`" rule at the top.
   - Add a `## Bidirectional contract` section that documents which lanes are added vs. inherited.
   - Open PR against `<product-repo>`.
3. **Both PRs MUST reference each other** in the PR description (one sentence: "Paired with PR #N in <other-repo>").
4. **For commands that exist in `~/.claude/commands/` but are wholly repo-specific** (e.g. `end2end-testing.md`, `benchg-ts.md`, `worldai-usage-email.md`), add a `> Worldai-only command. <description>.` banner block at the top, then a `## Repo-local counterpart` section pointing at `<product-repo>/.claude/commands/<name>.md`. Do NOT remove the user-scope file — leave the banner so anyone running the command from outside the product repo sees the scope warning.
5. **Create the repo-local pointer file** in `<product-repo>/.claude/commands/` (thin YAML frontmatter + 2-3 line pointer back to the user-scope command) so the product repo has a complete command surface.

**Why two repos, not one:** the user-scope `~/.claude/commands/` is shared across ALL `jleechanorg/*` repos via the `jleechanorg/claude-commands` worktree. The repo-local `<product-repo>/.claude/commands/` is loaded only when the agent is invoked from inside that product repo. Splitting them lets the same command have different lane sets per repo without forking the user-scope copy.

## Cross-repo pre-flight — find the right repo before opening the PR (added 2026-07-13)

Before opening a new PR, confirm the change belongs in the repo you're targeting. Recurring alerts and cross-cutting tools often live in a different repo than the product code they monitor. Opening the PR in the wrong repo means the worktree, CI, reviewers, and reviewer-bot signals all run against the wrong context.

**The trap:** when handling an alert like "X is broken in production," the natural instinct is to find the repo named in the alert and open a PR there. But if the alert is fired by a *watcher* script, the fix often belongs in the watcher's repo, not the watched repo. Watcher scripts, AO infra, and Hermes tooling live in `jleechanorg/jleechanclaw`. Product code lives in `$GITHUB_REPOSITORY`. Hermes skills live in `~/.hermes/skills/`. Mixing these up means the PR's diff doesn't match the target repo's CI matrix.

**Recipe (run BEFORE `git worktree add -b <new>`):**

```bash
# 1. Identify the source of the alert
#    - bot/cron watcher alert? Check ~/.hermes/scripts/ for the script name
#    - GitHub Action failure? Check the workflow file's repo + path
#    - Slack message about a service? Trace the alert source to its origin

# 2. List candidate repos for the fix
gh api 'orgs/jleechanorg/repos?per_page=100&sort=updated' \
  --jq '.[] | "\(.name) \(.description // "")"' | head -30

# 3. For each candidate repo, run a quick `git grep` from the terminal to find
#    the file the fix belongs in. The repo where the file lives = the PR target.
gh -C ~/repos/<candidate> ls-files | grep -E "<relevant-keyword>"

# 4. Verify the fix's natural reviewer set matches the target repo
gh api repos/<owner>/<repo>/contents/.github/CODEOWNERS --jq '.content' | base64 -d
```

**Verified case 2026-07-13, jleechanclaw #774 (recurring `is_test IS NULL` alert):** The MCP Agent Mail alert fired in `C0BCVG4F560` about Gemini rows with `is_test IS NULL`. Natural reflex: open PR in `your-project.com` where the BQ data lives. Correct target: `jleechanorg/jleechanclaw` — the watcher script `scripts/bq_coverage_watcher.py` lives there, and the watcher alert logic is what needs fixing (the underlying bug was already fixed in `your-project.com` #8351). PR-topology pre-flight found:
- `your-project.com` #8070 — open, wrong shape (the original 1264-line "add backfill + lock" attempt, superseded by #8351)
- `your-project.com` #8351 — merged, the actual root-cause fix
- The right target for the new work was `jleechanorg/jleechanclaw` because the watcher alerting logic (which is what needs updating to stop firing false positives) lives there.

**Anti-pattern:** Opening the PR in the "alarmed repo" by default. Always trace the alert source to its origin repo before opening the PR.

## Wind-down checkpoint — the WIP-pushed end-state (added 2026-07-12)When the user explicitly says they are pausing / restarting / the session must end NOW (e.g. "WIND-DOWN: Jeff is restarting", "checkpoint NOW", "stop and report state"), the right end-state is **WIP-pushed to a working branch, NOT merged**. This is a fifth valid end-state alongside the four in `finish-the-job`'s Contract.

**The recipe:**

1. **Commit all work** (WIP is fine — even partial code + tests is OK if the commit message is honest about state). Include any untracked files via `git add -A` so the diff matches what was in flight.
2. **Push to the working branch** — never to `main` and never to a "canonical" branch the user didn't designate. Use the worktree's tracking branch: `git push -u origin <branch>`.
3. **Reply in the thread with three lines, in this exact order:**
   - Branch name (full `origin/<branch>`)
   - Pushed SHA (`git rev-parse HEAD`)
   - `git status --porcelain` output (must be empty)
4. **Do NOT merge anything during wind-down.** Even if the PR is technically green, `gh pr merge` requires the user's deliberate go-ahead — not a session-end reflex.
5. **State what is unfinished** in the same reply so the next session can resume without re-deriving context: known-failing tests, unmerged PRs, unclosed beads, unverified repro commands, etc.

**Verified case 2026-07-12, jleechanorg/merge_train PR #41 follow-up:** the user sent "WIND-DOWN: Jeff is restarting the computer shortly. Please checkpoint NOW" mid-task. I had partial code + 3 failing tests + a WIP commit ready but not pushed. The right move was `git add -A && git commit -m "WIP(hooks): issue #42 — ..." && git push -u origin work/pr41-improvements`, then reply with branch + SHA + empty `git status --porcelain`, then pause. Did NOT touch `main`, did NOT merge PR #41, did NOT touch `~/.local/bin/conflict-warn-pre-tool.sh` (left byte-identical for the next session to deploy after the merge).

**Anti-patterns:**

- ❌ "I'll keep working until the end" — the user's wind-down is a hard stop. Keep working past it is an autonomy violation.
- ❌ Pushing a partial commit to `main` to "save it" — the user will merge to `main` deliberately, and seeing unverified code on `main` is worse than losing the WIP.
- ❌ A reply that says "still working, will continue after restart" without the branch/SHA/porcelain — the next session can't resume without that information.
- ❌ Merging a green-looking PR during wind-down without `MERGE APPROVED` — the merge gate is the user's, not the agent's.

## Worktree test-import via `Path.home()` quirk (added 2026-07-15)

Some test files import the source via an absolute path under `Path.home()` rather than a path relative to the test file. Concretely, `scripts/tests/test_bq_coverage_watcher.py` does:

```python
WATCHER_PATH = Path.home() / ".hermes" / "scripts" / "bq_coverage_watcher.py"
spec = importlib.util.spec_from_file_location("bq_coverage_watcher", WATCHER_PATH)
```

When you `git worktree add` and patch the watcher in the worktree, `pytest` does NOT pick up the worktree copy — it runs against `~/.hermes/scripts/bq_coverage_watcher.py` (the deployed prod copy). All "new wording" tests fail with confusing messages like `assert "Remediation:" in msg` against a deployed file that doesn't contain `Remediation:`.

**The trap:** you edit in the worktree, see green tests in your head, run `pytest`, get 4 failures, and assume your patch is wrong. The patch is fine — the test is loading the wrong module.

**The work-around (run once per test run, then restore before commit):**

```bash
# 1. Save the deployed copy for restore
cp ~/.hermes/scripts/<watcher>.py ~/.hermes/scripts/<watcher>.py.bak-$(date +%s)

# 2. Copy the patched worktree version into the import-target path
cp /tmp/<repo>-<topic>/scripts/<watcher>.py ~/.hermes/scripts/<watcher>.py

# 3. Run pytest from anywhere — tests pick up the patched file
python3 -m pytest /tmp/<repo>-<topic>/scripts/tests/test_<watcher>.py -v

# 4. ALWAYS restore before commit, otherwise the local deploy drifts from main
mv ~/.hermes/scripts/<watcher>.py.bak-$(date +%s) ~/.hermes/scripts/<watcher>.py
```

**Detection heuristic:** if a test fails on a substring your patch obviously adds (e.g. fails on `assert "Remediation:" in msg` when your patch literally added the string `Remediation:`), run `grep -n "<substring>" ~/.hermes/scripts/<watcher>.py` BEFORE the patch and AFTER the patch. If neither matches, the test is loading a different file. Use the work-around above.

**Verified case 2026-07-15, jleechanorg/jleechanclaw#781:** first test run had 4/11 failures with `assert "$PROJECT_ROOT/bq_logging.py" in msg` style errors. The patched file did contain the string; the test was loading the deployed 511-line copy that didn't have the new text. Work-around applied; 11/11 green; deployed file restored before commit. Without this trap-recognition, ~3 tool calls wasted re-reading the patch.

**Cross-reference:** skill `verify-telemetry-alert` Step 3a.1 (the same work-around appears in Step 5 of that recipe).

## Local `git fetch` auth-block work-around for jleechanclaw (added 2026-07-15)

`git fetch origin main` in `jleechanorg/jleechanclaw` (and most `jleechanorg/*` repos) fails with `Authentication failed for 'https://github.com/jleechanorg/jleechanclaw.git/'` even when `gh auth status` shows a working `jleechan2015` account. Root cause: the `origin` remote URL contains a truncated/placeholder token (`x-access-token:ghp_yg....git`) that no longer authenticates.

**Symptoms:**
```
$ git fetch origin main
remote: Invalid username or token. Password authentication is not supported for Git operations.
fatal: Authentication failed
```

**Work-around recipe:**

```bash
# 1. Reset origin to the clean public URL (no embedded placeholder token)
cd <worktree>
git remote set-url origin https://github.com/jleechanorg/<repo>.git

# 2. Force the gh-credential helper explicitly (the global gitconfig helper may be empty in worktrees)
git -c credential.helper='$HOME/.local/bin/gh.real auth git-credential' \
    fetch origin main

# 3. Confirm fetch succeeded
git rev-parse origin/main  # should now show the post-#774 SHA, not the stale one
```

**Why `gh auth setup-git` alone doesn't fix it:** it sets up the credential helper, but `git fetch` still uses the URL configured in `.git/config` for that specific remote. If that URL is broken, no helper resolves it. The two-step fix is mandatory.

**Verified case 2026-07-15, jleechanorg/jleechanclaw#781:** first fetch failed with `Authentication failed`. `gh auth setup-git` returned silently. After `git remote set-url origin https://github.com/jleechanorg/jleechanclaw.git` + explicit `gh.real auth git-credential`, fetch succeeded; `git rev-parse origin/main` jumped from stale `1a8c5aef` to post-#774 `99cb779`.

## Dirty-checkout pre-flight — refuse to dispatch onto a dirty or conflicted worktree (added 2026-07-28)

Before dispatching a worker (ao spawn / claudem / opencode) onto an existing checkout, **scan every candidate worktree + the main checkout for clean state**. A "clean" worktree is one where `git status --short` returns empty AND there are no merge/rebase conflicts. Dispatching onto a dirty worktree silently mixes your PR's commits with someone else's WIP, and dispatching onto a conflicted worktree (state `UU` / `AA` / `DD` rows in `git status --short`) makes the worker's first patch land on top of an unresolved merge — a guarantee the next rebase or merge will produce conflicts the agent never saw.

**Recipe (run BEFORE `git worktree add` OR before reusing an existing worktree):**

```bash
# 1. List ALL candidate worktrees for the repo (main + every entry under ~/.worktrees/, ~/projects/, ~/repos/)
gh repo list jleechanorg --json nameWithOwner --jq '.[].nameWithOwner' \
  | xargs -I{} sh -c 'printf "%s\n" "{}"' 2>/dev/null | head

# For each candidate, get status
for wt in ~/projects/<repo> ~/repos/jleechanorg/<repo> ~/.worktrees/*/<repo> 2>/dev/null; do
  if [ -d "$wt" ]; then
    echo "=== $wt ==="
    git -C "$wt" rev-parse --abbrev-ref HEAD 2>/dev/null
    git -C "$wt" rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null
    git -C "$wt" status --short --branch 2>/dev/null | head -30
  fi
done
```

**Decision matrix:**

| Worktree state | Action |
|---|---|
| `git status --short` returns empty | Safe to dispatch — worktree is clean. |
| `git status --short` shows only `M` / `A` / `??` on the planned-PR's intended files | Safe to dispatch — the dirt is the worker's intended changes. Confirm with the user. |
| `git status --short` shows `UU` / `AA` / `DD` (merge conflicts) | **DO NOT dispatch.** Resolve the conflicts first (`git status --short` to identify files, `git checkout --theirs/--ours <file>` or manual edit, then `git add` + `git commit` if needed). |
| `git status --short` shows unrelated modified files (e.g. `.beads/issues.jsonl`, unrelated `.py` files, `wt-<other-topic>/`) | **DO NOT dispatch.** The agent's first `git add` + commit will accumulate that dirt onto the new PR's branch. Either `git checkout -- <unrelated-file>` to drop, or pick a different worktree, or `git worktree add -B <new-topic> <wt-path> origin/main` for a fresh-clean branch. |
| No worktree exists OR all candidate worktrees are dirty | **Create a fresh worktree from `origin/main`:** `git worktree add -B <topic>-<short-hash> <path> origin/main`. Do NOT edit in the main checkout. |

**Why this matters even when the worker runs in its own sandboxed worktree:** many coding agents (claudem / opencode / Codex) accept a `--workdir` flag but still inherit the user's `.gitconfig`, GitHub auth tokens, and IDE state. If the agent's first action is `git status` and the working tree is dirty, the agent may either (a) silently commit on top of unrelated changes, or (b) refuse to commit and ask the user to clean up — neither outcome is acceptable for a one-shot dispatch.

**Anti-pattern:** picking the most-recently-touched worktree under `~/.worktrees/` because "it was used recently, must be safe." Recent activity is not the same as clean state. Always run `git status --short` first; never trust `mtime` or branch-name familiarity.

**Verified case 2026-07-28, $GITHUB_REPOSITORY:** the available worktrees were:
- `~/projects/your-project.com` — on branch `pr8399-w2verify`, 3 modified files (`.beads/issues.jsonl`, `analysis/campaign_analysis_sariel_v2.json`, `analysis/campaign_snapshot_sariel_v2.json`), 2 modified `$PROJECT_ROOT/*.py`, multiple untracked files (`repro-ta[REDACTED_OPENAI_KEY]`, `specs/skeptic-report.json`, etc.) → **dirty, do NOT dispatch**
- `~/repos/$GITHUB_REPOSITORY` — on branch `fix/cron-exit-semantics-and-oom-watchdog`, **unresolved merge conflicts** (`UU .claude/commands/code-standards.md`), 1 modified file → **conflicted, do NOT dispatch**
- No clean worktree available → the right move was to create a fresh worktree from `origin/main` before dispatching the claudem worker.

The lesson: scanning for clean state is the worktree equivalent of `git fetch origin` before push — a 5-second check that prevents a 30-minute cleanup. Add it to every dispatch workflow.