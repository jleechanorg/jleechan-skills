"""Contract tests for Beads ignore policy (bead bd-pr-portfolio-remediation-047.11)."""

import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BEADS_DIR = REPO_ROOT / ".beads"
BEADS_GITIGNORE = BEADS_DIR / ".gitignore"
ROOT_GITIGNORE = REPO_ROOT / ".gitignore"


class BeadsIgnorePolicyTest(unittest.TestCase):
    def test_beads_inner_gitignore_declares_expected_patterns(self) -> None:
        self.assertTrue(BEADS_GITIGNORE.is_file(), "Missing .beads/.gitignore")
        content = BEADS_GITIGNORE.read_text(encoding="utf-8")
        patterns = [
            "*.db",
            "*.db-journal",
            "*.db-wal*",
            "*.vacuum-wal-cert*",
            "*.fsqlite-migration-state",
            "*.tmp",
            "*.pre-migration-bak*",
        ]
        for pattern in patterns:
            with self.subTest(pattern=pattern):
                self.assertIn(
                    pattern,
                    content.splitlines(),
                    f"Pattern {pattern} missing from .beads/.gitignore",
                )

    def test_beads_inner_gitignore_retains_canonical_jsonl_export(self) -> None:
        content = BEADS_GITIGNORE.read_text(encoding="utf-8")
        lines = [line.strip() for line in content.splitlines() if line.strip() and not line.strip().startswith("#")]
        self.assertNotIn("issues.jsonl", lines)
        self.assertNotIn("*.jsonl", lines)

    def test_root_gitignore_ignores_doctor_runs_and_preserves_beads_jsonl(self) -> None:
        self.assertTrue(ROOT_GITIGNORE.is_file(), "Missing root .gitignore")
        content = ROOT_GITIGNORE.read_text(encoding="utf-8")
        self.assertIn(".doctor/", content.splitlines())
        lines = [line.strip() for line in content.splitlines() if line.strip() and not line.strip().startswith("#")]
        self.assertNotIn(".beads/", lines)
        self.assertNotIn(".beads", lines)

    def test_git_check_ignore_excludes_database_and_wal_artifacts(self) -> None:
        target_paths = [
            ".beads/beads.db",
            ".beads/beads.db-journal",
            ".beads/beads.db-wal",
            ".beads/beads.db-wal-cert",
            ".beads/beads.db-wal-cert-head",
            ".beads/.beads.db.schema-migration-20260101T000000.000000Z-0-0.vacuum-wal-cert",
            ".beads/beads.db.fsqlite-migration-state",
            ".beads/beads.db.pre-migration-bak",
            ".beads/beads.db.pre-migration-bak-shm",
            ".beads/beads.db.pre-migration-bak-wal",
            ".beads/query.tmp",
            ".doctor/runs/run-01/report.json",
        ]
        proc = subprocess.run(
            ["git", "check-ignore", *target_paths],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        ignored_files = set(proc.stdout.splitlines())
        for path in target_paths:
            with self.subTest(path=path):
                self.assertIn(path, ignored_files)

    def test_git_check_ignore_does_not_ignore_canonical_issues_jsonl(self) -> None:
        proc = subprocess.run(
            ["git", "check-ignore", ".beads/issues.jsonl"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            proc.returncode,
            1,
            ".beads/issues.jsonl should not be ignored by git",
        )

    def test_git_index_does_not_track_database_and_wal_artifacts(self) -> None:
        proc = subprocess.run(
            ["git", "ls-files", ".beads/"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        tracked = proc.stdout.splitlines()
        forbidden_suffixes = (
            ".db",
            ".db-journal",
            "-wal",
            "-wal-cert",
            "-wal-cert-head",
            ".fsqlite-migration-state",
            ".pre-migration-bak",
            ".pre-migration-bak-shm",
            ".pre-migration-bak-wal",
            ".tmp",
        )
        for file in tracked:
            for suffix in forbidden_suffixes:
                self.assertFalse(
                    file.endswith(suffix) or f"{suffix}." in file,
                    f"Forbidden artifact tracked in git: {file}",
                )


if __name__ == "__main__":
    unittest.main()
