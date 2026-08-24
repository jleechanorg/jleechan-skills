"""README must direct readers to the canonical skill library."""

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
README = REPO_ROOT / "README.md"


class ReadmeSkillCountsTest(unittest.TestCase):
    def test_readme_links_to_skill_library_without_a_stale_count(self):
        text = README.read_text(encoding="utf-8")
        self.assertIn(
            "[`.claude/skills/`](.claude/skills/)",
            text,
            msg="README.md must link to the canonical skill library",
        )


if __name__ == "__main__":
    unittest.main()
