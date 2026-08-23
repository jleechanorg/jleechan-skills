# GitHub API Reduction Design Notes

## Problem Statement

The `/copilot` slash command workflow makes multiple GitHub API calls per run. As of this change, the workflow has been audited to remove unnecessary API calls, with a focus on preventing use of automatic conversation-thread resolution APIs.

---

## Change: Remove Post-Summary Delta Recheck (Step 8.5)

**Before**: After posting the consolidated reply (Step 7), the workflow would re-fetch all comments and re-enter the processing loop if any new actionable comments arrived.

**After**: The workflow ends after Step 9 (push changes) and Step 10 (update PR description). No re-fetch occurs.

**Why**: The recheck loop was adding ≈4–5 extra API calls per run (4 comment re-fetches plus an optional `gh pr comment`) and creating unbounded iteration risk. Comments that arrive **after** the Step 7 consolidated reply are not seen in the same pass; the next `/copilot` run picks them up (idempotent). If merge or review policy requires zero gaps, re-run `/copilot` (or an outer `/fixprc` / `/copilotc` loop) before merging.

---

## Additional API Reduction Strategies

The following strategies are compatible with upstream GitHub API behavior and can reduce API call volume further without changing core workflow semantics.

### 1. GraphQL Default, REST Fallback

- **Default**: Use `gh api graphql` for batched queries (e.g., fetching PR + comments + checks in one round-trip).
- **Fallback**: When GraphQL returns a rate-limit error, switch to REST for individual endpoints.
- **Why**: GraphQL lets us fetch all needed fields in one call, reducing N+1 patterns.

```bash
# GraphQL: one call for PR metadata + comment count + review state
gh api graphql -f query='
  query($owner: String!, $repo: String!, $pr: Int!) {
    repository(owner: $owner, name: $repo) {
      pullRequest(number: $pr) {
        title, state, url
        comments { totalCount }
        reviews { totalCount }
      }
    }
  }' -f owner=OWNER -f repo=REPO -f pr=NUMBER
```

### 2. Event-First Invalidation

- **Mechanism**: Track `last_fetch_timestamp` in `cache_metadata.json` (written by `commentfetch.py`). On re-run, only process comments updated since that timestamp.
- **Implementation**: Reuse `commentfetch.py`'s `check_for_new_comments()` path / GitHub REST `since` parameter to scope comment fetches to `last_fetch_timestamp`.
- **Why**: Avoids re-fetching unchanged comments on every run.

```bash
# Only fetch comments updated after last run
gh api "repos/$OWNER/$REPO/issues/$PR/comments?since=2026-03-21T12:00:00Z" --paginate
```

### 3. Low-Frequency Backstop Polling

- **Mechanism**: Separate the "check for new comments" concern from the "process comments" concern.
- **Approach**: A lightweight polling agent (cron/scheduled) checks for new comments at low frequency (e.g., every 5 min) and notifies via a status check or CI comment.
- **Why**: Reduces per-run polling cost; new comment detection is decoupled from processing.

### 4. Worktree-First, PR-Last

- **Mechanism**: Prioritize local worktree operations (git diff, test run, file read) over remote API calls.
- **Approach**: Run `git diff` locally instead of fetching file contents via `repos/contents`. Cache CI/check status locally between steps.
- **Why**: Local git operations are free; each unnecessary `repos/contents` GET counts against rate limits.

```bash
# Local: free
git diff HEAD~1 --name-only

# Remote API: rate-limited
gh api "repos/$OWNER/$REPO/contents/path/to/file"
```

### 5. Batch Comment Fetching

- **Current**: `commentfetch.py` uses a `ThreadPoolExecutor` to fetch from 4 comment sources (inline, general, review, copilot) plus CI status concurrently.
- **Improvement**: Keep all 4 comment fetches (and CI status) in a single concurrent pipeline and use `--paginate` to collect all pages in one call.
- **Why**: Maintains low end-to-end latency while avoiding partial-fetch gaps and redundant re-fetches.

