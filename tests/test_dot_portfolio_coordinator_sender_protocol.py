import copy
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
