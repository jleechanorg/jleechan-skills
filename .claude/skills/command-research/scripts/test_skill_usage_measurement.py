import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from count_command_usage_unified import (
    load_known_skills,
    scan_claude_skill_invocations,
    scan_codex_skill_invocations,
    scan_hermes_skill_invocations,
    scan_skill_usage,
    _filter_skill_payload,
    _skill_destinations,
    timestamp_seconds,
)


class SkillUsageMeasurementTest(unittest.TestCase):
    def test_skill_roots_include_codex_and_deduplicate_symlinked_entries(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            claude_skill = root / ".claude" / "skills" / "shared" / "SKILL.md"
            codex_skill = root / ".codex" / "skills" / "codex-only" / "SKILL.md"
            claude_skill.parent.mkdir(parents=True)
            codex_skill.parent.mkdir(parents=True)
            claude_skill.write_text("---\nname: shared\n---\n", encoding="utf-8")
            codex_skill.write_text("---\nname: codex-only\n---\n", encoding="utf-8")
            link = root / ".codex" / "skills" / "shared" / "SKILL.md"
            link.parent.mkdir()
            link.symlink_to(claude_skill)

            skills = load_known_skills([root / ".claude", root / ".codex"])

            self.assertEqual(skills, {"shared", "codex-only"})

    def test_claude_counts_only_explicit_skill_tool_calls(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            session = Path(tmpdir) / "session.jsonl"
            records = [
                {
                    "type": "assistant",
                    "isSidechain": False,
                    "timestamp": "2026-08-28T00:00:00Z",
                    "message": {
                        "content": [
                            {"type": "text", "text": "See /alpha in the prompt."},
                            {
                                "type": "tool_use",
                                "name": "Skill",
                                "input": {"skill": "alpha"},
                            },
                        ]
                    },
                },
                {
                    "type": "assistant",
                    "isSidechain": True,
                    "timestamp": "2026-08-28T00:01:00Z",
                    "message": {
                        "content": [
                            {
                                "type": "tool_use",
                                "name": "Skill",
                                "input": {"skill": "alpha"},
                            }
                        ]
                    },
                },
                {
                    "type": "assistant",
                    "isSidechain": False,
                    "timestamp": "2026-08-28T00:02:00Z",
                    "message": {
                        "content": [
                            {"type": "text", "text": "Read /alpha/SKILL.md."}
                        ]
                    },
                },
            ]
            session.write_text(
                "".join(json.dumps(record) + "\n" for record in records),
                encoding="utf-8",
            )

            result = scan_claude_skill_invocations(
                {"alpha"}, cutoff=0, projects_dir=tmpdir
            )

            self.assertEqual(result["human"]["alpha"], 1)
            self.assertEqual(result["agent"]["alpha"], 1)
            self.assertEqual(result["unknown"]["alpha"], 0)
            self.assertEqual(result["record_types"]["assistant.tool_use.Skill"], 2)

    def test_claude_missing_projects_directory_returns_diagnostic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = scan_claude_skill_invocations(
                {"alpha"}, cutoff=0, projects_dir=Path(tmpdir) / "missing"
            )

            self.assertFalse(result["supported"])
            self.assertEqual(result["status"], "unsupported")
            self.assertIn("projects directory", result["diagnostic"])

    def test_claude_existing_empty_store_is_distinct_from_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = scan_claude_skill_invocations(
                {"alpha"}, cutoff=0, projects_dir=tmpdir
            )

            self.assertTrue(result["supported"])
            self.assertEqual(result["status"], "supported-empty")
            self.assertIn("no explicit Skill", result["diagnostic"])

    def test_claude_unreadable_record_reports_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            session = Path(tmpdir) / "session.jsonl"
            session.write_text("{}\n", encoding="utf-8")
            with patch("builtins.open", side_effect=PermissionError("denied")):
                result = scan_claude_skill_invocations(
                    {"alpha"}, cutoff=0, projects_dir=tmpdir
                )

            self.assertFalse(result["supported"])
            self.assertEqual(result["status"], "error")
            self.assertIn("Claude history read error", result["diagnostic"])

    def test_claude_malformed_records_are_counted_and_empty_store_is_explicit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            session = Path(tmpdir) / "session.jsonl"
            session.write_text(
                "\n".join(
                    [
                        "{not-json",
                        json.dumps({"type": "assistant", "timestamp": "NaN"}),
                        json.dumps({"type": "assistant", "timestamp": "2026-08-28T00:00:00Z"}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            result = scan_claude_skill_invocations(
                {"alpha"}, cutoff=0, projects_dir=tmpdir
            )

            self.assertEqual(result["malformed"]["json"], 1)
            self.assertEqual(result["malformed"]["timestamp"], 1)
            self.assertEqual(result["status"], "supported-empty")
            self.assertIn("malformed Claude", result["diagnostic"])

    def test_codex_ignores_slash_text_and_counts_explicit_skill_call(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            human_rollout = root / "human.jsonl"
            human_rollout.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "type": "event_msg",
                                "payload": {
                                    "type": "item_completed",
                                    "item": {
                                        "type": "UserMessage",
                                        "content": [{"type": "text", "text": "/alpha"}],
                                    },
                                },
                                "timestamp": "2026-08-28T00:00:00Z",
                            }
                        ),
                        json.dumps(
                            {
                                "type": "response_item",
                                "payload": {
                                    "type": "custom_tool_call",
                                    "name": "Skill",
                                    "input": {"skill": "alpha"},
                                },
                                "timestamp": "2026-08-28T00:00:01Z",
                            }
                        ),
                        json.dumps(
                            {
                                "type": "response_item",
                                "payload": {
                                    "type": "message",
                                    "content": [
                                        {
                                            "type": "tool_call",
                                            "function": {
                                                "name": "Skill",
                                                "arguments": {"skill": "alpha"},
                                            },
                                        }
                                    ],
                                },
                                "timestamp": "2026-08-28T00:00:02Z",
                            }
                        ),
                        json.dumps(
                            {
                                "type": "response_item",
                                "payload": {
                                    "type": "custom_tool_call",
                                    "name": "Skill",
                                    "input": {"skill": "alpha"},
                                },
                                "timestamp": "2026-08-28T00:00:01Z",
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            database = root / "state.sqlite"
            connection = sqlite3.connect(database)
            connection.execute(
                "CREATE TABLE threads (rollout_path TEXT, thread_source TEXT, "
                "updated_at_ms INTEGER)"
            )
            connection.execute(
                "INSERT INTO threads VALUES (?, ?, ?)",
                (str(human_rollout), "user", 1_800_000_000_000),
            )
            connection.execute(
                "INSERT INTO threads VALUES (?, ?, ?)",
                (str(human_rollout), "user", 1_800_000_000_000),
            )
            connection.commit()
            connection.close()

            result = scan_codex_skill_invocations(
                {"alpha"}, cutoff=0, db_path=database
            )

            self.assertEqual(result["human"]["alpha"], 2)
            self.assertEqual(result["agent"]["alpha"], 0)
            self.assertEqual(result["record_types"]["response_item.custom_tool_call.Skill"], 1)

    def test_codex_unsupported_schema_returns_diagnostic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            database = Path(tmpdir) / "state.sqlite"
            connection = sqlite3.connect(database)
            connection.commit()
            connection.close()

            result = scan_codex_skill_invocations(
                {"alpha"}, cutoff=0, db_path=database
            )

            self.assertFalse(result["supported"])
            self.assertEqual(result["status"], "unsupported")
            self.assertIn("threads", result["diagnostic"])

    def test_codex_missing_provenance_column_returns_diagnostic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            database = Path(tmpdir) / "state.sqlite"
            connection = sqlite3.connect(database)
            connection.execute("CREATE TABLE threads (rollout_path TEXT)")
            connection.commit()
            connection.close()

            result = scan_codex_skill_invocations(
                {"alpha"}, cutoff=0, db_path=database
            )

            self.assertFalse(result["supported"])
            self.assertEqual(result["status"], "unsupported")
            self.assertIn("provenance", result["diagnostic"])

    def test_codex_existing_empty_store_is_distinct_from_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            database = Path(tmpdir) / "state.sqlite"
            connection = sqlite3.connect(database)
            connection.execute(
                "CREATE TABLE threads (rollout_path TEXT, thread_source TEXT)"
            )
            connection.commit()
            connection.close()

            result = scan_codex_skill_invocations(
                {"alpha"}, cutoff=0, db_path=database
            )

            self.assertTrue(result["supported"])
            self.assertEqual(result["status"], "supported-empty")
            self.assertIn("no explicit Skill", result["diagnostic"])

    def test_codex_unreadable_store_reports_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            unreadable_path = Path(tmpdir) / "state.sqlite"
            unreadable_path.mkdir()

            result = scan_codex_skill_invocations(
                {"alpha"}, cutoff=0, db_path=unreadable_path
            )

            self.assertFalse(result["supported"])
            self.assertEqual(result["status"], "error")
            self.assertIn("Codex history read error", result["diagnostic"])

    def test_codex_recent_event_is_not_hidden_by_stale_thread_updated_at(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            rollout = root / "recent.jsonl"
            rollout.write_text(
                json.dumps(
                    {
                        "type": "response_item",
                        "payload": {
                            "type": "custom_tool_call",
                            "name": "Skill",
                            "input": {"skill": "alpha"},
                        },
                        "timestamp": "2026-08-28T00:00:01Z",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            database = root / "state.sqlite"
            connection = sqlite3.connect(database)
            connection.execute(
                "CREATE TABLE threads (rollout_path TEXT, thread_source TEXT, updated_at_ms INTEGER)"
            )
            connection.execute(
                "INSERT INTO threads VALUES (?, ?, ?)",
                (str(rollout), "user", 1),
            )
            connection.commit()
            connection.close()

            result = scan_codex_skill_invocations(
                {"alpha"}, cutoff=1_700_000_000, db_path=database
            )

            self.assertEqual(result["human"]["alpha"], 1)

    def test_codex_malformed_records_are_counted_and_empty_store_is_explicit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            rollout = root / "malformed.jsonl"
            rollout.write_text(
                "\n".join(
                    [
                        "{not-json",
                        json.dumps({"type": "response_item", "timestamp": "NaN"}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            database = root / "state.sqlite"
            connection = sqlite3.connect(database)
            connection.execute(
                "CREATE TABLE threads (rollout_path TEXT, thread_source TEXT)"
            )
            connection.execute(
                "INSERT INTO threads VALUES (?, ?)", (str(rollout), "user")
            )
            connection.commit()
            connection.close()

            result = scan_codex_skill_invocations(
                {"alpha"}, cutoff=0, db_path=database
            )

            self.assertEqual(result["malformed"]["json"], 1)
            self.assertEqual(result["malformed"]["timestamp"], 1)
            self.assertEqual(result["status"], "supported-empty")
            self.assertIn("malformed Codex", result["diagnostic"])

    def test_non_finite_cutoff_and_timestamp_fail_closed_diagnostically(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = scan_claude_skill_invocations(
                {"alpha"}, cutoff=float("nan"), projects_dir=tmpdir
            )

            self.assertEqual(result["malformed"]["cutoff"], 1)
            self.assertEqual(result["status"], "invalid-input")
            self.assertIn("cutoff", result["diagnostic"])
            self.assertIsNone(timestamp_seconds(float("nan")))
            self.assertIsNone(timestamp_seconds(float("inf")))

    def test_hermes_counts_tool_name_not_slash_text(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            database = Path(tmpdir) / "state.db"
            connection = sqlite3.connect(database)
            connection.execute(
                "CREATE TABLE sessions (id TEXT PRIMARY KEY, source TEXT, user_id TEXT, "
                "parent_session_id TEXT)"
            )
            connection.execute(
                "CREATE TABLE messages (session_id TEXT, role TEXT, content TEXT, "
                "tool_calls TEXT, tool_name TEXT, timestamp REAL)"
            )
            connection.executemany(
                "INSERT INTO sessions VALUES (?, ?, ?, ?)",
                [("human", "cli", "operator", None), ("agent", "subagent", "worker", "human")],
            )
            connection.executemany(
                "INSERT INTO messages VALUES (?, ?, ?, ?, ?, ?)",
                [
                    ("human", "user", "/alpha", None, None, 1_800_000_000),
                    (
                        "human",
                        "assistant",
                        "",
                        json.dumps([{"arguments": {"skill": "alpha"}}]),
                        "Skill",
                        1_800_000_001,
                    ),
                    (
                        "agent",
                        "assistant",
                        "",
                        json.dumps([{"name": "Skill", "arguments": {"skill": "alpha"}}]),
                        None,
                        1_800_000_002,
                    ),
                    (
                        "human",
                        "assistant",
                        "",
                        json.dumps({"arguments": {"skill": "alpha"}}),
                        "Skill",
                        1_800_000_003,
                    ),
                ],
            )
            connection.execute(
                "INSERT INTO messages VALUES (?, ?, ?, ?, ?, ?)",
                (
                    "human", "assistant", "",
                    json.dumps([{"arguments": {"skill": "alpha"}}]),
                    "Skill", 1_800_000_001,
                ),
            )
            connection.commit()
            connection.close()

            result = scan_hermes_skill_invocations(
                {"alpha"}, cutoff=0, db_path=database
            )

            self.assertEqual(result["human"]["alpha"], 2)
            self.assertEqual(result["agent"]["alpha"], 1)
            self.assertEqual(result["record_types"]["messages.tool_name.Skill"], 2)
            self.assertEqual(result["record_types"]["messages.tool_calls.Skill"], 1)

    def test_hermes_unsupported_schema_returns_diagnostic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            database = Path(tmpdir) / "state.db"
            connection = sqlite3.connect(database)
            connection.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY)")
            connection.commit()
            connection.close()

            result = scan_hermes_skill_invocations(
                {"alpha"}, cutoff=0, db_path=database
            )

            self.assertFalse(result["supported"])
            self.assertEqual(result["status"], "unsupported")
            self.assertIn("messages", result["diagnostic"])

    def test_hermes_malformed_data_reports_counters_and_keeps_safe_records(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            database = Path(tmpdir) / "state.db"
            connection = sqlite3.connect(database)
            connection.execute(
                "CREATE TABLE sessions (id TEXT PRIMARY KEY, source TEXT, user_id TEXT, "
                "parent_session_id TEXT)"
            )
            connection.execute(
                "CREATE TABLE messages (session_id TEXT, role TEXT, content TEXT, "
                "tool_calls TEXT, tool_name TEXT, timestamp REAL)"
            )
            connection.execute(
                "INSERT INTO sessions VALUES (?, ?, ?, ?)",
                ("human", "cli", "operator", None),
            )
            connection.executemany(
                "INSERT INTO messages VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (
                        "human", "assistant", "", json.dumps({"skill": "alpha"}),
                        "Skill", 1_800_000_000,
                    ),
                    (
                        "human", "assistant", "", "{not-json", "Skill", "not-a-time",
                    ),
                    (
                        "human", "assistant", "", "{not-json", None, 1_800_000_002,
                    ),
                ],
            )
            connection.commit()
            connection.close()

            result = scan_hermes_skill_invocations(
                {"alpha"}, cutoff=0, db_path=database
            )

            self.assertEqual(result["human"]["alpha"], 1)
            # The malformed timestamp row fails closed before its malformed
            # JSON payload is inspected.
            self.assertEqual(result["malformed"]["json"], 1)
            self.assertEqual(result["malformed"]["timestamp"], 1)
            self.assertEqual(
                result["diagnostic"],
                "malformed Hermes records: json=1, timestamp=1",
            )

    def test_hermes_stringified_malformed_arguments_are_safe_and_diagnosed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            database = Path(tmpdir) / "state.db"
            connection = sqlite3.connect(database)
            connection.execute(
                "CREATE TABLE sessions (id TEXT PRIMARY KEY, source TEXT, user_id TEXT, "
                "parent_session_id TEXT)"
            )
            connection.execute(
                "CREATE TABLE messages (session_id TEXT, role TEXT, content TEXT, "
                "tool_calls TEXT, tool_name TEXT, timestamp REAL)"
            )
            connection.execute(
                "INSERT INTO sessions VALUES (?, ?, ?, ?)",
                ("human", "cli", "operator", None),
            )
            connection.execute(
                "INSERT INTO messages VALUES (?, ?, ?, ?, ?, ?)",
                (
                    "human", "assistant", "", json.dumps(
                        [{"id": "bad", "name": "Skill", "arguments": "{not-json"}]
                    ), None, 1_800_000_000,
                ),
            )
            connection.commit()
            connection.close()

            result = scan_hermes_skill_invocations(
                {"alpha"}, cutoff=0, db_path=database
            )

            self.assertEqual(result["human"], {})
            self.assertEqual(result["malformed"]["json"], 1)
            self.assertIn("malformed Hermes", result["diagnostic"])

    def test_hermes_duplicate_rows_with_same_call_id_count_once(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            database = Path(tmpdir) / "state.db"
            connection = sqlite3.connect(database)
            connection.execute(
                "CREATE TABLE sessions (id TEXT PRIMARY KEY, source TEXT, user_id TEXT, "
                "parent_session_id TEXT)"
            )
            connection.execute(
                "CREATE TABLE messages (session_id TEXT, role TEXT, content TEXT, "
                "tool_calls TEXT, tool_name TEXT, timestamp REAL)"
            )
            connection.execute(
                "INSERT INTO sessions VALUES (?, ?, ?, ?)",
                ("human", "cli", "operator", None),
            )
            payload = json.dumps(
                [{"id": "same-call", "name": "Skill", "arguments": {"skill": "alpha"}}]
            )
            connection.executemany(
                "INSERT INTO messages VALUES (?, ?, ?, ?, ?, ?)",
                [
                    ("human", "assistant", "", payload, None, 1_800_000_000),
                    ("human", "assistant", "", payload, "Skill", 1_800_000_000),
                ],
            )
            connection.commit()
            connection.close()

            result = scan_hermes_skill_invocations(
                {"alpha"}, cutoff=0, db_path=database
            )

            self.assertEqual(result["human"]["alpha"], 1)

    def test_hermes_preserves_id_through_nested_stringified_arguments_and_timestamps(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            database = Path(tmpdir) / "state.db"
            connection = sqlite3.connect(database)
            connection.execute(
                "CREATE TABLE sessions (id TEXT PRIMARY KEY, source TEXT, user_id TEXT, "
                "parent_session_id TEXT)"
            )
            connection.execute(
                "CREATE TABLE messages (session_id TEXT, role TEXT, content TEXT, "
                "tool_calls TEXT, tool_name TEXT, timestamp REAL)"
            )
            connection.execute(
                "INSERT INTO sessions VALUES (?, ?, ?, ?)",
                ("human", "cli", "operator", None),
            )
            payload = json.dumps(
                [{
                    "id": "durable-call",
                    "function": {
                        "name": "Skill",
                        "arguments": json.dumps({"input": json.dumps({"skill": "alpha"})}),
                    },
                }]
            )
            connection.executemany(
                "INSERT INTO messages VALUES (?, ?, ?, ?, ?, ?)",
                [
                    ("human", "assistant", "", payload, None, 1_800_000_000),
                    ("human", "assistant", "", payload, None, 1_800_000_001),
                ],
            )
            connection.commit()
            connection.close()

            result = scan_hermes_skill_invocations(
                {"alpha"}, cutoff=0, db_path=database
            )

            self.assertEqual(result["human"]["alpha"], 1)

    def test_aggregate_preserves_store_schema_diagnostics(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            codex_db = Path(tmpdir) / "codex.sqlite"
            hermes_db = Path(tmpdir) / "hermes.db"
            sqlite3.connect(codex_db).close()
            sqlite3.connect(hermes_db).close()

            result = scan_skill_usage(
                {"alpha"},
                cutoff=0,
                claude_projects_dir=str(Path(tmpdir) / "missing-claude"),
                codex_db_path=codex_db,
                hermes_db_path=hermes_db,
            )

            self.assertFalse(result["stores"]["codex"]["supported"])
            self.assertFalse(result["stores"]["hermes"]["supported"])
            self.assertTrue(result["stores"]["codex"]["diagnostic"])
            self.assertTrue(result["stores"]["hermes"]["diagnostic"])

    def test_skill_mode_destination_filtering_is_explicit(self):
        payload = {
            "human": {"alpha": 2},
            "agent": {"alpha": 1},
            "unknown": {"beta": 3},
            "total": {"alpha": 3, "beta": 3},
            "stores": {
                "claude": {"human": {"alpha": 2}, "agent": {"alpha": 1}, "unknown": {}}
            },
        }
        _filter_skill_payload(payload, _skill_destinations(human_only=True))

        self.assertEqual(payload["human"], {"alpha": 2})
        self.assertEqual(payload["agent"], {})
        self.assertEqual(payload["unknown"], {})
        self.assertEqual(payload["total"], {"alpha": 2})
        self.assertEqual(payload["selected_destinations"], ["human"])
        self.assertEqual(payload["stores"]["claude"]["agent"], {})
        with self.assertRaises(ValueError):
            _skill_destinations(human_only=True, agent_only=True)


if __name__ == "__main__":
    unittest.main()
