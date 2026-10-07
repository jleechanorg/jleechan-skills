import hashlib
import json
import os
import stat
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / ".claude" / "skills" / "dot-portfolio-coordinator"
sys_path = str(SKILL_DIR / "scripts")
import sys
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)

CLI_SCRIPT = str(SKILL_DIR / "scripts" / "coordinator-portfolio.py")
WRAPPER_SCRIPT = str(SKILL_DIR / "scripts" / "dot-portfolio-coordinator-wrapper.sh")


class TestDotPortfolioCoordinatorObserve(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(dir="/tmp")
        self.run_dir = os.path.join(self.temp_dir.name, "observe_run")

        # Create a valid test sources registry in temp_dir
        self.sources_data = {
            "version": "1.0.0",
            "sources": [
                {
                    "id": "test-repo",
                    "namespace": "test",
                    "type": "github_repo",
                    "github_host": "github.com",
                    "repository": "example-org/test-repo",
                    "canonical_tracker": "github_issues",
                    "authority": "read_only",
                    "audience_policy": {"title": ["public"]}
                }
            ]
        }
        self.sources_file = os.path.join(self.temp_dir.name, "test_sources.json")
        with open(self.sources_file, "w") as f:
            json.dump(self.sources_data, f)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_observe_runs_real_collection_and_creates_private_files(self):
        cmd = [
            CLI_SCRIPT,
            "--sources", self.sources_file,
            "observe",
            "--duration", "2",
            "--interval", "1",
            "--run-dir", self.run_dir
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(proc.returncode, 0)

        # 1. Verify run_dir permissions (mode 0700)
        st = os.stat(self.run_dir)
        mode = st.st_mode & 0o777
        self.assertEqual(mode, 0o700)

        # 2. Verify files created: source_manifest.json, heartbeat.jsonl, latest_snapshot.json, final_receipt.json
        manifest_file = os.path.join(self.run_dir, "source_manifest.json")
        hb_file = os.path.join(self.run_dir, "heartbeat.jsonl")
        snap_file = os.path.join(self.run_dir, "latest_snapshot.json")
        receipt_file = os.path.join(self.run_dir, "final_receipt.json")

        self.assertTrue(os.path.exists(manifest_file))
        self.assertTrue(os.path.exists(hb_file))
        self.assertTrue(os.path.exists(snap_file))
        self.assertTrue(os.path.exists(receipt_file))

        # Check file modes are 0600
        for fpath in (manifest_file, hb_file, snap_file, receipt_file):
            f_mode = os.stat(fpath).st_mode & 0o777
            self.assertEqual(f_mode, 0o600, f"File {fpath} should be mode 0600")

        # 3. Verify real collection happened: snap_file contains 'test-repo'
        with open(snap_file, "r") as f:
            snap_data = json.load(f)
        self.assertIn("snapshots", snap_data)
        self.assertIn("test-repo", snap_data["snapshots"])

        # 4. Verify final receipt accurately records completed cycles
        with open(receipt_file, "r") as f:
            receipt = json.load(f)
        self.assertIn("completed_cycles", receipt)
        self.assertIn("partial_cycles", receipt)
        self.assertEqual(receipt.get("stop_reason"), "completed")

    def test_observe_drift_detection_stops_run(self):
        # We start observe for 10 seconds with interval 1.
        # But we modify the sources file immediately so it detects drift on tick 2.
        cmd = [
            CLI_SCRIPT,
            "--sources", self.sources_file,
            "observe",
            "--duration", "10",
            "--interval", "1",
            "--run-dir", self.run_dir
        ]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        time.sleep(1.2)
        # Modify the sources file to cause drift
        with open(self.sources_file, "a") as f:
            f.write("\n")

        stdout, stderr = proc.communicate(timeout=10)
        self.assertEqual(proc.returncode, 0)
        receipt_file = os.path.join(self.run_dir, "final_receipt.json")
        self.assertTrue(os.path.exists(receipt_file))
        with open(receipt_file, "r") as f:
            receipt = json.load(f)
        self.assertEqual(receipt.get("stop_reason"), "manifest_drift_detected")

    def test_observe_active_requires_grant(self):
        cmd = [
            CLI_SCRIPT,
            "--sources", self.sources_file,
            "observe",
            "--duration", "2",
            "--interval", "1",
            "--send-messages",
            "--run-dir", self.run_dir
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("error", proc.stderr.lower() + proc.stdout.lower())

    def test_observe_active_mode_with_grant_sends_messages(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            root = Path(tmp)
            started = time.time()
            accounts = []
            for name in ("first", "second", "third"):
                grant = {"grant_version": 1, "task_id": "dot-coordinator-separated-20261007",
                         "account_id": name, "action": "coordination_message", "max_messages": 12,
                         "min_interval_secs": 3600, "activated_at_epoch": started,
                         "expiry_epoch": started + 900}
                path = root / (name + ".json")
                path.write_text(json.dumps(grant)); path.chmod(0o400)
                accounts.append({"account": name, "grant_file": str(path),
                                 "grant_sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
            config = {"run_id": "integration", "task_id": "dot-coordinator-separated-20261007",
                      "activated_at_epoch": started, "duration_secs": 900,
                      "authority": "Continue the fixture task; no merge or destructive authority.",
                      "state_dir": self.run_dir,
                      "accounts": accounts}
            pilot = root / "pilot.json"
            pilot.write_text(json.dumps(config)); pilot.chmod(0o400)
            fake_dot = root / "dot"
            fake_dot.write_text("#!/bin/sh\nif [ \"$3\" = read ]; then echo 'fixture reply'; else echo DOT_SENT_VERIFIED; fi\n")
            fake_dot.chmod(0o700)
            fake_gh = root / "gh"
            fake_gh.write_text("#!/bin/sh\necho '[]'\n"); fake_gh.chmod(0o700)
            fake_agy = root / "agy"
            fake_agy.write_text("#!/usr/bin/env python3\nimport json,sys\nevent=json.loads(sys.stdin.readline())\np=json.loads(event['message']['content'].split('Packet JSON:' + chr(10))[-1])\nd={'event_id':p['event_id'],'task_id':p['task_id'],'stage':p['dialogue_stage'],'blockers':[],'message':'List current blockers with evidence.'}\nprint(json.dumps({'event':'result','result':{'status':'SUCCESS','response':json.dumps(d)}}))\n")
            fake_agy.chmod(0o700)
            env = dict(os.environ, PATH=str(root) + os.pathsep + os.environ["PATH"])
            cmd = [CLI_SCRIPT, "--sources", self.sources_file, "observe", "--interval", "1",
                   "--send-messages", "--pilot-config", str(pilot), "--transport-script", str(fake_dot),
                   "--run-dir", self.run_dir]
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
            observed = None
            try:
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline and proc.poll() is None:
                    state_file = Path(self.run_dir) / "run_state.json"
                    if state_file.exists():
                        observed = json.loads(state_file.read_text()).get("slots", {}).get("0")
                        if observed and observed.get("outcome") != "in_progress_hold":
                            break
                    time.sleep(0.05)
            finally:
                if proc.poll() is None:
                    proc.terminate()
                stdout, stderr = proc.communicate(timeout=5)
            self.assertIsNotNone(observed, (stdout, stderr))
            self.assertTrue(observed.get("delivery_verified"), (observed, stdout, stderr))
            receipt = json.loads((Path(self.run_dir) / "final_receipt.json").read_text())
            self.assertEqual(receipt["sent_messages"], 1)
            self.assertEqual(receipt["stop_reason"], "interrupted")
            self.assertEqual(receipt["mode"], "active")

    def test_wrapper_computes_outer_grace_period(self):
        # Inspect dot-portfolio-coordinator-wrapper.sh to ensure observe duration has + 120s grace
        with open(WRAPPER_SCRIPT, "r") as f:
            wrapper_content = f.read()
        self.assertIn("DEADLINE_SECS=$(( DURATION + 120 ))", wrapper_content)


if __name__ == "__main__":
    unittest.main()
