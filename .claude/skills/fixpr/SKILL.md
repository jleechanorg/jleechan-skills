---
name: fixpr
description: Analyze and fix PR blockers (CI failures, merge conflicts, bot/review feedback) to get a PR into a mergeable state — never merges it. Fresh GitHub receipts and applicable validation establish status; follow the canonical /green owner. Slash command /fixpr. Also embodied as the copilot-fixpr subagent type for parallel/automated PR-fixing dispatch. Use when a PR has failing CI, merge conflicts, or unresolved bot comments and needs to be driven to green.
---

# /fixpr — PR Fix Analysis (focused validation, GitHub-authoritative)

**Purpose**: fix authorized PR blockers and verify applicable checks and conflicts — never merge. Read the repository policy and `~/.claude/skills/pr-green-definition/SKILL.md` for /green; review applicability and merge authorization remain separate.

## The three commandments

1. **Focused validation**: use the smallest relevant tests for the actual failure and fix; CI owns full regression. Respect repository bans on unfiltered local suites. If the user prohibits local tests, use authorized cloud/CI execution; never make a local run a prerequisite.
2. **Fresh remote state and scoped proof**: GitHub is authoritative for PR head, remote checks and mergeability. Fetch and display fresh status before analysis and after every fix. `mergeable == "MERGEABLE"` establishes no conflicts, not passing CI; inspect applicable check conclusions. Qualifying local proof for backlogged CI may satisfy /green under its canonical owner and user/repository constraints. Report the evidence source and SHA; `mergeStateStatus` is informational.
3. **Never merge**: success means the merge button would be green, not that you clicked it.

## 2026-07 fleet-drive lessons (read before touching a multi-PR backlog)

These came out of driving a real 40+ PR backlog and matter as much as the mechanics below:

- **CodeRabbit is optional advisory review, not a merge gate.** CodeRabbit feedback is optional/advisory — read its feedback and triage actionable suggestions during the draft workflow, but its verdict (including `CHANGES_REQUESTED`), approval, silence, and review state are not `/green` or merge eligibility gates.
- **Check for active external automation before touching a PR.** A meaningful share of any backlog is already under active bot iteration (this exact `/fixpr` methodology running as the `copilot-fixpr` subagent, or codex automation) at any given moment — that work is partly self-resolving. Touching a PR that's mid-automation just races it; check recent commit/comment cadence first.
- **Evidence/review staleness compounds fast — re-derive, don't trust cached citations.** The dominant risk in a PR-fixing pass is stale artifacts, not incorrect code. Every real bug found in recent sessions came from re-deriving evidence at the PR's actual current head SHA rather than trusting an existing citation or a previous run's output.
- **"70+ open PRs" overstates actionability.** Typically only a minority are genuinely ready for a human merge call at any moment; most are either awaiting review/CI or under active automation. Triage before batch-driving.

## Workflow

### Step 0: Verify GitHub CLI auth (mandatory pre-flight)

Run `gh auth status` and a cheap read-only API probe. An error is not a reason
to ask the user to log in immediately. Inspect existing host auth without printing
tokens. If `GITHUB_TOKEN` is stale, retry only the command with
`env -u GITHUB_TOKEN gh auth status` and the same API probe, using saved host
auth; do not edit credentials or persistent configuration.

Before reporting blocked, follow
`~/.claude/skills/github-cli-reference/SKILL.md`: inspect auth/quota errors,
try bounded REST and GraphQL reads for the same target, and use unauthenticated
REST for public data if authenticated quota is exhausted. Cite the attempted
commands and errors. Escalate only a verified missing capability after existing
auth paths are exhausted; never create credentials or recommend login from one
status failure.

### Step 1: Gather repository context

Extract repo owner/name from git remote (handle both HTTPS and SSH URL forms), determine the default branch without assuming `main` (could be `master`/`develop`). Quote all bash variables.

### Step 2: Fetch fresh GitHub PR status (authoritative — never trust cache or local state)

```bash
gh pr view "$PR" --json state,headRefOid,baseRefName,headRefName,url,mergeStateStatus,statusCheckRollup,mergeable,reviews,comments
gh pr view "$PR" --json statusCheckRollup --jq '.statusCheckRollup[] | {name: (.name // .context), status, conclusion, state, url: (.detailsUrl // .targetUrl)}'
```

Check open/merged/closed state first; a closed PR is not a failing mergeability
probe. Bind findings to the returned head SHA, check/run URL and command output.
Re-read the head before each verification round and after a push. Inspect the
workflow and required-check configuration to establish which jobs apply.

| Observed check | Report |
|---|---|
| Required, applicable failure/error/timeout/cancellation | Failure with exact log and current-head receipt |
| Required, applicable queued/in-progress/pending | Pending, not failed; follow the owning /green backlog procedure within user/repo test limits |
| Intentionally skipped conditional job | Skipped with the workflow reason; not a failure or a passed test |
| Required check skipped, neutral, absent or applicability unknown | Unproven; inspect its condition and requirement before a gate verdict |
| Optional/advisory check | Report separately; CodeRabbit/Bugbot do not gate /green |
| Completed success | Passed at the recorded SHA, within that check's scope |

