"""Failed refreshes never mint a cutoff; both attention tables show the unmet obligation (PR #742 r8)."""

import json
import os
import tempfile
import unittest
from datetime import datetime, timezone

from scripts.prw_metrics import Collector, DashboardRenderer, MetricsAggregator, format_iso_utc

REPO = "o/r"
NOW = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)
PRIOR = "2026-11-07T08:00:00Z"
CACHED = {"number": 1, "repo": REPO, "state": "MERGED",
          "createdAt": "2026-11-05T00:00:00Z", "mergedAt": "2026-11-06T00:00:00Z"}


def _boom(repo, page, per_page):
    raise RuntimeError("api down")


class TestFailedRefreshCutoff(unittest.TestCase):
    def _state(self, manifest=None):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        with open(os.path.join(d.name, "enriched_prs.json"), "w") as f:
            json.dump([CACHED], f)
        if manifest is not None:
            with open(os.path.join(d.name, "source_manifest.json"), "w") as f:
                json.dump(manifest, f)
        return d.name

    def _collect(self, state, **kw):
        return Collector(repos=[REPO], cutoff_dt=NOW).collect_all(input_dir=state, **kw)

    def test_failed_refresh_without_prior_cutoff_stays_unknown(self):
        res = self._collect(self._state(), fetch_page_fn=_boom)
        src = res["sources"][REPO]
        self.assertEqual(src["status"], "PARTIAL_FAILURE")
        self.assertIsNone(src["cutoff"])
        summary = MetricsAggregator(cutoff_dt=NOW).aggregate_full_dataset(
            prs=res["prs"], sources=res["sources"], now_dt=NOW
        )
        self.assertEqual(summary["data_through"], "UNKNOWN")

    def test_failed_refresh_keeps_verified_prior_cutoff(self):
        state = self._state({REPO: {"status": "COMPLETE", "cutoff": PRIOR}})
        src = self._collect(state, fetch_page_fn=_boom)["sources"][REPO]
        self.assertEqual((src["status"], src["cutoff"]), ("PARTIAL_FAILURE", PRIOR))

    def test_failed_refresh_without_cache_has_no_cutoff(self):
        res = Collector(repos=[REPO], cutoff_dt=NOW).collect_all(fetch_page_fn=_boom)
        src = res["sources"][REPO]
        self.assertEqual(src["status"], "FAILED")
        self.assertIsNone(src["cutoff"])

    def test_timeline_failure_after_live_success_has_no_minted_cutoff(self):
        def fetch(repo, page, per_page):
            return [{"number": 2, "state": "open", "head": {"sha": "s2"}, "repo": repo}] if page == 1 else []

        def bad_timeline(repo, number):
            raise RuntimeError("timeline down")

        res = Collector(repos=[REPO], cutoff_dt=NOW).collect_all(fetch_page_fn=fetch, fetch_timeline_fn=bad_timeline)
        src = res["sources"][REPO]
        self.assertEqual(src["status"], "PARTIAL_FAILURE")
        self.assertIsNone(src["cutoff"])

    def test_live_success_stamps_collection_time(self):
        def fetch(repo, page, per_page):
            return [{"number": 2, "state": "open", "head": {"sha": "s2"}, "repo": repo}] if page == 1 else []

        res = Collector(repos=[REPO], cutoff_dt=NOW).collect_all(fetch_page_fn=fetch, fetch_timeline_fn=lambda r, n: [])
        self.assertEqual(res["sources"][REPO]["cutoff"], format_iso_utc(NOW))

    def test_no_source_provenance_does_not_default_to_collection_time(self):
        summary = MetricsAggregator(cutoff_dt=NOW).aggregate_full_dataset(prs=[CACHED], now_dt=NOW)
        self.assertEqual(summary["data_through"], "UNKNOWN")
        self.assertNotEqual(summary["status"], "FRESH")


BODY = """| Obligation | Required by | Status | Receipt | Candidate applicability |
|---|---|---|---|---|
| Source review quorum | Route | PASS | https://example.com/q | Current |
| Evidence review (/er) | Route | PENDING | none | Current |
"""


class TestAttentionTables(unittest.TestCase):
    def _render(self, observed):
        raw = {
            "number": 9, "state": "open", "title": "[waiting][CI] x", "html_url": f"https://github.com/{REPO}/pull/9",
            "created_at": "2026-11-05T00:00:00Z", "updated_at": "2026-11-06T00:00:00Z",
            "head": {"sha": "a1" * 20}, "body": BODY,
        }
        if observed:
            raw.update(
                has_continuous_observation=True, telemetry_coverage=1.0,
                eligible_intervals=[["2026-11-05T00:00:00Z", "2026-11-05T05:00:00Z"]],
            )
        pr = Collector().normalize_pr_record(raw, default_repo=REPO)
        summary = MetricsAggregator(cutoff_dt=NOW).aggregate_full_dataset(prs=[pr], now_dt=NOW)
        return summary, DashboardRenderer().render(summary)

    def test_known_duration_table_shows_unmet_obligation(self):
        summary, md = self._render(observed=True)
        self.assertEqual(summary["open_prs_known_idle"][0]["earliest_unmet_obligation"], "Evidence review (/er)")
        header = next(line for line in md.splitlines() if "Actionable Next Step" in line)
        self.assertIn("Earliest Unmet Obligation", header)
        row = next(line for line in md.splitlines() if line.startswith("| [https://github.com/o/r/pull/9]") and "**" in line)
        self.assertIn("Evidence review (/er)", row)
        self.assertEqual(header.count("|"), row.count("|"))

    def test_unknown_eligibility_table_still_shows_it(self):
        summary, md = self._render(observed=False)
        self.assertEqual(summary["open_prs_unknown_idle"][0]["earliest_unmet_obligation"], "Evidence review (/er)")
        self.assertIn("Evidence review (/er)", md)


if __name__ == "__main__":
    unittest.main()
