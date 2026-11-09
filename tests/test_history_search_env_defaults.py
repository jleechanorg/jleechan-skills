"""The on-demand recovery script uses explicitly admitted checkout roots.

The block is extracted from the reference and executed, so this tests the runnable
snippet, not its wording.
"""

import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = (
    ROOT / ".claude" / "skills" / "history-search" / "references" / "specialized-recovery.md"
)


def fsck_snippet() -> str:
    text = REFERENCE.read_text(encoding="utf-8")
    heading = re.search(
        r"(?ms)^## Git unreachable-object recovery\s*\n(.*?)(?=^## |\Z)", text
    )
    if heading is None:
        raise AssertionError("Git unreachable-object recovery section is missing")
    snippet = re.search(r"(?ms)^```bash\s*\n(.*?)^```\s*$", heading.group(1))
    if snippet is None:
        raise AssertionError("Git recovery section has no runnable bash snippet")
    return snippet.group(1)


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

    def make_repo_with_dangling_chain(self, repo: Path, count: int) -> None:
        repo.mkdir(parents=True)
        self.git(repo, "init", "-q")
        self.git(repo, "commit", "-q", "--allow-empty", "-m", "base")
        base = subprocess.check_output(
            ["git", "-C", str(repo), "rev-parse", "HEAD"], env=self.env, text=True
        ).strip()
        for index in range(count):
            self.git(repo, "commit", "-q", "--allow-empty", "-m", f"unreachable-{index}")
        self.git(repo, "reset", "-q", "--hard", base)

    def run_snippet(self, *args, **extra):
        return subprocess.run(
            ["bash", "-c", fsck_snippet(), "fsck-scan", *args],
            cwd=self.cwd,
            env={**self.env, **extra},
            capture_output=True,
            text=True,
            timeout=30,
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

    def test_explicit_checkout_wins_over_configured_roots(self):
        chosen = self.tmp / "chosen"
        other = self.tmp / "other"
        self.make_repo_with_dangling(chosen, "chosen-lost-work")
        self.make_repo_with_dangling(other, "other-lost-work")
        self.cwd = other
        proc = self.run_snippet(str(chosen), PROJECT_ROOT=str(other))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("chosen-lost-work", proc.stdout)
        self.assertNotIn("other-lost-work", proc.stdout)
        self.assertFalse((chosen / ".git" / "lost-found").exists())

    def test_candidate_cap_returns_success_with_only_bounded_results(self):
        repo = self.tmp / "many-unreachable"
        self.make_repo_with_dangling_chain(repo, 25)
        proc = self.run_snippet(str(repo))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(len(proc.stdout.splitlines()), 20)

    def test_current_checkout_is_derived(self):
        repo = self.tmp / "current"
        self.make_repo_with_dangling(repo, "current-lost-work")
        self.cwd = repo
        proc = self.run_snippet()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("current-lost-work", proc.stdout)
        self.assertFalse((repo / ".git" / "lost-found").exists())


if __name__ == "__main__":
    unittest.main()
