#!/usr/bin/env python3
"""Executable regression tests for the isolated /advice primary pair."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parent.parent
    / ".claude"
    / "skills"
    / "advice"
    / "scripts"
    / "run_primary_pair.py"
)


def run(*args: str, cwd: Path | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, env=env, text=True, capture_output=True, check=False)


class PrimaryPairTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.bin = self.root / "bin"
        self.sync = self.root / "sync"
        self.output = self.root / "out"
        self.bin.mkdir()
        self.sync.mkdir()
        run("git", "init", "-q", str(self.repo))
        run("git", "config", "user.email", "jleechan2015@users.noreply.github.com", cwd=self.repo)
        run("git", "config", "user.name", "Test", cwd=self.repo)
        (self.repo / "tracked.txt").write_text("original\n")
        run("git", "add", "tracked.txt", cwd=self.repo)
        run("git", "commit", "-qm", "fixture", cwd=self.repo)
        self.sha = run("git", "rev-parse", "HEAD", cwd=self.repo).stdout.strip()
        self.packet = self.root / "packet.txt"
        self.packet.write_text("DECISION:\nReview exact target.\n")
        self.env = os.environ.copy()
        self.env["PATH"] = f"{self.bin}:{self.env['PATH']}"
        self.env["ADVICE_TEST_SYNC_DIR"] = str(self.sync)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def executable(self, name: str, body: str) -> None:
        path = self.bin / name
        path.write_text("#!/bin/sh\nset -eu\n" + body)
        path.chmod(0o755)

    def invoke(self) -> subprocess.CompletedProcess[str]:
        return run(
            "python3",
            str(SCRIPT),
            "--repo",
            str(self.repo),
            "--ref",
            self.sha,
            "--packet-file",
            str(self.packet),
            "--output-dir",
            str(self.output),
            env=self.env,
        )

    def test_runs_codex_and_opus_concurrently_in_independent_exact_sha_clones(self) -> None:
        peer_wait = """
touch "$ADVICE_TEST_SYNC_DIR/%s.started"
i=0
while [ ! -e "$ADVICE_TEST_SYNC_DIR/%s.started" ] && [ "$i" -lt 100 ]; do
  sleep 0.01
  i=$((i + 1))
