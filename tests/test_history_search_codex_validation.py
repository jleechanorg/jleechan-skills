"""Validation of suspected Codex helper defects using synthetic fixtures only.

Every test builds a throwaway profile in a temp dir, passes it explicitly via
codex_homes/--codex-home, and forbids probing the real home directory.
"""

import contextlib
import io
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.history_search import main, search_codex

PROJECT = "/work/project"


class CodexValidationBase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name).resolve()
        self.sessions = self.home / "sessions"
        self.sessions.mkdir()
        self.db = self.home / "state_5.sqlite"
        with contextlib.closing(sqlite3.connect(self.db)) as con, con:
            con.execute("CREATE TABLE threads (id TEXT, title TEXT, first_user_message TEXT, "
                        "cwd TEXT, git_branch TEXT, created_at INTEGER, archived INTEGER, "
                        "updated_at INTEGER, rollout_path TEXT)")
        guard = patch("scripts.history_search.Path.home", side_effect=AssertionError("real home probed"))
        guard.start()
        self.addCleanup(guard.stop)

    def thread(self, tid, cwd=PROJECT, title="plain", first="begin", created=1, updated=1, rollout=True):
        path = self.sessions / f"rollout-{tid}.jsonl"
        with contextlib.closing(sqlite3.connect(self.db)) as con, con:
            con.execute("INSERT INTO threads VALUES (?,?,?,?,'main',?,0,?,?)",
                        (tid, title, first, cwd, created, updated, str(path) if rollout else None))
        return path

    def write_rollout(self, path, texts, cwd=PROJECT, pad=0):
        recs = [{"type": "session_meta", "payload": {"id": path.stem, "cwd": cwd}}]
        for text in texts:
            recs.append({"timestamp": "2026-11-09T12:00:00Z", "type": "response_item",
                         "payload": {"role": "user", "content": [{"type": "input_text", "text": text}]}})
        lines = [json.dumps(r) for r in recs]
        # Insert padding (filler records) between the first and the remaining records.
        filler = json.dumps({"type": "event_msg", "payload": {"type": "noop", "x": "p" * 1000}})
        lines[1:1] = [filler] * pad
        path.write_text("\n".join(lines) + "\n")

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.assertEqual(main(["--source", "codex", "--codex-home", str(self.home),
                                   "--cwd", PROJECT, "--json", *args]), 0)
        return json.loads(out.getvalue())["codex"], err.getvalue()


class CandidateStarvation(CodexValidationBase):
    def test_a_index_match_not_crowded_out_by_newer_unmatched_project_threads(self):
        for n in range(30):  # newer in-project threads that do not match the query
            self.thread(f"noise{n}", created=100 + n, updated=100 + n, rollout=False)
        self.thread("target", cwd="/elsewhere", title="zebra-marker design", created=1, updated=1,
                    rollout=False)
        hits = search_codex("zebra-marker", cwd=PROJECT, codex_homes=[self.home], limit=1)
        self.assertEqual([h.metadata["thread_id"] for h in hits], ["target"])

    def test_a_matching_project_thread_outranks_newer_external_matches(self):
        for n in range(30):  # newer in-project threads that do not match the query
            self.thread(f"noise{n}", created=1000 + n, updated=1000 + n, rollout=False)
        self.thread("wanted", title="zebra-marker design", created=1, updated=1, rollout=False)
        for n in range(20):  # newer matches elsewhere fill the supplementary limit
            self.thread(f"other{n}", cwd="/elsewhere", title="zebra-marker", created=500 + n,
                        updated=500 + n, rollout=False)
        hits = search_codex("zebra-marker", cwd=PROJECT, codex_homes=[self.home], limit=1)
        self.assertEqual([h.metadata["thread_id"] for h in hits], ["wanted"])

    def test_a_supplementary_matches_do_not_take_rollout_scan_slots(self):
        self.thread("noise", rollout=False)  # one in-project index row that does not match
        for n in range(20):  # indexed matches elsewhere, each with a rollout file
            p = self.thread(f"out{n}", cwd="/elsewhere", title="zebra-marker", created=500 + n,
                            updated=500 + n)
            self.write_rollout(p, ["unrelated"], cwd="/elsewhere")
        wanted = self.sessions / "rollout-wanted.jsonl"  # in-project followup with no index row
        self.write_rollout(wanted, ["zebra-marker followup"])
        newest = max(p.stat().st_mtime for p in self.sessions.iterdir()) + 10
        os.utime(wanted, (newest, newest))  # newest file regardless of timestamp resolution
        hits = search_codex("zebra-marker", cwd=PROJECT, codex_homes=[self.home], limit=1)
        self.assertEqual([h.metadata.get("path") for h in hits], [str(wanted)])

    def test_a_rollout_candidate_cap_is_documented_when_noise_fills_it(self):
        for n in range(30):
            p = self.thread(f"noise{n}", created=100 + n, updated=100 + n)
            self.write_rollout(p, ["nothing relevant here"])
        self.write_rollout(self.sessions / "rollout-target.jsonl", ["zebra-marker followup"],
                           cwd="/elsewhere")
        entries, err = self.run_cli("--limit", "1", "zebra-marker")
        self.assertEqual(entries, [])  # by design: bounded candidate sample
        self.assertIn("candidates <= 20", err)
        self.assertIn("absence not proven", err)


