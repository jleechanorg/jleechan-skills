"""Tests for worktree cleanup script and launchd plist template (bd-ygd)."""

import os
import plistlib
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "cleanup-projects-worktrees.sh"
PLIST_TEMPLATE = REPO_ROOT / "launchd" / "com.jleechan.cleanup-projects-worktrees.plist"


class WorktreeCleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)
        self.projects_dir = self.base_dir / "projects"
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.base_dir / "cleanup.log"

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_cleanup(self, *args: str) -> subprocess.CompletedProcess[str]:
        cmd = [
            "bash",
            str(SCRIPT),
            "--target-dir",
            str(self.projects_dir),
            "--log-file",
            str(self.log_file),
            *args,
        ]
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )

    def create_git_worktree(
        self,
        name: str,
        age_days: float,
        dirty: bool = False,
        untracked: bool = False,
    ) -> Path:
        """Create a mock git worktree with specified age and dirty state."""
        wt_path = self.projects_dir / name
        wt_path.mkdir(parents=True, exist_ok=True)

        # Initialize mock git repository / worktree
        subprocess.run(
            ["git", "init", "-q", str(wt_path)],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(wt_path), "config", "user.name", "Test User"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(wt_path), "config", "user.email", "test@example.com"],
            check=True,
        )

        test_file = wt_path / "README.md"
        test_file.write_text("# Project\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(wt_path), "add", "README.md"], check=True)
        env = dict(os.environ, HERMES_SKIP_EXAMPLE_COM_GUARD="1")
        subprocess.run(
            ["git", "-C", str(wt_path), "commit", "-q", "--no-verify", "-m", "Initial commit"],
            check=True,
            env=env,
        )

        if dirty:
            test_file.write_text("# Project modified\n", encoding="utf-8")
        if untracked:
            (wt_path / "untracked.txt").write_text("untracked\n", encoding="utf-8")

        # Adjust mtime for all files in the worktree
        target_mtime = time.time() - (age_days * 86400)
        os.utime(wt_path, (target_mtime, target_mtime))
        for root, dirs, files in os.walk(wt_path):
            for d in dirs:
                p = Path(root) / d
                os.utime(p, (target_mtime, target_mtime))
            for f in files:
                p = Path(root) / f
                os.utime(p, (target_mtime, target_mtime))

        return wt_path

    def test_dry_run_by_default_does_not_delete(self):
        wt = self.create_git_worktree("worktree_old_clean", age_days=25, dirty=False)
        result = self.run_cleanup()

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("DRY RUN", result.stdout)
        self.assertIn("worktree_old_clean", result.stdout)
        self.assertTrue(wt.exists(), "Worktree must not be deleted in dry-run mode")

    def test_protects_worktrees_younger_than_14_days(self):
        wt = self.create_git_worktree("worktree_young_clean", age_days=10, dirty=False)
        result = self.run_cleanup("--clean")

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertTrue(wt.exists(), "Worktree younger than 14 days must be protected")
        self.assertIn("PROTECTED", result.stdout)

    def test_protects_worktrees_between_14_and_21_days_under_default_threshold(self):
        wt = self.create_git_worktree("worktree_mid_clean", age_days=18, dirty=False)
        result = self.run_cleanup("--clean")

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertTrue(wt.exists(), "Worktree between 14 and 21 days must be skipped under default threshold")

    def test_protects_dirty_worktrees_even_if_older_than_21_days(self):
        wt_modified = self.create_git_worktree("worktree_dirty_mod", age_days=30, dirty=True)
        wt_untracked = self.create_git_worktree("worktree_dirty_untracked", age_days=30, untracked=True)

        result = self.run_cleanup("--clean")

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertTrue(wt_modified.exists(), "Modified worktree must be protected")
        self.assertTrue(wt_untracked.exists(), "Worktree with untracked files must be protected")
        self.assertIn("DIRTY", result.stdout)

    def test_cleans_clean_worktrees_older_than_21_days(self):
        wt_old_clean = self.create_git_worktree("worktree_to_clean", age_days=25, dirty=False)
        result = self.run_cleanup("--clean")

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertFalse(wt_old_clean.exists(), "Clean worktree older than 21 days must be deleted")
        self.assertIn("REMOVED", result.stdout)

    def test_archive_mode_moves_worktree_instead_of_delete(self):
        wt_old = self.create_git_worktree("worktree_archive_me", age_days=25, dirty=False)
        archive_dir = self.base_dir / "worktree_archive"
        result = self.run_cleanup("--clean", "--archive-dir", str(archive_dir))

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertFalse(wt_old.exists(), "Worktree should be moved out of projects")
        self.assertTrue((archive_dir / "worktree_archive_me").exists(), "Worktree must be in archive dir")

    def test_refuses_unsafe_min_age_floor_under_14_days(self):
        result = self.run_cleanup("--min-age-days", "7")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Safety violation", result.stderr + result.stdout)

    def test_ignores_directories_not_matching_worktree_prefix(self):
        regular_project = self.projects_dir / "my_cool_project"
        regular_project.mkdir()
        (regular_project / "file.txt").write_text("code\n", encoding="utf-8")
        target_mtime = time.time() - (40 * 86400)
        os.utime(regular_project, (target_mtime, target_mtime))

        result = self.run_cleanup("--clean")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertTrue(regular_project.exists(), "Non-worktree project must never be touched")

    def test_launchd_plist_template_validity(self):
        self.assertTrue(PLIST_TEMPLATE.is_file(), f"{PLIST_TEMPLATE} must exist")
        content = PLIST_TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("@HOME@", content, "Plist template must use @HOME@ placeholders")
        self.assertIn("com.jleechan.cleanup-projects-worktrees", content)
        self.assertIn("cleanup-projects-worktrees.sh", content)
        self.assertIn("--clean", content)

        # Ensure valid XML plist structure
        parsed = plistlib.loads(content.replace("@HOME@", "/Users/testuser").encode("utf-8"))
        self.assertEqual(parsed["Label"], "com.jleechan.cleanup-projects-worktrees")
        self.assertIn("ProgramArguments", parsed)
        self.assertIn("StartCalendarInterval", parsed)

    def test_worktree_with_recent_file_in_subdirectory_is_protected(self):
        wt = self.create_git_worktree("worktree_recent_subfile", age_days=30, dirty=False)
        sub_dir = wt / "src" / "deep"
        sub_dir.mkdir(parents=True, exist_ok=True)
        recent_file = sub_dir / "recent.py"
        recent_file.write_text("print('recent')\n", encoding="utf-8")
        # Touch recent file to 5 days ago (< 14 days)
        recent_mtime = time.time() - (5 * 86400)
        os.utime(recent_file, (recent_mtime, recent_mtime))

        result = self.run_cleanup("--clean")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertTrue(wt.exists(), "Worktree with recent file in subdirectory must be protected")
        self.assertIn("PROTECTED", result.stdout)

    def test_rebase_in_progress_is_protected(self):
        wt = self.create_git_worktree("worktree_rebasing", age_days=30, dirty=False)
        # Create .git/rebase-merge marker
        rebase_dir = wt / ".git" / "rebase-merge"
        rebase_dir.mkdir(parents=True, exist_ok=True)

        result = self.run_cleanup("--clean")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertTrue(wt.exists(), "Worktree with active rebase must be protected")
        self.assertIn("DIRTY", result.stdout)

    def test_merge_in_progress_is_protected(self):
        wt = self.create_git_worktree("worktree_merging", age_days=30, dirty=False)
        # Create .git/MERGE_HEAD marker
        merge_head = wt / ".git" / "MERGE_HEAD"
        merge_head.write_text("0123456789abcdef\n", encoding="utf-8")

        result = self.run_cleanup("--clean")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertTrue(wt.exists(), "Worktree with active merge must be protected")
        self.assertIn("DIRTY", result.stdout)

    def test_broken_git_directory_is_skipped(self):
        broken_dir = self.projects_dir / "worktree_broken"
        broken_dir.mkdir(parents=True, exist_ok=True)
        # Set old mtime
        old_mtime = time.time() - (30 * 86400)
        os.utime(broken_dir, (old_mtime, old_mtime))

        result = self.run_cleanup("--clean")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertTrue(broken_dir.exists(), "Broken non-git directory must be skipped for safety")
        self.assertIn("DIRTY", result.stdout)


if __name__ == "__main__":
    unittest.main()

