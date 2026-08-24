"""Batch 2 of the skill portability migration (bd-11g.15).

Each name below is still a loose <name>.md and must become a
<name>/SKILL.md directory with name/description frontmatter.
"""

import importlib
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

SKILLS_ROOT = REPO_ROOT / ".claude" / "skills"

BATCH2 = (
    "evidence-coverage",
    "evolve_loop",
    "fetch-x-tweet",
    "field-ownership-contracts",
    "game-evidence-reviewer",
    "harness-guardrails",
    "hermes-models",
    "llm-testing",
)


class SkillPortabilityBatch2Test(unittest.TestCase):
    def test_batch2_skill_is_proper(self):
        result = importlib.import_module("scripts.skill_portability_scan").scan(SKILLS_ROOT)
        for name in BATCH2:
            with self.subTest(name=name):
                self.assertIn(name, result["proper"])
                self.assertNotIn(name, result["orphan"])


if __name__ == "__main__":
    unittest.main()
