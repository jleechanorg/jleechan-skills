import fcntl
import io
import json
import sqlite3
import subprocess
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
real_observe_ci = nudger.observe_ci


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
        self.enterContext(patch.object(nudger, "observe_ci", return_value="no_checks_observed"))

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


    def target_tick(self, *, apply=True):
        path = self.root / "configuration.json"
        path.write_text(json.dumps(self.config))
        output = io.StringIO()
        with redirect_stdout(output):
            args = ["--config", str(path)] + (["--apply"] if apply else [])
            self.assertEqual(nudger.main(args), 0)
        return [json.loads(line) for line in output.getvalue().splitlines()]

    def test_persists_five_targets_before_any_external_operation(self):
        self.config["owners"] = []
        self.config["targets"] = [
            {"repo": "base/project", "number": number} for number in range(12, 17)
        ]
        state_path = Path(self.config["state_dir"]) / "receipts.sqlite3"

        def read(_cwd, endpoint, **_kwargs):
            number = int(endpoint.rsplit("/", 1)[1])
            with sqlite3.connect(state_path) as db:
                self.assertEqual(db.execute("SELECT count(*) FROM target").fetchone()[0], 5)
                self.assertTrue(all(row[0] for row in db.execute("SELECT next_action FROM target")))
            return dict(self.pr, number=number)

        with patch.object(nudger, "github", side_effect=read) as github:
            self.assertEqual(len(self.target_tick()), 5)
            self.assertEqual(len(self.target_tick()), 5)
            self.assertEqual(github.call_count, 10)

    def test_refresh_continues_under_launch_backoff(self):
        self.config["owners"] = []
        self.config["targets"] = [{"repo": "base/project", "number": 12}]
        with patch.object(nudger, "github", return_value=self.pr) as github,              patch.object(nudger.time, "time", return_value=1000) as clock:
            first = self.target_tick()[0]
            self.assertEqual(first["status"], "missing_owner")
            self.assertEqual(first["next_due"], 1600)
            clock.return_value = 1100
            second = self.target_tick()[0]
            self.assertEqual(second["next_due"], 1600)
            self.assertEqual(github.call_count, 2)


    def test_existing_owner_is_never_dispatched_in_observe_only_mode(self):
        self.config["targets"] = [{"repo": "base/project", "number": 12, "observe_only": True}]
        with patch.object(nudger, "github", return_value=self.pr), patch.object(nudger, "route") as route:
            self.assertEqual(self.target_tick()[0]["status"], "observing")
            route.assert_not_called()

    def test_launch_uses_measured_five_percent_idle(self):
        def mem(path):
            self.assertEqual(str(path), "/proc/meminfo")
            return "MemAvailable:  8000000 kB\n"

        with patch("pr_nudger_intake.platform.system", return_value="Linux"), \
                patch("pr_nudger_intake.time.sleep"), patch.object(Path, "read_text", autospec=True, side_effect=mem):
            for idle, allowed in ((499, False), (500, True)):
                with patch("pr_nudger_intake._linux_cpu", side_effect=[(0, 0), (10000, idle)]):
                    self.assertIs(nudger.launch_capacity(), allowed)
            with patch("pr_nudger_intake._linux_cpu", side_effect=OSError):
                self.assertFalse(nudger.launch_capacity())

    def test_rate_reset_and_backoff_survive_restart(self):
        self.config["owners"] = []
        self.config["targets"] = [{"repo": "base/project", "number": number} for number in (12, 13)]

        def requests(_cwd, *args):
            number = int(args[3].rsplit("/", 1)[1])
            if clock.return_value < 1800:
                response = 'HTTP/2 429 Too Many Requests\nRetry-After: 800\n\n{}'
                raise subprocess.CalledProcessError(1, args, output=response)
            return json.dumps(dict(self.pr, number=number))

        with patch.object(nudger.time, "time", return_value=1000) as clock, \
                patch.object(nudger, "command", side_effect=requests) as command:
            self.assertEqual([row["next_due"] for row in self.target_tick()], [1800, 1800])
            clock.return_value = 1799
            self.assertEqual([row["attempts"] for row in self.target_tick()], [1, 1])
            self.assertEqual(command.call_count, 1)
            clock.return_value = 1800
            self.assertEqual([row["status"] for row in self.target_tick()], ["missing_owner"] * 2)
            self.assertEqual(command.call_count, 3)

    def test_target_backoff_caps_without_affecting_the_other_target(self):
        self.config["owners"] = []
        self.config["targets"] = [{"repo": "base/project", "number": number} for number in (12, 13)]

        def read(_cwd, endpoint, **_kwargs):
            number = int(endpoint.rsplit("/", 1)[1])
            return dict(self.pr, number=number, state="closed" if number == 13 else "open")

        with patch.object(nudger, "github", side_effect=read), \
                patch.object(nudger.time, "time", return_value=1000) as clock:
            for delay in (600, 1200, 2400, 3600, 3600):
                by_pr = {row["pr"]: row for row in self.target_tick()}
                self.assertEqual(by_pr[12]["next_due"] - clock.return_value, delay)
                self.assertEqual((by_pr[13]["attempts"], by_pr[13]["next_due"]), (0, 0))
                clock.return_value += delay

    def test_one_hour_pickup_uses_exact_remote_branch_activity(self):
        self.config["owners"] = []
        self.config["targets"] = [{"repo": "base/project", "number": 12, "pickup_after_seconds": 3600}]
        events = [{"ref": "refs/heads/feature", "after": self.sha, "before": "0" * 40,
                   "activity_type": "push", "timestamp": "1970-01-01T00:16:40Z"}]

        def read(_cwd, endpoint, **kwargs):
            if endpoint.endswith("/activity"):
                self.assertEqual(endpoint, "repos/fork/project/activity")
                self.assertEqual(kwargs["params"]["ref"], "refs/heads/feature")
                return events
            return self.pr

        with patch.object(nudger, "github", side_effect=read), \
                patch.object(nudger.time, "time", return_value=4599) as clock:
            self.assertEqual(self.target_tick()[0]["status"], "pickup_not_due")
            self.assertEqual(self.target_tick(apply=False)[0]["status"], "pickup_not_due")
            clock.return_value = 4600
            self.assertEqual(self.target_tick(apply=False)[0]["status"], "missing_owner")
            clock.return_value = 5200
            self.assertEqual(self.target_tick()[0]["status"], "missing_owner")
            events.append(dict(events[0], after="1" * 40, timestamp="1970-01-01T01:23:20Z",
                               activity_type="force_push"))
            clock.return_value = 6400
            self.assertEqual(self.target_tick()[0]["status"], "remote_push_unverified")

    def test_bootstrap_attempt_is_persisted_before_process_and_bound_before_dispatch(self):
        self.config["owners"] = []
        self.config["targets"] = [{
            "repo": "base/project", "number": 12, "enrollment": {
                "cwd": str(self.cwd), "head_repo": "fork/project", "branch": "feature",
                "host": "test-host", "cli": "codex", "launch_authorized": True,
                "managed_exclusive": True,
            }
        }]
        state_path = Path(self.config["state_dir"]) / "receipts.sqlite3"

        def start(_enrollment, _identity, *, apply, recheck, begin_attempt):
            self.assertTrue(apply and recheck())
            path = begin_attempt()
            with sqlite3.connect(state_path) as db:
                attempt = json.loads(db.execute("SELECT bootstrap FROM target").fetchone()[0])
            self.assertEqual(Path(attempt["events_path"]), path)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            return "bootstrap_started"

        def deliver(owner, _prompt, _apply):
            with sqlite3.connect(state_path) as db:
                stored = json.loads(db.execute("SELECT owner FROM binding").fetchone()[0])
            self.assertEqual(stored["session"], owner["session"])
            self.assertTrue(owner["managed_exclusive"])
            self.assertEqual(owner["host"], "test-host")
            self.assertTrue(owner["recheck"]())
            return "delivered"

        with patch.object(nudger, "github", return_value=self.pr), \
                patch.object(nudger.socket, "gethostname", return_value="test-host"), \
                patch.object(nudger, "launch_capacity", return_value=True), \
                patch.object(nudger.pr_nudger_routes, "start_codex_bootstrap", side_effect=start, create=True) as launch, \
                patch.object(nudger.pr_nudger_routes, "inspect_codex_bootstrap", create=True) as inspect, \
                patch.object(nudger, "route", side_effect=deliver) as route:
            self.assertEqual(self.target_tick()[0]["status"], "bootstrap_started")
            inspect.return_value = ("reconciliation_required", None)
            self.assertEqual(self.target_tick()[0]["status"], "reconciliation_required")
            route.assert_not_called()
            def acknowledged(_enrollment, _identity, _attempt, *, bind):
                bind("only-native-session")
                with sqlite3.connect(state_path) as db:
                    self.assertIsNone(db.execute("SELECT bootstrap FROM target").fetchone()[0])
                return "bootstrapped", "only-native-session"

            inspect.side_effect = acknowledged
            self.assertEqual(self.target_tick()[0]["status"], "bootstrapped")
            self.assertEqual(self.target_tick()[0]["status"], "delivered")
            launch.assert_called_once()


    def test_new_exact_cmux_owner_bypasses_only_missing_owner_backoff(self):
        self.config["owners"] = []
        self.config["targets"] = [{
            "repo": "base/project", "number": 12,
            "enrollment": {"cwd": str(self.cwd), "host": "test-host"},
        }]
        live = dict(self.owner, cmux_discovered=True)

        def deliver(owner, _prompt, _apply):
            self.assertTrue(owner["cmux_discovered"] and owner["recheck"]("cmux"))
            return "delivered"

        def read(_cwd, endpoint, **_kwargs):
            if endpoint.endswith("/activity"):
                return [{"ref": "refs/heads/feature", "activity_type": "push",
                         "before": "0" * 40, "after": self.sha,
                         "timestamp": "1970-01-01T00:15:00Z"}]
            return self.pr

        with patch.object(nudger, "github", side_effect=read), \
                patch.object(nudger.socket, "gethostname", return_value="test-host"), \
                patch.object(nudger.time, "time", return_value=1000) as clock, \
                patch.object(nudger, "discover_owners", return_value={}) as discovery, \
                patch.object(nudger, "route", side_effect=deliver) as route:
            self.assertEqual(self.target_tick()[0]["status"], "missing_launch_authority")
            clock.return_value = 1001
            discovery.return_value = {str(self.cwd): [live]}
            self.config["targets"][0]["pickup_after_seconds"] = 3600
            self.assertEqual(self.target_tick()[0]["status"], "pickup_not_due")
            route.assert_not_called()
            clock.return_value = 4500
            self.assertEqual(self.target_tick()[0]["status"], "delivered")
            clock.return_value = 4501
            self.assertEqual(self.target_tick()[0]["status"], "delivered")
            route.assert_called_once()


    def test_current_head_ci_refreshes_during_launch_backoff(self):
        self.config["owners"] = []
        self.config["targets"] = [{"repo": "base/project", "number": 12}]
        ci = {
            "headRefOid": self.sha,
            "statusCheckRollup": [{"status": "IN_PROGRESS", "conclusion": ""}],
        }

        def command(cwd, *args):
            if args[:3] == ("gh", "api", "graphql"):
                self.assertEqual(args[:4], ("gh", "api", "graphql", "--include"))
                self.assertEqual(args[-6:], ("-f", "owner=base", "-f", "repo=project", "-F", "number=12"))
                commit = {"oid": self.sha, "statusCheckRollup": {"contexts": {
                    "pageInfo": {"hasNextPage": ci.get("has_next", False)},
                    "nodes": ci["statusCheckRollup"],
                }}}
                return json.dumps({"data": {"repository": {"pullRequest": {
                    "headRefOid": ci["headRefOid"], "commits": {"nodes": [{"commit": commit}]},
                }}}})
            return self.command(cwd, *args)

        with patch.object(nudger, "github", return_value=self.pr), \
                patch.object(nudger, "observe_ci", side_effect=real_observe_ci), \
                patch.object(nudger, "command", side_effect=command), \
                patch.object(nudger.time, "time", return_value=1000) as clock:
            first = self.target_tick()[0]
            self.assertEqual((first["ci_status"], first["next_due"]), ("pending", 1600))
            ci["statusCheckRollup"] = [{"status": "COMPLETED", "conclusion": "FAILURE"}]
            clock.return_value = 1100
            second = self.target_tick()[0]
            self.assertEqual((second["ci_status"], second["next_due"]), ("failing", 1600))
            path = Path(self.config["state_dir"]) / "receipts.sqlite3"
            with sqlite3.connect(path) as db:
                self.assertEqual(db.execute(
                    "SELECT head, status, observed_at FROM target_ci"
                ).fetchone(), (self.sha, "failing", 1100))
            ci["headRefOid"] = "0" * 40
            self.assertEqual(self.target_tick()[0]["ci_status"], "stale_head")
            ci["headRefOid"] = self.sha
            ci["statusCheckRollup"] = []
            self.assertEqual(self.target_tick()[0]["ci_status"], "no_checks_observed")


    def test_ci_graphql_reset_does_not_suspend_rest_refresh(self):
        self.config["owners"] = []
        self.config["targets"] = [{"repo": "base/project", "number": 12}]
        requests = []

        def command(_cwd, *args):
            if args[:3] == ("gh", "api", "graphql"):
                requests.append("graphql")
                raise subprocess.CalledProcessError(
                    1, args, output="HTTP/2 429 Too Many Requests\nRetry-After: 900\n\n{}",
                )
            requests.append("core")
            return json.dumps(self.pr)

        with patch.object(nudger, "observe_ci", side_effect=real_observe_ci), \
                patch.object(nudger, "command", side_effect=command), \
                patch.object(nudger.time, "time", return_value=1000) as clock:
            self.assertEqual(self.target_tick()[0]["ci_status"], "rate_limited")
            clock.return_value = 1100
            self.assertEqual(self.target_tick()[0]["ci_status"], "rate_limited")
            self.assertEqual(requests, ["core", "graphql", "core"])
            path = Path(self.config["state_dir"]) / "receipts.sqlite3"
            with sqlite3.connect(path) as db:
                self.assertEqual(db.execute(
                    "SELECT bucket, reset_at FROM github_budget"
                ).fetchall(), [("graphql", 1900)])

    def test_only_local_auth_failure_allows_anonymous_inspection(self):
        failure_code = 4

        def command(cwd, *args):
            if args[0] == "gh":
                raise subprocess.CalledProcessError(failure_code, args)
            return real_command(cwd, *args)

        with patch.object(nudger, "command", side_effect=command), \
                patch("urllib.request.OpenerDirector.open") as fetch, \
                patch.object(nudger, "route", return_value="would_deliver") as route:
            fetch.return_value.__enter__.return_value.read.return_value = json.dumps([self.pr]).encode()
            self.assertEqual(self.status(apply=False), "would_deliver")
            request = fetch.call_args.args[0]
            self.assertEqual(request.get_method(), "GET")
            self.assertEqual(request.full_url, "https://api.github.com/repos/base/project/pulls"
                             "?head=fork%3Afeature&state=open&per_page=2")
            self.assertIsNone(request.get_header("Authorization"))
            self.assertFalse(Path(self.config["state_dir"]).exists())
            self.assertEqual(self.status(), "blocked_discovery")
            failure_code = 1
            self.assertEqual(self.status(apply=False), "blocked_discovery")
        fetch.assert_called_once()
        route.assert_called_once()
        self.assertFalse(route.call_args.args[2])

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

    def test_dot_delivery_receipt_preserves_the_exact_parent_without_account_digest(self):
        self.owner.update(cli="dot", parent_message_id="fixture-parent", identity_sha256="1" * 64)

        def deliver(owner, _prompt, _apply):
            self.assertTrue(owner["recheck"]("dot"))
            return "delivered"

        with patch.object(nudger, "route", side_effect=deliver):
            self.assertEqual(self.status(), "delivered")
        with sqlite3.connect(Path(self.config["state_dir"]) / "receipts.sqlite3") as state:
            owner = json.loads(state.execute("SELECT owner FROM delivery").fetchone()[0])
        self.assertEqual(owner["parent_message_id"], "fixture-parent")
        self.assertEqual(owner["transport"], "dot")
        self.assertNotIn("identity_sha256", owner)

    def test_explicit_owner_resume_defaults_on_and_honors_opt_outs(self):
        def resume(owner, _prompt, _apply):
            return "would_deliver" if owner["headless_resume"] else "blocked_headless_disabled"

        with patch.object(nudger, "route", side_effect=resume):
            self.assertEqual(self.status(apply=False), "would_deliver")
            self.owner["headless_resume"] = False
            self.assertEqual(self.status(apply=False), "blocked_headless_disabled")
            self.owner["headless_resume"] = True
            self.config["headless_resume"] = False
            self.assertEqual(self.status(apply=False), "blocked_headless_disabled")

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
