"""The stale-singleton reaper: it only acts on provably stale, own-host locks.

A coordinator run that ends by terminating Chrome can leave SingletonLock,
SingletonCookie and SingletonSocket behind, and the launcher then fails closed on
that profile forever. These tests pin the safety rules: act only when the lock
names this host, the holder pid is dead and no live process uses the profile; and
never delete - always rename to a recoverable .stale-<ts> name.
"""
import importlib.util
import os
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".claude/skills/dot-coordinator/scripts/reap_stale_singletons.py"
spec = importlib.util.spec_from_file_location("reaper", SCRIPT)
reaper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reaper)


class ReaperContractTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.profile = Path(self.tmp.name) / "profile"
        self.profile.mkdir()
        for name in reaper.NAMES:
            (self.profile / name).write_text("x")

    def tearDown(self):
        self.tmp.cleanup()

    def lock(self, host, pid):
        target = self.profile / "SingletonLock"
        if os.path.lexists(target):
            target.unlink()
        target.symlink_to(f"{host}-{pid}")

    def test_reaps_a_provably_stale_lock_and_never_deletes(self):
        self.lock(socket.gethostname(), 999999)          # this host, dead pid
        with patch.object(reaper, "pid_alive", return_value=False), \
             patch.object(reaper, "processes_on", return_value=[]):
            message = reaper.reap("acct", self.profile, apply=True)
        self.assertIn("provably stale", message)
        for name in reaper.NAMES:
            self.assertFalse(os.path.lexists(self.profile / name), name)
            stale = list(self.profile.glob(f"{name}.stale-*"))
            self.assertEqual(len(stale), 1, f"{name} must be renamed, not deleted: {stale}")

    def test_leaves_a_live_holder_alone(self):
        self.lock(socket.gethostname(), 4242)
        with patch.object(reaper, "pid_alive", return_value=True):
            message = reaper.reap("acct", self.profile, apply=True)
        self.assertIn("is alive", message)
        self.assertTrue(os.path.lexists(self.profile / "SingletonLock"))

    def test_leaves_a_foreign_host_lock_alone(self):
        self.lock("some-other-machine", 4242)
        message = reaper.reap("acct", self.profile, apply=True)
        self.assertIn("held by some-other-machine", message)
        self.assertTrue(os.path.lexists(self.profile / "SingletonLock"))

    def test_leaves_the_profile_alone_when_a_process_still_uses_it(self):
        self.lock(socket.gethostname(), 999999)
        with patch.object(reaper, "pid_alive", return_value=False), \
             patch.object(reaper, "processes_on", return_value=[123]):
            message = reaper.reap("acct", self.profile, apply=True)
        self.assertIn("use the profile", message)
        self.assertTrue(os.path.lexists(self.profile / "SingletonLock"))

    def test_dry_run_reports_without_touching_anything(self):
        self.lock(socket.gethostname(), 999999)
        with patch.object(reaper, "pid_alive", return_value=False), \
             patch.object(reaper, "processes_on", return_value=[]):
            message = reaper.reap("acct", self.profile, apply=False)
        self.assertIn("would rename", message)
        self.assertTrue(os.path.lexists(self.profile / "SingletonLock"))
        self.assertTrue(os.path.lexists(self.profile / "SingletonCookie"))

    def test_unrecognised_lock_target_is_left_untouched(self):
        target = self.profile / "SingletonLock"
        target.unlink()
        target.symlink_to("garbage-without-a-pid")
        message = reaper.reap("acct", self.profile, apply=True)
        self.assertIn("unrecognised", message)
        self.assertTrue(os.path.lexists(target))


if __name__ == "__main__":
    unittest.main()
