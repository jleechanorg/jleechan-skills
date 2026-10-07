import hashlib
import io
import json
import os
import stat
import subprocess
import tempfile
import time
import unittest
from unittest import mock
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / ".claude" / "skills" / "dot-portfolio-coordinator"
sys_path = str(SKILL_DIR / "scripts")
import sys
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)

from modules.registry import SourceRegistry
from modules import sender as sender_module


class TestDotPortfolioCoordinatorSender(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        # Set temp_dir mode to 0700 for grant parent dir requirement
        os.chmod(self.temp_dir.name, 0o700)
        self.state_dir = os.path.join(self.temp_dir.name, "state")
        os.mkdir(self.state_dir, 0o700)
        self.lock_file = os.path.join(self.state_dir, "sender.lock")

        # Create valid root grant file (mode 0400, owner current uid, valid bounds)
        self.grant_data = {
            "grant_version": 1,
            "task_id": "dot-coordinator-separated-20261007",
            "account_id": "default",
            "action": "send_dot_test_message",
            "activated_at_epoch": int(time.time()) - 10,
            "max_messages": 3,
            "min_interval_secs": 3600,
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

    def _run_sender(self, env_vars=None, args=None, account="default"):
        cmd = [
            self.sender_script,
            "--account", account,
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

    def test_non_finite_grant_expiry_rejected(self):
        self.grant_data["expiry_epoch"] = float("nan")
        grant_bytes = json.dumps(self.grant_data, sort_keys=True).encode("utf-8")
        os.chmod(self.grant_file, 0o600)
        with open(self.grant_file, "wb") as f:
            f.write(grant_bytes)
        os.chmod(self.grant_file, 0o400)
        self.grant_sha256 = hashlib.sha256(grant_bytes).hexdigest()
        rc, res, _ = self._run_sender({
            "COORDINATOR_CHANGE_ID": "ev-nan",
            "COORDINATOR_CHANGE_SUMMARY": "NaN must not pass"
        })
        self.assertEqual(rc, 2)
        self.assertEqual(res["outcome"], "invalid")

    def test_state_directory_is_required_and_private(self):
        cmd = [self.sender_script, "--account", "default", "--grant-file", self.grant_file,
               "--grant-sha256", self.grant_sha256, "--transport-script", self.fake_dot_script]
        env = dict(os.environ, DOT_PORTFOLIO_STATE_DIR=self.state_dir,
                   COORDINATOR_CHANGE_ID="ev-no-state",
                   COORDINATOR_CHANGE_SUMMARY="No implicit state")
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("state_dir", proc.stdout)

    def test_full_prompt_is_not_truncated(self):
        summary = "x" * 6000
        rc, res, _ = self._run_sender({
            "COORDINATOR_CHANGE_ID": "ev-long",
            "COORDINATOR_CHANGE_SUMMARY": summary
        })
        self.assertEqual(rc, 0)
        self.assertEqual(res["outcome"], "delivered")

    def test_reconcile_option_is_rejected_until_supported(self):
        rc, res, _ = self._run_sender({
            "COORDINATOR_CHANGE_ID": "ev-reconcile",
            "COORDINATOR_CHANGE_SUMMARY": "Must not ignore reconcile"
        }, args=["--reconcile-receipt", "/tmp/receipt"])
        self.assertEqual(rc, 2)
        self.assertEqual(res["outcome"], "invalid")

    def test_grant_interval_and_message_cap_are_enforced(self):
        state = {
            "schema_version": 1,
            "grant_sha256": self.grant_sha256,
            "attempted_count": 1,
            "last_attempt_epoch": time.time() - 30,
            "last_sent_epoch": 0,
            "retained_event_ids": [],
            "pending_delivery": None,
        }
        account_file = os.path.join(self.state_dir, "account_default.json")
        with open(account_file, "w", encoding="utf-8") as f:
            json.dump(state, f)
        os.chmod(account_file, 0o600)
        env = {"COORDINATOR_CHANGE_ID": "ev-too-soon",
               "COORDINATOR_CHANGE_SUMMARY": "Hourly interval"}
        rc, res, _ = self._run_sender(env, args=["--force"])
        self.assertEqual(rc, 0)
        self.assertEqual(res["reason"], "grant_min_interval")

        state["attempted_count"] = self.grant_data["max_messages"]
        state["last_attempt_epoch"] = time.time() - 3601
        with open(account_file, "w", encoding="utf-8") as f:
            json.dump(state, f)
        rc, res, _ = self._run_sender(env, args=["--force"])
        self.assertEqual(rc, 0)
        self.assertEqual(res["reason"], "grant_message_limit")

    def test_corrupt_state_holds_without_transport(self):
        account_file = os.path.join(self.state_dir, "account_default.json")
        with open(account_file, "w", encoding="utf-8") as f:
            f.write("{")
        os.chmod(account_file, 0o600)
        rc, res, _ = self._run_sender({
            "COORDINATOR_CHANGE_ID": "ev-corrupt",
            "COORDINATOR_CHANGE_SUMMARY": "Do not reset corrupted state"
        })
        self.assertEqual(rc, 3)
        self.assertEqual(res["reason"], "state_corrupt_hold")

    def test_default_transport_path_is_sibling_dot_skill(self):
        env = {
            "COORDINATOR_CHANGE_ID": "ev-default-transport",
            "COORDINATOR_CHANGE_SUMMARY": "Verify default path without sending",
        }
        expected_transport = str(SKILL_DIR.parent / "dot" / "scripts" / "dot.sh")
        with mock.patch.dict(os.environ, env), \
                mock.patch.dict(os.environ, {"DOT_TRANSPORT_SCRIPT": "/tmp/ambient-must-be-ignored"}), \
                mock.patch.object(sender_module, "run_bounded_command",
                                  return_value=(0, "DOT_SENT_VERIFIED\n", "")) as run, \
                mock.patch("sys.stdout", new_callable=io.StringIO):
            rc = sender_module.run_sender_cli([
                "--account", "default", "--state-dir", self.state_dir,
                "--lock-file", self.lock_file, "--grant-file", self.grant_file,
                "--grant-sha256", self.grant_sha256,
            ])
        self.assertEqual(rc, 0)
        self.assertEqual(run.call_args.args[0][0], expected_transport)

    def test_grant_requires_exact_read_only_mode(self):
        os.chmod(self.grant_file, 0o600)
        rc, res, _ = self._run_sender({
            "COORDINATOR_CHANGE_ID": "ev-grant-mode",
            "COORDINATOR_CHANGE_SUMMARY": "Reject writable grant"
        })
        self.assertEqual(rc, 2)
        self.assertIn("grant", res["reason"])

    def test_invalid_state_numbers_are_corrupt_holds(self):
        account_file = os.path.join(self.state_dir, "account_default.json")
        for attempts, last_attempt, last_sent in (
            (1, float("inf"), 0), (-1, 0, 0), (1, 0, float("nan")),
        ):
            state = {"schema_version": 1, "grant_sha256": self.grant_sha256,
                     "attempted_count": attempts, "last_attempt_epoch": last_attempt,
                     "last_sent_epoch": last_sent, "retained_event_ids": [],
                     "pending_delivery": None}
            with open(account_file, "w", encoding="utf-8") as f:
                json.dump(state, f)
            os.chmod(account_file, 0o600)
            rc, res, _ = self._run_sender({
                "COORDINATOR_CHANGE_ID": f"ev-state-invalid-{attempts}-{last_attempt}",
                "COORDINATOR_CHANGE_SUMMARY": "Reject non-finite state"
            })
            self.assertEqual(rc, 3)
            self.assertEqual(res["reason"], "state_corrupt_hold")

    def test_worker_sha_is_actual_module_digest(self):
        self.assertEqual(sender_module.WORKER_SHA,
                         hashlib.sha256(Path(sender_module.__file__).read_bytes()).hexdigest())

    def test_corrupt_status_is_explicit_hold(self):
        account_file = os.path.join(self.state_dir, "account_default.json")
        with open(account_file, "w", encoding="utf-8") as f:
            f.write("{")
        os.chmod(account_file, 0o600)
        rc, res, _ = self._run_sender(args=["--status", "--json"])
        self.assertEqual(rc, 3)
        self.assertEqual(res["outcome"], "hold")
        self.assertTrue(res["delivery_unverified"])

    def test_custom_lock_filename_is_rejected(self):
        rc, res, _ = self._run_sender({
            "COORDINATOR_CHANGE_ID": "ev-lock-name",
            "COORDINATOR_CHANGE_SUMMARY": "Reject split lock"
        }, args=["--lock-file", os.path.join(self.state_dir, "other.lock")])
        self.assertEqual(rc, 2)
        self.assertEqual(res["reason"], "canonical_lock_file_required")

    def test_verification_marker_must_be_exact_line(self):
        with open(self.fake_dot_script, "w", encoding="utf-8") as f:
            f.write('#!/usr/bin/env bash\necho "DOT_SENT_VERIFIED "\nexit 0\n')
        env = {"COORDINATOR_CHANGE_ID": "ev-marker-space",
               "COORDINATOR_CHANGE_SUMMARY": "Trailing whitespace is not marker"}
        rc, res, _ = self._run_sender(env)
        self.assertEqual(rc, 4)
        self.assertEqual(res["reason"], "send_unverified")


if __name__ == "__main__":
    unittest.main()
