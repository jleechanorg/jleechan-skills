"""Unit tests for scripts/verify_review_packet.py executable behavior."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "verify_review_packet.py"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class VerifyReviewPacketTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def _git(self, repo: Path, *args: str) -> str:
        env = {
            **os.environ,
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
        }
        res = subprocess.run(
            [
                "git",
                "-C",
                str(repo),
                "-c",
                "user.name=Test User",
                "-c",
                "user.email=test@example.com",
                *args,
            ],
            capture_output=True,
            text=True,
            env=env,
            check=True,
        )
        return res.stdout.strip()

    def _init_repo(self) -> Path:
        repo = self.root / "repo"
        repo.mkdir()
        self._git(repo, "init", "-q", "-b", "main")
        (repo / "shared.txt").write_text("line 1\nline 2\n", encoding="utf-8")
        self._git(repo, "add", "shared.txt")
        self._git(repo, "commit", "-qm", "initial")
        self._git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
        return repo

    def _run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_script_is_executable(self) -> None:
        self.assertTrue(SCRIPT.is_file())
        self.assertTrue(os.access(SCRIPT, os.X_OK))

    def test_requires_repo_or_packet_dir(self) -> None:
        res = self._run_cli()
        self.assertEqual(res.returncode, 2)

    def test_clean_diverged_branches_pass_with_expected_head(self) -> None:
        repo = self._init_repo()
        # Advance origin/main on an independent file
        self._git(repo, "checkout", "-qb", "upstream-base")
        (repo / "upstream.txt").write_text("upstream change\n", encoding="utf-8")
        self._git(repo, "add", "upstream.txt")
        self._git(repo, "commit", "-qm", "upstream")
        self._git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")

        # Create feature branch from initial commit touching a disjoint file
        self._git(repo, "checkout", "-qb", "feature", "main")
        (repo / "feature.txt").write_text("feature change\n", encoding="utf-8")
        self._git(repo, "add", "feature.txt")
        self._git(repo, "commit", "-qm", "feature")
        head_sha = self._git(repo, "rev-parse", "HEAD")

        res = self._run_cli(
            "--repo",
            str(repo),
            "--base",
            "origin/main",
            "--head",
            "HEAD",
            "--expected-head",
            head_sha,
            "--json",
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        payload = json.loads(res.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["codes"], [])
        self.assertEqual(payload["repo"]["head_sha"], head_sha)
        self.assertEqual(len(payload["repo"]["merge_tree"]), 40)

        # Also works when --repo points directly to the .git directory
        git_dir_res = self._run_cli(
            "--repo",
            str(repo / ".git"),
            "--base",
            "origin/main",
            "--head",
            "feature",
            "--expected-head",
            head_sha,
        )
        self.assertEqual(git_dir_res.returncode, 0, git_dir_res.stderr)
        self.assertIn("OK:", git_dir_res.stdout)

    def test_conflict_with_base_exits_nonzero_with_diagnostic(self) -> None:
        repo = self._init_repo()
        # Advance origin/main modifying shared.txt
        self._git(repo, "checkout", "-qb", "upstream-conflict")
        (repo / "shared.txt").write_text("upstream version\nline 2\n", encoding="utf-8")
        self._git(repo, "commit", "-qam", "upstream edit")
        self._git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")

        # Modify same line on feature branch
        self._git(repo, "checkout", "-qb", "feature", "main")
        (repo / "shared.txt").write_text("feature version\nline 2\n", encoding="utf-8")
        self._git(repo, "commit", "-qam", "feature edit")

        res = self._run_cli("--repo", str(repo), "--base", "origin/main", "--head", "HEAD", "--json")
        self.assertEqual(res.returncode, 1)
        payload = json.loads(res.stdout)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["codes"], ["CONFLICT_WITH_BASE"])

        text_res = self._run_cli("--repo", str(repo), "--base", "origin/main", "--head", "HEAD")
        self.assertEqual(text_res.returncode, 1)
        self.assertIn("CONFLICT_WITH_BASE", text_res.stderr)

    def test_head_drift_and_short_sha_fail_closed(self) -> None:
        repo = self._init_repo()
        head_sha = self._git(repo, "rev-parse", "HEAD")
        wrong_sha = "a" * 40

        res = self._run_cli(
            "--repo",
            str(repo),
            "--base",
            "origin/main",
            "--head",
            "HEAD",
            "--expected-head",
            wrong_sha,
            "--json",
        )
        self.assertEqual(res.returncode, 1)
        payload = json.loads(res.stdout)
        self.assertEqual(payload["codes"], ["HEAD_DRIFT"])

        # Abbreviated SHA must also fail closed
        short_res = self._run_cli(
            "--repo",
            str(repo),
            "--base",
            "origin/main",
            "--head",
            "HEAD",
            "--expected-head",
            head_sha[:7],
            "--json",
        )
        self.assertEqual(short_res.returncode, 1)
        self.assertEqual(json.loads(short_res.stdout)["codes"], ["HEAD_DRIFT"])

    def test_missing_ref_and_invalid_repo_fail_closed(self) -> None:
        repo = self._init_repo()
        missing_ref = self._run_cli(
            "--repo",
            str(repo),
            "--base",
            "refs/remotes/origin/does-not-exist",
            "--head",
            "HEAD",
            "--json",
        )
        self.assertEqual(missing_ref.returncode, 1)
        self.assertEqual(json.loads(missing_ref.stdout)["codes"], ["MISSING_REF"])

        not_a_repo = self.root / "plain_dir"
        not_a_repo.mkdir()
        bad_repo = self._run_cli("--repo", str(not_a_repo), "--json")
        self.assertEqual(bad_repo.returncode, 1)
        self.assertEqual(json.loads(bad_repo.stdout)["codes"], ["INVALID_REPO"])

    def test_packet_dir_valid_with_manifest_json_and_sha256sums(self) -> None:
        packet = self.root / "packet"
        (packet / "head").mkdir(parents=True)
        diff_bytes = b"diff --git a/a.py b/a.py\n+x = 1\n"
        code_bytes = b"x = 1\n"
        (packet / "base.diff").write_bytes(diff_bytes)
        (packet / "head" / "a.py").write_bytes(code_bytes)

        head_sha = "b" * 40
        manifest = {
            "head_sha": head_sha,
            "files": {
                "base.diff": _sha256_bytes(diff_bytes),
                "head/a.py": {"sha256": _sha256_bytes(code_bytes)},
            },
        }
        (packet / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        (packet / "SHA256SUMS").write_text(
            f"{_sha256_bytes(diff_bytes)}  base.diff\n"
            f"{_sha256_bytes(code_bytes)} *./head/a.py\n",
            encoding="utf-8",
        )

        res = self._run_cli("--packet-dir", str(packet), "--expected-head", head_sha, "--json")
        self.assertEqual(res.returncode, 0, res.stderr)
        payload = json.loads(res.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["packet"]["verified_files"], 4)

    def test_packet_dir_list_manifest_format_and_head_drift(self) -> None:
        repo = self._init_repo()
        actual_head = self._git(repo, "rev-parse", "HEAD")
        stale_head = "c" * 40

        packet = self.root / "packet_list"
        packet.mkdir()
        diff_bytes = b"diff --git a/shared.txt b/shared.txt\n"
        (packet / "base.diff").write_bytes(diff_bytes)
        manifest = {
            "head_sha": stale_head,
            "files": [{"path": "base.diff", "sha256": _sha256_bytes(diff_bytes)}],
        }
        (packet / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

        # Combined check catches stale manifest.json head_sha against repo HEAD
        res = self._run_cli(
            "--repo",
            str(repo),
            "--base",
            "origin/main",
            "--head",
            "HEAD",
            "--packet-dir",
            str(packet),
            "--json",
        )
        self.assertEqual(res.returncode, 1)
        payload = json.loads(res.stdout)
        self.assertEqual(payload["codes"], ["HEAD_DRIFT"])

        # Updating manifest head_sha to actual_head passes combined check
        manifest["head_sha"] = actual_head
        (packet / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        ok_res = self._run_cli(
            "--repo",
            str(repo),
            "--base",
            "origin/main",
            "--head",
            "HEAD",
            "--packet-dir",
            str(packet),
            "--json",
        )
        self.assertEqual(ok_res.returncode, 0)

    def test_packet_dir_rejects_git_metadata_missing_diff_and_hash_mismatch(self) -> None:
        packet = self.root / "bad_packet"
        packet.mkdir()
        (packet / ".git").write_text("gitdir: /somewhere\n", encoding="utf-8")

        res = self._run_cli("--packet-dir", str(packet), "--json")
        self.assertEqual(res.returncode, 1)
        payload = json.loads(res.stdout)
        self.assertEqual(payload["codes"], ["GIT_METADATA_PRESENT", "MISSING_BASE_DIFF"])

        # Fix .git and add base.diff, then corrupt SHA256SUMS
        (packet / ".git").unlink()
        (packet / "base.diff").write_text("diff content\n", encoding="utf-8")
        (packet / "SHA256SUMS").write_text(
            f"{'0' * 64}  base.diff\n"
            f"{'1' * 64}  missing.txt\n",
            encoding="utf-8",
        )
        mismatch_res = self._run_cli("--packet-dir", str(packet), "--json")
        self.assertEqual(mismatch_res.returncode, 1)
        mismatch_payload = json.loads(mismatch_res.stdout)
        self.assertEqual(mismatch_payload["codes"], ["HASH_MISMATCH"])
        self.assertEqual(len(mismatch_payload["errors"]), 2)

    def test_packet_dir_rejects_traversal_and_symlinks(self) -> None:
        outside = self.root / "secret.txt"
        outside.write_text("secret\n", encoding="utf-8")

        packet = self.root / "escape_packet"
        packet.mkdir()
        diff_bytes = b"diff\n"
        (packet / "base.diff").write_bytes(diff_bytes)
        (packet / "link.txt").symlink_to(outside)
        (packet / "SHA256SUMS").write_text(
            f"{_sha256_bytes(b'secret\n')}  ../secret.txt\n"
            f"{_sha256_bytes(b'secret\n')}  link.txt\n",
            encoding="utf-8",
        )

        res = self._run_cli("--packet-dir", str(packet), "--json")
        self.assertEqual(res.returncode, 1)
        payload = json.loads(res.stdout)
        self.assertEqual(payload["codes"], ["MANIFEST_INVALID"])
        self.assertEqual(len(payload["errors"]), 2)


if __name__ == "__main__":
    unittest.main()
