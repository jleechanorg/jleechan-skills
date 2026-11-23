import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import pr_nudger_round as round_cli  # noqa: E402


class RoundTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.repo = self.root / "work"
        git = lambda *a: subprocess.run(["git", "-C", str(self.repo), *a], check=True, capture_output=True)
        self.repo.mkdir()
        git("init", "-q", "-b", "feature")
        git("remote", "add", "origin", "https://github.com/base/project.git")
        git("-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "--allow-empty", "-m", "x")
        self.config = self.root / "config.json"
        self.policy = self.root / "policy.md"
        self.policy.write_text("# Shared policy\nEscalate only what only the user can do\n")
        self.codex_home = self.root / "codex"
        self.codex_home.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *argv):
        with patch.dict(os.environ, {"CODEX_HOME": str(self.codex_home)}), \
                patch.object(round_cli.shutil, "which", side_effect=lambda name: f"/bin/{name}"):
            round_cli.main(["--config", str(self.config), *argv])

    def test_enroll_writes_profile_wrapper_and_managed_target_then_retire(self):
        scope = self.root / "scope.md"
        scope.write_text("Scope: prove the fixture behavior.\n")
        self.run_cli("enroll", "--repo", "base/project", "--pr", "12", "--cwd", str(self.repo),
                     "--model", "fixture-model", "--hours", "1", "--scope-file", str(scope),
                     "--policy", str(self.policy), "--profiles-dir", str(self.root / "profiles"))
        item = json.loads(self.config.read_text())["targets"][0]
        enrollment = item["enrollment"]
        self.assertFalse(item["observe_only"])
        self.assertEqual((enrollment["branch"], enrollment["head_repo"], enrollment["model"]),
                         ("feature", "base/project", "fixture-model"))
        self.assertTrue(enrollment["managed_exclusive"] and enrollment["launch_authorized"])
        profile = Path(enrollment["profile_dir"])
        text = (profile / "AGENTS.md").read_text()
        self.assertTrue(text.startswith("# Shared policy"))
        self.assertIn("owns only base/project PR #12", text)
        self.assertTrue(text.rstrip().endswith("prove the fixture behavior."))
        self.assertEqual(os.readlink(profile / "auth.json"), str(self.codex_home / "auth.json"))
        wrapper = Path(enrollment["cli_bin"]).read_text()
        self.assertIn("exit 124", wrapper)
        self.assertIn("/bin/codex", wrapper)
        first = enrollment["cli_bin"]
        with patch.object(round_cli.time, "time", return_value=round_cli.time.time() + 60):
            self.run_cli("enroll", "--repo", "base/project", "--pr", "12", "--cwd", str(self.repo),
                         "--model", "fixture-model", "--hours", "2",
                         "--policy", str(self.policy), "--profiles-dir", str(self.root / "profiles"))
        # Re-enrolling changes the wrapper path, so the nudger retires the old session.
        self.assertNotEqual(json.loads(self.config.read_text())["targets"][0]["enrollment"]["cli_bin"], first)
        self.run_cli("retire", "--repo", "base/project", "--pr", "12")
        with self.assertRaises(SystemExit):
            self.run_cli("retire", "--repo", "base/project", "--pr", "99")
        self.assertTrue(json.loads(self.config.read_text())["targets"][0]["observe_only"])

    def test_retry_now_marks_the_target_due(self):
        state = self.root / "state"
        state.mkdir()
        self.config.write_text(json.dumps({"state_dir": str(state), "targets": []}))
        with sqlite3.connect(state / "receipts.sqlite3") as db:
            db.execute("CREATE TABLE target (repo TEXT, number INTEGER, next_due REAL)")
            db.execute("INSERT INTO target VALUES ('base/project', 12, 9e12)")
        self.run_cli("retry-now", "--repo", "base/project", "--pr", "12")
        with sqlite3.connect(state / "receipts.sqlite3") as db:
            self.assertLess(db.execute("SELECT next_due FROM target").fetchone()[0], 9e12)
        (state / "receipts.sqlite3").unlink()
        with self.assertRaises(SystemExit):
            self.run_cli("retry-now", "--repo", "base/project", "--pr", "12")
        self.assertFalse((state / "receipts.sqlite3").exists())
        with patch.object(round_cli.subprocess, "run") as run:
            self.run_cli("retry-now", "--repo", "base/project", "--pr", "12", "--kick")
        run.assert_called_once()
        self.assertFalse((state / "receipts.sqlite3").exists())

    def test_retry_now_kick_supports_named_lanes(self):
        self.config.write_text(json.dumps({"state_dir": str(self.root / "missing"), "targets": []}))
        with patch.object(round_cli.os, "getuid", return_value=501), \
                patch.object(round_cli.subprocess, "run") as run:
            with patch.object(round_cli.sys, "platform", "darwin"):
                self.run_cli("retry-now", "--repo", "base/project", "--pr", "12", "--kick")
                self.run_cli("retry-now", "--repo", "base/project", "--pr", "12", "--kick",
                             "--name", "pr-owner-nudger-agy")
            with patch.object(round_cli.sys, "platform", "linux"):
                self.run_cli("retry-now", "--repo", "base/project", "--pr", "12", "--kick")
                self.run_cli("retry-now", "--repo", "base/project", "--pr", "12", "--kick",
                             "--name", "pr-owner-nudger-agy")
        self.assertEqual(
            [call.args[0] for call in run.call_args_list],
            [
                ["launchctl", "kickstart", "gui/501/org.prw.pr-owner-nudger"],
                ["launchctl", "kickstart", "gui/501/org.prw.pr-owner-nudger-agy"],
                ["systemctl", "--user", "start", "pr-owner-nudger.service"],
                ["systemctl", "--user", "start", "pr-owner-nudger-agy.service"],
            ],
        )
        for bad in ("../x", "a b", ".hidden"):
            with patch.object(round_cli.subprocess, "run") as bad_run:
                with self.assertRaises(SystemExit):
                    self.run_cli("retry-now", "--repo", "base/project", "--pr", "12", "--kick", "--name", bad)
                bad_run.assert_not_called()

    def test_enroll_supports_agy_cli_without_codex_auth_or_codex_policy(self):
        scope = self.root / "scope.md"
        scope.write_text("Scope: prove agy owner.\n")
        with patch.object(round_cli, "POLICY", self.root / "missing-codex.md"), \
                patch.object(round_cli, "AGY_POLICY", self.root / "missing-agy.md"):
            self.run_cli("enroll", "--cli", "agy", "--headless-only", "--repo", "base/project", "--pr", "12",
                         "--cwd", str(self.repo), "--model", "gemini-4-hydrogen-high",
                         "--hours", "1", "--scope-file", str(scope),
                         "--profiles-dir", str(self.root / "profiles"))
        item = json.loads(self.config.read_text())["targets"][0]
        enrollment = item["enrollment"]
        self.assertEqual(enrollment["cli"], "agy")
        self.assertEqual(enrollment["model"], "gemini-4-hydrogen-high")
        self.assertTrue(enrollment["headless_only"])
        self.assertNotIn("resume_sandbox", enrollment)
        profile = Path(enrollment["profile_dir"])
        self.assertFalse((profile / "auth.json").exists())
        self.assertIn("Scope: prove agy owner.", (profile / "scope.md").read_text())
        self.assertIn("Scope: prove agy owner.", (profile / "AGENTS.md").read_text())
        self.assertIn("/bin/agy", Path(enrollment["cli_bin"]).read_text())


if __name__ == "__main__":
    unittest.main()
