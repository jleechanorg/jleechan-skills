"""Offline collection must preserve cache uncertainty (PR #742 P0-2)."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone

from scripts.prw_metrics import Collector, DashboardRenderer, MetricsAggregator, format_iso_utc

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = "o/r"
PRS = [{"number": 1, "repo": REPO, "state": "MERGED",
        "createdAt": "2026-11-01T00:00:00Z", "mergedAt": "2026-11-02T00:00:00Z"}]


class TestOfflineFreshness(unittest.TestCase):
    def _state(self, manifest):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        with open(os.path.join(d.name, "enriched_prs.json"), "w") as f:
            json.dump(PRS, f)
        if manifest is not None:
            with open(os.path.join(d.name, "source_manifest.json"), "w") as f:
                f.write(manifest if isinstance(manifest, str) else json.dumps(manifest))
        return d.name

    def _run(self, manifest):
        now = datetime.now(timezone.utc)
        collector = Collector(repos=[REPO], cutoff_dt=now)
        res = collector.collect_all(input_dir=self._state(manifest), offline=True)
        summary = MetricsAggregator(cutoff_dt=now).aggregate_full_dataset(
            prs=res["prs"], sources=res["sources"], now_dt=now
        )
        return res, summary, DashboardRenderer().render(summary)

    def _assert_unknown_stays_stale(self, manifest):
        res, summary, md = self._run(manifest)
        src = res["sources"][REPO]
        self.assertIsNone(src["cutoff"])
        self.assertEqual(src["status"], "STALE")
        self.assertEqual(res["status"], "STALE")
        self.assertEqual(summary["status"], "STALE")
        self.assertEqual(summary["data_through"], "UNKNOWN")
        self.assertIn("**STALE**", md)
        self.assertNotIn("**FRESH**", md)

    def test_absent_manifest(self):
        self._assert_unknown_stays_stale(None)

    def test_invalid_cutoff(self):
        self._assert_unknown_stays_stale({REPO: {"status": "COMPLETE", "cutoff": "garbage"}})

    def test_unparseable_manifest_file(self):
        self._assert_unknown_stays_stale("{not json")

    def test_manifest_marked_stale_without_cutoff(self):
        self._assert_unknown_stays_stale({REPO: {"status": "STALE", "cutoff": None}})

    def test_manifest_marked_stale_with_cutoff_is_not_trusted(self):
        recent = format_iso_utc(datetime.now(timezone.utc))
        self._assert_unknown_stays_stale({REPO: {"status": "STALE", "cutoff": recent}})

    def test_old_manifest_keeps_its_old_cutoff(self):
        res, summary, md = self._run({REPO: {"status": "COMPLETE", "cutoff": "2026-01-01T00:00:00Z"}})
        self.assertEqual(res["sources"][REPO]["cutoff"], "2026-01-01T00:00:00Z")
        self.assertEqual(summary["status"], "STALE")
        self.assertEqual(summary["data_through"], "2026-01-01T00:00:00Z")

    def test_recent_verified_manifest_is_fresh(self):
        recent = format_iso_utc(datetime.now(timezone.utc))
        res, summary, _ = self._run({REPO: {"status": "COMPLETE", "cutoff": recent}})
        self.assertEqual(res["sources"][REPO]["status"], "COMPLETE")
        self.assertEqual(summary["status"], "FRESH")

    def test_cli_entry_point(self):
        env = dict(os.environ, PRW_METRICS_REPOS=REPO)
        proc = subprocess.run(
            [sys.executable, os.path.join(ROOT, "scripts", "prw_metrics.py"), "--offline",
             "--input-dir", self._state(None), "--cutoff", format_iso_utc(datetime.now(timezone.utc))],
            env=env, capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("**STALE**", proc.stdout)
        self.assertNotIn("**FRESH**", proc.stdout)


if __name__ == "__main__":
    unittest.main()
