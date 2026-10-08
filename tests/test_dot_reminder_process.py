"""Trusted POSIX child supervision contract; never invokes model or browser."""
import importlib.util
import os
from pathlib import Path
import signal
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT/'.claude/skills/dot-portfolio-coordinator/scripts/reminder_process.py'


def load_process():
    spec = importlib.util.spec_from_file_location('reminder_process', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FiniteProcessTests(unittest.TestCase):
    def setUp(self):
        self.runner = load_process()

    def invoke(self, program, **kwargs):
        return self.runner.run([sys.executable, '-c', program], **kwargs)

    def test_natural_zero_with_exact_output(self):
        result = self.invoke('import sys; sys.stdout.write("out"); sys.stderr.write("err")', timeout=2)
        self.assertEqual(result['stdout'], b'out')
        self.assertEqual(result['stderr'], b'err')
        self.assertEqual(result['returncode'], 0)
        self.assertTrue(result['natural_exit'])
        self.assertTrue(result['cleanup_ok'])
        self.assertFalse(result['forced_cleanup'])

    def test_natural_nonzero_is_not_timeout(self):
        result = self.invoke('raise SystemExit(7)', timeout=2)
        self.assertEqual(result['returncode'], 7)
        self.assertTrue(result['natural_exit'])
        self.assertEqual(result['reason'], 'exited')

    def test_timeout_ignoring_term_is_finite_and_not_natural(self):
        start = time.monotonic()
        result = self.invoke('import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)', timeout=.3)
        self.assertLess(time.monotonic()-start, 3)
        self.assertEqual(result['reason'], 'timeout')
        self.assertFalse(result['natural_exit'])
        self.assertTrue(result['cleanup_ok'])

    def test_output_ceiling_and_plus_one(self):
        for stream in ['stdout', 'stderr']:
            for length in [1024, 1025]:
                with self.subTest(stream=stream, length=length):
                    result = self.invoke(f'import sys; sys.{stream}.write("x"*{length})', timeout=2, max_output=1024)
                    self.assertLessEqual(len(result['stdout'])+len(result['stderr']), 1024)
                    self.assertEqual(result['reason'], 'exited' if length==1024 else 'output_limit')
                    self.assertTrue(result['cleanup_ok'])

    def test_oversized_input_rejected_without_launch(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp)/'launched'
            with self.assertRaises(ValueError):
                self.invoke(f'open({str(marker)!r},"w").close()', input_bytes=b'x'*65, max_input=64)
            self.assertFalse(marker.exists())

    def test_simultaneous_stream_pressure_does_not_hang_stdin(self):
        start = time.monotonic()
        program = 'import os\nwhile True:\n os.write(1,b"x"*4096)\n os.write(2,b"y"*4096)\n'
        result = self.invoke(program, input_bytes=b'z'*65536, timeout=.5, max_output=8192)
        self.assertLess(time.monotonic()-start, 3)
        self.assertLessEqual(len(result['stdout'])+len(result['stderr']), 8192)
        self.assertEqual(result['reason'], 'output_limit')
        self.assertTrue(result['cleanup_ok'])

    def test_nested_child_pipe_holder_is_killed_and_never_delivery_eligible(self):
        with tempfile.TemporaryDirectory() as tmp:
            pidfile = Path(tmp)/'grandchild.pid'
            grandchild = f'import os,time; open({str(pidfile)!r},"w").write(str(os.getpid())); time.sleep(30)'
            child = f'import subprocess,sys,time; subprocess.Popen([sys.executable,"-c",{grandchild!r}]); time.sleep(30)'
            parent = f'import subprocess,sys,time; subprocess.Popen([sys.executable,"-c",{child!r}]); time.sleep(.2)'
            started = time.monotonic()
            result = self.invoke(parent, timeout=.5)
            self.assertLess(time.monotonic()-started, 3)
            self.assertTrue(pidfile.exists())
            self.assertTrue(result['forced_cleanup'])
            self.assertTrue(result['cleanup_ok'])
            self.assertNotEqual(result['reason'], 'exited')
            pid = int(pidfile.read_text())
            row = self.runner.snapshot(time.monotonic()+1).get(pid)
            self.assertTrue(row is None or row[2].startswith('Z'))

    def test_nonfinite_timeout_rejected_before_spawn(self):
        for value in [0, -1, float('nan'), float('inf')]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.invoke('pass', timeout=value)

class CleanupRegressionTests(unittest.TestCase):
    def setUp(self):
        self.runner = load_process()
        self.children = []
        self.popen = self.runner.subprocess.Popen

    def launch(self, *args, **kwargs):
        child = self.popen(*args, **kwargs)
        if args[0][0] == sys.executable:
            self.children.append(child)
        return child

    def tearDown(self):
        for child in self.children:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait(timeout=2)

    def test_observation_failure_still_stops_direct_child(self):
        from unittest.mock import patch
        with patch.object(self.runner.subprocess, 'Popen', side_effect=self.launch):
            with patch.object(self.runner, 'snapshot', side_effect=RuntimeError('observer unavailable')):
                result = self.runner.run([sys.executable, '-c', 'import time; time.sleep(30)'], timeout=.5)
        self.assertIsNotNone(self.children[0].poll(), 'observer failure leaked direct child')
        self.assertFalse(result['cleanup_ok'])

    def test_cancellation_propagates_after_child_cleanup(self):
        from unittest.mock import patch
        with patch.object(self.runner.subprocess, 'Popen', side_effect=self.launch):
            with patch.object(self.runner, 'snapshot', side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt):
                    self.runner.run([sys.executable, '-c', 'import time; time.sleep(30)'], timeout=.5)
        self.assertIsNotNone(self.children[0].poll(), 'cancellation leaked direct child')

    def test_exited_leader_group_member_is_stopped(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            pidfile = Path(tmp)/'pid'
            child_code = 'import time; time.sleep(30)'
            parent_code = f'import subprocess,sys; p=subprocess.Popen([sys.executable,"-c",{child_code!r}],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,stdin=subprocess.DEVNULL); open({str(pidfile)!r},"w").write(str(p.pid))'
            original = self.runner.snapshot
            first, fixture_identity = True, None
            def delayed_snapshot(deadline):
                nonlocal first, fixture_identity
                if first:
                    first = False
                    until = time.monotonic()+1
                    while not pidfile.exists() and time.monotonic() < until:
                        time.sleep(.005)
                    time.sleep(.05)
                table = original(deadline)
                if pidfile.exists() and pidfile.read_text():
                    row = table.get(int(pidfile.read_text()))
                    if row is not None and fixture_identity is None:
                        fixture_identity = row[3]
                return table
            pid = None
            try:
                with patch.object(self.runner, 'snapshot', side_effect=delayed_snapshot):
                    result = self.runner.run([sys.executable, '-c', parent_code], timeout=2)
                pid = int(pidfile.read_text())
                row = original(time.monotonic()+1).get(pid)
                self.assertTrue(row is None or row[2].startswith('Z'), 'orphan remained in owned group')
                self.assertTrue(result['forced_cleanup'])
                self.assertTrue(result['cleanup_ok'])
            finally:
                if pid is None and pidfile.exists():
                    pid = int(pidfile.read_text())
                if pid is not None:
                    row = original(time.monotonic()+1).get(pid)
                    if row is not None and row[3] == fixture_identity and not row[2].startswith('Z'):
                        self.runner.kill_observed(pid, fixture_identity, time.monotonic()+1)

    def test_expired_snapshot_never_returns_empty_success(self):
        with self.assertRaises(TimeoutError):
            self.runner.snapshot(time.monotonic()-1)

    def test_observed_child_escaping_group_is_stopped(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            ready, go, escaped = [Path(tmp)/name for name in ('ready', 'go', 'escaped')]
            child_code = f'import os,time; from pathlib import Path; Path({str(ready)!r}).write_text(str(os.getpid()))\nwhile not Path({str(go)!r}).exists(): time.sleep(.005)\nos.setsid(); Path({str(escaped)!r}).touch(); time.sleep(30)'
            parent_code = f'import subprocess,sys,time; subprocess.Popen([sys.executable,"-c",{child_code!r}]); time.sleep(30)'
            original = self.runner.snapshot
            fixture_identity = None
            def release_after_observation(deadline):
                nonlocal fixture_identity
                table = original(deadline)
                if ready.exists() and ready.read_text() and int(ready.read_text()) in table:
                    fixture_identity = table[int(ready.read_text())][3]
                    go.touch()
                return table
            pid = None
            try:
                with patch.object(self.runner, 'snapshot', side_effect=release_after_observation):
                    result = self.runner.run([sys.executable, '-c', parent_code], timeout=.4)
                pid = int(ready.read_text())
                self.assertTrue(escaped.exists(), 'fixture never escaped its group')
                row = original(time.monotonic()+1).get(pid)
                self.assertTrue(row is None or row[2].startswith('Z'), 'observed escaped child survived')
                self.assertTrue(result['cleanup_ok'])
                self.assertTrue(result['forced_cleanup'])
            finally:
                if pid is None and ready.exists() and ready.read_text():
                    pid = int(ready.read_text())
                if pid is not None:
                    row = original(time.monotonic()+1).get(pid)
                    if row is not None and row[3] == fixture_identity and not row[2].startswith('Z'):
                        self.runner.kill_observed(pid, fixture_identity, time.monotonic()+1)

    def test_selector_creation_failure_still_stops_child(self):
        from unittest.mock import patch
        with patch.object(self.runner.subprocess, 'Popen', side_effect=self.launch):
            with patch.object(self.runner.selectors, 'DefaultSelector', side_effect=OSError('selector unavailable')):
                result = self.runner.run([sys.executable, '-c', 'import time; time.sleep(30)'], timeout=.5)
        self.assertIsNotNone(self.children[0].poll())
        self.assertNotEqual(result['reason'], 'exited')

    def test_killpg_race_does_not_skip_individual_cleanup(self):
        from unittest.mock import patch
        with patch.object(self.runner.subprocess, 'Popen', side_effect=self.launch):
            with patch.object(self.runner.os, 'killpg', side_effect=ProcessLookupError):
                result = self.runner.run([sys.executable, '-c', 'import time; time.sleep(30)'], timeout=.1)
        self.assertIsNotNone(self.children[0].poll())
        self.assertTrue(result['cleanup_ok'])

    def test_integer_output_limit_required(self):
        for limit in (float('inf'), float('nan'), 1.5):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                self.runner.run([sys.executable, '-c', 'pass'], max_output=limit)

    def test_reused_observed_pid_is_not_signaled(self):
        from unittest.mock import patch
        observer, kill_observed = self.runner.snapshot, self.runner.kill_observed
        unrelated_pid = os.getpid()
        observations, unsafe_signals = 0, []
        def replaced_identity(deadline):
            nonlocal observations
            table = observer(deadline)
            observations += 1
            if self.children:
                group = table[unrelated_pid][1]
                owner = self.children[0].pid if observations == 1 else 1
                table[unrelated_pid] = (owner, group, 'S', b'old' if observations == 1 else b'new')
            return table
        def guarded_identity(pid, identity, deadline):
            if pid == unrelated_pid:
                unsafe_signals.append(pid)
                raise AssertionError('attempt to signal reused identity')
            return kill_observed(pid, identity, deadline)
        with patch.object(self.runner.subprocess, 'Popen', side_effect=self.launch):
            with patch.object(self.runner, 'snapshot', side_effect=replaced_identity):
                with patch.object(self.runner, 'kill_observed', side_effect=guarded_identity):
                    result = self.runner.run([sys.executable, '-c', 'import time; time.sleep(30)'], timeout=.1)
        self.assertGreater(observations, 1)
        self.assertEqual(unsafe_signals, [])
        self.assertTrue(result['cleanup_ok'])

    def test_unsupported_identity_adapter_fails_closed(self):
        from unittest.mock import patch
        with patch.object(self.runner.subprocess, 'Popen', side_effect=self.launch):
            with patch.object(self.runner.sys, 'platform', 'unsupported'):
                result = self.runner.run([sys.executable, '-c', 'import time; time.sleep(30)'], timeout=.1)
        self.assertIsNotNone(self.children[0].poll())
        self.assertFalse(result['cleanup_ok'])
        self.assertFalse(result['natural_exit'])


class LinuxIdentityTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform.startswith('linux'), 'Linux pidfd contract')
    def test_pidfd_is_closed_and_reused_identity_is_not_signaled(self):
        from unittest.mock import patch
        runner = load_process()
        with patch.object(runner.os, 'pidfd_open', return_value=123) as opened:
            with patch.object(runner, 'snapshot', return_value={7: (1, 1, 'S', b'new')}):
                with patch.object(runner.signal, 'pidfd_send_signal') as sent:
                    with patch.object(runner.os, 'close') as closed:
                        runner.kill_observed(7, b'old', time.monotonic()+1)
        opened.assert_called_once_with(7)
        sent.assert_not_called()
        closed.assert_called_once_with(123)


class DarwinIdentityTests(unittest.TestCase):
    def setUp(self):
        import ctypes
        from unittest.mock import Mock
        self.runner = load_process()
        self.ctypes = ctypes
        self.lib = Mock()
        self.rows = {os.getpid(): (os.getppid(), os.getpgrp(), 2, 123456, 987654)}
        def list_pids(buffer, capacity):
            for index, pid in enumerate(self.rows):
                buffer[index] = pid
            return len(self.rows)
        def read_pid(pid, flavor, argument, pointer, size):
            self.assertEqual((flavor, argument), (3, 0))
            row = pointer._obj
            row.pid = pid
            row.ppid, row.pgid, row.status, row.start_sec, row.start_usec = self.rows[pid]
            return self.ctypes.sizeof(row)
        self.lib.proc_listallpids.side_effect = list_pids
        self.lib.proc_pidinfo.side_effect = read_pid

    def snapshot(self, deadline=None):
        from unittest.mock import patch
        with patch.object(self.runner.sys, 'platform', 'darwin'):
            with patch.object(self.runner.ctypes, 'CDLL', return_value=self.lib):
                return self.runner.snapshot(time.monotonic()+1 if deadline is None else deadline)

    def test_darwin_abi_offsets_and_identity_precision(self):
        self.assertEqual(self.ctypes.sizeof(self.runner.BSD), 136)
        self.assertEqual(self.runner.BSD.start_sec.offset, 120)
        self.assertEqual(self.runner.BSD.start_usec.offset, 128)
        self.assertEqual(self.snapshot()[os.getpid()], (os.getppid(), os.getpgrp(), 'S', (123456, 987654)))
        self.lib.proc_pidinfo.assert_called_once()

    def test_zombie_status_is_distinct(self):
        self.rows[999999] = (os.getpid(), os.getpgrp(), 5, 123456, 1)
        self.assertEqual(self.snapshot()[999999][2], 'Z')

    def test_short_or_denied_identity_is_not_empty_success(self):
        for size in (0, 135):
            with self.subTest(size=size):
                self.lib.proc_pidinfo.side_effect = None
                self.lib.proc_pidinfo.return_value = size
                self.ctypes.set_errno(13)
                with self.assertRaises(OSError):
                    self.snapshot()

    def test_vanished_process_is_skipped(self):
        original = self.lib.proc_pidinfo.side_effect
        self.rows[999999] = (os.getpid(), os.getpgrp(), 2, 123456, 1)
        def vanish(pid, *args):
            if pid == 999999:
                self.ctypes.set_errno(3)
                return 0
            return original(pid, *args)
        self.lib.proc_pidinfo.side_effect = vanish
        self.assertNotIn(999999, self.snapshot())

    def test_full_or_failed_enumeration_is_rejected(self):
        self.lib.proc_listallpids.side_effect = None
        for count in (0, -1, 32768, 32769):
            with self.subTest(count=count):
                self.lib.proc_listallpids.return_value = count
                with self.assertRaises((OSError, ValueError)):
                    self.snapshot()

    def test_wrong_self_abi_and_invalid_microseconds_are_rejected(self):
        for row in ((0, os.getpgrp(), 2, 123456, 1), (os.getppid(), os.getpgrp(), 2, 123456, 1000000)):
            with self.subTest(row=row):
                self.rows[os.getpid()] = row
                with self.assertRaises(ValueError):
                    self.snapshot()

    def test_deadline_covers_enumeration_and_each_identity(self):
        with self.assertRaises(TimeoutError):
            self.snapshot(time.monotonic()-1)
        self.lib.proc_pidinfo.assert_not_called()

    def test_mac_identity_reuse_prevents_signal(self):
        from unittest.mock import patch
        for fresh, expected in (((1, 1, 'S', (4, 6)), False), ((1, 1, 'S', (4, 5)), True), (None, False)):
            with self.subTest(fresh=fresh), patch.object(self.runner.sys, 'platform', 'darwin'):
                with patch.object(self.runner, 'snapshot', return_value={} if fresh is None else {123: fresh}):
                    with patch.object(self.runner.os, 'kill') as kill:
                        self.runner.kill_observed(123, (4, 5), time.monotonic()+1)
                        self.assertEqual(kill.called, expected)
                        if expected:
                            kill.assert_called_once_with(123, signal.SIGKILL)


if __name__ == '__main__':
    unittest.main()