Never use `status != SUCCESS` or `conclusion != SUCCESS` as a blanket failure
classifier. `statusCheckRollup` mixes StatusContext `state` with CheckRun
`status/conclusion`. Preserve the raw fields; unknown schemas are unverified,
not invented failures. Follow the canonical /green owner for the final gate
decision; a nonempty status list does not itself prove a blocker.

Fetch and display current mergeability and review feedback too.
`mergeable == MERGEABLE` establishes no conflicts, not successful CI or merge
authorization. `mergeStateStatus` is informational. Use the fetched base/head
and local merge inspection to identify actual conflict content; a PR diff alone
does not contain conflict markers. Iterate review/comment lists rather than
treating them as dictionaries. Human review restrictions remain separate;
CodeRabbit/Bugbot verdicts, silence and approvals are advisory.

### Step 3: Detect CI-vs-local discrepancies

Inspect the exact failing workflow command and logs first. Reproduce with the
smallest relevant test/filter in an authorized environment. Prefer cloud/CI when
the user prohibits local tests. A current CI failure can supply RED evidence;
do not require a duplicate local failure before fixing an already-established
cause. Record where RED and GREEN actually ran.

For a genuine mismatch between environments, use `/redgreen` (alias `/tdd`)
within those constraints: isolate the failing assertion/environment, fix the
cause, and verify the focused case. Compare dependency versions, configuration,
timezone/locale and filesystem behavior before guessing. If reproduction is
blocked, continue read-only diagnosis and disclose the missing proof; do not
invent a pass. Full regression remains in CI, never an unfiltered local default.

### Step 4: Apply fixes

Already-authorized CI fixes proceed without another confirmation. Keep small test-only fixes proportional; honor a request for manual testing or no long reviews, while recording what remains untested. Do not add a review campaign or local suite as an invented prerequisite.

Focus on the immediate blockers in this PR. Common categories: environment issues (deps, env vars, timeouts), code issues (imports, assertions, types), test issues (expectations, races, edge cases).

**Pattern detection** (optional `--scope=pattern`): after fixing the immediate blocker, scan the codebase for the same pattern elsewhere (e.g. a Firestore-mocking mismatch that recurs across several test files) and fix all instances — prevents the same class of failure recurring in the next PR.

### Step 5: Merge conflicts (if present)

```bash
git fetch origin
# Inspect current branch/upstream, working tree, fetched base and PR head first.
# Reconcile active writers; preserve unrelated edits. Select an explicit merge
# or repository-approved rebase only after inspecting the exact target refs.
# resolve conflicts
PR_NUMBER="<pr-number>"
BRANCH_NAME=$(git rev-parse --abbrev-ref HEAD)
DOCS_DIR="docs/conflicts/$(echo "$BRANCH_NAME" | tr '/' '-')-pr${PR_NUMBER}"
mkdir -p "$DOCS_DIR"
# document EACH conflict resolution in $DOCS_DIR/conflict_summary.md, then:
# run focused affected checks in the authorized environment, then commit
```

**Every conflict resolution must document**: file, conflict type, original markers, resolution, WHY, risk level (Low/Medium/High). Preservation priority: never lose functionality (combine features when possible), prefer bug fixes over new features on conflict, maintain backward compatibility, keep security improvements from both branches.

Example `conflict_summary.md` entry:
```markdown
### File: `src/auth.py`
**Conflict Type**: Authentication logic
**Risk Level**: High
**Original Conflict**:
\```python
<<<<<<< HEAD
def login(user, password):
    return basic_auth(user, password)
=======
def login(user, password, mfa=None):
    if mfa:
        return mfa_auth(user, password, mfa)
    return basic_auth(user, password)
>>>>>>> main
\```
**Resolution**: **Combined** — retained authentication and main's MFA support
- Before: `<focused command>` → <observed result/environment>
- After: `<focused command>` → <observed result/environment>
**Reasoning**: Main branch added MFA (security improvement), backward compatible (mfa is optional), no conflicting business logic on our branch.
```

Follow `~/.claude/skills/resolving-merge-conflicts/SKILL.md`. Before push, run
its owning script with the explicit reviewed base and documentation directory:

```bash
~/.claude/skills/resolving-merge-conflicts/scripts/check_resolution_doc.sh "$BASE_REF" docs/conflicts
```

Each conflicted file must have a heading containing its path in backticks,
a `Kept both`, `Combined` or `Dropped side` label, and `- Before:` /
`- After:` test lines. The script checks merge commits in BASE..HEAD; for a
rebase also compare the documented files with the original conflict list.
Preserve both sides where compatible; record every dropped behavior and reason.

