"""Synthetic bounded Codex retrieval regressions; never read live history."""

import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from scripts.history_search import main, search_codex
from io import StringIO


class CodexRelevanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.sessions = self.home / "sessions"
        self.sessions.mkdir()
        self.db = self.home / "state_5.sqlite"

    def rollout(self, name, cwd, messages):
        path = self.sessions / f"rollout-{name}.jsonl"
        records = [{"type": "session_meta", "payload": {"id": name, "cwd": cwd}}]
        records.extend({"timestamp": "2026-11-09T12:00:00Z", "type": "response_item",
                        "payload": {"role": role, "content": [{"type": "input_text", "text": text}]}}
                       for role, text in messages)
        path.write_text("\n".join(map(json.dumps, records)) + "\n")
        return path

    def index(self, modern=True):
        with sqlite3.connect(self.db) as con:
            con.execute("CREATE TABLE threads (id TEXT, title TEXT, first_user_message TEXT, "
                        "cwd TEXT, git_branch TEXT, created_at INTEGER, archived INTEGER"
                        + (", updated_at INTEGER, rollout_path TEXT" if modern else "") + ")")
            rows = [("old", "needle", "needle unrelated", "/elsewhere", "main", 1, 0),
                    ("recent", "Project work", "Begin", "/work/project", "main", 2, 0)]
            for row in rows:
                if modern:
                    row += (100 if row[0] == "recent" else 1,
                            str(self.sessions / f"rollout-{row[0]}.jsonl"))
                con.execute("INSERT INTO threads VALUES (" + ",".join("?" for _ in row) + ")", row)

    def test_sessions_root_symlink_is_never_scanned_or_opened(self):
        outside = self.home / "outside"
        outside.mkdir()
        (outside / "rollout-secret.jsonl").write_text(json.dumps({"role": "user", "content": "needle secret"}) + "\n")
        self.sessions.rmdir()
        self.sessions.symlink_to(outside, target_is_directory=True)
        with patch("builtins.open") as opened, patch("os.scandir") as scanned:
            hits = search_codex("needle", codex_homes=[self.home])
        self.assertEqual(hits, [])
        opened.assert_not_called()
        scanned.assert_not_called()

    def test_legacy_user_message_rejects_contradictory_roles(self):
        path = self.sessions / "rollout-legacy.jsonl"
        records = [{"role": role, "user_message": "needle tool payload"}
                   for role in ("tool", "assistant", "system")]
        records += [{"message": {"role": "tool"}, "user_message": "needle nested tool"},
                    {"user_message": "needle genuine legacy"}]
        path.write_text("\n".join(map(json.dumps, records)) + "\n")
        hits = search_codex("needle", codex_homes=[self.home], limit=10)
        self.assertEqual([hit.snippet for hit in hits], ["needle genuine legacy"])
        self.assertFalse(hits[0].metadata["human_verified"])

    def test_index_activity_does_not_redate_first_message(self):
        from datetime import datetime
        self.index()
        activity = 1794355200
        with sqlite3.connect(self.db) as con:
            con.execute("UPDATE threads SET cwd=?, updated_at=?, rollout_path=NULL WHERE id='old'",
                        ("/work/project", activity))
        self.rollout("recent", "/work/project", [("user", "needle actual recent message")])
        hits = search_codex("needle", cwd="/work/project", codex_homes=[self.home], limit=1)
        self.assertEqual(hits[0].snippet, "needle actual recent message")
        all_hits = search_codex("needle", cwd="/work/project", codex_homes=[self.home], limit=5)
        hint = next(hit for hit in all_hits if hit.metadata["thread_id"] == "old")
        self.assertEqual(hint.timestamp, datetime.fromtimestamp(1).strftime("%Y-%m-%d %H:%M:%S"))
        self.assertEqual(hint.metadata["thread_activity_timestamp"],
                         datetime.fromtimestamp(activity).strftime("%Y-%m-%d %H:%M:%S"))
        self.assertEqual(hint.metadata["thread_activity_source"], "updated_at")

    def test_public_cli_finds_project_followup_despite_unrelated_index_hit(self):
        self.index()
        path = self.rollout("recent", "/work/project", [("user", "needle followup " + "x" * 100)])
        out = StringIO()
        with patch("sys.stdout", out), patch("scripts.history_search.Path.home", side_effect=AssertionError("default probed")):
            self.assertEqual(main(["--source", "codex", "--codex-home", str(self.home),
                                   "--cwd", "/work/project", "--limit", "1", "--max-chars", "30",
                                   "--json", "needle"]), 0)
        entries = json.loads(out.getvalue())["codex"]
        self.assertEqual(len(entries), 1)
        self.assertIn("needle followup", entries[0]["snippet"])
        self.assertLessEqual(len(entries[0]["snippet"]), 30)
        self.assertEqual(entries[0]["metadata"]["path"], str(path))
        self.assertEqual(entries[0]["metadata"]["role"], "user")
        self.assertFalse(entries[0]["metadata"]["human_verified"])

    def test_legacy_index_still_searches_followups_and_no_query(self):
        self.index(modern=False)
        self.rollout("recent", "/work/project", [("user", "needle followup")])
        hits = search_codex("needle", cwd="/work/project", codex_homes=[self.home], limit=1)
        self.assertEqual(hits[0].snippet, "needle followup")
        overview = search_codex(cwd="/work/project", codex_homes=[self.home], limit=1)
        self.assertEqual(len(overview), 1)
        self.assertEqual(overview[0].metadata["cwd"], "/work/project")

    def test_tool_and_unattributed_nested_messages_are_not_user_prompts(self):
        path = self.rollout("roles", "/work/project", [("tool", "needle secret"), ("user", "needle injected")])
        with path.open("a") as stream:
            stream.write(json.dumps({"message": {"role": "tool", "content": "needle tool"}}) + "\n")
        hits = search_codex("needle", codex_homes=[self.home])
        self.assertEqual([hit.snippet for hit in hits], ["needle injected"])
        self.assertFalse(hits[0].metadata["human_verified"])

    def test_index_match_beyond_excerpt_and_literal_sql_input(self):
        self.index(modern=False)
        with sqlite3.connect(self.db) as con:
            con.execute("UPDATE threads SET title = 'plain', first_user_message = ? WHERE id = 'recent'",
                        ("x" * 200 + " needle ' OR 1=1 --",))
        hits = search_codex("needle ' OR 1=1 --", codex_homes=[self.home], max_chars=20)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].snippet, "x" * 20)
        self.assertEqual(search_codex("unmatched ' OR 1=1 --", codex_homes=[self.home]), [])

    def test_updated_project_candidate_beats_newer_creation_and_index_is_read_only(self):
        self.index()
        self.rollout("recent", "/work/project", [("user", "needle updated")])
        with sqlite3.connect(self.db) as con:
            for number in range(25):
                con.execute("INSERT INTO threads VALUES (?, 'plain', 'begin', '/work/project', 'main', ?, 0, 2, NULL)",
                            (f"other-{number}", number + 100))
        before = self.db.read_bytes()
        hits = search_codex("needle", cwd="/work/project", codex_homes=[self.home], limit=1)
        self.assertEqual(hits[0].snippet, "needle updated")
        self.assertEqual(self.db.read_bytes(), before)

    def test_outside_index_pointer_and_symlink_are_never_opened(self):
        self.index()
        with sqlite3.connect(self.db) as con:
            con.execute("UPDATE threads SET rollout_path = NULL WHERE id = 'old'")
            con.execute("UPDATE threads SET rollout_path = ? WHERE id = 'recent'",
                        (str(self.home / "denied" / "rollout-secret.jsonl"),))
        (self.sessions / "rollout-link.jsonl").symlink_to(self.home / "denied" / "rollout-secret.jsonl")
        with patch("builtins.open", side_effect=AssertionError("unadmitted open")) as opened:
            hits = search_codex("needle", cwd="/work/project", codex_homes=[self.home])
        opened.assert_not_called()
        self.assertEqual(hits[0].metadata["thread_id"], "old")

    def test_line_and_byte_bounds_report_partial_even_without_hits(self):
        path = self.sessions / "rollout-bounded.jsonl"
        record = json.dumps({"role": "user", "content": "ordinary"}) + "\n"
        needle = json.dumps({"role": "user", "content": "needle"}) + "\n"
        # The sample now keeps both ends: absence still cannot be claimed for
        # an omitted middle record, or a record larger than the record budget.
        for content in (record * 2000 + needle + record * 2000,
                        json.dumps({"role": "user", "content": "needle" + "x" * 65536}) + "\n"):
            with self.subTest(size=len(content)):
                path.write_text(content)
                stderr = StringIO()
                with patch("sys.stderr", stderr):
                    self.assertEqual(search_codex("needle", codex_homes=[self.home]), [])
                self.assertIn("absence not proven", stderr.getvalue())

    def test_recent_tail_survives_oversized_record_with_byte_provenance(self):
        self.index()
        path = self.rollout("recent", "/work/project", [])
        with path.open("a") as stream:
            stream.write(json.dumps({"type": "turn_context", "payload": {"model": "stale-model"}}) + "\n")
            stream.write(json.dumps({"role": "tool", "content": "x" * (2 * 1024 * 1024)}) + "\n")
            for number in range(2):
                stream.write(json.dumps({"timestamp": f"2026-11-09T12:00:0{number}Z",
                                         "role": "user", "content": f"needle tail {number}"}) + "\n")
        original_open = open
        reads = []
        class ObservedReader:
            def __init__(self, stream):
                self.stream = stream
            def __enter__(self):
                return self
            def __exit__(self, *args):
                self.stream.close()
            def __getattr__(self, name):
                return getattr(self.stream, name)
            def read(self, size=-1):
                if size < 0:
                    raise AssertionError("unbounded read")
                data = self.stream.read(size)
                reads.append(len(data))
                return data
            def readline(self, size=-1):
                if size < 0:
                    raise AssertionError("unbounded readline")
                data = self.stream.readline(size)
                reads.append(len(data))
                return data
        with patch("builtins.open", side_effect=lambda *a, **kw: ObservedReader(original_open(*a, **kw))):
            hits = search_codex("needle", cwd="/work/project", codex_homes=[self.home], limit=2)
        self.assertEqual([hit.snippet for hit in hits], ["needle tail 1", "needle tail 0"])
        self.assertLessEqual(sum(reads), 1024 * 1024)
        for hit in hits:
            self.assertIsNone(hit.metadata.get("line"))
            self.assertNotIn("model", hit.metadata)  # skipped turns cannot inherit stale model
            self.assertFalse(hit.metadata["human_verified"])
            self.assertEqual(hit.metadata["cwd"], "/work/project")
            with path.open("rb") as stream:
                stream.seek(hit.metadata["byte_offset"])
                self.assertEqual(json.loads(stream.readline())["content"], hit.snippet)

    def test_recent_followup_after_two_thousand_records_has_exact_locator(self):
        path = self.rollout("long", "/work/project", [])
        padding = json.dumps({"role": "assistant", "content": "ordinary"}) + "\n"
        with path.open("a") as stream:
            stream.write(padding * 5000)
            stream.write(json.dumps({"type": "turn_context", "payload": {"model": "recent-model"}}) + "\n")
            stream.write(json.dumps({"role": "user", "content": "needle late followup"}) + "\n")
        hits = search_codex("needle", cwd="/work/project", codex_homes=[self.home], limit=1)
        self.assertEqual([hit.snippet for hit in hits], ["needle late followup"])
        self.assertEqual(hits[0].metadata["line"], 5003)
        self.assertEqual(hits[0].metadata["model"], "recent-model")
        self.assertEqual(hits[0].metadata["model_source"], "turn_context")

    def test_final_unterminated_record_and_result_limit(self):
        path = self.rollout("recent", "/work/project", [("user", f"needle {i}") for i in range(10)])
        path.write_text(path.read_text().rstrip("\n"))
        hits = search_codex("needle", codex_homes=[self.home], limit=3, max_chars=8)
        self.assertEqual(len(hits), 3)
        self.assertTrue(all(len(hit.snippet) <= 8 for hit in hits))
        self.assertEqual(len(search_codex("needle 9", codex_homes=[self.home])), 1)

    def test_candidate_file_budget_is_enforced(self):
        for number in range(30):
            self.rollout(str(number), "/elsewhere", [("user", "ordinary")])
        original_open = open
        with patch("builtins.open", wraps=original_open) as opened:
            self.assertEqual(search_codex("needle", codex_homes=[self.home], limit=1), [])
        self.assertEqual(opened.call_count, 20)

    def test_corrupt_rollout_and_database_report_errors(self):
        self.db.write_bytes(b"not sqlite")
        (self.sessions / "rollout-broken.jsonl").write_text("not json\n")
        stderr = StringIO()
        with patch("sys.stderr", stderr):
            self.assertEqual(search_codex("needle", codex_homes=[self.home]), [])
        self.assertIn("errors=2", stderr.getvalue())

    def test_limit_keeps_newest_matching_followup_in_same_project(self):
        path = self.rollout("recent", "/work/project", [("user", "needle early"), ("user", "needle later")])
        records = path.read_text().splitlines()
        early = json.loads(records[1])
        early["timestamp"] = "2025-01-01T00:00:00Z"
        records[1] = json.dumps(early)
        path.write_text("\n".join(records) + "\n")
        hits = search_codex("needle", cwd="/work/project", codex_homes=[self.home], limit=1)
        self.assertEqual(hits[0].snippet, "needle later")


if __name__ == "__main__":
    unittest.main()
