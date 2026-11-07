# Specification: PRW Metrics Dashboard

## 1. Outcome

A lightweight, automated metrics collector and renderer that publishes a single, private GitHub Markdown dashboard at `dashboards/prw/README.md` in the private `roadmap` repository. The dashboard refreshes every four hours via macOS `launchd`, providing the operator with transparent visibility into:
1. Multi-repository delivery velocity and cycle times across rolling seven-day windows (`W1` preceding vs. `W2` recent).
2. Labeled stage dwell time across Stages 0 through 5, explicitly separated from agent idle time.
3. Granular, per-attempt handoff waiting delays derived from verified receipt and timeline events.
4. An actionable Open PR Attention Table that connects open PRs to their earliest unmet required obligations, accountable owners, active job handles, and receipt links.

---

## 2. Non-Goals

1. **No Automatic State Changes**: The dashboard is strictly observational. It performs zero PR status mutations, label synchronizations, automatic approvals, merges, nudges, or comments.
2. **No Public Site or GitHub Pages**: No public dashboard, GitHub Pages deployment, or external web service. All rendering uses GitHub's native Markdown viewer inside the private `roadmap` repo.
3. **No Heavy Compute or Paid Models**: No LLM invocations, full test suite executions, or heavy browser automation inside the scheduled collector job.
4. **No Fabricated Telemetry**: Unobserved intervals and missing telemetry are never estimated or reported as `0s`; they are strictly reported as `UNKNOWN` (`telemetry coverage 0%`).
5. **No Credential Storage**: No secrets, personal tokens, or API keys are embedded in plist templates, scripts, or tracked repository files.

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

### 3.2 Handoff & Idle Arithmetic
- **Per-Attempt Timestamps**: Timestamp subtraction for review handoff intervals (`review_requested_at` to `actual_review_started_at`) must be computed strictly within the same review attempt. If multiple attempts occurred, each attempt is recorded separately; timestamps from different attempts are never combined.
- **Honest Missing Data**: If owner, job, or hold observation is absent during an open interval, `eligible_unattended_interval` must evaluate to `UNKNOWN`, never `0s`.
- **Pre-Change Window Independence**: Pre-change window cutoffs must be presented as historical baselines, not post-change causal improvements.

### 3.3 Dashboard Health States
The dashboard must cleanly surface operational states in the header and tables:
- `FRESH`: Refreshed within the last 4-hour cycle.
- `STALE`: Prior collection preserved when a refresh was missed (e.g. machine offline/sleep), prominently displaying the last successful collection timestamp.
- `PARTIAL_FAILURE`: An individual repository or query shard failed; the dashboard renders available data, notes the partial error, and preserves the prior cutoff without fabricating zeroes.
- `EMPTY`: Cohort or window containing zero events.
- `UNKNOWN`: Missing observational telemetry or unrecorded fields.
- `CONFLICT`: Contradictory timeline events or out-of-order stage transitions.

### 3.4 Scheduling & Publication
- **Calendar Intervals**: Scheduled via `launchd` in 4-hour calendar slots at `00:17`, `04:17`, `08:17`, `12:17`, `16:17`, `20:17` local time, writing all timestamps in UTC.
- **Scoped Publication**: Publishes strictly to `dashboards/prw/README.md` in private `roadmap` using standard fast-forward git pushes with remote-head reconciliation. Never uses force-push.
- **Atomic Failure Handling**: On API or script failure, the existing dashboard is preserved; no partial or empty Markdown commit is published.

---

## 4. User Stories

See [User Story: PRW Metrics Dashboard](../user-stories/prw-metrics-dashboard.md) for full before/after narratives and operator workflows across:
- Scenario 1: Morning Operational Triage.
- Scenario 2: Sprint Velocity and Bottleneck Analysis.
- Scenario 3: Respecting Parked and Unobserved States.
- Scenario 4: Offline and Rate-Limit Resilience.

---

## 5. Proof Plan

