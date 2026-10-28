"""Neutral naming and shared legacy exclusion/state contracts; no live services."""
import importlib.util
import os
import fcntl
import shutil
import tempfile
from pathlib import Path
import subprocess
import unittest
from tests.subprocess_environment import isolated_home_environment
ROOT = Path(__file__).resolve().parents[1]
NEW = ROOT / '.claude/skills/dot-coordinator'
OLD = ROOT / '.claude/skills/agy-dot-coordinator'
class CoordinatorNaming(unittest.TestCase):
    def test_neutral_canonical_skill_and_entrypoint(self):
        self.assertIn('name: dot-coordinator', (NEW / 'SKILL.md').read_text())
        self.assertTrue((NEW / 'scripts/dot-coordinator-wrapper.sh').is_file())
    def test_legacy_shims_forward_to_single_implementation(self):
        for name, target in [('agy-dot-coordinator-wrapper.sh', 'dot-coordinator-wrapper.sh'),
                             ('pi-lunaroute-adapter.sh', 'pi-lunaroute-adapter.sh'),
                             ('ping-dots.py', 'ping-dots.py'),
                             ('review-with-coordinator-lock.py', 'review-with-coordinator-lock.py')]:
            path = OLD / 'scripts' / name
            self.assertFalse(path.is_symlink())
            self.assertIn("dot-coordinator/scripts/" + target, path.read_text())
        r = subprocess.run(['bash', str(OLD / 'scripts/agy-dot-coordinator-wrapper.sh'), '--help'], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('--account', r.stdout)
    def test_retired_review_aliases_leave_existing_hold_untouched(self):
        with tempfile.TemporaryDirectory() as directory:
            lock = Path(directory) / 'shared.lock'
            before = None
            with lock.open('a') as held:
                before = lock.stat().st_ino
                fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
                for package in (OLD, NEW):
                    result = subprocess.run(['python3', str(package / 'scripts/review-with-coordinator-lock.py'), '--', 'true'],
                        env={**os.environ, 'COORDINATOR_LOCK_FILE': str(lock)}, capture_output=True, text=True)
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertEqual(lock.stat().st_ino, before)
    def test_installer_preserves_aliases_and_existing_hold_ledger(self):
        from tests.test_installer import InstallerIntegrationTest
        helper = InstallerIntegrationTest()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = helper.make_fixture(root)
            for package in (OLD, NEW):
                shutil.copytree(package, fixture / '.claude/skills' / package.name, symlinks=True,
                    ignore=shutil.ignore_patterns('__pycache__'))
            home = root / 'home'
            state = home / '.local/state/ai.gemini.agy-dot-coordinator'
            state.mkdir(parents=True)
            stop = state / 'STOP'; stop.write_text('operator hold')
            pending = state / 'send-fixture.pending'; pending.write_text('uncertain fixture')
            before = [(p.stat().st_ino, p.read_bytes()) for p in (stop, pending)]
            target = root / 'installed'
            environment = isolated_home_environment(home)
            result = helper.run_installer(
                fixture,
                target,
                extra_environment={
                    'HOME': environment['HOME'],
                    'PATH': environment['PATH'],
                },
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            alias = target / 'skills/agy-dot-coordinator/scripts/ping-dots.py'
            self.assertFalse(alias.is_symlink())
            self.assertIn('dot-coordinator/scripts/ping-dots.py', alias.read_text())
            check = subprocess.run(['python3', str(alias), '--help'], capture_output=True, text=True)
            self.assertEqual(check.returncode, 0, check.stderr)
            self.assertEqual(before, [(p.stat().st_ino, p.read_bytes()) for p in (stop, pending)])

    def test_shared_helpers_keep_guards_but_coordinator_does_not_consume_them(self):
        launcher = (NEW / 'scripts/ping-dots.py').read_text()
        review = (NEW / 'scripts/review-with-coordinator-lock.py').read_text()
        dot = (ROOT / '.claude/skills/dot/scripts/dot.sh').read_text()
        self.assertNotIn('COORDINATOR_STATE_DIR', launcher)
        self.assertNotIn('COORDINATOR_PENDING_FILE', launcher)
        self.assertNotIn('fcntl.flock', launcher)
        self.assertNotIn('global_lock', launcher)
        self.assertIn('retired', review.lower())
        # dot.sh no longer creates coordinator reservations or profile locks.
        self.assertNotIn('ai.gemini.agy-dot-coordinator/STOP', dot)
        self.assertNotIn('DOT_PROFILE_LOCKED', dot)
        self.assertNotIn('flock', dot)
    def test_no_activation_entrypoint(self):
        for name in ['install-launchagent.sh', 'install-systemd.sh']:
            r = subprocess.run(['bash', str(NEW / 'scripts' / name)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 2)
            self.assertIn('Activation is not performed', r.stderr)
if __name__ == '__main__': unittest.main()
