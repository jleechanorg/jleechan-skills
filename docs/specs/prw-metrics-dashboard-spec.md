# Specification: PRW Metrics Dashboard

## 1. Outcome

A lightweight, automated metrics collector and renderer that publishes a single, private GitHub Markdown dashboard at `dashboards/prw/README.md` in the private `roadmap` repository (`<org>/roadmap`). The dashboard refreshes every four hours via macOS `launchd`, providing the operator with transparent visibility into:
1. Multi-repository delivery velocity and cycle times across rolling seven-day windows (`W1` preceding vs. `W2` recent).
2. Labeled stage dwell time across Stages 0 through 5, explicitly separated from agent idle time.
3. Operational execution state via `[status][short detail]` titles (`working`, `waiting`, `blocked`, `queued`, `ready`, `unknown`), separating operational activity from lifecycle stages.
4. Granular, per-attempt handoff waiting delays and strict time semantics (distinguishing operation elapsed, active wall time union, agent effort sum, and non-waste residuals).
5. Human interaction and episode annotations (`good`, `bad`, `mixed`, `unknown`) with channel coverage auditing.
6. An actionable Open PR Attention Table that connects open PRs to their earliest unmet required obligations, accountable owners, active job handles, and receipt links.
7. Private telemetry retention under `dashboards/prw/telemetry/` in `<org>/roadmap`, enabling deterministic study readback and historical reconstruction when local Scratch directories are rotated.

---

## 2. Non-Goals

1. **No Automatic State Changes**: The dashboard is strictly observational. It performs zero PR status mutations, label synchronizations, automatic approvals, merges, nudges, or comments.
2. **No Public Site or GitHub Pages**: No public dashboard, GitHub Pages deployment, or external web service. All rendering uses GitHub's native Markdown viewer inside the private `roadmap` repo.
3. **No Heavy Compute or Paid Models**: No recurring LLM invocations, full test suite executions, or heavy browser automation inside the scheduled collector job.
4. **No Fabricated Telemetry**: Unobserved intervals and missing telemetry are never estimated or reported as `0s`; they are strictly reported as `UNKNOWN` (`telemetry coverage 0%`).
5. **No Credential Storage**: No secrets, personal tokens, or API keys are embedded in plist templates, scripts, or tracked repository files.
6. **No Heuristic Keyword Classifiers**: Human intervention quality is evaluated via model review or human annotation citing explicit evidence, never keyword matching, regex rules, or crude sentiment scoring.

---

## 3. Acceptance Criteria

### 3.1 Data Collection & Window Filtering
- **Multi-Repository Scope**: Queries configured repositories (for example `<org>/skills-repo`, `<org>/frontend-repo`, and `<org>/backend-repo`) independently using paginated GitHub API queries.
- **Exact Half-Open Windows**: Divides the rolling 14-day evaluation horizon into two equal, non-overlapping 7-day windows at an immutable UTC collection cutoff $T_{\text{cutoff}}$:
  - $\text{W1 (Preceding Window)}: [T_{\text{cutoff}} - 14\text{d}, T_{\text{cutoff}} - 7\text{d})$
  - $\text{W2 (Recent Window)}: [T_{\text{cutoff}} - 7\text{d}, T_{\text{cutoff}})$
- **Backlog Partitioning**: Partitions PRs merged within each window into:
  - *Comparable Recent Merges* ($\le 7$ days from `createdAt` to `mergedAt`).
  - *Historical Backlog Merges* ($> 7$ days old at merge), preventing long-parked draft branches from skewing recent turnaround statistics.
- **Private Telemetry Retention**: Sanitized event/episode records, collected PR records, timeline events, handoff receipts and per-source cutoffs (fixed fields only; PR bodies, raw message text, transcripts, excerpts and error strings are never retained) are stored under `dashboards/prw/telemetry/<window_slug>/` in `<org>/roadmap`, ensuring deterministic audit studies and dashboard rebuilds even after local host Scratch is cleared.

