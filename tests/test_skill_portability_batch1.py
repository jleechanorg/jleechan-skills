"""Batch1 conversion contract: these 9 skills must be <name>/SKILL.md directories.

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

BATCH1 = (
    "agento_report",
    "bq-evidence-reading",
    "bypass-claims",
    "crash",
    "deletion-milestone",
    "design-doc-backup-worldarchitect",
    "distributed-caching",
    "domain-lock-standards",
    "engplan",
)


class SkillPortabilityBatch1Test(unittest.TestCase):
    def test_batch1_skills_are_proper(self):
        result = importlib.import_module("scripts.skill_portability_scan").scan(SKILLS_ROOT)
        unconverted = sorted(name for name in BATCH1 if name not in result["proper"])
        self.assertEqual(unconverted, [], f"batch1 skills not yet converted to <name>/SKILL.md: {unconverted}")


if __name__ == "__main__":
    unittest.main()
