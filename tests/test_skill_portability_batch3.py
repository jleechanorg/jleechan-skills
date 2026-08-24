import importlib
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

SKILLS_ROOT = REPO_ROOT / ".claude" / "skills"

BATCH3 = (
    "no-second-llm-calls",
    "org-runner-audit",
    "pr-description-format",
    "pr-efficiency-audit",
    "pre-cr-checklist",
    "repo-and-infra-locations",
    "repro-copy",
    "second-call-boundary",
)


class SkillPortabilityBatch3Test(unittest.TestCase):
    def test_batch3_skill_is_proper(self):
        result = importlib.import_module("scripts.skill_portability_scan").scan(SKILLS_ROOT)
        for name in BATCH3:
            with self.subTest(name=name):
                self.assertIn(name, result["proper"])
                self.assertNotIn(name, result["orphan"])


if __name__ == "__main__":
    unittest.main()
