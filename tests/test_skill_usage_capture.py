from __future__ import annotations

import datetime as dt
import json
import sqlite3
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from scripts.capture_command_skill_usage import (
    _extract_codex_jsonl,
    _inventory_paths,
    capture,
    extract_claude_telemetry,
    extract_codex_telemetry,
    extract_skill_read_events,
    skill_inventory,
)
from scripts.skill_read_telemetry import _shell_read_paths

STAMP = dt.datetime(2026, 9, 1, tzinfo=dt.timezone.utc)
WINDOW_START = STAMP - dt.timedelta(days=1)
WINDOW_END = STAMP + dt.timedelta(days=1)


class SkillUsageCaptureTest(unittest.TestCase):
    def test_shell_read_paths_reject_expansion_and_glob_operands(self) -> None:
        for command in (
            'cat "$HOME/.claude/skills/x.md"',
            "cat ${ROOT}/.claude/skills/x.md",
            "cat $(pwd)/.claude/skills/x.md",
            "cat `pwd`/.claude/skills/x.md",
            "cat /repo/.claude/skills/*.md",
            "cat /repo/.claude/skills/{a,b}.md",
        ):
            with self.subTest(command=command):
                self.assertEqual(_shell_read_paths(command), [])

        self.assertEqual(
            _shell_read_paths("cat '/repo/.claude/skills/$HOME.md'"),
            ["/repo/.claude/skills/$HOME.md"],
        )
        self.assertEqual(
            _shell_read_paths(r"cat /repo/.claude/skills/\*.md"),
            ["/repo/.claude/skills/*.md"],
        )

    def test_structured_dynamic_shell_read_is_not_emitted(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            events = extract_skill_read_events(
                {
                    "type": "function_call",
                    "name": "exec_command",
                    "arguments": json.dumps(
                        {"cmd": 'cat "$HOME/.claude/skills/x.md"'}
                    ),
                },
                runtime="codex",
                timestamp=STAMP,
                source_path_id="source",
                cwd=str(root),
                coverage=Counter(),
            )
            self.assertEqual(events, [])

    def test_recursive_inventory_uses_frontmatter_and_avoids_symlink_cycle(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "alpha").mkdir()
            (root / "alpha" / "SKILL.md").write_text("---\nname: declared-alpha\n---\n")
            (root / "loose.md").write_text("# Loose skill\n")
            (root / "alpha" / "references").mkdir()
            (root / "alpha" / "references" / "ignored.md").write_text("# reference\n")
            try:
                (root / "alpha" / "cycle").symlink_to(root, target_is_directory=True)
            except OSError:
                self.skipTest("symlinks unavailable")
            rows = skill_inventory(
                inventory_roots=[{"scope": "repo", "path": str(root)}]
            )
            self.assertEqual(
                [row["skill"] for row in rows], ["declared-alpha", "loose"]
            )
            self.assertEqual(rows[0]["skill_id"], "repo:alpha/SKILL.md")
            self.assertEqual(
                [p.name for p in _inventory_paths(root)], ["SKILL.md", "loose.md"]
            )

    def test_claude_read_and_selection_are_distinct_and_noise_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill = root / "skills" / "gcp" / "SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text("---\nname: gcp-deployments\n---\n")
            history = root / "history.jsonl"
            records = [
                {
                    "type": "assistant",
                    "timestamp": STAMP.isoformat(),
                    "sessionId": "s1",
                    "cwd": str(root),
                    "message": {
                        "content": [
                            {
                                "type": "tool_use",
                                "name": "Skill",
                                "input": {"skill": "gcp-deployments"},
                            },
                            {
                                "type": "tool_use",
                                "name": "Read",
                                "input": {"file_path": str(skill)},
                            },
                        ]
                    },
                },
                {
                    "type": "assistant",
                    "timestamp": STAMP.isoformat(),
                    "message": {
                        "content": [
                            {
                                "type": "text",
                                "text": "catalog gcp-deployments; grep SKILL.md",
                            }
                        ]
                    },
                },
            ]
            history.write_text(
                "\n".join(json.dumps(record) for record in records) + "\n"
            )
            coverage = Counter()
            events = extract_claude_telemetry(
                root,
                WINDOW_START,
                WINDOW_END,
                coverage,
                skill_inventory(skills_root=root / "skills"),
            )
            self.assertEqual(
                [event["kind"] for event in events if event["runtime"] == "claude"],
                ["skill_read", "skill_selection"],
            )
            read = next(event for event in events if event["kind"] == "skill_read")
            self.assertEqual(read["selected_name"], "gcp-deployments")
            self.assertEqual(read["session_id"], "s1")

    def test_codex_function_custom_and_orchestration_reads(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            inventory = [
                {
                    "scope": "home",
                    "path": str(root / "skills" / "x" / "SKILL.md"),
                    "name": "x",
                }
            ]
            skill = root / "skills" / "x" / "SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text("# x\n")
            payload = [
                {
                    "type": "function_call",
                    "name": "Read",
                    "arguments": json.dumps({"file_path": str(skill)}),
                },
                {
                    "type": "custom_tool_call",
                    "name": "read_file",
                    "input": {"path": str(skill)},
                },
                {
                    "type": "function_call",
                    "name": "functions.exec",
                    "arguments": f'tools.exec_command({{"cmd": "cat {skill}"}})',
                },
                {
                    "type": "commandExecution",
                    "id": "exec-1",
                    "command": "grep x elsewhere",
                    "commandActions": [{"type": "read", "path": str(skill)}],
                },
                {
                    "type": "function_call",
                    "name": "grep",
                    "arguments": {"pattern": "x", "path": str(skill)},
                },
                {
                    "type": "function_call",
                    "name": "echo",
                    "arguments": {"cmd": f"cat {skill}"},
                },
            ]
            events = extract_skill_read_events(
                payload,
                runtime="codex",
                timestamp=STAMP,
                source_path_id="source",
                session_id="s2",
                cwd=str(root),
                inventory=inventory,
                coverage=Counter(),
            )
            self.assertEqual(len(events), 4)
            self.assertTrue(all(event["kind"] == "skill_read" for event in events))
            self.assertTrue(all(event["selected_name"] == "x" for event in events))

    def test_actual_codex_custom_exec_payload_and_lexical_symlink_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            real = root / "real"
            real_skill = real / "skills" / "x" / "SKILL.md"
            real_skill.parent.mkdir(parents=True)
            real_skill.write_text("# x\n")
            alias = root / "alias"
            try:
                alias.symlink_to(real, target_is_directory=True)
            except OSError:
                self.skipTest("symlinks unavailable")
            lexical = alias / "skills" / "x" / "SKILL.md"
            payload = {
                "timestamp": STAMP.isoformat(),
                "type": "response_item",
                "payload": {
                    "type": "custom_tool_call",
                    "id": "ctc-1",
                    "call_id": "call-1",
                    "name": "exec",
                    "input": f'tools.exec_command({{"cmd":"cat skills/x/SKILL.md","workdir":"{alias}"}})',
                },
            }
            events = extract_skill_read_events(
                payload,
                runtime="codex",
                timestamp=STAMP,
                source_path_id="source",
                cwd=str(root),
                coverage=Counter(),
            )
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["selected_path"], str(lexical))

    def test_no_id_command_executions_are_distinct_but_actions_deduplicate(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill = root / "skills" / "x" / "SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text("# x\n")
            payload = [
                {
                    "type": "commandExecution",
                    "command": f"/bin/bash -lc 'cat {skill}'",
                    "commandActions": [{"type": "read", "path": str(skill)}],
                },
                {
                    "type": "commandExecution",
                    "command": f"/bin/bash -lc 'cat {skill}'",
                    "commandActions": [{"type": "read", "path": str(skill)}],
                },
            ]
            events = extract_skill_read_events(
                payload,
                runtime="codex",
                timestamp=STAMP,
                source_path_id="source",
                session_id="session",
                cwd=str(root),
                coverage=Counter(),
            )
            self.assertEqual(len(events), 2)
            self.assertEqual(len({event["event_id"] for event in events}), 2)
            repeated = extract_skill_read_events(
                payload,
                runtime="codex",
                timestamp=STAMP,
                source_path_id="source",
                session_id="session",
                cwd=str(root),
                coverage=Counter(),
            )
            self.assertEqual(
                [event["event_id"] for event in events],
                [event["event_id"] for event in repeated],
            )
            other_source = extract_skill_read_events(
                payload,
                runtime="codex",
                timestamp=STAMP,
                source_path_id="other-source",
                session_id="session",
                cwd=str(root),
                coverage=Counter(),
            )
            self.assertNotEqual(
                {event["event_id"] for event in events},
                {event["event_id"] for event in other_source},
            )

    def test_no_id_records_keep_jsonl_and_sqlite_positions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill = root / "skills" / "x" / "SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text("# x\n")
            item = {
                "type": "commandExecution",
                "command": f"/bin/bash -lc 'cat {skill}'",
            }
            rollout = root / "session.jsonl"
            rollout.write_text(
                "".join(
                    json.dumps(
                        {
                            "timestamp": STAMP.isoformat(),
                            "type": "response_item",
                            "payload": item,
                        }
                    )
                    + "\n"
                    for _ in range(2)
                )
            )
            events = _extract_codex_jsonl(
                rollout,
                WINDOW_START,
                WINDOW_END,
                Counter(),
                [],
            )
            jsonl_reads = [e for e in events if e["kind"] == "skill_read"]
            self.assertEqual(len(jsonl_reads), 2)
            self.assertEqual(len({e["event_id"] for e in jsonl_reads}), 2)
            repeated = _extract_codex_jsonl(
                rollout,
                WINDOW_START,
                WINDOW_END,
                Counter(),
                [],
            )
            self.assertEqual(
                [e["event_id"] for e in events],
                [e["event_id"] for e in repeated],
            )

            db = root / "thread_history_1.sqlite"
            conn = sqlite3.connect(db)
            conn.execute(
                "CREATE TABLE thread_items (thread_id TEXT, item_id TEXT, "
                "created_at_ms INTEGER, item_json TEXT, item_type TEXT)"
            )
            for item_id in ("row-1", "row-2"):
                conn.execute(
                    "INSERT INTO thread_items VALUES (?, ?, ?, ?, ?)",
                    (
                        "thread",
                        item_id,
                        int(STAMP.timestamp() * 1000),
                        json.dumps(item),
                        "",
                    ),
                )
            conn.commit()
            conn.close()
            first = extract_codex_telemetry(root, WINDOW_START, WINDOW_END, Counter())
            second = extract_codex_telemetry(root, WINDOW_START, WINDOW_END, Counter())
            first_reads = [e for e in first if e["kind"] == "skill_read"]
            second_reads = [e for e in second if e["kind"] == "skill_read"]
            self.assertEqual(len(first_reads), 2)
            self.assertEqual(
                [e["event_id"] for e in first_reads],
                [e["event_id"] for e in second_reads],
            )

    def test_no_id_generic_reads_keep_jsonl_positions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill = root / "skills" / "x" / "SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text("# x\n")
            item = {
                "type": "function_call",
                "name": "Read",
                "arguments": json.dumps({"file_path": str(skill)}),
            }
            rollout = root / "session.jsonl"
            rollout.write_text(
                "".join(
                    json.dumps(
                        {
                            "timestamp": STAMP.isoformat(),
                            "type": "response_item",
                            "payload": item,
                        }
                    )
                    + "\n"
                    for _ in range(2)
                )
            )
            first = _extract_codex_jsonl(
                rollout,
                WINDOW_START,
                WINDOW_END,
                Counter(),
                [],
            )
            second = _extract_codex_jsonl(
                rollout,
                WINDOW_START,
                WINDOW_END,
                Counter(),
                [],
            )
            first_reads = [e for e in first if e["kind"] == "skill_read"]
            second_reads = [e for e in second if e["kind"] == "skill_read"]
            self.assertEqual(len(first_reads), 2)
            self.assertEqual(len({e["event_id"] for e in first_reads}), 2)
            self.assertEqual(
                [e["event_id"] for e in first_reads],
                [e["event_id"] for e in second_reads],
            )

    def test_codex_rollout_metadata_and_bash_lc_workdir_are_carried_forward(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workdir = root / "checkout"
            skill = workdir / ".claude" / "skills" / "nested.md"
            skill.parent.mkdir(parents=True)
            skill.write_text("# nested\n")
            rollout = root / "rollout.jsonl"
            records = [
                {
                    "timestamp": STAMP.isoformat(),
                    "type": "session_meta",
                    "payload": {"id": "rollout-id", "cwd": str(workdir)},
                },
                {
                    "timestamp": STAMP.isoformat(),
                    "type": "turn_context",
                    "payload": {"turn_id": "turn-id", "cwd": str(workdir)},
                },
                {
                    "timestamp": STAMP.isoformat(),
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "exec_command",
                        "arguments": json.dumps(
                            {
                                "cmd": "/bin/bash -lc 'cat .claude/skills/nested.md'",
                                "workdir": str(workdir),
                            }
                        ),
                        "call_id": "call-1",
                    },
                },
            ]
            rollout.write_text("\n".join(json.dumps(row) for row in records) + "\n")
            coverage = Counter()
            events = _extract_codex_jsonl(
                rollout, WINDOW_START, WINDOW_END, coverage, []
            )
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["session_id"], "rollout-id")
            self.assertEqual(events[0]["cwd"], str(workdir))
            self.assertEqual(events[0]["selected_path"], str(skill))

    def test_functions_exec_requires_actual_tools_call(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill = root / ".claude" / "skills" / "x.md"
            skill.parent.mkdir(parents=True)
            skill.write_text("# x\n")
            payload = [
                {
                    "type": "function_call",
                    "name": "functions.exec",
                    "arguments": f"text('cmd: cat {skill}')",
                },
                {
                    "type": "function_call",
                    "name": "functions.exec",
                    "arguments": f"tools.exec_command({{cmd: 'cat {skill}'}})",
                },
            ]
            events = extract_skill_read_events(
                payload,
                runtime="codex",
                timestamp=STAMP,
                source_path_id="source",
                cwd=str(root),
                coverage=Counter(),
            )
            self.assertEqual(len(events), 1)

    def test_sqlite_and_rollout_precedence_deduplicates_stable_call_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            sessions = root / "sessions"
            sessions.mkdir()
            skill = root / "skills" / "x" / "SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text("# x\n")
            call = {
                "type": "function_call",
                "name": "exec_command",
                "arguments": json.dumps({"cmd": f"/bin/bash -lc 'cat {skill}'"}),
                "call_id": "stable-call",
            }
            rollout = {
                "timestamp": STAMP.isoformat(),
                "session_id": "thread",
                "type": "response_item",
                "payload": call,
            }
            (sessions / "one.jsonl").write_text(json.dumps(rollout) + "\n")
            other = dict(call, call_id="rollout-only")
            (sessions / "two.jsonl").write_text(
                json.dumps(
                    {
                        "timestamp": STAMP.isoformat(),
                        "type": "response_item",
                        "payload": other,
                    }
                )
                + "\n"
            )
            db = root / "thread_history_1.sqlite"
            conn = sqlite3.connect(db)
            conn.execute(
                "CREATE TABLE thread_items (thread_id TEXT, item_id TEXT, created_at_ms INTEGER, item_json TEXT, item_type TEXT)"
            )
            sqlite_item = {
                "type": "commandExecution",
                "id": "stable-call",
                "command": f"/bin/bash -lc 'cat {skill}'",
            }
            conn.execute(
                "INSERT INTO thread_items VALUES (?, ?, ?, ?, ?)",
                (
                    "thread",
                    "stable-call",
                    int(STAMP.timestamp() * 1000),
                    json.dumps(sqlite_item),
                    "",
                ),
            )
            user_item = {
                "type": "userMessage",
                "content": [{"type": "text", "text": "/ready"}],
            }
            conn.execute(
                "INSERT INTO thread_items VALUES (?, ?, ?, ?, ?)",
                (
                    "thread",
                    "user-1",
                    int(STAMP.timestamp() * 1000),
                    json.dumps(user_item),
                    "userMessage",
                ),
            )
            conn.commit()
            conn.close()
            coverage = Counter()
            events = extract_codex_telemetry(root, WINDOW_START, WINDOW_END, coverage)
            self.assertEqual(
                len([event for event in events if event["kind"] == "skill_read"]), 2
            )
            self.assertEqual(
                len(
                    [event for event in events if event["kind"] == "command_candidate"]
                ),
                1,
            )
            self.assertGreaterEqual(coverage["files_discovered"], 3)

    def test_capture_half_open_utc_window_and_exclusions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill = root / "skills" / "x" / "SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text("---\nname: x\n---\n")
            history = root / "claude"
            history.mkdir()
            records = []
            for session, timestamp in (
                ("keep", "2026-09-01T00:00:00Z"),
                ("drop", "2026-09-01T12:00:00Z"),
                ("boundary", "2026-09-02T00:00:00Z"),
            ):
                records.append(
                    {
                        "type": "assistant",
                        "timestamp": timestamp,
                        "sessionId": session,
                        "cwd": str(root),
                        "message": {
                            "content": [
                                {
                                    "type": "tool_use",
                                    "name": "Read",
                                    "input": {"file_path": str(skill)},
                                }
                            ]
                        },
                    }
                )
            (history / "session.jsonl").write_text(
                "\n".join(json.dumps(row) for row in records) + "\n"
            )
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema": "claude_usage_audit_manifest.v2",
                        "snapshot_id": "s",
                        "window_start_inclusive": "2026-09-01T00:00:00Z",
                        "window_end_exclusive": "2026-09-02T00:00:00Z",
                        "claude_history_root": str(history),
                        "codex_root": str(root / "empty-codex"),
                        "hermes_root": str(root / "empty-hermes"),
                        "skill_inventory_roots": [
                            {"scope": "repo", "path": str(root / "skills")}
                        ],
                        "inventory_snapshot": "inventory.json",
                        "normalized_event_corpus": "corpus.json",
                        "excluded_session_ids": ["drop"],
                    }
                )
            )
            capture(manifest)
            corpus = json.loads((root / "corpus.json").read_text())
            self.assertEqual(len(corpus["events"]), 1)
            self.assertEqual(corpus["events"][0]["session_id"], "keep")
            self.assertEqual(corpus["coverage"]["events_excluded_by_manifest"], 1)


if __name__ == "__main__":
    unittest.main()
