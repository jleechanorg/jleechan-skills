"""Prompt contracts for the /sq TDD plan self-review, not model execution tests."""

from pathlib import Path
import os
import subprocess
import tempfile
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

    def test_sq_advice_uses_roadmap_repository_relative_documents(self):
        text = QUICK_SKILLS[0].read_text()

        self.assertIn(
            'if ! ROADMAP_REPO="$(git -C "$HOME/roadmap" rev-parse --show-toplevel)" ||',
            text,
        )
        self.assertIn('[ -z "$ROADMAP_REPO" ]', text)
        self.assertIn('case "$SPEC_PATH" in', text)
        self.assertIn('SPEC_DOCUMENT="${SPEC_PATH#"$ROADMAP_REPO"/}"', text)
        self.assertIn('case "$PLAN_PATH" in', text)
        self.assertIn('PLAN_DOCUMENT="${PLAN_PATH#"$ROADMAP_REPO"/}"', text)
        self.assertIn(
            '--repo "$ROADMAP_REPO" --document "$SPEC_DOCUMENT" '
            '--document "$PLAN_DOCUMENT"',
            text,
        )
        self.assertNotIn('--document "$SPEC_PATH"', text)
        self.assertNotIn('--document "$PLAN_PATH"', text)

    def test_sq_advice_setup_rejects_a_missing_git_roadmap(self):
        text = QUICK_SKILLS[0].read_text()
        marker = "Resolve and validate the roadmap repository"
        start = text.index("```bash", text.index(marker)) + len("```bash\n")
        end = text.index("\n     ```", start)
        setup = "\n".join(
            line[5:] if line.startswith("     ") else line
            for line in text[start:end].splitlines()
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir)
            (home / "roadmap").mkdir()
            env = {
                **os.environ,
                "HOME": str(home),
                "SPEC_PATH": str(home / "roadmap" / "design.md"),
                "PLAN_PATH": str(home / "roadmap" / "plan.md"),
            }
            result = subprocess.run(
                ["/bin/bash", "-c", setup],
                cwd=home,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not a Git repository", result.stderr)


if __name__ == "__main__":
    unittest.main()
