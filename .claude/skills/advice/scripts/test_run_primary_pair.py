#!/usr/bin/env python3
"""Smoke tests for the installed exact-SHA advice runner.

The source checkout has deeper integration tests in tests/test_advice_primary_pair.py.
"""

from __future__ import annotations

import importlib.util
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
