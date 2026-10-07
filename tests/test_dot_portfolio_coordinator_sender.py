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
PREPARED_NONCE = "0123456789abcdef0123456789abcdef"
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
            f'echo "prepared {PREPARED_NONCE}"\n'
            'read -t 5 -r cmd || cmd="timeout"\n'
            f'if [[ "$cmd" == "commit {PREPARED_NONCE}" ]]; then\n'
            '  echo "DOT_SENT_VERIFIED"\n'
            '  exit 0\n'
            'else\n'
            '  exit 1\n'
            'fi\n'
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
        self.assertEqual(rc, 0, (res, err))
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
            f.write(
                '#!/usr/bin/env bash\n'
                f'echo "prepared {PREPARED_NONCE}"\n'
                'read -t 5 -r cmd || cmd="timeout"\n'
                'echo "FAILED: DOT_SENT_VERIFIED was not reached"\n'
                'exit 1\n'
            )

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

        def fake_interactive_run(cmd, interact, **kwargs):
            child = mock.Mock()
            child.read_frame.side_effect = [
                f"prepared {PREPARED_NONCE}".encode(), b"DOT_SENT_VERIFIED"
            ]
            interact(child)
            return None

        with mock.patch.dict(os.environ, env), \
                mock.patch.dict(os.environ, {"DOT_TRANSPORT_SCRIPT": "/tmp/ambient-must-be-ignored"}), \
                mock.patch.object(sender_module, "run_bounded_interactive_command",
                                  side_effect=fake_interactive_run) as run, \
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
            f.write(
                '#!/usr/bin/env bash\n'
                f'echo "prepared {PREPARED_NONCE}"\n'
                'read -t 5 -r cmd || cmd="timeout"\n'
                f'if [[ "$cmd" == "commit {PREPARED_NONCE}" ]]; then\n'
                '  echo "DOT_SENT_VERIFIED "\n'
                '  exit 0\n'
                'fi\n'
                'exit 1\n'
            )
        env = {"COORDINATOR_CHANGE_ID": "ev-marker-space",
               "COORDINATOR_CHANGE_SUMMARY": "Trailing whitespace is not marker"}
        rc, res, _ = self._run_sender(env)
        self.assertEqual(rc, 4)
        self.assertEqual(res["reason"], "send_unverified")

    def test_grant_invalid_or_expired_after_prepared_aborts_without_delivered_receipt(self):
        import shlex
        root = Path(self.temp_dir.name)
        click_marker = root / "click_marker_test2.txt"
        abort_marker = root / "abort_marker_test2.txt"
        prepared_marker = root / "prepared_marker_test2.txt"

        fake_transport = root / "fake_transport_test2.sh"
        fake_transport.write_text(
            "#!/bin/sh\n"
            f"echo 'prepared {PREPARED_NONCE}' > {shlex.quote(str(prepared_marker))}\n"
            f"chmod 0600 {shlex.quote(self.grant_file)}\n"
            f"echo '{{\"corrupted\": true}}' > {shlex.quote(self.grant_file)}\n"
            f"chmod 0400 {shlex.quote(self.grant_file)}\n"
            f"printf 'prepared {PREPARED_NONCE}\\n'\n"
            "read -t 5 -r cmd || cmd='timeout'\n"
            "case \"$cmd\" in\n"
            f"  'commit {PREPARED_NONCE}')\n"
            f"    echo 'clicked' > {shlex.quote(str(click_marker))}\n"
            "    echo 'DOT_SENT_VERIFIED'\n"
            "    exit 0\n"
            "    ;;\n"
            "  *)\n"
            f"    echo \"$cmd\" > {shlex.quote(str(abort_marker))}\n"
            "    exit 0\n"
            "    ;;\n"
            "esac\n"
        )
        fake_transport.chmod(0o700)

        env = {
            "COORDINATOR_CHANGE_ID": "ev-grant-expired-post-prep",
            "COORDINATOR_CHANGE_SUMMARY": "Test abort on grant expiry",
        }
        rc, res, _ = self._run_sender(
            env_vars=env,
            args=["--transport-script", str(fake_transport)],
        )

        self.assertTrue(prepared_marker.exists(), "Transport must have reached prepared state")
        self.assertTrue(abort_marker.exists(), "Sender must have sent abort after grant became invalid")
        self.assertIn("abort", abort_marker.read_text())
        self.assertFalse(click_marker.exists(), "Irreversible click must not happen when grant is invalid")
        self.assertNotEqual(rc, 0)
        self.assertIsNotNone(res)
        self.assertNotEqual(res.get("outcome"), "delivered")
        self.assertFalse(res.get("delivery_verified", False))
        self.assertEqual(res.get("outcome"), "uncertain")
        self.assertIn("grant", res.get("reason", ""))

    def test_successful_source_and_grant_revalidation_commits_and_clicks_in_same_context(self):
        import shlex
        root = Path(self.temp_dir.name)
        click_marker = root / "click_marker_test3.txt"
        prepared_marker = root / "prepared_marker_test3.txt"
        commit_received = root / "commit_received_test3.txt"

        fake_transport = root / "fake_transport_test3.sh"
        fake_transport.write_text(
            "#!/bin/sh\n"
            f"echo 'prepared {PREPARED_NONCE}' > {shlex.quote(str(prepared_marker))}\n"
            f"printf 'prepared {PREPARED_NONCE}\\n'\n"
            "read -t 5 -r cmd || cmd='timeout'\n"
            "case \"$cmd\" in\n"
            f"  'commit {PREPARED_NONCE}')\n"
            f"    echo \"$cmd\" > {shlex.quote(str(commit_received))}\n"
            f"    echo 'clicked' > {shlex.quote(str(click_marker))}\n"
            "    echo 'DOT_SENT_VERIFIED'\n"
            "    exit 0\n"
            "    ;;\n"
            "  *)\n"
            "    exit 1\n"
            "    ;;\n"
            "esac\n"
        )
        fake_transport.chmod(0o700)

        source_checked = []

        def source_cb():
            source_checked.append(True)
            return True, "ok"

        env = {
            "COORDINATOR_CHANGE_ID": "ev-success-test3",
            "COORDINATOR_CHANGE_SUMMARY": "Test commit on valid revalidation",
        }
        with mock.patch.dict(os.environ, env):
            rc = sender_module.run_sender_cli(
                [
                    "--account", "default",
                    "--state-dir", self.state_dir,
                    "--lock-file", self.lock_file,
                    "--grant-file", self.grant_file,
                    "--grant-sha256", self.grant_sha256,
                    "--transport-script", str(fake_transport),
                ],
                source_callback=source_cb,
            )

        self.assertEqual(rc, 0)
        self.assertTrue(prepared_marker.exists(), "Transport must have reached prepared state")
        self.assertTrue(source_checked, "Source callback must have run after prepared")
        self.assertTrue(commit_received.exists(), "Transport must have received commit command")
        self.assertEqual(
            commit_received.read_text().strip(), f"commit {PREPARED_NONCE}"
        )
        self.assertTrue(click_marker.exists(), "Transport must only click after valid commit received")

    def test_sender_rejects_prepared_frame_without_nonce(self):
        env = {
            "COORDINATOR_CHANGE_ID": "ev-missing-nonce",
            "COORDINATOR_CHANGE_SUMMARY": "Reject a prepared frame without nonce",
        }
        child = mock.Mock()
        child.read_frame.side_effect = [b"prepared", b"aborted"]
        source_callback = mock.Mock(return_value=(True, "ok"))

        def fake_interactive_run(cmd, interact, **kwargs):
            interact(child)

        with mock.patch.dict(os.environ, env), \
                mock.patch.object(sender_module, "run_bounded_interactive_command",
                                  side_effect=fake_interactive_run), \
                mock.patch("sys.stdout", new_callable=io.StringIO) as stdout:
            rc = sender_module.run_sender_cli(
                ["--account", "default", "--state-dir", self.state_dir,
                 "--lock-file", self.lock_file, "--grant-file", self.grant_file,
                 "--grant-sha256", self.grant_sha256,
                 "--transport-script", self.fake_dot_script],
                source_callback=source_callback,
            )

        results = [json.loads(line.removeprefix("COORDINATOR_RESULT "))
                   for line in stdout.getvalue().splitlines()
                   if line.startswith("COORDINATOR_RESULT ")]
        self.assertNotEqual(rc, 0)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["outcome"], "uncertain")
        self.assertEqual(results[0]["reason"], "invalid_prepared_frame")
        source_callback.assert_not_called()
        self.assertIn("abort", [call.args[0] for call in child.send_frame.call_args_list])

    def test_sender_exceptions_use_fixed_reason_codes(self):
        cases = (
            ("read", b"unused", 4, "prepared_transport_unavailable"),
            ("source", f"prepared {PREPARED_NONCE}".encode(),
             0, "source_callback_failed"),
            ("commit", f"prepared {PREPARED_NONCE}".encode(),
             4, "commit_send_failed"),
        )
        for index, (case, prepared_frame, expected_rc, expected_reason) in enumerate(cases):
            with self.subTest(case=case):
                state_dir = Path(self.temp_dir.name) / f"state-{index}"
                state_dir.mkdir(mode=0o700)
                lock_file = state_dir / "sender.lock"
                env = {
                    "COORDINATOR_CHANGE_ID": f"ev-private-error-{index}",
                    "COORDINATOR_CHANGE_SUMMARY": "Keep transport errors private",
                }
                child = mock.Mock()
                if case == "read":
                    child.read_frame.side_effect = RuntimeError("private transport detail")
                else:
                    child.read_frame.side_effect = [prepared_frame, b"aborted"]
                if case == "commit":
                    child.send_frame.side_effect = RuntimeError("private commit detail")
                callback = mock.Mock(return_value=(True, "ok"))
                if case == "source":
                    callback.side_effect = RuntimeError("private callback detail")

                def fake_interactive_run(cmd, interact, **kwargs):
                    interact(child)

                with mock.patch.dict(os.environ, env), \
                        mock.patch.object(sender_module, "run_bounded_interactive_command",
                                          side_effect=fake_interactive_run), \
                        mock.patch("sys.stdout", new_callable=io.StringIO) as stdout:
                    rc = sender_module.run_sender_cli(
                        ["--account", "default", "--state-dir", str(state_dir),
                         "--lock-file", str(lock_file), "--grant-file", self.grant_file,
                         "--grant-sha256", self.grant_sha256,
                         "--transport-script", self.fake_dot_script],
                        source_callback=callback,
                    )

                output = stdout.getvalue()
                results = [json.loads(line.removeprefix("COORDINATOR_RESULT "))
                           for line in output.splitlines()
                           if line.startswith("COORDINATOR_RESULT ")]
                self.assertEqual(rc, expected_rc)
                self.assertEqual(len(results), 1)
                self.assertEqual(results[0]["reason"], expected_reason)
                self.assertNotIn("private ", output)


if __name__ == "__main__":
    unittest.main()
