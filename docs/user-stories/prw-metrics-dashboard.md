# User Story: PRW Metrics Dashboard

## Problem Statement

When operating autonomous development workflows across multiple repositories (for example `<org>/skills-repo`, `<org>/frontend-repo`, and `<org>/backend-repo`), the engineering operator faces severe information fragmentation:
1. Operational metrics and attempt receipts are scattered across ad-hoc local files, scratch paths, and disparate GitHub PR timelines.
2. Long-parked PRs (e.g. branches legitimately waiting on multi-day architectural consensus or user feedback) cannot easily be distinguished from abandoned or stalled PRs that have an executable, authorized next action with nobody acting.
3. Prior reports conflated stage label dwell time (elapsed wall-clock time in a stage) with agent idleness, resulting in misleading or unverified idle accusations.
4. Timestamp subtraction often mixed different review attempts or treated unobserved intervals as zero instead of explicitly flagging missing telemetry as unknown.

## User Persona

- **Primary Persona**: Engineering Operator / Platform Tech Lead.
- **Goal**: Maintain high-throughput delivery velocity across all repositories, identify genuine operational bottlenecks (such as review pickup delays or long-running CI queues), and immediately spot any PR that has an executable, authorized next step without an active worker.

---

## Before: Disconnected Reports and Conflated Dwell vs. Idle

Before this dashboard:
- The operator had to run manual shell scripts or grep through scratch directories to understand delivery throughput and cycle times.
- Stored reports listed gross PR lead times (from `createdAt` to `mergedAt`) that buried sprint execution speed under days of parked draft status. For example, a 95-file refactor that took 1 hour of active execution appeared as taking 72 hours because the PR was opened early as a draft design RFC.
- If an agent exited without advancing a PR, the operator had no centralized view showing whether the PR was blocked by an external dependency, waiting on human review, or stalled with an executable next step.
- Handoff delays were either unmonitored or calculated by ad-hoc scripts that combined review request timestamps from one attempt with review start timestamps from a later retry attempt.
- Unobserved telemetry intervals were frequently reported as `0s` idle, falsely implying continuous execution monitoring where observation coverage was actually missing.

---

## After: Single Private GitHub Markdown Dashboard

After implementing the PRW Metrics Dashboard:
- The operator opens a single, private GitHub Markdown document at `dashboards/prw/README.md` (rendered directly by GitHub's authenticated interface in the private `roadmap` repository).
- The dashboard is automatically refreshed every four hours by a lightweight local scheduler, with UTC timestamps and explicit data freshness indicators.
- The operator can immediately:
  1. **Compare Repositories Across Rolling Windows**: Inspect throughput, median, and p75 creation-to-merge durations across two equal, rolling seven-day windows (`W1` preceding 7 days vs. `W2` recent 7 days), with historical backlog PRs (>7 days old) partitioned so long-parked branches do not distort recent sprint performance.
  2. **Inspect Stage Dwell Separately from Agent Idle**: Clearly view the elapsed time PRs spend in each stage (Stages 0 through 5), explicitly labeled as elapsed stage duration rather than agent idleness.
  3. **Track Granular Handoff Waiting Intervals**: Review concrete, per-attempt handoff intervals (Evidence Ready to Review Dispatch, Review Request to Actual Reviewer Start, Review Return to Next Substantive Action, and Final Ready / Authority to Merge), where unavailable or unobserved fields are strictly reported as `UNKNOWN` rather than zero.
  4. **Act on the Open PR Attention Table**: Review all currently open PRs sorted by actionable need, directly seeing:
     - PR link and candidate HEAD SHA.
     - Earliest unmet required obligation (from the PR's unified Review Ledger).
     - Concrete next action and accountable owner.
     - Active job handle and wake condition (or explicit hold reason).
     - Elapsed waiting duration and direct links to attempt receipts.
  5. **Observe Explicit Status and Data Quality States**:
     - `FRESH`: Dashboard refreshed within the standard 4-hour schedule.
     - `STALE`: Prior collection snapshot cleanly preserved when collection was delayed (e.g. machine sleep or offline period), with the last successful collection timestamp prominently shown.
     - `PARTIAL_FAILURE`: An individual API query or repository failed, cleanly reporting the partial failure while preserving other repository metrics without inventing zero counts.
     - `EMPTY`: Cohort or window with zero events, correctly reported as empty.
     - `UNKNOWN`: Missing telemetry or unobserved intervals reported as `UNKNOWN` (`telemetry coverage 0%`) rather than false idle accusations.
     - `CONFLICT`: Out-of-order or contradictory stage timestamps surfaced explicitly with a conflict warning.

---

## Key Scenarios

### Scenario 1: Morning Operational Triage
The operator opens `dashboards/prw/README.md` to conduct the morning triage. They scan the **Open PR Attention Table**:
- PR #102 is marked `stage:3-evidence-review`, with `next_action: Reviewer Seat 1 dispatch`, `owner: subagent-lane-b`, and `waiting_duration: 12m`. The operator sees it is actively running.
- PR #105 is marked `stage:1-coding`, but has `blocker: Quota exhausted on Claude API`, `owner: unassigned`, `waiting_duration: 4h 15m`. The operator immediately recognizes that this PR has a genuine blocker requiring operator credit refresh, and resolves it without reading full transcripts.

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

---

## Privacy and Portability Invariants

- **No Personal Identifiers**: The dashboard source code and documentation contain zero machine usernames, personal directory paths (`$HOME` or `@HOME@` placeholders only), private email addresses, tailnet IPs, or personal hostnames.
- **No Embedded Credentials**: Authentication relies on existing ambient CLI access; no GitHub tokens or secrets are stored in plist templates or rendered Markdown.
- **Private Roadmap Target**: The rendered dashboard is published strictly to the private `roadmap` repository (`dashboards/prw/README.md`) via scoped fast-forward commits, with zero public exposure.
