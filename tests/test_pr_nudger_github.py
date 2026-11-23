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

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import pr_owner_nudger as nudger  # noqa: E402


class PullRefreshTest(unittest.TestCase):
    def test_tick_observes_exact_graphql_head_when_rest_is_exhausted(self):
        repo, number = "base/project", 12
        first_head = "1" * 40
        next_head = "2" * 40
        current_head = first_head
        requests = []
        graph_exhausted = False

        def command(_cwd, *args):
            if args[3] == f"repos/{repo}/pulls/{number}":
                requests.append("rest")
                raise subprocess.CalledProcessError(
                    1, args, output="HTTP/2 403 Forbidden\nX-RateLimit-Remaining: 0\n"
                    "X-RateLimit-Reset: 1800\n\n{}",
                )
            self.assertEqual(args[:3], ("gh", "api", "graphql"))
            self.assertIn("owner=base", args)
            self.assertIn("repo=project", args)
            self.assertIn("number=12", args)
            query = next(arg for arg in args if arg.startswith("query="))
            pr = {"headRefOid": current_head}
            if "statusCheckRollup" in query:
                requests.append("ci")
                pr["commits"] = {"nodes": [{"commit": {
                    "oid": current_head, "statusCheckRollup": None,
                }}]}
            else:
                requests.append("refresh")
                if graph_exhausted:
                    raise subprocess.CalledProcessError(
                        1, args, output="HTTP/2 403 Forbidden\nX-RateLimit-Remaining: 0\n"
                        "X-RateLimit-Reset: 1700\n\n{}",
                    )
                pr.update(
                    number=number, state="OPEN", title="[coding] Example", body="Notes on the secondary rate limit",
                    baseRefName="main", baseRepository={"nameWithOwner": "Base/Project"},
                    headRefName="feature", headRepository={"nameWithOwner": "Fork/Project"},
                    labels={"nodes": [{"name": "stage:1-coding"}],
                            "pageInfo": {"hasNextPage": False}},
                )
            return ("HTTP/2 200 OK\n\n"
                    + json.dumps({"data": {"repository": {"pullRequest": pr}}}))

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / "state"
            config = root / "config.json"
            config.write_text(json.dumps({
                "enabled": True, "state_dir": str(state),
                "targets": [{"repo": repo, "number": number, "observe_only": True}],
            }))
            args = ["--config", str(config), "--apply"]

            def tick():
                output = io.StringIO()
                with redirect_stdout(output):
                    nudger.main(args)
                return json.loads(output.getvalue().splitlines()[0])

            with patch.object(nudger, "command", side_effect=command), \
                    patch.object(nudger.time, "time", return_value=1000) as clock:
                self.assertEqual(tick()["status"], "observing")
                current_head = next_head
                clock.return_value = 1100
                self.assertEqual(tick()["status"], "observing")
                graph_exhausted = True
                clock.return_value = 1200
                self.assertEqual(tick()["status"], "blocked_github_rate")
                clock.return_value = 1300
                self.assertEqual(tick()["status"], "blocked_github_rate")
            self.assertEqual(requests, ["rest", "refresh", "ci", "refresh", "ci", "refresh"])
            with sqlite3.connect(state / "receipts.sqlite3") as db:
                self.assertEqual(db.execute(
                    "SELECT head, observed_status, stage FROM target"
                ).fetchone(), (next_head, "actionable", "stage:1-coding"))
                self.assertEqual(db.execute(
                    "SELECT head, status FROM target_ci"
                ).fetchone(), (next_head, "no_checks_observed"))
                self.assertEqual(db.execute(
                    "SELECT bucket, reset_at FROM github_budget ORDER BY bucket"
                ).fetchall(), [("core", 1800), ("graphql", 1700)])


    def test_secondary_rest_limit_does_not_attempt_graphql(self):
        budget = nudger.Intake(None, None, 1000)
        endpoint = "repos/base/project/pulls/12"
        response = 'HTTP/2 429 Too Many Requests\nRetry-After: 20\n\n{}'
        with patch.object(nudger, "command", side_effect=subprocess.CalledProcessError(
            1, [], output=response,
        )) as command:
            with self.assertRaises(nudger.RateLimited):
                nudger.github(Path.cwd(), endpoint, budget=budget)
            self.assertEqual(nudger.observe_ci("base/project", 12, "1" * 40, budget),
                             "rate_limited")
        command.assert_called_once()


if __name__ == "__main__":
    unittest.main()
