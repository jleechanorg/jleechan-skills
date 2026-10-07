import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / ".claude" / "skills" / "dot-portfolio-coordinator"
import sys
sys.path.insert(0, str(SKILL_DIR / "scripts"))

from modules.registry import SourceRegistry
from modules.sender_protocol import NotificationBindingManager


class TestDotPortfolioCoordinatorSender(unittest.TestCase):
    def setUp(self):
        self.sources_json_path = SKILL_DIR / "references" / "sources.json"
        self.registry = SourceRegistry.from_file(str(self.sources_json_path))

        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_dir = os.path.join(self.temp_dir.name, "state")
        self.binding_file = os.path.join(self.temp_dir.name, "bindings.json")
        self.binding_mgr = NotificationBindingManager(self.registry, self.binding_file)

        # Create fake dot.sh transport
        self.bin_dir = os.path.join(self.temp_dir.name, "bin")
        os.makedirs(self.bin_dir, exist_ok=True)
        self.fake_dot_script = os.path.join(self.bin_dir, "fake_dot.sh")
        with open(self.fake_dot_script, "w") as f:
            f.write('#!/usr/bin/env bash\necho "DOT_SENT_VERIFIED"\nexit 0\n')
        st = os.stat(self.fake_dot_script)
        os.chmod(self.fake_dot_script, st.st_mode | stat.S_IEXEC)

        self.sender_script = str(SKILL_DIR / "scripts" / "dot-portfolio-coordinator-sender.sh")

    def tearDown(self):
        self.temp_dir.cleanup()

    def _run_sender(self, env_vars=None, args=None):
        env = dict(os.environ)
        env["DOT_PORTFOLIO_STATE_DIR"] = self.state_dir
        env["DOT_PORTFOLIO_BINDINGS_FILE"] = self.binding_file
        env["DOT_TRANSPORT_SCRIPT"] = self.fake_dot_script
        env["DOT_TEST_CALLER_PRINCIPAL"] = "verified-local-principal"
        if env_vars:
            env.update(env_vars)

        cmd = [self.sender_script] + (args or [])
        proc = subprocess.run(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        result_line = None
        for line in proc.stdout.splitlines():
            if line.startswith("COORDINATOR_RESULT "):
                result_line = json.loads(line[len("COORDINATOR_RESULT "):])
            elif line.startswith("COORDINATOR_STATUS "):
                result_line = json.loads(line[len("COORDINATOR_STATUS "):])

        return proc.returncode, result_line, proc.stderr

    def test_quiet_wake_on_no_input(self):
        rc, res, err = self._run_sender()
        self.assertEqual(rc, 0)
        self.assertIsNotNone(res)
        self.assertEqual(res.get("outcome"), "quiet")

    def test_missing_auth_ref_fails_before_transport(self):
        env = {
            "COORDINATOR_CHANGE_ID": "ev-001",
            "COORDINATOR_CHANGE_SUMMARY": "Test change summary"
        }
        rc, res, err = self._run_sender(env_vars=env)
        self.assertNotEqual(rc, 0)
        self.assertIsNotNone(res)
        self.assertEqual(res.get("outcome"), "invalid")
        self.assertIn("authorization", res.get("reason", "").lower())

    def test_valid_delivery_persists_binding_and_receipt(self):
        # Register binding first
        binding = self.binding_mgr.register_binding(
            control_record_id="bd-ctrl-1",
            action_id="act-101",
            attempt_id="att-1",
            account="default",
            event_id="ev-101",
            kind="delta",
            message_sha256="abc123sha",
            task_key={"github_host": "github.com", "repository": "example-org/roadmap", "source_namespace": "roadmap", "bead_id": "bd-ctrl-1"},
            grant_version="v1",
            control_entry_digest="dig-123"
        )
        auth_ref = "bd-ctrl-1/act-101/att-1"

        env = {
            "COORDINATOR_CHANGE_ID": "ev-101",
            "COORDINATOR_CHANGE_SUMMARY": "Test valid delivery"
        }
        args = ["--authorization-ref", auth_ref, "--account", "default"]

        rc, res, err = self._run_sender(env_vars=env, args=args)
        self.assertEqual(rc, 0)
        self.assertIsNotNone(res)
        self.assertEqual(res.get("outcome"), "delivered")
        self.assertTrue(res.get("delivery_verified"))

        # Verify duplicate detection on immediate retry
        rc_dup, res_dup, _ = self._run_sender(env_vars=env, args=args)
        self.assertEqual(rc_dup, 0)
        self.assertEqual(res_dup.get("outcome"), "duplicate")

    def test_receipt_hold_on_uncertain_send(self):
        # Fake dot that fails
        with open(self.fake_dot_script, "w") as f:
            f.write('#!/usr/bin/env bash\necho "DOT_SEND_UNVERIFIED"\nexit 4\n')

        self.binding_mgr.register_binding(
            control_record_id="bd-ctrl-1",
            action_id="act-201",
            attempt_id="att-1",
            account="default",
            event_id="ev-201",
            kind="delta",
            message_sha256="abc201sha",
            task_key={"github_host": "github.com", "repository": "example-org/roadmap", "source_namespace": "roadmap", "bead_id": "bd-ctrl-1"},
            grant_version="v1",
            control_entry_digest="dig-201"
        )
        auth_ref = "bd-ctrl-1/act-201/att-1"

        env = {
            "COORDINATOR_CHANGE_ID": "ev-201",
            "COORDINATOR_CHANGE_SUMMARY": "Failing send attempt"
        }
        args = ["--authorization-ref", auth_ref, "--account", "default"]

        rc, res, err = self._run_sender(env_vars=env, args=args)
        self.assertNotEqual(rc, 0)
        self.assertEqual(res.get("outcome"), "uncertain")

        # Second attempt on account must be blocked by the existing hold!
        rc_hold, res_hold, _ = self._run_sender(env_vars=env, args=args)
        self.assertNotEqual(rc_hold, 0)
        self.assertEqual(res_hold.get("outcome"), "uncertain")
        self.assertEqual(res_hold.get("reason"), "receipt_hold")

    def test_read_only_status(self):
        args = ["--status", "--json", "--account", "default"]
        rc, res, err = self._run_sender(args=args)
        self.assertEqual(rc, 0)
        self.assertIsNotNone(res)
        self.assertEqual(res.get("account"), "default")
        self.assertIn("delivery_unverified", res)
        self.assertIn("retained_event_ids", res)


if __name__ == "__main__":
    unittest.main()
