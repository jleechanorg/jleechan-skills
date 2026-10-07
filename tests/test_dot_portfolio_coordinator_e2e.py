import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / ".claude" / "skills" / "dot-portfolio-coordinator"
CLI_SCRIPT = str(SKILL_DIR / "scripts" / "coordinator-portfolio.py")


class TestDotPortfolioCoordinatorE2E(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
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

    def test_cli_reserve_and_settle(self):
        # 1. Reserve
        req = {
            "task_key": {
                "github_host": "github.com",
                "repository": "example-org/roadmap",
                "source_namespace": "roadmap",
                "bead_id": "bd-1"
            },
            "grant_version": "v1",
            "action_id": "act-e2e-1",
            "attempt_id": "att-1",
            "currency": "USD",
            "max_cost": 0.15
        }
        proc_res = self._run_cli(["reserve", "--request", json.dumps(req), "--sources", self.sources_file])
        self.assertEqual(proc_res.returncode, 0)
        res_data = json.loads(proc_res.stdout)
        self.assertEqual(res_data["status"], "reserved")
        self.assertEqual(res_data["accepted_amount"], 0.15)
        res_id = res_data["reservation_id"]

        # 2. Status
        proc_stat = self._run_cli(["status", "--reservation-id", res_id, "--sources", self.sources_file])
        self.assertEqual(proc_stat.returncode, 0)
        stat_data = json.loads(proc_stat.stdout)
        self.assertEqual(stat_data["status"], "active")

        # 3. Settle
        settle_req = {
            "reservation_id": res_id,
            "actual_cost": 0.12,
            "evidence_reference": "https://example.com/receipt/1",
            "evidence_digest": "sha-rec-1"
        }
        proc_set = self._run_cli(["settle", "--request", json.dumps(settle_req), "--sources", self.sources_file])
        self.assertEqual(proc_set.returncode, 0)
        set_data = json.loads(proc_set.stdout)
        self.assertEqual(set_data["status"], "settled")
        self.assertEqual(set_data["settled_amount"], 0.12)

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

        proc = self._run_cli(["resolve-notification", "--ref", ref, "--sources", self.sources_file])
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
