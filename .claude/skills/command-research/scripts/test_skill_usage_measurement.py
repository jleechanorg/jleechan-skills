import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from count_command_usage_unified import (
    load_known_skills,
    scan_claude_skill_invocations,
    scan_codex_skill_invocations,
    scan_hermes_skill_invocations,
    scan_skill_usage,
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
            connection.commit()
            connection.close()

            result = scan_codex_skill_invocations(
                {"alpha"}, cutoff=0, db_path=database
            )

            self.assertEqual(result["human"]["alpha"], 1)
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
            self.assertIn("provenance", result["diagnostic"])

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
                ],
            )
            connection.commit()
            connection.close()

            result = scan_hermes_skill_invocations(
                {"alpha"}, cutoff=0, db_path=database
            )

            self.assertEqual(result["human"]["alpha"], 1)
            self.assertEqual(result["agent"]["alpha"], 1)
            self.assertEqual(result["record_types"]["messages.tool_name.Skill"], 1)
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
            self.assertIn("messages", result["diagnostic"])

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


if __name__ == "__main__":
    unittest.main()
