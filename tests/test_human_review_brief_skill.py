from pathlib import Path
import re
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = REPO_ROOT / ".claude" / "skills" / "human-review-brief" / "SKILL.md"
COMMAND_PATH = REPO_ROOT / ".claude" / "commands" / "what-to-review.md"
PR_SUMMARY_PATH = REPO_ROOT / ".claude" / "skills" / "pr-summary" / "SKILL.md"


class HumanReviewBriefSkillTests(unittest.TestCase):
    def test_skill_exists_with_valid_frontmatter(self) -> None:
        self.assertTrue(SKILL_PATH.is_file(), f"Missing skill file: {SKILL_PATH}")
        text = SKILL_PATH.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\n"), "Skill must start with YAML frontmatter")
        self.assertIn("name: human-review-brief", text)

    def test_command_dispatcher_points_to_skill(self) -> None:
        self.assertTrue(COMMAND_PATH.is_file(), f"Missing command file: {COMMAND_PATH}")
        cmd_text = COMMAND_PATH.read_text(encoding="utf-8")
        self.assertIn("human-review-brief/SKILL.md", cmd_text)
        self.assertIn("$ARGUMENTS", cmd_text)

    def test_portability_no_hardcoded_personal_paths(self) -> None:
        for path in (SKILL_PATH, COMMAND_PATH, PR_SUMMARY_PATH):
            text = path.read_text(encoding="utf-8")
            self.assertIsNone(
                re.search(r"/(Users|home)/[A-Za-z0-9_.-]+/", text),
                f"Non-portable user path found in {path}",
            )


if __name__ == "__main__":
    unittest.main()
