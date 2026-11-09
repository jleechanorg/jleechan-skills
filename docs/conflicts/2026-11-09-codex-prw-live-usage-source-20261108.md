# Merge resolution: PRW query metrics - 2026-11-09

Merged query metrics commit 2553daca8ec3acb256b5d5281b032d6b15915e02 into codex/prw-live-usage-source-20261108.

## `scripts/prw_metrics.py`

- Hunk 1 (SUMMARY_SCHEMA): **Combined** - retained native source coverage fields and added the query branch's per-PR cost distribution projection.
- Hunk 2 (handoff renderer): **Combined** - measured handoffs keep sample counts, coverage, median, p75, p50, p90, and p99. If every handoff has zero observations, the dashboard reports NOT COLLECTED instead of rendering placeholder zero rows; Stage Dwell remains separate.
- Hunk 3 (usage summary renderer): **Combined** - retained the native source acquisition line and added the query branch's explicitly attributed cost percentiles. Percentiles remain UNKNOWN when no priced per-PR sample exists.

## Tests

- Before: native usage/steering suite on eeadc62 - `python3 -m unittest tests.test_prw_metrics_native_human_steering tests.test_native_usage_collector` -> 17 passed.
- Before: query branch validation on 2553daca - DuckDB query suite -> 8 passed, as recorded by the merge owner.
- After: 70 passed across `test_prw_metrics_queries`, `test_prw_metrics_native_human_steering`, `test_native_usage_collector`, `test_prw_metrics_usage_cli`, `test_prw_metrics_human_truth`, `TestCLIEnvironmentDefaults`, and `TestPublisher.test_failed_collection_retains_prior_and_does_not_commit`, using the task-scoped DuckDB environment. The host-specific interpreter path is omitted for portability; no alternate command is asserted here.
- After: `python3 -m py_compile scripts/prw_metrics.py scripts/prw_metrics_queries.py scripts/native_usage_collector.py` -> passed.
- After: `git diff --cached --check` -> passed.