class MatchQueryBudget(CodexValidationBase):
    def test_a_interrupted_match_query_keeps_primary_rows(self):
        self.thread("target", title="zebra-marker design", created=5, updated=5, rollout=False)
        real_connect = sqlite3.connect

        class Cursor:
            def __init__(self, cur):
                self.cur, self.selects = cur, 0

            def execute(self, sql, *args):
                if "FROM threads" in sql:
                    self.selects += 1
                    if self.selects == 2:  # the shared step budget runs out here
                        raise sqlite3.OperationalError("interrupted")
                return self.cur.execute(sql, *args)

        class Connection:
            def __init__(self, con):
                self.con = con

            def cursor(self):
                return Cursor(self.con.cursor())

            def __getattr__(self, name):
                return getattr(self.con, name)

        with patch("scripts.history_search.sqlite3.connect",
                   side_effect=lambda *a, **k: Connection(real_connect(*a, **k))):
            entries, err = self.run_cli("--limit", "1", "zebra-marker")
        self.assertEqual([e["metadata"]["thread_id"] for e in entries], ["target"])
        self.assertIn("errors=1", err)


class NullableUpdateOrdering(CodexValidationBase):
    def test_b_null_updated_at_falls_back_to_created_at(self):
        for n in range(25):  # same cwd, stale non-null updated_at, title matches
            self.thread(f"old{n}", title="needle old", created=10, updated=10 + n, rollout=False)
        self.thread("fresh", title="needle fresh", created=5000, updated=None, rollout=False)
        hits = search_codex("needle", cwd=PROJECT, codex_homes=[self.home], limit=1)
        self.assertEqual(hits[0].metadata["thread_id"], "fresh")


class NoQueryFallbackRecency(CodexValidationBase):
    def test_c_fallback_uses_last_activity_like_primary_path(self):
        # No thread matches the cwd, so the unscoped fallback query runs.
        self.thread("created_late", cwd="/a/one", created=2000, updated=2001, rollout=False)
        self.thread("active_late", cwd="/b/two", created=1000, updated=9000, rollout=False)
        hits = search_codex(cwd="/nowhere/else", codex_homes=[self.home], limit=1)
        self.assertEqual(hits[0].metadata["thread_id"], "active_late")

    def test_c_fallback_null_updated_at_uses_created_at(self):
        self.thread("stale", cwd="/a/one", created=10, updated=500, rollout=False)
        self.thread("fresh", cwd="/b/two", created=900, updated=None, rollout=False)
        hits = search_codex(cwd="/nowhere/else", codex_homes=[self.home], limit=1)
        self.assertEqual(hits[0].metadata["thread_id"], "fresh")


    def big_store(self, count, updated, indexes):
        with contextlib.closing(sqlite3.connect(self.db)) as con, con:
            con.executemany("INSERT INTO threads VALUES (?,'plain','begin','/other','main',?,0,?,NULL)",
                            ((f"t{n}", n, n if updated else None) for n in range(count)))
            for column in indexes:
                con.execute(f"CREATE INDEX idx_{column} ON threads({column} DESC, id DESC)")
        return search_codex(cwd="/nowhere/else", codex_homes=[self.home], limit=1)

    # The next three use the real progress handler, no mocks. The base helper passes each.
    def test_c_fallback_stays_within_step_budget_on_a_large_indexed_store(self):
        hits = self.big_store(40000, updated=True, indexes=("created_at", "updated_at"))
        self.assertEqual([h.metadata["thread_id"] for h in hits], ["t39999"])
        self.assertEqual(hits[0].metadata["coverage_errors"], 0)

    def test_c_fallback_keeps_results_when_only_created_at_is_indexed(self):
        hits = self.big_store(40000, updated=True, indexes=("created_at",))
        self.assertEqual([h.metadata["thread_id"] for h in hits], ["t39999"])

    def test_c_fallback_returns_newest_thread_when_every_updated_at_is_null(self):
        hits = self.big_store(80000, updated=False, indexes=("created_at", "updated_at"))
        self.assertEqual([h.metadata["thread_id"] for h in hits], ["t79999"])
        self.assertEqual(hits[0].metadata["coverage_errors"], 0)


class UnreadMiddleCoverage(CodexValidationBase):
    def test_d_match_only_in_unread_middle_is_empty_but_flagged(self):
        path = self.thread("big")
        # ~3 MiB file; the match sits in the middle, beyond head and tail windows.
        self.write_rollout(path, [])
        with path.open("a") as f:
            filler = json.dumps({"type": "event_msg", "payload": {"x": "p" * 1000}}) + "\n"
            f.write(filler * 1500)
            f.write(json.dumps({"timestamp": "t", "type": "response_item", "payload": {
                "role": "user", "content": [{"type": "input_text", "text": "middle-marker"}]}}) + "\n")
            f.write(filler * 1500)
        self.assertGreater(path.stat().st_size, 2 * 1024 * 1024)
        entries, err = self.run_cli("middle-marker")
        self.assertEqual(entries, [])  # by design: bounded sample misses the middle
        self.assertIn("absence not proven", err)
        self.assertIn("1 MiB", err)

    def test_d_hit_elsewhere_reports_bounded_coverage_metadata(self):
        path = self.thread("small")
        self.write_rollout(path, ["tail-marker"])
        entries, _ = self.run_cli("tail-marker")
        self.assertEqual(entries[0]["metadata"]["coverage"], "bounded rollout sample")
        self.assertIn("coverage_errors", entries[0]["metadata"])


if __name__ == "__main__":
    unittest.main()
