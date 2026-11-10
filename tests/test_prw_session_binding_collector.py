"""Collector attributes usage through the session binding ledger (synthetic data only)."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scripts.native_usage_collector import collect_native_history

REPO = Path(__file__).resolve().parents[1]
PIN = "5c93ac7769d2"
CUTOFF = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)
EXPECTED = {"pr": "acme/app#42", "weight": 1.0, "method": "convention",
            "convention_ref": "prw-session-binding/v1", "basis": "hook_session_binding",
            "receipt_refs": ["prw-session-binding/v1:{session}:acme/app#42:2026-11-09T10:00:00Z"],
            "rationale": "session bound to this PR by the hook ledger"}


def expected(session):
    return dict(EXPECTED, receipt_refs=[EXPECTED["receipt_refs"][0].format(session=session)])


def claude_row(request_id, ts, session="sess-claude", tokens=100):
    return {"type": "assistant", "timestamp": ts, "requestId": request_id, "sessionId": session,
            "message": {"id": "msg-" + request_id, "model": "claude-test",
                        "usage": {"input_tokens": tokens, "output_tokens": 10}}}


def codex_rows(session, items):
    rows = [{"type": "session_meta", "payload": {"id": session}}]
    for response_id, ts, tokens in items:
        rows.append({"type": "token_usage_record", "timestamp": ts,
                     "payload": {"response_id": response_id,
                                 "usage": {"input_tokens": tokens, "output_tokens": 10}}})
    return rows


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def ledger_row(ts, session, pr="acme/app#42", runtime="claude"):
    return {"v": 1, "ts": ts, "runtime": runtime, "session_id": session, "kind": "pr_binding",
            "repo": "acme/app", "branch": "feat", "pr": pr, "source": "gh_pr_create"}


class SessionBindingCollectorBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "history"
        self.root.mkdir()
        write_jsonl(self.root / "claude.jsonl", [
            claude_row("r1", "2026-11-09T09:00:00Z", tokens=100),
            claude_row("r2", "2026-11-09T10:10:00Z", tokens=200),
            claude_row("r3", "2026-11-09T10:40:00Z", tokens=300),
        ])
        write_jsonl(self.root / "codex.jsonl", codex_rows("sess-codex", [
            ("c1", "2026-11-09T09:00:00Z", 100),
            ("c2", "2026-11-09T10:10:00Z", 200),
            ("c3", "2026-11-09T10:40:00Z", 300),
        ]))
        self.ledger = Path(self.tmp.name) / "ledger.jsonl"
        write_jsonl(self.ledger, [
            ledger_row("2026-11-09T10:00:00Z", "sess-claude"),
            ledger_row("2026-11-09T10:00:00Z", "sess-codex", runtime="codex"),
        ])

    def collect(self, **kw):
        return collect_native_history([self.root], cutoff=CUTOFF, **kw)

    @staticmethod
    def attrs(data):
        return {r["request_id"]: r.get("attributions") for r in data["usage_records"]}


class SessionBindingCollectorTests(SessionBindingCollectorBase):
    def test_claude_and_codex_sessions_bound_after_binding_only(self):
        data = self.collect(session_bindings=[self.ledger])
        attrs = self.attrs(data)
        for early, late, session in (("r1", ("r2", "r3"), "sess-claude"),
                                     ("c1", ("c2", "c3"), "sess-codex")):
            self.assertFalse(attrs[early])
            for request in late:
                self.assertEqual(attrs[request], [expected(session)])
        self.assertEqual(data["stats"]["session_bound_usage_records"], 4)
        exported = {r["request_id"]: r for r in data["export_records"] if r["record_type"] == "usage"}
        self.assertEqual(exported["r2"]["attributions"], [dict(expected("sess-claude"), rationale="retained")])

    def test_request_level_binding_wins(self):
        ann = Path(self.tmp.name) / "ann.jsonl"
        direct = {"pr": "acme/app#99", "weight": 1.0, "method": "direct"}
        write_jsonl(ann, [{"provider": "anthropic", "request_id": "r3", "pr_binding": direct}])
        data = self.collect(session_bindings=[self.ledger], annotation_path=ann)
        attrs = self.attrs(data)
        self.assertEqual(attrs["r3"], [direct])
        self.assertEqual(attrs["r2"], [expected("sess-claude")])
        self.assertEqual(data["stats"]["session_bound_usage_records"], 3)

    def test_stats_report_join_counters(self):
        with self.ledger.open("a") as handle:
            handle.write("garbage\n")
        data = self.collect(session_bindings=[self.ledger])
        stats = data["stats"]
        self.assertEqual(stats["session_binding_records"], 2)
        self.assertEqual(stats["session_binding_malformed"], 1)
        self.assertEqual(stats["session_bound_usage_records"], 4)

    def test_missing_ledger_is_not_fatal(self):
        data = self.collect(session_bindings=[Path(self.tmp.name) / "none.jsonl"])
        self.assertEqual(data["stats"]["session_bound_usage_records"], 0)
        self.assertEqual(data["stats"]["session_binding_missing_files"], 1)

    def test_cli_flag_is_repeatable_and_attributes(self):
        out = Path(self.tmp.name) / "out.jsonl"
        second = Path(self.tmp.name) / "second.jsonl"
        write_jsonl(second, [])
        subprocess.run(
            [sys.executable, str(REPO / "scripts" / "native_usage_collector.py"),
             "--history-root", str(self.root), "--cutoff", "2026-11-09T12:00:00Z",
             "--session-bindings", str(self.ledger), "--session-bindings", str(second),
             "--output", str(out)],
            check=True, capture_output=True, text=True, timeout=60, cwd=self.tmp.name)
        rows = [json.loads(line) for line in out.read_text().splitlines()]
        bound = [r for r in rows if r.get("attributions")]
        self.assertEqual(len(bound), 4)


class DownstreamValidationTests(SessionBindingCollectorBase):
    """Real path: collector export -> load_usage_events -> aggregate_usage."""

    def aggregate(self, **kw):
        from scripts.native_usage_collector import write_normalized_history
        from scripts.prw_metrics import aggregate_usage, load_usage_events
        data = self.collect(**kw)
        out = Path(self.tmp.name) / "export.jsonl"
        write_normalized_history(out, data["export_records"])
        return aggregate_usage(load_usage_events(out), []), data

    def test_bound_events_validate_and_leave_unallocated(self):
        summary, _ = self.aggregate(session_bindings=[self.ledger])
        self.assertEqual(summary["event_count"], 6)
        self.assertEqual(summary["unallocated"]["event_count"], 2)  # r1 and c1 only
        bound = [e for e in summary["events"] if e.get("validated_attributions")]
        self.assertEqual(len(bound), 4)
        for event in bound:
            (attr,) = event["validated_attributions"]
            self.assertEqual(attr["pr"], "acme/app#42")
            self.assertEqual(attr["method"], "convention")
            self.assertEqual(attr["weight"], "1")
            # convention_ref is nulled by prw_metrics._usage_label ("/" is not allowed);
            # the query keys on method == "convention" only, so this is not asserted.
            self.assertTrue(attr["receipt_refs"])

    def test_without_ledger_everything_is_unallocated(self):
        summary, _ = self.aggregate()
        self.assertEqual(summary["unallocated"]["event_count"], 6)
        self.assertFalse(any(e.get("validated_attributions") for e in summary["events"]))


class ByteIdentityTests(SessionBindingCollectorBase):
    def test_without_flag_output_matches_pin_collector(self):
        pin = subprocess.run(["git", "show", f"{PIN}:scripts/native_usage_collector.py"],
                             cwd=REPO, capture_output=True, text=True)
        if pin.returncode != 0:
            self.skipTest("pin commit not available: " + pin.stderr.strip())
        pin_dir = Path(self.tmp.name) / "pin"
        pin_dir.mkdir()
        (pin_dir / "pin_collector.py").write_text(pin.stdout, encoding="utf-8")
        env = dict(os.environ, PYTHONPATH=str(REPO / "scripts"))

        def run(script, out):
            subprocess.run(
                [sys.executable, str(script), "--history-root", str(self.root),
                 "--cutoff", "2026-11-09T12:00:00Z", "--output", str(out)],
                check=True, capture_output=True, text=True, timeout=60, env=env, cwd=self.tmp.name)
            return out.read_bytes(), Path(str(out) + ".stats.json").read_bytes()

        old = run(pin_dir / "pin_collector.py", Path(self.tmp.name) / "old.jsonl")
        new = run(REPO / "scripts" / "native_usage_collector.py", Path(self.tmp.name) / "new.jsonl")
        self.assertEqual(old, new)


if __name__ == "__main__":
    unittest.main()
