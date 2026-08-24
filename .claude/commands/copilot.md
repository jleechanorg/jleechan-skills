---
description: /copilot - Orchestrated PR Comment Processing
type: llm-orchestration
execution_mode: immediate
---

## EXECUTION INSTRUCTIONS FOR CLAUDE

**When /copilot is invoked, YOU (Claude) must execute ALL steps below directly.**

**Script policy:** Do not introduce new orchestration wrappers. Use `/extended-library:pair` in Step 5c when its trigger criteria are met.

**Usage:** `/copilot [PR_NUMBER]`

Note for Codex and non-Claude shells: slash commands are workflow shorthands. Execute the documented underlying Python/script implementations when slash command runners are unavailable.

---

### Step 1: Identify PR

```bash
# If PR_NUMBER not provided, auto-detect from current branch:
gh pr view --json number,title,url,headRefName --jq '{number, title, url, headRefName}'
```

Store the PR number for all subsequent steps.

### Step 2: Fetch All Comments

Run `/extended-library:commentfetch <PR_NUMBER>` to get all PR comments (inline, general, review, bot).

### Step 2b: Filter Previously Resolved Comments (Idempotency)

Read the PR description and check for an existing `<!-- COPILOT_TRACKING_START -->` table. If one exists:

1. Parse the tracking table rows to find comments with status **Fixed** or **Acknowledged**
2. Remove those comment IDs from the working set - they are already resolved and do not need re-processing
3. **Preserve their original tracking_reason** - store the reason text from the existing table row. Do NOT replace it with boilerplate like "Previously addressed in an earlier copilot run"
4. Log the count: `Skipping N previously resolved comments (M fixed, K acknowledged)`

Comments marked **Deferred**, **Unresolved**, or **Ignored** remain in the working set for re-evaluation - their status may change.

If no tracking table exists, this is a fresh run - process all comments.

**Step 2c: Display Comment Count (REV-iac0 + REV-g9fbp fix - MANDATORY)**

After filtering, you MUST display the total comment count upfront:

```
COMMENTS TO PROCESS: N total
  - CRITICAL: X (includes bot: X_bot)
  - BLOCKING: Y (includes bot: Y_bot)
  - IMPORTANT: Z (includes bot: Z_bot)
  - STYLE: W
```

**CRITICAL REQUIREMENT (REV-g9fbp):** Bot comments (CodeRabbit, Copilot, Cursor Bugbot, Codex) ARE counted and MUST be categorized by severity. Do NOT exclude bot comments from the count. Most actionable issues come from bot comments - they are NOT optional.

This count is MANDATORY and must be displayed before proceeding. This prevents shortcut bias by making the scope explicit.

### Step 3: Check CI Status

Run `/extended-library:gstatus` to check CI status, merge state, and identify failing checks.

### Step 4: Categorize Every Comment (REV-g9fbp + REV-3sc0t fix)

**What counts as a trackable comment:**
- Inline review comments (from `gh api pulls/<PR>/comments`)
- General PR comments with substantive content (from `gh pr view --json comments`)
- Review parent bodies ONLY if they contain unique actionable feedback not duplicated in child inline comments
- **Include bot comments**: CodeRabbit, Copilot, Cursor Bugbot, Codex - these are NOT excluded
- **Only exclude**: `[AI responder]` tagged comments (our own), empty review bodies, auto-generated meta-comments (e.g., CodeRabbit walkthrough summaries, coverage report bots) that contain no actionable request

**Bot Comment Classification (REV-3sc0t fix):**
When categorizing, identify if each comment is from a bot (author_association = "BOT") and mark it in your analysis. Bot comments are NOT optional - they must be categorized and addressed just like human comments.

Read each comment and assign a severity. **Bot credibility tier**: CI bots (test/lint failures) > static analysis (CodeRabbit) > AI reviewers (Copilot, Cursor Bugbot).

