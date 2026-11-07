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
- **Equal weekly window stratification**:
  * Compare equal weekly windows stratified by **repository**, **selected route/risk** (e.g. instruction-only, bounded-code, UI/evidence; extracted mechanically from the PR Review Ledger's declared route or repository file-path classification via repo tooling, recording `UNKNOWN` when neither is present), and **size** (e.g. small/compact vs medium/large).
  * For each stratum, report **median**, **p75**, sample count (**n**), observational telemetry **coverage** (percentage of PRs with complete event telemetry), and **still-open work** (in-flight PRs at window cutoff).
  * Keep **backlog separate** from intra-window delivery to avoid confounding historical backlog aging with current-window execution velocity.
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
- **Derived handoff and lead-time metrics**:
  * Where observational runtime telemetry (`run.stats.json`) or attempt receipts exist, derive the lifecycle and closeout intervals:
    - *PR lead time*: `merged_at` minus `created_at`.
    - *Pre-publication time*: PR `created_at` minus task `accepted_at`.
    - *Task-to-merge*: `merged_at` minus task `accepted_at` (exposes delays hidden by late PR creation).
    - *Authorized closeout delay*: `merged_at` minus `authority_ready_at` (or `UNKNOWN` when `authority_ready_at` is `null` or unrecorded).
- **No mixed-event conversion claims**: Do not compute a naive "merge rate" by dividing merged PRs by created PRs within the same window. PRs merged during a window include backlog items created earlier, while PRs created near the window end are right-censored (still in flight). Never present mixed event counts as a causal speed or cohort conversion rate.
- **No unsupported productivity or causal claims**: Do not attribute duration or throughput changes to tooling or developer speed without controlled task mix, backlog normalization, and explicit confounding factor documentation.

### 3. Stage Dwell & Title Parsing
- **Mechanical stage tracking**: Extract stage entry and exit timestamps from mechanical labels (e.g. `stage/*`), execution records in the PR description, or timeline commit events.
- **Title parsing and operational status compatibility**:
  * **Legacy stage titles**: Historical PRs may carry legacy two-letter stage prefixes (e.g. `[fa]`, `[sp]`, `[ev]`, `[cd]`, `[rv]`, `[cr]`) or trailing stage suffixes (e.g. `[final approval]`, `[spec]`). Preserve legacy stage-title parsing for historical PR dwell calculations.
  * **Operational status titles**: Migrated repositories adopt `[status][short detail] <substantive change> [<cli>][<model>]` (e.g. `[working][fixing review]`, `[waiting][CI]`, `[queued][source review]`, `[ready][needs approval]`, `[blocked][user pause]`). Status tokens reflect the current active execution state or dependency; NEVER reinterpret operational status tokens like `[working]`, `[waiting]`, `[queued]`, `[ready]`, `[blocked]`, or `[unknown]` as stage transitions. Lifecycle stages remain tracked exclusively by mechanical labels (`stage/*`) and PR review ledgers.
- **Stage event uncertainty**: When stage transitions are missing, non-linear, or contradictory across labels and commit timestamps, record stage dwell status as `UNKNOWN` or `CONFLICT` with explicit uncertainty notes rather than assuming sequence or guessing timestamps.
- **Handoff metrics and interval analysis**:
  * Extract granular handoff metrics from observational Scratch runtime telemetry (`run.stats.json`) and review receipts:
    - *Evidence dispatch delay*: `review_requested_at` minus `evidence_ready_at` (interval between required proof being complete, readable, and available at candidate SHA and actual review dispatch). Both endpoints and proof applicability required.
    - *Reviewer pickup delay*: `actual_review_started_at` minus `review_requested_at` (time until the reviewer actually initiates substantive inspection; an acknowledged message or `queued_at` is not review start).
    - *Review execution time*: `review_return_at` minus `actual_review_started_at`.
    - *Driver response delay*: `next_substantive_action_started_at` minus `review_return_at` (time from review return to driver resuming substantive action; may contain legitimate work or waits).
    - *Authorized closeout delay*: `merged_at` minus `authority_ready_at` (time between `FINAL_READY` + merge authority being verified and actual merge execution).
    - *Eligible unattended interval*: Derived classification column computed only from recorded receipt/process timestamps (`review_return_at` to `next_substantive_action_started_at` when an executable authorized action existed with no active owner/job or legitimate hold; otherwise `UNKNOWN` or an identified waiting category).
- **Censoring and waiting rules**:
  * **Interval censoring on invalidation**: If proof is invalidated before reviewer pickup (e.g. candidate head SHA moved or claims changed), close/censor that interval with the explicit reason rather than counting the whole period as reviewer neglect.
  * **Waiting category separation**: Treat active execution, CI/provider waits, explicit user holds, authority waits, and unknown periods separately.
  * **No inferred idleness from quiet periods**: Never infer uninterrupted idleness from missing GitHub writes (e.g. periods without comment or push events).
- **Dwell breakdown**:
  * Record time spent per stage, repeated stage cycles, merge-conflict holds, and CI wait times.
  * Clearly distinguish **GitHub quiet time** (periods without comment or push events) from an agent being idle or forgotten.
  * Distinguish automated CI delays or human review holds from agent stall or neglect.

### 4. Time Semantics & Active Effort Model

To prevent conflating total elapsed calendar time with agent effort or wasted time, adhere strictly to the following semantic distinctions:

| Metric | Definition | Measurement Constraints & Bounds |
|---|---|---|
| **PR elapsed** | `merged_at - created_at` | Total delivery cycle time; open PRs at collection cutoff are right-censored. Includes parked/draft time. |
| **Task elapsed** | `endpoint_at - original_accepted_at` | Total task cycle from acceptance to verified completion. Missing original acceptance is strictly `UNKNOWN`. `closure_sprint_elapsed` is measured separately. |
| **Observed operation elapsed** | `queued_at -> completed_at` for CLI or API operations | Span encompassing local setup, remote provider queue time, execution, and network I/O. When inner process/CPU boundaries are absent, this MUST be labeled *observed operation elapsed*, not pure model reasoning or CPU active time. |
| **Observed active wall time** | Interval union ($\bigcup [t_{\text{start}}, t_{\text{end}}]$) of evidenced substantive agent/model/tool execution intervals for this PR | Wall-clock span where at least one agent or tool was actively executing on this PR. Never gap-filled from message timestamps; endpoint verification required. |
| **Agent effort** | Sum ($\sum (t_{\text{end}} - t_{\text{start}})$) of per-agent evidenced active intervals | Cumulative worker execution time across all parallel agents/subagents. Can exceed *Observed active wall time* and *PR elapsed*. **Never sum agent effort together with active wall time.** |
| **Waiting time** | Observed CI/provider/dependency/human-hold intervals | Segregated into distinct categories (CI queue, provider rate limit, external dependency, human review/hold); use interval union for aggregate waiting time. |
| **Avoidable unattended time** | Disjoint evidenced intervals with an executable authorized action, no executing owner/job, and no legitimate hold | Requires positive eligibility, authority, and continuity evidence. If active worker or hold state is unobserved, evaluates strictly to `UNKNOWN`. |

#### Essential Accounting Rules
- **Residual Rule**: Residual duration (`PR elapsed - observed_active_wall_time`) is **NOT** wasted time. It contains observed waiting times (CI runs, external dependencies), legitimate human review and design reflection, authorized pauses, and unobserved periods. Incomplete telemetry yields observed lower bounds and explicit `UNKNOWN` duration, never a speculative decomposition into waste.
- **Active Wall Time vs. Agent Effort**: Wall time answers "how long was the clock running while work occurred?" whereas agent effort answers "how many worker-hours were consumed across all lanes?". They answer orthogonal questions and must never be combined or confused.
- **Four-Hour Sampling Uncertainty**: Four-hour snapshot cadences observe state periodically; they cannot certify continuous inactivity between samples. Snapshots must never fabricate continuous idleness between observations.

### 5. Human Interactions per PR & Episode Annotation

Human interventions must be tracked accurately to identify genuine agent failures versus routine collaboration and new product guidance.

#### 1. Message Count vs. Deduplicated Episodes
- **Raw human message count**: Total count of inbound human messages in the task/PR context.
- **Deduplicated intervention episodes**: One distinct human contribution or issue plus its immediate clarifying follow-ups constitutes exactly **one episode** (e.g. three consecutive messages from the operator clarifying a single spec ambiguity count as 3 messages but 1 episode).
- **Auditability**: For every episode, record the exact episode boundaries, source conversation runtime, and source `message_id`s so grouping is fully inspectable.

#### 2. Rigorous Origin Filtering & Bot Exclusion
- **Exclude Non-Human Triggers**: Initial task assignments, automated bots, background agents, quota/resume watchdogs, scheduled reminders, and copied/mirrored transcripts are strictly excluded from human intervention counts.
- **Origin Verification**: A message delivered with `role=user` or in a user channel is not automatically a genuine human intervention. Inspect transport metadata, sender IDs, and context. Unclear origins MUST remain `UNKNOWN` and be excluded from confident human interaction counts.

#### 3. Four Semantic Episode Categories
Classification must be authored by the PR driver, an independent human reviewer, or a bounded retrospective model pass citing specific evidence, model/version, and confidence. **NEVER use keyword matching, substring rules, or regex heuristics to classify human interactions.**

| Category | Operational Meaning | Evidenced Examples |
|---|---|---|
| **good** (*value-adding*) | Intended human review, domain judgment, design pivot, or changed requirement. | Human reviews valid visual video evidence and updates spec; operator supplies an authorized merge or scope decision upon request. |
| **bad** (*avoidable*) | Human effort caused by an evidenced agent error, rule violation, or missed authorized follow-through. | Agent ignored existing repository rule; agent stopped with an executable, authorized next action and the human had to manually nudge/resume it. Root-cause investigations (`/harness`) to address the same failure belong to the same episode, not a separate `good` episode. |
| **mixed** | One episode contains both useful new domain judgment and correction of an agent error. | Operator approves an architectural direction while also pointing out an agent test regression introduced in the same turn. |
| **unknown** | Insufficient context, unclear responsibility, or uncertain PR association. | Bare prompt like `"continue"` or `"proceed"` with ambiguous prior task activity or absent hold state. |

#### 4. Attribution, Population Rates & Calibration
- **Preserve Unassigned Episodes**: Task-level episodes that cannot be definitively linked to a specific PR must be recorded with `pr_attribution: "unassigned"`. Never artificially force a task-level intervention into a specific PR.
- **No Conflated Population Rates**: Never divide a selected incident sample by the total count of repository PRs to claim an overall human-intervention or error rate.
- **Channel Coverage Invariant**: Never claim a PR or task is `"zero-touch"` unless all applicable human communication channels (e.g. Dot history, direct CLI sessions, Slack threads) were explicitly audited and covered.
- **Post-Merge Corrections**: Interventions that address regressions after PR merge must be recorded with timing `post_merge`, not excluded or hidden from the PR's historical audit.
- **Cross-Annotator Calibration**: When evaluating human interaction quality, run calibration on a shared sample of episodes across independent annotators. If annotators disagree on attribution or category, record the resolution as `mixed` or `unknown`; never resolve disagreements by arbitrary majority vote.

### 6. Qualitative Duplicate & Code Classification
- **Substantive duplicate detection**: Do not use naive title-string similarity heuristics. Flag duplicate or abandoned attempts only through agent inspection of actual evidence: identical goals, overlapping diffs, or explicit PR closure notes referencing superseding work.
- **Duplicate full review tracking**:
  * Track duplicate full reviews only when unchanged claim coverage is established (e.g. re-running an entire review suite on a candidate where existing receipts already verified valid claim coverage without head or contract drift).
- **Quality safeguards and regression tracking**:
  * Optimize the largest measured wait or repeated work, but always track post-approval P0 discoveries/reverts alongside duration and throughput metrics so speed does not conceal lower quality or bypassed standards.
- **Repository-native code classification**: If tracking LOC, use the target repository's real classification tooling and definitions (e.g. pygount or repo language configs), rather than crude title prefixes (`fix/feat`) or hardcoded path exclusions.

## Storage & Reporting

- **Scheduled collection & dashboard:** `scripts/prw_metrics.py` (and `scripts/run_prw_metrics.sh`) implements the scheduled 4-hour rolling collector and private dashboard renderer following this skill's window, handoff, and `UNKNOWN` idle rules.
- **Reuse existing records**: Leverage `history`, `ms`, and existing PR timeline receipts. Do not introduce new enforcement frameworks, background scorers, or ledgers.
- **Audit reports**: Save human-readable summary reports to `~/roadmap/` (e.g. `~/roadmap/pr-efficiency-<repo>-<window>.md`).
- **Private telemetry retention**: Retain underlying observational telemetry under `dashboards/prw/telemetry/` in the private `roadmap` repository (`<org>/roadmap`) to guarantee reproducible audit studies and deterministic rebuilds even when local Scratch directories are rotated.
- **Bulky evidence**: Save large raw JSON dumps, event logs, and paginated query payloads to Scratch space (`diskm scratch-new` or host scratch), never in the primary repository tree.
