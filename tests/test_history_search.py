"""Tests for sparse history search across Claude, Codex, Hermes, agy, and Cursor."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from scripts.history_search import (
    ALL_SOURCES,
    HistoryEntry,
    ansify,
    color,
    format_results,
    main,
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

    def test_cli_rejects_nonpositive_budgets_before_search(self) -> None:
        for option in ("--limit", "--max-chars"):
            for value in ("0", "-1"):
                with self.subTest(option=option, value=value):
                    with patch(
                        "scripts.history_search.search_history", return_value={}
                    ) as search:
                        with patch("sys.stderr"), patch("builtins.print"):
                            with self.assertRaises(SystemExit) as error:
                                main([option, value])
                        self.assertEqual(error.exception.code, 2)
                        search.assert_not_called()

    def test_cli_accepts_explicit_audit_budgets_above_sparse_defaults(self) -> None:
        with patch(
            "scripts.history_search.search_history", return_value={}
        ) as search:
            with patch("builtins.print"):
                self.assertEqual(main(["--limit", "50", "--max-chars", "500"]), 0)
        self.assertEqual(search.call_args.kwargs["limit"], 50)
        self.assertEqual(search.call_args.kwargs["max_chars"], 500)

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

    def test_codex_search_includes_active_and_default_homes(self) -> None:
        for directory, message in (
            (".codex-astra", "active profile history"),
            (".codex", "default profile history"),
        ):
            sessions = self.temp_dir / directory / "sessions"
            sessions.mkdir(parents=True)
            (sessions / "rollout-test.jsonl").write_text(json.dumps({
                "timestamp": "2026-09-08",
                "role": "user",
                "content": message,
            }) + "\n")
        with patch("pathlib.Path.home", return_value=self.temp_dir), patch.dict(
            "os.environ", {"CODEX_HOME": str(self.temp_dir / ".codex-astra")}
        ):
            results = search_codex(query="profile history")
        self.assertEqual(
            {entry.snippet for entry in results},
            {"active profile history", "default profile history"},
        )

    def test_explicit_codex_homes_are_scoped_and_aliases_are_deduplicated(self) -> None:
        profile = self.temp_dir / "custom-profile"
        sessions = profile / "sessions"
        sessions.mkdir(parents=True)
        (sessions / "rollout-test.jsonl").write_text(json.dumps({
            "timestamp": "2026-09-08",
            "type": "response_item",
            "payload": {
                "type": "message", "role": "user",
                "content": [{"type": "input_text", "text": "custom trace"}],
            },
        }) + "\n")
        alias = self.temp_dir / "profile-alias"
        alias.symlink_to(profile, target_is_directory=True)
        results = search_codex(query="custom trace", codex_homes=[profile, alias])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].snippet, "custom trace")
        self.assertEqual(results[0].metadata["codex_home"], str(profile.resolve()))

    def test_codex_profile_indexes_deduplicate_threads_and_sort_full_timestamps(self) -> None:
        homes = [self.temp_dir / "first", self.temp_dir / "second"]
        for index, home in enumerate(homes):
            home.mkdir()
            with sqlite3.connect(home / "state_5.sqlite") as con:
                con.execute("CREATE TABLE threads (id TEXT, title TEXT, first_user_message TEXT, cwd TEXT, git_branch TEXT, created_at INTEGER, archived INTEGER)")
                con.executemany("INSERT INTO threads VALUES (?, ?, ?, ?, ?, ?, ?)", [
                    ("shared", "history", "shared history", "/work", "main", 1788283000, 0),
                    (f"unique-{index}", "history", f"history {index}", "/work", "main", 1788283010 + index, 0),
                ])
        results = search_codex(query="history", codex_homes=homes)
        self.assertEqual(
            [entry.metadata["thread_id"] for entry in results],
            ["unique-1", "unique-0", "shared"],
        )

    def test_codex_mixed_index_and_rollout_profiles_sort_actual_instants(self) -> None:
        indexed = self.temp_dir / "indexed"
        indexed.mkdir()
        with sqlite3.connect(indexed / "state_5.sqlite") as con:
            con.execute("CREATE TABLE threads (id TEXT, title TEXT, first_user_message TEXT, cwd TEXT, git_branch TEXT, created_at INTEGER, archived INTEGER)")
            con.execute("INSERT INTO threads VALUES (?, ?, ?, ?, ?, ?, ?)",
                        ("indexed", "history", "indexed history", "/work", "main", 1788283000, 0))
        rollouts = self.temp_dir / "rollouts"
        (rollouts / "sessions").mkdir(parents=True)
        (rollouts / "sessions/rollout-test.jsonl").write_text(json.dumps({
            "timestamp": datetime.fromtimestamp(1788283060, timezone.utc).isoformat(),
            "role": "user", "content": "newer rollout history",
        }) + "\n")
        results = search_codex(query="history", codex_homes=[indexed, rollouts])
        self.assertEqual(
            [entry.snippet for entry in results],
            ["newer rollout history", "indexed history"],
        )

    def test_sqlite_searches_preserve_literal_path_characters(self) -> None:
        for directory in (
            "ordinary", "hash#profile", "query?profile",
            "percent%23profile", "space ü profile",
        ):
            profile = self.temp_dir / directory
            profile.mkdir()
            database = profile / "state_5.sqlite"
            with sqlite3.connect(database) as connection:
                connection.executescript("""
                    CREATE TABLE threads (
                        id TEXT, title TEXT, first_user_message TEXT, cwd TEXT,
                        git_branch TEXT, created_at INTEGER, archived INTEGER
                    );
                    INSERT INTO threads VALUES (
                        't1', 'literalpath', 'literalpath', '/fixture/project',
                        'main', 1788283033, 0
                    );
                    CREATE TABLE sessions (id TEXT, title TEXT, source TEXT);
                    INSERT INTO sessions VALUES ('s1', 'literalpath', 'fixture');
                    CREATE TABLE messages (
                        id INTEGER, session_id TEXT, timestamp INTEGER,
                        role TEXT, content TEXT, tool_name TEXT, tool_calls TEXT
                    );
                    INSERT INTO messages VALUES (
                        1, 's1', 1788283033, 'user', 'literalpath', NULL, NULL
                    );
                    CREATE TABLE conversation_summaries (
                        conversation_id TEXT, title TEXT, preview TEXT,
                        step_count INTEGER, last_modified_time TEXT,
                        workspace_uris TEXT, agent_name TEXT, killed INTEGER
                    );
                    INSERT INTO conversation_summaries VALUES (
                        'c1', 'literalpath', 'literalpath', 1,
                        '2026-09-01T12:00:00Z', '/fixture/project', 'agy', 0
                    );
                """)
            before_bytes = database.read_bytes()
            before_paths = set(self.temp_dir.rglob("*"))
            searches = (
                (search_codex, {"codex_homes": [profile]}),
                (search_codex, {
                    "db_path": database, "sessions_dir": profile / "sessions",
                }),
                (search_hermes, {"db_path": database}),
                (search_agy, {
                    "db_path": database, "brain_dir": profile / "brain",
                    "history_file": profile / "history.jsonl",
                }),
            )
            for search, options in searches:
                with self.subTest(
                    directory=directory, search=search.__name__, options=options
                ):
                    results = search(query="literalpath", **options)
                    self.assertEqual(len(results), 1)
                    self.assertEqual(results[0].snippet, "literalpath")
                    self.assertEqual(database.read_bytes(), before_bytes)
                    self.assertEqual(set(self.temp_dir.rglob("*")), before_paths)

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

    def test_codex_search_profile_isolation_and_sibling_inference(self) -> None:
        fake_home = self.temp_dir / "fake_home"
        real_sessions = fake_home / ".codex" / "sessions" / "sub"
        real_sessions.mkdir(parents=True)
        (real_sessions / "rollout-secret.jsonl").write_text(
            json.dumps({"role": "user", "content": "SECRET_FROM_REAL_HOME_SESSIONS"}) + "\n"
        )
        real_db = fake_home / ".codex" / "state_5.sqlite"
        real_db.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(real_db)) as con:
            con.execute("CREATE TABLE threads (id TEXT, title TEXT, first_user_message TEXT, cwd TEXT, git_branch TEXT, created_at INTEGER, archived INTEGER)")
            con.execute("INSERT INTO threads VALUES ('t1', 'sec', 'SECRET_FROM_REAL_DB', '/p', 'm', 1788283033, 0)")

        # 1. Explicit db only with empty db must not search real home sessions
        isolated_profile = self.temp_dir / "isolated_profile"
        isolated_profile.mkdir(parents=True)
        empty_db = isolated_profile / "empty_state_5.sqlite"
        with sqlite3.connect(str(empty_db)) as con:
            con.execute("CREATE TABLE threads (id TEXT, title TEXT, first_user_message TEXT, cwd TEXT, git_branch TEXT, created_at INTEGER, archived INTEGER)")

        with patch("pathlib.Path.home", return_value=fake_home):
            results = search_codex(query="SECRET_FROM_REAL_HOME_SESSIONS", db_path=empty_db)
            self.assertEqual(len(results), 0)

        # 2. Explicit sessions only with empty sessions must not query default database
        empty_sessions = isolated_profile / "empty_sessions"
        empty_sessions.mkdir()
        with patch("pathlib.Path.home", return_value=fake_home):
            results = search_codex(query="SECRET_FROM_REAL_DB", sessions_dir=empty_sessions)
            self.assertEqual(len(results), 0)

        # 3. Sibling inference: explicit db finds rollouts in sibling sessions/ directory
        sibling_sessions = isolated_profile / "sessions" / "rollouts"
        sibling_sessions.mkdir(parents=True)
        (sibling_sessions / "rollout-sibling.jsonl").write_text(
            json.dumps({"role": "user", "content": "FIND_IN_SIBLING_SESSIONS"}) + "\n"
        )
        with patch("pathlib.Path.home", return_value=fake_home):
            sibling_results = search_codex(query="FIND_IN_SIBLING_SESSIONS", db_path=empty_db)
            self.assertEqual(len(sibling_results), 1)
            self.assertIn("FIND_IN_SIBLING_SESSIONS", sibling_results[0].snippet)

    def test_codex_search_empty_codex_home_does_not_become_cwd_nor_suppress_defaults(self) -> None:
        fake_home = self.temp_dir / "fake_home_default"
        default_sessions = fake_home / ".codex" / "sessions" / "sub"
        default_sessions.mkdir(parents=True)
        (default_sessions / "rollout.jsonl").write_text(
            json.dumps({"role": "user", "content": "FROM_DEFAULT_HOME_PROFILE"}) + "\n"
        )

        cwd_dir = self.temp_dir / "cwd_dir"
        cwd_sessions = cwd_dir / "sessions"
        cwd_sessions.mkdir(parents=True)
        (cwd_sessions / "rollout-cwd.jsonl").write_text(
            json.dumps({"role": "user", "content": "SECRET_FROM_CWD"}) + "\n"
        )

        with patch.dict("os.environ", {"CODEX_HOME": ""}), patch("pathlib.Path.home", return_value=fake_home), patch("os.getcwd", return_value=str(cwd_dir)):
            results_empty = search_codex(query="FROM_DEFAULT_HOME_PROFILE", codex_homes=["", "   "])
            self.assertEqual(len(results_empty), 1)
            self.assertIn("FROM_DEFAULT_HOME_PROFILE", results_empty[0].snippet)

            results_cwd = search_codex(query="SECRET_FROM_CWD", codex_homes=[""])
            self.assertEqual(len(results_cwd), 0)

    def test_codex_model_metadata_attribution_per_turn(self) -> None:
        profile_dir = self.temp_dir / "model_audit_profile"
        sessions_dir = profile_dir / "sessions" / "sub"
        sessions_dir.mkdir(parents=True)

        rollout_file = sessions_dir / "rollout-model-change.jsonl"
        lines = [
            json.dumps({"type": "session_meta", "payload": {"model": "initial-meta-model"}}),
            json.dumps({"type": "turn_context", "payload": {"turn_id": "1", "model": "gpt-5.1-codex"}}),
            json.dumps({"type": "response_item", "payload": {"role": "user", "content": "Question in turn 1"}}),
            json.dumps({"type": "turn_context", "payload": {"turn_id": "2", "model": "gpt-5.3-codex"}}),
            json.dumps({"type": "response_item", "payload": {"role": "user", "content": "Question in turn 2"}}),
        ]
        rollout_file.write_text("\n".join(lines) + "\n")

        results = search_codex(query="Question in turn", sessions_dir=sessions_dir, limit=10)
        self.assertEqual(len(results), 2)
        turn1 = next(r for r in results if "turn 1" in r.snippet)
        turn2 = next(r for r in results if "turn 2" in r.snippet)
        self.assertEqual(turn1.metadata.get("model"), "gpt-5.1-codex")
        self.assertEqual(turn1.metadata.get("model_source"), "turn_context")
        self.assertEqual(turn2.metadata.get("model"), "gpt-5.3-codex")
        self.assertEqual(turn2.metadata.get("model_source"), "turn_context")

        # Database search with model column
        db_path = profile_dir / "state_5.sqlite"
        with sqlite3.connect(str(db_path)) as con:
            con.execute("CREATE TABLE threads (id TEXT, title TEXT, first_user_message TEXT, cwd TEXT, git_branch TEXT, created_at INTEGER, archived INTEGER, model TEXT)")
            con.execute("INSERT INTO threads VALUES ('t_model', 'Model Thread', 'Database search query with model', '/proj', 'main', 1788283033, 0, 'claude-3-7-sonnet')")
        db_results = search_codex(query="Database search query with model", db_path=db_path)
        self.assertEqual(len(db_results), 1)
        self.assertEqual(db_results[0].metadata.get("model"), "claude-3-7-sonnet")
        self.assertEqual(db_results[0].metadata.get("model_source"), "database")


if __name__ == "__main__":
    unittest.main()
