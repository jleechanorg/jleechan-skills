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
    def _run_setup(self, home, spec, plan, tail=""):
        text = QUICK_SKILLS[0].read_text()
        marker = "Resolve and validate the roadmap repository"
        start = text.index("```bash", text.index(marker)) + len("```bash\n")
        end = text.index("\n     ```", start)
        setup = "\n".join(
            line[5:] if line.startswith("     ") else line
            for line in text[start:end].splitlines()
        )
        env = {**os.environ, "HOME": str(home), "SPEC_PATH": str(spec), "PLAN_PATH": str(plan)}
        return subprocess.run(
            ["/bin/bash", "-c", setup + tail],
            cwd=home, env=env, capture_output=True, text=True, check=False,
        )

    def test_sq_advice_setup_rejects_a_missing_git_roadmap(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir)
            (home / "roadmap").mkdir()
            result = self._run_setup(home, home / "roadmap/design.md", home / "roadmap/plan.md")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not a Git repository", result.stderr)

    def test_sq_advice_setup_yields_repository_relative_documents(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir).resolve()
            roadmap = home / "roadmap"
            roadmap.mkdir()
            subprocess.run(["git", "init", "-q", str(roadmap)], check=True)
            tail = '\nprintf "%s|%s" "$SPEC_DOCUMENT" "$PLAN_DOCUMENT"'
            ok = self._run_setup(home, roadmap / "d/design.md", roadmap / "plan.md", tail)
            outside = self._run_setup(home, home / "design.md", roadmap / "plan.md", tail)
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertEqual(ok.stdout, "d/design.md|plan.md")
        self.assertNotEqual(outside.returncode, 0)


if __name__ == "__main__":
    unittest.main()
