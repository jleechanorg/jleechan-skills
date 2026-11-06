"""Offline behavior of the explicitly approved stateless coordinator."""
import fcntl, hashlib
from pathlib import Path
from unittest.mock import patch
import unittest
from tests import test_simple_dot_ping as harness

class StatelessCoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.f = harness.LauncherExecutionTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
    def invoke(self):
        # Old fixture names are retained solely to exercise legacy inputs.
        with patch.object(harness.PING, 'STATE', self.f.state, create=True), patch.object(harness.PING, 'STOP', self.f.state / 'STOP', create=True):
            def spawn(command, **options):
                self.child_env = options["env"]
                return harness.FakePiProcess()
            return self.f.invoke(on_spawn=spawn)
    def test_old_stop_pending_and_corrupt_ledger_are_not_consumed_or_changed(self):
        self.f.state.mkdir()
        artifacts = {'STOP':b'operator', 'send-old.pending':b'unknown', 'state.json':b'corrupt'}
        for name,data in artifacts.items(): (self.f.state/name).write_bytes(data)
        result,spawned=self.invoke()
        self.assertEqual(result,0)
        self.assertNotIn('COORDINATOR_PENDING_FILE',self.child_env)
        for name,data in artifacts.items(): self.assertEqual((self.f.state/name).read_bytes(),data)
    def test_shared_flock_is_not_acquired_or_replaced(self):
        lockdir=self.f.lock_base/'dot-profile-locks';lockdir.mkdir(parents=True)
        lock=lockdir/(hashlib.sha256(str(self.f.profile).encode()).hexdigest()[:16]+'.lock')
        with lock.open('a') as held:
            fcntl.flock(held,fcntl.LOCK_EX|fcntl.LOCK_NB)
            inode=lock.stat().st_ino
            self.assertEqual(self.invoke()[0],0)
            self.assertEqual(lock.stat().st_ino,inode)
    def test_state_directory_is_not_created(self):
        self.assertEqual(self.invoke()[0],0)
        self.assertFalse(self.f.state.exists())
    def test_chrome_singleton_guard_remains(self):
        (self.f.profile/'SingletonLock').symlink_to(self.f.home/'missing')
        with self.assertRaisesRegex(harness.PING.Blocked,'SingletonLock'): self.invoke()
if __name__=='__main__': unittest.main()
