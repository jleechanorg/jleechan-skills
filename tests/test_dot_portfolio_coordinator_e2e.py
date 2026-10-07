import json
import os
import pwd
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / ".claude" / "skills" / "dot-portfolio-coordinator"
CLI_SCRIPT = str(SKILL_DIR / "scripts" / "coordinator-portfolio.py")


class TestDotPortfolioCoordinatorE2E(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(dir="/tmp")
        self.sources_file = str(SKILL_DIR / "references" / "sources.json")
        self.ledger_file = os.path.join(self.temp_dir.name, "ledger.json")
        self.bindings_file = os.path.join(self.temp_dir.name, "bindings.json")

    def tearDown(self):
        self.temp_dir.cleanup()

    def _run_cli(self, args, extra_env=None):
        env = dict(os.environ)
        env["DOT_PORTFOLIO_LEDGER_FILE"] = self.ledger_file
        env["DOT_PORTFOLIO_BINDINGS_FILE"] = self.bindings_file
        env["DOT_TEST_CALLER_PRINCIPAL"] = "verified-local-principal"
        if extra_env:
            env.update(extra_env)

        cmd = [CLI_SCRIPT] + args
        return subprocess.run(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

    def test_cli_help(self):
        proc = self._run_cli(["--help"])
        self.assertEqual(proc.returncode, 0)
        self.assertIn("Dot Portfolio Coordinator", proc.stdout)

    def test_cli_refuses_unverified_spend_despite_forged_environment(self):
        for command in ("reserve", "settle"):
            with self.subTest(command=command):
                proc = self._run_cli([command, "--request", json.dumps({"max_cost": 0.15}),
                                      "--sources", self.sources_file])
                self.assertEqual(proc.returncode, 2)
                data = json.loads(proc.stdout)
                self.assertEqual(data["status"], "rejected")
                self.assertEqual(data["reason"], "capability_blocked")
                self.assertEqual(data["caller_principal"], pwd.getpwuid(os.getuid()).pw_name)
        self.assertFalse(Path(self.ledger_file).exists())
        proc = self._run_cli(["status", "--reservation-id", "caller-invented",
                              "--sources", self.sources_file])
        data = json.loads(proc.stdout)
        self.assertEqual(data["status"], "unknown_reservation")
        self.assertEqual(data["reason"], "capability_blocked")

    def test_cli_resolve_notification(self):
        # Register a binding directly in bindings_file
        ref = "bd-ctrl-1/act-001/att-1"
        data = {
            ref: {
                "control_record_id": "bd-ctrl-1",
                "action_id": "act-001",
                "attempt_id": "att-1",
                "account": "default",
                "event_id": "ev-001"
            }
        }
        with open(self.bindings_file, "w") as f:
            json.dump(data, f)

        proc = self._run_cli(["resolve-notification", "--ref", ref, "--bindings-file", self.bindings_file, "--sources", self.sources_file])
        self.assertEqual(proc.returncode, 0)
        out_json = json.loads(proc.stdout)
        self.assertEqual(out_json["event_id"], "ev-001")

    def test_cli_observe_finite_duration_and_heartbeat(self):
        run_dir = os.path.join(self.temp_dir.name, "observe_run")
        proc = self._run_cli([
            "observe",
            "--duration", "2",
            "--interval", "1",
            "--run-dir", run_dir,
            "--sources", self.sources_file
        ])
        self.assertEqual(proc.returncode, 0)

        # Check heartbeat file and source manifest
        hb_file = os.path.join(run_dir, "heartbeat.jsonl")
        manifest_file = os.path.join(run_dir, "source_manifest.json")
        self.assertTrue(os.path.exists(hb_file))
        self.assertTrue(os.path.exists(manifest_file))

        with open(hb_file, "r") as f:
            lines = [l.strip() for l in f if l.strip()]
        self.assertGreater(len(lines), 0)


if __name__ == "__main__":
    unittest.main()