### 3.2 Time Semantics & Active Work Model
- **Per-Attempt Timestamps**: Timestamp subtraction for review handoff intervals (`review_requested_at` to `actual_review_started_at`) must be computed strictly within the same review attempt. Timestamps from different attempts are never combined.
- **Strict Time Semantics**:
  - `PR elapsed`: `merged_at - created_at` (open PRs right-censored at collection cutoff).
  - `Task elapsed`: `endpoint_at - original_accepted_at` (missing acceptance is `UNKNOWN`; closure sprint duration is separate).
  - `Observed operation elapsed`: `queued_at -> completed_at` for CLI or model operations, encompassing setup, provider queuing, and I/O. Labeled *operation elapsed*, never pure CPU or reasoning active time unless inner execution boundaries exist.
  - `Observed active wall time`: Interval union ($\bigcup [t_{\text{start}}, t_{\text{end}}]$) of evidenced substantive agent/tool execution intervals for this PR. Never gap-filled from message timestamps.
  - `Agent effort`: Sum ($\sum (t_{\text{end}} - t_{\text{start}})$) of per-agent evidenced active intervals across parallel agents. Can exceed active wall time and PR elapsed; never summed together with active wall time.
  - `Waiting time`: Observed CI/provider/dependency/human-hold intervals; report category breakdown and interval union.
  - `Avoidable unattended time`: Disjoint evidenced intervals with an executable authorized action, no executing owner/job, and no legitimate hold; requires positive eligibility and continuity evidence, otherwise `UNKNOWN`.
- **Empty Duration Cohorts**: When a duration distribution has `n = 0`, report its median and p75 as `UNKNOWN`; preserve observed zero-duration events as numeric zero.
- **Residual Rule**: Residual duration (`PR elapsed - observed_active_wall_time`) is NOT wasted time. It contains observed waiting times, human reflection, and unobserved periods.
- **Honest Missing Data**: If owner, job, or hold observation is absent during an open interval, `eligible_unattended_interval` evaluates strictly to `UNKNOWN`, never `0s`.

### 3.3 Operational Status Titles
- **Parsing Operational Titles**: The collector supports PR titles formatted as `[status][short detail] <substantive change> [<cli>][<model>]`.
- **Status Tokens**: Valid status tokens include `working`, `waiting`, `blocked`, `queued`, `ready`, and `unknown`.
- **Decoupling Status from Stages**: Status tokens reflect present-moment execution activity or pending dependency. They must NEVER be reinterpreted as lifecycle stage transitions. Lifecycle stages remain tracked strictly by mechanical labels (`stage:*`) and PR review ledgers.
- **Legacy Compatibility**: Historical PRs carrying two-letter stage prefixes (e.g. `[fa]`, `[sp]`) or trailing stage suffixes (e.g. `[final approval]`) are parsed for historical stage dwell without converting status tokens into stages.

### 3.4 Human Interactions & Episode Annotation
- **Deduplicated Episodes**: Raw message count is distinguished from deduplicated intervention episodes (one distinct human contribution/issue plus clarifying follow-ups = 1 episode). Record episode boundaries and source `message_id`s.
- **Human Actor and Source Identity**: A positively classified `actor_status: human` establishes the speaker independently of the source channel; `role=user` or a channel label alone is not human proof. Deduplicate message IDs within explicit `source_namespace`, falling back to channel/origin; missing or malformed IDs make message identity coverage partial or unknown and cannot prove Dot connector completeness.
- **Bot and Origin Filtering**: Count initial task assignment messages in raw human messages and initial task requests, but exclude them from qualifying follow-up episodes. Exclude automated bots, background agents, quota/resume watchdogs, and copied/mirrored transcripts; unclear origins remain `UNKNOWN`.
- **Semantic Classification**: Four categories authored by driver, reviewer, or bounded model pass citing specific evidence (never keyword/regex rules):
  - `good` (*value-adding*): Intended human review, new domain judgment, spec revision from valid video evidence, requested merge decision.
  - `bad` (*avoidable*): Human effort caused by an evidenced agent error, rule miss, or unresumed authorized step. Root-cause `/harness` work belongs to the same episode.
  - `mixed`: The human contribution itself contains both useful new domain judgment and correction of an agent miss; annotator disagreement alone is not `mixed`.
  - `unknown`: Insufficient context, unclear responsibility, or uncertain PR association.