| Severity | Criteria | Action | DON'T fix if... |
|----------|----------|--------|-----------------|
| **CRITICAL** | Security vulns, production blockers, ImportErrors | **Must fix in code** | Never skip. If unfixable, explain why. |
| **BLOCKING** | Test failures, CI issues, logic bugs | **Must fix in code** | Comment is from low-tier AI reviewer AND contradicts CI evidence |
| **IMPORTANT** | Performance, architecture, code duplication | **Fix if meets scope check AND diff <= 5 lines, else defer** | Fix requires new files, new dependencies, or architectural changes |
| **STYLE** | Style, docs, naming, minor suggestions | **Fix max 5 quick wins. ACKNOWLEDGED for rest.** | Already at 5 STYLE fixes this run |

**Scope-creep examples to reject regardless of severity:**
- Comment suggests adding TypedDict/dataclass infrastructure -> DEFERRED (new pattern, not in PR scope)
- Comment requests new test file for edge case -> DEFERRED (new file creation)
- Comment asks to refactor unrelated module -> NOT_DONE (wrong scope)

### Step 4.5: Scope Guard Checkpoint (MANDATORY)

Before fixing anything, complete this checkpoint:

1. **State the PR goal in one sentence:** Write it out. (e.g., "Replace /copilot Python orchestration with pure LLM prompt")
2. **For each CRITICAL/BLOCKING comment**, confirm: Does this fix serve the PR goal, or does it introduce new infrastructure/patterns/files? If the latter, reclassify as DEFERRED with reason "Out of scope - [description]".
3. **Comment validity check:** Before implementing any fix, verify the comment is correct by reading the referenced code. If a bot comment contradicts the actual code behavior (e.g., flags a bug that doesn't exist), mark it NOT_DONE with reason "Comment incorrect - [evidence]". Do NOT blindly implement bot suggestions.
4. **STYLE budget:** Count fixable STYLE comments. If > 5, pick the 5 with smallest diff. ACKNOWLEDGED the rest.
5. **Log the scope line:**
```
SCOPE: "<PR goal sentence>"
IN-SCOPE FIXES: N CRITICAL, M BLOCKING, K IMPORTANT, J STYLE (capped at 5)
DEFERRED (out of scope): L comments
NOT_DONE (invalid): P comments
```

### Step 5: Fix Comments That Need Code Changes

**Step 5a: Decide /extended-library:pair vs inline fixing (MANDATORY LOG)**

Count the total in-scope CRITICAL + BLOCKING comments and log:
```
PAIR DECISION: X CRITICAL + Y BLOCKING = Z total
```

Enforcement rules:
- **Z >= 6**: You MUST use `/extended-library:pair` (Step 5b-5c). STOP — do not proceed to inline fixing.
- **Z <= 5**: Fix inline directly (skip to Step 5d).
- **Z >= 6 AND `/extended-library:pair` is unavailable**: Log `PAIR UNAVAILABLE: falling back to inline for Z comments`. Fix inline but add `[PAIR_FALLBACK]` tag to each response in responses.json so the tracking table shows these were not dual-verified.
- **If you skip /extended-library:pair when Z >= 6 without logging PAIR UNAVAILABLE, the run is invalid.**

**Step 5b: Collect CRITICAL/BLOCKING comments for /extended-library:pair** (only if 6+ comments)

Gather all CRITICAL and BLOCKING comments into a single task spec:

```markdown
Fix all CRITICAL and BLOCKING PR review comments for PR #<NUMBER>.

Branch: <branch_name>

## Comments to fix:

### [CRITICAL] <file>:<line> (from <reviewer>)
<comment body>

### [BLOCKING] <file>:<line> (from <reviewer>)
<comment body>

## Rules:
- Read each file before modifying
- Run tests after fixes: ./run_tests.sh <relevant_test_files>
- Commit each logical fix separately with message referencing the comment
- Do NOT defer - these are CRITICAL/BLOCKING and must be fixed
```

**Step 5c: Launch /extended-library:pair with the task spec**

Run `/extended-library:pair` with the task spec from Step 5b. `/extended-library:pair` routes to:

```bash
bash ralph/ralph-pair.sh run
```

This gives dual-agent coder+verifier: Claude implements, Codex verifies tests pass.

**Step 5d: Fix inline** (default path, or fallback if /extended-library:pair fails)

If 5 or fewer CRITICAL/BLOCKING comments, or `/extended-library:pair` errors out, times out, or is unavailable:
1. Read the file referenced in the comment
2. Understand the issue
3. Implement the fix using Edit/MultiEdit tools
4. If the fix is complex or risky, note it as deferred with a reason

**Step 5e: Handle IMPORTANT and STYLE comments (always inline)**

**"Straightforward" means ALL of these are true:**
1. The fix modifies only files already changed in this PR
2. The net diff is <= 5 lines changed
3. No new imports, files, classes, or dependencies are introduced
4. The fix does not change public API signatures or function contracts

If ANY condition fails, the fix is NOT straightforward. Defer it with reason citing which condition failed.

For IMPORTANT comments: fix if straightforward (all 4 conditions above), otherwise DEFERRED.
For STYLE comments: fix up to 5 quick wins (straightforward per above). ACKNOWLEDGED for the rest. Do NOT fix all STYLE comments — cap at 5 per run.

**ACKNOWLEDGED vs NOT_DONE:**
- ACKNOWLEDGED = comment is valid feedback, but intentionally not fixing (style preference, out of scope, low priority)
- NOT_DONE = comment is factually wrong, already handled, or based on misunderstanding. Include evidence.

These do NOT go through `/extended-library:pair` - fix them directly.

**Step 5f: Post summary after /extended-library:pair completes (CRITICAL - REV-j6i3d fix)**

After `/extended-library:pair` completes (success OR failure), you MUST still post a summary comment:

1. Check session directory for responses.json:
   - `/tmp/<repo>/<branch>/pair-<session_id>/responses.json`
   - Or `/tmp/copilot/pair-<session_id>/responses.json`

2. If responses.json exists:
   - Proceed to Step 6 and Step 7 to post summary
   - Include verification status badge:
     - **VERIFIED**: All fixes verified by verifier agent
     - **PARTIAL**: Some fixes applied, verification incomplete
     - **UNVERIFIED**: Fixes applied but verification timed out

3. If responses.json does NOT exist:
   - `/extended-library:pair` failed to generate responses - handle as failure

**This step is MANDATORY regardless of `/extended-library:pair` outcome.** The PR must always have a summary comment posted.

### Step 6: Generate ACTION_ACCOUNTABILITY responses.json

Before posting any reply, create `/tmp/<repo>/<branch>/copilot/responses.json`. This file is the **single source of truth** - both the consolidated reply (Step 7) and the tracking table (Step 10) MUST derive their metrics from this file.

**Include ALL comments** - both newly processed AND carried-forward from prior runs:

Per-comment entry fields:
- `comment_id` (string or integer)
- `reply_text` (required)
- `category` (`CRITICAL` | `BLOCKING` | `IMPORTANT` | `STYLE`)
- `response` (`FIXED` | `ALREADY_IMPLEMENTED` | `DEFERRED` | `ACKNOWLEDGED` | `NOT_DONE`)
- `tracking_reason` (MUST be 2-3 sentences — see quality gate below)
- `carried_forward` (boolean - true if this entry was resolved in a prior run)
- `evidence` (required for FIXED: commit hash or test result. Empty string for non-FIXED responses.)

**tracking_reason quality gate (REV-kvze4):** Each reason must name the specific action and outcome. Self-check before writing responses.json — reject any reason that matches these BAD patterns:

| BAD (reject) | GOOD (accept) |
|---------------|---------------|
| "Previously addressed in an earlier copilot run" | "Fixed missing `[AI responder]` prefix in consolidated reply template. Commit a1b2c3d." |
| "Acknowledged this feedback" | "Comment requests TypedDict infrastructure. Deferred — requires new file and is outside PR scope of replacing Python orchestration." |
| "This was already handled" | "Bot flagged step cross-reference error (5c vs 5d). Fixed jump target in Step 5a decision table to point to 5d for inline path." |

**File-level metadata** (top of responses.json):
- `files_modified`: list of files changed this run. If N (number of fix commits) > 0, compute with `git diff --name-only HEAD~N..HEAD`; if N = 0, set `files_modified` to `[]` (do not run `HEAD~0`).
- `total_comments`: count of all trackable comments
- `new_this_run`: count processed this run (excluding carried-forward)
- `carried_forward`: count preserved from prior runs

If code changes are made, use this commit message format (the `[copilot]` prefix is MANDATORY for all copilot-generated commits):

```text
[copilot] fix: <short description of what was fixed>

Comment: https://github.com/<owner>/<repo>/pull/<pr>#discussion_r<comment_id>
```

The `[copilot]` prefix identifies commits made by the /copilot workflow in `git log` and remote history. Never omit it.

If code changes were made, create the local commit(s) before Step 7 so consolidated replies can reference real commit hashes.

### Step 7: Post Consolidated Reply (Direct - No External Scripts)

**Do NOT use `/extended-library:commentreply` or `commentreply.py`.** You (the LLM) build and post the reply directly.

**Procedure:**
1. Read `/tmp/<repo>/<branch>/copilot/responses.json` (created in Step 6)
2. Tally all metrics by counting entries in the file:
   - `total` = number of entries
   - `fixed` = entries where response is FIXED or ALREADY_IMPLEMENTED
   - `deferred` = entries where response is DEFERRED
   - `acknowledged` = entries where response is ACKNOWLEDGED
   - `not_done` = entries where response is NOT_DONE
   - `new_this_run` = entries where carried_forward is false
   - `carried_forward` = entries where carried_forward is true
   - `files_modified` = from the file-level metadata
3. Build the consolidated comment using the template below
4. Write it to a temp file and post:

```bash
REPLY_FILE=$(mktemp)
# Write the consolidated comment markdown to $REPLY_FILE
gh pr comment <PR_NUMBER> --body-file "$REPLY_FILE"
rm -f "$REPLY_FILE"
```

**Template (all values from responses.json tallies):**

```markdown
[AI responder]
## Copilot Response - All Comments Addressed

**Coverage:** X/Y comments addressed (Z fixed, W deferred, V acknowledged, U not done)
**This run:** A new, B carried forward from prior runs
**Files modified:** file1.py, file2.md (or "None" if no code changes)
**CI status:** [Re-check with `gh pr checks <PR>` immediately before posting]

### CRITICAL/BLOCKING Fixes
- **[file:line]** - Issue summary -> Fixed in commit abc123 / Deferred: reason

### IMPORTANT
- **[file:line]** - Issue summary -> Fixed / Deferred: reason

### STYLE / NON-ACTIONABLE (REV-iac0 fix - renamed from ROUTINE)
- Acknowledged: brief summary of routine items addressed
```

**Self-check before posting (MANDATORY - all 4 checks must pass):**
1. **Coverage arithmetic**: Z + W + V + U MUST equal X (total addressed). Each response type (fixed/deferred/acknowledged/not_done) appears EXACTLY ONCE. If a category appears twice, you have a bug — fix it.
2. **No test claims without evidence**: If you claim tests pass, you MUST link a CI run URL (`gh pr checks <PR> --web`) or evidence bundle path. Never assert "N tests pass" without a linked artifact.
3. **Fresh CI status**: Run `gh pr checks <PR_NUMBER>` immediately before posting to get current CI state. Do NOT reuse stale CI data from Step 2.
4. **Total matches responses.json**: Count entries in responses.json and verify it matches X/Y.

### Step 7.5: Resolve Conversation Threads (MANDATORY for FIXED/DEFERRED)

After posting the consolidated reply, resolve the conversation threads for comments that were fixed or deferred. This keeps the PR clean and shows progress.

Because GitHub's REST API does not support resolving PR review threads, you MUST use the GraphQL API to perform the resolution. However, `responses.json` tracks comments by their numeric database `comment_id`, whereas the `resolveReviewThread` mutation requires the global GraphQL node ID (`PullRequestReviewThread.id`).

**Procedure to map and resolve conversation threads:**

1. Read the list of `comment_id` values from `/tmp/<repo>/<branch>/copilot/responses.json` where `response` is `FIXED` or `ALREADY_IMPLEMENTED`.
2. For each numeric `comment_id`, retrieve the global GraphQL `PullRequestReviewThread.id` by querying `PullRequestReviewComment` with `fullDatabaseId` matching that numeric identifier.
   Use the following mapping query:
   ```bash
   gh api graphql -f query='
     query($owner: String!, $repo: String!, $pullNumber: Int!) {
       repository(owner: $owner, name: $repo) {
         pullRequest(number: $pullNumber) {
           reviewComments(first: 100) {
             nodes {
               fullDatabaseId
               pullRequestReviewThread {
                 id
                 isResolved
               }
             }
           }
         }
       }
     }
   ' -f owner="{owner}" -f repo="{repo}" -F pullNumber={pull_number}
   ```
3. Match each `responses.json comment_id` to the `fullDatabaseId` in the query response, and extract its corresponding `PullRequestReviewThread.id`.
4. Call the `resolveReviewThread` mutation with that resolved `thread.id`:
   ```bash
   gh api graphql -f query='
     mutation($threadId: ID!) {
       resolveReviewThread(input: { threadId: $threadId }) {
         thread {
           id
           isResolved
         }
       }
     }
   ' -f threadId="<thread_id>"
   ```
5. Log the count: `Resolved N conversation threads (X fixed, Y deferred)`

**Why this matters:** Correctly translating `PullRequestReviewComment.fullDatabaseId` to `PullRequestReviewThread.id` allows us to reliably target and resolve the exact conversation threads on GitHub without encountering non-existent REST endpoints or dead commands.

### Step 8: Verify Coverage (REV-g9fbp fix - severity-based)

Run `/extended-library:commentcheck` with severity-based coverage requirements:

| Severity | Required Coverage | Notes |
|----------|------------------|-------|
| CRITICAL | 100% | Must fix all |
| BLOCKING | 100% | Must fix all |
| IMPORTANT | 90% | Fix most, some can defer |
| STYLE | 0% (optional) | Acknowledge only |

**This is a HARD STOP** - do not proceed if CRITICAL/BLOCKING coverage is less than 100%.

### Step 8.5: Post-Summary Delta Recheck (MANDATORY)

Immediately after Step 8, fetch comments again and compare against the comment IDs in `responses.json`.

Hard requirements:
- If new actionable comments arrived after the Step 7 summary timestamp, the run is **not complete**.
- Re-enter processing for the new comments (back to Step 4), regenerate `responses.json`, and post a refreshed consolidated summary.
- Only proceed to Step 9 when there are **zero new actionable comments** since the most recent summary.

This check prevents stale "all addressed" summaries when reviewers/bots post new findings during the run.

### Step 9: Push Changes

If any code changes were made, run `/extended-library:pushl` to push. (Commits were created in Step 6 before the consolidated reply was posted in Step 7)

### Step 9.5: Verify Run Quality (Blocking Gate)

Launch the `copilot-verifier` subagent to independently audit this run's quality. Use **sonnet** model for full verification (includes judgment checks on tracking_reason quality and status truthfulness). Use **haiku** if only mechanical checks (1, 2, 5, 6, 7) are needed and you want lower cost.

```
Task({
  subagent_type: "copilot-verifier",
  model: "sonnet",
  description: "Verify copilot run quality",
  prompt: "Verify /copilot run for PR #<NUMBER> on branch <BRANCH>.
    responses.json: /tmp/<repo>/<branch>/copilot/responses.json
    PR goal: <PR goal sentence from Step 4.5>
    Fix commits this run: N
    Run all 7 checks and write verification_report.json."
})
```

**Gate enforcement:**
- **PASS**: Proceed to Step 10 normally.
- **PARTIAL**: Proceed to Step 10 but include a `<!-- VERIFICATION: PARTIAL -->` badge and list the failed checks in the tracking table header.
- **FAIL**: **STOP.** Do not update the tracking table. Log the verification failures. The copilot run must fix the integrity violations (closure, truthfulness, or pair compliance) before the tracking table can be published.

If the verifier agent is unavailable (file not found, timeout), log `VERIFIER UNAVAILABLE` and proceed to Step 10 with a `<!-- VERIFICATION: SKIPPED -->` badge. Do not block on infrastructure issues.

### Step 10: Update PR Description with Tracking Table

Append or update a tracking table in the PR description. Use temp file to avoid shell injection:

```bash
# Save current PR body to temp file
TMPFILE=$(mktemp)
gh pr view <PR_NUMBER> --json body --jq '.body' > "$TMPFILE"

# Edit $TMPFILE to add/update tracking table between markers while preserving all other content:
# <!-- COPILOT_TRACKING_START --> ... <!-- COPILOT_TRACKING_END -->

# Update PR using --body-file (avoids shell injection)
gh pr edit <PR_NUMBER> --body-file "$TMPFILE"
rm -f "$TMPFILE"
```

**Rules for the tracking table:**
- If `<!-- COPILOT_TRACKING_START -->` markers already exist, replace only that section
- **Preserve previously resolved rows**: Merge new results with existing table entries. Comments already marked **Fixed** or **Acknowledged** from prior runs keep their status and reason - do not overwrite them
- Comments re-evaluated this run (previously Deferred/Unresolved/Ignored) get their status updated
- Every comment from every reviewer must appear in the table (current run + prior runs combined)
- Include a 2-3 sentence `tracking_reason` in the Summary column (quality per REV-kvze4)

**Truthful status rules (REV-za1lr):** Status must reflect reality, not intent.

| Status | Meaning | Required evidence |
|--------|---------|-------------------|
| **Fixed** | Code change committed that addresses the comment | Commit hash in tracking_reason |
| **Deferred** | Valid comment, not fixing this run | Specific reason (scope, complexity, which straightforward condition failed) |
| **Acknowledged** | Valid feedback, no code change needed | Why no change is needed |
| **Not Done** | Comment is invalid or already handled | Evidence (code snippet, test result) |
| **Unresolved** | Could not determine how to address | What was attempted |

**Do NOT mark "Fixed" unless a commit exists.** If you made a code change but haven't committed yet, status is "Unresolved" until the commit lands. If you only added a comment/explanation, status is "Acknowledged", not "Fixed".

---

## Key Rules

1. **Severity-based coverage mandate**:
   - CRITICAL/BLOCKING: 100% required (must fix all in-scope comments)
   - IMPORTANT: 90% required (most must be fixed or deferred with specific reason)
   - STYLE: max 5 fixes per run, rest ACKNOWLEDGED
   - Only exception: `[AI responder]` tagged comments (our own)
2. **No skipping bot comments** - Bot comments at CRITICAL/BLOCKING must be addressed. But verify correctness first (Step 4.5.3).
3. **Fix within scope** - Fixes must serve the PR's stated goal (Step 4.5.1). New infrastructure, new files, new patterns = DEFERRED, not fixed. This replaces "fix over defer".
4. **Honest tracking** - Every tracking_reason must be a unique 2-3 sentence description. NEVER use boilerplate. Preserve original reasons from prior runs.
5. **Single consolidated comment** - Post ONE summary comment, not individual replies
6. **Idempotent re-runs** - Skip previously Fixed/Acknowledged comments, re-evaluate Deferred/Unresolved/Ignored
7. **Single source of truth** - Both the consolidated reply and tracking table derive from `responses.json`. Mismatch = stop and reconcile.

## Effectiveness KPIs (REV-962a7 — closure over volume)

After completing all steps, log these metrics. **Closure rate is the primary KPI, not comment count.**

```
COPILOT RUN COMPLETE:
  Closure rate:       X/Y CRITICAL+BLOCKING fixed with commits (target: 100%)
  Scope discipline:   A/B fixes were in-scope (target: 100%)
  STYLE budget:       C/5 STYLE quick wins used
  Boilerplate check:  D tracking_reasons failed quality gate (target: 0)
  Pair compliance:    [USED / SKIPPED (<=5) / FALLBACK / VIOLATED]
```

**A run is successful when:**
- Closure rate = 100% for CRITICAL/BLOCKING (every one has a commit hash)
- Scope discipline = 100% (no new files, no new patterns created)
- Boilerplate check = 0 (every tracking_reason passes the quality gate from Step 6)
- Pair compliance is not VIOLATED

**A run is NOT successful just because:** comments were fetched, a summary was posted, or coverage percentage is high. ACKNOWLEDGED comments do not count toward closure.