---

## Example PR Lifecycle: API Call Comparison

### Scenario: Single `/copilot` run on a PR with 10 comments

#### Before This Change (with Step 8.5 Delta Recheck)

| Step | API Call | Method | Count |
|------|----------|--------|-------|
| 1 | Get PR info | `gh pr view --json ...` | 1 |
| 2 | Fetch all comments (4 sources) | `commentfetch.py` (4 parallel) | 4 |
| 3 | Check CI status | `gh api repos/.../commits/.../status` | 1 |
| 4 | Categorize (LLM only, no API) | — | 0 |
| 5 | Fix code (local, no API) | — | 0 |
| 6 | Write responses.json (local) | — | 0 |
| 7 | Post consolidated comment | `gh pr comment` | 1 |
| 8 | Coverage check | `/commentcheck` (local) | 0 |
| **8.5** | **Delta recheck: re-fetch all comments** | `commentfetch.py` (4 parallel) | **4** |
| **8.5** | **If new comments: re-process + re-post** | `gh pr comment` | **1** |
| 9 | Push (if code changes) | `git push` (git protocol, not GH API) | 0 |
| 10 | Update PR description | `gh pr edit --body-file` | 1 |
| **Total** | | | **~13 calls** |

#### After This Change (Step 8.5 Removed)

| Step | API Call | Method | Count |
|------|----------|--------|-------|
| 1 | Get PR info | `gh pr view --json ...` | 1 |
| 2 | Fetch all comments (4 sources) | `commentfetch.py` (4 parallel) | 4 |
| 3 | Check CI status | `gh api repos/.../commits/.../status` | 1 |
| 4 | Categorize (LLM only, no API) | — | 0 |
| 5 | Fix code (local, no API) | — | 0 |
| 6 | Write responses.json (local) | — | 0 |
| 7 | Post consolidated comment | `gh pr comment` | 1 |
| 8 | Coverage check | `/commentcheck` (local) | 0 |
| 9 | Push (if code changes) | `git push` (git protocol, not GH API) | 0 |
| 10 | Update PR description | `gh pr edit --body-file` | 1 |
| **Total** | | | **~8 calls** |

#### API Call Delta

| Metric | Before | After | Reduction |
|--------|--------|-------|-----------|
| Total API calls (per run) | ~13 | ~8 | **~38% fewer** |
| Calls saved (delta recheck) | — | — | **~5 calls** |
| Thread resolution API calls | 0 | 0 | Eliminated intent to add |
| Re-fetch on new comments | ~4-8 extra | 0 | **Eliminated** |

#### With Future Optimizations (GraphQL + Event-First)

| Optimization | Estimated Additional Reduction |
|---|---|
| GraphQL batch fetch (4 sources → 1) | -3 calls |
| Event-first invalidation (skip unchanged) | -1-4 calls per re-run |
| Local git diff (no repos/contents fetch) | -0 to -2 calls |
| **Fully optimized total** | **~2-4 calls** |

---

## Thread Resolution API Calls — Explicit List

The following GitHub API operations are **never called** by `/copilot` (before or after this change):

| Operation | API Surface (examples) | Reason |
|-----------|------------------------|--------|
| Resolve or unresolve a review thread | GraphQL: `resolveReviewThread`, `unresolveReviewThread` (or any REST equivalent) | Not called — resolution is tracked only in the PR description table |
| Delete an issue or PR comment | Any `DELETE` operation that removes review or issue comments | Never needed |
| Mutate comment content or metadata for the purpose of changing resolution state | Any `PATCH` operation on review or issue comments | Not called — resolution semantics are not driven by direct comment mutation |

---

## Design Constraints

1. **No breaking changes to core workflow** — comment processing, tracking table, and coverage gate remain unchanged.
2. **PR description is source of truth** — resolution state is always visible and auditable in the tracking table.
3. **Idempotent by default** — re-running `/copilot` safely reconciles state without side effects.
4. **Rate-limit aware** — all API calls should be auditable and countable from logs.
