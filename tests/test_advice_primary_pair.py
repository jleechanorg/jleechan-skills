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

    def test_runs_codex_and_opus_concurrently_in_distinct_exact_sha_worktrees(self) -> None:
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
        self.executable("codexs", peer_wait % ("codex", "opus", "opus", "codex"))
        self.executable("claude", peer_wait % ("opus", "codex", "codex", "opus"))

        result = self.invoke()

        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads((self.output / "receipt.json").read_text())
        self.assertTrue(receipt["overlap_proven"])
        self.assertEqual(receipt["worktree_shas"], {"codex": self.sha, "opus": self.sha})
        self.assertEqual(receipt["reviewers"]["codex"]["status"], "success")
        self.assertEqual(receipt["reviewers"]["opus"]["status"], "success")
        self.assertNotEqual((self.sync / "codex.cwd").read_text(), (self.sync / "opus.cwd").read_text())
        self.assertEqual(receipt["original_checkout_unchanged"], True)

    def test_preserves_full_permission_flags_on_codex_fallback_and_opus(self) -> None:
        self.executable("codexs", "exit 17\n")
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

    def test_fails_closed_when_original_checkout_changes(self) -> None:
        self.env["ADVICE_TEST_ORIGINAL_REPO"] = str(self.repo)
        self.executable(
            "codexs",
            "printf 'mutated\\n' >> \"$ADVICE_TEST_ORIGINAL_REPO/tracked.txt\"\n"
            "printf 'VERDICT: APPROVED\\nCOVERAGE: all\\n'\n",
        )
        self.executable("claude", "printf 'VERDICT: APPROVED\\nCOVERAGE: all\\n'\n")

        result = self.invoke()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("original checkout changed", result.stderr.lower())
        receipt = json.loads((self.output / "receipt.json").read_text())
        self.assertEqual(receipt["original_checkout_unchanged"], False)


if __name__ == "__main__":
    unittest.main()
