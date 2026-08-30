"""Regression contracts for behavior preserved by thin command migration."""

import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / ".claude" / "skills"


class ThinCommandReviewRegressionsTest(unittest.TestCase):
    def test_memory_search_keeps_low_cost_codex_fanout_policy_in_skill(self):
        skill = (SKILLS_DIR / "memory-search" / "SKILL.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("gpt-5.3-codex-spark", skill)
        self.assertIn("reasoning_effort: medium", skill)
        self.assertRegex(skill, r"(?i)never.+sol")

    def test_browser_control_recovers_authorized_share_sign_in_shell(self):
        skill = (SKILLS_DIR / "browser-control" / "SKILL.md").read_text(
            encoding="utf-8"
        )

        self.assertRegex(skill, r"(?i)sign-in shell")
        self.assertIn("browserclaw cookies decrypt", skill)
        self.assertIn("browserclaw cookies inject", skill)
        self.assertRegex(skill, r"(?i)do not ask the user to paste")
        self.assertIn("gemini-share-link-as-user.md", skill)

    def test_execute_compatibility_reference_local_links_resolve(self):
        reference = SKILLS_DIR / "execute" / "references" / "legacy-command.md"
        local_links = [
            target.split("#", 1)[0]
            for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", reference.read_text())
            if target.startswith(".")
        ]

        self.assertTrue(local_links, "execute compatibility reference needs local links")
        missing = [target for target in local_links if not (reference.parent / target).is_file()]
        self.assertEqual([], missing, f"broken relocated execute links: {missing}")


if __name__ == "__main__":
    unittest.main()
