import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SKILL_DIR = Path(__file__).resolve().parent.parent / ".claude/skills/dot-portfolio-coordinator"
sys.path.insert(0, str(SKILL_DIR / "scripts"))
from modules.sender_protocol import NotificationBindingManager, SenderProtocolError


class TestNotificationBindingManager(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "bindings.json"
        self.manager = NotificationBindingManager(None, str(self.path))
        self.args = dict(
            control_record_id="control", action_id="action", attempt_id="attempt",
            account="account", event_id="event", kind="status",
            message_sha256="a" * 64,
            task_key={"repository": "example-org/project", "bead_id": "item"},
            grant_version="v1", control_entry_digest="b" * 64,
        )
        self.ref = "control/action/attempt"

    def test_corrupt_binding_store_rejects_load_read_and_write_without_reset(self):
        self.manager.register_binding(**self.args)
        valid = json.loads(self.path.read_text())
        corrupt = ["{broken", "null", "[]", json.dumps({self.ref: {}})]
        for field, value in (("task_key", []), ("event_id", None),
                             ("control_record_id", "wrong"), ("message_sha256", "invalid")):
            bad = copy.deepcopy(valid); bad[self.ref][field] = value
            corrupt.append(json.dumps(bad))
        for raw in corrupt:
            with self.subTest(raw=raw):
                self.path.write_text(raw)
                before = self.path.read_bytes()
                state = copy.deepcopy(self.manager.bindings)
                with self.assertRaises(SenderProtocolError):
                    NotificationBindingManager(None, str(self.path))
                for operation in (lambda: self.manager.resolve_notification(self.ref),
                                  lambda: self.manager.register_binding(**dict(self.args, action_id="new"))):
                    with self.assertRaises(SenderProtocolError):
                        operation()
                    self.assertEqual(self.path.read_bytes(), before)
                    self.assertEqual(self.manager.bindings, state)
        self.path.write_text(json.dumps(valid))
        self.assertEqual(NotificationBindingManager(None, str(self.path)).resolve_notification(self.ref), valid[self.ref])

    def test_unreadable_bindings_reject_without_changing_bytes(self):
        self.manager.register_binding(**self.args)
        before = self.path.read_bytes()
        with patch("builtins.open", side_effect=PermissionError("fixture denied")):
            with self.assertRaises(SenderProtocolError):
                NotificationBindingManager(None, str(self.path))
            with self.assertRaises(SenderProtocolError):
                self.manager.register_binding(**dict(self.args, action_id="new"))
        self.assertEqual(self.path.read_bytes(), before)

    def test_prewrite_reload_rejects_sequential_stale_manager_conflict(self):
        stale = NotificationBindingManager(None, str(self.path))
        original = self.manager.register_binding(**self.args)
        before = self.path.read_bytes()
        with self.assertRaises(SenderProtocolError):
            stale.register_binding(**dict(self.args, event_id="changed"))
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(stale.resolve_notification(self.ref), original)

    def test_identical_registration_preserves_timestamp_state_and_file(self):
        with patch("modules.sender_protocol.time.strftime", return_value="first"):
            original = self.manager.register_binding(**self.args)
        before = self.path.read_bytes()
        state = copy.deepcopy(self.manager.bindings)
        with patch("modules.sender_protocol.time.strftime", return_value="later"), patch.object(self.manager, "_save") as save:
            replay = self.manager.register_binding(**self.args)
        self.assertEqual(replay, original)
        self.assertEqual(self.manager.bindings, state)
        self.assertEqual(self.path.read_bytes(), before)
        save.assert_not_called()
        reloaded = NotificationBindingManager(None, str(self.path))
        self.assertEqual(reloaded.register_binding(**self.args), original)
        self.assertEqual(self.path.read_bytes(), before)

    def test_changed_immutable_fields_reject_before_mutation(self):
        self.manager.register_binding(**self.args)
        before = self.path.read_bytes()
        state = copy.deepcopy(self.manager.bindings)
        for field in ("account", "event_id", "kind", "message_sha256", "task_key", "grant_version", "control_entry_digest"):
            with self.subTest(field=field):
                changed = copy.deepcopy(self.args)
                changed[field] = {"repository": "example-org/other"} if field == "task_key" else "changed"
                with patch.object(self.manager, "_save") as save:
                    with self.assertRaises(SenderProtocolError):
                        self.manager.register_binding(**changed)
                save.assert_not_called()
                self.assertEqual(self.manager.bindings, state)
                self.assertEqual(self.path.read_bytes(), before)

    def test_nested_inputs_and_returned_bindings_do_not_alias_state(self):
        manager = NotificationBindingManager(None)
        original = copy.deepcopy(self.args["task_key"])
        result = manager.register_binding(**self.args)
        self.args["task_key"]["bead_id"] = "input-mutated"
        self.assertEqual(manager.resolve_notification(self.ref)["task_key"], original)
        result["task_key"]["bead_id"] = "result-mutated"
        resolved = manager.resolve_notification(self.ref)
        self.assertEqual(resolved["task_key"], original)
        resolved["task_key"]["bead_id"] = "resolve-mutated"
        self.assertEqual(manager.resolve_notification(self.ref)["task_key"], original)
        replay_args = dict(self.args, task_key=original)
        replay = manager.register_binding(**replay_args)
        replay["task_key"]["bead_id"] = "replay-mutated"
        self.assertEqual(manager.resolve_notification(self.ref)["task_key"], original)


if __name__ == "__main__":
    unittest.main()
