"""Exercise real-shaped capture records through scoped reporting."""

import datetime as dt
import json
import unittest
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.audit_command_skill_usage import audit
from scripts.capture_command_skill_usage import _extract_codex_jsonl, capture
from scripts.skill_read_telemetry import extract_skill_read_events
from tests.test_command_skill_usage_audit import build_audit_fixture, digest


class SkillUsagePipelineTest(unittest.TestCase):
    def test_audit_rejects_changed_capture_exclusions(self):
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            manifest_path = build_audit_fixture(root, events=[])
            manifest = json.loads(manifest_path.read_text())
            corpus_path = root / manifest["normalized_event_corpus"]
            corpus = json.loads(corpus_path.read_text())
            corpus["exclusions"] = {
                "excluded_session_ids": ["audit-session"],
                "excluded_cwds": [str(root / "audit")],
            }
            corpus_path.write_text(json.dumps(corpus))
            manifest["normalized_event_corpus_sha256"] = digest(corpus_path.read_bytes())
            manifest.update(corpus["exclusions"])
            manifest_path.write_text(json.dumps(manifest))
            audit(manifest_path, root / "baseline")
            for key, value in (
                ("excluded_session_ids", []),
                ("excluded_session_ids", ["other-session"]),
                ("excluded_cwds", []),
                ("excluded_cwds", [str(root / "other")]),
            ):
                with self.subTest(key=key, value=value):
                    changed = {**manifest, key: value}
                    manifest_path.write_text(json.dumps(changed))
                    with self.assertRaisesRegex(ValueError, "exclusions.*manifest"):
                        audit(manifest_path, root / "changed")

    def test_non_string_record_discriminators_are_not_tool_calls(self):
        self.assertEqual(self.read_events({"type": {"type": "string"}}), [])
        self.assertEqual(self.read_events({"type": ["function_call"]}), [])
        self.assertEqual(
            self.read_events(
                {
                    "type": "commandExecution",
                    "commandActions": [{"type": {}}],
                }
            ),
            [],
        )
        self.assertEqual(
            self.read_events(
                {
                    "type": "commandExecution",
                    "commandActions": None,
                }
            ),
            [],
        )

    def read_events(self, payload):
        return extract_skill_read_events(
            payload,
            runtime="codex",
            timestamp=dt.datetime(2026, 9, 1, tzinfo=dt.UTC),
            source_path_id="source",
            session_id="session",
            cwd="/session",
        )

    def test_command_action_and_shell_are_one_observation(self):
        events = self.read_events(
            {
                "type": "commandExecution",
                "id": "call",
                "command": "/bin/bash -lc 'cat /repo/skills/x/SKILL.md'",
                "commandActions": [{"type": "read", "path": "/repo/skills/x/SKILL.md"}],
            }
        )
        self.assertEqual(len(events), 1)

    def test_orchestration_preserves_each_call_workdir(self):
        events = self.read_events(
            {
                "type": "custom_tool_call",
                "name": "functions.exec",
                "call_id": "outer",
                "input": 'await tools.exec_command({cmd: "cat .claude/skills/x.md", workdir: "/repo/a"}); '
                'await tools.exec_command({cmd: "cat .claude/skills/x.md", workdir: "/repo/b"});',
            }
        )
        self.assertEqual(
            {e["selected_path"] for e in events},
            {
                "/repo/a/.claude/skills/x.md",
                "/repo/b/.claude/skills/x.md",
            },
        )
        self.assertEqual(len({e["event_id"] for e in events}), 2)

    def test_js_strings_comments_and_dynamic_operands_are_not_read_calls(self):
        for code in (
            '// tools.exec_command({cmd: "cat /repo/skills/x/SKILL.md"})',
            "const x = 'tools.exec_command({cmd: \"cat /repo/skills/x/SKILL.md\"})'; text(x);",
            'await tools.exec_command({cmd: "cat /repo/skills/x/SKILL.md" + extra});',
        ):
            with self.subTest(code=code):
                self.assertEqual(
                    self.read_events(
                        {
                            "type": "custom_tool_call",
                            "name": "functions.exec",
                            "call_id": "outer",
                            "input": code,
                        }
                    ),
                    [],
                )

    def test_history_command_keeps_exclusion_metadata(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "history.jsonl"
            path.write_text(
                json.dumps(
                    {
                        "ts": 1788220800,
                        "session_id": "excluded-session",
                        "cwd": "/excluded-repo",
                        "text": "/ready",
                    }
                )
                + "\n"
            )
            stamp = dt.datetime.fromtimestamp(1788220800, dt.UTC)
            events = _extract_codex_jsonl(
                path,
                stamp - dt.timedelta(days=1),
                stamp + dt.timedelta(days=1),
                Counter(),
                [],
            )
            self.assertEqual(events[0]["session_id"], "excluded-session")
            self.assertEqual(events[0]["cwd"], "/excluded-repo")

    def test_shell_comments_heredocs_and_prose_are_not_file_reads(self):
        for command in (
            "cat /tmp/log\nprintf '%s' '/repo/skills/x/SKILL.md'",
            "cat /tmp/log # /repo/skills/x/SKILL.md",
            "cat <<'EOF'\n/repo/skills/x/SKILL.md\nEOF",
        ):
            with self.subTest(command=command):
                self.assertEqual(
                    self.read_events(
                        {
                            "type": "function_call",
                            "name": "exec_command",
                            "call_id": "shell",
                            "arguments": {"cmd": command},
                        }
                    ),
                    [],
                )

    def test_rollout_context_and_lexical_scope_survive_capture_and_audit(self):
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            project = root / "project"
            claude_skills = project / ".claude/skills"
            codex_skills = project / ".codex/skills"
            source = claude_skills / "gcp-deployments/SKILL.md"
            source.parent.mkdir(parents=True)
            source.write_text("---\nname: gcp-deployments\n---\n# Deployment guide\n")
            codex_skills.mkdir(parents=True)
            (codex_skills / "gcp-deployments").symlink_to(source.parent)
            codex_logs = root / "codex"
            rollout = codex_logs / "sessions/2026/08/10/session.jsonl"
            rollout.parent.mkdir(parents=True)
            records = [
                {
                    "type": "session_meta",
                    "timestamp": "2026-07-01T00:00:00Z",
                    "payload": {"id": "real-session", "cwd": str(root)},
                },
                {
                    "type": "response_item",
                    "timestamp": "2026-08-10T12:00:00Z",
                    "payload": {
                        "type": "function_call",
                        "name": "exec_command",
                        "call_id": "read-guide",
                        "arguments": json.dumps(
                            {
                                "cmd": "cat .codex/skills/gcp-deployments/SKILL.md",
                                "workdir": str(project),
                            }
                        ),
                    },
                },
                {
                    "type": "turn_context",
                    "timestamp": "2026-08-10T12:01:00Z",
                    "payload": {"cwd": str(root / "audit")},
                },
                {
                    "type": "response_item",
                    "timestamp": "2026-08-10T12:02:00Z",
                    "payload": {
                        "type": "function_call",
                        "name": "exec_command",
                        "call_id": "audit-read",
                        "arguments": json.dumps(
                            {
                                "cmd": f"cat {source}",
                            }
                        ),
                    },
                },
            ]
            rollout.write_text("".join(json.dumps(row) + "\n" for row in records))
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "snapshot_id": "integration",
                        "window_start_inclusive": "2026-07-30T00:00:00Z",
                        "window_end_exclusive": "2026-08-29T00:00:00Z",
                        "boundary_convention": "start <= event timestamp < end",
                        "inventory_snapshot": "inventory.json",
                        "normalized_event_corpus": "corpus.json",
                        "command_inventory_root": str(root / "commands"),
                        "skill_inventory_roots": [
                            {"scope": "claude", "path": str(claude_skills)},
                            {"scope": "codex", "path": str(codex_skills)},
                        ],
                        "claude_history_root": str(root / "claude-history"),
                        "codex_root": str(codex_logs),
                        "hermes_root": str(root / "hermes"),
                        "excluded_cwds": [str(root / "audit")],
                    }
                )
            )
            capture(manifest)
            audit(manifest, root / "out")
            report = json.loads((root / "out/skill-usage-30d.json").read_text())
            rows = {row["scope"]: row for row in report["skills"]}
            self.assertEqual(set(rows), {"claude", "codex"})
            self.assertEqual(rows["codex"]["file_read_attempts"], 1)
            self.assertEqual(rows["claude"]["file_read_attempts"], 0)
            self.assertEqual(report["total_file_read_attempts"], 1)
            self.assertEqual(report["events"][0]["session_id"], "real-session")
            self.assertEqual(
                report["capture_coverage"]["events_excluded_by_manifest"], 1
            )
            self.assertFalse(rows["codex"]["archive_eligible_from_usage_alone"])


if __name__ == "__main__":
    unittest.main()
