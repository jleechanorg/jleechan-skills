import hashlib
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


class RecurringPilotTests(unittest.TestCase):
    """Real driver validation, sender eligibility, and prepared transport receipts."""

    def setUp(self):
        from modules import sender

        temp = tempfile.TemporaryDirectory(dir="/tmp")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.started = 10000
        self.now = self.started
        self.driver_delay = 0
        self.packets = []
        self.config = {
            "run_id": "recurring-fixture", "task_id": "dot-coordinator-separated-20261007",
            "activated_at_epoch": self.started, "duration_secs": 10800,
            "authority": "Check current fixture work; no merge authority.",
            "state_dir": str(self.root), "accounts": [],
        }
        for account in ("first", "second", "third"):
            grant = {
                "grant_version": 1, "task_id": self.config["task_id"],
                "account_id": account, "action": "coordination_message",
                "activated_at_epoch": self.started, "expiry_epoch": self.started + 10800,
                "max_messages": 2, "min_interval_secs": 3600,
            }
            path = self.root / (account + ".json")
            path.write_text(json.dumps(grant))
            path.chmod(0o400)
            self.config["accounts"].append({
                "account": account, "grant_file": str(path),
                "grant_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            })
        item = {"id": "7", "title": "Fixture current work", "updated_at": "version-1",
                "task_composite_key": ["github.com", "example-org/repo", "fixture", "7"]}
        self.binding, reason = cli.task_source_binding("fixture", item)
        self.assertEqual(reason, "ok")
        self.snapshot = {"candidate_bindings": [{
            "task_id": "fixture-7", "source_binding": self.binding,
        }]}
        self.source_reader = mock.Mock(side_effect=lambda expected, timeout: (self.binding, "ok"))
        self.transport = self.root / "fake-dot.sh"
        self.capture = self.root / "commits.txt"
        self.transport.write_text(
            "#!/bin/sh\n"
            "test \"$1\" = --account && test \"$3\" = send-once || exit 2\n"
            "nonce=0123456789abcdef0123456789abcdef\n"
            "echo \"prepared $nonce\"\n"
            "read -r cmd\n"
            "test \"$cmd\" = \"commit $nonce\" || exit 0\n"
            "printf '%s %s\\n' \"$2\" \"$COORDINATOR_CHANGE_ID\" >> \"$DOT_CAPTURE_FILE\"\n"
            "echo DOT_SENT_VERIFIED\n"
        )
        self.transport.chmod(0o700)
        self.enterContext(mock.patch.dict(os.environ, {"DOT_CAPTURE_FILE": str(self.capture)}))
        self.enterContext(mock.patch("time.time", side_effect=lambda: self.now))
        # Only model execution is faked; packet and decision validation stay real.
        self.enterContext(mock.patch("modules.driver_adapter.shutil.which", return_value="/fixture/agy"))
        self.enterContext(mock.patch("modules.driver_adapter.run_bounded_command", side_effect=self.model))
        self.send = self.enterContext(mock.patch.object(cli, "call_sender", wraps=cli.call_sender))
        self.grants = self.enterContext(mock.patch.object(
            sender, "validate_operator_grant", wraps=sender.validate_operator_grant,
        ))
        self.state = cli.load_run_state(self.root, "fixture", 10800, self.started)
        self.slots = cli.pilot_slots(self.config)

    def model(self, argv, **kwargs):
        event = json.loads(kwargs["input_text"])
        packet = json.loads(event["message"]["content"].split("Packet JSON:\n")[-1])
        self.packets.append(packet)
        self.now += self.driver_delay
        decision = {
            "schema_version": 1, "event_id": packet["event_id"], "task_id": "fixture-7",
            "outcome": "send_proposal", "stage": packet["dialogue_stage"],
            "source_binding": self.binding, "grant_binding": packet["grant_binding"],
            "correlation": None, "judgment": {"assessment": "unknown", "safe_next_action": "ask Dot"},
            "blockers": [], "action": "send", "message": "Check current fixture work.",
        }
        return 0, json.dumps({"event": "result", "result": {
            "status": "SUCCESS", "response": json.dumps(decision),
        }}), ""

    def process(self):
        cli.process_due_slots(
            self.config, self.state, self.root, self.snapshot, "agy", str(self.transport),
            time.monotonic() + 10000, self.now, source_receipt_reader=self.source_reader,
        )

    def resume(self):
        self.state = cli.load_run_state(self.root, "fixture", 10800, self.now)

    def ledger(self):
        return json.loads((self.root / "sender-0" / "account_first.json").read_text())

    def assert_two_receipts(self):
        ids = [self.slots[index]["event_id"] for index in (0, 3)]
        self.assertEqual(self.capture.read_text().splitlines(), ["first " + event for event in ids])
        ledger = self.ledger()
        self.assertEqual(ledger["retained_event_ids"], ids)
        self.assertEqual(ledger["attempted_count"], 2)
        self.assertIsNone(ledger["pending_delivery"])
        self.assertEqual(self.source_reader.call_count, 2)
        self.assertEqual(self.state["started_at_epoch"], self.started)
        self.assertEqual(self.state["duration_secs"], 10800)
        print("verified same-account receipts:", json.dumps(ids))

    def test_two_same_account_slots_each_invoke_driver_and_sender(self):
        self.driver_delay = 120
        self.process()
        self.assertTrue(self.state["slots"]["0"]["delivery_verified"])
        self.driver_delay = 0
        self.now += 3600
        self.resume()
        self.process()
        self.assertTrue(self.state["slots"]["3"]["delivery_verified"], self.state["slots"]["3"])
        ids = [self.slots[index]["event_id"] for index in (0, 3)]
        self.assertEqual([packet["event_id"] for packet in self.packets], ids)
        self.assertEqual([call.args[1] for call in self.send.call_args_list], ids)
        self.assertEqual(self.grants.call_count, 8)
        for packet in self.packets:
            self.assertEqual(packet["dialogue_stage"], "inventory")
            self.assertEqual(packet["phase"], "inventory_due")
            self.assertEqual(packet["previous_dot_reply"], "")
            self.assertIsNone(packet["correlation"])
        self.assert_two_receipts()
        self.resume()
        self.process()
        self.assertEqual(self.send.call_count, 2)
        # A third distinct slot still obeys the real grant's two-message cap.
        self.now += 3600
        self.process()
        self.assertEqual(self.state["slots"]["6"]["reason"], "grant_message_limit")
        self.assert_two_receipts()

    def test_resumed_challenge_checkpoint_does_not_gate_current_work(self):
        self.state["dialogue"]["0"] = "challenge"
        cli.atomic_write_json(self.root / "run_state.json", self.state)
        self.resume()
        self.process()
        self.assertTrue(self.state["slots"]["0"]["delivery_verified"], self.state["slots"]["0"])
        self.assertEqual(len(self.packets), 1)
        self.assertEqual(self.send.call_count, 1)

    def seed_delayed_first_receipt(self):
        # Isolate scheduling from the legacy dialogue gate: seed a real sender
        # receipt at the time a 120-second first-slot model run would finish.
        self.now += 120
        account = self.config["accounts"][0]
        sender_root = cli.private_run_directory(str(self.root / "sender-0"))
        result = cli.call_sender(
            ["--account", "first", "--state-dir", str(sender_root),
             "--grant-file", account["grant_file"], "--grant-sha256", account["grant_sha256"],
             "--transport-script", str(self.transport), "--full-rollup"],
            self.slots[0]["event_id"], "Check current fixture work.",
            source_callback=lambda: (True, "ok"),
        )
        self.assertTrue(result["delivery_verified"])
        self.state["slots"]["0"] = result
        cli.atomic_write_json(self.root / "run_state.json", self.state)

    def test_spacing_defer_resumes_with_real_eligibility_and_one_success(self):
        self.seed_delayed_first_receipt()
        self.now = self.slots[3]["due_epoch"]
        self.process()
        deferred = {"outcome": "deferred", "reason": "grant_min_interval", "delivery_verified": False}
        self.assertEqual(self.state["slots"]["3"], deferred)
        self.assertEqual(self.ledger()["attempted_count"], 1)
        self.assertEqual(self.ledger()["last_attempt_epoch"], self.started + 120)
        self.now += 119
        self.resume()
        self.process()
        self.assertEqual(self.state["slots"]["3"], deferred)
        self.assertEqual(len(self.packets), 2)
        self.assertEqual(self.ledger()["attempted_count"], 1)
        self.now += 1
        self.resume()
        self.process()
        self.assertTrue(self.state["slots"]["3"]["delivery_verified"], self.state["slots"]["3"])
        self.assertEqual(self.ledger()["attempted_count"], 2)
        self.assertEqual(self.ledger()["last_attempt_epoch"], self.started + 3720)
        self.assertEqual(self.ledger()["retained_event_ids"],
                         [self.slots[index]["event_id"] for index in (0, 3)])
        self.assertEqual(self.source_reader.call_count, 1)
        self.assertEqual(self.send.call_count, 4)
        self.resume()
        self.process()
        self.assertEqual(self.send.call_count, 4)
        self.assertEqual(len(self.capture.read_text().splitlines()), 2)
        self.assertEqual(self.state["started_at_epoch"], self.started)
        print("spacing: deferred at +3600 and +3719; delivered once at +3720; attempts=2")

    def test_spacing_defer_expires_at_original_slot_boundary(self):
        self.seed_delayed_first_receipt()
        self.now = self.slots[3]["due_epoch"]
        self.process()
        self.assertEqual(self.state["slots"]["3"]["reason"], "grant_min_interval")
        self.now += 1200
        # The next account is terminal so only the expired slot is under test.
        self.state["slots"]["4"] = {"outcome": "in_progress_hold", "delivery_verified": False}
        cli.atomic_write_json(self.root / "run_state.json", self.state)
        self.resume()
        self.process()
        self.assertEqual(self.state["slots"]["3"]["outcome"], "missed_slot")
        self.assertEqual(self.send.call_count, 2)
        self.assertEqual(self.ledger()["attempted_count"], 1)

    def test_only_unverified_spacing_defer_is_retryable(self):
        outcomes = [
            {"outcome": "in_progress_hold", "delivery_verified": False},
            {"outcome": "uncertain", "reason": "receipt_hold", "delivery_verified": False},
            {"outcome": "slot_failed_hold", "delivery_verified": False},
            *[{"outcome": "deferred", "reason": reason, "delivery_verified": False}
              for reason in ("grant_message_limit", "cooldown", "lock_contention_or_invalid_lock")],
            {"outcome": "deferred", "reason": "grant_min_interval", "delivery_verified": True},
        ]
        for outcome in outcomes:
            with self.subTest(outcome=outcome):
                self.state["slots"]["0"] = outcome
                cli.atomic_write_json(self.root / "run_state.json", self.state)
                self.resume()
                self.process()
                self.assertEqual(self.state["slots"]["0"], outcome)
        self.send.assert_not_called()
        self.assertEqual(self.packets, [])

    def test_spacing_defer_after_model_work_cannot_extend_slot_window(self):
        account = self.config["accounts"][0]
        path = Path(account["grant_file"])
        grant = json.loads(path.read_text())
        grant["min_interval_secs"] = 6000
        path.chmod(0o600)
        path.write_text(json.dumps(grant))
        path.chmod(0o400)
        account["grant_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.seed_delayed_first_receipt()
        self.now = self.slots[3]["due_epoch"] + 1100
        self.driver_delay = 101
        self.process()
        self.assertEqual(self.state["slots"]["3"]["outcome"], "missed_slot")
        self.assertEqual(self.now, self.slots[3]["due_epoch"] + 1201)
        self.assertEqual(self.ledger()["attempted_count"], 1)

    def test_uncertain_receipt_remains_terminal_and_holds_later_slots(self):
        self.transport.write_text(
            "#!/bin/sh\n"
            "echo attempted >> \"$DOT_CAPTURE_FILE\"\n"
            "echo prepared 0123456789abcdef0123456789abcdef\n"
            "read -r cmd\n"
            "exit 1\n"
        )
        self.process()
        self.assertEqual(self.state["slots"]["0"]["outcome"], "uncertain")
        self.assertIsNotNone(self.ledger()["pending_delivery"])
        self.resume()
        self.process()
        self.assertEqual(self.send.call_count, 1)
        self.now += 3600
        self.process()
        self.assertEqual(self.state["slots"]["3"]["reason"], "receipt_hold")
        self.assertEqual(self.ledger()["attempted_count"], 1)
        self.assertEqual(self.capture.read_text().splitlines(), ["attempted"])
