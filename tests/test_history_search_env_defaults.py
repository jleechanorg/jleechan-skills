"""The history-search fsck block resolves its checkout roots at run time.

The block is extracted from SKILL.md and executed, so this tests the runnable
snippet, not its wording.
"""

import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".claude" / "skills" / "history-search" / "SKILL.md"


def fsck_snippet() -> str:
    text = SKILL.read_text(encoding="utf-8")
    section = text.split("### Parallel block G", 1)[1]
    return section.split("```bash\n", 1)[1].split("\n```", 1)[0]


class HistorySearchFsckRootTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.home = self.tmp / "home"
        self.cwd = self.tmp / "cwd"
        for directory in (self.home, self.cwd):
            directory.mkdir()
        self.env = {
            "HOME": str(self.home),
            "PATH": "/usr/bin:/bin",
            "LANG": "C",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CEILING_DIRECTORIES": str(self.tmp),
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
        }
        # A checkout at the old hardcoded default must not be scanned.
        self.make_repo_with_dangling(self.home / "projects" / "legacy", "legacy-lost-work")

    def git(self, repo, *args):
        subprocess.run(["git", "-C", str(repo), *args], check=True, env=self.env, capture_output=True)

    def make_repo_with_dangling(self, repo: Path, subject: str) -> None:
        repo.mkdir(parents=True)
        self.git(repo, "init", "-q")
        self.git(repo, "commit", "-q", "--allow-empty", "-m", "base")
        self.git(repo, "commit", "-q", "--allow-empty", "-m", subject)
        self.git(repo, "reset", "-q", "--hard", "HEAD~1")

    def run_snippet(self, *args, **extra):
        return subprocess.run(
            ["bash", "-c", fsck_snippet(), "fsck-scan", *args],
            cwd=self.cwd,
            env={**self.env, **extra},
            capture_output=True,
            text=True,
            timeout=60,
        )

    def test_outside_a_checkout_without_config_names_variable(self):
        proc = self.run_snippet()
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("PROJECT_ROOT not configured", proc.stderr)
        self.assertNotIn("legacy-lost-work", proc.stdout)

    def test_projects_dir_scans_each_checkout(self):
        parent = self.tmp / "src"
        self.make_repo_with_dangling(parent / "widgets", "widgets-lost-work")
        proc = self.run_snippet(PROJECTS_DIR=str(parent))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("widgets-lost-work", proc.stdout)
        self.assertNotIn("legacy-lost-work", proc.stdout)

    def test_project_root_wins_over_repo_root_and_current_checkout(self):
        self.make_repo_with_dangling(self.tmp / "chosen", "chosen-lost-work")
        self.make_repo_with_dangling(self.tmp / "other", "other-lost-work")
        self.cwd = self.tmp / "other"
        proc = self.run_snippet(PROJECT_ROOT=str(self.tmp / "chosen"), REPO_ROOT=str(self.tmp / "other"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("chosen-lost-work", proc.stdout)
        self.assertNotIn("other-lost-work", proc.stdout)

    def test_current_checkout_is_derived(self):
        repo = self.tmp / "current"
        self.make_repo_with_dangling(repo, "current-lost-work")
        self.cwd = repo
        proc = self.run_snippet()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("current-lost-work", proc.stdout)


if __name__ == "__main__":
    unittest.main()
