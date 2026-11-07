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
- **Half-open exact timestamp postfilters**: GitHub search date syntax (`created:START..END`, `merged:START..END`, `closed:START..END`) operates on day/minute resolution with inclusive boundaries. Apply an exact postfilter on ISO-8601 timestamps matched to the specific measured event to maintain half-open `[WINDOW_START, WINDOW_END)` boundaries:
  * When filtering created PRs (`created:...`), postfilter on `createdAt`: `createdAt >= WINDOW_START && createdAt < WINDOW_END`.
  * When filtering merged PRs (`merged:...`), postfilter on `mergedAt`: `mergedAt >= WINDOW_START && mergedAt < WINDOW_END`. Never filter merge events on `createdAt`, which drops backlog PRs created prior to the window start that merged inside the window.
  * When filtering closed unmerged PRs (`closed:...`), postfilter on `closedAt`: `closedAt >= WINDOW_START && closedAt < WINDOW_END`.

### 2. Throughput & Cohort Metrics
- **Separate event counts & explicit denominators**:
  * PRs created within the window ($N_{\text{created}}$, denominator for creation cohort).
  * PRs merged within the window ($N_{\text{merged}}$, denominator for merge delivery cohort).
  * PRs closed unmerged within the window ($N_{\text{closed\_unmerged}}$).
- **Window scenario & censoring rules**:
  * **Backlog merges**: A PR created before `WINDOW_START` and merged inside `[WINDOW_START, WINDOW_END)` MUST count toward window merges ($N_{\text{merged}}$).
  * **Right-censored in-flight PRs**: A PR created inside `[WINDOW_START, WINDOW_END)` and merged after `WINDOW_END` (or still open at cutoff) is right-censored / unmerged at cutoff; it counts toward $N_{\text{created}}$ but is excluded from completed intra-window cohort duration.
- **Completed PR lifecycle duration**:
  * Distinguish **merged-event cohort latency** from **both-created-and-merged cohort latency**, always reporting distinct metrics and naming explicit denominators:
    - *Merged-event cohort duration* ($N_{\text{merged}}$ denominator): Duration from `createdAt` to `mergedAt` for all PRs merged within `[WINDOW_START, WINDOW_END)`. Reflects total delivery cycle time including historical backlog aging.
    - *Both-created-and-merged cohort duration* ($N_{\text{created\_and\_merged}}$ denominator): Duration from `createdAt` to `mergedAt` strictly for PRs both created and merged within `[WINDOW_START, WINDOW_END)`. Reflects turnaround time for intra-window cycles; document right-censoring bias (longer tasks initiated in the window remain in flight).
  * Report distribution statistics: **median** and **p75** duration alongside sample size (**n**).
  * Document caveats: backlog aging, task mix (e.g. large refactors vs small fixes), and right-censoring of in-progress work.
- **No mixed-event conversion claims**: Do not compute a naive "merge rate" by dividing merged PRs by created PRs within the same window. PRs merged during a window include backlog items created earlier, while PRs created near the window end are right-censored (still in flight). Never present mixed event counts as a causal speed or cohort conversion rate.
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
