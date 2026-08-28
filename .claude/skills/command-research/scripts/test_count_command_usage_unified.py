import json
import os
import sqlite3
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from count_command_usage_unified import (
    is_imperative_invocation,
    is_listing_or_report,
    load_known_commands,
    scan_claude,
    scan_codex,
)


class TestCountCommandUsageUnified(unittest.TestCase):
    def setUp(self):
        self.known_cmds = {
            "fixpr",
            "copilot",
            "es",
            "er",
            "execute",
            "green",
            "advice",
            "repro",
            "smoke",
            "ms",
            "f",
        }

    def _write_session_and_scan(
        self,
        msg: str,
        is_subagent: bool = True,
        prompt_source: str = "agent",
        role: str = "user",
        msg_type: str = "user",
    ):
        with tempfile.TemporaryDirectory() as tmpdir:
            proj_dir = os.path.join(tmpdir, "test-project")
            os.makedirs(proj_dir)
            session_file = os.path.join(proj_dir, "session_test.jsonl")
            with open(session_file, "w", encoding="utf-8") as f:
                header = {"type": "system"}
                if is_subagent:
                    header["isSidechain"] = True
                f.write(json.dumps(header) + "\n")

                record = {
                    "type": msg_type,
                    "role": role,
                    "message": {"content": msg},
                    "promptSource": prompt_source if not is_subagent else "agent",
                }
                f.write(json.dumps(record) + "\n")
            return scan_claude(self.known_cmds, cutoff=0, projects_dir=tmpdir)

    def test_skill_file_dump_not_counted(self):
        msg = (
            "Base directory for this skill: /Users/jleechan/.claude/skills/fixpr\n\n"
            "# /fixpr — PR Fix Analysis\n"
            "Analyze PR failure reasons and output recommendations."
        )
        h, a = self._write_session_and_scan(msg, is_subagent=True)
        self.assertEqual(a["fixpr"], 0)

    def test_readme_export_prompt_not_counted(self):
        msg = (
            "You are updating the README for jleechanorg/claude-commands\n"
            "- /copilot: Autonomous PR pairing orchestrator\n"
            "- /fixpr: Automated PR remediation agent\n"
            "- /es: Evidence standards"
        )
        h, a = self._write_session_and_scan(msg, is_subagent=True)
        self.assertEqual(a["copilot"], 0)

    def test_report_listing_not_counted(self):
        msg = "Most agent-driven: /es, /er, /green, /advice, /repro"
        h, a = self._write_session_and_scan(msg, is_subagent=True)
        for cmd in ["es", "er", "green", "advice", "repro"]:
            self.assertEqual(a[cmd], 0, f"Expected 0 agent count for {cmd}, got {a[cmd]}")
            self.assertEqual(h[cmd], 0, f"Expected 0 human count for {cmd}, got {h[cmd]}")

    def test_markdown_table_listing_not_counted(self):
        msg = (
            "| Rank | Command | Total |\n"
            "|---|---|---|\n"
            "| 1 | /execute | 7136 |\n"
            "| 2 | /copilot | 6203 |"
        )
        h, a = self._write_session_and_scan(msg, is_subagent=True)
        self.assertEqual(a["execute"], 0)
        self.assertEqual(a["copilot"], 0)

    def test_stray_mention_not_counted(self):
        msg = "...stale Green Gate — need fresh push. /fixpr codex automation present in #7592 history..."
        h, a = self._write_session_and_scan(msg, is_subagent=True)
        self.assertEqual(a["fixpr"], 0)

    def test_boilerplate_narrative_not_counted(self):
        msg = (
            "...A same-model /er + /advice pass (both Claude) signed off on a 'fixed' "
            "production bug; a single codex adversarial pass immediately found 5 real defects..."
        )
        h, a = self._write_session_and_scan(msg, is_subagent=True)
        self.assertEqual(a["er"], 0)
        self.assertEqual(a["advice"], 0)

    def test_genuine_imperative_invocation_counted(self):
        msg = "run /fixpr on this PR to resolve the CI failures"
        h, a = self._write_session_and_scan(msg, is_subagent=True)
        self.assertEqual(a["fixpr"], 1)

    def test_command_tag_always_counted(self):
        msg = "<command-name>/fixpr</command-name>"
        h, a = self._write_session_and_scan(msg, is_subagent=True)
        self.assertEqual(a["fixpr"], 1)

    def test_command_at_start_of_line_counted(self):
        msg = "/copilot review this branch"
        h, a = self._write_session_and_scan(msg, is_subagent=True)
        self.assertEqual(a["copilot"], 1)

    def test_archived_commands_are_known_scan_targets(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            command = root / "commands_archive/2026-retired/velocity.md"
            command.parent.mkdir(parents=True)
            command.write_text("# /velocity\n", encoding="utf-8")

            known = load_known_commands([root])

            self.assertIn("velocity", known)

    def test_claude_scan_applies_cutoff_to_event_timestamp(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "project"
            project.mkdir()
            session = project / "session.jsonl"
            records = [
                {"type": "system", "timestamp": "2026-07-01T00:00:00Z"},
                {
                    "type": "user",
                    "message": {"content": "/velocity old"},
                    "promptSource": "typed",
                    "timestamp": "2026-07-01T00:00:00Z",
                },
                {
                    "type": "user",
                    "message": {"content": "/velocity recent"},
                    "promptSource": "typed",
                    "timestamp": "2026-08-20T00:00:00Z",
                },
            ]
            session.write_text(
                "".join(json.dumps(record) + "\n" for record in records),
                encoding="utf-8",
            )
            cutoff = datetime(2026, 8, 1, tzinfo=UTC).timestamp()

            human, _ = scan_claude({"velocity"}, cutoff, tmpdir)

            self.assertEqual(human["velocity"], 1)

    def test_codex_scan_applies_cutoff_to_thread_timestamp(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            database = Path(tmpdir) / "state.sqlite"
            rollout = Path(tmpdir) / "rollout.jsonl"
            rollout.write_text(
                "".join(
                    json.dumps(record) + "\n"
                    for record in [
                        {
                            "timestamp": "2026-07-01T00:00:00Z",
                            "type": "event_msg",
                            "payload": {
                                "type": "item_completed",
                                "item": {
                                    "type": "UserMessage",
                                    "content": [{"type": "text", "text": "/velocity old"}],
                                },
                            },
                        },
                        {
                            "timestamp": "2026-08-20T00:00:00Z",
                            "type": "event_msg",
                            "payload": {
                                "type": "item_completed",
                                "item": {
                                    "type": "UserMessage",
                                    "content": [
                                        {"type": "text", "text": "/velocity recent"}
                                    ],
                                },
                            },
                        },
                    ]
                ),
                encoding="utf-8",
            )
            subagent_rollout = Path(tmpdir) / "subagent-rollout.jsonl"
            subagent_rollout.write_text(
                json.dumps(
                    {
                        "timestamp": "2026-08-20T00:00:00Z",
                        "type": "event_msg",
                        "payload": {
                            "type": "item_completed",
                            "item": {
                                "type": "UserMessage",
                                "content": [
                                    {"type": "text", "text": "/velocity delegated"}
                                ],
                            },
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            connection = sqlite3.connect(database)
            connection.execute(
                "CREATE TABLE threads (rollout_path TEXT, first_user_message TEXT, "
                "has_user_event INTEGER, thread_source TEXT, created_at_ms INTEGER, "
                "updated_at_ms INTEGER)"
            )
            connection.executemany(
                "INSERT INTO threads VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (
                        str(rollout),
                        "/velocity old",
                        0,
                        "user",
                        1_700_000_000_000,
                        1_800_000_000_000,
                    ),
                    (
                        str(subagent_rollout),
                        "/velocity delegated",
                        0,
                        "subagent",
                        1_800_000_000_000,
                        1_800_000_000_000,
                    ),
                ],
            )
            connection.commit()
            connection.close()

            cutoff = datetime(2026, 8, 1, tzinfo=UTC).timestamp()
            human, agent, unknown, sources = scan_codex(
                {"velocity"}, cutoff=cutoff, db_path=database
            )

            self.assertEqual(human["velocity"], 1)
            self.assertEqual(agent["velocity"], 1)
            self.assertEqual(unknown["velocity"], 0)
            self.assertEqual(sources, {"user": 1, "subagent": 1})

    def test_scan_codex_fails_closed_without_thread_source(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            database = Path(tmpdir) / "state.sqlite"
            connection = sqlite3.connect(database)
            connection.execute("CREATE TABLE threads (rollout_path TEXT)")
            connection.commit()
            connection.close()

            with self.assertRaisesRegex(
                RuntimeError, "Failed to scan Codex history database"
            ):
                scan_codex({"velocity"}, cutoff=0, db_path=database)


if __name__ == "__main__":
    unittest.main()