done
[ -e "$ADVICE_TEST_SYNC_DIR/%s.started" ]
pwd > "$ADVICE_TEST_SYNC_DIR/%s.cwd"
printf 'VERDICT: APPROVED\\nCOVERAGE: all\\n'
"""
        self.executable("codex", peer_wait % ("codex", "opus", "opus", "codex"))
        self.executable("claude", peer_wait % ("opus", "codex", "codex", "opus"))

        result = self.invoke()

        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads((self.output / "receipt.json").read_text())
        self.assertTrue(receipt["overlap_proven"])
        self.assertEqual(receipt["clone_shas"], {"codex": self.sha, "opus": self.sha})
        self.assertEqual(receipt["checkout_kind"], "independent_clone_no_local")
        self.assertEqual(receipt["reviewers"]["codex"]["status"], "success")
        self.assertEqual(receipt["reviewers"]["opus"]["status"], "success")
        self.assertNotEqual((self.sync / "codex.cwd").read_text(), (self.sync / "opus.cwd").read_text())
        self.assertEqual(receipt["original_checkout_unchanged"], True)

    def test_preserves_explicit_full_permission_flags_on_codex_and_opus(self) -> None:
        self.executable(
            "codex",
            "printf '%s\\n' \"$@\" > \"$ADVICE_TEST_SYNC_DIR/codex.args\"\n"
            "printf 'VERDICT: APPROVED\\nCOVERAGE: all\\n'\n",
        )
        self.executable(
            "claude",
            "printf '%s\\n' \"$@\" > \"$ADVICE_TEST_SYNC_DIR/opus.args\"\n"
            "printf 'VERDICT: APPROVED\\nCOVERAGE: all\\n'\n",
        )

        result = self.invoke()

        self.assertEqual(result.returncode, 0, result.stderr)
        codex_args = (self.sync / "codex.args").read_text().splitlines()
        opus_args = (self.sync / "opus.args").read_text().splitlines()
        self.assertIn("--yolo", codex_args)
        self.assertIn("gpt-5.6-terra", codex_args)
        self.assertIn("--dangerously-skip-permissions", opus_args)
        self.assertIn("opus", opus_args)

    def test_exit_zero_without_a_verdict_is_an_error_and_other_lane_can_succeed(self) -> None:
        self.executable("codex", "printf 'no structured verdict\\n'\n")
        self.executable("claude", "printf 'VERDICT: APPROVED\\nCOVERAGE: all\\n'\n")

        result = self.invoke()

        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads((self.output / "receipt.json").read_text())
        self.assertEqual(receipt["reviewers"]["codex"]["status"], "error")
        self.assertEqual(receipt["reviewers"]["codex"]["attempts"][0]["failure"], "missing_verdict")
        self.assertEqual(receipt["reviewers"]["opus"]["status"], "success")

    def test_fails_when_both_lanes_return_empty_or_malformed_output(self) -> None:
        self.executable("codex", "printf ''\n")
        self.executable("claude", "printf 'VERDICT:   \\n'\n")

        result = self.invoke()

        self.assertEqual(result.returncode, 4)
        self.assertIn("neither primary reviewer returned a verdict", result.stderr)
        receipt = json.loads((self.output / "receipt.json").read_text())
        self.assertEqual(receipt["reviewers"]["codex"]["status"], "error")
        self.assertEqual(receipt["reviewers"]["opus"]["status"], "error")

    def test_independent_clones_isolate_ref_and_config_mutations(self) -> None:
        mutation = (
            "git config reviewer.evil true\n"
            "git update-ref refs/heads/reviewer-evil HEAD\n"
            "printf 'VERDICT: APPROVED\\nCOVERAGE: all\\n'\n"
        )
        self.executable("codex", mutation)
        self.executable("claude", mutation)

        result = self.invoke()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotEqual(
            run("git", "config", "--get", "reviewer.evil", cwd=self.repo).returncode,
            0,
        )
        self.assertNotEqual(
            run("git", "show-ref", "--verify", "--quiet", "refs/heads/reviewer-evil", cwd=self.repo).returncode,
            0,
        )

    def test_refuses_dirty_input_checkout_before_dispatch(self) -> None:
        (self.repo / "untracked.txt").write_text("not represented by the SHA\n")
        self.executable("codex", "touch \"$ADVICE_TEST_SYNC_DIR/codex.ran\"\n")
        self.executable("claude", "touch \"$ADVICE_TEST_SYNC_DIR/opus.ran\"\n")

        result = self.invoke()

        self.assertEqual(result.returncode, 2)
        self.assertIn("input checkout must be clean", result.stderr.lower())
        self.assertFalse((self.sync / "codex.ran").exists())
        self.assertFalse((self.sync / "opus.ran").exists())

    def test_refuses_tracked_input_changes_before_dispatch(self) -> None:
        (self.repo / "tracked.txt").write_text("dirty tracked state\n")
        self.executable("codex", "touch \"$ADVICE_TEST_SYNC_DIR/codex.ran\"\n")
        self.executable("claude", "touch \"$ADVICE_TEST_SYNC_DIR/opus.ran\"\n")

        result = self.invoke()

        self.assertEqual(result.returncode, 2)
        self.assertIn("input checkout must be clean", result.stderr.lower())
        self.assertFalse((self.sync / "codex.ran").exists())
        self.assertFalse((self.sync / "opus.ran").exists())

    def test_fails_closed_when_original_checkout_changes(self) -> None:
        self.env["ADVICE_TEST_ORIGINAL_REPO"] = str(self.repo)
        self.executable(
            "codex",
            "printf 'mutated\\n' >> \"$ADVICE_TEST_ORIGINAL_REPO/tracked.txt\"\n"
            "printf 'VERDICT: APPROVED\\nCOVERAGE: all\\n'\n",
        )
        self.executable("claude", "printf 'VERDICT: APPROVED\\nCOVERAGE: all\\n'\n")

        result = self.invoke()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("original checkout or repository metadata changed", result.stderr.lower())
        receipt = json.loads((self.output / "receipt.json").read_text())
        self.assertEqual(receipt["original_checkout_unchanged"], False)

    def test_fails_closed_when_an_ignored_file_changes_without_reading_its_content(self) -> None:
        (self.repo / ".gitignore").write_text(".env\n")
        run("git", "add", ".gitignore", cwd=self.repo)
        run("git", "commit", "-qm", "ignore local environment", cwd=self.repo)
        self.sha = run("git", "rev-parse", "HEAD", cwd=self.repo).stdout.strip()
        ignored = self.repo / ".env"
        ignored.write_text("SECRET=do-not-read\n")
        self.env["ADVICE_TEST_IGNORED_FILE"] = str(ignored)
        self.executable(
            "codex",
            "printf 'ordinary ignored-file mutation with a new size\\n' > \"$ADVICE_TEST_IGNORED_FILE\"\n"
            "printf 'VERDICT: APPROVED\\nCOVERAGE: all\\n'\n",
        )
        self.executable("claude", "printf 'VERDICT: APPROVED\\nCOVERAGE: all\\n'\n")

        result = self.invoke()

        self.assertEqual(result.returncode, 3)
        self.assertIn("original checkout or repository metadata changed", result.stderr.lower())
        receipt = json.loads((self.output / "receipt.json").read_text())
        self.assertEqual(receipt["original_repository_unchanged"], False)

    def test_ignored_file_fingerprint_does_not_require_content_access(self) -> None:
        (self.repo / ".gitignore").write_text(".env\n")
        run("git", "add", ".gitignore", cwd=self.repo)
        run("git", "commit", "-qm", "ignore local environment", cwd=self.repo)
        self.sha = run("git", "rev-parse", "HEAD", cwd=self.repo).stdout.strip()
        ignored = self.repo / ".env"
        ignored.write_text("SECRET=do-not-read\n")
        ignored.chmod(0)
        self.executable("codex", "printf 'VERDICT: APPROVED\\nCOVERAGE: all\\n'\n")
        self.executable("claude", "printf 'VERDICT: APPROVED\\nCOVERAGE: all\\n'\n")

        try:
            result = self.invoke()
        finally:
            ignored.chmod(0o600)

        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
