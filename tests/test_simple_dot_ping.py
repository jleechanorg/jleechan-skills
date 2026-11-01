"""Fail-closed contract tests for the scheduler-bound Pi coordinator launcher."""
import importlib.util
import os
import socket
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
from contextlib import ExitStack, redirect_stderr, redirect_stdout
import fcntl
import hashlib
import io
import json
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / '.claude/skills/dot-coordinator/scripts/ping-dots.py'
SPEC = importlib.util.spec_from_file_location('dot_coordinator_launcher', SCRIPT)
PING = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PING)


class LauncherContractTests(unittest.TestCase):
    def test_account_is_mandatory_and_rejects_injection(self):
        with patch.object(sys, 'argv', ['ping-dots.py']):
            with self.assertRaises(SystemExit):
                PING.main()
        with patch.object(sys, 'argv', ['ping-dots.py', '--account', '../other']):
            with self.assertRaises(PING.Blocked):
                PING.main()

    def test_missing_identity_binding_fails_before_config_or_process_launch(self):
        with patch.dict(os.environ, {'DOT_EXPECTED_IDENTITY_SHA256': ''}):
            with patch.object(sys, 'argv', ['ping-dots.py', '--account', 'alpha']):
                with self.assertRaisesRegex(PING.Blocked, 'identity binding'):
                    PING.main()

    def test_chrome_is_headless_on_every_platform(self):
        src = SCRIPT.read_text()
        self.assertNotIn("if not os.environ.get('DISPLAY'): mcp_args.append('--headless')", src)
        self.assertIn("mcp_args += ['--headless', '--chromeArg=--password-store=gnome-libsecret']", src)
        self.assertIn("mcp_args += ['--headless', '--chromeArg=--password-store=keychain']", src)
        self.assertIn('headless on every host', (ROOT / '.claude/skills/dot-coordinator/SKILL.md').read_text())

    def test_dangling_singleton_lock_is_detected(self):
        import tempfile
        with tempfile.TemporaryDirectory(dir='/tmp') as temp:
            profile = Path(temp)
            (profile / 'SingletonLock').symlink_to(profile / 'missing-target')
            self.assertFalse((profile / 'SingletonLock').exists())
            self.assertTrue(os.path.lexists(profile / 'SingletonLock'))
            self.assertIn("os.path.lexists(profile / 'SingletonLock')", SCRIPT.read_text())



    def test_scheduler_wrapper_is_thin_and_does_not_choose_account(self):
        wrapper = (SCRIPT.parent / 'dot-coordinator-wrapper.sh').read_text()
        self.assertIn('exec python3', wrapper)
        self.assertNotIn('--account', wrapper)
        self.assertNotIn('rotation', wrapper)


class FakePiProcess:
    def __init__(self, returncode=0):
        self.returncode = returncode
        self.pid = 2_000_000_000
    def poll(self): return self.returncode
    def communicate(self, timeout): return ('agent result', '')
    def terminate(self): self.returncode = -15
    def wait(self, timeout=None): return self.returncode


class LauncherExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir='/tmp')
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.profile = self.home / 'profile'
        (self.profile / 'Default').mkdir(parents=True)
        self.state = self.home / 'state'
        self.lock = self.home / 'coordinator.lock'
        self.lock_base = self.home / 'locks'
        self.config = self.home / 'dot.json'
        self.config.write_text(json.dumps({'accounts': {'alpha': {
            'user_data_dir': str(self.profile), 'profile_directory': 'Default',
            'url': 'https://example.invalid/chat'}}}))
        self.chrome = self.home / 'chrome'
        self.chrome.touch()
        self.pi = self.home / 'pi'
        self.pi.touch()
        self.node_home = self.home / '.nvm/versions/node/v22.22.0'
        (self.node_home / 'bin').mkdir(parents=True)
        (self.node_home / 'bin/node').touch()
        self.mcp = self.node_home / 'lib/node_modules/chrome-devtools-mcp/build/src/bin/chrome-devtools-mcp.js'
        self.mcp.parent.mkdir(parents=True)
        self.mcp.touch()
        (self.node_home / 'lib/node_modules/chrome-devtools-mcp/package.json').write_text(json.dumps({'version': '1.6.0'}))
        self.pi_config = self.home / '.pi/agent'
        self.pi_config.mkdir(parents=True)
        (self.pi_config / 'mcp.json').write_text(json.dumps({'mcpServers': {'unrelated': {'command': 'no-start'}}}))
        self.env = {
            'HOME': str(self.home), 'DOT_EXPECTED_IDENTITY_SHA256': 'a' * 64,
            'DOT_CONFIG_FILE': str(self.config), 'DOT_CHROME_BIN': str(self.chrome),
            'CHROME_DEVTOOLS_MCP_JS': str(self.mcp), 'PI_BIN': str(self.pi),
            'PI_CODING_AGENT_DIR': str(self.pi_config), 'COORDINATOR_STATE_DIR': str(self.state),
            'COORDINATOR_LOCK_FILE': str(self.lock), 'DOT_LOCK_BASE': str(self.lock_base),
            'DISPLAY': ':9', 'PATH': str(self.node_home / 'bin') + os.pathsep + os.environ.get('PATH', ''),
        }

    def invoke(self, fake_proc=None, on_spawn=None):
        spawned = {}
        def spawn(command, **options):
            spawned['command'] = command
            spawned['mcp'] = json.loads((Path(options['cwd']) / '.pi/mcp.json').read_text())
            if on_spawn: return on_spawn(command, **options)
            return fake_proc or FakePiProcess()
        with ExitStack() as stack:
            stack.enter_context(patch.object(PING.Path, 'home', return_value=self.home))
            stack.enter_context(patch.object(PING, 'STATE', self.state, create=True))
            stack.enter_context(patch.object(PING, 'STOP', self.state / 'STOP', create=True))
            stack.enter_context(patch.dict(os.environ, self.env, clear=False))
            stack.enter_context(patch.object(PING.subprocess, 'check_output', return_value=''))
            stack.enter_context(patch.object(PING.subprocess, 'Popen', side_effect=spawn))
            stack.enter_context(patch.object(sys, 'argv', ['ping-dots.py', '--account', 'alpha']))
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                result = PING.main()
        return result, spawned

    def test_launcher_uses_owned_mcp_with_isolated_global_config(self):
        result, spawned = self.invoke()
        self.assertEqual(result, 0)
        servers = spawned['mcp']['mcpServers']
        self.assertFalse(servers['unrelated']['enabled'])
        browser = servers['dot_browser']
        self.assertEqual(browser['exposure'], 'direct')
        self.assertEqual(browser['command'], str(self.node_home / 'bin/node'))
        self.assertIn(str(self.mcp), browser['args'])
        self.assertIn('--userDataDir=' + str(self.profile.absolute()), browser['args'])
        self.assertFalse({'--provider', '--model'} & set(spawned['command']))

    def test_no_attempt_ledger_or_global_review_lock_is_created(self):
        def agent(command, **options):
            self.assertNotIn('COORDINATOR_ATTEMPT_FILE', options['env'])
            self.assertNotIn('COORDINATOR_PENDING_FILE', options['env'])
            return FakePiProcess()
        self.invoke(on_spawn=agent)
        self.assertFalse(self.lock.exists())
        self.assertEqual(list(self.state.glob('attempt-*')), [])

    def test_configured_cli_prefix_is_literal_argv(self):
        prefix = ['--thinking', 'medium', 'literal spaces; $HOME $(never-run)']
        self.env['COORDINATOR_CLI_ARGS'] = json.dumps(prefix)
        _, spawned = self.invoke()
        self.assertEqual(spawned['command'][:1 + len(prefix)], [str(self.pi), *prefix])

    def test_invalid_cli_prefix_is_rejected_before_spawn(self):
        for value in ('"--thinking medium"', '{}', '[4]', '["bad\\u0000arg"]'):
            with self.subTest(value=value):
                self.env['COORDINATOR_CLI_ARGS'] = value
                with self.assertRaisesRegex(PING.Blocked, 'CLI arguments'):
                    self.invoke()




    def test_timeout_terminates_pi_and_preserves_agent_owned_marker(self):
        class TimedOut(FakePiProcess):
            def __init__(self): self.returncode, self.pid = None, 2_000_000_000
            # The launcher streams Pi to a log file and waits on the process, so the
            # timeout contract lives on wait() rather than communicate().
            def wait(self, timeout=None): raise subprocess.TimeoutExpired('pi', timeout)
            def terminate(self): self.returncode = -15
        old_timeout = PING.TIMEOUT
        self.addCleanup(setattr, PING, 'TIMEOUT', old_timeout)
        PING.TIMEOUT = 1
        self.state.mkdir()
        pending = self.state / ('send-' + hashlib.sha256(b'alpha').hexdigest()[:16] + '.pending')
        pending.write_text('private send intent')
        process = TimedOut()
        with self.assertRaisesRegex(PING.Blocked, 'deadline'):
            self.invoke(process)
        self.assertEqual(process.returncode, -15)
        self.assertEqual(pending.read_text(), 'private send intent')

    def test_sigterm_cleans_owned_pi_process_group_without_state_lock(self):
        ready, cleaned = self.home / 'child.ready', self.home / 'child.cleaned'
        child = self.home / 'child.py'
        child.write_text('''import fcntl, os, signal, time
from pathlib import Path
def cleanup(*_):
    Path(os.environ["DOT_CHILD_CLEANED_FILE"]).write_text("cleaned")
    raise SystemExit
signal.signal(signal.SIGTERM, cleanup)
Path(os.environ["DOT_CHILD_READY_FILE"]).write_text("ready")
time.sleep(60)
''')
        self.pi.write_text(f'''#!{sys.executable}
import os, subprocess, sys, time
from pathlib import Path
child = subprocess.Popen([sys.executable, {str(child)!r}])
Path(os.environ["DOT_CHILD_PID_FILE"]).write_text(str(child.pid))
time.sleep(60)
''')
        self.pi.chmod(0o755)
        profile_lock = self.lock_base / 'dot-profile-locks' / (hashlib.sha256(str(self.profile.absolute()).encode()).hexdigest()[:16] + '.lock')
        env = dict(os.environ, **self.env, DOT_TEST_LOCK_FILE=str(profile_lock), DOT_CHILD_SCRIPT=str(child),
                   DOT_CHILD_PID_FILE=str(self.home / 'child.pid'),
                   DOT_CHILD_READY_FILE=str(ready), DOT_CHILD_CLEANED_FILE=str(cleaned))
        harness = f'''import importlib.util, sys
spec = importlib.util.spec_from_file_location("dot_launcher", {str(SCRIPT)!r})
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.GRACE = 0.4
sys.argv = [{str(SCRIPT)!r}, "--account", "alpha"]
module.main()
'''
        launcher = subprocess.Popen([sys.executable, '-c', harness], env=env,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 5
            while not ready.exists() and time.monotonic() < deadline:
                time.sleep(.02)
            self.assertTrue(ready.exists(), 'dummy owned child did not start')
            launcher.terminate()
            launcher.communicate(timeout=5)
            self.assertEqual(launcher.returncode, 128 + PING.signal.SIGTERM)
            self.assertEqual(cleaned.read_text(), 'cleaned')
        finally:
            if launcher.poll() is None: launcher.kill()
            launcher.wait()
            launcher.stdout.close()
            launcher.stderr.close()

    def test_nonzero_exit_preserves_agent_owned_marker(self):
        self.state.mkdir()
        pending = self.state / ('send-' + hashlib.sha256(b'alpha').hexdigest()[:16] + '.pending')
        pending.write_text('private send intent')
        with self.assertRaisesRegex(PING.Blocked, 'verify delivery before any retry'):
            self.invoke(FakePiProcess(returncode=7))
        self.assertEqual(pending.read_text(), 'private send intent')




    def _plant_singleton(self, pid):
        lock = self.profile / 'SingletonLock'
        lock.symlink_to(f'{socket.gethostname()}-{pid}')
        (self.profile / 'SingletonCookie').symlink_to('cookie-value')
        (self.profile / 'SingletonSocket').symlink_to(str(self.home / 'sock'))
        return lock

    def test_dead_singleton_blocks_names_the_files_and_is_never_deleted(self):
        self._plant_singleton(9_000_000_001)  # never a live pid
        with self.assertRaises(PING.Blocked) as caught:
            self.invoke()
        message = str(caught.exception)
        for name in ('SingletonLock', 'SingletonCookie', 'SingletonSocket'):
            self.assertIn(str(self.profile / name), message)
            self.assertTrue(os.path.lexists(self.profile / name), f'{name} must survive')
        # A dead PID alone is never sufficient reason to remove the singletons.
        self.assertIn('verify', message)
        self.assertIn('uncertain', message)
        self.assertNotIn('if its process is dead', message)

    def test_live_singleton_blocks_without_deleting(self):
        lock = self._plant_singleton(os.getpid())
        with self.assertRaisesRegex(PING.Blocked, 'SingletonLock'):
            self.invoke()
        self.assertTrue(os.path.lexists(lock))

class PiLogRetentionTests(unittest.TestCase):
    """The retained Pi transcript must be private and redacted end-to-end."""

    def _run(self, fake_factory):
        case = LauncherExecutionTests('run')
        case.setUp()
        self.addCleanup(case.doCleanups)
        case.invoke(on_spawn=fake_factory)
        logs = sorted(Path(tempfile.gettempdir()).glob('dot-coordinator-pi-alpha-*.log'),
                      key=lambda item: item.stat().st_mtime)
        self.assertTrue(logs, 'the launcher must retain a Pi log')
        return logs[-1]

    def test_completed_run_keeps_a_private_redacted_log(self):
        expected = 'a' * 64  # matches DOT_EXPECTED_IDENTITY_SHA256 in the harness env

        def spawn(command, **options):
            out = options['stdout']
            child_fd = os.dup(out if isinstance(out, int) else out.fileno())
            os.write(child_fd, f'prompt {expected}\nagent step 1\n'.encode())
            os.close(child_fd)

            class Done(FakePiProcess):
                def __init__(self):
                    super().__init__(returncode=0)

                def wait(self, timeout=None):
                    return 0

            return Done()

        log = self._run(spawn)
        self.assertEqual(log.stat().st_mode & 0o777, 0o600)
        text = log.read_text()
        self.assertNotIn(expected, text)
        self.assertIn('[identity redacted]', text)
        self.assertIn('agent step 1', text)

class PiLogInterruptTests(unittest.TestCase):
    """An interrupt must still stop the group and redact the retained log."""

    def test_keyboard_interrupt_finalizes_after_stopping_the_child(self):
        expected = 'a' * 64  # matches DOT_EXPECTED_IDENTITY_SHA256 in the harness env
        written = {}

        class Interrupted(FakePiProcess):
            def __init__(self): self.returncode, self.pid = None, 2_000_000_002
            def wait(self, timeout=None):
                if written.get('fd') is not None:
                    os.write(written['fd'], (f'prompt {expected}\n').encode())
                    os.close(written['fd'])
                    written['fd'] = None
                raise KeyboardInterrupt()
            def terminate(self): self.returncode = -15
            def poll(self): return self.returncode

        def spawn(command, **options):
            # The launcher closes its own descriptor right after spawn, so the child
            # emulation holds its own duplicate, exactly as a real child would.
            out = options['stdout']
            written['fd'] = os.dup(out if isinstance(out, int) else out.fileno())
            return Interrupted()

        case = LauncherExecutionTests('run')
        case.setUp()
        self.addCleanup(case.doCleanups)
        with self.assertRaises(KeyboardInterrupt):
            case.invoke(on_spawn=spawn)
        logs = sorted(Path(tempfile.gettempdir()).glob('dot-coordinator-pi-alpha-*.log'),
                      key=lambda item: item.stat().st_mtime)
        self.assertTrue(logs, 'the retained log must exist after an interrupt')
        self.assertNotIn(expected, logs[-1].read_text())







class PinnedMcpSelectionTests(unittest.TestCase):
    """The launcher must pick the Node 22 tree that actually carries the pinned MCP."""

    def _node_tree(self, root, version, mcp_version=None):
        bin_dir = root / f'node-{version}' / 'bin'
        bin_dir.mkdir(parents=True)
        if mcp_version is None:
            return bin_dir
        mcp_js = bin_dir.parent / 'lib/node_modules/chrome-devtools-mcp/build/src/bin/chrome-devtools-mcp.js'
        mcp_js.parent.mkdir(parents=True)
        mcp_js.write_text('#!/usr/bin/env node\n', encoding='utf-8')
        pkg = bin_dir.parent / 'lib/node_modules/chrome-devtools-mcp/package.json'
        pkg.write_text(json.dumps({'version': mcp_version}), encoding='utf-8')
        return bin_dir

    def test_later_node_tree_with_the_pinned_mcp_wins(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bare = self._node_tree(root, 'v22.22.0')
            with_mcp = self._node_tree(root, 'v22.23.1', '1.6.0')
            bin_dir, mcp_js = PING.pinned_mcp([bare, with_mcp])
            self.assertEqual(bin_dir, with_mcp)
            self.assertTrue(str(mcp_js).endswith('chrome-devtools-mcp.js'))

    def test_wrong_version_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stale = self._node_tree(root, 'v22.22.0', '1.5.0')
            good = self._node_tree(root, 'v22.23.1', '1.6.0')
            self.assertEqual(PING.pinned_mcp([stale, good])[0], good)

    def test_no_qualifying_tree_fails_closed_with_the_searched_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bare = self._node_tree(root, 'v22.22.0')
            with self.assertRaisesRegex(PING.Blocked, 'searched'):
                PING.pinned_mcp([bare])


if __name__ == '__main__':
    unittest.main()
