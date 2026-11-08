"""Canonical receipts, equal-duration attempts and PR-body attention fields (PR #742 round 3)."""

import json
import os
import tempfile
import unittest
from datetime import datetime, timezone

from scripts.prw_metrics import Collector, DashboardRenderer, MetricsAggregator, parse_pr_body_record

REPO = "o/r"
HEAD = "a" * 40
OLD = "b" * 40


def _round(n, sha, base_hour):
    def ts(h, m=0):
        return f"2026-11-05T{base_hour + h:02d}:{m:02d}:00Z"

    return {
        "round": n,
        "candidate_sha": sha,
        "evidence_ready_at": ts(0),
        "review_requested_at": ts(0, 30),
        "actual_review_started_at": ts(1),
        "review_return_at": ts(2),
        "next_substantive_action_started_at": ts(2, 15),
    }


STATS = {
    "endpoint": "FINAL_READY",
    "candidate_sha": HEAD,
    "timestamps": {
        "accepted_at": "2026-11-05T00:00:00Z",
        "merged_at": "2026-11-05T20:00:00Z",
        "review_return_at": None,
    },
    "rounds": [_round(1, OLD, 1), _round(2, HEAD, 8)],
    "model_usage": {"output_tokens": None},
}


class TestCanonicalReceipts(unittest.TestCase):
    PR = {"repo": REPO, "number": 7, "headRefOid": HEAD, "mergedAt": "2026-11-05T20:00:00Z"}

    def _rows(self, stats, prs=None):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "pr7"))
            with open(os.path.join(d, "pr7", "run.stats.json"), "w") as f:
                json.dump(stats, f)
            records = Collector().collect_receipts_from_dir(d)
        data = MetricsAggregator().compute_handoff_breakdown(prs or [dict(self.PR)], handoff_records=records, total_cohort_n=1)
        return {r["name"]: r for r in data}

    def test_rounds_become_per_round_samples(self):
        rows = self._rows(STATS)
        self.assertEqual(rows["evidence_ready -> review_requested"]["sample_n"], 2)
        self.assertEqual(rows["review_requested -> actual_review_started"]["median_sec"], 1800.0)
        self.assertEqual(rows["review_return -> next_substantive_action"]["sample_n"], 2)
        self.assertEqual(rows["task_accepted -> merged"]["median_sec"], 72000.0)
        self.assertEqual(rows["task_accepted -> merged"]["observed_n"], 1)

    def test_null_timestamps_and_unidentified_receipts_yield_nothing(self):
        rows = self._rows(dict(STATS, candidate_sha="c" * 40, rounds=[]))
        self.assertTrue(all(r["status"] == "UNKNOWN" for r in rows.values()))
        stats = json.loads(json.dumps(STATS))
        for rnd in stats["rounds"]:
            rnd["review_requested_at"] = None
        rows = self._rows(stats)
        self.assertEqual(rows["evidence_ready -> review_requested"]["status"], "UNKNOWN")
        self.assertEqual(rows["review_return -> next_substantive_action"]["sample_n"], 2)

    def test_round_without_identity_is_skipped(self):
        stats = json.loads(json.dumps(STATS))
        del stats["rounds"][0]["candidate_sha"]
        del stats["rounds"][1]["round"]
        rows = self._rows(stats)
        self.assertEqual(rows["review_return -> next_substantive_action"]["status"], "UNKNOWN")


class TestEqualDurationAttempts(unittest.TestCase):
    def test_equal_durations_remain_distinct_attempts(self):
        pr = {
            "repo": REPO, "number": 1, "headRefOid": "sha1",
            "evidence_ready_at": "2026-11-05T10:00:00Z", "review_requested_at": "2026-11-05T11:00:00Z",
        }
        records = [
            {
                "name": "evidence_ready -> review_requested", "repo": REPO, "number": 1,
                "candidate_sha": "sha1", "attempt_number": n, "source_receipt": f"r{n}", "duration_sec": dur,
            }
            for n, dur in ((1, 3600.0), (2, 3600.0), (3, 7200.0))
        ]
        data = MetricsAggregator().compute_handoff_breakdown([pr], handoff_records=records, total_cohort_n=1)
        row = next(r for r in data if r["name"] == "evidence_ready -> review_requested")
        self.assertEqual(row["sample_n"], 3)
        self.assertEqual(row["observed_n"], 1)
        self.assertEqual(row["median_sec"], 3600.0)


BODY = """## Review ledger
| Obligation | Required by | Status | Receipt | Candidate applicability |
|---|---|---|---|---|
| Source review quorum | Selected route | PASS | https://example.com/r/quorum | Valid |
| Evidence review (/er) | Selected route | PENDING | <Receipt or exemption> | Unknown |
| Visual approval | Changed claims | N/A | https://example.com/r/visual | Reason |

## Execution
```text
endpoint: FINAL_READY
candidate: {candidate}
next_action: Dispatch evidence review
owner: lane-b
job_handle: job-4711
wake_condition: reviewer response
blocker: <only if no executable authorized action remains>
```
"""


def _live_pr(candidate=HEAD[:7]):
    return {
        "number": 9, "state": "open", "title": "[working][fixing review] x", "html_url": f"https://github.com/{REPO}/pull/9",
        "created_at": "2026-11-05T00:00:00Z", "updated_at": "2026-11-06T00:00:00Z",
        "head": {"sha": HEAD}, "body": BODY.format(candidate=candidate),
    }


class TestBodyAttentionFields(unittest.TestCase):
    def _render(self, raw):
        pr = Collector().normalize_pr_record(raw, default_repo=REPO)
        cutoff = datetime(2026, 11, 7, tzinfo=timezone.utc)
        summary = MetricsAggregator(cutoff_dt=cutoff).aggregate_full_dataset(prs=[pr], now_dt=cutoff)
        return pr, DashboardRenderer().render(summary)

    def test_execution_record_and_ledger_reach_rendered_table(self):
        pr, md = self._render(_live_pr())
        self.assertEqual(pr["owner"], "lane-b")
        self.assertEqual(pr["earliest_unmet_obligation"], "Evidence review (/er)")
        for needle in ("lane-b", "Dispatch evidence review", "job-4711", "reviewer response",
                       "Evidence review (/er)", "https://example.com/r/quorum", "https://example.com/r/visual"):
            self.assertIn(needle, md)

    def test_placeholders_are_not_values(self):
        pr, _ = self._render(_live_pr())
        self.assertIsNone(pr["hold_status"])

    def test_stale_candidate_record_is_ignored(self):
        pr, md = self._render(_live_pr(candidate="deadbee"))
        self.assertIsNone(pr["owner"])
        self.assertIsNone(pr["next_action"])
        self.assertNotIn("job-4711", md)

    def test_top_level_fields_win_over_body(self):
        raw = dict(_live_pr(), owner="explicit-owner")
        self.assertEqual(Collector().normalize_pr_record(raw, default_repo=REPO)["owner"], "explicit-owner")

    def test_no_record_stays_unknown(self):
        self.assertEqual(parse_pr_body_record("plain description", HEAD), {})


if __name__ == "__main__":
    unittest.main()
