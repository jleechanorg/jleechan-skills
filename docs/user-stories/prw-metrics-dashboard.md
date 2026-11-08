# User Story: PRW Metrics Dashboard

## Problem Statement

When operating autonomous development workflows across multiple repositories (for example `<org>/skills-repo`, `<org>/frontend-repo`, and `<org>/backend-repo`), the engineering operator faces severe information fragmentation:
1. Operational metrics and attempt receipts are scattered across ad-hoc local files, scratch paths, and disparate GitHub PR timelines.
2. Long-parked PRs (e.g. branches legitimately waiting on multi-day architectural consensus or user feedback) cannot easily be distinguished from abandoned or stalled PRs that have an executable, authorized next action with nobody acting.
3. Prior reports conflated stage label dwell time (elapsed wall-clock time in a stage) with agent idleness, resulting in misleading or unverified idle accusations.
4. Timestamp subtraction often mixed different review attempts or treated unobserved intervals as zero instead of explicitly flagging missing telemetry as unknown.
5. PR titles carried either legacy two-letter stage abbreviations or trailing suffixes that did not indicate whether work was actively executing, waiting on a job, or blocked on a dependency.
6. Elapsed PR duration was naively equated with wasted time or continuous agent effort, conflating total CLI operation spans with reasoning time, and parallel agent effort with elapsed wall-clock time.
7. Human interventions were counted as raw message tallies without differentiating productive design guidance from avoidable agent errors, without filtering automated bot messages, and without verifying human communication channel coverage.
8. Local telemetry in ephemeral Scratch directories was rotated out, making retrospective multi-week audit studies unreproducible.

## User Persona

- **Primary Persona**: Engineering Operator / Platform Tech Lead.
- **Goal**: Maintain high-throughput delivery velocity across all repositories, identify genuine operational bottlenecks (such as review pickup delays or long-running CI queues), immediately spot any PR that has an executable, authorized next step without an active worker, and accurately differentiate productive human review from avoidable agent errors.

---

## Before: Disconnected Reports and Conflated Dwell vs. Idle

Before this dashboard:
- The operator had to run manual shell scripts or grep through scratch directories to understand delivery throughput and cycle times.
- Stored reports listed gross PR lead times (from `createdAt` to `mergedAt`) that buried sprint execution speed under days of parked draft status. For example, a 95-file refactor that took 1 hour of active execution appeared as taking 72 hours because the PR was opened early as a draft design RFC.
- If an agent exited without advancing a PR, the operator had no centralized view showing whether the PR was blocked by an external dependency, waiting on human review, or stalled with an executable next step.
- Titles carried legacy prefixes like `[fa]` or `[rv]`, which revealed a stage category but gave no hint whether an agent was actively fixing a test, waiting on remote CI, or blocked by a missing credential.
- Elapsed time minus active time was carelessly branded as "wasted time," ignoring necessary CI wait times, human reflection, and unobserved periods. Parallel subagents led to confused metrics where agent hours were added directly to wall-clock hours.
- Human messages were counted indiscriminately: an operator sending three short messages to clarify an ambiguous spec was logged as three agent failures, while automated bot pings and resume watchdogs were counted as human interventions.
- Handoff delays were either unmonitored or calculated by ad-hoc scripts that combined review request timestamps from one attempt with review start timestamps from a later retry attempt.
- Unobserved telemetry intervals were frequently reported as `0s` idle, falsely implying continuous execution monitoring where observation coverage was actually missing.
- When local host scratch space was cleaned, the raw logs disappeared, preventing any reproducible historical re-audit.

---

## After: Single Private GitHub Markdown Dashboard

