"""Executable behavior checks for the PR creation quantity hook."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
HOOK = REPO / ".claude/hooks/protect-pr-create.sh"


def open_pr(number, head="other", base="main"):
    return {"number": number, "headRefName": head, "baseRefName": base}


class ProtectPrCreateHookTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(
            prefix="protect-pr-create-", dir="/tmp"
        )
        self.temp_dir = Path(self.temp.name)
        self.gh_stub_dir = self.temp_dir / "bin"
        self.gh_stub_dir.mkdir()
        self.gh_call_marker = self.temp_dir / "gh-called"
        gh_stub = self.gh_stub_dir / "gh"
        gh_stub.write_text(
            "#!/bin/sh\nprintf called > \"$GH_CALL_MARKER\"\nexit 91\n"
        )
        gh_stub.chmod(0o755)
        self.path = os.pathsep.join(
            [str(self.gh_stub_dir), str(Path(sys.executable).parent), os.defpath]
        )

    def tearDown(self):
        self.temp.cleanup()

    def run_hook(self, command, open_prs, *, override_env=False):
        environment = dict(os.environ)
        environment["PROTECT_PR_CREATE_MOCK_JSON"] = json.dumps(open_prs)
        environment["BASH_ENV"] = "/dev/null"
        environment["PATH"] = self.path
        environment["GH_CALL_MARKER"] = str(self.gh_call_marker)
        if override_env:
            environment["ALLOW_PR_STACK_OVERRIDE"] = "1"
        else:
            environment.pop("ALLOW_PR_STACK_OVERRIDE", None)
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": command},
            "cwd": str(REPO),
        }
        return subprocess.run(
            [str(HOOK)],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            cwd=REPO,
            env=environment,
            timeout=5,
            check=False,
        )

    def assert_mocked_github(self):
        self.assertFalse(
            self.gh_call_marker.exists(),
            "the hook bypassed its fixture and attempted a GitHub call",
        )

    def test_main_target_does_not_enforce_stack_caps(self):
        result = self.run_hook("gh pr create --head feature --base main", [])
        self.assert_mocked_github()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_split_below_cap_is_allowed(self):
        existing = [open_pr(i, f"split/widget/{i}") for i in range(4)]
        result = self.run_hook(
            "gh pr create --head split/widget/new --base main", existing
        )
        self.assert_mocked_github()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_split_at_cap_is_blocked(self):
        existing = [open_pr(i, f"split/widget/{i}") for i in range(5)]
        result = self.run_hook(
            "gh pr create --head split/widget/new --base main", existing
        )
        self.assert_mocked_github()
        self.assertEqual(result.returncode, 2)
        self.assertIn("split PR quantity cap", result.stderr)

    def test_stacked_below_cap_is_allowed(self):
        existing = [open_pr(i, base="parent") for i in range(8)]
        result = self.run_hook(
            "gh pr create --head feature --base parent", existing
        )
        self.assert_mocked_github()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_stacked_at_cap_is_blocked(self):
        existing = [open_pr(i, base="parent") for i in range(9)]
        result = self.run_hook(
            "gh pr create --head feature --base parent", existing
        )
        self.assert_mocked_github()
        self.assertEqual(result.returncode, 2)
        self.assertIn("stacked PR ceiling", result.stderr)

    def test_inline_override_allows_authorized_split(self):
        existing = [open_pr(i, f"split/widget/{i}") for i in range(5)]
        result = self.run_hook(
            "ALLOW_PR_STACK_OVERRIDE=1 gh pr create --head split/widget/new --base main",
            existing,
        )
        self.assert_mocked_github()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_env_prefix_allows_authorized_stack(self):
        existing = [open_pr(i, base="parent") for i in range(9)]
        result = self.run_hook(
            "env ALLOW_PR_STACK_OVERRIDE=1 gh pr create --head feature --base parent",
            existing,
        )
        self.assert_mocked_github()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_environment_override_allows_authorized_stack(self):
        existing = [open_pr(i, base="parent") for i in range(9)]
        result = self.run_hook(
            "gh pr create --head feature --base parent", existing, override_env=True
        )
        self.assert_mocked_github()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_text_mention_does_not_authorize_override(self):
        existing = [open_pr(i, f"split/widget/{i}") for i in range(5)]
        result = self.run_hook(
            "echo ALLOW_PR_STACK_OVERRIDE=1 && gh pr create --head split/widget/new --base main",
            existing,
        )
        self.assert_mocked_github()
        self.assertEqual(result.returncode, 2)
        self.assertIn("split PR quantity cap", result.stderr)


if __name__ == "__main__":
    unittest.main()