- **Attribution & Coverage Rules**:
  - Preserve `pr_attribution: "unassigned"` for task-level episodes; never force assignment to a PR.
  - Never divide an incident sample by total PR population to claim a failure rate.
  - Never claim "zero-touch" unless all relevant human channels (including Dot history) are audited.
  - Count post-merge corrections under `post_merge`.
- **Cross-Annotator Calibration**: Evaluate sample episodes across independent annotators. A valid explicit adjudicated label wins; without one, use an agreed annotator label and record unresolved disagreement as `unknown`.

### 3.5 Dashboard Health States
The dashboard must cleanly surface operational states in the header and tables:
- `FRESH`: Refreshed within the last 4-hour cycle.
- `STALE`: Prior collection preserved when a refresh was missed (e.g. machine offline/sleep), prominently displaying the last successful collection timestamp.
- `PARTIAL_FAILURE`: An individual repository or query shard failed; the dashboard renders available data, notes the partial error, and preserves the prior cutoff without fabricating zeroes.
- `EMPTY`: Cohort or window containing zero events.
- `UNKNOWN`: Missing observational telemetry or unrecorded fields.
- `CONFLICT`: Contradictory timeline events or out-of-order stage transitions.

### 3.6 Scheduling & Publication
- **Calendar Intervals**: Scheduled via `launchd` in 4-hour calendar slots at `00:17`, `04:17`, `08:17`, `12:17`, `16:17`, `20:17` local time, writing all timestamps in UTC.
- **State and Lock Directories**: After configuration is loaded, create the effective state directory and lock-file parent required for collection.
- **Scoped Publication**: Publishes strictly to `dashboards/prw/README.md` and `dashboards/prw/telemetry/` in private `roadmap` using standard fast-forward git pushes with remote-head reconciliation. Never uses force-push.
- **Atomic Failure Handling**: On API or script failure, the existing dashboard is preserved; no partial or empty Markdown commit is published.

---

## 4. User Stories

See [User Story: PRW Metrics Dashboard](../user-stories/prw-metrics-dashboard.md) for full before/after narratives and operator workflows across:
- Scenario 1: Morning Operational Triage.
- Scenario 2: Sprint Velocity and Bottleneck Analysis.
- Scenario 3: Respecting Parked and Unobserved States.
- Scenario 4: Offline and Rate-Limit Resilience.
- Scenario 5: Human Interaction Triage and Quality Calibration.

---

## 5. Proof Plan

### 5.1 Automated TDD Unit Tests
1. **`tests/test_prw_metrics.py`**:
   - Pagination handling across $> 100$ items.
   - Deduplication of overlapping search results across shards.
   - Half-open window partitioning (`W1` vs. `W2`).
   - Timestamp subtraction arithmetic within single attempts.
   - Time semantics: active wall union vs agent effort sum; operation elapsed labeling.
   - Parsing of `[status][short detail]` titles without reinterpreting them as stages.
   - Human episode deduplication and bot origin filtering.
   - Assertion that missing telemetry outputs `UNKNOWN` instead of `0s`.
   - Markdown rendering across `FRESH`, `STALE`, `PARTIAL_FAILURE`, and `EMPTY` states.
2. **`tests/test_prw_metrics_scheduler.py`**:
   - Verification of `@HOME@` placeholder replacement in the launchd plist template.
   - Validation that the six `:17` calendar slots are present.
   - Verification that no tokens or private credentials exist in the template or wrapper.
   - Validation of temporary rendered plist via `plutil -lint`.

