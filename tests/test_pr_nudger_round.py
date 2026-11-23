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
        scope.write_text("Scope: prove the portrait carries the gender.\n")
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
        self.assertTrue(text.rstrip().endswith("prove the portrait carries the gender."))
        self.assertEqual(os.readlink(profile / "auth.json"), str(self.codex_home / "auth.json"))
        wrapper = Path(enrollment["cli_bin"]).read_text()
        self.assertIn("exit 124", wrapper)
        self.assertIn("/bin/codex", wrapper)
        self.run_cli("retire", "--repo", "base/project", "--pr", "12")
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


if __name__ == "__main__":
    unittest.main()
