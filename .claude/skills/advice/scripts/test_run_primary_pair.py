#!/usr/bin/env python3
"""Smoke tests for the installed exact-SHA advice runner.

The source checkout has deeper integration tests in tests/test_advice_primary_pair.py.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


RUNNER_PATH = Path(__file__).with_name("run_primary_pair.py")
SPEC = importlib.util.spec_from_file_location("advice_primary_pair", RUNNER_PATH)
assert SPEC is not None and SPEC.loader is not None
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class InstalledRunnerTest(unittest.TestCase):
    def test_review_scratch_root_uses_canonical_resolver(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            scratch = Path(temporary) / "scratch"
            scratch.mkdir()
            completed = subprocess.CompletedProcess(
                [str(runner.SCRATCH_RESOLVER)], 0, stdout=f"{scratch}\n", stderr=""
            )
            with mock.patch.object(runner.subprocess, "run", return_value=completed) as resolve:
                self.assertEqual(runner.resolve_review_scratch_root(), scratch)
        self.assertEqual(resolve.call_args.args[0], [str(runner.SCRATCH_RESOLVER)])

    def test_review_scratch_root_refuses_unavailable_resolver(self) -> None:
        completed = subprocess.CompletedProcess(
            [str(runner.SCRATCH_RESOLVER)], 1, stdout="", stderr="Scratch volume unavailable\n"
        )
        with mock.patch.object(runner.subprocess, "run", return_value=completed):
            with self.assertRaisesRegex(RuntimeError, "canonical Scratch resolver failed"):
                runner.resolve_review_scratch_root()

    def test_review_scratch_root_accepts_canonical_no_scratch_fallback(self) -> None:
        completed = subprocess.CompletedProcess(
            [str(runner.SCRATCH_RESOLVER)], 0, stdout="/tmp\n", stderr=""
        )
        with mock.patch.object(runner.subprocess, "run", return_value=completed):
            self.assertEqual(runner.resolve_review_scratch_root(), Path("/tmp"))

    def test_scratch_dir_thin_dispatches_to_explicit_disk_magician_cli(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            diskm = root / "diskm"
            diskm.write_text("#!/bin/sh\nprintf '/canonical-scratch\\n'\n")
            diskm.chmod(0o755)
            result = subprocess.run(
                [str(runner.SCRATCH_RESOLVER), "tmp"],
                capture_output=True,
                text=True,
                env={**os.environ, "DISK_MAGICIAN_DISKM_BIN": str(diskm)},
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "/canonical-scratch\n")

    def test_scratch_dir_preserves_disk_magician_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            diskm = root / "diskm"
            diskm.write_text("#!/bin/sh\necho unavailable >&2\nexit 75\n")
            diskm.chmod(0o755)
            result = subprocess.run(
                [str(runner.SCRATCH_RESOLVER)],
                capture_output=True,
                text=True,
                env={**os.environ, "DISK_MAGICIAN_DISKM_BIN": str(diskm)},
            )
        self.assertEqual(result.returncode, 75)
        self.assertEqual(result.stderr, "unavailable\n")

    def test_scratch_dir_uses_user_local_cli_outside_login_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "home"
            diskm = home / ".local" / "bin" / "diskm"
            diskm.parent.mkdir(parents=True)
            diskm.write_text("#!/bin/sh\nprintf '/user-local-scratch\\n'\n")
            diskm.chmod(0o755)
            env = {
                **os.environ,
                "HOME": str(home),
                "PATH": "/usr/bin:/bin",
                "BASH_ENV": "/dev/null",
            }
            env.pop("DISK_MAGICIAN_DISKM_BIN", None)
            result = subprocess.run(
                [str(runner.SCRATCH_RESOLVER)], capture_output=True, text=True, env=env
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "/user-local-scratch\n")

    def test_scratch_allocation_failure_does_not_reserve_output_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / "repo"
            scratch = root / "scratch"
            repo.mkdir()
            scratch.mkdir()
            for args in (
                ("init", "-q"),
                ("config", "user.email", "test@example.invalid"),
                ("config", "user.name", "Test"),
            ):
                subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)
            (repo / "tracked.txt").write_text("base\n")
            subprocess.run(["git", "-C", str(repo), "add", "tracked.txt"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-qm", "base"], check=True)
            packet = root / "packet.txt"
            packet.write_text("Review this revision.\n")
            output = root / "output"
            args = [
                "--repo", str(repo), "--ref", "HEAD", "--packet-file", str(packet),
                "--output-dir", str(output), "--reviewers", "codex",
            ]
            with mock.patch.object(runner, "resolve_review_scratch_root", return_value=scratch), \
                    mock.patch.object(runner.tempfile, "mkdtemp", side_effect=OSError("full")):
                self.assertEqual(runner.main(args), 2)
            self.assertFalse(output.exists())

            review = {
                "status": "success", "transport": "test",
                "stdout": "VERDICT: APPROVED\nCOVERAGE: all\n", "attempts": [],
                "started_ns": 1, "ended_ns": 2,
            }
            with mock.patch.object(runner, "resolve_review_scratch_root", return_value=scratch), \
                    mock.patch.object(runner, "codex_lane", return_value=review):
                self.assertEqual(runner.main(args), 0)
            self.assertTrue((output / "receipt.json").is_file())

    def test_reviewer_gets_eof_with_parent_stdin_open(self) -> None:
        child = (
            "import importlib.util, sys\n"
            f"spec = importlib.util.spec_from_file_location('r', {str(RUNNER_PATH)!r})\n"
            "r = importlib.util.module_from_spec(spec); spec.loader.exec_module(r)\n"
            "result = r.execute([sys.executable, '-c', "
            "'import sys; sys.stdin.read(); print(\"EOF\")'], '.', 'review', 1, 0.2)\n"
            "print('RESULT', result[0], result[1].strip(), result[3], flush=True)\n"
        )
        parent = subprocess.Popen(
            [sys.executable, "-c", child], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        try:
            parent.wait(timeout=8)
            output = parent.stdout.read()
            error = parent.stderr.read()
            self.assertEqual(parent.returncode, 0, error)
            self.assertIn("RESULT 0 EOF False", output)
        finally:
            if parent.poll() is None:
                parent.kill()
                parent.wait(timeout=2)
            parent.stdin.close()
            parent.stdout.close()
            parent.stderr.close()

    def test_ps_has_ten_second_timeout(self) -> None:
        completed = subprocess.CompletedProcess(["ps"], 0, stdout="123 1 started\n", stderr="")
        with mock.patch.object(runner.subprocess, "run", return_value=completed) as ps:
            self.assertEqual(runner.process_snapshot(), {123: (1, "started")})
        self.assertEqual(ps.call_args.kwargs["timeout"], 10.0)

    def test_dirty_revision_is_rejected_before_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / "repo"
            repo.mkdir()
            for args in (
                ("init", "-q"),
                ("config", "user.email", "test@example.invalid"),
                ("config", "user.name", "Test"),
            ):
                subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)
            (repo / "tracked.txt").write_text("base\n")
            subprocess.run(["git", "-C", str(repo), "add", "tracked.txt"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-qm", "base"], check=True)
            (repo / "tracked.txt").write_text("dirty\n")
            packet = root / "packet.txt"
            packet.write_text("Review this revision.\n")
            with mock.patch.object(runner, "create_clone") as clone:
                result = runner.main([
                    "--repo", str(repo), "--ref", "HEAD", "--packet-file", str(packet),
                    "--output-dir", str(root / "output"), "--reviewers", "codex",
                ])
            self.assertEqual(result, 2)
            clone.assert_not_called()
            self.assertFalse((root / "output").exists())

    def test_verdict_requires_a_recognizable_line(self) -> None:
        self.assertTrue(runner.has_verdict("VERDICT: APPROVED\n"))
        self.assertTrue(runner.has_verdict("**VERDICT:** APPROVED\n"))
        self.assertFalse(runner.has_verdict("I reviewed it; the verdict is unclear.\n"))

    def test_reviewer_selection_remains_codex_and_opus(self) -> None:
        required = [
            "--repo", ".", "--ref", "HEAD", "--packet-file", "packet.txt",
            "--output-dir", "/tmp/advice-test-output",
        ]
        with mock.patch.dict(runner.os.environ, {"ADVICE_CODEX_MODEL": "gpt-6-sol"}):
            self.assertEqual(runner.parse_args(required).reviewers, ["codex", "opus"])
            self.assertEqual(runner.parse_args(required + ["--reviewers", "opus"]).reviewers, ["opus"])
            with self.assertRaises(SystemExit):
                runner.parse_args(required + ["--reviewers", "codex,agy"])


if __name__ == "__main__":
    unittest.main()