After implementing the PRW Metrics Dashboard:
- The operator opens a single, private GitHub Markdown document at `dashboards/prw/README.md` (rendered directly by GitHub's authenticated interface in the private `roadmap` repository `<org>/roadmap`).
- The dashboard is automatically refreshed every four hours by a lightweight local scheduler, with UTC timestamps and explicit data freshness indicators.
- The operator can immediately:
  1. **Compare Repositories Across Rolling Windows**: Inspect throughput, median, and p75 creation-to-merge durations across two equal, rolling seven-day windows (`W1` preceding 7 days vs. `W2` recent 7 days), with historical backlog PRs (>7 days old) partitioned so long-parked branches do not distort recent sprint performance.
  2. **Inspect Stage Dwell Separately from Agent Idle**: Clearly view the elapsed time PRs spend in each stage (Stages 0 through 5), explicitly labeled as elapsed stage duration rather than agent idleness.
  3. **Read Operational Status at a Glance**: Scan PR titles formatted as `[status][short detail]` (e.g. `[working][fixing review]`, `[waiting][CI]`, `[queued][source review]`, `[ready][needs approval]`, `[blocked][user pause]`), knowing immediately whether an agent is active, waiting, or paused, completely decoupled from lifecycle stage progression.
  4. **Evaluate Strict Time Semantics and Effort**:
     - *Observed Operation Elapsed*: Start-to-end duration for CLI/model operations including queue and I/O.
     - *Observed Active Wall Time*: True interval union of substantive agent execution on the PR.
     - *Agent Effort*: Cumulative sum of parallel worker execution, never confused with wall time.
     - *Non-Wasted Residual*: Residual duration (`elapsed - active`) is explicitly acknowledged as containing legitimate waits, human reflection, and unobserved periods, never speculatively branded as waste.
  5. **Audit Human Interactions and Episode Quality**:
     - *Deduplicated Episodes*: Grouping raw follow-up messages into distinct episodes with source message IDs.
     - *Rigorous Bot Exclusion*: Filtering out background watchdogs, agents, and automated prompts.
     - *Four Semantic Categories*: Differentiating `good` (value-adding review/guidance) from `bad` (avoidable agent misses), `mixed`, and `unknown`, verified via model/human rationales rather than naive regex rules.
     - *Channel Coverage & Unassigned Preservation*: Tracking channel audit state (e.g. Dot history) and preserving task-level unassigned episodes without forcing them into PR metrics.
  6. **Track Granular Handoff Waiting Intervals**: Review concrete, per-attempt handoff intervals (Evidence Ready to Review Dispatch, Review Request to Actual Reviewer Start, Review Return to Next Substantive Action, and Final Ready / Authority to Merge), where unavailable or unobserved fields are strictly reported as `UNKNOWN` rather than zero.
  7. **Act on the Open PR Attention Table**: Review all currently open PRs sorted by actionable need, directly seeing:
     - PR link, operational status title, and candidate HEAD SHA.
     - Earliest unmet required obligation (from the PR's unified Review Ledger).
     - Concrete next action and accountable owner.
     - Active job handle and wake condition (or explicit hold reason).
     - Elapsed waiting duration and direct links to attempt receipts.
  8. **Reconstruct Historical Studies Deterministically**: Query retained private telemetry under `dashboards/prw/telemetry/` in `<org>/roadmap` to reproduce multi-week audit studies even after host Scratch directories are cleared.
  9. **Observe Explicit Status and Data Quality States**:
     - `FRESH`: Dashboard refreshed within the standard 4-hour schedule.
     - `STALE`: Prior collection snapshot cleanly preserved when collection was delayed (e.g. machine sleep or offline period), with the last successful collection timestamp prominently shown.
     - `PARTIAL_FAILURE`: An individual API query or repository failed, cleanly reporting the partial failure while preserving other repository metrics without inventing zero counts.
     - `EMPTY`: Cohort or window with zero events, correctly reported as empty.
     - `UNKNOWN`: Missing telemetry or unobserved intervals reported as `UNKNOWN` (`telemetry coverage 0%`) rather than false idle accusations.
     - `CONFLICT`: Out-of-order or contradictory stage timestamps surfaced explicitly with a conflict warning.

---

## Key Scenarios

### Scenario 1: Morning Operational Triage
The operator opens `dashboards/prw/README.md` to conduct morning triage and scans the **Open PR Attention Table**:
- PR #742 has title `[working][fixing review] Correct wiki path`, marked `stage:3-evidence-review`, with `next_action: Reviewer Seat 2 dispatch`, `owner: subagent-lane-b`, and `waiting_duration: 12m`. The operator sees immediately that it is actively executing.
- PR #562 has title `[waiting][CI] Upgrade jest runner`, marked `stage:4-ci-undraft`, with `next_action: Re-run Jest test suite`, `owner: lane-a`, and `waiting_duration: 18m`. The operator knows it is waiting on a remote GitHub Action run, not stalled.
- PR #11205 has title `[ready][needs approval] Migrate auth schema`, marked `stage:5-final-approval`, with `next_action: Awaiting user approval`, `owner: driver`, `status: HOLD:OPERATOR`, and `waiting_duration: 1h 45m`. The operator sees it is ready for merge authority review.
- PR #105 has title `[blocked][user pause] Claude API upgrade`, marked `stage:1-coding`, but has `blocker: Quota exhausted on Claude API`, `owner: unassigned`, `waiting_duration: 4h 15m`. The operator immediately recognizes that this PR has a genuine blocker requiring operator credit refresh, and resolves it without reading full transcripts.

### Scenario 2: Sprint Velocity and Bottleneck Analysis
The operator reviews the **Repository Comparison** and **Handoff Delays** sections:
- In `<org>/frontend-repo`, `W2` median creation-to-merge dropped from 12.7h to 6.2h, while `W1` vs `W2` throughput remained steady.
- In `<org>/skills-repo`, the median handoff delay from `review_returned` to `next_action` is 2m, proving rapid driver response after reviewer return.
- However, Reviewer Pickup Delay shows `35m` across 3 attempts on macOS due to local tool wrappers, while Linux runs show `< 1s`. The operator uses this evidence to route static reviews to Linux workers.

### Scenario 3: Respecting Parked and Unobserved States
A feature PR was opened as a draft 10 days ago while awaiting UX feedback:
- The dashboard classifies it under the `Backlog / Parked (> 7d)` partition.
- Its stage dwell is reported as `240h` in Stage 0, clearly labeled as elapsed calendar dwell.
- The Eligible Unattended Interval is reported as `UNKNOWN (telemetry coverage 0%)` because no active worker heartbeat telemetry was recorded during the parked period, preventing false accusations of workflow neglect.

### Scenario 4: Offline and Rate-Limit Resilience
During an overnight scheduled run at `04:17 UTC`, the host laptop was asleep:
- Upon waking at `07:30 UTC`, the next scheduled execution runs at `08:17 UTC`.
- In the meantime, opening the dashboard displays `Status: STALE`, showing `Data Cutoff (UTC): 2026-11-07 00:17:00Z` and `Last Successful Collection: 2026-11-07 00:17:00Z`.
- No half-empty commits or destroyed history occur; the previous valid metrics remain completely readable.

### Scenario 5: Human Interaction Triage and Quality Calibration
The operator inspects the **Human Interaction & Episode Breakdown** section:
- Across 34 raw inbound human messages, the collector identified 20 deduplicated intervention episodes.
- 14 episodes (70%) are categorized as `good` (value-adding domain review, such as the operator watching video evidence and refining a gameplay spec, or granting an authorized merge approval).
- 4 episodes (20%) are categorized as `bad` (avoidable agent errors, such as an agent ignoring an established repository rule or halting when an executable authorized step remained).
- 2 episodes are categorized as `mixed` (combining architectural approval with a prompt to fix a regression).
- 2 task-level episodes could not be attributed to a single PR and are preserved honestly as `pr_attribution: "unassigned"`.
- The dashboard explicitly notes that "zero-touch" is NOT claimed because the Dot communication channel is untested.
- Two independent reviewers calibrated their category assignments on a shared sample, ensuring stable, reproducible classification.

### Scenario 6: Deterministic Audit Study from Retained Private Telemetry
The platform tech lead conducts a 14-day delivery retrospective:
- Although local developer machines rotated their `/tmp` and Scratch workspaces over the past two weeks, all underlying observational telemetry JSON files and attempt receipts were committed under `dashboards/prw/telemetry/` in `<org>/roadmap`.
- The tech lead executes a local replay script pointing to `dashboards/prw/telemetry/2026-10-24_2026-11-07/`.
- The script deterministically reproduces the exact dashboard tables, median cycle times, and handoff delay distributions, verifying that the published metrics are 100% auditable and reproducible.

---

## Privacy and Portability Invariants

- **No Personal Identifiers**: The dashboard source code and documentation contain zero machine usernames, personal directory paths (`$HOME` or `@HOME@` placeholders only), private email addresses, tailnet IPs, or personal hostnames.
- **No Embedded Credentials**: Authentication relies on existing ambient CLI access; no GitHub tokens or secrets are stored in plist templates or rendered Markdown.
- **Private Roadmap Target**: The rendered dashboard and underlying telemetry are published strictly to the private `roadmap` repository (`dashboards/prw/README.md` and `dashboards/prw/telemetry/`) via scoped fast-forward commits, with zero public exposure.
