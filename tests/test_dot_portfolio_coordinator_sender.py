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

from modules.registry import SourceRegistry


class TestDotPortfolioCoordinatorSender(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        # Set temp_dir mode to 0700 for grant parent dir requirement
        os.chmod(self.temp_dir.name, 0o700)
        self.state_dir = os.path.join(self.temp_dir.name, "state")
        self.lock_file = os.path.join(self.temp_dir.name, "sender.lock")

        # Create valid root grant file (mode 0400, owner current uid, valid bounds)
        self.grant_data = {
            "grant_version": 1,
            "task_id": "dot-coordinator-separated-20261007",
            "account_id": "default",
            "action": "send_dot_test_message",
            "max_messages": 10,
            "min_interval_secs": 1,
            "expiry_epoch": int(time.time()) + 3600
        }
        self.grant_file = os.path.join(self.temp_dir.name, "test_grant.json")
        grant_bytes = json.dumps(self.grant_data, sort_keys=True).encode("utf-8")
        with open(self.grant_file, "wb") as f:
            f.write(grant_bytes)
        os.chmod(self.grant_file, 0o400)
        self.grant_sha256 = hashlib.sha256(grant_bytes).hexdigest()

        # Create fake dot.sh transport that verifies argv: --account EXACT send-once MSGFILE
        self.bin_dir = os.path.join(self.temp_dir.name, "bin")
        os.makedirs(self.bin_dir, exist_ok=True)
        self.fake_dot_script = os.path.join(self.bin_dir, "fake_dot.sh")
        script_content = (
            '#!/usr/bin/env bash\n'
            '# Check exact argument passing\n'
            'if [[ "$1" != "--account" || -z "$2" || "$3" != "send-once" || -z "$4" ]]; then\n'
            '  echo "INVALID_ARGV: $*" >&2\n'
            '  exit 2\n'
            'fi\n'
            'echo "DOT_SENT_VERIFIED"\n'
            'exit 0\n'
        )
        with open(self.fake_dot_script, "w") as f:
            f.write(script_content)
        st = os.stat(self.fake_dot_script)
        os.chmod(self.fake_dot_script, st.st_mode | stat.S_IEXEC)

        self.sender_script = str(SKILL_DIR / "scripts" / "dot-portfolio-coordinator-sender.sh")

    def tearDown(self):
        # restore permission to allow cleanup if needed
        try:
            os.chmod(self.grant_file, 0o600)
        except Exception:
            pass
        self.temp_dir.cleanup()

    def _run_sender(self, env_vars=None, args=None):
        cmd = [
            self.sender_script,
            "--account", "default",
            "--state-dir", self.state_dir,
            "--lock-file", self.lock_file,
            "--grant-file", self.grant_file,
            "--grant-sha256", self.grant_sha256,
            "--transport-script", self.fake_dot_script
        ] + (args or [])

        env = dict(os.environ)
        if env_vars:
            env.update(env_vars)

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

    def test_grant_sha256_mismatch_blocks_send(self):
        env = {
            "COORDINATOR_CHANGE_ID": "ev-grant-1",
            "COORDINATOR_CHANGE_SUMMARY": "Test message"
        }
        # Provide forged sha
        args = ["--grant-sha256", "0000000000000000000000000000000000000000000000000000000000000000"]
        rc, res, err = self._run_sender(env_vars=env, args=args)
        self.assertNotEqual(rc, 0)
        self.assertIsNotNone(res)
        self.assertEqual(res.get("outcome"), "invalid")
        self.assertIn("grant", res.get("reason", "").lower())

    def test_grant_symlink_rejected(self):
        sym_grant = os.path.join(self.temp_dir.name, "sym_grant.json")
        os.symlink(self.grant_file, sym_grant)
        env = {
            "COORDINATOR_CHANGE_ID": "ev-sym-1",
            "COORDINATOR_CHANGE_SUMMARY": "Test symlink"
        }
        args = ["--grant-file", sym_grant]
        rc, res, err = self._run_sender(env_vars=env, args=args)
        self.assertNotEqual(rc, 0)
        self.assertEqual(res.get("outcome"), "invalid")
        self.assertIn("grant", res.get("reason", "").lower())

    def test_valid_delivery_with_verified_grant(self):
        env = {
            "COORDINATOR_CHANGE_ID": "ev-101",
            "COORDINATOR_CHANGE_SUMMARY": "Valid test delivery message"
        }
        rc, res, err = self._run_sender(env_vars=env)
        self.assertEqual(rc, 0)
        self.assertIsNotNone(res)
        self.assertEqual(res.get("outcome"), "delivered")
        self.assertTrue(res.get("delivery_verified"))

        # Duplicate detection on immediate retry (cannot force duplicate)
        rc_dup, res_dup, _ = self._run_sender(env_vars=env, args=["--force"])
        self.assertEqual(rc_dup, 0)
        self.assertEqual(res_dup.get("outcome"), "duplicate")

    def test_receipt_requires_standalone_verified_not_substring(self):
        # Fake dot script returns substring inside error line
        with open(self.fake_dot_script, "w") as f:
            f.write('#!/usr/bin/env bash\necho "FAILED: DOT_SENT_VERIFIED was not reached"\nexit 1\n')

        env = {
            "COORDINATOR_CHANGE_ID": "ev-substr-1",
            "COORDINATOR_CHANGE_SUMMARY": "Testing substring failure"
        }
        rc, res, err = self._run_sender(env_vars=env)
        self.assertNotEqual(rc, 0)
        self.assertEqual(res.get("outcome"), "uncertain")
        self.assertEqual(res.get("reason"), "send_unverified")

        # Account should now have an uncertainty hold
        rc_hold, res_hold, _ = self._run_sender(env_vars=env)
        self.assertNotEqual(rc_hold, 0)
        self.assertEqual(res_hold.get("outcome"), "uncertain")
        self.assertEqual(res_hold.get("reason"), "receipt_hold")

    def test_read_only_status_creates_no_files(self):
        clean_state_dir = os.path.join(self.temp_dir.name, "clean_state")
        args = ["--status", "--json", "--state-dir", clean_state_dir]
        rc, res, err = self._run_sender(args=args)
        self.assertEqual(rc, 0)
        self.assertIsNotNone(res)
        self.assertEqual(res.get("account"), "default")
        self.assertIsNone(res.get("state_sha256"))
        # clean_state_dir should not have been created
        self.assertFalse(os.path.exists(clean_state_dir))

    def test_unsupported_poll_blocked_not_ignored(self):
        env = {
            "COORDINATOR_CHANGE_ID": "ev-poll-1",
            "COORDINATOR_CHANGE_SUMMARY": "Test poll"
        }
        args = ["--poll-reply"]
        rc, res, err = self._run_sender(env_vars=env, args=args)
        self.assertNotEqual(rc, 0)
        self.assertEqual(res.get("outcome"), "invalid")
        self.assertIn("poll", res.get("reason", "").lower())


if __name__ == "__main__":
    unittest.main()
