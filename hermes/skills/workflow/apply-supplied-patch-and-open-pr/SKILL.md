---
name: apply-supplied-patch-and-open-pr
version: 1.1.0
description: |
  When a user (often via Slack, GitHub, or email) sends a pre-built patch + a
  structured instructions file (UPSTREAM-PROMPT.md style) and asks you to open
  the PR — clone the target repo, branch from origin/main, git am the patch,
  run the user's listed test suites verbatim, push, and open the PR with the
  title/body the user supplied. Distinct from `always-pr-never-local-edit`
  (which dispatches fix-X work to AO), and from `github-pr-workflow` (general
  PR lifecycle); this is the bounded "land this patch" workflow where the
  intent, title, body, and verification gates are pre-specified.

  v1.2.0 adds Pitfalls P8 (force-push after origin branch deletion), P9
  (two-tier "delete X gate" distinction — workflow gate vs pipeline node
  type), and P10 (pre-existing test-failure attribution via stash/reset/
  restore). Verified case #3 (2026-07-21, dark-factory PR #407 skeptic-
  gate deletion + receipt-gate-reviewer follow-up commit).

when_to_use: |
  - User message has an attached `.patch`/`.diff` file AND a text description
    of where it should land ("apply this to disk_magician", "open a PR on
    <repo> with this", etc.)
  - Slack/GitHub/email message body is short ("Handle", "apply this", "open
    the PR") because the *files* are the ask, not the body text
  - User-provided instructions file lists exact test suites and exact PR title
    + body template (often called UPSTREAM-PROMPT.md, RUNBOOK.md, HANDOFF.md)

triggers:
  - "Handle"
  - "apply this patch"
  - "open the PR with this"
  - "land this upstream"
  - "git am this"
  - "use the instructions in the attached file"

allowed-tools:
  - mcp__slack__*
  - terminal
  - read_file
  - write_file
  - patch
  - skill_view

context: inline
---

# apply-supplied-patch-and-open-pr

Apply a user-supplied patch to its target repository, run the listed verification
suites, push, and open the PR with the title + body the user provided. Distinct
from `always-pr-never-local-edit` (route-through-AO for general fix work) and
from `github-pr-workflow` (general PR lifecycle).

## When this skill fits

This is the right skill when ALL of the following hold:

1. The user has sent a **pre-built patch file** (typically `.patch` or `.diff`
   attached to a Slack/GitHub/email message). The diff is *not* something you
   need to write.
2. The user has sent **structured instructions** — either inline in the
   message body or in a sibling instructions file (often named
   `UPSTREAM-PROMPT.md`, `RUNBOOK.md`, `HANDOFF.md`, or `<name>-PROMPT.md`).
   These instructions explicitly call out:
   - The target repository (e.g. `jleechanorg/disk_magician`)
   - The branch name to create (e.g. `findings-wiki-contract`)
   - The list of test suites to run (e.g. `tests/test_safety_lib.sh`)
   - The PR title + body template
   - Whether to merge or leave for review
3. The work is **bounded** — pre-specified, not iterate-to-green. If the patch
   doesn't apply cleanly, fall back to `git apply --3way` per the instructions,
   then conflict resolution per the recipe below.

If ANY of these is missing (no patch, no instructions, OR unclear target),
this is NOT the right skill — fall back to either:

- **`always-pr-never-local-edit`** if the user said "fix X" and you have to
  figure out the diff yourself
- **`github-pr-workflow`** if it's a general PR task without a supplied patch

## Trigger-1 anti-pattern: don't narrate before reading attachments

When a Slack message has a body word like "Handle" (1-2 words, generic) AND
file attachments, **the attachments are the ask**, not the body. The wrong
move is to immediately write narration messages like:

- "I see file attachments..."
- "Let me work on this..."
- "On it — applying the patch..."

before checking what the attachments actually are. The right move is to
**download the attachments first, read them, then compose a single coherent
response**. Verified failure mode (2026-07-15, jleechanorg/disk_magician
PR #17): the bot wrote 4 narration messages before realizing the body text
was empty/short and the actual ask lived in the patch + UPSTREAM-PROMPT.md
file pair.

**The rule:** if `mcp__slack__conversations_replies` shows a parent message
with `files: [...]` populated and a body of ≤5 words, the first tool call
in the response turn MUST be reading the files — not writing a narration
message.

## Recipe — the 7-step bounded workflow

### Step 1 — Pre-flight checks (parallel, fast)

```bash
# A) gh auth status
gh auth status 2>&1 | head -3

# B) Does the target repo exist + what is its default branch HEAD?
gh api repos/<OWNER>/<REPO> --jq '{default_branch, pushed_at, archived}'
gh api repos/<OWNER>/<REPO>/branches/main --jq '{sha, date}'

# C) Does a PR for this topic already exist? (REST, not GraphQL — GraphQL hits
#    rate limits fast and you can avoid them)
gh api "repos/<OWNER>/<REPO>/pulls?state=all&head=<OWNER>:<branch>&per_page=10" \
  --jq '.[] | {number, title, state, head_sha, url}'

# D) List open PRs + branches matching the topic to avoid stepping on existing work
gh api "repos/<OWNER>/<REPO>/pulls?state=open&per_page=20" \
  --jq '.[] | {number, title, head_ref, author: .user.login}'
gh api "repos/<OWNER>/<REPO>/branches?per_page=100" \
  --jq '.[] | select(.name | test("<topic-regex>")) | .name'
```

**Decision matrix (after pre-flight):**

| Finding | Action |
|---|---|
| Auth OK, repo exists, HEAD matches the patch's base SHA exactly (`git log --oneline origin/main -1` returns the SHA named in the patch message) | Proceed — `git am` will apply cleanly |
| Auth OK, repo exists, HEAD differs from the patch base SHA | Try `git am`; on conflict, abort and use `git apply --3way <patch>`, resolve, then commit. Expected conflict points per the instructions file (e.g. `pyproject.toml` version bump, `CLAUDE.md` append) |
| Auth OK, repo exists, but PR for this branch/topic already exists | STOP. Confirm with the user — do NOT push onto a non-owned PR head (see `pr-cleanup-replay` skill, Phase -1). Either push to the existing branch and comment on the PR, OR close the existing PR and open a fresh one. |
| **A prior-session PR for the SAME topic is OPEN but the new patch is a "refreshed/supersedes" version** (new instructions file says "REFRESHED … supersedes the YYYY-MM-DD patch", OR the existing PR's base SHA is N commits behind current `origin/main`) | This is the **supersede pattern** — see Pitfall P7. Open a NEW branch from current `origin/main` (e.g. `<branch>-v2`), apply the refreshed patch, open a NEW PR, then **close the prior PR with a "superseded by #N" comment** linking to the new PR. Do NOT rebase the prior PR; do NOT push onto its branch head. The new PR is the source of truth. |
| A related branch exists with the same topic but not yet PR'd | Inspect it: `gh api .../compare/<patch-base-sha>...heads/<related-branch>` — if `ahead_by > 0` and the topic matches, consider whether to push onto that branch instead of opening a parallel one |

### Step 2 — Clone to a scratch dir (NOT the user's home directory)

```bash
SCRATCH=/tmp/<task-prefix>-<unix-ts>
mkdir -p "$SCRATCH"
cd "$SCRATCH"
git clone --quiet https://github.com/<OWNER>/<REPO>.git repo
cd repo

# Verify local HEAD matches origin/main (sanity)
git rev-parse HEAD       # should equal the SHA from Step 1.B
git fetch origin main --quiet
git rev-parse origin/main  # same as above
```

**Why scratch /tmp/:** the user's home directory has a directory-state tracker
(`CLAUDE.md` "Working directory lock — stay in the session's primary cwd"),
and writing to an existing home dir creates the "file modified since read"
divergence error. A scratch dir is fully isolated.

### Step 3 — Branch + apply the patch

```bash
# Branch from origin/main (clean, no carried-over history)
git checkout -B <branch-name> origin/main
git rev-parse HEAD  # confirm same as origin/main

# Apply the patch (provided the base SHA matches)
git am <path-to-patch>
echo "git am exit: $?"

# If git am fails (HEAD has moved past the patch base):
#   1. git am --abort
#   2. git apply --3way <patch>
#   3. Resolve conflicts per the instructions file (often only pyproject.toml
#      version + CLAUDE.md appends are conflict points)
#   4. git add <resolved-files>
#   5. git commit -m "<original-commit-message>"
```

### Step 4 — Run the user-listed test suites verbatim

The instructions file lists specific test paths. Run EACH one and capture the
exit code. Do NOT substitute "I think these tests are equivalent" — the user
gave you an exact list because those are the gates they want on the PR.

```bash
echo "=== <test-suite-1> ==="
bash <path-to-test-1> 2>&1 | tail -15
echo "exit=${PIPESTATUS[0]}"

echo "=== <test-suite-2> ==="
bash <path-to-test-2> 2>&1 | tail -15
echo "exit=${PIPESTATUS[0]}"

# ...repeat for each suite listed in the instructions file
```

**Required evidence per suite:**
- Exit code (printed)
- Last 10-15 lines of output (so the user can see PASS/FAIL counts)
- For pure-PASS suites: the line that says "ALL TESTS PASSED" or equivalent

**If a test FAILS:** STOP. Do NOT push. Do NOT open the PR. Report the
failing test verbatim in the Slack reply and ask the user how to proceed.

### Step 5 — Verify guardrails from the instructions file

Most UPSTREAM-PROMPT.md files list guardrails like:
- "No machine paths (/Users/<name>/...) belong in any committed file"
- "Must not add any file under findings_wiki/ other than README + TEMPLATE"
- "Run `findings_lint.sh --upstream` for purity"

Verify each guardrail with a `grep`/`ls`/the linter the instructions file
calls out. The pitfalls section below has worked examples.

### Step 6 — Push + open the PR

```bash
# Push (pre-push secret guard runs automatically on jleechanorg/* repos)
git push -u origin <branch-name>
echo "remote SHA: $(git rev-parse origin/<branch-name>)"
# Confirm SHA matches local: must equal `git rev-parse HEAD`
```

**Open the PR** with title + body from the instructions file (verbatim, but
un-indented if it was indented by the user):

```bash
~/.hermes/scripts/gh-safe-publish pr create \
  --repo <OWNER>/<REPO> \
  --base main \
  --head <branch-name> \
  --title "<exact title from instructions file>" \
  --body-file /tmp/<task-prefix>/PR_BODY.md

# Capture
gh pr list --head <branch-name> --json number,title,url,state
```

**Do NOT merge** unless the instructions explicitly say "merge it yourself".
Most UPSTREAM-PROMPT.md files say "leave the PR for the repo owner to review"
out of politeness — but the agent's default is also "no merge without explicit
`MERGE APPROVED`" per SOUL.md merge discipline.

### Step 7 — Post the Slack reply

If the user sent this from Slack, post ONE reply with:
- PR URL (linked markdown, see `.cursor/rules/pr-hyperlink.mdc`)
- Branch name + final SHA
- Exit code + tail of each test suite
- A summary of the guardrail checks
- The patch location if archived (gist URL or local path)

If `mcp__slack__conversations_add_message` returns `not_in_channel` (sub-class
5f, cross-workspace bot-token hard-block), follow SOUL.md
`slack-cross-workspace-fallback-xoxp` — fall back to `SLACK_USER_TOKEN` via
Path B curl. Note in the message body if the message will appear under the
user's identity instead of the bot identity.

Schedule a one-shot 20m check-back cron per
`## COMMIT: one-time-status-cron-after-every-task` so the user gets a
follow-up only if CodeRabbit posts a verdict or the user comments.

### Step 8 — Cleanup

```bash
rm -rf /tmp/<task-prefix>/repo /tmp/<task-prefix>/PR_BODY.md
# Optional: preserve the patch itself at /tmp/<task-prefix>/<patch-file>
# for re-application if the user wants to redo the PR
```

## Pitfalls

### P1 — Overwriting non-owned PRs (cross-ref `pr-cleanup-replay`)

If Step 1.C finds an existing PR whose branch or title matches the new topic,
DO NOT push onto that branch's head. The user's instructions file may not
mention an existing PR because they were written assuming a clean slate. Stop
and ask. The verifying-SHA check (`gh api repos/.../branches/<branch>`) tells
you whose PR it is — if it's not yours, the right move is to open a NEW PR
on a NEW branch from `origin/main`, leaving the existing PR alone.

### P2 — The instructions file lists "git am" but `git am` fails

The instructions file usually has a section like "If `git am` fails... use
`git apply --3way`". But the actual conflict resolution is project-specific.
Common conflict points across `jleechanorg/*` repos:

- **`pyproject.toml` version bump** — instructions usually say "take the
  higher version and bump patch". The pattern is to read the current version,
  read the patch version, take `max(current, patch)` and increment patch by 1.
- **`CLAUDE.md` append** — instructions usually say "append the two new
  sections at the end". The pattern is `cat >> CLAUDE.md << 'EOF'` then
  commit with the same message.
- **Sub-tree duplication** — some `jleechanorg/*` repos mirror `scripts/` to
  `src/<package>/scripts/`. If the patch touches one but not the other, the
  conflict resolution is to also apply the patch to the mirroring path
  (often a separate `cp` or `rsync`).

If the conflict is none of the above, STOP and ask. Do not invent a resolution.

### P3 — Tests fail on placeholder paths the user told you to ignore

The instructions file may say "No machine paths (/Users/<name>/...) belong
in any committed file" — but the patch itself may contain
`/Users/nobody/protected-tree` as a TEST FIXTURE in `tests/test_*.sh`. These
are deliberate placeholders (`/Users/nobody/` = "no specific user"). Do NOT
report them as a guardrail violation. Verify the placeholder is in a test
file (`tests/` or `scripts/test*`) AND uses `/Users/nobody/` (not the user's
real home), then move on.

### P4 — Both Slack tokens lack `files:write` for binary evidence

Per `evidence-attach-to-slack` v1.8.0, the OAuth scope gap on both
`HERMES_SLACK_BOT_TOKEN` and `SLACK_USER_TOKEN` means you cannot upload the
patch to the Slack thread directly. v1.9.0 covers the text-file case: push
the patch to a public gist via `gh gist create <file>` (text is text, no
clone-and-replace dance). Capture the SHA via `git clone https://gist.github.com/<id>.git`
+ `git rev-parse HEAD` and embed `https://gist.githubusercontent.com/<user>/<id>/raw/<sha>/<file>`
in the Slack reply.

### P5 — The user wants to be the assignee, not you

By default, the PR author is whoever ran `gh pr create` (which is whoever
authenticated `gh`). That's fine for jleechanorg/* repos where
`jleechan2015` is the active `gh` user. But if a different account did the
auth, the PR is owned by that account. Verify `gh pr view <N> --json author`
matches the user the instructions expect. If it doesn't, add `--assignee`
to the `gh pr create` call.

### P6 — Slack thread routing for the summary reply

After opening the PR, post the summary to the SAME thread the user started
in (per SOUL.md `slack-reply-inherit-thread-ts`). If the user's most recent
message was a HERMES-bot self-message, scan further back — do NOT reply to
the bot self-message. The `not_in_channel` error on `conversations_add_message`
indicates you need the xoxp fallback (P5 above cross-references this).

### P8 — Force-pushing a follow-up commit when the origin branch was deleted by a prior session

When the prior session shipped a PR by force-pushing, then the agent
crashed/ended before merge — and a NEW session is asked to follow up on the
same PR by adding commits — the workflow is:

1. Verify origin/PR state via `gh pr view <N> --json headRefOid` — head
   should still resolve even if the feature branch is gone locally.
2. Reconstruct from the PR's head SHA directly:
   ```bash
   git fetch origin +refs/pull/<N>/head:refs/remotes/origin/pr/<N>
   git checkout -B <branch> refs/remotes/origin/pr/<N>
   ```
3. Add the follow-up commit on top of that ref.
4. When pushing, use plain `--force`, NOT `--force-with-lease`. The lease
   target (the deleted remote ref) doesn't exist on origin, so
   `--force-with-lease` will return "stale info" and fail. Plain
   `--force` rewrites the same path (`refs/heads/<branch>`) and is correct
   here because no other agent or branch is sharing that ref.
5. Verify with `gh pr view <N> --json headRefOid` returns your new SHA
   before claiming the push landed.

Verified 2026-07-21 on `jleechanorg/dark-factory` PR #407: prior session
shipped commit `f461f93da`, then origin branch `receipt-gate-reviewer` was
deleted (no on-disk lease target). Follow-up commit `b04df6f44` pushed
with `--force` succeeded; `gh pr view 407 --json headRefOid` then
returned `b04df6f44960db5dca15b0539e9360d8956736bd` confirming PR head
moved correctly.

### P9 — Two-tier "delete X gate" distinction (workflow gate vs pipeline node type)

When the user says "delete the X gate" in a dark-factory / agent-orchestrator
project, distinguish TWO unrelated layers:

- **Workflow-level gate**: `.github/workflows/X-gate*.yml` files. These
  define GitHub Actions checks that block PRs (e.g. `skeptic-gate-caller.yml`
  triggers on `pull_request_target` and posts a `skeptic` status check).
  Deleting these removes the CI gate.
- **Pipeline-level gate type**: a handler registered in
  `runner/handlers.py` TYPE_REGISTRY (e.g. `gate_skeptic` →
  `_gate_skeptic(node, ctx)` in `runner/handler_universal_prompts.py`)
  used by DOT pipelines as a `type="gate_X"` node. Many `.dot` pipelines
  + many tests + many fixtures depend on this registration.

Deleting the workflow gate does NOT affect the pipeline node type. Most
"delete X" requests target the workflow gate (the CI blocker); deleting
both is rare and requires updating fixtures + tests.

Discovery workflow:
```bash
# Workflow gate check
ls -la .github/workflows/ | grep -i X

# Pipeline node type check
grep -rn "gate_X\b" runner/ handlers.py
grep -rn "gate_X\b" tests/ tests/fixtures/
```

### P10 — Pre-existing test-failure attribution via stash/reset/restore

When you delete code that some tests depend on, the deletion will break
those tests. To attribute which failures are caused by your deletion vs.
pre-existing on `origin/main` (per SOUL.md `same-test-name-rule`):

```bash
# 1. Capture current changes
git stash

# 2. Reset to origin/main
git reset --hard origin/main

# 3. Run the failing tests on clean main
.venv/bin/python -m pytest tests/test_X.py -v --no-header 2>&1 | tail -20

# 4. Restore the branch + changes
git checkout -B <branch> refs/remotes/origin/pr/<N>   # or origin/<branch>
git stash pop

# 5. Compare results — if same SHA, same exit code, same error line →
#    PRE-EXISTING (not your fault). Attribute correctly in the PR summary.
```

Verified 2026-07-21 on `jleechanorg/dark-factory` PR #407: 4 test
failures observed after skeptic-gate deletion; stash/reset confirmed all
4 had identical SHA + identical output on `origin/main` (3× git-lfs PATH
drift, 1× macOS `/bin/false` not-found). Zero new failures caused by
deletion.

### P11 — Fresh destructive user comments OVERRIDE prior closeouts

When the user previously claimed a PR was closed out (e.g. comment 5111574771
on your-project.com PR #8661 said "all CodeRabbit blockers fixed"), then
later posts a file comment like "Delete this" or "Do not add things specific
to a campaign", the destructive comment **overrides** the closeout — even
if the closeout was posted by the same agent. Workflow:

1. **Before executing any closeout work**, re-fetch
   `gh api "repos/<OWNER>/<REPO>/issues/<N>/comments?per_page=100"` and
   `gh api "repos/<OWNER>/<REPO>/pulls/<N>/comments?per_page=100"` and
   sort by `created_at`. If any comment is destructive-verbing
   (`delete`, `remove`, `revert`, `do not add`, `drop`, `simplify to`)
   AND newer than the most recent closeout claim, the closeout is stale.
2. **Reclassify the work** as destructive-removal: delete the named
   files/constants, then update the tests that referenced them, then push.
   Do NOT do another round of "fix the CodeRabbit findings" — the user
   is telling you the whole PR is the wrong shape.
3. **Ask one question, not five.** If the destructive comment is ambiguous
   (e.g. "delete this" without specifying scope), ask one `clarify` with
   the scope choices. Do not invent a destructive scope and do not redo
   the full closeout.
4. **Reference the newer comment in the PR comment** so the reviewer can
   see why the work shifted from "fix CodeRabbit" to "delete the artifact".

Verified 2026-08-01 on `$GITHUB_REPOSITORY` PR #8661: a
2026-07-29 closeout claimed all 5 CodeRabbit P1/P2 items were fixed.
Two 2026-08-01 user file comments ("Do not add things specific to a
campaign" on `constants.py`, "Delete this" on the overlay) overrode the
closeout. Net effect: 4 Spellblade-specific artifacts deleted, 910 lines
removed, +44/-0 net diff left on the PR (just generic shared-contract
text). The earlier fix work was not wasted — it informed the right answer
("delete the artifacts, keep the generic sections") — but the agent must
NOT have blindly executed the closeout instructions.

### P12 — Explain rebase-before-push necessity in the approval ask, not after

If a destructive-Removal rebase is required (e.g. the local branch needs
to be rebased onto current `origin/main` before push, so the cleanup
commit is a fast-forward onto the remote tip), make the rebase reason
**part of the approval ask**, not a follow-up explanation. The user
should not have to ask "why is force-push needed?" after the push lands.

**Approval-ask template** (use before any force-push that requires prior user
approval):

> Need force-push to `feat/<branch>` because the local branch was rebased
> onto current `origin/main` (N newer commits behind your remote tip
> `<sha>`), so the cleanup commit can't be a fast-forward onto the old
> remote tip. Alternative: open a new branch + new PR (safer, reviewable
> independently). Approve force-push, or pick the new-branch route?

**Why this matters:** the user typed "force push is fine although i donts
ee why thats needed" — the user accepted the push, but the framing landed
as mysterious. The next session should reverse this: name the reason
in the same message as the approval, not after.

Verified 2026-08-01 on `$GITHUB_REPOSITORY` PR #8661: the
agent should have surfaced "the local branch is 6 commits behind
`origin/main` because I rebased onto current main first" in the
approval ask, not in the post-push reply.

### P13 — Multi-reviewer fan-out loop on destructive-removal cleanup (iteration gate)

After a P11 destructive cleanup, dense PRs (multiple CodeRabbit items,
multiple reviewers, dangling references, generic-vs-campaign rules)
need a **multi-reviewer second-opinion pass** before the work is shippable.
The pattern is:

1. **List the open review items** before writing any new code: `gh api
   "repos/<OWNER>/<REPO>/pulls/<N>/comments?per_page=100"` (issue-level) + the
   `latestOpinion` GraphQL review-thread query (per-thread resolution
   state). The 2-axis matrix is: severity x staleness. Moot items (target
   file deleted) you can cross off in 30 seconds; live items need a fix plan.
2. **Run /advice (3 reviewers) + /web-advice (multi-model) in parallel.**
   The reviewer roles are:
   - **Reviewer A (source-accuracy):** byte-equality of any copied files
     (e.g. shared contracts cherry-picked from a sibling branch), include
     resolution, test suite pass count, MBTI/alignment/campaign-shaped
     string scan across the diff.
   - **Reviewer B (external-docs / spec compliance):** repo conventions
     (AGENTS.md, the prompts/CLAUDE.md), commit-attribution rule, README
     alignment, hidden internal-only data leakage.
   - **Reviewer C (adversarial):** cross-agent coverage, runtime failure
     modes for directives, orphan references, conflict with other recent
     changes.
   - **/web-advice is the cross-model independent review** — it does NOT
     share the prior context. Use `codex exec` (Codex CLI) as the
     recorded second-opinion if Aside-side Web LLM tabs (ChatGPT/Grok)
     are not available on the active account (Aside CLI on a Google-only
     account returns "model not available" for openai/gpt-5, gpt-5.x,
     anthropic/claude-sonnet-4.5, google/gemini-2.5-pro). Codex CLI is
     always available. Pull the diff into `evidence/<pr>.diff` and feed
     it as the prompt.
3. **Convergence signal:** when 2 of 3 /advice reviewers + Codex agree
   on a finding, the finding is real — fix it. Don't fix reviewer-unique
   nits unless they fall in the user's destructive scope.
4. **Re-run after fix.** Don't compose a one-shot pass — the iteration
   is the value. Watch the live transcript (`~/.hermes/cache/delegation/
   live/<deleg-id>/task-N.log`) for the final `status=completed` block
   before trusting the verdict.
5. **Final-state acceptance requires:**
   - All reviewer APPROVED-as-is verdicts collected (or only the
     deferred-to-PR-A items remaining).
   - Codex APPROVE.
   - 4-lane (ponytail/ZFC/root-cause-first) all PASS for the diff.
   - Test suite green on the rebased branch.
   - Diff is `N files / +X / -Y` with no MBTI/alignment player-facing
     exposure (verified by grep against the 16 MBTI type codes +
     big-five + alignment labels).
   - Then force-push + PR comment + 20m babysit cron.

#### P13a — Cross-prompt coverage gap (the DialogAgent pattern)

When a `{{PROMPT_INCLUDE:}}` directive lives in a parent prompt (e.g.
`narrative_system_instruction.md`) and the rule is described as
"mandatory for every agent on every turn", but a lighter agent
(`DialogAgent`) only loads a stripped variant (`narrative_lite`),
the claim is false. Two real signals that this is happening:

- `grep -A 5 "REQUIRED_PROMPT_ORDER" $PROJECT_ROOT/agents.py DialogAgent`
  returns a list that includes `narrative_lite` but not `narrative`.
- The prompt description says "every agent" but the lighter parent
  doesn't have the same `{{PROMPT_INCLUDE:}}` directive.

The fix has two options:

| Option | When to use | Cost |
|---|---|---|
| **Include from the lighter parent too** (recommended) | The rule is genuinely global (e.g. npc autonomy, witness rules) | +12 lines per lighter parent |
| **Soften the wording** in the heavy parent | The rule is heavy-parent-specific (e.g. long-form narrative only) | One-line edit, but you lose the "mandatory everywhere" claim |

The include-from-lighter-parent option is almost always right because
the rule is genuinely global — DialogAgent narrates, narrating needs
the contract. Verified 2026-08-01 on PR #8661, where the Codex
review flagged the gap and the fix was to add 4 `{{PROMPT_INCLUDE:}}`
directives to `narrative_lite_system_instruction.md` covering the
same 4 narrative contracts.

#### P13b — Pulling shared contracts from a sibling PR (the PR-A cherry-pick pattern)

When the destructively-removed code referenced contracts that live
on a sister PR (e.g. PR-A `feat/shared-contracts-mbti-internal-drive`),
**don't redeclare the contracts inline** — pull them from the sister
branch via `git show <branch>:<path>` and write them as new files.
This is the right move when:

- The sister PR has already been reviewed and the contracts are
  considered load-bearing.
- The contracts are pulling shared payload (rules, state schemas) that
  the destructive-removal PR needs to reference.
- The sister PR is the canonical source of truth for the contracts.

The pattern is:

```bash
# Verify byte-equality after pull
for f in <list-of-contracts>; do
  diff -q \
    <(git show origin/<sister-branch>:$PROJECT_ROOT/prompts/shared/$f) \
    $PROJECT_ROOT/prompts/shared/$f
done
# Should print 0 differences

# Pull only the contracts you need (not the whole branch)
for f in <list-of-contracts>; do
  git show origin/<sister-branch>:$PROJECT_ROOT/prompts/shared/$f \
    > $PROJECT_ROOT/prompts/shared/$f
done
```

**Do NOT pull the sister PR's MBTI-internal-data file** (e.g.
`ai_generated_mystery_and_internal_drive_plot_arc.md`) — that's the
internal-only personality model that lives on PR-A only. The user
explicitly stated "Did not touch PR #8539 (MBTI internal-only
canonical contract) or the PR-A worktree" in the closeout comment.
Verify with `ls <shared>/` and grep for "mystery" / "internal_drive" /
"MBTI" before commit.

**Then wire the contracts via `{{PROMPT_INCLUDE:}}`** in the parents
that need them. The `{{PROMPT_INCLUDE:}}` directive is the canonical
mechanism documented in `$PROJECT_ROOT/prompts/AGENTS.md` and `$PROJECT_ROOT/prompts/
CLAUDE.md` §"Shared rules across agents". Existing examples:
- `narrative_system_instruction.md:66` → `shared/npc_canon_anchoring.md`
- `character_creation_*.md:24-60` → `shared/skill_selection_rules.md` +
  `shared/user_directive_supremacy.md`
- `dice_system_instruction.md:59` → `shared/dice_notation_contract.md`

Use markdown-link references (`See <file>.md for the rule.`) ONLY for
human reading; the `{{PROMPT_INCLUDE:}}` directive is what the runtime
resolves. The `{{PROMPT_INCLUDE:}}` form is parsed by
`$PROJECT_ROOT/agent_prompts._resolve_prompt_includes` (fail-fast on
missing/unsafe targets — see `agent_prompts.py:817-881`).

Verified 2026-08-01 on PR #8661: 5 shared contracts pulled from PR-A
`feat/shared-contracts-mbti-internal-drive` (byte-identical, verified
via `diff -q`), wired into narrative + combat + narrative_lite, all
3 lighter agents (DialogAgent, LiteDialogAgent via narrative_lite,
StoryModeAgent via mandatory narrative injection) now see the rules.

#### P13c — `/web-advice` fallback when ChatGPT Web / Grok Web are unavailable

The `/web-advice` skill assumes multi-model access via `aside-mcp` or
browser tabs to ChatGPT Web + Grok Web + Gemini Web. On a Google-only
Aside account, the model list returns "not available" for all three
official Web LLM providers:

```
$ aside exec -m openai/gpt-5 "test"
Error: Requested model openai/gpt-5 is not available for this account.
$ aside exec -m anthropic/claude-sonnet-4-5 "test"
Error: Requested model anthropic/claude-sonnet-4-5 is not available for this account.
$ aside exec -m google/gemini-2.5-pro "test"
Error: Requested model google/gemini-2.5-pro is not available for this account.
```

The fallback when this happens:

1. **Use `codex exec` (CLI)** as the recorded multi-model second-opinion.
   It runs on `gpt-5.3-codex-spark` by default and has its own quota.
   Build the prompt + diff, save to `evidence/<pr>-prompt.md` and
   `evidence/<pr>.diff`, pass via `codex exec --cd <worktree> -m <model>`.
2. **Post the synthesis as a PR comment** with a transparency note
   explaining which models were queried. The Green Gate accept
   criterion is "independent adversarial review recorded on the PR",
   not "specifically ChatGPT Web + Grok Web".
3. **In the Slack reply**, state the constraint explicitly: "ChatGPT Web
   + Grok Web tabs were not queryable from this account (Aside-side
   model list does not include them on the active Google-only
   account). Codex is the multi-model second-opinion of record."

The Codex-as-second-opinion pattern is durable across the broader PR
review workflow — it's not specific to P13. Documented here so that
when a future session hits the same "Aside model not available" wall,
the fallback is one tool call away.

Verified 2026-08-01 on PR #8661: Codex review found the same DialogAgent
coverage gap that /advice Reviewer C found (independent convergence =
strong signal). Pre-fix verdict: CHANGES REQUESTED. Post-fix verdict:
APPROVE. The Codex approval was the deciding factor for shipping.

#### P13d — The "iterate until /advice and /web-advice approve" user directive

When the user types "keep iterating until PR comments are handled and
/advice and /web-advice approve" (or equivalent), this is a
**completion criterion**, not a vibe. The work is not done until:

1. Both /advice (3 reviewers) /web-advice (Codex) return APPROVED.
2. The diff passes the 4-lane (/document-standards) check.
3. Tests pass.
4. The PR comment is posted with the full per-comment fix map.
5. Force-push is approved + executed.
6. The 20-min babysit cron is scheduled.

If any of those gate-criteria fails, fix the underlying issue and
re-run the relevant reviewer. Don't ask the user "should I keep
iterating?" — the directive is the user explicitly saying "iterate
until X is true." The right move is to keep working until X is true
or until a hard block surfaces (missing credentials, ambiguous
preference, etc.).

Verified 2026-08-01 on PR #8661: the user-typed phrase "Keep iterating
until PR comments are handled and /advice and /web-advice approve"
drove 3 rounds of reviewer fan-out (initial → fix DialogAgent gap →
re-run) before the convergence signal was strong enough to ship. The
post-fix `/advice` Reviewer C re-run and the `/web-advice` Codex re-run
both returned APPROVED, which is the ship criteria.

### P13 checklist — when the user types "iterate until reviews approve"

When the user types "iterate until /advice + /web-advice approve" (or
the PR has multiple review items from a destructive cleanup):

1. **List open review items** via `gh api .../issues/<N>/comments` +
   `reviews(last:5)` + the `latestOpinion` GraphQL thread query. Mark
   each item as live vs. moot.
2. **For live items, identify the minimal fix surface.** Generic
   rules → `shared/` contracts via `{{PROMPT_INCLUDE:}}`. Campaign-
   specific → delete. Duplicated localization → extract to one shared.
3. **Verify the existing tests pass** on the rebased branch
   (`cd <worktree> && $HOME/projects/your-project.com/venv/bin/python -m unittest <module>`).
4. **Run /advice (3 reviewers) + /web-advice (Codex) in parallel.**
   Use `delegate_task` for the /advice fan-out. Use `codex exec` for
   the /web-advice fallback when ChatGPT/Grok Web tabs are unavailable.
5. **Convergence signal:** 2/3 /advice reviewers + Codex all agree on
   a finding → fix it. Re-run only the disagreeing reviewers.
6. **Apply the fix.** Verify tests still pass. Force-push only after
   the convergence signal is strong.
7. **Post the PR comment** with the full per-comment fix map + review
   verdicts table. Use `gh pr comment <N> --body "..."`.
8. **Schedule a 20-min babysit cron** targeting the same Slack channel
   via `hermes cron create "20m" --name "<name> status (20m)" --deliver
   'slack:<channel>' --repeat 1`. The cron will report CI status +
   CodeRabbit review flip (or self-cancel if the PR is merged).

## P7 — Refreshed patch supersedes a prior-session PR for the same topic

### P7 — Refreshed patch supersedes a prior-session PR for the same topic

This is a recurring shape when the user re-runs the same workflow with a
**refreshed patch** (e.g. new patch supersedes the previous day's patch).
The verification case (2026-07-16, disk_magician): user sent the same patch
shape (sister files: `<topic>.patch` + `<topic>-PROMPT.md`) two days in a
row; the new instructions file literally said "REFRESHED 2026-07-16,
supersedes the 2026-07-15 patch."

**Detection signals (Step 1 pre-flight):**
- A same-topic PR is OPEN from a prior session (`gh api .../pulls?state=all&head=<OWNER>:<branch>` returns a match)
- `gh api repos/<OWNER>/<REPO>/compare/<new-base-sha>...<prior-PR-head-sha>` returns `behind_by > 0` or `status: diverged`
- The instructions file says "REFRESHED", "supersedes", "v2", or similar

**What to do (no user confirmation needed — this is the natural end-state of "supersedes"):**
1. Use a fresh branch name from current `origin/main` — e.g. `<branch>-v2`,
   `<branch>-refreshed-<date>`. NEVER push onto the prior PR's branch head
   (P1 applies: that branch is owned by the prior session's commit, and
   `git push --force` onto it would rewrite history that other PRs may
   reference).
2. Apply the refreshed patch on the fresh branch (the new patch's base SHA
   should match current `origin/main`).
3. Open the NEW PR; in the body, reference the prior PR explicitly:
   `> **Note:** this PR **supersedes** [PR #N](...) — the <date> patch
   against base \`<prior-base-sha>\`. PR #N is now <N> commits behind main;
   this refreshed patch (against base \`<new-base-sha>\`) is the new source
   of truth.`
4. Close the prior PR with a comment that links to the new PR and quotes
   the user's "supersedes" directive. Do NOT delete the prior branch —
   leave it in place for diff inspection. `gh pr close <N> --repo ... --comment "..."`
5. In the Slack summary reply, name both PRs and explain the close as a
   supersede (not a rejection). One-time 20m status cron targets the new
   PR's URL.

**Why this is non-destructive and safe to do without asking:** closing a PR
with a supersede comment is a reversible action (reopen via `gh pr reopen`
in <2s). The user explicitly stated the new patch supersedes the old — the
"no confirmation gate" applies because the directive is unambiguous.

**Failure modes to avoid:**
- ❌ Pushing onto the prior PR's branch head (`git push --force-with-lease
  origin HEAD:refs/heads/<prior-branch>`) — rewrites shared history, breaks
  reviewers' local checkouts, fails SOUL.md `never-push-onto-someone-elses-pr-head`
- ❌ Asking the user "Want me to close the prior PR?" mid-stream — the
  supersede directive is the user's explicit instruction; this is the
  finish-the-job end-state
- ❌ Deleting the prior branch — leaves no diff trail if the new PR is reverted
- ❌ Forgetting to mention the prior PR in the new PR body — CodeRabbit
  reviewers will see two PRs for the same feature and ask which is canonical

## Verified case

2026-07-15, `jleechanorg/disk_magician` PR #17 — Slack message "Handle" +
two attached files (`0001-feat-safety-machine-loca.disk-magician-findings-wiki.patch`
41,016 B, and `UPSTREAM-PROMPT.md` 4,213 B / 71 lines). The instructions file
listed:

- Target repo: `jleechanorg/disk_magician`
- Branch: `findings-wiki-contract`
- Base SHA: `efc51ba` (and `git ls-remote` confirmed HEAD was exactly `efc51ba` at apply time)
- 4 test suites + 1 lint to run
- PR title + body template
- "Do NOT merge — leave the PR for the repo owner to review"

End-state: PR #17 opened, all 4 test suites green, lint clean, base SHA
exactly matched. No existing PR for the topic. No push onto a non-owned
branch. Slack summary posted via xoxp fallback (bot token had `not_in_channel`).
Patch archived at a public gist via `gh gist create` (text-file shortcut,
v1.9.0).

2026-07-16, `jleechanorg/disk_magician` PR #21 (supersedes PR #17) — same
patch shape, refreshed version. Slack message body "Make sure these are
handled or do the extra work as needed. use /ms and search slack history
might already be in progress" + 2 file attachments:
- `0001-feat-safety-machine-loca.disk-magician-findings-wiki.patch` (64,987 B
  — refreshed, supersedes the 2026-07-15 patch)
- `UPSTREAM-PROMPT.md` (188,464 B / 71 lines — explicit "REFRESHED 2026-07-16,
  supersedes the 2026-07-15 patch" in opening paragraph)

**Deltas from the 2026-07-15 patch:**
- Base SHA: `b187d8e8` (was `efc51ba`); current `origin/main` HEAD matched
  the new base exactly → `git am` applied cleanly with no conflicts.
- Scope grew: 35 files / +1092/-33 (was 17 / +856/-4). New gates wired into
 ALL cleanup scripts (was 2: `cleanup_agent_artifacts` + `cleanup_worktrees`).
 New Section N: `~/Snapchat/Dev/.cache/bazel` governance with pgrep+lsof
 liveness gates. New CLAUDE.md sections.
 - 4 test suites all green: `test_safety_lib.sh` PASS=31, `test_cleanup_safety.sh`
 93/93, `test_package_sync.sh` PASS=16 ALL TESTS PASSED, `findings_lint.sh
 --upstream` clean.
 - Prior PR #17 detected as `diverged, behind_by=14` against current main.
 Followed P7 supersede pattern: created fresh branch `findings-wiki-contract-v2`
 from `b187d8e8`, pushed `3d63d703`, opened PR #21 (MERGEABLE), closed
 PR #17 with supersede comment. Branch `findings-wiki-contract` left in
 place for diff inspection (NOT deleted).

 2026-07-21, `jleechanorg/dark-factory` PR #407 — follow-up commit on a
 prior-session PR. Slack message body "lets delete skeptic gate and then
 directly code this PR" + 3 file attachments (`GUIDE.md`,
 `INSTRUCTIONS.md`, `receipt-gate-reviewer.patch`). Prior session had
 shipped commit `f461f93da` and then the origin branch
 `receipt-gate-reviewer` was deleted (no on-disk lease target for
 `--force-with-lease`).

 **P8 applied (force-push after branch deletion):** reconstructed from
 `refs/pull/407/head`, added 3rd commit `b04df6f44` deleting
 `.github/workflows/skeptic-gate*.yml` + `.github/actions/skeptic-setup/`
 + 6 adversarial tests + `evidence-gate.yml` "Skeptic PASS" line, pushed
 with plain `--force`. `gh pr view 407 --json headRefOid` confirmed
 PR head moved from `f461f93` to `b04df6f44`.

 **P9 applied (two-tier skeptic-gate distinction):** user said "delete
 skeptic gate" — workflow-level gate (CI blocker) deleted; pipeline-level
 `_gate_skeptic` DOT node type kept (used by level5 pipelines + tests).

 **P10 applied (pre-existing failure attribution):** observed 4 test
 failures after deletion; stash/reset/restore to `origin/main` confirmed
 all 4 byte-identical pre-existing (3× git-lfs PATH drift,
 1× macOS `/bin/false` not-found). PR summary cited zero new failures.

 End-state: PR #407 `+331/-863` across 8 files, all remaining CI checks
 green (test, daemon-tests, Evidence Gate, CodeRabbit SUCCESS, Bugbot
 NEUTRAL). Skeptic no longer in `statusCheckRollup` (gate deleted).
 Bead `$USER-pm8f` closed as resolved-via-deletion.

- **No patch attached.** If the user said "fix this bug" with no diff, you
  need `always-pr-never-local-edit` + AO dispatch — that's a fix-X task, not
  an apply-supplied-patch task.
- **No instructions file.** If the user just sent a patch with no
  structured instructions, the workflow is much more flexible — you have to
  figure out the target repo, branch name, test gates yourself. That's
  closer to `github-pr-workflow` with an `apply` step added.
- **User said "apply this locally, don't push yet."** This skill assumes the
  user wants the PR opened. For "stage this and show me" tasks, do just
  Steps 1-5 then report.
- **User gave you destructive ops (force-push, branch delete on protected
  branch, etc.).** STOP. Per SOUL.md merge discipline + commit/push gate,
  destructive operations require explicit user approval in the current thread
  (`MERGE APPROVED`-style signal).

## Support files

- `scripts/apply_patch_and_open_pr.sh` — end-to-end shell recipe for the
  pre-flight + clone + branch + git am + test + push + pr-create sequence.
  Re-runnable; takes `<OWNER>/<REPO>` `<branch>` `<patch>` `<instructions>`
  as positional args.
- `references/pre-existing-failure-attribution.md` — the 5-step
  stash/reset/restore protocol for machine-checking that a test failure
  is pre-existing on `origin/main` (companion to P10; used to satisfy
  SOUL.md `same-test-name-rule` + `qa-test-failure-dismissal-anti-pattern`).
- `references/upstream-prompt-format.md` — the canonical structure of an
  `UPSTREAM-PROMPT.md` / `RUNBOOK.md` file (what sections to expect, what
  to extract from each).
- `references/refreshed-patch-supersede-pattern.md` — the recurring
  "refreshed patch supersedes prior-session PR" shape (Pitfall P7); how to
  detect it, what to do, and why this is durable across repos.

**Filesystem layout:**
```
~/.hermes/skills/workflow/apply-supplied-patch-and-open-pr/
├── SKILL.md                          (this file)
├── scripts/
│   └── apply_patch_and_open_pr.sh    (chmod +x required: `chmod +x scripts/apply_patch_and_open_pr.sh`)
└── references/
    └── upstream-prompt-format.md
```
