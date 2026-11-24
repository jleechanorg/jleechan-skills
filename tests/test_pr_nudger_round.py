import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import pr_nudger_round as round_cli  # noqa: E402
import pr_owner_nudger as nudger  # noqa: E402


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

    def test_pr_nudger_model_takes_top_precedence(self):
        e = self.enroll_model(env={"PR_NUDGER_MODEL": "gemini-9.9-override",
                                   "PI_MODEL": "deepseek-v4.1-flash",
                                   "CODEX_MODEL": "gpt-9-caller"})
        self.assertEqual((e["cli"], e["model"]), ("agy", "gemini-9.9-override"))

    def test_both_explicit_flags_are_used_as_is(self):
        e_agy = self.enroll_model("--cli", "agy", "--model", "custom-model")
        self.assertEqual((e_agy["cli"], e_agy["model"]), ("agy", "custom-model"))
        e_codex = self.enroll_model("--cli", "codex", "--model", "gemini-3.8-flash-high")
        self.assertEqual((e_codex["cli"], e_codex["model"]), ("codex", "gemini-3.8-flash-high"))

    def test_explicit_claude_model_without_cli_is_refused(self):
        with self.assertRaises(SystemExit) as ctx:
            self.enroll_model("--model", "claude-opus-5-5")
        self.assertIn("claude-opus-5-5", str(ctx.exception))
        self.assertFalse(self.config.exists())

    def test_explicit_model_without_cli_still_derives_the_route(self):
        e_gemini = self.enroll_model("--model", "gemini-9.9-pinned")
        self.assertEqual((e_gemini["cli"], e_gemini["model"]), ("agy", "gemini-9.9-pinned"))
        e_codex = self.enroll_model("--model", "gpt-9-pinned")
        self.assertEqual((e_codex["cli"], e_codex["model"]), ("codex", "gpt-9-pinned"))

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

    def test_enroll_scope_instructs_stage5_final_ready_record(self):
        with patch.object(round_cli, "AGY_POLICY", self.root / "missing-agy.md"):
            self.run_cli("enroll", "--cli", "agy", "--headless-only", "--repo", "base/project", "--pr", "12",
                         "--cwd", str(self.repo), "--model", "gemini-4-hydrogen-high",
                         "--hours", "1", "--profiles-dir", str(self.root / "profiles"))
        profile = Path(json.loads(self.config.read_text())["targets"][0]["enrollment"]["profile_dir"])
        scope_text = (profile / "scope.md").read_text()
        agents_text = (profile / "AGENTS.md").read_text()
        expected_lines = (
            "status: FINAL_READY",
            "candidate: <40-char-sha>",
            "owner: <owner>",
            "next_action: none",
        )
        for text in (scope_text, agents_text):
            self.assertIn("stage:5-final-approval", text)
            for line in expected_lines:
                self.assertIn(line, text)

        extracted = [
            match.group(0)
            for match in re.finditer(
                r"(?m)^(?:status|candidate|owner|next_action):[ \t]*\S[^\n]*$",
                scope_text,
            )
        ]
        self.assertEqual(set(extracted), set(expected_lines))

        sha = "a" * 40
        record = "\n".join(
            line.replace("<40-char-sha>", sha).replace("<owner>", "agy-owner")
            for line in extracted
        )
        for section in ("## Execution Record", "## PR Stage"):
            pr = {
                "state": "open",
                "title": "[fa] Example",
                "head": {"sha": sha},
                "labels": [{"name": "stage:5-final-approval"}],
                "body": f"{section}\n{record}\n",
            }
            self.assertEqual(nudger.pr_status(pr), "final_ready")

    def test_prune_subcommand_removes_closed_and_expired_targets_preserving_active_and_0600(self):
        state = self.root / "state"
        state.mkdir()
        now = 2_000_000_000.0
        config = {
            "enabled": True,
            "state_dir": str(state),
            "prune_after_hours": 24,
            "targets": [
                # PR 12: open and active with future deadline -> KEEP
                {"repo": "base/project", "number": 12, "observe_only": False,
                 "enrollment": {"cli_bin": str(self.root / f"codex-deadline-{int(now + 3600)}")}},
                # PR 13: closed/merged on GitHub -> PRUNE
                {"repo": "base/project", "number": 13, "observe_only": False},
                # PR 14: open & observe_only (even with old deadline) -> KEEP
                {"repo": "base/project", "number": 14, "observe_only": True,
                 "enrollment": {"cli_bin": str(self.root / "codex-deadline-1700000000")}},
                # PR 15: open on GitHub, expired in receipts.sqlite3 > 24h ago -> PRUNE
                {"repo": "base/project", "number": 15, "observe_only": False},
                # PR 16: open on GitHub, expired 1h ago (< 24h) -> KEEP until TTL
                {"repo": "base/project", "number": 16, "observe_only": False},
                # PR 17: open on GitHub, deadline wrapper expired > 24h ago -> PRUNE
                {"repo": "base/project", "number": 17, "observe_only": False,
                 "enrollment": {"cli_bin": str(self.root / f"codex-deadline-{int(now - 25 * 3600)}")}},
            ],
        }
        self.config.write_text(json.dumps(config))
        self.config.chmod(0o600)
        with sqlite3.connect(state / "receipts.sqlite3") as db:
            db.execute("CREATE TABLE target (repo TEXT, number INTEGER, reason TEXT, expired_at REAL, closed_at REAL)")
            db.execute("CREATE TABLE delivery (repo TEXT, number INTEGER, status TEXT, time REAL)")
            db.execute("INSERT INTO target VALUES ('base/project', 12, 'delivered', NULL, NULL)")
            db.execute("INSERT INTO target VALUES ('base/project', 13, 'delivered', NULL, NULL)")
            db.execute("INSERT INTO target VALUES ('base/project', 15, 'expired', ?, NULL)", (now - 25 * 3600,))
            db.execute("INSERT INTO target VALUES ('base/project', 16, 'expired', ?, NULL)", (now - 1 * 3600,))
            db.execute("INSERT INTO delivery VALUES ('base/project', 15, 'expired', ?)", (now - 25 * 3600,))
            db.execute("INSERT INTO delivery VALUES ('base/project', 16, 'expired', ?)", (now - 1 * 3600,))

        def fake_github(_cwd, endpoint, **_kwargs):
            num = int(endpoint.rsplit("/", 1)[1])
            return {"number": num, "state": "closed" if num == 13 else "open", "labels": [],
                    "title": "PR", "body": "", "head": {"sha": "a" * 40, "ref": "f", "repo": {"full_name": "base/project"}},
                    "base": {"repo": {"full_name": "base/project"}}}

        with patch.object(round_cli.time, "time", return_value=now), \
             patch.object(round_cli, "github", side_effect=fake_github, create=True):
            self.run_cli("prune", "--dry-run")
            self.assertEqual([t["number"] for t in json.loads(self.config.read_text())["targets"]],
                             [12, 13, 14, 15, 16, 17])

            self.run_cli("prune")
            self.assertEqual([t["number"] for t in json.loads(self.config.read_text())["targets"]],
                             [12, 14, 16])
            self.assertEqual(self.config.stat().st_mode & 0o777, 0o600)
            with sqlite3.connect(state / "receipts.sqlite3") as db:
                kept = [r[0] for r in db.execute("SELECT number FROM target ORDER BY number").fetchall()]
                self.assertEqual(kept, [12, 16])

            # Explicit --prune-after-hours 0.5 prunes PR 16 (expired 1h ago) while keeping 12 and 14.
            self.run_cli("prune", "--prune-after-hours", "0.5")
            self.assertEqual([t["number"] for t in json.loads(self.config.read_text())["targets"]],
                             [12, 14])

    def test_prune_subcommand_preserves_concurrent_edits_and_closed_grace_period(self):
        state = self.root / "state"
        state.mkdir()
        now = 2_000_000_000.0
        config = {
            "enabled": True,
            "state_dir": str(state),
            "prune_closed_after_hours": 2,
            "targets": [
                {"repo": "base/project", "number": 12, "observe_only": False},
                {"repo": "base/project", "number": 13, "observe_only": False},
            ],
        }
        self.config.write_text(json.dumps(config))
        self.config.chmod(0o600)
        with sqlite3.connect(state / "receipts.sqlite3") as db:
            db.execute("CREATE TABLE target (repo TEXT, number INTEGER, reason TEXT, expired_at REAL, closed_at REAL)")
            db.execute("INSERT INTO target VALUES ('base/project', 12, 'closed', NULL, ?)", (now - 3 * 3600,))
            db.execute("INSERT INTO target VALUES ('base/project', 13, 'closed', NULL, ?)", (now - 1 * 3600,))

        def fake_github(_cwd, endpoint, **_kwargs):
            num = int(endpoint.rsplit("/", 1)[1])
            if num == 13:
                updated = json.loads(self.config.read_text())
                updated["targets"].append({"repo": "base/project", "number": 14, "observe_only": True})
                self.config.write_text(json.dumps(updated))
            return {"number": num, "state": "closed", "labels": [], "title": "PR", "body": "",
                    "head": {"sha": "a" * 40, "ref": "f", "repo": {"full_name": "base/project"}},
                    "base": {"repo": {"full_name": "base/project"}}}

        with patch.object(round_cli.time, "time", return_value=now), \
             patch.object(round_cli, "github", side_effect=fake_github, create=True):
            self.run_cli("prune")

        self.assertEqual([t["number"] for t in json.loads(self.config.read_text())["targets"]], [13, 14])
        self.assertEqual(self.config.stat().st_mode & 0o777, 0o600)
        with sqlite3.connect(state / "receipts.sqlite3") as db:
            kept = [r[0] for r in db.execute("SELECT number FROM target ORDER BY number").fetchall()]
            self.assertEqual(kept, [13])

    def test_prune_preserves_reenrolled_final_ready_offline_and_starts_closed_grace(self):
        state = self.root / "state"
        state.mkdir()
        now = 2_000_000_000.0
        sha = "a" * 40
        config = {
            "enabled": True,
            "state_dir": str(state),
            "prune_after_hours": 24,
            "prune_closed_after_hours": 2,
            "targets": [
                # PR 12: freshly re-enrolled (future deadline + changed cli_bin) despite stale SQLite expiry -> KEEP
                {"repo": "base/project", "number": 12, "observe_only": False,
                 "enrollment": {"cli_bin": str(self.root / f"codex-deadline-{int(now + 3600)}")}},
                # PR 13: open FINAL_READY even with old deadline + stale SQLite expiry -> KEEP
                {"repo": "base/project", "number": 13, "observe_only": False,
                 "enrollment": {"cli_bin": str(self.root / f"codex-deadline-{int(now - 30 * 3600)}")}},
                # PR 14: closed on GitHub, no initial closed_at -> initialize grace, prune only at +2h
                {"repo": "base/project", "number": 14, "observe_only": False},
                # PR 15: offline GitHub error -> KEEP + warn on stderr
                {"repo": "base/project", "number": 15, "observe_only": False,
                 "enrollment": {"cli_bin": str(self.root / f"codex-deadline-{int(now - 30 * 3600)}")}},
            ],
        }
        self.config.write_text(json.dumps(config))
        self.config.chmod(0o600)
        with sqlite3.connect(state / "receipts.sqlite3") as db:
            db.execute("CREATE TABLE target (repo TEXT, number INTEGER, next_action TEXT, reason TEXT, expired_at REAL, closed_at REAL)")
            db.execute("CREATE TABLE delivery (repo TEXT, number INTEGER, status TEXT, time REAL, owner TEXT)")
            db.execute("INSERT INTO target VALUES ('base/project', 12, 'expired', 'expired', ?, NULL)", (now - 30 * 3600,))
            db.execute("INSERT INTO delivery VALUES ('base/project', 12, 'expired', ?, ?)",
                       (now - 30 * 3600, json.dumps({"cli_bin": str(self.root / "codex-deadline-old")})))
            db.execute("INSERT INTO target VALUES ('base/project', 13, 'expired', 'expired', ?, NULL)", (now - 30 * 3600,))

        final_body = f"## PR Stage\nstatus: FINAL_READY\ncandidate: {sha}\nowner: agy\nnext_action: none\n"

        def fake_github(_cwd, endpoint, **_kwargs):
            num = int(endpoint.rsplit("/", 1)[1])
            if num == 15:
                raise OSError("network offline")
            if num == 13:
                return {"number": 13, "state": "open", "labels": [{"name": "stage:5-final-approval"}],
                        "title": "[ready] Done", "body": final_body,
                        "head": {"sha": sha, "ref": "f", "repo": {"full_name": "base/project"}},
                        "base": {"repo": {"full_name": "base/project"}}}
            return {"number": num, "state": "closed" if num == 14 else "open", "labels": [],
                    "title": "PR", "body": "",
                    "head": {"sha": sha, "ref": "f", "repo": {"full_name": "base/project"}},
                    "base": {"repo": {"full_name": "base/project"}}}

        clock = [now]
        with patch.object(round_cli.time, "time", side_effect=lambda: clock[0]), \
             patch.object(round_cli, "github", side_effect=fake_github, create=True):
            self.run_cli("prune")
            self.assertEqual([t["number"] for t in json.loads(self.config.read_text())["targets"]], [12, 13, 14, 15])

            clock[0] = now + 3600.0
            self.run_cli("prune")
            self.assertEqual([t["number"] for t in json.loads(self.config.read_text())["targets"]], [12, 13, 14, 15])

            clock[0] = now + 2 * 3600.0
            self.run_cli("prune")
            self.assertEqual([t["number"] for t in json.loads(self.config.read_text())["targets"]], [12, 13, 15])

    def test_prune_standalone_grace_no_db_reopen_resets_and_replacement_deadline_ages_out(self):
        state = self.root / "fresh-state"
        now = 2_000_000_000.0
        config = {
            "enabled": True,
            "state_dir": str(state),
            "prune_after_hours": 24,
            "prune_closed_after_hours": 2,
            "targets": [
                {"repo": "base/project", "number": 12, "observe_only": False,
                 "enrollment": {"cli_bin": str(self.root / f"codex-deadline-{int(now + 3600)}")}},
                {"repo": "base/project", "number": 14, "observe_only": False},
            ],
        }
        self.config.write_text(json.dumps(config))
        pr14_state = ["closed"]

        def fake_github(_cwd, endpoint, **_kwargs):
            num = int(endpoint.rsplit("/", 1)[1])
            return {"number": num, "state": pr14_state[0] if num == 14 else "open", "labels": [],
                    "title": "PR", "body": "",
                    "head": {"sha": "a" * 40, "ref": "f", "repo": {"full_name": "base/project"}},
                    "base": {"repo": {"full_name": "base/project"}}}

        clock = [now]
        with patch.object(round_cli.time, "time", side_effect=lambda: clock[0]), \
             patch.object(round_cli, "github", side_effect=fake_github, create=True):
            # No pre-existing DB: initializes closed_at for PR 14 at t=now.
            self.run_cli("prune")
            self.assertTrue((state / "receipts.sqlite3").is_file())
            self.assertEqual([t["number"] for t in json.loads(self.config.read_text())["targets"]], [12, 14])
            # Reopening PR 14 at t+1.5h clears closed_at; reclosing at t+2h starts a fresh 2h grace window.
            clock[0] = now + 1.5 * 3600
            pr14_state[0] = "open"
            self.run_cli("prune")
            clock[0] = now + 2.0 * 3600
            pr14_state[0] = "closed"
            self.run_cli("prune")
            self.assertEqual([t["number"] for t in json.loads(self.config.read_text())["targets"]], [12, 14])
            # At t+4h (2h after re-closure) PR 14 prunes; at t+26h (25h after PR 12's +1h deadline) PR 12 also prunes.
            clock[0] = now + 4.0 * 3600
            self.run_cli("prune")
            self.assertEqual([t["number"] for t in json.loads(self.config.read_text())["targets"]], [12])
            clock[0] = now + 26.0 * 3600
            self.run_cli("prune")
            self.assertEqual(json.loads(self.config.read_text())["targets"], [])

    def test_prune_preserves_reopened_non_expired_observe_only_despite_stale_delivery_expiry(self):
        state = self.root / "state"
        state.mkdir()
        now = 2_000_000_000.0
        config = {
            "enabled": True,
            "state_dir": str(state),
            "prune_after_hours": 24,
            "targets": [{"repo": "base/project", "number": 12, "observe_only": True}],
        }
        self.config.write_text(json.dumps(config))
        with sqlite3.connect(state / "receipts.sqlite3") as db:
            db.execute("CREATE TABLE target (repo TEXT, number INTEGER, next_action TEXT, observed_status TEXT, reason TEXT, expired_at REAL, closed_at REAL)")
            db.execute("CREATE TABLE delivery (repo TEXT, number INTEGER, status TEXT, time REAL)")
            db.execute("INSERT INTO target VALUES ('base/project', 12, 'refresh_pr', 'actionable', 'observing', NULL, NULL)")
            db.execute("INSERT INTO delivery VALUES ('base/project', 12, 'expired', ?)", (now - 30 * 3600,))

        def fake_github(_cwd, _endpoint, **_kwargs):
            return {"number": 12, "state": "open", "labels": [], "title": "PR", "body": "",
                    "head": {"sha": "a" * 40, "ref": "f", "repo": {"full_name": "base/project"}},
                    "base": {"repo": {"full_name": "base/project"}}}

        with patch.object(round_cli.time, "time", return_value=now), \
             patch.object(round_cli, "github", side_effect=fake_github, create=True):
            self.run_cli("prune")

        self.assertEqual([t["number"] for t in json.loads(self.config.read_text())["targets"]], [12])


if __name__ == "__main__":
    unittest.main()
