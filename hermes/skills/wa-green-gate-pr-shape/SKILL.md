---
name: wa-green-gate-pr-shape
description: When /green on a your-project.com PR fails, the right fix is PR-shape cleanup, not gate adjustment. Use when a PR title claims small scope but the diff is large, or when Green Gate Precheck fails with stale `origin/main`/re-replays-of-merged-PRs pattern. v1.1.0 fires for the "user sees nothing diff" class (backend-only field-adds that ship without a frontend consumer). v1.2.0 fires when GATE-6 or GATE-6b fails on the PR description body (missing canonical sections, missing anchor URLs/code-blocks, no gist link). v1.4.0 fires when Gate-8 (Smoke) is still red after Precheck passes — MOCK mode is the default; only REAL-mode dispatch via the REST workflow_dispatch endpoint satisfies Gate-8. v1.6.0 fires for content-only PRs under world_reference/ — docs-only exemption in scope; gh pr merge --merge works directly. v1.9.0 fires for two new classes - the LOC ratchet failure (process_action_unified grew from X to Y; world_logic.py line count bound 12000) and the mis-closed "Superseded by #N" PR that must be reopened before AO --claim-pr works.
version: 2.1.0
author: hermes (learned from PR #8408 → #8411, 2026-07-14; PR #7953, 2026-07-15; PR #8423, 2026-07-17; PR #8467, 2026-07-20; PR #8462, 2026-07-20; PR #8486, 2026-07-20 [world_reference/ content-only path]; PR #8485, 2026-07-20 [Gate-0 Tenets/Design-Decision anchor for production-code PRs + gate-0 synchronize-only retrigger]; PR #8467-v2, 2026-07-21 [setting-agnostic invariant regression + PR-already-merged early-exit check]; PR #8536, 2026-07-23 [LOC ratchet + Design Doc line-count "raise this limit" directive + mis-closed Superseded-by reopen pattern]; PR #8527 → #8548, 2026-07-23 [`$PROJECT_ROOT/prompts/injection/` extraction closing the `pr_description_gate.py` path-filter loophole on agent_prompts.py inline prompt blocks]; PR #8462 + #8544, 2026-07-24 [three-way "merge if /green AND /er AND /advice approved" conditional — verdict-lookup recipe, default-deny on missing verdicts, Green Gate aggregator ≠ underlying CI pitfall, `gh pr checks` → `gh api .../check-runs` swap])
triggers:
  - "user sees nothing diff"
  - "what's the point of the PR"
  - "no frontend consumer"
  - "backend only"
  - "frontend bundle grep"
  - "no user-visible diff"
  - "PR is all backend"
  - "diff is all backend"
  - "[frontend] issue"
  - "frontend banner missing"
  - "soft-warn banner missing"
  - "field added but no UI"
  - "verify_user_visible_diff"
  - "Gate-8 no deployed GCP preview service for this PR head SHA"
  - "Smoke Gate Wait timed out waiting for mcp-smoke-tests"
  - "mcp smoke no deployed preview"
  - "preview slot reassigned"
  - "retest smoke after cloud run preview reassignment"
  - "world_reference content-only PR"
  - "GATE-1 FAIL but mergeable"
  - "CodeRabbit rate limit non-blocking"
  - "Design Doc Grep Gate fail"
  - "GATE-0 missing Tenets"
  - "Gate-0 needs linked artifact"
  - "design-doc-gate.yml fail"
  - "edit body no re-trigger Gate 0"
  - "PR already merged while polling"
  - "user merged mid-poll"
  - "mergeable but closed"
  - "stop retriggering green gate"
  - "test_divine_prompts_setting_agnostic failing"
  - "D&D entity leaked into default text"
  - "Oghma Mystra Ao default text"
  - "the Weave Netherese in default text"
  - "ACTIVE OBSERVERS missing from HUD"
  - "Appendix A marker splits default text"
  - "setting-agnostic invariant test"
  - "raise this limit"
  - "raise the limit"
  - "process_action_unified grew"
  - "function LOC ratchet"
  - "baseline exceeded"
  - "world_logic.py line count"
  - "wc -l world_logic"
  - "superseded by PR"
  - "Superseded by"
  - "PR_NOT_OPEN"
  - "closed as superseded"
  - "verify supersede claim"
  - "reopen closed PR"
  - "claim-pr PR_NOT_OPEN"
  - "Real LLM Evidence N/A but PR injects a prompt"
  - "PR doesnt change prompts but injects a prompt"
  - "agent_prompts.py inlined f-string prompt"
  - "build_*_instruction inline prompt"
  - "$PROJECT_ROOT/prompts/injection/"
  - "PR-description-gate path filter loophole"
  - "moving prompts to injection directory"
  - "merge if green and er and advice approved"
  - "review and merge if approved"
  - "/green and /er and /advice"
  - "merge approved if green"
  - "three-way approval conditional"
  - "default-deny on missing verdicts"
  - "/er verdict"
  - "/advice verdict"
  - "/er FAIL"
  - "/er PASS"
  - "no /er comment"
  - "no /advice comment"
  - "Green Gate aggregator vs underlying CI"
  - "gh pr checks requires --watch"
  - "gh api check-runs instead of gh pr checks"
  - "review PRs and merge approved"
  - "batch review PRs"
---

# /green on your-project.com — when gate fails on shape, fix the PR not the gate

## Symptom

You got asked to `/green` a PR. It fails Green Gate Precheck at GATE-1 (CI red) or GATE-6 (no evidence). The PR title claims small scope (e.g., "Align dice prompt examples") but the actual diff is 10-30x larger (e.g., 24 files / +1309/-89). The branch is built from a stale `origin/main@<oid>`. The PR body has wrong commit SHA + copy-pasted `CURSOR_SUMMARY` from a previous PR + `/tmp/...jsonl` paths instead of real evidence URLs.

## New symptom class (added v1.1.0) — "user sees nothing diff"

The PR is small (+89/-16 across 3 files) but the **title promises a UX change** ("surface quota counters on interaction success path", "[frontend] Quota-wall retention UX"). The diff is **all backend** — no `$PROJECT_ROOT/frontend_v1/` files touched. The issue title says "[frontend] ..." but only the backend half landed. A user loading the deployed preview before vs after this PR sees **identical pixels**.

User complaint (verbatim, 2026-07-15 PR #7953): *"what's the point of the PR if the user sees nothing diff?"*

**Diagnostic recipe — `verify_user_visible_diff.sh` workflow:**
1. `gh pr view <N> --repo $GITHUB_REPOSITORY --json files --jq '.files[].path'` → if zero `$PROJECT_ROOT/frontend_v1/` files in the diff AND the PR title/issue claims a UX change, this class fires.
2. `gh pr view <N> --json title,body` → if the body says "the frontend can render X" or "consumer exists" but X is not in this PR's diff, this class fires.
3. **Live frontend-bundle grep** (the load-bearing step — verifies wire-vs-UI gap):
   ```bash
   # Pull the deployed PR preview URL from any "Deployment Complete" bot comment
   PREVIEW=$(gh pr view <N> --json comments --jq '.comments[] | select(.body | test("Deployment Complete"; "i")) | .body' | grep -oE 'mvp-site-app-[a-z0-9-]+' | sort -u | tail -1)
   curl -fsSL "https://${PREVIEW}-i6xf2p72ka-uc.a.run.app/frontend_v1/app.js" -o /tmp/app.js
   curl -fsSL "https://${PREVIEW}-i6xf2p72ka-uc.a.run.app/frontend_v1/api.js" -o /tmp/api.js
   # Are the new field names actually read on the success path?
   python3 -c "import re,sys; \
     body=open('/tmp/app.js').read()+open('/tmp/api.js').read(); \
     fields=['daily_remaining','hourly_remaining','reset_time_daily','reset_time_hourly']; \
     [print(f, '->', len(re.findall(f, body)), 'hits (all inside jsonError = no success-path consumer)') for f in fields]"
   ```
4. If every `reset_time_*` hit lives inside `jsonError` / 429-modal handling (the pre-existing error path) and **zero hits exist on the success-path response body**, the PR is the broken-shape class. User-visible diff: NONE.

**Why this matters:** Green Gate passes (tests green, evidence URL present), Skeptic PASSes (gate logic only checks PR description fields), CodeRabbit APPROVES (it reads diff vs title — but title-only review misses the "field added but no consumer" gap). All automated gates go green; the user is the only reviewer who catches it. Don't merge these as-is.

**Fix options (in preference order):**
1. **Best**: split the PR — `#7953-backend` (just the field-add, honest scope) + `#7953A-frontend` (banner UI consuming the new fields). Each PR reviewable on its own.
2. **Acceptable**: keep #7953 but rewrite the PR body to be honest: *"backend half — frontend banner lands in follow-up PR #XXXX"*, link the issue, update the body so a future reviewer doesn't get fooled.
3. **Worst**: merge as-is and pretend the frontend lands later — this is the path that produces "user sees nothing diff" PRs the user keeps catching. Banned.

When you find this class: open a bead (`br create "<N> backend field-add has zero frontend consumer" --type bug --priority 2`), link the deployed-bundle grep output, and ask the user for the split decision before merging. Do not merge the PR in current shape without explicit user call.

## Why this is the canonical pattern

`./claude/projects/-Users-$USER-worldarchitect-ai/memory/feedback_2026-07-14_pr8408_gate-killer-pattern.md` (if it exists). Three structural failures compound:

1. **Branch from stale `origin/main`**: branch tip is 877 commits AHEAD and has no merge-base with current `origin/main`. Common cause: `origin/main` had 6+ new merges since the branch was checked out. The branch's "ahead 877" includes re-replays of merged commits (#N appears 2x on the branch's history) + maybe accidentally-created remote `refs/heads/origin/main` if someone typed `git push origin HEAD:refs/heads/origin/main` once.
2. **Mis-bundled commits**: the branch contains 6+ commits that are duplicates of work already merged (titles like "Merge remote-tracking branch 'origin/main' into fix/X" + cherry-picks of `#N`). Only 2 commits are net-new actual work.
3. **PR body fabricated**: GitHub-formatted body used to render correctly for old PR-template; in modern git, the body stores claim text (commit SHA, evidence URLs, summary). If the body claims a SHA that doesn't exist or has copy-pasted a `CURSOR_SUMMARY` block from PR #N-1, the gate fails.

## Recipe

Run from `~/.worktrees/wa-<N>-green` (use a fresh worktree, not the dirty main checkout).

```bash
# 1. Diagnose: confirm scope mismatch
gh pr view <N> --repo $GITHUB_REPOSITORY --json additions,deletions,changedFiles,headRefOid,baseRefOid,headRefName,baseRefName
git -C $HOME/.worktrees/wa-<N>-green log --oneline origin/main..HEAD --no-merges --first-parent
# Count: how many of those SHAs are duplicates of merged work?

# 2. Identify the truly net-new commits (not from origin/main history)
git -C $HOME/.worktrees/wa-<N>-green log --all --format='%H %s' | grep "<one-line-cue>"

# 3. Create clean branch from current origin/main
cd $HOME/.worktrees/wa-<N>-green
git fetch origin main
git checkout -B fix/<N>-green-driving origin/main
# Apply just the net-new diff (cherry-pick or direct `patch -p1` for the file edits only)

# 4. Single squashed commit on fresh origin/main
git add $PROJECT_ROOT/prompts/  # or your scope
git commit -m "<cleanly worded scope>"
git push origin fix/<N>-green-driving

# 5. PR body MUST pass `pr_description_gate.py` --overall=PASS:
python3 .github/scripts/pr_description_gate.py \
  --body-file /tmp/body.md \
  --changed-files $PROJECT_ROOT/prompts/X.md \
  --changed-files $PROJECT_ROOT/prompts/Y.md

# 6. Body MUST include a gist URL — https://github.com/... PR links do NOT satisfy GATE-6
~/.hermes/scripts/gh-safe-publish gist create --public --desc "PR #<M> evidence" /tmp/clean_diff.patch /tmp/commit.md

# 7. Close old PR with comment pointing at new one
gh pr close <N> --repo $GITHUB_REPOSITORY --comment "Superseded by #<M> (clean prompt-only extraction)."

# 8. Open new PR with verified body
~/.hermes/scripts/gh-safe-publish pr create --repo $GITHUB_REPOSITORY \
  --base main --head fix/<N>-green-driving \
  --title "<correct scope>" \
  --body-file /tmp/body.md

# 9. Run /advice on the new PR — fix any docs-accuracy issues BEFORE pushing
delegate_task(toolsets=['terminal','file'], goal='docs-accuracy review')

# 10. /smoke real (comment-router dispatches on ref=main; useful as fallback)
~/.hermes/scripts/gh-safe-publish pr comment <M> --repo $GITHUB_REPOSITORY --body "/smoke real"
```

## Gate /don't adjust/ rule

The gate is *correctly catching these failures* per AGENTS.md. Three configurations you MUST know about — failing any one costs 1+ failed CI runs per attempt:

**GATE-0 (Design Doc Grep) — 2026-07-20 PR #8485 fix:** The `design-doc-gate.yml` workflow only fires on `pull_request: [opened, ready_for_review, synchronize, reopened]` (NOT `edited`). Body-only edits via `gh pr edit` will not re-trigger Gate 0 — it requires an actual `synchronize` event on the PR head branch. **Empty-commit recipe:** `git -c user.email=jleechan2015@users.noreply.github.com -c user.name=jleechan2015 commit --allow-empty -m "ci: refresh green gates after body restructure" && git push origin HEAD:refs/heads/<branch>`.

For **production-code PRs** that touch `$PROJECT_ROOT/**/*.py` AND need a design doc anchor, the body MUST include one of:
- `## Tenets` section, OR
- `## Design Decision` section

…with a reference to a bead ID (`rev-<id>`) AND a linked artifact (`world_reference/<file>.md` or `.beads/issues.jsonl`). Verified pattern (PR #8485 body):
```markdown
## Tenets (or Design Decision)

The disable is the safe prelude to the god-mechanics redesign. Original spec: `world_reference/aizen_god_mechanics.md` (11K). Bead: `$USER-d8lo`.
```

The Gate 0 grep looks for either the section header + linked `.md` artifact or a bead reference in `.beads/issues.jsonl`. Pure `## Tenets` prose without a linked file fails — the linked artifact must exist on disk at the cited path.

**GATE-6 evidence trigger** (`.github/workflows/green-gate.yml`):
```bash
grep -B 2 -A 6 "^smoke_required\|SMOKE_REQUIRED" .github/workflows/green-gate.yml
```
Triggers: `^(testing_(mcp|ui)/|$PROJECT_ROOT/|deploy\.sh$|\.github/workflows/evidence-gate\.yml$)`

**GATE-6 vs GATE-6b (different gates, both fire):**
- **GATE-6** (evidence-link heuristic, bash grep on PR body + comments): matches `.mp4|.gif|.cast|.png|.jpg|.jpeg|.webp|loom.com|asciinema.org|youtu.be|youtube.com|gist.github.com|/gist|user-attachments`. **Plain `https://github.com/...` PR diff links do NOT satisfy this — you need a gist, video, image, or asciinema URL.**
- **GATE-6b** (PR description gate, runs `python3 .github/scripts/pr_description_gate.py`): validates the 8 canonical sections + anchor requirements. See below.

**GATE-6b 8-section contract (NEW v1.2.0 — verified PR #8423, 2026-07-17, 4 failed runs to crack; PR #8467, 2026-07-20, agent missed 5 sections in first body):**

The PR description gate requires **ALL 8 sections** to be present with `## ` (two-hash, line-start) prefix, in this exact order:

1. `## Summary`
2. `## Production Code Changes`
3. `## Test Changes`
4. `## Known Limitations`
5. `## Unit Test Evidence`
6. `## Non-Unit Test Evidence`
7. `## Real LLM Evidence` (N/A allowed only if no `$PROJECT_ROOT/prompts/**` files touched)
8. `## Evidence`

Each section must have **≥10 chars content density**. The 4 evidence sections (`## Unit Test Evidence`, `## Non-Unit Test Evidence`, `## Real LLM Evidence`, `## Evidence`) MUST contain **at least one anchor**: a real `https?://` URL OR a fenced code block (`` ``` ... ``` ``). Plain prose URLs are accepted by the regex — no need for markdown link syntax. A section with only prose and no URL/code block fails with `reason: "evidence section needs a URL or backticked code block"`.

If your PR body has `https://github.com/...` (a PR link) but no `gist.github.com/...` URL, **GATE-6 fails** — add the gist URL.

**Canonical PR-body template (NEW v1.3.0 — paste and adapt every body before first push):**

Use this skeleton for every worldai PR. Fill in, run the local validator, then push. Skipping any section drops you back into the 4-CI-cycle thrash.

```markdown
## Summary
- <one-paragraph scope statement>
- <bullets of concrete changes>

## Production Code Changes
- `path/to/file.py` (<+N>/<-M>): <description of real diff content>

## Test Changes
- `path/to/test_X.py`: <new/updated tests> (or "no test changes — `<reason>`")

## Known Limitations
- <honest scope> or "none beyond what the summary states"

## Unit Test Evidence
```bash
./run_tests.sh --full
# output: <paste a few PASS lines + summary, or link to gist if output is huge>
```
or link: <https://gist.github.com/.../raw/.../test_output.txt>

## Non-Unit Test Evidence
- <media URL — .mp4|.gif|.cast|.webp|loom.com|asciinema.org|youtube.com>
- or, for prompt-only changes, the JSON contract diff inline:

```json
{"state_updates": {"custom_campaign_state": {"faction_dissonance": {"helm": 57}}}}
```
with `role: model` candidate marker.

## Real LLM Evidence
- `/es` bundle (gist, JSON): <https://gist.github.com/.../raw/.../bundle.json>
- `<agy>` invocation line and SHA captured at:
- Sample response excerpt:

```json
{"role": "model", "content": "<echo of narrative>"}
```

## Evidence
- `/es` bundle URL: <https://gist.github.com/.../raw/.../bundle.json>
- Capture script: `~/.hermes/scripts/worldai/<your-test>.py`
- GitHub PR HEAD SHA: `<ec74ca...>`
- Contract check exit code: `0 (PASS)`
```

**Why the 8-section template works:** the local validator script `python3 .github/scripts/pr_description_gate.py` returns `overall: PASS` only when all 8 headers appear in order with non-empty bodies AND every evidence section has an anchor (URL or fenced code). A "natural" PR body without this scaffold typically hits GATE-6b FAIL on `missing_sections: [Production Code Changes, Test Changes, Unit Test Evidence, Non-Unit Test Evidence, Evidence]` (5 missing — this was PR #8467 v1).

**Pre-amble anti-pattern (2026-07-20 PR #8467):** writing a beautifully detailed `## Summary` + `## Verification` + `## Command(s) used` while omitting the boilerplate 8-section scaffold. Every word in the right sections except the right sections themselves. Validator says FAIL. Fix: append the missing sections, don't rewrite the prose.

### Re-triggering the gate after body edits

`gh workflow run green-gate.yml -f pr_number=N` lands on `head_branch=main`, not the PR branch (see `drive-pr-to-green` v2.5.6 — same pitfall). After editing the PR body, you need an actual `synchronize` event on the PR's head branch. The working pattern is an empty commit:

```bash
git -c user.email=harness@hermes.ai -c user.name=hermes-agent commit --allow-empty \
  -m "ci: re-trigger green gate after body section fix"
git push origin <branch>
```

Each body edit costs ~2-3 minutes for the new Green Gate Precheck run. Expect 2-5 iterations to crack a fresh body. **Local dry-run before push** (zero API cost):

```bash
python3 .github/scripts/pr_description_gate.py --body-file /tmp/body.md \
  --changed-files $PROJECT_ROOT/foo.py \
  --changed-files .gitignore
```

Returns JSON with `overall: "PASS"` or `"FAIL"` + the exact `missing_sections` / `anchor_missing_sections` arrays. Run this locally first; do not discover missing sections by watching CI time out 4 times.

### Why "GATE-6b FAIL on first push" is so common

The repo's prior PR template (or copy-pasted body from another PR) typically only includes the old `## Evidence` section. The modern validator requires 7 more. Burn rate observed: 4 CI cycles (≈12 minutes wasted) before cracking all 8 sections + anchor pattern. Run the local validator before your first push to skip this entirely.

### Conditional section waivers

The validator examines `changed_files` to decide which sections can be N/A:
- `$PROJECT_ROOT/prompts/**` → `## Real LLM Evidence` required with `LLM_RESPONSE_MARKERS` substring (Gemini/OpenAI/Anthropic JSON shape, `Request:`/`Response:` line)
- `$PROJECT_ROOT/frontend_v*/**` or `$PROJECT_ROOT/static/**` or `$PROJECT_ROOT/templates/**` → `## Non-Unit Test Evidence` requires media URL (`.mp4|.gif|.cast|.webp` or loom/asciinema/user-attachments)
- `$PROJECT_ROOT/**/*.py` (outside tests) → `## Non-Unit Test Evidence` requires LLM response OR `/end2end-testing` response/payload marker
- Docs-only (`docs/`, `README.md`, `AGENTS.md`, `CLAUDE.md`, `.claude/`, `.codex/`, `.cursor/`, **`world_reference/`**) → all evidence gates bypass with `GATE-6 PASS: docs-only change set`

**`world_reference/` content-only PRs — verified PR #8486 (2026-07-20):**

`world_reference/*.md` files are *content-only* campaign bibles / source documents for the WA prompts to reference — not production code, not runtime, not frontend. They follow the same docs-only exemption as `docs/`, `AGENTS.md`, etc. When the validator sees only `world_reference/<file>.md` changes, it reports `GATE-6 PASS: evidence not required for this change set` and `GATE-6b SKIP: PR description gate not required for this change set`.

**Diagnose first — if your branch is content-only, check the gate log for these two PASS/SKIP lines before assuming the body is wrong:**

```bash
gh run view <green-gate-run-id> --repo $GITHUB_REPOSITORY --log-failed \
  | grep -E "GATE-6 (PASS|FAIL)|GATE-6b (PASS|SKIP|FAIL)"
```

If you see `GATE-6 PASS: evidence not required for this change set` AND `GATE-6b SKIP: PR description gate not required for this change set`, the body does NOT need the 8-section scaffold — the validator already gave you the bypass. Adding the 8 sections anyway is harmless (validator accepts them) but unnecessary.

**Verify merge is still possible despite GATE-1 FAIL.** Content-only `world_reference/` PRs frequently fail GATE-1 with the *self-referential* failure mode (gate fails because its children were skipped because it failed) and GATE-3 with `CR=FAIL(status=failure comment=none)` from CodeRabbit rate-limiting (documented pattern, not a real content issue). Both are non-blocking on this PR class because branch protection on `main` is:

```bash
gh api repos/$GITHUB_REPOSITORY/branches/main/protection \
  --jq '{required_status_checks_contexts: .required_status_checks.contexts,
         required_approving_review_count: .required_pull_request_reviews.required_approving_review_count,
         enforce_admins: .enforce_admins.enabled}'
```

If `required_status_checks_contexts: []` AND `required_approving_review_count: 0` AND `enforce_admins: false` (verified PR #8486), the PR is *mergeable* (`gh pr view --json mergeable` returns `MERGEABLE`) regardless of Green Gate Precheck failure. Run `gh pr merge <N> --merge --delete-branch` directly — don't try to fix the gate.

**What this means for content PR workflow:**

1. Single-commit, clean branch from `origin/main`
2. PR body should still be *honest* (Summary + Inspiration links + Provenance) but doesn't need the 8-section template
3. `gh pr merge --merge --delete-branch` works even when Green Gate Precheck fails for self-referential or rate-limit reasons
4. Don't waste cycles trying to fix GATE-1 / GATE-3 on a content-only PR — the gate isn't required and isn't catching a real issue

## Gate-8 (Smoke) fail-closed REAL-mode dispatch (NEW v1.4.0)

GATE-8 is the **`Smoke Gate Wait`** job inside `green-gate.yml`. It is **fail-closed** and the default is **MOCK** — the gate only passes when a REAL-mode `MCP Smoke Tests` workflow run completes successfully for the PR head SHA. This is the most common reason a PR sits at `mergeable_state: unstable` after Precheck passes.

**The 3 dispatch paths and which one actually works:**

| Path | Lands in MOCK or REAL? | Why |
|---|---|---|
| `/smoke` PR comment → comment-router → `gh workflow run` | **MOCK** | comment-router dispatch hardcodes `-f inputs[pr_number]=N` and does NOT pass `test_mode`. The workflow's `test_mode` input default is `mock`. So `/smoke real` ALSO lands in mock — the comment-router ignores the `real` token. |
| `gh workflow run mcp-smoke-tests.yml -f pr_number=N -f test_mode=real` | fails with "fatal: not a git repository" | `gh workflow run` shorthand requires `.git` context; the workflow runner is `ubuntu-latest` with no checkout. Verified 2026-07-20. |
| **`gh api POST repos/$GITHUB_REPOSITORY/actions/workflows/mcp-smoke-tests.yml/dispatches -f ref=main -f inputs[pr_number]=N -f inputs[test_mode]=real`** | **REAL ✅** | REST endpoint, no git context, all inputs passed correctly. |

**Working recipe (verified PR #8467, 2026-07-20):**

```bash
# 1. Get token
TOKEN=$(gh auth status --show-token | awk '/Token:/{print $2}')

# 2. Dispatch REAL-mode smoke run via REST
curl -fsS -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept: application/vnd.github+json" \
  -H "Content-Type: application/json" \
  -d '{"ref":"main","inputs":{"pr_number":"<N>","test_mode":"real"}}' \
  https://api.github.com/repos/$GITHUB_REPOSITORY/actions/workflows/mcp-smoke-tests.yml/dispatches
# 204 = queued

# 3. Wait ~3-6 min for the run to complete
gh api "repos/$GITHUB_REPOSITORY/actions/runs?per_page=10" \
  | jq '.workflow_runs[] | select(.name == "MCP Smoke Tests") | {status, conclusion, updated_at}'

# 4. Once success, re-run the failed Green Gate so it sees the smoke success
gh run rerun <green-gate-run-id> --repo $GITHUB_REPOSITORY --failed
```

**Why Gate-8 polls fail-closed without a REAL smoke run:** the gate script checks `gh api repos/.../actions/runs?head_sha=<SHA>&status=completed` for `conclusion=success` runs of `mcp-smoke-tests.yml` at `test_mode=real`. If the only run is `MOCK`, the gate times out at 45 polls (15 min) with `GATE-8 FAIL: timed out waiting for a REAL-mode mcp-smoke-tests pass for SHA <sha>`. The fix is to dispatch the REAL run — don't wait, don't retry mock.

**When to skip Gate-8 entirely:** for docs-only / AGENTS.md / .claude/ / .codex/ / .cursor/ changes, the green-gate precheck reports `GATE-6 PASS: docs-only change set — evidence link not required`. Gate-8 is still wired but will accept a non-REAL run. Verify by checking the gate log for `GATE-6 PASS: docs-only change set` before assuming you need to dispatch.

## Gate-8 variant: `MCP Smoke Tests` fails with "No deployed GCP preview service was found" (NEW v1.5.0, PR #8462)

Distinct failure mode from "MOCK-vs-REAL". The smoke run lands in REAL mode correctly, but the workflow's preview-lookup step reports:

```
❌ MCP Smoke Tests Failed
Reason: No deployed GCP preview service was found for this PR head SHA
```

**Root cause:** The Cloud Run preview slot is **per-head-SHA**, but `Deploy PR Preview (Rotating Pool)` reassigns slots on a round-robin basis as new PRs deploy. The slot that was deployed for an older head SHA `X` gets reassigned when PR `Y` lands its own deploy. By the time `MCP Smoke Tests` tries to find a preview for SHA `X`, the slot has rotated to a different PR's URL.

**Diagnosis (3 commands):**

```bash
PR_NUM=8462
TOKEN=$(gh auth status --show-token | awk '/Token:/{print $2}')

# 1. Find the PR's deploy-preview comment for the CURRENT head SHA
gh api -H "Authorization: Bearer $TOKEN" -H "Accept: application/vnd.github+json" \
  "repos/$GITHUB_REPOSITORY/issues/${PR_NUM}/comments?per_page=20" \
  | jq -r '.[] | select(.body | test("Deployment Complete"; "i")) | .body' \
  | grep -oE 'mvp-site-app-[a-z0-9-]+' | sort -u | tail -1

# 2. Look for the smoke run that failed AND check its conclusion
gh api -H "Authorization: Bearer $TOKEN" -H "Accept: application/vnd.github+json" \
  "repos/$GITHUB_REPOSITORY/actions/runs?branch=fix/<branch-name>&per_page=10" \
  | jq -r '.workflow_runs[] | select(.name == "MCP Smoke Tests") | "\(.head_sha[:10]) \(.conclusion) \(.html_url)"'

# 3. Compare commit SHAs — if smoke SHA ≠ preview SHA, the slot rotated
```

**Fix (empty-commit retrigger — distinct from the body-edit retrigger in v1.4.0):**

```bash
# From the PR's worktree (or any clone on the branch)
git -c user.email=jleechan2015@users.noreply.github.com -c user.name=jleechan2015 \
    commit --allow-empty \
    -m "fix(<scope>): trigger fresh preview deploy for Gate 8 real-mode smoke"
git push origin HEAD

# Wait ~7 min for pr-preview.yml to deploy + label the new slot for pr_number=N
# Then re-dispatch the smoke run via REST (NOT /smoke comment — that's MOCK):
gh api -X POST -H "Authorization: Bearer $TOKEN" \
     -H "Accept: application/vnd.github+json" -H "Content-Type: application/json" \
     -d '{"ref":"fix/<branch>","inputs":{"pr_number":"<N>","test_mode":"real"}}' \
     "https://api.github.com/repos/$GITHUB_REPOSITORY/actions/workflows/mcp-smoke-tests.yml/dispatches"
```

**Pitfall — `gh workflow run` fails with GraphQL rate-limit even with `--ref`:**

```bash
# ❌ Fails with "unable to determine default branch for ... GraphQL: API rate limit already exceeded"
gh workflow run mcp-smoke-tests.yml --repo $GITHUB_REPOSITORY \
  --field pr_number=8462 --field test_mode=real

# ❌ Same GraphQL failure even with --ref
gh workflow run mcp-smoke-tests.yml --repo $GITHUB_REPOSITORY \
  --ref fix/bq-payloads-schema-cold-replica-fix \
  --field pr_number=8462 --field test_mode=real

# ✅ REST dispatch bypasses GraphQL
curl -fsS -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept: application/vnd.github+json" \
  -H "Content-Type: application/json" \
  -d '{"ref":"fix/bq-payloads-schema-cold-replica-fix","inputs":{"pr_number":"8462","test_mode":"real"}}' \
  https://api.github.com/repos/$GITHUB_REPOSITORY/actions/workflows/mcp-smoke-tests.yml/dispatches
# 204 = queued
```

**Anti-patterns:**

- ❌ Re-running the smoke workflow via the failed run's "Re-run" button — it uses `MOCK` mode (the default input value) and lands in the same MOCK-vs-REAL trap.
- ❌ Editing the PR body hoping that retriggers the smoke workflow — the smoke workflow only watches its own inputs, not the PR body.
- ❌ Just waiting 15 min and assuming the slot will re-rotate back — slots are FIFO and once reassigned, they don't return.

## Anchor-only-fails pitfall (NEW v1.4.0 — PR #8467)

GATE-6b's `anchor_missing_sections` check is a SECOND pass that fires AFTER `missing_sections: []`. The validator returns `overall: FAIL` even when all 8 sections are present if any of the 4 evidence sections (`## Unit Test Evidence`, `## Non-Unit Test Evidence`, `## Real LLM Evidence`, `## Evidence`) lacks an anchor: a real `https?://` URL or a fenced code block (``` ``` ```, ≥80 chars).

**Anti-pattern:** writing `## Unit Test Evidence\nN/A — no unit tests added. Reference: \`pytest testing_mcp/test_X.py\`` — the inline backticks are NOT an anchor. The validator regex `FENCED_CODE_RE = re.compile(r"\`\`\`[\\s\\S]+?\`\`\`", re.MULTILINE)` only matches triple-backtick fenced blocks.

**Fix:** use a fenced code block with the command inline:

```markdown
## Unit Test Evidence
N/A — no unit tests added. Reference command (existing test continues to pass against modified prompts):

\`\`\`bash
cd $HOME/.worktrees/<branch> && python3 -m pytest testing_mcp/test_X.py -x -v
\`\`\`
```

Or include a URL anchor (gist, mp4, loom link). Plain prose mentioning the URL is NOT enough — the anchor regex matches only the URL itself, not surrounding markdown text.

**Diagnosis:** when the validator fails after `missing_sections: []`, the error is in `anchor_missing_sections`. Run the local dry-run with `--body-file` and grep for the failing section names:

```bash
python3 .github/scripts/pr_description_gate.py --body-file /tmp/body.md \
  --changed-files $PROJECT_ROOT/foo.py \
  | jq '.anchor_missing_sections, .missing_sections'
# Returns: ["## Unit Test Evidence"] (single anchor missing) → fix as above
```

## `pr_description_gate.py` path-filter loophole on `$PROJECT_ROOT/prompts/**` (NEW v2.0.0 — PR #8548, 2026-07-23)

**The trap:** the GATE-6b "Prompt change" rule is path-filtered:

```
# .github/scripts/pr_description_gate.py — Prompt change (any $PROJECT_ROOT/prompts/** file):
# ## Real LLM Evidence MUST contain a real LLM HTTP raw response (URL or inline code block).
```

A PR that inlines a 16-line LLM-bound prompt block as a Python f-string inside `$PROJECT_ROOT/agent_prompts.py` materially alters the served prompt — but the rule's path filter means `## Real LLM Evidence` is correctly classified as N/A. The validator says PASS, but the spirit of the rule (real LLM behavior evidence for any change that alters LLM-served content) is bypassed.

**Verified incident (PR #8527 → PR #8548, 2026-07-23):** PR #8527 inlined a companion-quest cadence block in `build_living_world_instruction`. The PR body honestly said *"Real-LLM Evidence is N/A for the prompt-change rule"* — the path filter said so. Jeffrey flagged the loophole directly: *"Even if this PR doesnt change prompts/ it is injecting a prompt. Maybe we should move all the injectable prompts from inline code to $PROJECT_ROOT/prompts/injection/?"*. The clean replay (PR #8548) extracted the inline block to `$PROJECT_ROOT/prompts/injection/living_world_companion_cadence.md` and closed the loophole: the new file is now under `$PROJECT_ROOT/prompts/**`, so the path filter correctly fires and forces real-LLM evidence for future edits to that block.

**Three operational rules when touching LLM-served content in `$PROJECT_ROOT/agent_prompts.py`:**

1. **Any string literal that gets concatenated into the served prompt is a "prompt change" — regardless of whether the file extension is `.py` or `.md`.** If you find yourself writing a multi-line f-string that contains "PER-TURN OBLIGATION" or "MUST" or "Emit `<state_updates.X>`", that's an injected prompt. Move it to `$PROJECT_ROOT/prompts/injection/<name>.md` and load via `read_file_cached(constants.<NAME>_PATH).format(**kwargs)`.

2. **Every `$PROJECT_ROOT/prompts/injection/*.md` file MUST be registered in 3 places:**
   - `$PROJECT_ROOT/constants.py` — `PROMPT_TYPE_<NAME>` (str), `INJECTION_PROMPTS_DIR`, `<NAME>_PATH` (str path)
   - `$PROJECT_ROOT/agent_prompts.py` — `PATH_MAP[constants.PROMPT_TYPE_<NAME>] = constants.<NAME>_PATH` so the schema-cache warmup loop and `test_all_prompt_files_are_registered_in_service` see it
   - `$PROJECT_ROOT/tests/test_prompts.py` — add `constants.PROMPT_TYPE_<NAME>` to the `conditional_prompts` set inside `TestPromptLoading::test_all_registered_prompts_are_actually_used` (around line 670) — otherwise the test reports the new file as "always-loaded but never loaded"

3. **The validator-broaden follow-up is a SEPARATE PR.** Don't try to broaden the path filter to `$PROJECT_ROOT/**/*.py` in the same PR that does the extraction — that turns a 5-file refactor into a multi-gate-validator change. Land the extraction cleanly first; broaden the rule in a follow-up that adds `inject_prompt_count_changed` detection (a pre-push script that diffs `build_*_instruction` return values between `origin/main` and the PR head).

**Local-dry-run check before pushing any PR that touches `$PROJECT_ROOT/agent_prompts.py`:**

```bash
# Does this PR change what the LLM sees, regardless of file extension?
git diff origin/main..HEAD -- $PROJECT_ROOT/agent_prompts.py | \
  grep -E '^\+.*(f"|f\\".*OBLIGATION|MUST|emit `state_updates|companion_arc|next_companion_arc_turn)' | \
  head -20
# If you see hits, that's an injected prompt. Move to prompts/injection/ before pushing.
```

**Verified fix recipe (PR #8548, 2026-07-23):**

```bash
# 1. Extract the inline block to a new .md file
cat > $PROJECT_ROOT/prompts/injection/<name>.md <<'EOF'
**🎯 <LABEL>**
On this trigger turn (`current_turn = {current_turn}`), you MUST ...
Cadence anchor: `living_world_instruction.md` §"Turn Cadence"
EOF

# 2. Add constants (in $PROJECT_ROOT/constants.py)
PROMPT_TYPE_<NAME> = "<name>"
INJECTION_PROMPTS_DIR = os.path.join(PROMPTS_DIR, "injection")
<NAME>_PATH = os.path.join(INJECTION_PROMPTS_DIR, "<name>.md")

# 3. Register in PATH_MAP (in $PROJECT_ROOT/agent_prompts.py)
constants.PROMPT_TYPE_<NAME>: constants.<NAME>_PATH,

# 4. Replace the inline block with the load call
injection_path = os.path.join("mvp_site", constants.<NAME>_PATH)
loaded = read_file_cached(injection_path).format(current_turn=turn_number)

# 5. Add to conditional_prompts in tests/test_prompts.py
constants.PROMPT_TYPE_<NAME>,  # Only on <trigger condition>

# 6. Pin the contract in the existing test file (4 cases minimum)
class Test<N>InjectionFileContract(unittest.TestCase):
    def test_injection_md_file_exists(self): ...
    def test_injection_md_file_binds_<X>_template(self): ...
    def test_dynamic_block_loads_from_injection_path(self): ...
    def test_agent_prompts_does_not_inline_<name>_block(self): ...

# 7. Verify byte-equivalence of the dynamic block content (marker check)
python3 -c "
import sys; sys.path.insert(0, '.')
from mvp_site.file_cache import clear_file_cache
from mvp_site.agent_prompts import PromptBuilder
from unittest.mock import MagicMock
clear_file_cache()
builder = PromptBuilder(game_state=None)
mock_gs = MagicMock(); mock_gs.last_living_world_turn = 0
mock_gs.check_living_world_trigger.return_value = (True, 'test', None)
mock_gs.get_companion_arcs_summary.return_value = ''
mock_gs.custom_campaign_state = {'next_companion_arc_turn': 3, 'companion_arcs': {}}
builder.game_state = mock_gs
out = builder.build_living_world_instruction(3)
for marker in ['COMPANION QUEST CADENCE', 'PER-TURN OBLIGATION', 'current_turn = 3',
               'current_turn + 1', 'current_turn + 2', 'Turn 3: MANDATORY',
               'next_companion_arc_turn', 'companion_arcs']:
    assert marker in out, f'MISSING: {marker!r}'
print('all markers present, length =', len(out))
"
```

The full PR #8548 diff was 5 files / +401 / −1 vs `origin/main` (cherry-picked the load-bearing cadence commits + one refactor commit). The dynamic block is byte-equivalent (1364 chars vs 1361; +3 from `os.path.join` indirection).

**Why this isn't a same-PR validator change:** broadening `pr_description_gate.py` to detect Python f-string prompt injection is a *behavior* change to the validator (it now flags more PRs). Mixing it with a refactor that *unblocks* extraction makes attribution of test failures impossible. Land the refactor first; broaden the rule in a follow-up; cite this PR's pattern in the follow-up's PR body.

## Don't panic on these

- **Self-hosted runner pool 8+ queued is normal.** Don't spam `gh workflow run mcp-smoke-tests.yml` — those dispatch on `ref=main` with `headBranch=main`, defeating the exact-SHA poll filter.
- **`Smoke Gate Wait (Gate 8)` polls up to 15 minutes.** If it's green for 4/7 (Precheck, Bugbot, CodeRabbit, your reviewerA), just wait.

## Draft→non-draft + Gate-0 chicken-and-egg (NEW v1.9.0 — PR #8509, 2026-07-21)

**The trap:** you file a PR as DRAFT, then realize the PR body needs a `## Tenets` section (Gate-0 Design Doc Grep requirement) before you can flip non-draft. You PATCH the body — Gate-0 doesn't re-fire because `design-doc-gate.yml` only watches `pull_request: [opened, ready_for_review, synchronize, reopened]`, NOT `edited`. You `gh pr ready` → "GraphQL rate limit exceeded". You try REST PATCH `{"draft": false}` → 200 OK but `draft: true` comes back unchanged. The CI is in a chicken-and-egg: most gates are guarded by `if: github.event.pull_request.draft == false` so they stay `skipped` until you flip non-draft, but Gate-0 won't run again to bless the body until an event fires.

**What ACTUALLY happens (verified PR #8509, 2026-07-21):**

```bash
# 1. PATCH the body first via REST (GraphQL is rate-limited often):
TOKEN=$(gh auth token)
curl -fsS -X PATCH \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept: application/vnd.github+json" \
  -H "Content-Type: application/json" \
  -d "$(jq -Rs '{body: .}' < $HOME/.hermes/wa-repro-8507/pr-body.md)" \
  https://api.github.com/repos/$GITHUB_REPOSITORY/pulls/8509

# 2. Force Gate-0 to re-run via workflow_dispatch (the body-only PATCH does NOT
#    fire Gate-0; an empty commit on the PR branch DOES, via the synchronize event):
git -c user.email=jleechan2015@users.noreply.github.com -c user.name=jleechan2015 \
    commit --allow-empty -m "ci: refresh gate 0 after body restructure"
git push origin HEAD:refs/heads/<branch>

# 3. The Design Doc Gate workflow is 261075490 (per `gh workflow list`); invoke it:
gh workflow run 261075490 --repo $GITHUB_REPOSITORY \
    --ref <branch> -f pr_sha=<head-sha>
# Note: takes `pr_sha` as required input.

# 4. Wait for Gate-0 to land and verify success:
sleep 30 && gh run list --repo $GITHUB_REPOSITORY \
    --workflow 261075490 --limit 2 --json status,conclusion,headSha
# → "Design Doc Gate completed success" for the head SHA

# 5. NOW flip to non-draft via GraphQL or REST:
# GraphQL (preferred when budget allows):
gh pr ready 8509 --repo $GITHUB_REPOSITORY
# REST (when GraphQL is rate-limited; core REST has separate budget):
# PATCH /repos/{owner}/{repo}/pulls/{pull_number} with {"draft": false}
```

**Why REST PATCH `{"draft": false}` returns 200 OK but `draft: true` unchanged in some sessions:** when `mergeable_state: unstable` is the GH-default state for any draft→non-draft transition AND `if: github.event.pull_request.draft == false` guards exist on real gates, the PATCH may *appear* to no-op while GH is internally queuing the transition. The actual draft flip happens when the next PATCH or action lands. **Verify with `gh api repos/.../pulls/<N> --jq '{draft,mergeable_state,updated_at}'`** — if `updated_at` is recent and `mergeable_state` is changing, the flip is in progress; if it's stuck at `unstable` for >5 min, the Gate-0 re-run hasn't landed yet.

**`mergeable_state: unstable` is NOT a draft-flip blocker.** Don't panic and don't manually merge. It just means the green-gate suite is queued or running. The flip succeeds independently.

**When the flip keeps "failing" (REST returns 200 but draft stays true):**

| State | Action |
|---|---|
| `mergeable_state: unstable` + GraphQL rate-limited | Wait 5-10 min for GraphQL to refresh, retry `gh pr ready` |
| `mergeable_state: unstable` + GraphQL fresh | Check `gh api rate_limit --jq '.resources.graphql.remaining'`; if 4887+, use `gh pr ready` directly |
| Body missing `## Tenets` or linked artifact | The flip is queued but Gate-0 will FAIL again; the flip doesn't actually go through until Gate-0 passes |
| All gates `skipped` because of `if: !PR.draft` guard | Most likely the flip *did* succeed; verify with `gh pr view --json draft` |
| Body content gates (GATE-6b 8-section scaffold) | Different gate from Gate-0; run the local validator: `python3 .github/scripts/pr_description_gate.py --body-file <body>` |

**Anti-pattern:** PATCH `draft:false` → see `draft:true` → PATCH again → see `draft:true` → repeat 5 times. Each PATCH costs REST budget. Instead: verify Gate-0 success via `gh run list --workflow 261075490 --limit 2`, confirm body has `## Tenets` + linked artifact, then ONE flip attempt.

**Why this matters:** the user's typical reaction to "PR is draft" is "make it non-draft" (3 separate mid-turn steers in this session). The agent's typical reaction is "I've already PATCHed it, why is it still draft?" Both reactions are reasonable; the missing context is that GH needs (a) Gate-0 success on the body and (b) the body content gate (`pr_description_gate.py` 8-section scaffold) before the flip is durable. Use the recipe above; expect one empty-commit retrigger + one `gh pr ready` to land the flip in a single cycle.

## "PR already merged" early-exit check (NEW v1.8.0 — PR #8467 close call)

**The trap:** you fix a CI failure, push a commit, then start polling Green Gate Precheck which keeps reporting `GATE-1 FAIL: CI=failure` or `GATE-3 FAIL: CodeRabbit rate-limited`. You push another empty commit to retrigger the gate. The precheck polls again. Same fail. You push ANOTHER empty commit. Meanwhile, the user (or `skeptic-cron.yml`, or a CodeRabbit auto-approve that finally cleared) merged the PR 8 minutes ago — but your polling loop doesn't know that.

**Symptom pattern:** Green Gate Precheck shows `conclusion: failure` on the *latest* run, but `gh pr checks` shows all real CI jobs (Directory tests, lint, etc.) PASS. The "failure" is just the gate itself reporting an old/stale evaluation.

**Mandatory first-action before pushing any empty retrigger commit:**

```bash
# 1. Is the PR even still open?
gh pr view <N> --repo $GITHUB_REPOSITORY --json state,mergedAt,mergedBy,headRefOid,mergeCommit
# If state == "MERGED" or state == "CLOSED" → STOP. Do not push another retrigger commit.
#                                  The PR is gone. Verify it landed on main and report success.

# 2. If still OPEN, are the underlying checks actually green?
gh pr checks <N> --repo $GITHUB_REPOSITORY
# Look at Directory tests / Presubmit Checks / lint / etc. — if ALL real CI jobs PASS
# and the only "fail" is the Green Gate aggregator itself, you're in the
# "gate saw a transition window, CI is fine now" trap. One empty-commit retrigger is fine.
# Two or more in a row = stop and check whether the user merged mid-poll.

# 3. If still OPEN and checks show real failures, fix the underlying CI issue first
#    (per `evidence-attach-presend-gate` and `same-test-name-rule`).
```

**Why this matters:** every empty-commit retrigger on a closed/merged PR is a wasted push (and a tiny noise burst on the PR timeline). More importantly, you burn your iteration budget retriggering a gate that no longer matters — when the user has been waiting for you to *report success* on the merge.

**Verified incident (PR #8467, 2026-07-21):** the user (`jleechan2015`) merged the PR at 2026-07-21T02:11:18Z while I was in the middle of an empty-commit loop waiting for Green Gate polls to settle. I pushed `ba9b69091b` (after the fix) and `e3df733ce3` (after CI fully green) — both went onto a now-merged PR head. The actual fix landed cleanly (`9f6fbc9bd6` is in `origin/main` via the merge commit `a659905baa`), but the session ended with 2 wasted empty commits and an unfinished gate-recovery narrative instead of a clean "PR merged at <SHA>, fix verified on origin/main, all checks green" report.

**Heuristic — when to stop retriggering Green Gate:**

| `gh pr view` state | `gh pr checks` shows | Action |
|---|---|---|
| `OPEN` | Any real CI red | Fix the CI issue, then one retrigger commit |
| `OPEN` | All real CI green, only Green Gate aggregator red | One empty-commit retrigger. If still red after that, **stop** and read the gate log for the GATE-* line — GATE-3 (CodeRabbit) is rate-limited, that's a known non-issue per env-preferences.mdc |
| `MERGED` or `CLOSED` | (don't matter) | **STOP immediately.** Verify the merge commit is in `origin/main` via `git merge-base --is-ancestor <merge-commit-sha> origin/main`, then report success. Do not push retriggers. |

## Setting-agnostic invariant regression (NEW v1.8.0 — PR #8467 v2)

**Symptom:** `Directory tests (core-mvp-2(self hosted))` fails because `test_divine_prompts_setting_agnostic.py` reports 3 failures on a PR that touches `$PROJECT_ROOT/prompts/divine/`:
- `test_no_dnd_default_entities` — D&D entities (`Mystra`, `Helm`, `Oghma`, `Savras`, `Torm`, `Shar`, `Karsus`, `Mystryl`, `Netheril`, `Forgotten Realms`, `the Weave`) leaked into default text
- `test_no_ao_in_default_text` — standalone `Ao` leaked into default text
- `test_hud_observers_are_generic` — `[DIVINE HUD ... ACTIVE OBSERVERS: ...]` block missing or references D&D entities

**Why this class fires on divine-system PRs:** the `divine_leverage_system.md` prompt has an explicit setting-agnostic contract — D&D Forgotten Realms entities belong ONLY in the `## Appendix A: D&D Forgotten Realms Adaptation Appendix` section at the bottom. The test reads the file, splits at the `APPENDIX_MARKER = "# Appendix A: D&D Forgotten Realms Adaptation Appendix"` line, and asserts that the *default-text portion* (everything above the marker) has zero D&D entity mentions. Any new example, worked sample, or HUD template that uses `Oghma`, `Mystra`, `Ao`, or `Forgotten Realms` as a default reference fails the test.

**Trigger table — content that ALWAYS fails this test class:**

| Content | Where it goes wrong | Fix |
|---|---|---|
| Worked example like `STATUS: Suspicion (Oghma's faction is the most suspicious)` | default-text worked example | Replace with generic placeholder: `(the watch-god's faction is the most suspicious)` |
| Example like `for D&D Forgotten Realms see Appendix A.3` | default-text docs | Replace with: `(the Appendix A.3 mapping is for reference only when the campaign is D&D)` |
| Example like `e.g. Ao in D&D Forgotten Realms` | default-text Apex Predator removal note | Replace with: `(the top-tier cosmic entity)` |
| Dropped HUD `> ACTIVE OBSERVERS:` line when restructuring the HUD template | default-text HUD template | Restore the line with generic placeholders: `> ACTIVE OBSERVERS: [None / The Watchers / The Seers / etc.]` |
| `"the Weave"` or `"Netherese High Magic"` anywhere in default text | any | Move to D&D Appendix or replace with `the source-fabric` / `the primordial magic substrate` |

**Run this locally before pushing any PR that touches `$PROJECT_ROOT/prompts/divine/`:**

```bash
cd $HOME/.worktrees/<branch>
python3 -m unittest mvp_site.tests.test_divine_prompts_setting_agnostic -v
```

If it fails, the artifact log at `$PROJECT_ROOT/test-results/test_divine_prompts_setting_agnostic.py.<hash>.log` lists the exact `span=(N,M)` offset of each leaked entity — no need to re-derive. The diff is always < 10 lines and surgical: never rewrite the prompt, just neutralize the leaked entity reference.

**Why this matters for `/green`:** GATE-1 (`Directory tests (core-mvp-2)`) is fail-closed. This test class is the dominant cause of GATE-1 FAIL on prompt-only PRs touching the divine tier. Catching it locally saves the 6-7 min CI cycle + the empty-commit-retrigger dance.

## Verification (post-cleanup)

```bash
gh pr view <M> --repo $GITHUB_REPOSITORY --json additions,deletions,changedFiles
# Expect: small diff matching title (e.g., 4-10 files, <100 lines)

gh pr checks <M> --repo $GITHUB_REPOSITORY
# Expect: Precheck PASS, Bugbot PASS, CodeRabbit PASS, Smoke pending
```

## Anti-patterns to avoid

1. **Don't `git checkout origin/main -- <files>` on a worktree that has re-replayed merges** — it'll introduce a 22-file diff that conflates net-new with old/merged work.
2. **Don't `sed -i.bak` and then commit** — BSD sed on macOS leaves `*.bak` files unless you `set -e` early. Use `patch -p1` with a fenced diff or `write_file` from a Python script.
3. **Don't try to fix the gate** before auditing the PR. The gate is enforcing AGENTS.md evidence policy. Fix the PR shape.
4. **Don't re-dispatch `/smoke` from `gh workflow run`** — comment-router dispatches on `ref=main` which breaks `headBranch` filter. The natural flow: deploy-preview must land first, then mcp-smoke-tests picks up the PR head SHA via `pr_ref` outputs.
5. **Don't `git push origin HEAD:refs/heads/origin/main`** — this creates a parallel `origin/main` branch on the remote that confuses future `git merge-base origin/main HEAD` lookups (returns empty).

## LOC ratchet + Design Doc line-count failure (NEW v1.9.0 — PR #8536, 2026-07-23)

**Symptom — two related ratchet failures on the same PR:**

1. **Function LOC Ratchet (`Function LOC Ratchet (world_logic.py / llm_service.py)` job in `presubmit-checks.yml`):** prints e.g. `process_action_unified grew from 2101 to 2149 lines (baseline exceeded by 48). Extract/shrink the function or run --update only after a deliberate size increase is reviewed and approved.` The ratchet enforces per-function line-counts stored in `scripts/function_loc_baseline.json`.
2. **Design Doc Grep Gate (`world_logic.py line count` row in `design-doc-gate.yml`):** prints e.g. `expected ≤12000, actual 12108 FAIL`. This is a separate file-level bound (currently 12000) that any production PR can trip by adding net lines to `$PROJECT_ROOT/world_logic.py`.

**User's literal directive that triggered this class:** *"raise this limit then merge the PR github.com/.../89346420267?pr=8536"*. The user is granting approval to raise the ratchet — they want the PR green, not a refactor.

**Working recipe (verified PR #8536, 2026-07-23):**

```bash
# 1. BEFORE editing any numeric constant, obey grep-before-constant-change across the project:
rg "2101" -l   # the OLD process_action_unified baseline; find every duplicate
rg "process_action_unified" -l scripts/function_loc_baseline.json scripts/check_function_loc_ratchet.py tests/scripts/test_check_function_loc_ratchet.py
# Every hit must be updated together in one commit. Common dup sites:
#   scripts/function_loc_baseline.json  (the JSON baseline)
#   scripts/check_function_loc_ratchet.py  (the default-allowance value)
#   tests/scripts/test_check_function_loc_ratchet.py  (asserts the bound)
# Leaving a duplicate = CR/bugbot flags the ratchet as still misconfigured.

# 2. Make the SMALLEST deliberate baseline update that accepts the current size:
# - For the function ratchet: bump only the `process_action_unified` entry from 2101 to 2149
#   (or 2150 to leave a 1-line margin) in `scripts/function_loc_baseline.json`.
# - Update any test that pins the old number.
# - DO NOT bump the global per-function cap (e.g. 2101 -> 2500 for all functions) just to
#   mask unrelated growth. The ratchet is per-function for a reason.

# 3. For the separate world_logic.py line-count bound (Design Doc Grep):
# - Bump ONLY the targeted file's bound in the workflow comment, e.g. 12000 -> 12200
#   with a note explaining the merged-main growth that justified the bump.
# - Don't raise the bound to e.g. 15000 to swallow unrelated future growth.
# - The workflow comment block in design-doc-gate.yml is the source of truth.

# 4. Verify locally before push:
python3 scripts/check_function_loc_ratchet.py
wc -l < $PROJECT_ROOT/world_logic.py
# Both must show PASS / within the new bound.

# 5. Commit + push; PR title MUST be honest about the limit raise (not "minor cleanup"):
git commit -m "chore(ratchet): raise process_action_unified baseline 2101->2149 (PR #8536 god-mode directive lifecycle)"
git push origin fix/bq-godmode-directive-lifecycle-events
git rev-parse origin/fix/bq-godmode-directive-lifecycle-events
```

**Why the deliberate `2101 -> 2149` and not `2101 -> 3000`:** the ratchet is a regression alarm. Bumping the baseline to 3000 because one function is now 2149 lines silently disables the alarm for every future growth between 2149 and 3000. The audit-defensible bump is the minimum required + a small margin (1-5 lines), with a code comment explaining which PR added the size.

**Diagnostic recipe for the world_logic.py bound:** the line bound is enforced inside `design-doc-gate.yml` with `check_upper_bound "world_logic.py line count" "12000" "wc -l < $PROJECT_ROOT/world_logic.py"`. If the PR touches `$PROJECT_ROOT/world_logic.py` and the file is now >12000 lines, this gate fails BEFORE CodeRabbit even sees the diff. The bound value lives in the workflow YAML, NOT in any constant file.

**Pitfall — silent overall-cap raise:** grep the workflow file for OTHER upper-bound `wc -l` checks before bumping `world_logic.py`. If a sibling `wc -l < $PROJECT_ROOT/llm_service.py` is also in the 11000 range and the PR doesn't touch it, raising the bound on the wrong file would mask the alarm. Always scope bumps to the file(s) the PR actually grew.

## Mis-closed "Superseded by #N" PR (NEW v1.9.0 — PR #8536, 2026-07-23)

**Symptom:** the user asks you to drive a specific PR #M to green. `gh pr view M --json state` returns `"CLOSED"`. A search for sibling PRs finds #N where the body says *"Superseded by #N"*. The close comment is short and references a PR title/branch that look unrelated to PR #M's title/branch/files. `ao spawn --claim-pr M` fails with `failed to claim PR M: PR is not open (PR_NOT_OPEN)`.

**Verified incident (PR #8536, 2026-07-23):** PR #8536's body claimed it was "Superseded by #8537 (the narrow, non-conflicting version)". But #8537's title is *"fix(cost): make SYSTEM_INSTRUCTION_EMERGENCY_THRESHOLD an actual functional floor"* — entirely unrelated to #8536's *"fix(bq): log god-mode directive lifecycle events for forensic visibility"*. They touch different files, different bead IDs (`rev-duqrw` vs `rev-z4gv5`), different scopes. The supersede claim was a mislabel by the previous PR author.

**Anti-pattern — trust the supersede claim and abandon PR #M:** the user's literal directive was `/green PR #M`. The "Superseded by" comment is an artifact of prior-agent behavior, not a user instruction. Don't abandon the user's request because a comment said so.

**Mandatory verification recipe BEFORE reopening or abandoning:**

```bash
# 1. Compare the two PRs by title/branch/files/bead:
gh pr view <M> --repo <OWNER>/<REPO> --json title,headRefName,files --jq '{title,branch:.headRefName,files:[.files[].path]}'
gh pr view <N> --repo <OWNER>/<REPO> --json title,headRefName,files --jq '{title,branch:.headRefName,files:[.files[].path]}'
# If file paths overlap by >=80% AND titles are in the same domain → legit supersede.
# If file paths don't overlap OR titles are unrelated → MISLABELLED supersede, the literal PR is the canonical one.

# 2. Check the bead ID / issue link in each body:
gh pr view <M> --json body --jq '.body' | grep -oE 'rev-[a-z0-9]+|#[0-9]+|#[A-Z]+-[0-9]+' | sort -u | head -5
gh pr view <N> --json body --jq '.body' | grep -oE 'rev-[a-z0-9]+|#[0-9]+|#[A-Z]+-[0-9]+' | sort -u | head -5
# Different beads, different issues → independent work, not a real supersede.

# 3. Check the timeline for the actual close reason:
gh api repos/<OWNER>/<REPO>/issues/<M>/timeline --jq '.[] | select(.event=="closed") | {actor:.actor.login, created_at}'
# If the close actor is `jleechan2015` and the only comment before close was
# the "Superseded by #N" self-comment, it's a mislabel — reopen.

# 4. REOPEN (only if (1) and (2) say it's a mislabel):
gh api -X PATCH repos/<OWNER>/<REPO>/pulls/<M> -f state=open \
  --jq '{number,state,html_url,head_sha:.head.sha}'
# Verify state changed to "OPEN" before proceeding:
gh pr view <M> --json state --jq .state

# 5. Now `ao spawn --claim-pr <M>` works:
ao spawn --project <project> --claim-pr <M> --no-takeover --harness agy --prompt "..."
```

**Why this matters for `ao spawn`:** `ao spawn --claim-pr <N>` runs `gh api repos/<owner>/<repo>/pulls/<N>` to verify ownership before creating a session. The API returns 422 (`PR_NOT_OPEN`) for closed PRs even when they were just closed moments ago. The verifier path has NO automatic reopen — the agent must reopen manually before the spawn succeeds.

**Edge case — the supersede was legit:** if `gh pr view <M>` and `gh pr view <N>` show 80%+ file overlap and the same bead ID, the supersede is real. The right move is to drive #N instead, with a one-line acknowledgment to the user: *"`/green PR #M` → #M was legitimately superseded by #N (same files + bead). Driving #N instead."* Don't blindly reopen a PR that's already been replaced.

**Forbidden pattern — leaving the mislabel in place:** if the supersede is wrong, you MUST reopen #M AND leave a comment on #N correcting the cross-reference. Otherwise a future session sees the same "Superseded by #N" comment and repeats the disambiguation.

## Three-way "merge if approved" conditional (NEW v2.1.0 — PR #8462, #8544, 2026-07-24)

**Symptom — the user pattern:** *"Review logging PRs and merge approved if /green and /er and /advice approved."* The same word will appear for every batch-review request. The condition is three approvals, ALL required. Merging on partial signal violates the gate.

**The three signals, where they live, and how to look them up:**

| Signal | What it is | Where to find it | Pass pattern |
|---|---|---|---|
| `/green` | 7-green gate (7 conditions in SOUL.md) | `gh pr view <N> --json statusCheckRollup` + reviews + comments | All 7 conditions green, no failing check, last CodeRabbit state = `APPROVED`, no unresolved CR comments, evidence-review-bot PASS, github-actions[bot] `VERDICT: PASS` |
| `/er` | evidence-review verdict | PR comments, posted by `jleechan2015` by the evidence-review run | Body contains `Evidence review verdict: /er PASS` (or `/er FAIL <reason>` when failing) |
| `/advice` | docs-accuracy second-opinion | PR comments, posted by `jleechan2015` by the advice run | Body contains an explicit "approve"/"LGTM" signal — note: when no advice comment exists yet, `/advice` is **not approved** (default-deny) |

**Critical pitfalls:**

1. **`/er` and `/advice` are NOT user-invocable Hermes slash commands** in the way `/simplify` or `/er` (if it exists as a skill) would be. They are **PR-comment verdicts** posted by evidence-review and advice runs that the user invokes separately. When the user says "/er and /advice approved", they mean: *look up those comments on the PR — if both are present and both say PASS, the conditional is met*. If either is missing or says FAIL, the conditional is NOT met, regardless of what `/green` says.

2. **Default-deny on missing verdicts.** A PR with no `/er` comment at all is `/er: NOT APPROVED` (not "neutral", not "pending"). A PR with no `/advice` comment is `/advice: NOT APPROVED`. Don't merge on absence of verdict; the user is asking you to verify the verdict exists.

3. **Green Gate (aggregator) ≠ underlying CI.** Green Gate Precheck can report `SUCCESS` while `Directory tests (core-mvp-2(self hosted))` is `FAILURE`. The aggregator is a *summary* — verify the underlying check-runs (`gh api repos/.../commits/<sha>/check-runs`) directly. Look for the latest run of each named check, NOT the aggregator's conclusion.

4. **CodeRabbit state in 7-green is `APPROVED` of latest, not historical.** If CodeRabbit said APPROVED on commit 1, CHANGES_REQUESTED on commit 2, then COMMENTED on commit 3 (e.g. rate-limit summary), the *latest* state is COMMENTED — NOT APPROVED. The 7-green gate is fail-closed here.

**Verdict-lookup recipes (zero-LLM, run before claiming "/er approved"):**

```bash
# /er verdict on PR #N
gh api repos/$GITHUB_REPOSITORY/issues/<N>/comments --jq \
  '[.[] | select(.body | test("/er ")) | {user: .user.login, created_at, body}] | .[-1]'
# Expect body to match: /er PASS  OR  /er FAIL <reason>
# If empty array: /er was never run on this PR → not approved.

# /advice verdict on PR #N
gh api repos/$GITHUB_REPOSITORY/issues/<N>/comments --jq \
  '[.[] | select(.body | test("/advice ")) | {user: .user.login, created_at, body}] | .[-1]'
# If empty: /advice was never run → not approved.

# Underlying CI checks (the truth under Green Gate aggregator)
gh api repos/$GITHUB_REPOSITORY/commits/<head_sha>/check-runs --jq \
  '.check_runs | sort_by(.started_at) | reverse | unique_by(.name) | .[] | {name, conclusion, started_at}'

# CodeRabbit latest review state
gh api repos/$GITHUB_REPOSITORY/pulls/<N>/reviews --jq \
  '[.[] | select(.user.login == "coderabbitai[bot]")] | max_by(.submitted_at) | {state, submitted_at}'

# Skeptic verdict (Gate 7 — github-actions[bot] VERDICT: PASS)
gh api repos/$GITHUB_REPOSITORY/issues/<N>/comments --jq \
  '[.[] | select(.user.login == "github-actions[bot]" and (.body | test("VERDICT: PASS"; "i")))] | .[-1]'
```

**Tool pitfall — `gh pr checks` requires `--watch` (interactive).** It exits immediately with empty output in non-TTY mode. The working pattern is `gh api .../check-runs` (REST, no watch required) as shown above. Don't waste iteration budget trying to make `gh pr checks` work — switch to the API.

**The "reviewer batch" workflow (what to do when the user asks "review N PRs and merge approved"):**

1. For each PR in the batch, run all four lookups in parallel (3 curl commands + 1 `gh pr view --json`). This is read-only and fast.
2. For each PR, build a 3-row verdict table (`/green: PASS/FAIL`, `/er: PASS/FAIL/NA`, `/advice: PASS/FAIL/NA`).
3. Only PRs where ALL THREE are PASS are merge candidates. Stop. Report to the user.
4. For PRs where any verdict is FAIL or NA, do NOT merge. Report the missing/failed verdict explicitly and offer the next-action (drive-to-green AO spawn, or "user handles themselves").
5. Never merge a PR where you have to *guess* at any of the three verdicts. The user invoked the conditional for a reason.

**Verified session 2026-07-24 (PR #8462, #8544):** user asked to "review and merge approved if /green and /er and /advice approved". PR #8462 had an existing `/er FAIL Green Gate + Gates 1-6 fail; CodeRabbit rate-limited; canonical **Evidence**: <gist> (head <sha>) line absent` comment from 2026-07-21, plus 2 of 3 self-hosted MVP test shards FAILING on the latest commit, plus no `/advice` comment. PR #8544 had `Function LOC Ratchet` FAILING, no CodeRabbit review (rate-limited only), no `/er` or `/advice` comment. NEITHER met the conditional. Neither was merged; both were reported with the exact missing verdict and a "next action" recommendation. This is the canonical example of the pattern.

## Support files

- `scripts/verify_user_visible_diff.sh` — **NEW v1.1.0** — auto-detects the "backend-only field-add with no frontend consumer" class. Pulls the deployed PR preview's `app.js` + `api.js`, greps for new field names, and reports hits inside `jsonError` 429 handling (no success-path consumer) vs outside. Returns RED FLAG (exit 0) when at least one PR-added field is unread on the success path. Use before merging any PR whose title/issue promises a UX change.
- `templates/pr-body-8-section.md` — **NEW v1.3.0** — copy-paste this scaffold into every worldai PR body. Includes all 8 canonical sections (`## Summary`, `## Production Code Changes`, `## Test Changes`, `## Known Limitations`, `## Unit Test Evidence`, `## Non-Unit Test Evidence`, `## Real LLM Evidence`, `## Evidence`) with anchor-shaped code blocks pre-baked for the 4 evidence sections. Running `python3 .github/scripts/pr_description_gate.py --body-file <body>` against this template returns `overall: PASS` before any CI cycle.
- `scripts/dispatch-real-smoke.sh` — **NEW v1.4.0** — POST a REAL-mode `MCP Smoke Tests` workflow_dispatch for a given PR number via the REST API. Use when Gate-8 fails with "default smoke runs in MOCK mode and does not satisfy the gate". The PR-comment `/smoke` route hardcodes MOCK (comment-router does not pass `test_mode=real`); `gh workflow run` fails with "fatal: not a git repository". Only the REST endpoint works.

## Reference files

- Your Project green gate workflow: `.github/workflows/green-gate.yml`
- PR description gate: `.github/scripts/pr_description_gate.py`
- Evidence gate: `.github/workflows/evidence-gate.yml`
- Design Doc Grep gate: `.github/workflows/design-doc-gate.yml`
- AGENTS.md evidence policy: `/es` and `/review` sections in `AGENTS.md`
- Self-hosted runner label var: `vars.SELF_HOSTED_RUNNER_LABELS`
- **`references/pr8485-gate0-tenets-anchor.md`** — NEW v1.7.0 — full PR #8485 case transcript. Production-code PR that needed Gate-0 `## Tenets` + linked `world_reference/*.md` artifact, plus the empty-commit re-trigger pattern (Gate-0 doesn't fire on `edited`), plus the user's mid-session "merge approved if only prompt/test" conditional that excluded the PR. Use as the canonical reference when a backend PR needs Gate-0 anchor.
- **`references/pr8467-v2-divine-prompts-setting-agnostic.md`** — NEW v1.8.0 — full PR #8467 v2 transcript. Covers (a) the `test_divine_prompts_setting_agnostic.py` 3-failure class (D&D entity leak + dropped ACTIVE OBSERVERS block) with the exact artifact-log path + span offsets + surgical fix, and (b) the "PR already merged mid-poll" loop that wasted 2 empty-commit pushes after the user merged. Use as the canonical reference when a `$PROJECT_ROOT/prompts/divine/` PR fails GATE-1, or when Green Gate Precheck stays red after CI settled green.
- Original case: PR #7953 (2026-07-15) — `feat(quota): surface quota counters on interaction success path` — +89/-16 across 3 backend files, zero frontend files, zero JS bundle hits for `daily_remaining` / `reset_time_daily` outside the pre-existing `jsonError` 429 path. Bead: `rev-u8bth`.
- **PR #8467 (2026-07-20):** PR body had `## Summary` + `## Real LLM Evidence` + `## Known Limitations` + `## Verification` — beautifully written, completely wrong shape. GATE-6b validator reported 5 missing sections. Without the 8-section template, every agent author who knows the project well but doesn't have the section list memorized burns 2-3 CI cycles (6-9 min) to discover the right shape.
- **PR #8485 (2026-07-20):** disable sovereign/multiverse tier. 5 production files. Needed Gate-0 anchor (`## Tenets` + `world_reference/aizen_god_mechanics.md` link). After 3 empty commits: 5/7 green (GATE-0 PASS, GATE-2 PASS, GATE-5 PASS, GATE-6 PASS, GATE-6b PASS; GATE-1 + GATE-3 stuck on vendor rate-limits). User's "merge approved once /green AND only prompt/test" conditional excludes this PR → did NOT merge.
- **`gh-rate-limit-and-transient-failures` (sibling skill):** when `gh pr checks` returns `GraphQL rate limit exceeded` mid-debug, the working recipe is `gh api -H 'Accept: application/vnd.github+json' -H 'X-GitHub-Api-Version: 2022-11-28' ...` (REST endpoints, not subject to the GraphQL bucket).
