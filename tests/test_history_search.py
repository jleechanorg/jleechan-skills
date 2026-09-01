"""Tests for sparse history search across Claude, Codex, Hermes, agy, and Cursor."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest

from scripts.history_search import (
    ALL_SOURCES,
    HistoryEntry,
    ansify,
    color,
    format_results,
    search_agy,
    search_claude,
    search_codex,
    search_cursor,
    search_hermes,
    search_history,
)


class TestHistorySearch(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="test_hist_search_"))

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_search_claude_indexing_and_malformed_json_tolerance(self) -> None:
        proj_dir = self.temp_dir / "claude_projects" / "-Users-test-myproject"
        proj_dir.mkdir(parents=True)
        session_file = proj_dir / "session1.jsonl"

        lines = [
            json.dumps({"timestamp": "2026-08-01T12:00:00", "message": {"role": "user", "content": "How to implement sparse history search?"}}),
            "MALFORMED_JSON_LINE_{{{",
            json.dumps({"timestamp": "2026-08-01T12:05:00", "type": "assistant", "message": {"role": "assistant", "content": "Here is how..."}}),
            json.dumps({
                "timestamp": "2026-08-01T12:10:00",
                "message": {
                    "role": "user",
                    "content": [{"type": "text", "text": "Can we support agy and cursor transcripts?"}],
                },
            }),
        ]
        session_file.write_text("\n".join(lines), encoding="utf-8")

        # Search with query
        results = search_claude(
            query="cursor",
            cwd="/Users/test/myproject",
            projects_dir=self.temp_dir / "claude_projects",
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].source, "claude")
        self.assertIn("cursor transcripts", results[0].snippet)
        self.assertEqual(results[0].label, "-Users-test-myproject")

        # Search without query (overview)
        all_results = search_claude(
            query="",
            cwd="/Users/test/myproject",
            projects_dir=self.temp_dir / "claude_projects",
        )
        self.assertEqual(len(all_results), 2)

    def test_search_codex_sqlite_and_rollout_fallback(self) -> None:
        db_path = self.temp_dir / "state_5.sqlite"
        con = sqlite3.connect(str(db_path))
        con.execute("""
            CREATE TABLE threads (
                id TEXT PRIMARY KEY,
                title TEXT,
                first_user_message TEXT,
                cwd TEXT,
                git_branch TEXT,
                created_at INTEGER,
                archived INTEGER
            )
        """)
        # 1788283033 is in epoch seconds (year 2026)
        con.execute("""
            INSERT INTO threads (id, title, first_user_message, cwd, git_branch, created_at, archived)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            "t1",
            "Investigate latency anomaly",
            "Please check the trace spans for latency in mobile campaign flow",
            "/Users/test/project-alpha",
            "fix/mobile-latency",
            1788283033,
            0,
        ))
        con.execute("""
            INSERT INTO threads (id, title, first_user_message, cwd, git_branch, created_at, archived)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            "t2",
            "Archived thread",
            "Should not appear in active search results",
            "/Users/test/project-alpha",
            "main",
            1788283000,
            1,
        ))
        con.commit()
        con.close()

        results = search_codex(query="latency", cwd="/Users/test/project-alpha", db_path=db_path)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].source, "codex")
        self.assertIn("trace spans", results[0].snippet)
        self.assertIn("project-alpha", results[0].label)
        self.assertEqual(results[0].timestamp[:4], "2026")

        # Test rollout fallback when DB absent
        sess_dir = self.temp_dir / "codex_sessions" / "sub1" / "sub2" / "sub3"
        sess_dir.mkdir(parents=True)
        rollout_file = sess_dir / "rollout-01.jsonl"
        rollout_file.write_text(
            json.dumps({"timestamp": "2026-08-05", "role": "user", "content": "Rollout prompt test"}) + "\n",
            encoding="utf-8",
        )

        rollout_results = search_codex(
            query="Rollout",
            db_path=self.temp_dir / "nonexistent.sqlite",
            sessions_dir=self.temp_dir / "codex_sessions",
        )
        self.assertEqual(len(rollout_results), 1)
        self.assertIn("Rollout prompt test", rollout_results[0].snippet)

    def test_search_hermes_fts5_and_like_fallback(self) -> None:
        db_path = self.temp_dir / "hermes_state.db"
        con = sqlite3.connect(str(db_path))
        con.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY, title TEXT, source TEXT)")
        con.execute("""
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY,
                session_id TEXT,
                timestamp INTEGER,
                role TEXT,
                content TEXT,
                tool_name TEXT,
                tool_calls TEXT
            )
        """)
        con.execute("CREATE VIRTUAL TABLE messages_fts USING fts5(content)")
        con.execute("INSERT INTO sessions VALUES ('s1', 'Refactor auth tokens', 'slack')")
        con.execute("""
            INSERT INTO messages VALUES (1, 's1', 1788283033, 'user', 'Check refresh token expiration handler', NULL, NULL)
        """)
        con.execute("INSERT INTO messages_fts (rowid, content) VALUES (1, 'Check refresh token expiration handler')")
        con.commit()
        con.close()

        # FTS5 search
        results = search_hermes(query="refresh token", db_path=db_path)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].source, "hermes")
        self.assertIn("refresh token expiration", results[0].snippet)

        # Fallback LIKE search on DB without FTS table
        db_no_fts = self.temp_dir / "hermes_no_fts.db"
        con2 = sqlite3.connect(str(db_no_fts))
        con2.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY, title TEXT, source TEXT)")
        con2.execute("""
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY,
                session_id TEXT,
                timestamp INTEGER,
                role TEXT,
                content TEXT,
                tool_name TEXT,
                tool_calls TEXT
            )
        """)
        con2.execute("INSERT INTO sessions VALUES ('s2', 'CLI tool execution', 'terminal')")
        con2.execute("INSERT INTO messages VALUES (2, 's2', 1788283033, 'tool', 'tool result payload', 'deploy_tool', NULL)")
        con2.commit()
        con2.close()

        like_results = search_hermes(query="deploy_tool", db_path=db_no_fts)
        self.assertEqual(len(like_results), 1)
        self.assertIn("deploy_tool", like_results[0].label)

    def test_search_agy_summaries_and_brain_logs(self) -> None:
        db_path = self.temp_dir / "conversation_summaries.db"
        con = sqlite3.connect(str(db_path))
        con.execute("""
            CREATE TABLE conversation_summaries (
                conversation_id TEXT PRIMARY KEY,
                title TEXT,
                preview TEXT,
                step_count INTEGER,
                last_modified_time TEXT,
                workspace_uris TEXT,
                agent_name TEXT,
                killed INTEGER
            )
        """)
        con.execute("""
            INSERT INTO conversation_summaries VALUES (
                'conv-123',
                'Fix PR review issues in dark factory',
                'Updated daemon watchdog timeout and repaired harness retry gate',
                42,
                '2026-08-31T14:30:00Z',
                '/Users/test/dark-factory',
                'agy',
                0
            )
        """)
        con.commit()
        con.close()

        results = search_agy(query="watchdog", db_path=db_path)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].source, "agy")
        self.assertIn("daemon watchdog", results[0].snippet)
        self.assertIn("steps=42", results[0].label)

        # Test brain logs fallback when DB is missing
        brain_dir = self.temp_dir / "agy_brain" / "conv-456" / ".system_generated" / "logs"
        brain_dir.mkdir(parents=True)
        transcript_file = brain_dir / "transcript.jsonl"
        transcript_file.write_text(
            json.dumps({
                "step_index": 1,
                "source": "USER_EXPLICIT",
                "type": "USER_INPUT",
                "created_at": "2026-08-30T10:00:00Z",
                "content": "Add support for agy history search",
            }) + "\n",
            encoding="utf-8",
        )

        brain_results = search_agy(
            query="history search",
            db_path=self.temp_dir / "nonexistent.db",
            brain_dir=self.temp_dir / "agy_brain",
        )
        self.assertEqual(len(brain_results), 1)
        self.assertIn("Add support for agy history search", brain_results[0].snippet)

    def test_search_cursor_prompt_history_chats_and_transcripts(self) -> None:
        cursor_dir = self.temp_dir / "cursor"
        cursor_dir.mkdir(parents=True)

        # 1. prompt_history.json
        prompt_file = cursor_dir / "prompt_history.json"
        prompt_data = [
            "first prompt",
            {"prompt": "Scaffold a new CLI command for history search", "timestamp": "2026-08-28T09:00:00"},
            {"text": "Refactor Cursor prompt history reader", "ts": "2026-08-28T10:00:00"},
        ]
        prompt_file.write_text(json.dumps(prompt_data), encoding="utf-8")

        prompt_results = search_cursor(
            query="history search",
            prompt_history_path=prompt_file,
        )
        self.assertEqual(len(prompt_results), 1)
        self.assertEqual(prompt_results[0].source, "cursor")
        self.assertIn("Scaffold a new CLI command", prompt_results[0].snippet)

        # 2. agent-transcripts
        projects_dir = cursor_dir / "projects" / "my-project" / "agent-transcripts" / "session-01"
        projects_dir.mkdir(parents=True)
        agent_file = projects_dir / "session-01.jsonl"
        agent_file.write_text(
            json.dumps({
                "timestamp": "2026-08-29T11:00:00",
                "role": "user",
                "message": {"content": [{"type": "text", "text": "Cursor agent transcript sample prompt"}]},
            }) + "\n",
            encoding="utf-8",
        )

        agent_results = search_cursor(
            query="transcript sample",
            prompt_history_path=self.temp_dir / "nonexistent.json",
            projects_dir=cursor_dir / "projects",
        )
        self.assertEqual(len(agent_results), 1)
        self.assertIn("transcript sample prompt", agent_results[0].snippet)

        # 3. chats
        chats_dir = cursor_dir / "chats" / "chat-uuid"
        chats_dir.mkdir(parents=True)
        meta_file = chats_dir / "meta.json"
        meta_file.write_text(
            json.dumps({"schemaVersion": 1, "cwd": "/Users/test/cursor-project", "notes": "chat metadata sample"}),
            encoding="utf-8",
        )

        chat_results = search_cursor(
            query="cursor-project",
            prompt_history_path=self.temp_dir / "nonexistent.json",
            chats_dir=cursor_dir / "chats",
        )
        self.assertEqual(len(chat_results), 1)
        self.assertIn("cursor-project", chat_results[0].snippet)

    def test_graceful_handling_absent_databases_and_corrupt_files(self) -> None:
        # Nonexistent paths across all sources
        results = search_history(
            query="anything",
            claude_projects_dir=self.temp_dir / "absent_claude",
            codex_db_path=self.temp_dir / "absent_codex.sqlite",
            codex_sessions_dir=self.temp_dir / "absent_codex_sessions",
            hermes_db_path=self.temp_dir / "absent_hermes.db",
            agy_db_path=self.temp_dir / "absent_agy.db",
            agy_brain_dir=self.temp_dir / "absent_brain",
            cursor_prompt_history_path=self.temp_dir / "absent_cursor.json",
            cursor_chats_dir=self.temp_dir / "absent_chats",
            cursor_projects_dir=self.temp_dir / "absent_projects",
        )
        self.assertEqual(set(results.keys()), set(ALL_SOURCES))
        for src in ALL_SOURCES:
            self.assertEqual(results[src], [])

        # Corrupt / garbage files
        corrupt_claude = self.temp_dir / "corrupt_claude" / "proj"
        corrupt_claude.mkdir(parents=True)
        (corrupt_claude / "bad.jsonl").write_bytes(b"\xff\xfe\x00\x01\x80\x90garbage-data")

        corrupt_prompt = self.temp_dir / "corrupt_prompt.json"
        corrupt_prompt.write_text("NOT_JSON_DATA_AT_ALL", encoding="utf-8")

        corrupt_db = self.temp_dir / "corrupt.db"
        corrupt_db.write_bytes(b"NOT_A_SQLITE_DATABASE_HEADER")

        # Ensure no exception is raised
        corrupt_results = search_history(
            query="test",
            claude_projects_dir=self.temp_dir / "corrupt_claude",
            codex_db_path=corrupt_db,
            hermes_db_path=corrupt_db,
            agy_db_path=corrupt_db,
            cursor_prompt_history_path=corrupt_prompt,
        )
        self.assertIsInstance(corrupt_results, dict)

    def test_ansify_and_formatting(self) -> None:
        colored = ansify("agy", "2026-08-01 | Test Title | my match snippet", query="match", use_color=True)
        self.assertIn("\033[33m", colored)  # yellow label for agy
        self.assertIn("\033[1;33m", colored)  # match highlight
        self.assertIn("Test Title", colored)

        plain = ansify("cursor", "2026-08-01 | prompt | my prompt text", query="prompt", use_color=False)
        self.assertEqual(plain, "[Cursor] 2026-08-01 | prompt | my prompt text")

        dummy_results = {
            "claude": [HistoryEntry("claude", "2026-08-01", "proj", "sample claude")],
            "codex": [HistoryEntry("codex", "2026-08-01", "wt", "sample codex")],
            "hermes": [HistoryEntry("hermes", "2026-08-01", "slack", "sample hermes")],
            "agy": [HistoryEntry("agy", "2026-08-01", "agy title", "sample agy")],
            "cursor": [HistoryEntry("cursor", "2026-08-01", "prompt_history", "sample cursor")],
        }
        output = format_results(dummy_results, query="sample", use_color=False)
        self.assertIn("📁 Claude Code (1 matches)", output)
        self.assertIn("🤖 Codex (1 matches)", output)
        self.assertIn("⚡ Hermes (1 matches)", output)
        self.assertIn("🌐 agy CLI (1 matches)", output)
        self.assertIn("🖥️  Cursor (1 matches)", output)


if __name__ == "__main__":
    unittest.main()
