"""Batch4 conversion contract: final batch; after conversion orphan count reaches 0.

Integration test against the live .claude/skills/ tree, not a fixture — the point
is to track the real conversion state of these specific skills.
"""

import importlib
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

SKILLS_ROOT = REPO_ROOT / ".claude" / "skills"

BATCH4 = (
    "slack-identity",
    "slash-command-translation",
    "soak",
    "test-classification",
    "testing-gap-close",
    "vibe-code-2d-game",
    "worktree-protection",
)


class SkillPortabilityBatch4Test(unittest.TestCase):
    def test_batch4_skills_are_proper(self):
        result = importlib.import_module("scripts.skill_portability_scan").scan(SKILLS_ROOT)
        unconverted = sorted(name for name in BATCH4 if name not in result["proper"])
        self.assertEqual(
            unconverted,
            [],
            msg=f"batch4 skills not yet converted to <name>/SKILL.md: {unconverted}",
        )


if __name__ == "__main__":
    unittest.main()