### 5.2 Real Operational & Visual Verification
1. **Launchd Job Verification**: Execute `launchctl print gui/$(id -u)/com.jleechan.prw-metrics` to confirm job registration, execute one manual test run, and verify generated output.
2. **Private Publication Verification**: Verify clean push and readback of `dashboards/prw/README.md` and telemetry records on the private `roadmap` repository.
3. **Browser Visual Inspection**: Open `https://github.com/<org>/roadmap/blob/main/dashboards/prw/README.md` in a verified headless browser session to ensure tables render cleanly on narrow and wide desktop viewports.

---

## 6. Mock / Layout Preview

```markdown
# PRW Quality & Handoff Metrics Dashboard

**Status**: FRESH | **Generated (UTC)**: 2026-11-07 12:17:00Z | **Data Cutoff (UTC)**: 2026-11-07 12:00:00Z
**Rolling Horizon**: [2026-10-24 12:00:00Z, 2026-11-07 12:00:00Z)
**Windows**: W1 (Prior 7d): [10-24, 10-31) | W2 (Recent 7d): [10-31, 11-07)
**Telemetry Coverage**: 85.2% (14 / 16 active PRs observed)

---

## 1. Repository Comparison (W1 Prior vs. W2 Recent)

| Repository | Window | Created | Merged (<=7d) | Backlog Merged (>7d) | Open | Median Open->Merge | p75 Open->Merge |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **<org>/skills-repo** | W1 | 75 | 71 | 1 (173h) | 12 | 1.55h | 6.53h |
| | W2 | 102 | 93 | 13 (331h) | 18 | 2.38h | 21.32h |
| **<org>/frontend-repo** | W1 | 145 | 133 | 18 (201h) | 22 | 7.24h | 46.53h |
| | W2 | 128 | 120 | 5 (271h) | 19 | 5.72h | 14.17h |
| **<org>/backend-repo**| W1 | 150 | 141 | 7 (280h) | 25 | 13.69h | 45.76h |
| | W2 | 135 | 126 | 17 (300h) | 21 | 7.18h | 48.99h |

---

## 2. Stage Dwell Durations (Elapsed Stage Time, Not Agent Idle)

| Repository | Stage 0 (Spec) | Stage 1 (Code) | Stage 2 (Evidence) | Stage 3 (Review) | Stage 4 (CI/Undraft) | Stage 5 (Approval) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **skills-repo** | 0.25h | 1.10h | 0.45h | 0.85h | 0.30h | 0.20h |
| **frontend-repo** | 0.50h | 2.15h | 1.20h | 1.45h | 1.10h | 0.40h |
| **backend-repo** | 0.40h | 3.20h | 1.50h | 1.80h | 1.25h | 0.50h |

---

## 3. Time Semantics & Effort Breakdown

| Metric | Sample (n) | Median | p75 | Definition / Notes |
|---|:---:|:---:|:---:|---|
| **Observed Operation Elapsed** | 42 | 4m 12s | 11m 30s | Queued to completed CLI/API span (includes setup & I/O) |
| **Observed Active Wall Time** | 38 | 1.85h | 4.20h | Union of substantive agent/tool execution intervals |
| **Agent Effort (Sum)** | 38 | 3.10h | 8.45h | Sum of parallel worker active intervals (can exceed wall time) |
| **Observed Waiting Time** | 38 | 0.45h | 1.60h | Union of CI queues, provider limits, and human holds |
| **Residual (Non-Wasted)** | 38 | 0.60h | 2.10h | Elapsed minus active wall time; includes reflection & unobserved spans |

---

## 4. Handoff Delays (Granular Attempt Measurements)

| Metric | Sample (n) | Median Delay | p75 Delay | Telemetry Coverage | Status |
|---|:---:|:---:|:---:|:---:|:---:|
| **Evidence Ready -> Review Dispatch** | 42 | 1m 15s | 2m 45s | 100% | FRESH |
| **Review Request -> Actual Reviewer Start** | 42 | < 1s (Linux) | 35m (Mac rtk) | 95.2% | FRESH |
| **Review Return -> Next Substantive Action** | 38 | 2m 10s | 5m 30s | 92.1% | FRESH |
| **Final Ready + Authority -> Executed Merge** | 36 | 1m 45s | 3m 20s | 100% | FRESH |

---

## 5. Human Interaction & Episode Breakdown

| Category | Episodes | Raw Messages | Share of Observed | Operational Meaning |
|---|:---:|:---:|:---:|---|
| **Good (Value-Adding)** | 14 | 22 | 70.0% | Spec refinement from video evidence, requested merge decision |
| **Bad (Avoidable)** | 4 | 7 | 20.0% | Agent rule miss, unresumed authorized action |
| **Mixed** | 2 | 5 | 10.0% | New guidance combined with error correction |
| **Unknown** | 3 | 3 | - | Insufficient context or unclear channel attribution |
| **Total Observed** | 20 | 34 | 100.0% | Channel audit: CLI (covered), Slack (covered), Dot (untested) |

*Note: 2 task-level episodes retained as `pr_attribution: "unassigned"`. "Zero-touch" not claimed while Dot channel is untested.*

---

## 6. Open PR Attention Table

| PR | Title (Operational Status) | Candidate SHA | Earliest Unmet Obligation | Next Action | Owner | Waiting Duration | Receipts |
|---|---|:---:|---|---|---|:---:|:---:|
| **#742** | `[working][fixing review] Correct wiki path` | `a1b2c3d` | Source Review Quorum | Dispatch Seat 2 review | lane-b | 12m | [Receipt](receipts/742.md) |
| **#562** | `[waiting][CI] Upgrade jest runner` | `d4e5f6a` | CI and Undraft | Re-run Jest test suite | lane-a | 18m | [Receipt](receipts/562.md) |
| **#11205**| `[ready][needs approval] Migrate auth schema` | `b7c8d9e` | Merge Authority | Awaiting user approval | driver | 1h 45m | [Receipt](receipts/11205.md) |
| **#738** | `[blocked][user pause] Design tokens RFC` | `e9f0a1b` | UNKNOWN | Design consensus | none | 72h | UNKNOWN (0% coverage) |

---

## 7. Notes & Data Definitions
- **Operational Titles**: Format `[status][short detail]`. Operational status tokens reflect present-moment execution; never reinterpreted as stage advancement.
- **Stage Dwell**: Calendar duration between observed stage labels; does NOT imply agent neglect.
- **Eligible Idle**: Derived only when an authorized next action was executable without an active worker; unobserved periods evaluate to `UNKNOWN`.
- **Backlog**: PRs merged $>7$ days after creation.
```

