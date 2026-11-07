---
name: pr-efficiency-audit
description: Audit PR throughput, creation-to-merge duration, and stage dwell using exact UTC windows, full pagination, and mechanical event histories.
---

# PR Efficiency Audit (/efficiency)

Audits pull request throughput, lifecycle duration, and stage dwell across exact equal UTC windows without flawed sampling, artificial conversion metrics, or crude string-similarity heuristics.

## Measurement Protocol

### 1. Window Definition & Full Pagination
- **Exact UTC windows**: Define equal, non-overlapping or comparable windows using ISO-8601 timestamps (e.g. `[YYYY-MM-DDTHH:MM:SSZ, YYYY-MM-DDTHH:MM:SSZ)`).
- **Full pagination via GraphQL**: `gh pr list` does not support `--paginate`. Use `gh api graphql --paginate` with `$endCursor: String` and `pageInfo { hasNextPage, endCursor }` to traverse all results sequentially:
  ```bash
  # Query PRs created within window using cursor pagination
  gh api graphql --paginate -f query='
    query($q: String!, $endCursor: String) {
      search(query: $q, type: ISSUE, first: 100, after: $endCursor) {
        issueCount
        pageInfo {
          hasNextPage
          endCursor
        }
        nodes {
          ... on PullRequest {
            number
            title
            state
            createdAt
            closedAt
            mergedAt
            labels(first: 20) {
              nodes { name }
            }
          }
        }
      }
    }
  ' -f q="repo:<owner>/<repo> is:pr created:<WINDOW_START>..<WINDOW_END>"
  ```
  Query merged PRs in the same window separately if measuring merge events:
  ```bash
  # Query PRs merged within window using cursor pagination
  gh api graphql --paginate -f query='
    query($q: String!, $endCursor: String) {
      search(query: $q, type: ISSUE, first: 100, after: $endCursor) {
        issueCount
        pageInfo {
          hasNextPage
          endCursor
        }
        nodes {
          ... on PullRequest {
            number
            title
            state
            createdAt
            closedAt
            mergedAt
            labels(first: 20) {
              nodes { name }
            }
          }
        }
      }
    }
  ' -f q="repo:<owner>/<repo> is:pr is:merged merged:<WINDOW_START>..<WINDOW_END>"
  ```
- **Search-count and cap checks**: Verify `issueCount` on the first response page. GitHub Search caps results at 1,000 items. If `issueCount >= 1000`, the query hits the cap and will truncate; split the time window into narrower sub-windows (e.g. daily slices) to ensure complete data retrieval.
- **Half-open exact timestamp postfilters**: GitHub search date syntax (`created:START..END`) operates on day/minute resolution with inclusive boundaries. Apply an exact postfilter on ISO-8601 timestamps (`createdAt >= WINDOW_START && createdAt < WINDOW_END`) to maintain half-open `[WINDOW_START, WINDOW_END)` window boundaries.

### 2. Throughput & Cohort Metrics
- **Separate event counts**:
  * PRs created within the window.
  * PRs merged within the window.
  * PRs closed unmerged within the window.
- **No mixed-event conversion claims**: Do not compute a naive "merge rate" by dividing merged PRs by created PRs within the same window. PRs merged during a window include backlog items created earlier, while PRs created near the window end are right-censored (still in flight). Never present mixed event counts as a causal speed or cohort conversion rate.
- **Completed PR lifecycle duration**:
  * For PRs both created and merged (or closed cohorts), compute exact duration from creation to merge/closure.
  * Report distribution statistics: **median** and **p75** duration alongside sample size (**n**).
  * Document caveats: backlog aging, task mix (e.g. large refactors vs small fixes), and right-censoring of in-progress work.
- **No unsupported productivity or causal claims**: Do not attribute duration or throughput changes to tooling or developer speed without controlled task mix, backlog normalization, and explicit confounding factor documentation.

### 3. Stage Dwell & Timeline Analysis
- **Mechanical stage tracking**: Extract stage entry and exit timestamps from existing mechanical labels (e.g. `stage/*`), PR title stage tags, or timeline commit events.
- **Stage event uncertainty**: When stage transitions are missing, non-linear, or contradictory across labels and commit timestamps, record stage dwell status as `UNKNOWN` or `CONFLICT` with explicit uncertainty notes rather than assuming sequence or guessing timestamps.
- **Dwell breakdown**:
  * Record time spent per stage, repeated stage cycles, merge-conflict holds, and CI wait times.
  * Clearly distinguish **GitHub quiet time** (periods without comment or push events) from an agent being idle or forgotten.
  * Distinguish automated CI delays or human review holds from agent stall or neglect.

### 4. Qualitative Duplicate & Code Classification
- **Substantive duplicate detection**: Do not use naive title-string similarity heuristics. Flag duplicate or abandoned attempts only through agent inspection of actual evidence: identical goals, overlapping diffs, or explicit PR closure notes referencing superseding work.
- **Repository-native code classification**: If tracking LOC, use the target repository's real classification tooling and definitions (e.g. pygount or repo language configs), rather than crude title prefixes (`fix/feat`) or hardcoded path exclusions.

## Storage & Reporting

- **Reuse existing records**: Leverage `history`, `ms`, and existing PR timeline receipts. Do not introduce new enforcement frameworks, background scorers, or ledgers.
- **Audit reports**: Save human-readable summary reports to `~/roadmap/` (e.g. `~/roadmap/pr-efficiency-<repo>-<window>.md`).
- **Bulky evidence**: Save large raw JSON dumps, event logs, and paginated query payloads to Scratch space (`diskm scratch-new` or host scratch), never in the repository tree.
