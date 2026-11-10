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
        for prefix in (record * 2000, "x" * 65536):
            with self.subTest(size=len(prefix)):
                path.write_text(prefix + json.dumps({"role": "user", "content": "needle"}) + "\n")
                stderr = StringIO()
                with patch("sys.stderr", stderr):
                    self.assertEqual(search_codex("needle", codex_homes=[self.home]), [])
                self.assertIn("absence not proven", stderr.getvalue())

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
