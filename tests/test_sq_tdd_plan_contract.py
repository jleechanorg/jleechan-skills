"""Prompt contracts for the /sq TDD plan self-review, not model execution tests."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
QUICK_SKILLS = (
    ROOT / ".claude/skills/superpowers-quick/SKILL.md",
    ROOT / "portable/skills/superpowers-quick/SKILL.md",
)


class SqTddPlanContractTest(unittest.TestCase):
    def test_sq_aliases_delegate_without_copying_the_workflow(self):
        aliases = (
            ROOT / ".claude/commands/sq.md",
            ROOT / "portable/skills/sq/SKILL.md",
        )
        for path in aliases:
            with self.subTest(path=path.relative_to(ROOT)):
                text = path.read_text()
                self.assertIn("superpowers-quick/SKILL.md", text)
                self.assertNotIn("TDD plan step check", text)
                self.assertLessEqual(len(text.splitlines()), 15)

    def test_each_behavior_task_gets_ordered_superpowers_tdd_steps(self):
        expected_steps = (
            "write the failing test",
            "run it to verify the expected failure",
            "write the minimal implementation",
            "run the test and relevant regressions to verify they pass",
            "commit",
        )
        for path in QUICK_SKILLS:
            with self.subTest(path=path.relative_to(ROOT)):
                text = path.read_text()
                self.assertIn("**TDD plan step check (before advice):**", text)
                check = text.split("**TDD plan step check (before advice):**", 1)[1]
                self.assertIn("For every task that changes behavior", check)
                positions = [check.index(step) for step in expected_steps]
                self.assertEqual(positions, sorted(positions))
                self.assertIn("exact test and implementation paths", check)
                self.assertIn("runnable commands", check)
                self.assertIn("expected RED/GREEN outcomes", check)
                self.assertLess(text.index("**TDD plan step check"),
                                text.index("Run `/advice`" if path == QUICK_SKILLS[0]
                                           else "Run [advice]"))

    def test_plan_check_repairs_gaps_without_running_implementation(self):
        for path in QUICK_SKILLS:
            with self.subTest(path=path.relative_to(ROOT)):
                text = path.read_text()
                self.assertIn("fix missing, reordered, or vague steps", text)
                self.assertIn("recheck the saved plan before advice", text)
                self.assertIn("`TDD Plan Check`", text)
                self.assertIn("`TDD: N/A`", text)
                self.assertIn("concrete reason and a specific verification check", text)
                self.assertIn("do not execute tests, edit implementation code, or commit", text)
                self.assertIn("not evidence that RED/GREEN tests have run", text)
                self.assertIn("TDD plan step check is complete", text)


if __name__ == "__main__":
    unittest.main()
