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
        self.temp_dir = tempfile.TemporaryDirectory()
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
        grant_dir = tempfile.TemporaryDirectory()
        os.chmod(grant_dir.name, 0o700)
        grant_data = {
            "grant_version": 1,
            "task_id": "dot-coordinator-separated-20261007",
            "account_id": "test-account",
            "action": "send_dot_test_message",
            "max_messages": 5,
            "min_interval_secs": 1,
            "expiry_epoch": int(time.time()) + 3600
        }
        grant_file = os.path.join(grant_dir.name, "grant.json")
        grant_bytes = json.dumps(grant_data, sort_keys=True).encode("utf-8")
        with open(grant_file, "wb") as f:
            f.write(grant_bytes)
        os.chmod(grant_file, 0o400)
        grant_sha = hashlib.sha256(grant_bytes).hexdigest()

        # Fake transport
        fake_dot = os.path.join(grant_dir.name, "fake_dot.sh")
        with open(fake_dot, "w") as f:
            f.write("#!/bin/sh\necho 'DOT_SENT_VERIFIED'\nexit 0\n")
        os.chmod(fake_dot, 0o755)

        env = os.environ.copy()
        env["DOT_TRANSPORT_SCRIPT"] = fake_dot

        cmd = [
            CLI_SCRIPT,
            "--sources", self.sources_file,
            "observe",
            "--duration", "2",
            "--interval", "1",
            "--notification-interval", "1",
            "--send-messages",
            "--grant-file", grant_file,
            "--grant-sha256", grant_sha,
            "--account", "test-account",
            "--run-dir", self.run_dir
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        self.assertEqual(proc.returncode, 0, f"STDOUT: {proc.stdout}, STDERR: {proc.stderr}")

        receipt_file = os.path.join(self.run_dir, "final_receipt.json")
        self.assertTrue(os.path.exists(receipt_file))
        with open(receipt_file, "r") as f:
            receipt = json.load(f)
        self.assertGreaterEqual(receipt.get("sent_messages", 0), 1)
        self.assertEqual(receipt.get("mode"), "active")
        grant_dir.cleanup()

    def test_wrapper_computes_outer_grace_period(self):
        # Inspect dot-portfolio-coordinator-wrapper.sh to ensure observe duration has + 120s grace
        with open(WRAPPER_SCRIPT, "r") as f:
            wrapper_content = f.read()
        self.assertIn("DEADLINE_SECS=$(( DURATION + 120 ))", wrapper_content)


if __name__ == "__main__":
    unittest.main()
