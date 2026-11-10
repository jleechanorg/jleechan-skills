"""Session-to-PR binding ledger join."""

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scripts.prw_session_bindings import binding_at, load


def T(h, m=0):
    return datetime(2026, 11, 9, h, m, tzinfo=timezone.utc)


def rec(ts, kind, session="s1", **kw):
    r = {"v": 1, "ts": ts, "runtime": "claude", "session_id": session, "kind": kind}
    r.update(kw)
    return r


def pr(ts, number=42, session="s1", repo="acme/app", branch="feat"):
    return rec(ts, "pr_binding", session, pr=f"{repo}#{number}", repo=repo, branch=branch)


class SessionBindingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "ledger.jsonl"

    def index(self, records, extra_lines=()):
        lines = [json.dumps(r) if isinstance(r, dict) else r for r in records]
        self.path.write_text("\n".join(list(lines) + list(extra_lines)) + "\n")
        return load([self.path])

    def test_window_start(self):
        idx, _ = self.index([pr("2026-11-09T10:00:00Z")])
        self.assertIsNone(binding_at(idx, "s1", T(9, 59)))
        self.assertEqual(binding_at(idx, "s1", T(10, 0)), "acme/app#42")
        self.assertEqual(binding_at(idx, "s1", T(10, 5)), "acme/app#42")

    def test_second_binding_replaces(self):
        idx, _ = self.index([pr("2026-11-09T10:00:00Z"), pr("2026-11-09T11:00:00Z", 43)])
        self.assertEqual(binding_at(idx, "s1", T(10, 59)), "acme/app#42")
        self.assertEqual(binding_at(idx, "s1", T(11, 0)), "acme/app#43")

    def test_branch_other_same_repo_clears(self):
        idx, _ = self.index([pr("2026-11-09T10:00:00Z"),
                             rec("2026-11-09T10:30:00Z", "branch", repo="acme/app", branch="other")])
        self.assertEqual(binding_at(idx, "s1", T(10, 29)), "acme/app#42")
        self.assertIsNone(binding_at(idx, "s1", T(10, 30)))

    def test_branch_other_repo_clears(self):
        idx, _ = self.index([pr("2026-11-09T10:00:00Z"),
                             rec("2026-11-09T10:30:00Z", "branch", repo="acme/lib", branch="feat")])
        self.assertIsNone(binding_at(idx, "s1", T(10, 31)))

    def test_branch_same_keeps(self):
        idx, _ = self.index([pr("2026-11-09T10:00:00Z"),
                             rec("2026-11-09T10:30:00Z", "branch", repo="acme/app", branch="feat")])
        self.assertEqual(binding_at(idx, "s1", T(11)), "acme/app#42")

    def test_rebind_after_clear(self):
        idx, _ = self.index([pr("2026-11-09T10:00:00Z"),
                             rec("2026-11-09T10:30:00Z", "branch", repo="acme/app", branch="other"),
                             pr("2026-11-09T11:00:00Z", 50, branch="other")])
        self.assertIsNone(binding_at(idx, "s1", T(10, 45)))
        self.assertEqual(binding_at(idx, "s1", T(11, 1)), "acme/app#50")

    def test_start_and_stop_ignored(self):
        idx, _ = self.index([pr("2026-11-09T10:00:00Z"),
                             rec("2026-11-09T10:10:00Z", "session_start", repo="acme/lib", branch="x"),
                             rec("2026-11-09T10:20:00Z", "stop", repo="acme/lib", branch="y")])
        self.assertEqual(binding_at(idx, "s1", T(11)), "acme/app#42")

    def test_other_session_and_unknown(self):
        idx, _ = self.index([pr("2026-11-09T10:00:00Z")])
        self.assertIsNone(binding_at(idx, "s2", T(11)))
        self.assertIsNone(binding_at(idx, "", T(11)))
        self.assertIsNone(binding_at(idx, None, T(11)))

    def test_out_of_order(self):
        idx, _ = self.index([rec("2026-11-09T10:30:00Z", "branch", repo="acme/app", branch="other"),
                             pr("2026-11-09T10:00:00Z")])
        self.assertEqual(binding_at(idx, "s1", T(10, 15)), "acme/app#42")
        self.assertIsNone(binding_at(idx, "s1", T(10, 45)))

    def test_malformed_counted(self):
        bad = [
            "not json",
            "[1, 2]",
            json.dumps(pr("2026-11-09T10:00:00Z") | {"v": 2}),
            json.dumps(pr("yesterday")),
            json.dumps(pr("2026-11-09T10:00:00Z") | {"pr": "nonsense"}),
        ]
        idx, stats = self.index([pr("2026-11-09T10:00:00Z")], bad)
        self.assertEqual(stats["session_binding_malformed"], 5)
        self.assertEqual(stats["session_binding_records"], 1)
        self.assertEqual(binding_at(idx, "s1", T(11)), "acme/app#42")

    def test_missing_file(self):
        idx, stats = load([Path(self.tmp.name) / "nope.jsonl"])
        self.assertEqual(stats["session_binding_missing_files"], 1)
        self.assertIsNone(binding_at(idx, "s1", T(11)))


if __name__ == "__main__":
    unittest.main()
