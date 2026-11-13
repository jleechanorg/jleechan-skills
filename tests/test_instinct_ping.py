"""Behavioral tests for the launchd Instinct ping wrapper."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "instinct-ping.sh"


class InstinctPingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / "home"
        self.home.mkdir()
        self.cli = self.home / ".claude/skills/instinct/scripts/instinct.mjs"
        self.cli.parent.mkdir(parents=True)
        self.cli.write_text("// fake CLI path\n", encoding="utf-8")
        self.node = self.home / ".nvm/versions/node/v22.22.0/bin/node"
        self.node.parent.mkdir(parents=True)
        self.node.write_text(
            "#!/bin/sh\n"
            "echo $* >> $FAKE_CALLS\n"
            "case $* in\n"
            '  *read*) echo "$FAKE_READ_OUTPUT"; exit "$FAKE_READ_RC" ;;\n'
            '  *send*) exit "$FAKE_SEND_RC" ;;\n'
            '  *) echo "unexpected fake CLI invocation: $*" >&2; exit 99 ;;\n'
            "esac\n",
            encoding="utf-8",
        )
        self.node.chmod(0o755)
        self.calls = Path(self.temp.name) / "calls"
        self.repo = Path(self.temp.name) / "target"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        subprocess.run(
            ["git", "-C", str(self.repo), "checkout", "-qb", "review/topic"], check=True
        )
        subprocess.run(
            ["git", "-C", str(self.repo), "config", "user.name", "Test"], check=True
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(self.repo),
                "config",
                "user.email",
                "test@example.invalid",
            ],
            check=True,
        )
        (self.repo / "target.txt").write_text("target\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.repo), "add", "target.txt"], check=True)
        subprocess.run(
            ["git", "-C", str(self.repo), "commit", "-qm", "target"], check=True
        )

    def run_tick(self, **overrides: str) -> subprocess.CompletedProcess[str]:
        env = {
            key: value
            for key, value in os.environ.items()
            if key.startswith("LC_") or key in ("LANG", "PATH")
        }
        env.update(
            {
                "HOME": str(self.home),
                "FAKE_CALLS": str(self.calls),
                "FAKE_READ_OUTPUT": "",
                "FAKE_READ_RC": "0",
                "FAKE_SEND_RC": "0",
                "INSTINCT_IMSG_CONTACT": "+15555550199",
                "INSTINCT_PING_TASK": "review task",
                "INSTINCT_PING_REPO": str(self.repo),
                "INSTINCT_PING_PR": "781",
                "INSTINCT_PING_ASK": "review this branch",
            }
        )
        env.update(overrides)
        return subprocess.run(
            ["/bin/bash", str(SCRIPT), "tick"],
            cwd=self.repo,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

    def call_lines(self) -> list[str]:
        return (
            self.calls.read_text(encoding="utf-8").splitlines()
            if self.calls.exists()
            else []
        )

    def request_id(self) -> str:
        state = self.home / ".local/state/instinct-ping/state.json"
        return json.loads(state.read_text(encoding="utf-8"))["request_id"]

    def test_unreadable_reply_read_sends_nothing(self) -> None:
        result = self.run_tick(FAKE_READ_RC="4")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.call_lines()), 1)
        self.assertIn("read", self.call_lines()[0])
        self.assertIn("reply read unavailable", result.stdout.lower())

    def test_send_rc_9_latches_uncertain_and_next_tick_does_not_resend(self) -> None:
        self.run_tick(FAKE_SEND_RC="9")
        first = self.call_lines()
        self.assertTrue(any("send" in line for line in first), first)
        self.run_tick()
        self.assertEqual(self.call_lines(), first)

    def test_old_request_verdict_does_not_stop_or_reset_current_task(self) -> None:
        old_id = "old-request-123"
        self.run_tick(FAKE_READ_OUTPUT=f"REQUEST_ID: {old_id}\nVERDICT: PASS\n")
        current_id = self.request_id()
        self.assertNotEqual(current_id, old_id)
        self.assertTrue(any("send" in line for line in self.call_lines()))

    def test_current_request_verdict_completes_before_send(self) -> None:
        self.run_tick()
        request_id = self.request_id()
        self.calls.write_text("", encoding="utf-8")
        result = self.run_tick(
            FAKE_READ_OUTPUT=f"REQUEST_ID: {request_id} VERDICT: PASS\n"
        )
        self.assertEqual(len(self.call_lines()), 1)
        self.assertIn("verdict received", result.stdout.lower())

    def test_quoted_template_with_current_id_is_not_a_verdict(self) -> None:
        self.run_tick()
        request_id = self.request_id()
        self.calls.write_text("", encoding="utf-8")
        result = self.run_tick(
            FAKE_READ_OUTPUT=(
                f"REQUEST_ID: {request_id}, then VERDICT: PASS|FAIL|BLOCKED, "
                "then cite evidence"
            )
        )
        self.assertTrue(
            any("send" in line for line in self.call_lines()), result.stdout
        )
        self.assertNotIn("verdict received", result.stdout.lower())

    def test_request_names_accessible_pr_branch_commit_and_repo(self) -> None:
        commit = subprocess.check_output(
            ["git", "-C", str(self.repo), "rev-parse", "HEAD"], text=True
        ).strip()
        result = self.run_tick(INSTINCT_PING_DRY_RUN="1")
        self.assertIn(f"repo: {self.repo}", result.stdout)
        self.assertIn("branch: review/topic", result.stdout)
        self.assertIn(f"commit: {commit}", result.stdout)
        self.assertIn("PR: #781", result.stdout)
        self.assertFalse(any("send" in line for line in self.call_lines()))

    def test_reset_creates_a_new_request_id(self) -> None:
        self.run_tick()
        first_id = self.request_id()
        subprocess.run(
            ["/bin/bash", str(SCRIPT), "reset"],
            cwd=self.repo,
            env={"HOME": str(self.home), "PATH": os.environ.get("PATH", "")},
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        self.run_tick()
        self.assertNotEqual(self.request_id(), first_id)

    def test_unconfigured_tick_sends_nothing(self) -> None:
        result = self.run_tick(
            INSTINCT_IMSG_CONTACT="",
            INSTINCT_PING_TASK="",
            INSTINCT_PING_REPO="",
            INSTINCT_PING_PR="",
            INSTINCT_PING_ASK="",
        )
        self.assertEqual(self.call_lines(), [])
        self.assertIn("configuration required", result.stdout.lower())


if __name__ == "__main__":
    unittest.main()
