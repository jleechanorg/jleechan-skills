import os
import signal
import subprocess
import sys
import time
import unittest
import tempfile
from unittest import mock
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

    def test_interrupt_terminates_owned_group_and_reraises(self):
        process = mock.Mock(pid=43210)
        process.communicate.side_effect = [KeyboardInterrupt(), ("", "")]
        with mock.patch("modules.process_utils.subprocess.Popen", return_value=process):
            with mock.patch("modules.process_utils.os.killpg") as kill:
                with self.assertRaises(KeyboardInterrupt):
                    run_bounded_command(["unused"])
                kill.assert_called_with(43210, signal.SIGKILL)

    def test_timeout_kills_group_after_its_leader_exits(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            path = Path(tmp) / "child.pid"
            code = "import subprocess,sys; p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); open(sys.argv[1],'w').write(str(p.pid))"
            try:
                with self.assertRaises(ProcessTimeoutError):
                    run_bounded_command([sys.executable, "-c", code, str(path)], timeout_secs=1)
                pid = int(path.read_text())
                state = subprocess.run(["ps", "-p", str(pid), "-o", "stat="], capture_output=True, text=True).stdout.strip()
                self.assertTrue(not state or state.startswith("Z"), state)
            finally:
                if path.exists():
                    try:
                        os.kill(int(path.read_text()), signal.SIGKILL)
                    except ProcessLookupError:
                        pass


if __name__ == "__main__":
    unittest.main()
