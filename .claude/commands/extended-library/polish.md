---
description: /polish - Iterative PR Green Loop (up to N iterations)
type: llm-orchestration
execution_mode: immediate
---

## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE

**When this command is invoked, YOU (Claude) must execute these steps immediately.**
**This is NOT documentation - these are COMMANDS to execute right now.**
**Use TodoWrite to track progress through multi-phase workflows.**

**Usage:** `/polish [N] [PR_NUMBER]`
- `N` = max iterations (default: 5)
- `PR_NUMBER` = target PR (default: auto-detect from current branch)

**Goal:** Keep the PR draft through `/es`, `/er`, and `/advice`, then drive the
ready PR through the canonical two-gate `/green`, looping up to N times.

**CRITICAL — DO NOT MERGE:** This command evaluates and fixes PR readiness. It NEVER executes merge commands (`gh pr merge`, `gh api .../merge`). Merging requires explicit human "MERGE APPROVED" in the conversation. Reporting draft-readiness + `/green` is the terminal state — not merging.

---

### Stop conditions

1. While draft, `/es`, `/er`, and `/advice` pass at the current head per
   `~/.claude/skills/draft-first-pr/SKILL.md`.
2. After marking ready, `/green` passes at the current head per
   `~/.claude/skills/pr-green-definition/SKILL.md`.
3. CodeRabbit and Bugbot feedback has been triaged as advisory; neither is a
   required verdict.

---

### Loop Algorithm

```text
# Derive repo context once before the loop
REPO_FULL="$(gh repo view --json nameWithOwner --jq '.nameWithOwner')"
OWNER="${REPO_FULL%%/*}"
NAME="${REPO_FULL##*/}"
PR="<PR_NUMBER>"

for iteration in 1..N:
  1. Run /copilot <PR_NUMBER>   # fetch + triage all comments, fix blocking issues
  2. Run /fixpr <PR_NUMBER>     # fix any remaining inline PR blockers
  3. Run /er                    # check evidence bundle (skip if none present)
  4. If changes made → commit + push with /pushl
  5. Wait for CI to settle (gh run watch or poll statusCheckRollup)
  6. Evaluate the canonical draft-readiness and `/green` conditions:
     # Fetch CI status and mergeability
     gh pr view <PR_NUMBER> --json statusCheckRollup,mergeable,mergeStateStatus
     # Use GraphQL to get bot-specific reviews and thread resolution.
     # Paginate reviewThreads: real PRs can exceed 100 threads (see automation/jleechanorg_pr_automation).
     # reviewThreads uses cursor-based pagination: on first call omit cursor entirely (pass no cursor param — not even empty string);
     # read pageInfo { hasNextPage endCursor }; if hasNextPage is true, re-run with -f cursor=<endCursor>,
     # accumulating all nodes until hasNextPage is false. Do NOT pass cursor="" — GitHub GraphQL rejects empty string cursors.
     # If any thread may have >20 comments, page through that thread's comments connection using its pageInfo until all comments are collected.
     # Note: the reviews connection uses last:100 ordered chronologically by submittedAt — sufficient for most PRs; if CR has >100 reviews, accumulate in reverse order. Add pageInfo to all paginated connections for cursor-based navigation.
     gh api graphql \
       -f query='
         query($owner:String!, $name:String!, $pr:Int!, $cursor:String) {
           repository(owner:$owner, name:$name) {
             pullRequest(number:$pr) {
               reviews(last:100) {
                 pageInfo { hasNextPage endCursor }
                 nodes { author { login } state bodyText submittedAt }
               }
               reviewThreads(first:100, after:$cursor) {
                 pageInfo { hasNextPage endCursor }
                 nodes {
                   isResolved
                   comments(last:20) {
                     pageInfo { hasNextPage endCursor }
                     nodes { author { login } body }
                   }
                 }
               }
             }
           }
         }
       ' \
       -f owner="$OWNER" -f name="$NAME" -F pr="$PR"
     - Check CI: statusCheckRollup evaluates to 0 via canonical jq filter ([.statusCheckRollup[] | select((.__typename == "StatusContext" and (((.state // "") | ascii_upcase) != "SUCCESS")) or (.__typename == "CheckRun" and .name != "Green Gate" and .name != "Cursor Bugbot" and ((((.status // "") | ascii_upcase) != "COMPLETED") or (((.conclusion // "") | ascii_upcase) != "SUCCESS"))))] | length)
     - Check mergeable: MERGEABLE (handle UNKNOWN state by polling)
     - Surface CodeRabbit/Bugbot comments for triage, but do not require their verdicts.
     - Check draft readiness: `/es`, `/er`, and `/advice` PASS at this head.
  7. If draft readiness and both `/green` gates pass → STOP, report success
  8. Continue to next iteration
```

**Note on CI evaluation timing**: Each iteration pushes (step 4) then waits for CI to settle (step 5), so fixes land before the next iteration's evaluation. With N=1 and fixes needed, CI must complete and re-run before the loop can report green.

---

### Step 1: Identify PR and Parse Args

Use TodoWrite to track progress through each iteration.

```bash
# Parse N (first numeric arg) and PR_NUMBER (second arg or auto-detect)
gh pr view --json number,title,url,headRefName --jq '{number, title, url, headRefName}'
```

---

### Step 2: Execute Loop

Run the loop algorithm above up to N times (default 5).

Apply intelligence: if /copilot finds no blocking issues and CI is already green, skip to evaluation immediately rather than making unnecessary changes.

**IMPORTANT — Uncommitted changes guard**: Before evaluating green conditions (Step 6), verify there are no uncommitted changes with `git status --porcelain` (covers staged, unstaged, AND untracked files). If any output exists, do NOT report the PR as green — commit first with `/pushl` before Step 7 evaluation.

---

### Step 3: After Loop Completes

Report final status:
- Which conditions are green
- Which conditions are still red (with specific blockers)
- What was fixed across iterations
- Whether PR is ready to merge

Print a final status table with draft readiness and /green conditions and their current state.
