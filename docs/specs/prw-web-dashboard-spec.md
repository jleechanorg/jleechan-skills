# Specification: PRW metrics web dashboard snapshot and static page

## 1. Outcome

The PRW metrics job can write a compact, versioned JSON snapshot of the per-PR and cohort figures it already computes, and a static page renders that snapshot with filters, charts, a PR table, a detail panel and CSV export.

1. `scripts/prw_metrics_web_export.py` builds the snapshot from structured inputs only: the renderer summary, the DuckDB query result and the cached PR list.
2. `scripts/prw_metrics.py --dashboard-json <path>` writes it after a run that computed query metrics. Without the option, behaviour is unchanged.
3. `web/prw-dashboard/` is a dependency-free page that fetches `dashboard.json` from its own directory and derives every view from one filtered slice.
4. The page reports the per-PR verified human prompt tail for the filtered slice: PRs above 4 prompts, the excess over 4, PRs at 14 or more, and nearest-rank p50/p90/p99, with attribution filters for the first two groups. The page computes these from the PR rows; the export adds no summary of its own. The population is PRs with at least one verified prompt: the collector records no count for a PR with none, so those stay unknown. With fewer than 3 such PRs every figure is withheld.
   Each PR row carries `human.mid_pr`: confirmed verified human messages strictly after the first recorded stage and before the first final stage (else `mergedAt` when on or before the snapshot cutoff), compared at full timestamp precision. Confirmed means a direct binding or reviewed context with EXPLICIT or REVIEWED_CONTEXT confidence; branch matches and low-confidence context are not confirmed. It is null (unknown, never 0) when the PR has any unconfirmed verified message (`unconfirmed_verified_messages`), when the collector's history window starts after the first recorded stage, or when the interval has no valid start or end.
   When the collector fails it leaves `last_failure.json` (`time_utc`, `exit_status`) beside `dashboard.json` and removes it on success. The page fetches it optionally (404 or a parse error means no banner) and shows a failure banner when `time_utc` is newer than the snapshot `generated_at`.
   Decision: tail counts stay withheld below the 3-observation floor (tile, table and CSV); the >4 count includes the initial request, low-confidence PR associations are counted unqualified, and period filters use lifetime overlap with whole-snapshot totals. The launchd job serves `~/.local/share/prw-dashboard/current`, which returns 404 until the first snapshot is populated.
5. When a summary supplies `annotation_freshness` (`status`, `reviewed_through`), the snapshot passes it through the same summary projection as every other field; otherwise it is `UNKNOWN`. No collector in this repository writes the field yet.
6. `launchd/org.prw.dashboard.plist.template` is an optional template that serves a local copy of the page on the loopback interface only. Nothing in this change installs it.

## 2. Non-goals

- Choosing an audience, exposing the page beyond the local machine, or deciding where a real snapshot may be published.
- Wiring `--dashboard-json` into a scheduled job or installing anything on a host.
- New measurements: the export only projects values the job already computes.
- Committing any real snapshot data.

## 3. Acceptance criteria

1. An unobserved value is `null` in the snapshot and shown as unavailable on the page, never as zero; each PR carries the status that explains it.
2. Prompt text, PR bodies, reasoning and credentials present in inputs do not appear in the snapshot, the page or its CSV exports.
3. `--dashboard-json` without query metrics warns and leaves any previous snapshot in place; the snapshot is written atomically.
4. Percentiles the page computes for a filtered slice equal the job's DuckDB cohort values for the same population (nearest-rank).
5. Filters (period, repository, state, attribution, size, search) narrow the table, cards and charts consistently; a row opens a detail panel that Escape closes.
6. Count-chart axes label every gridline with a distinct, evenly spaced whole number at its true height.
7. The page makes no request outside its own origin; `?data=` accepts only a bare `*.json` file name; a missing snapshot shows an error banner; a narrow phone viewport has no horizontal page overflow.

## 4. User stories

- As someone reviewing PR-workflow cost and timing, I open one page, filter by period, repository, state and attribution, and see per-PR figures and cohort percentiles that match what the metrics job reports, with unobserved values shown as missing.
- As the operator of the metrics job, I add one flag to also produce the page's data file, and nothing changes when I leave it off.

## 5. Proof plan

- Unit: `tests/test_prw_metrics_web_export.py` (export projection, null handling, marker exclusion, atomic write) and `web/prw-dashboard/stats.test.cjs` under Node (quantiles, filters, aggregation, axis ticks, CSV).
- Real caller: run `scripts/prw_metrics.py --offline --query-metrics --dashboard-json` on synthetic inputs (two `acme/*` repositories, nine PRs, direct usage attributions, marker strings in PR bodies and prompts).
- Browser: isolated headless Chromium journey over that generated snapshot, checking criteria 4-7 and capturing desktop, filtered, detail-panel, period, phone and error-state screenshots.
- Full repository suite at base and head; CI on the PR head.

## 6. Mock

Exempt: the page is new and has no prior design. The rendered screenshots from the proof plan serve as the reviewable appearance record.

## 7. Risks

- A real snapshot names repositories, PR titles and URLs; publishing one is a separate decision.
- Client-side percentiles are checked against the job for the fixture cohorts, not across many real snapshots.
- Per-PR cost needs `--scenario-catalog`; without it the page shows cost as unavailable.
