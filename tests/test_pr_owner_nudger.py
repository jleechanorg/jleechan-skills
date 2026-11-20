import fcntl
import io
import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import pr_owner_nudger as nudger  # noqa: E402


real_command = nudger.command


class DispatcherTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.repo = self.root / "repository"
        self.cwd = self.root / "linked worktree"
        self.repo.mkdir()
        self.git("init", "-b", "main")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "commit", "--allow-empty", "-m", "Initialize")
        self.git("remote", "add", "origin", "git@github.com:fork/project.git")
        self.git("worktree", "add", "-b", "feature", str(self.cwd))
        self.sha = self.git("rev-parse", "HEAD", cwd=self.cwd)
        self.owner = {"cwd": str(self.cwd), "repo": "base/project",
                      "cli": "codex", "session": "fixture-session"}
        self.pr = {"number": 12, "state": "open", "title": "[coding] Example", "labels": [],
                   "head": {"ref": "feature", "sha": self.sha,
                            "repo": {"full_name": "fork/project"}},
                   "base": {"repo": {"full_name": "base/project"}}}
        self.dual_fork = False
        self.config = {"enabled": True, "state_dir": str(self.root / "state"),
                       "owners": [self.owner]}
        self.enterContext(patch.object(nudger, "discover_owners", return_value={}))
        self.enterContext(patch.object(nudger, "command", side_effect=self.command))

    def git(self, *args, cwd=None):
        return nudger.command(cwd or self.repo, "git", *args).strip()

    def command(self, cwd, *args):
        if args[0] != "gh":
            return real_command(cwd, *args)
        target = f"repos/{self.pr['base']['repo']['full_name']}/pulls"
        self.assertEqual(args[-2:], ("--hostname", "github.com"))
        if args[1:-2] == ("api", "repos/fork/project"):
            return json.dumps({"full_name": "fork/project", "fork": True,
                               "parent": {"full_name": "base/project"}})
        if args[1:-2] == ("api", f"{target}/{self.pr['number']}"):
            return json.dumps(self.pr)
        branch = "feature" if cwd == self.cwd else "main"
        self.assertIn(args[4], (target, "repos/fork/project/pulls"))
        self.assertEqual(args[1:-2], ("api", "-X", "GET", args[4], "-f", f"head=fork:{branch}",
                                       "-f", "state=open", "-F", "per_page=2"))
        if branch == "feature" and args[4] == target:
            return json.dumps([self.pr])
        if branch == "feature" and self.dual_fork:
            duplicate = dict(self.pr, base={"repo": {"full_name": "fork/project"}})
            return json.dumps([duplicate])
        return "[]"

    def status(self, apply=True):
        path = self.root / "config.json"
        path.write_text(json.dumps(self.config))
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(nudger.main(["--config", str(path)] + (["--apply"] if apply else [])), 0)
        for line in output.getvalue().splitlines():
            row = json.loads(line)
            if row.get("cwd", str(self.cwd)) == str(self.cwd):
                return row["status"]
        self.fail("No outcome for owner worktree")

    def test_dry_run_opt_in_and_persistent_cooldown(self):
        def deliver(owner, _prompt, apply):
            self.assertEqual((owner["pr"], owner["sha"]), (12, self.sha))
            self.assertTrue(owner["recheck"]())
            return "delivered" if apply else "would_deliver"

        with patch.object(nudger, "route", side_effect=deliver) as route:
            self.assertEqual(self.status(apply=False), "would_deliver")
            self.assertFalse(Path(self.config["state_dir"]).exists())
            self.config["enabled"] = False
            self.assertEqual(self.status(), "disabled")
            self.config["enabled"] = True
            self.assertEqual(self.status(), "delivered")
            self.assertEqual(self.status(), "cooldown")
        self.assertEqual(route.call_count, 2)

    def test_stage_five_uses_current_owner_receipt(self):
        stage, hold = {"name": "stage:5-final-approval"}, {"name": "hold:operator"}
        body = f"## PR Stage\ncandidate: {self.sha}\nowner: driver\nendpoint: FINAL_READY\n"
        next_action = "next_action: read missing closing receipts"
        human_wait = "status: WAITING_HUMAN\nblocker: merge approval\nwake_condition: operator approves"
        ready = body + "status: FINAL_READY"
        published = "## PR Stage\n\nStage 5 (final approval): **FINAL_READY** at "
        published += f"`{self.sha}`. Closing checks passed. Merge authorization: not authorized."
        published_plain = f"## PR Stage\n\nStage 5 — FINAL_READY at `{self.sha}`, base `{'1' * 40}`."
        ready_title = "[ready][needs MERGE APPROVED] Example"
        scenarios = [
            ("[fa] Closing", [stage], body + next_action, "busy"),
            ("[ready] Closing", [stage], body + next_action, "busy"),
            ("[blocked] Waiting", [stage, hold], body + "blocker: test handset", "busy"),
            ("[blocked] Waiting", [stage, hold], body + human_wait + "\n" + next_action, "busy"),
            ("[blocked] Waiting", [stage, hold], body + human_wait, "awaiting_final_approval"),
            ("[fa] Closing", [stage], ready, "final_ready"),
            ("[ready] Example", [stage], ready.replace(self.sha, "0" * 40), "busy"),
            (ready_title, [stage], published, "final_ready"),
            (ready_title, [stage], published_plain, "final_ready"),
            (ready_title, [stage], published.replace(self.sha, "0" * 40), "busy"),
            (ready_title, [stage], published + "\n" + next_action, "busy"),
        ]
        with patch.object(nudger, "route", return_value="busy") as route:
            for title, labels, record, expected in scenarios:
                with self.subTest(title=title, expected=expected):
                    self.pr.update(title=title, labels=labels, body=record)
                    self.assertEqual(self.status(), expected)
        self.assertEqual(route.call_count, 7)

    def test_rechecks_exact_pr_immediately_before_dispatch(self):
        def drift(owner, _prompt, _apply):
            self.pr["head"]["sha"] = "0" * 40
            self.assertFalse(owner["recheck"]())
            return "stale_pr"

        with patch.object(nudger, "route", side_effect=drift):
            self.assertEqual(self.status(), "stale_pr")
            self.assertEqual(self.status(), "stale_head")

    def test_ambiguous_or_mismatched_bindings_never_route(self):
        with patch.object(nudger, "route") as route:
            self.config["owners"].append(dict(self.owner, session="other-session"))
            self.assertEqual(self.status(), "ambiguous_owner")
            self.config["owners"].pop()
            self.pr["head"]["repo"]["full_name"] = "another/project"
            self.assertEqual(self.status(), "pr_mismatch")
        route.assert_not_called()

    def test_discovered_owner_survives_surface_loss_only_for_same_pr(self):
        self.config.update(owners=[], worktree_roots=[str(self.repo)])
        live = {str(self.cwd): [{"cwd": str(self.cwd), "cli": self.owner["cli"],
                                "session": self.owner["session"], "cmux_discovered": True}]}
        allow_resume = []

        def route(owner, _prompt, _apply):
            self.assertEqual(owner["session"], self.owner["session"])
            allow_resume.append(owner["headless_resume"])
            if len(allow_resume) == 1:
                owner["confirm_owner"]("workspace:1", "surface:1")
            return "busy"

        with patch.object(nudger, "discover_owners", side_effect=[live, live, {}, {}]), \
                patch.object(nudger, "route", side_effect=route) as send:
            self.dual_fork = True
            self.assertEqual(self.status(), "ambiguous_pr")
            send.assert_not_called()
            self.dual_fork = False
            self.assertEqual(self.status(), "busy")
            self.assertEqual(self.status(), "busy")
            self.pr["number"] = 13
            self.assertEqual(self.status(), "missing_owner")
        self.assertEqual(allow_resume, [False, True])
        self.assertEqual(send.call_count, 2)

    def test_post_send_exception_leaves_reconciliation_hold(self):
        def interrupt(owner, _prompt, _apply):
            self.assertTrue(owner["recheck"]("cmux"))
            raise RuntimeError("Delivery result unavailable")

        with patch.object(nudger, "route", side_effect=interrupt) as route:
            self.assertEqual(self.status(), "reconciliation_required")
            self.assertEqual(self.status(), "reconciliation_required")
        route.assert_called_once()
        with sqlite3.connect(Path(self.config["state_dir"]) / "receipts.sqlite3") as state:
            status, sha, owner = state.execute("SELECT status, sha, owner FROM delivery").fetchone()
        self.assertEqual((status, sha), ("pending_delivery", self.sha))
        self.assertEqual(json.loads(owner)["session"], self.owner["session"])

    def test_overlapping_apply_exits_before_routing(self):
        state = Path(self.config["state_dir"])
        state.mkdir()
        with (state / "tick.lock").open("a") as lock, patch.object(nudger, "route") as route:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertEqual(self.status(), "overlapping_tick")
        route.assert_not_called()
