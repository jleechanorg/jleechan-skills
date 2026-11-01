from pathlib import Path
import re
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = REPO_ROOT / ".claude" / "skills" / "human-review-brief" / "SKILL.md"
COMMAND_PATH = REPO_ROOT / ".claude" / "commands" / "what-to-review.md"
PR_SUMMARY_PATH = REPO_ROOT / ".claude" / "skills" / "pr-summary" / "SKILL.md"


class HumanReviewBriefSkillTests(unittest.TestCase):
    def test_skill_exists_with_valid_frontmatter_and_core_sections(self) -> None:
        self.assertTrue(SKILL_PATH.is_file(), f"Missing skill file: {SKILL_PATH}")
        text = SKILL_PATH.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\n"), "Skill must start with YAML frontmatter")
        self.assertIn("name: human-review-brief", text)
        self.assertIn("## What Was Done", text)
        self.assertIn("## What to Review as a Human", text)
        self.assertIn("Why the LLM cannot do this:", text)
        self.assertIn("What Current Evidence Does NOT Prove", text)
        self.assertIn("git merge-tree --write-tree", text)

    def test_skill_covers_mac_and_linux_empirical_blind_spots(self) -> None:
        text = SKILL_PATH.read_text(encoding="utf-8")
        for required_phrase in (
            "Visual / UX / Hidden-State Verification",
            "Main-Merge Smuggling, Stale Base Diffs & Silent Reverts",
            "Partial, Stale-SHA, or Substitute-Provider Gates",
            "Product Constants, Cooldowns & Prompt Compression",
            "Zero-Framework Cognition (ZFC) & Scope-Blind Backend Guards",
            "Cross-PR Stack & Shared Token/Budget Ratchets",
            "Provider-Boundary & Structured-Output Schema Complexity",
            "Cross-Host (macOS vs Linux) & Viewport Parity",
            "Linux Systemd / Cgroup Live State & Runner Side Effects",
            "Delivery vs Execution, Subprocess Stdin & Hook Hygiene",
        ):
            self.assertIn(required_phrase, text)

    def test_command_dispatcher_points_to_skill(self) -> None:
        self.assertTrue(COMMAND_PATH.is_file(), f"Missing command file: {COMMAND_PATH}")
        cmd_text = COMMAND_PATH.read_text(encoding="utf-8")
        self.assertIn("human-review-brief/SKILL.md", cmd_text)
        self.assertIn("$ARGUMENTS", cmd_text)

    def test_pr_summary_links_to_human_review_brief(self) -> None:
        self.assertTrue(PR_SUMMARY_PATH.is_file(), f"Missing pr-summary file: {PR_SUMMARY_PATH}")
        pr_summary_text = PR_SUMMARY_PATH.read_text(encoding="utf-8")
        self.assertIn("#### `### What to Review as a Human`", pr_summary_text)
        self.assertIn("human-review-brief/SKILL.md", pr_summary_text)
        self.assertIn("Why the LLM cannot do this:", pr_summary_text)

    def test_portability_no_hardcoded_personal_paths(self) -> None:
        for path in (SKILL_PATH, COMMAND_PATH, PR_SUMMARY_PATH):
            text = path.read_text(encoding="utf-8")
            self.assertIsNone(
                re.search(r"/(Users|home)/[A-Za-z0-9_.-]+/", text),
                f"Non-portable user path found in {path}",
            )


if __name__ == "__main__":
    unittest.main()
