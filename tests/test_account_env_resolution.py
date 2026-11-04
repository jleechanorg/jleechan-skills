"""Account-specific script defaults resolve from the env-var registry.

See docs/portability-env-vars.md. Each script must target the repository or
channel the operator configured, and must fail with a "not configured" error
naming the variable when nothing is configured or derivable.
"""

import argparse
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / ".claude" / "skills"
CI_QUEUE_TRIM = SKILLS / "ci-queue-trim" / "scripts" / "ci_queue_trim.py"
LUNA = SKILLS / "luna" / "scripts" / "audit_prs.py"
SLACK_UPLOAD = SKILLS / "slack-media-upload" / "scripts" / "slack_upload.py"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StubGhMixin:
    """Run scripts from a non-git temp dir with a stub `gh` first on PATH."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.cwd = self.tmp / "work"
        self.cwd.mkdir()
        self.log = self.tmp / "gh.log"
        bindir = self.tmp / "bin"
        bindir.mkdir()
        gh = bindir / "gh"
        # `gh repo view` prints $STUB_GH_REPO, or exits non-zero when it is
        # unset (no derivable repo); list calls return [].
        gh.write_text(
            "#!/bin/sh\n"
            f'printf "%s\\n" "$*" >> "{self.log}"\n'
            'if [ "$1" = repo ]; then\n'
            '  [ -n "$STUB_GH_REPO" ] || exit 1\n'
            '  echo "$STUB_GH_REPO"; exit 0\n'
            'fi\n'
            "echo '[]'\n"
        )
        gh.chmod(0o755)
        self.env = {
            k: v for k, v in os.environ.items()
            if k not in {"GITHUB_REPOSITORY", "STUB_GH_REPO", "GIT_DIR", "GIT_WORK_TREE"}
        }
        self.env["PATH"] = f"{bindir}{os.pathsep}{self.env.get('PATH', '')}"
        self.env["GIT_CEILING_DIRECTORIES"] = str(self.tmp)

    def tearDown(self):
        self._tmp.cleanup()

    def run_script(self, script, *args, **extra_env):
        return subprocess.run(
            [sys.executable, str(script), *args],
            cwd=self.cwd, env={**self.env, **extra_env},
            capture_output=True, text=True, timeout=60,
        )

    def gh_calls(self):
        return self.log.read_text() if self.log.exists() else ""


class CiQueueTrimRepoTest(StubGhMixin, unittest.TestCase):
    def test_github_repository_wins_over_derived_repo(self):
        result = self.run_script(
            CI_QUEUE_TRIM, GITHUB_REPOSITORY="acme/widgets", STUB_GH_REPO="other/derived"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--repo acme/widgets", self.gh_calls())
        self.assertNotIn("other/derived", self.gh_calls())

    def test_unset_repository_is_derived_from_gh(self):
        result = self.run_script(CI_QUEUE_TRIM, STUB_GH_REPO="other/derived")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--repo other/derived", self.gh_calls())

    def test_unconfigured_repo_exits_naming_variable(self):
        result = self.run_script(CI_QUEUE_TRIM)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("GITHUB_REPOSITORY", result.stderr)
        self.assertNotIn("run list", self.gh_calls())


class LunaRepoTest(StubGhMixin, unittest.TestCase):
    def test_github_repository_wins_over_derived_repo(self):
        result = self.run_script(
            LUNA, GITHUB_REPOSITORY="acme/widgets", STUB_GH_REPO="other/derived"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--repo acme/widgets", self.gh_calls())
        self.assertNotIn("other/derived", self.gh_calls())

    def test_unset_repository_is_derived_from_gh(self):
        result = self.run_script(LUNA, STUB_GH_REPO="other/derived")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--repo other/derived", self.gh_calls())

    def test_unconfigured_repo_exits_naming_variable(self):
        result = self.run_script(LUNA)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("GITHUB_REPOSITORY", result.stderr)
        self.assertNotIn("pr list", self.gh_calls())

    def test_review_dir_is_named_after_target_repo(self):
        audit_prs = load("luna_audit_prs_env", LUNA)
        with tempfile.TemporaryDirectory() as scratch:
            scratch = Path(scratch).resolve()
            with mock.patch.object(audit_prs, "_scratch_root", return_value=str(scratch)):
                review_dir = audit_prs.get_luna_review_dir("acme/widgets")
            self.assertEqual(Path(review_dir), scratch / "widgets" / "luna-reviews")


class SlackUploadDmChannelTest(unittest.TestCase):
    def resolve(self, **env):
        try:
            slack_upload = load("slack_upload_env", SLACK_UPLOAD)
        except ImportError as exc:
            self.skipTest(f"slack_upload dependency missing: {exc}")
        args = argparse.Namespace(channel=None, dm=True)
        with mock.patch.dict(os.environ, env, clear=True):
            return slack_upload.resolve_channel(args)

    def test_operator_dm_channel_is_used(self):
        self.assertEqual(self.resolve(SLACK_OPERATOR_DM_CHANNEL="D1"), "D1")

    def test_unconfigured_dm_exits_naming_variable(self):
        with self.assertRaises(SystemExit) as raised:
            self.resolve()
        self.assertIn("SLACK_OPERATOR_DM_CHANNEL", str(raised.exception.code))


if __name__ == "__main__":
    unittest.main()
