"""Regression contracts for portable approval and evidence-gate skills."""

import json
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.history_search import search_claude, search_cursor


REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS = REPO_ROOT / ".claude" / "skills"
COMMANDS = REPO_ROOT / ".claude" / "commands"


def skill(name: str) -> str:
    return (SKILLS / name / "SKILL.md").read_text()


class ApprovalContractsTest(unittest.TestCase):

    def test_commentcheck_fenced_code_blocks_are_not_nested(self) -> None:
        path = COMMANDS / "extended-library" / "commentcheck.md"
        in_fence = False
        fence_count = 0

        for line_number, line in enumerate(path.read_text().splitlines(), start=1):
            if line.startswith("### Phase 5:") or line.startswith("### Phase 6:"):
                self.assertFalse(in_fence, f"phase heading fenced at {line_number}")
            if not line.startswith("```"):
                continue
            fence_count += 1
            if in_fence:
                self.assertEqual(
                    line.strip(),
                    "```",
                    f"unexpected nested fence at {line_number}",
                )
                in_fence = False
            else:
                in_fence = True

        self.assertGreater(fence_count, 0)
        self.assertFalse(in_fence, "commentcheck.md has an unclosed code fence")

    def test_superpowers_quick_and_dependencies_have_valid_packages(self) -> None:
        command_path = COMMANDS / "superpowers-quick.md"
        self.assertTrue(command_path.is_file(), command_path)
        self.assertIn(
            "~/.claude/skills/superpowers-quick/SKILL.md",
            command_path.read_text(encoding="utf-8"),
        )

        package_names = (
            "superpowers-quick",
            "superpowers-brainstorming",
            "superpowers-writing-plans",
        )
        package_texts = {}
        for name in package_names:
            path = SKILLS / name / "SKILL.md"
            self.assertTrue(path.is_file(), path)
            text = path.read_text(encoding="utf-8")
            metadata = re.match(r"\A---\n(.*?)\n---\n", text, re.S)
            self.assertIsNotNone(metadata, path)
            self.assertRegex(
                metadata.group(1), rf"(?m)^name:\s*{re.escape(name)}$"
            )
            package_texts[name] = text

        self.assertRegex(
            package_texts["superpowers-quick"],
            r"(?m)^disable-model-invocation:\s*false$",
        )
    def test_history_claude_helper_enforces_result_and_excerpt_budgets(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            projects = root / "claude_projects"
            project = projects / "fixture-project"
            project.mkdir(parents=True)
            for index in range(4):
                path = project / f"session-{index}.jsonl"
                entries = [{"timestamp": "2026-10-04", "message": {
                    "role": "assistant", "content": "SYNTHETIC_PRIVATE_PAYLOAD"}}]
                entries += [{"timestamp": "2026-10-04", "message": {
                    "role": "user", "content": f"question-{index} " + "x" * 600}}
                    for _ in range(4)]
                path.write_text("\n".join(json.dumps(row) for row in entries) + "\n")
                os.utime(path, (index + 1, index + 1))

            results = search_claude(
                query="question", cwd="/fixture-project", limit=5, max_chars=500,
                projects_dir=projects,
            )
            self.assertEqual(len(results), 5)
            self.assertTrue(all(result.source == "claude" for result in results))
            self.assertTrue(all(len(result.snippet) <= 500 for result in results))
            self.assertTrue(all("question" in result.snippet for result in results))
            self.assertNotIn("SYNTHETIC_PRIVATE_PAYLOAD", "\n".join(r.snippet for r in results))
            self.assertNotIn("session-0.jsonl", {r.metadata["file"] for r in results})

    def test_cursor_helper_uses_selected_source_and_preserves_budget_behavior(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "prompt_history.json"
            source.write_text(json.dumps([{"prompt": "needle " + "x" * 600}] * 5))
            results = search_cursor(
                query="needle", limit=3, max_chars=500,
                prompt_history_path=source,
                projects_dir=root / "absent-projects",
                chats_dir=root / "absent-chats",
            )
            self.assertEqual(len(results), 3)
            self.assertTrue(all(result.source == "cursor" for result in results))
            self.assertTrue(all(len(result.snippet) <= 500 for result in results))
            self.assertTrue(all("needle" in result.snippet for result in results))

            source.write_text("{")
            self.assertEqual(
                search_cursor(
                    query="needle", prompt_history_path=source,
                    projects_dir=root / "absent-projects",
                    chats_dir=root / "absent-chats",
                ),
                [],
            )

            source.write_text(json.dumps([{"prompt": "needle"}]))
            with patch("builtins.open", side_effect=PermissionError("fixture denied")):
                denied = search_cursor(
                    query="needle", prompt_history_path=source,
                    projects_dir=root / "absent-projects",
                    chats_dir=root / "absent-chats",
                )
            self.assertEqual(denied, [])


class WorkspaceSpecificIdentifierTest(unittest.TestCase):
    def test_agento_report_has_no_workspace_specific_slack_channel(self):
        report = (SKILLS / "agento-report" / "SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn("#ai-slack-test", report)


if __name__ == "__main__":
    unittest.main()

