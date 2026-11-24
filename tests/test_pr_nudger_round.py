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
                     "--cli", "codex",
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
                         "--cli", "codex",
                         "--model", "fixture-model", "--hours", "2",
                         "--policy", str(self.policy), "--profiles-dir", str(self.root / "profiles"))
        # Re-enrolling changes the wrapper path, so the nudger retires the old session.
        self.assertNotEqual(json.loads(self.config.read_text())["targets"][0]["enrollment"]["cli_bin"], first)
        self.run_cli("retire", "--repo", "base/project", "--pr", "12")
        with self.assertRaises(SystemExit):
            self.run_cli("retire", "--repo", "base/project", "--pr", "99")
        self.assertTrue(json.loads(self.config.read_text())["targets"][0]["observe_only"])

    def enroll_model(self, *extra, env=None):
        """Enroll and return the persisted model, with the calling agent's env cleared."""
        clean = {k: "" for k in round_cli.CALLER_MODEL_ENV}
        clean.update(env or {})
        with patch.dict(os.environ, clean):
            self.run_cli("enroll", "--repo", "base/project", "--pr", "12", "--cwd", str(self.repo),
                         "--hours", "1", "--policy", str(self.policy),
                         "--profiles-dir", str(self.root / "profiles"), *extra)
        return json.loads(self.config.read_text())["targets"][0]["enrollment"]

    def test_cli_and_model_both_inherit_from_the_caller(self):
        # The operator asked for this: neither flag given, the caller's own model decides the
        # route, so the enrolled owner is the same agent that dispatched it.
        e = self.enroll_model(env={"CODEX_MODEL": "gpt-9-caller"})
        self.assertEqual((e["cli"], e["model"]), ("codex", "gpt-9-caller"))

    def test_a_gemini_caller_model_selects_agy(self):
        e = self.enroll_model(env={"AGY_MODEL": "gemini-9.9-caller"})
        self.assertEqual((e["cli"], e["model"]), ("agy", "gemini-9.9-caller"))

    def test_the_callers_own_var_decides_the_route_not_a_lower_precedence_one(self):
        # This host's real shape: PI_MODEL (the running agent) precedes AGY_MODEL. The route
        # must follow the caller's own model, not silently pair agy with a cross-family value.
        e = self.enroll_model(env={"PI_MODEL": "deepseek-v4.1-flash",
                                   "AGY_MODEL": "gemini-9.9-caller"})
        self.assertEqual((e["cli"], e["model"]), ("codex", "deepseek-v4.1-flash"))

    def test_no_caller_falls_back_to_agy(self):
        e = self.enroll_model()
        self.assertEqual((e["cli"], e["model"]), ("agy", round_cli.AGY_FALLBACK_MODEL))

    def test_explicit_cli_keeps_the_caller_model_when_it_fits(self):
        e = self.enroll_model("--cli", "agy", env={"AGY_MODEL": "gemini-9.9-caller"})
        self.assertEqual((e["cli"], e["model"]), ("agy", "gemini-9.9-caller"))

    def test_explicit_cli_overrides_a_cross_family_caller_model(self):
        # --cli agy with a non-gemini caller model: the CLI wins, and agy takes its fallback.
        e = self.enroll_model("--cli", "agy", env={"CODEX_MODEL": "gpt-9-caller"})
        self.assertEqual((e["cli"], e["model"]), ("agy", round_cli.AGY_FALLBACK_MODEL))

    def test_explicit_codex_without_a_fitting_model_refuses(self):
        # codex has no safe default; enrolling one whose CLI would reject the model is worse
        # than a loud failure here.
        with self.assertRaises(SystemExit):
            self.enroll_model("--cli", "codex", env={"AGY_MODEL": "gemini-9.9-caller"})
        with self.assertRaises(SystemExit):
            self.enroll_model("--cli", "codex")

    def test_explicit_model_derives_the_cli(self):
        e = self.enroll_model("--model", "gemini-9.9-pinned", env={"CODEX_MODEL": "gpt-9-caller"})
        self.assertEqual((e["cli"], e["model"]), ("agy", "gemini-9.9-pinned"))

    def test_explicit_model_and_cli_are_used_as_given(self):
        e = self.enroll_model("--cli", "codex", "--model", "pinned-model")
        self.assertEqual((e["cli"], e["model"]), ("codex", "pinned-model"))

    def test_a_claude_caller_model_is_never_handed_to_codex(self):
        # A Claude identifier is not codex-family: agy is gemini-only and `codex exec --model`
        # rejects a Claude name, so inheriting one would enrol an owner that fails at bootstrap.
        self.assertFalse(round_cli.family_matches("claude-opus-5-5", "codex"))
        self.assertFalse(round_cli.family_matches("claude-opus-5-5", "agy"))
        self.assertEqual(round_cli.cli_for_model("claude-opus-5-5"), "")

    def test_claude_caller_model_falls_back_instead_of_enrolling_codex(self):
        e = self.enroll_model(env={"CLAUDE_MODEL": "claude-opus-5-5"})
        self.assertEqual(e["cli"], "agy")
        self.assertEqual(e["model"], round_cli.AGY_FALLBACK_MODEL)

    def test_codex_still_accepts_a_non_gemini_non_claude_model(self):
        # The permissive default is deliberate: unknown codex-served families must keep working.
        for model in ("deepseek-v4.1-flash", "gpt-6.2-sol", "gpt-6-luna"):
            self.assertTrue(round_cli.family_matches(model, "codex"), model)
            self.assertEqual(round_cli.cli_for_model(model), "codex")

    def test_explicit_mismatched_pair_is_refused(self):
        # --cli codex with a gemini model would enrol a codex owner that rejects the model.
        with self.assertRaises(SystemExit):
            self.enroll_model("--cli", "codex", "--model", "gemini-9.9-pinned")
        with self.assertRaises(SystemExit):
            self.enroll_model("--cli", "agy", "--model", "gpt-9-pinned")

    def test_explicit_model_without_cli_still_derives_the_route(self):
        e = self.enroll_model("--model", "gemini-9.9-pinned")
        self.assertEqual((e["cli"], e["model"]), ("agy", "gemini-9.9-pinned"))

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
