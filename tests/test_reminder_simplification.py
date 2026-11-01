"""Scheduled reminder owns no task ledger or global review exclusion."""
from pathlib import Path
import os, subprocess, tempfile, unittest
ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / '.claude/skills/dot-coordinator'
class SimpleReminder(unittest.TestCase):
    def test_no_coordinator_global_lock_or_attempt_receipt(self):
        source = (PACKAGE / 'scripts/ping-dots.py').read_text()
        self.assertNotIn('global_lock', source)
        self.assertNotIn('COORDINATOR_ATTEMPT_FILE', source)
        self.assertNotIn('profile_lock', source)
        self.assertNotIn('COORDINATOR_PENDING_FILE', source)
    def test_dot_owns_tasks_and_only_transport_uncertainty_is_retained(self):
        skill = (PACKAGE / 'SKILL.md').read_text()
        self.assertIn('Each Dot owns its task state', skill)
        self.assertIn('Do not inspect, assign, implement or track tasks', skill)
        self.assertIn('No durable record carries this uncertainty', skill)
        self.assertNotIn('Resume feasible work', skill)
        self.assertNotIn('For each open item', skill)
    def test_legacy_review_helper_fails_closed_without_holding_or_running(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / 'ran'
            lock = Path(directory) / 'global.lock'
            result = subprocess.run(['python3', str(PACKAGE / 'scripts/review-with-coordinator-lock.py'), '--',
                'python3', '-c', f'open({str(marker)!r}, "w").write("ran")'],
                env={**os.environ, 'COORDINATOR_LOCK_FILE': str(lock)}, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertFalse(marker.exists())
            self.assertFalse(lock.exists())
if __name__ == '__main__': unittest.main()