### 5.1 Automated TDD Unit Tests
1. **`tests/test_prw_metrics.py`**:
   - Pagination handling across $> 100$ items.
   - Deduplication of overlapping search results across shards.
   - Half-open window partitioning (`W1` vs. `W2`).
   - Timestamp subtraction arithmetic within single attempts.
   - Assertion that missing telemetry outputs `UNKNOWN` instead of `0s`.
   - Markdown rendering across `FRESH`, `STALE`, `PARTIAL_FAILURE`, and `EMPTY` states.
2. **`tests/test_prw_metrics_scheduler.py`**:
   - Verification of `@HOME@` placeholder replacement in the launchd plist template.
   - Validation that the six `:17` calendar slots are present.
   - Verification that no tokens or private credentials exist in the template or wrapper.
   - Validation of temporary rendered plist via `plutil -lint`.

### 5.2 Real Operational & Visual Verification
1. **Launchd Job Verification**: Execute `launchctl print gui/$(id -u)/com.jleechan.prw-metrics` to confirm job registration, execute one manual test run, and verify generated output.
2. **Private Publication Verification**: Verify clean push and readback of `dashboards/prw/README.md` on the private `roadmap` repository.
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

## 3. Handoff Delays (Granular Attempt Measurements)

| Metric | Sample (n) | Median Delay | p75 Delay | Telemetry Coverage | Status |
|---|:---:|:---:|:---:|:---:|:---:|
| **Evidence Ready -> Review Dispatch** | 42 | 1m 15s | 2m 45s | 100% | FRESH |
| **Review Request -> Actual Reviewer Start** | 42 | < 1s (Linux) | 35m (Mac rtk) | 95.2% | FRESH |
| **Review Return -> Next Substantive Action** | 38 | 2m 10s | 5m 30s | 92.1% | FRESH |
| **Final Ready + Authority -> Executed Merge** | 36 | 1m 45s | 3m 20s | 100% | FRESH |

---

## 4. Open PR Attention Table

| PR | Repo | Candidate SHA | Earliest Unmet Obligation | Next Action | Owner | Status / Hold | Waiting Duration | Receipts |
|---|---|:---:|---|---|---|:---:|:---:|:---:|
| **#742** | skills-repo | `a1b2c3d` | Source Review Quorum | Dispatch Seat 2 review | lane-b | ACTIVE | 12m | [Receipt](receipts/742.md) |
| **#562** | frontend-repo | `d4e5f6a` | CI and Undraft | Re-run Jest test suite | lane-a | CI_WAIT | 18m | [Receipt](receipts/562.md) |
| **#11205**| backend-repo | `b7c8d9e` | Merge Authority | Awaiting user approval | driver | HOLD:OPERATOR | 1h 45m | [Receipt](receipts/11205.md) |
| **#738** | skills-repo | `e9f0a1b` | UNKNOWN | Design consensus | none | PARKED | 72h | UNKNOWN (0% coverage) |

---

## 5. Notes & Data Definitions
- **Stage Dwell**: Calendar duration between observed stage labels; does NOT imply agent neglect.
- **Eligible Idle**: Derived only when an authorized next action was executable without an active worker; unobserved periods evaluate to `UNKNOWN`.
- **Backlog**: PRs merged $>7$ days after creation.
```

---

## 7. Risks & Mitigations

| Risk | Severity | Mitigation |
|---|:---:|---|
| **Accidental Credential Leakage** | Critical | Sourcing profile and ambient `gh` CLI credentials only. Zero tokens, passwords, or personal hostnames in plists, scripts, or tracked Markdown files. |
| **Merge / Git Publication Conflict** | Medium | The publisher fetches the remote `roadmap` branch, attempts a clean fast-forward rebase, reconciles only `dashboards/prw/README.md`, and fails safely without force-pushing. |
| **Misleading Idle Accusations** | High | Clear visual and lexical separation between stage dwell (elapsed calendar time) and eligible unattended delay. Unobserved telemetry is strictly displayed as `UNKNOWN (telemetry coverage 0%)`. |
| **Host Sleep / Network Interruption** | Low | If the Mac is asleep or offline during a scheduled slot, the job runs on next wake; the previous dashboard remains intact and is explicitly stamped with its prior cutoff and `STALE` status. |
