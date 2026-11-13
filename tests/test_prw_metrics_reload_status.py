"""Saved source status and failure provenance survive offline reloads (PR #742 round 4, P0-3)."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from scripts.prw_metrics import Collector, DashboardRenderer, MetricsAggregator, format_iso_utc

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = "o/r"
NOW = datetime.now(timezone.utc)
RECENT = format_iso_utc(NOW - timedelta(minutes=5))
PR = {"number": 1, "repo": REPO, "state": "MERGED",
      "createdAt": format_iso_utc(NOW - timedelta(days=2)), "mergedAt": format_iso_utc(NOW - timedelta(days=1))}


class TestReloadKeepsStatus(unittest.TestCase):
    def _scratch(self, sources):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        with open(os.path.join(d.name, "enriched_prs.json"), "w") as f:
            json.dump([PR], f)
        with open(os.path.join(d.name, "source_manifest.json"), "w") as f:
            json.dump(sources, f)
        return d.name

    def _bundle(self, sources):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        with open(os.path.join(d.name, "retained_prs.jsonl"), "w") as f:
            f.write(json.dumps(PR) + "\n")
        with open(os.path.join(d.name, "retained_sources.json"), "w") as f:
            json.dump(sources, f)
        return d.name

    def _collect(self, **kw):
        res = Collector(repos=[REPO], cutoff_dt=NOW).collect_all(offline=True, **kw)
        summary = MetricsAggregator(cutoff_dt=NOW).aggregate_full_dataset(
            prs=res["prs"], sources=res["sources"], now_dt=NOW
        )
        if res["status"] in ("FAILED", "PARTIAL_FAILURE"):
            summary["status"] = res["status"]
        return res, summary, DashboardRenderer().render(summary)

    def _check(self, loader, status, expected_overall):
        sources = {REPO: {"status": status, "cutoff": RECENT}}
        res, summary, md = self._collect(**{loader: getattr(self, "_scratch" if loader == "input_dir" else "_bundle")(sources)})
        self.assertEqual(res["sources"][REPO]["status"], status)
        self.assertEqual(res["status"], expected_overall)
        self.assertEqual(summary["status"], expected_overall)
        self.assertNotIn("**FRESH**", md)

    def test_scratch_manifest_partial_failure(self):
        self._check("input_dir", "PARTIAL_FAILURE", "PARTIAL_FAILURE")
        res, _, _ = self._collect(input_dir=self._scratch({REPO: {"status": "PARTIAL_FAILURE", "cutoff": RECENT}}))
        self.assertEqual(res["sources"][REPO]["cutoff"], RECENT)

    def test_scratch_manifest_failed(self):
        self._check("input_dir", "FAILED", "PARTIAL_FAILURE")

    def test_scratch_manifest_stale(self):
        self._check("input_dir", "STALE", "STALE")

    def test_retained_bundle_partial_failure(self):
        self._check("telemetry_dir", "PARTIAL_FAILURE", "PARTIAL_FAILURE")

    def test_retained_bundle_failed(self):
        self._check("telemetry_dir", "FAILED", "PARTIAL_FAILURE")

    def test_retained_bundle_stale(self):
        self._check("telemetry_dir", "STALE", "STALE")

    def test_timeline_partial_failure_entry_survives(self):
        sources = {
            REPO: {"status": "PARTIAL_FAILURE", "cutoff": RECENT},
            REPO + ":timeline": {"status": "PARTIAL_FAILURE"},
        }
        res, summary, md = self._collect(input_dir=self._scratch(sources))
        self.assertEqual(res["sources"][REPO + ":timeline"]["status"], "PARTIAL_FAILURE")
        self.assertEqual(summary["status"], "PARTIAL_FAILURE")

    def test_complete_with_verified_cutoff_stays_complete_and_fresh(self):
        for loader, make in (("input_dir", self._scratch), ("telemetry_dir", self._bundle)):
            res, summary, _ = self._collect(**{loader: make({REPO: {"status": "COMPLETE", "cutoff": RECENT}})})
            self.assertEqual(res["sources"][REPO]["status"], "COMPLETE")
            self.assertEqual(summary["status"], "FRESH")

    def test_scratch_overrides_retained_bundle(self):
        res, _, _ = self._collect(
            input_dir=self._scratch({REPO: {"status": "PARTIAL_FAILURE", "cutoff": RECENT}}),
            telemetry_dir=self._bundle({REPO: {"status": "COMPLETE", "cutoff": RECENT}}),
        )
        self.assertEqual(res["sources"][REPO]["status"], "PARTIAL_FAILURE")

    def test_cli_reload_of_partial_failure(self):
        env = dict(os.environ, PRW_METRICS_REPOS=REPO)
        proc = subprocess.run(
            [sys.executable, os.path.join(ROOT, "scripts", "prw_metrics.py"), "--offline", "--cutoff", format_iso_utc(NOW),
             "--input-dir", self._scratch({REPO: {"status": "PARTIAL_FAILURE", "cutoff": RECENT}})],
            env=env, capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("**PARTIAL_FAILURE**", proc.stdout)
        self.assertNotIn("**FRESH**", proc.stdout)


if __name__ == "__main__":
    unittest.main()
