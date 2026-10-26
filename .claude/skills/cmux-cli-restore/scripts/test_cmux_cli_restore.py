#!/usr/bin/env python3
"""Regression tests for cmux-cli-restore.sh.

The dot-coordination reviewer found a fail-open: a failed `cmux capture-pane`
meant "no human gate", so the script would still send ctrl+c into a surface it
could not read. These tests pin the closed behaviour: if the surface cannot be
read, nothing is sent at all.
"""
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("cmux-cli-restore.sh")
WS = "workspace:1000120002"
SF = "surface:1000120005"


class StubCmux:
    """A stub `cmux` on PATH that records every invocation and replies per mode."""

    def __init__(self, mode: str):
        self.dir = Path(tempfile.mkdtemp(prefix="cmux-stub-"))
        self.log = self.dir / "calls.log"
        self.log.write_text("")
        stub = self.dir / "cmux"
        stub.write_text(
            "#!/bin/bash\n"
            f'printf "%s\\n" "$*" >> "{self.log}"\n'
            'case "$*" in\n'
            f'  *capture-pane*)\n'
            f'    case "{mode}" in\n'
            '      fail) exit 1 ;;\n'
            '      empty) exit 0 ;;\n'
            '      gate) printf "%s\\n" "Goal remains blocked pending human merge approval"; exit 0 ;;\n'
            '      clean) printf "%s\\n" "jleechan@host:~/work$"; exit 0 ;;\n'
            '    esac ;;\n'
            '  *) exit 0 ;;\n'
            'esac\n'
        )
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    def calls(self) -> list[str]:
        return [line for line in self.log.read_text().splitlines() if line.strip()]

    def sent(self) -> list[str]:
        return [c for c in self.calls() if c.startswith(("send ", "send-key "))]


def run(stub: StubCmux) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PATH"] = f"{stub.dir}:{env.get('PATH', '')}"
    return subprocess.run(
        ["bash", str(SCRIPT), "--workspace", WS, "--surface", SF, "--cli", "codex"],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )


class FailClosedCaptureTest(unittest.TestCase):
    def test_unreadable_surface_aborts_without_any_keystroke(self):
        stub = StubCmux("fail")
        proc = run(stub)
        self.assertNotEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(proc.returncode, 7, "expected the capture-failure exit code")
        self.assertEqual(stub.sent(), [], f"sent despite unreadable surface: {stub.sent()}")
        self.assertIn("no keystroke sent", proc.stdout)

    def test_empty_capture_aborts_without_any_keystroke(self):
        stub = StubCmux("empty")
        proc = run(stub)
        self.assertNotEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(stub.sent(), [], f"sent on an empty capture: {stub.sent()}")

    def test_human_gate_refuses_without_any_keystroke(self):
        stub = StubCmux("gate")
        proc = run(stub)
        self.assertEqual(proc.returncode, 4, proc.stdout + proc.stderr)
        self.assertIn("human gate", proc.stdout)
        self.assertEqual(stub.sent(), [], f"sent into a human-gated lane: {stub.sent()}")

    def test_dry_run_never_sends(self):
        stub = StubCmux("clean")
        env = dict(os.environ)
        env["PATH"] = f"{stub.dir}:{env.get('PATH', '')}"
        proc = subprocess.run(
            ["bash", str(SCRIPT), "--dry-run", "--workspace", WS, "--surface", SF, "--cli", "codex"],
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
        )
        self.assertEqual(stub.sent(), [], f"dry-run sent: {stub.sent()}")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
