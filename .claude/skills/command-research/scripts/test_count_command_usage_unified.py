import json
import os
import tempfile
import unittest

from count_command_usage_unified import (
    is_imperative_invocation,
    is_listing_or_report,
    scan_claude,
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


if __name__ == "__main__":
    unittest.main()
