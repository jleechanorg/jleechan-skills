import importlib.util
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".claude/skills/dot-portfolio-coordinator/scripts/coordinator-portfolio.py"
spec = importlib.util.spec_from_file_location("portfolio_cli", SCRIPT)
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


class PilotTests(unittest.TestCase):
    def test_schedule_is_stable_and_exactly_36_slots(self):
        config = {"run_id": "pilot-a", "activated_at_epoch": 1000,
                  "duration_secs": 43200, "accounts": [{"account": x} for x in ("a", "b", "c")]}
        slots = cli.pilot_slots(config)
        self.assertEqual(len(slots), 36)
        self.assertEqual([x["due_epoch"] for x in slots[:4]], [1000, 2200, 3400, 4600])
        self.assertEqual([x["account_index"] for x in slots[:4]], [0, 1, 2, 0])
        self.assertEqual(slots, cli.pilot_slots(json.loads(json.dumps(config))))
        self.assertEqual(len({x["event_id"] for x in slots}), 36)

    def test_private_run_directory_rejects_existing_public_directory_without_chmod(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            path = Path(tmp) / "public"
            path.mkdir(mode=0o755)
            with self.assertRaises(ValueError):
                cli.private_run_directory(str(path))
            self.assertEqual(path.stat().st_mode & 0o777, 0o755)

    def test_sender_exit_zero_is_not_verified_delivery(self):
        def deferred(argv, source_callback=None):
            print('COORDINATOR_RESULT {"outcome":"deferred","delivery_verified":false}')
            return 0
        with mock.patch("modules.sender.run_sender_cli", side_effect=deferred):
            result = cli.call_sender([], "event", "full message")
        self.assertFalse(result["delivery_verified"])
        self.assertEqual(result["outcome"], "deferred")

    def test_sender_preserves_full_prompt_and_restores_environment(self):
        text = "begin\n" + "complete guidance " * 300 + "\nend"
        def delivered(argv, source_callback=None):
            self.assertEqual(os.environ["COORDINATOR_CHANGE_SUMMARY"], text)
            print('COORDINATOR_RESULT {"outcome":"delivered","delivery_verified":true}')
            return 0
        with mock.patch.dict(os.environ, {"COORDINATOR_CHANGE_SUMMARY": "prior"}):
            with mock.patch("modules.sender.run_sender_cli", side_effect=delivered):
                result = cli.call_sender([], "event", text)
            self.assertEqual(os.environ["COORDINATOR_CHANGE_SUMMARY"], "prior")
        self.assertTrue(result["delivery_verified"])

    def test_resume_preserves_deadline_and_terminal_slots(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            root = Path(tmp)
            state = cli.load_run_state(root, "binding", 43200, 1000)
            state["slots"]["0"] = {"outcome": "uncertain"}
            cli.atomic_write_json(root / "run_state.json", state)
            resumed = cli.load_run_state(root, "binding", 43200, 9999)
            self.assertEqual(resumed["started_at_epoch"], 1000)
            self.assertEqual(resumed["slots"]["0"]["outcome"], "uncertain")
            with self.assertRaises(ValueError):
                cli.load_run_state(root, "different", 43200, 1000)

    def test_pilot_config_requires_three_distinct_accounts_and_bounded_window(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            path = Path(tmp) / "pilot.json"
            config = {"run_id": "p", "task_id": "dot-coordinator-separated-20261007",
                      "activated_at_epoch": time.time(), "duration_secs": 43200,
                      "authority": "Continue the authorized task; no merge authority.",
                      "accounts": [{"account": "same", "grant_file": "/tmp/g", "grant_sha256": "a" * 64}] * 3}
            path.write_text(json.dumps(config)); path.chmod(0o400)
            with self.assertRaises(ValueError):
                cli.load_pilot_config(str(path))

    def test_missing_driver_response_does_not_send(self):
        import types
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            root = Path(tmp)
            config = {"task_id": "task", "authority": "scope",
                      "accounts": [{"account": "a", "grant_file": "g", "grant_sha256": "s"}]}
            state = {"dialogue": {}}
            fake = types.SimpleNamespace(DriverAdapter=mock.Mock())
            fake.DriverAdapter.return_value.decide.return_value = {"status": "driver_failed", "reason": "timeout"}
            with mock.patch.dict("sys.modules", {"modules.driver_adapter": fake}):
                with mock.patch("modules.process_utils.run_bounded_command", return_value=(0, "reply", "")):
                    with mock.patch.object(cli, "call_sender") as send:
                        result = cli.run_pilot_slot(config, {"event_id": "event", "account_index": 0},
                                                    state, {}, root, "agy", "/tmp/dot", time.monotonic() + 1000)
            self.assertEqual(result["outcome"], "driver_failed")
            send.assert_not_called()