---

## 7. Risks & Mitigations

| Risk | Severity | Mitigation |
|---|:---:|---|
| **Accidental Credential Leakage** | Critical | Sourcing profile and ambient `gh` CLI credentials only. Zero tokens, passwords, or personal hostnames in plists, scripts, or tracked Markdown files. |
| **Merge / Git Publication Conflict** | Medium | The publisher fetches the remote `roadmap` branch, attempts a clean fast-forward rebase, reconciles only `dashboards/prw/README.md` and telemetry files, and fails safely without force-pushing. |
| **Misleading Idle Accusations** | High | Clear visual and lexical separation between stage dwell (elapsed calendar time) and eligible unattended delay. Residual duration (`elapsed - active`) is explicitly defined as non-waste. Unobserved telemetry is strictly displayed as `UNKNOWN (telemetry coverage 0%)`. |
| **Telemetry Loss Across Host Rotations** | Medium | Sanitized event logs (fixed scalar fields) and receipts are committed under `dashboards/prw/telemetry/` in `<org>/roadmap`, guaranteeing reproducible audit studies and deterministic rebuilds even when local Scratch is rotated. |
| **Subjective Human Intervention Scoring** | Medium | Grounded in four strict semantic categories authored by model/human evaluation with cited evidence rationales, origin metadata checks (excluding bots), cross-annotator calibration, and explicit preservation of `unassigned` task episodes. |
| **Host Sleep / Network Interruption** | Low | If the host is asleep or offline during a scheduled slot, the job runs on next wake; the previous dashboard remains intact and is explicitly stamped with its prior cutoff and `STALE` status. |
