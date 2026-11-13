# Specification: PRW metrics web dashboard snapshot and static page

## 1. Outcome

The PRW metrics job can write a compact, versioned JSON snapshot of the per-PR and cohort figures it already computes, and a static page renders that snapshot with filters, charts, a PR table, a detail panel and CSV export.

1. `scripts/prw_metrics_web_export.py` builds the snapshot from structured inputs only: the renderer summary, the DuckDB query result and the cached PR list.
2. `scripts/prw_metrics.py --dashboard-json <path>` writes it after a run that computed query metrics. Without the option, behaviour is unchanged.
3. `web/prw-dashboard/` is a dependency-free page that fetches `dashboard.json` from its own directory and derives every view from one filtered slice.

## 2. Non-goals

- Hosting the page, choosing an audience, or deciding where a real snapshot may be published.
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
