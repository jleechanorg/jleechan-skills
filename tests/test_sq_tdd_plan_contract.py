"""Executable check of the /sq advice setup snippet."""

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
