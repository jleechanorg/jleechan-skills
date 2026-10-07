import os
import signal
import subprocess
import sys
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / ".claude" / "skills" / "dot-portfolio-coordinator"
sys.path.insert(0, str(SKILL_DIR / "scripts"))

from modules.process_utils import run_bounded_command, ProcessTimeoutError


class TestDotPortfolioCoordinatorProcessUtils(unittest.TestCase):
    def test_successful_command_execution(self):
        rc, stdout, stderr = run_bounded_command([sys.executable, "-c", "print('hello_bounded')"], timeout_secs=5)
        self.assertEqual(rc, 0)
        self.assertIn("hello_bounded", stdout)

    def test_timeout_terminates_process_group_and_grandchildren(self):
        # Python script that spawns a background grandchild sleep process
        grandchild_script = (
            "import subprocess, sys, time\n"
            "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\n"
            "print(f'GRANDCHILD_PID={p.pid}', flush=True)\n"
            "time.sleep(30)\n"
        )
        t0 = time.time()
        with self.assertRaises(ProcessTimeoutError) as ctx:
            run_bounded_command([sys.executable, "-c", grandchild_script], timeout_secs=2)
        elapsed = time.time() - t0
        self.assertLess(elapsed, 6)  # should not hang waiting for 30s sleep


if __name__ == "__main__":
    unittest.main()