### Step 6: Pre-push checklist (mandatory — do not push if any item unchecked)

```
[ ] Exact current-head failure/log inspected; focused RED/GREEN recorded in the authorized environment
[ ] Smallest relevant checks pass, or explicitly documented user-directed validation limits apply; full regression remains in CI
[ ] If conflicts existed: explicit base inspected, resolution documented, affected checks run where permitted, owning documentation script passes
[ ] Only intended files staged; staged diff inspected; unrelated work preserved and writer ownership reconciled
[ ] Current branch, upstream and explicit push target printed and verified against the PR head branch
```

### Step 7: Push and re-verify GitHub (never claim success from local state alone)

Stage named paths only; never stage the whole worktree. Before committing, inspect
the staged diff and confirm it contains only this fix. Include the creating CLI
and model in the commit message per the active repository contract.

```bash
git status --short
git add -- "$FIX_PATH" "$TEST_PATH" # include the named conflict doc when applicable
git diff --cached --check
git diff --cached --stat
git diff --cached
git commit -m "$COMMIT_MESSAGE"

current_branch=$(git branch --show-current)
upstream=$(git rev-parse --abbrev-ref --symbolic-full-name '@{upstream}')
printf 'branch=%s upstream=%s target=%s/%s\n' "$current_branch" "$upstream" "$PUSH_REMOTE" "$PR_HEAD_BRANCH"
test -n "$current_branch" || exit 1
test "$upstream" = "$PUSH_REMOTE/$PR_HEAD_BRANCH" || exit 1
git push "$PUSH_REMOTE" "$current_branch:refs/heads/$PR_HEAD_BRANCH"
gh pr view "$PR" --json headRefOid,url,statusCheckRollup,mergeable,mergeStateStatus
```

Resolve `PUSH_REMOTE` and `PR_HEAD_BRANCH` from the actual PR and remote
configuration, not guesswork. If tracking is missing, verify the target before
setting it. A differently named local branch is valid when its upstream and the
explicit local-to-remote mapping match the intended PR branch. Fetch that remote,
re-read the PR head, and verify its ancestry and writer ownership before pushing.
A mismatch requires ownership/target reconciliation, not a force-push.
Record the pushed commit URL and re-fetch current-head checks; an accepted push
does not establish green. Use asynchronous CI monitoring rather than a fixed
sleep; never merge.

## Auto-apply mode (`--auto-apply`)

This flag is not required to perform already-authorized fixes. Optional automatic expansion is scoped to safe fixes only: import corrections, whitespace/formatting, doc updates, bot-suggested non-logic-changing improvements. Always preserve existing functionality, business logic, and security patterns from both branches. Apply one category at a time, test after each, stop on unexpected failure.

## Risk classification for conflict/fix decisions

- **Low**: docs, comments, formatting, test additions.
- **Medium**: UI changes, non-critical features, config updates.
- **High**: auth, data handling, payment processing, API contract changes.

## Complex/parallel mode — 4 specialist agent roles

For PRs with >10 distinct issues or extensive CI failures, spawn specialists instead of one linear pass (Claude/the orchestrator retains overall workflow control):
1. **CI-Analysis-Agent** — GitHub CI failure analysis and fix recommendations.
2. **Conflict-Resolution-Agent** — merge conflict analysis and safe resolution.
3. **Bot-Feedback-Agent** — processes automated bot comments, implements applicable suggestions.
4. **Verification-Agent** — validates fix effectiveness, re-checks mergeability.

This is also the shape the `copilot-fixpr` subagent type embodies for automated/parallel dispatch across a PR fleet.

## Examples

```bash
/fixpr 1234                                # analyze + fix, default scope
/fixpr 1234 --auto-apply                   # auto-apply safe fixes only
/fixpr 1234 --scope=pattern                # fix + scan codebase for the same pattern elsewhere
/fixpr 1234 --scope=comprehensive --auto-apply

# CI-vs-local discrepancy (auto-triggers /redgreen):
# Local: all tests pass. GitHub: test-unit FAILING.
/fixpr 1234
# -> detects discrepancy, issues:
/redgreen --pr 1234 --check "test-unit" --gh-log "AssertionError: Expected 'foo' but got 'FOO'"
# -> reproduces in the authorized environment, fixes, runs focused checks + CI
```

## Integration points

- `/copilot` — comprehensive PR workflow orchestration (fixpr is one phase of it).
- `/commentreply` — respond to review feedback after fixing.
- `/pushl` — push fixes to remote.
- `/redgreen` (alias `/tdd`) — auto-triggered for CI-vs-local discrepancies.
- Project validation — smallest relevant checks in the authorized environment; CI runs full regression.

## Error recovery

Gracefully handle missing tools by trying alternatives; explain clearly what failed and why; suggest manual steps when automation isn't possible; preserve partial progress rather than failing completely.
