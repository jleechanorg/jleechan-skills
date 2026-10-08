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

from modules import process_utils
from modules.process_utils import ProcessTimeoutError, run_bounded_command


class TestDotPortfolioCoordinatorProcessUtils(unittest.TestCase):
    def test_successful_command_execution(self):
        rc, stdout, stderr = run_bounded_command([sys.executable, "-c", "print('hello_bounded')"], timeout_secs=5)
        self.assertEqual(rc, 0)
        self.assertIn("hello_bounded", stdout)

    def test_successful_command_cleans_descendant_after_leader_exits(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            path = Path(tmp) / "child.pid"
            code = (
                "import subprocess,sys,time; "
                "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'], "
                "stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); "
                "open(sys.argv[1],'w').write(str(p.pid)); time.sleep(.05)"
            )
            rc, _, _ = run_bounded_command(
                [sys.executable, "-c", code, str(path)], timeout_secs=5
            )
            self.assertEqual(rc, 0)
            pid = int(path.read_text())
            state = subprocess.run(
                ["ps", "-p", str(pid), "-o", "stat="],
                capture_output=True,
                text=True,
                check=False,
            ).stdout.strip()
            self.assertTrue(not state or state.startswith("Z"), state)

    def test_interactive_child_frames_prepare_and_commit_and_cleans_group(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            pid_path = Path(tmp) / "child.pid"
            code = (
                "import subprocess,sys; "
                "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'], "
                "stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); "
                "open(sys.argv[1],'w').write(str(p.pid)); "
                "print('prepared',flush=True); "
                "frame=sys.stdin.buffer.readline(); "
                "print(frame.decode().strip(),flush=True)"
            )

            def interact(child):
                self.assertEqual(child.read_frame(), b"prepared")
                child.send_frame(b"commit")
                return child.read_frame()

            result = process_utils.run_bounded_interactive_command(
                [sys.executable, "-c", code, str(pid_path)],
                interact,
                timeout_secs=5,
            )
            self.assertEqual(result, b"commit")
            pid = int(pid_path.read_text())
            state = subprocess.run(
                ["ps", "-p", str(pid), "-o", "stat="],
                capture_output=True,
                text=True,
                check=False,
            ).stdout.strip()
            self.assertTrue(not state or state.startswith("Z"), state)

    def test_natural_exit_result_preserves_callback_and_nonzero_code(self):
        for rc in (0, 7):
            with self.subTest(rc=rc):
                completed = process_utils.run_bounded_interactive_command(
                    [sys.executable, "-c", f"import sys; print('marker',flush=True); sys.exit({rc})"],
                    lambda child: child.read_frame(), timeout_secs=2,
                    wait_for_exit=True,
                )
                self.assertEqual(completed.result, b"marker")
                self.assertEqual(completed.returncode, rc)

    def test_natural_exit_wait_uses_remaining_absolute_deadline(self):
        proc = mock.Mock(pid=43210)
        proc.wait.return_value = 0
        with mock.patch.object(process_utils.subprocess, "Popen", return_value=proc), \
                mock.patch.object(process_utils, "InteractiveChild"), \
                mock.patch.object(process_utils.time, "monotonic", side_effect=[100, 100.75, 100.8]), \
                mock.patch.object(process_utils, "_group_exists", return_value=False), \
                mock.patch.object(process_utils, "_terminate_owned_group"):
            completed = process_utils.run_bounded_interactive_command(
                ["unused"], lambda child: "marker", timeout_secs=1, wait_for_exit=True,
            )
        self.assertEqual(completed.returncode, 0)
        proc.wait.assert_called_once_with(timeout=0.25)

    def test_natural_exit_completed_after_original_deadline_is_rejected(self):
        proc = mock.Mock(pid=43210)
        proc.wait.return_value = 0
        with mock.patch.object(process_utils.subprocess, "Popen", return_value=proc), \
                mock.patch.object(process_utils, "InteractiveChild"), \
                mock.patch.object(process_utils.time, "monotonic", side_effect=[100, 100.75, 101.01]), \
                mock.patch.object(process_utils, "_group_exists", return_value=False), \
                mock.patch.object(process_utils, "_terminate_owned_group"), \
                self.assertRaises(ProcessTimeoutError):
            process_utils.run_bounded_interactive_command(
                ["unused"], lambda child: "marker", timeout_secs=1, wait_for_exit=True,
            )

    def test_natural_exit_rejects_marker_then_hang_or_live_descendant(self):
        cases = (
            "import time; print('marker',flush=True); time.sleep(30)",
            "import subprocess,sys; subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); print('marker',flush=True)",
        )
        for code in cases:
            with self.subTest(code=code):
                with self.assertRaises((ProcessTimeoutError, process_utils.ProcessExecutionError)):
                    process_utils.run_bounded_interactive_command(
                        [sys.executable, "-c", code], lambda child: child.read_frame(),
                        timeout_secs=1, wait_for_exit=True,
                    )

    def test_interactive_child_timeout_cleans_group(self):
        code = "import time; print('prepared',flush=True); time.sleep(30)"

        def wait_forever(child):
            child.read_frame()
            return child.read_frame()

        with self.assertRaises(ProcessTimeoutError):
            process_utils.run_bounded_interactive_command(
                [sys.executable, "-c", code],
                wait_forever,
                timeout_secs=1,
            )

    def test_interactive_child_send_is_bounded_by_absolute_deadline(self):
        code = "import time; time.sleep(30)"

        def fill_pipe(child):
            for _ in range(4):
                child.send_frame(b"x" * 65536)

        started = time.monotonic()
        with self.assertRaises(ProcessTimeoutError):
            process_utils.run_bounded_interactive_command(
                [sys.executable, "-c", code],
                fill_pipe,
                timeout_secs=1,
            )
        self.assertLess(time.monotonic() - started, 4)

    def test_interactive_child_enforces_inbound_frame_byte_limit(self):
        code = "print('12345',flush=True)"
        with self.assertRaises(Exception) as ctx:
            process_utils.run_bounded_interactive_command(
                [sys.executable, "-c", code],
                lambda child: child.read_frame(),
                timeout_secs=5,
                max_frame_bytes=4,
            )
        self.assertEqual(ctx.exception.__class__.__name__, "ProcessExecutionError")

    def test_buffered_frame_cannot_be_read_after_deadline(self):
        code = "print('first\\nsecond',flush=True)"
        read_expired = []

        def read_after_deadline(child):
            self.assertEqual(child.read_frame(), b"first")
            time.sleep(1.05)
            try:
                child.read_frame()
            except ProcessTimeoutError:
                read_expired.append(True)

        with self.assertRaises(ProcessTimeoutError):
            process_utils.run_bounded_interactive_command(
                [sys.executable, "-c", code],
                read_after_deadline,
                timeout_secs=1,
            )
        self.assertEqual(read_expired, [True])

    def test_interactive_child_supports_abort_frame(self):
        code = (
            "import sys; print('prepared',flush=True); "
            "print(sys.stdin.buffer.readline().decode().strip(),flush=True)"
        )

        def abort(child):
            self.assertEqual(child.read_frame(), b"prepared")
            child.send_frame("abort")
            return child.read_frame()

        self.assertEqual(
            process_utils.run_bounded_interactive_command(
                [sys.executable, "-c", code], abort, timeout_secs=5
            ),
            b"abort",
        )

    def test_interactive_child_callback_error_is_preserved_after_cleanup(self):
        code = "import time; print('prepared',flush=True); time.sleep(30)"

        def fail(_child):
            raise ValueError("callback failed")

        with self.assertRaisesRegex(ValueError, "callback failed"):
            process_utils.run_bounded_interactive_command(
                [sys.executable, "-c", code], fail, timeout_secs=5
            )

    def test_interactive_child_rejects_newline_injected_frame(self):
        code = "import time; print('prepared',flush=True); time.sleep(30)"

        def inject(child):
            child.read_frame()
            child.send_frame(b"commit\nabort")

        with self.assertRaises(Exception) as ctx:
            process_utils.run_bounded_interactive_command(
                [sys.executable, "-c", code], inject, timeout_secs=5
            )

    def test_cleanup_failure_is_surfaced(self):
        process = mock.Mock(pid=43210)
        process.communicate.return_value = ("ok", "")
        process.wait.return_value = 0
        with mock.patch("modules.process_utils.subprocess.Popen", return_value=process):
            with mock.patch("modules.process_utils._group_exists", return_value=True):
                with mock.patch(
                    "modules.process_utils.os.killpg",
                    side_effect=PermissionError("denied"),
                ):
                    with self.assertRaises(Exception) as ctx:
                        run_bounded_command(["unused"])
        self.assertEqual(ctx.exception.__class__.__name__, "ProcessCleanupError")

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
            with mock.patch(
                "modules.process_utils._group_exists", side_effect=[True, False, False]
            ):
                with mock.patch("modules.process_utils.os.killpg") as kill:
                    with self.assertRaises(KeyboardInterrupt):
                        run_bounded_command(["unused"])
                kill.assert_called_with(43210, signal.SIGTERM)

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
