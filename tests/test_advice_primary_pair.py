#!/usr/bin/env python3
"""Executable regression tests for the isolated /advice primary pair."""

from __future__ import annotations

import json
import importlib.util
import io
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock
from contextlib import redirect_stderr


SCRIPT = (
    Path(__file__).resolve().parent.parent
    / ".claude"
    / "skills"
    / "advice"
    / "scripts"
    / "run_primary_pair.py"
)


def load_runner_module():
    spec = importlib.util.spec_from_file_location("advice_primary_pair_runner", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(*args: str, cwd: Path | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, env=env, text=True, capture_output=True, check=False)


def test_process_start_identity(pid: int) -> str | None:
    proc_stat = Path("/proc") / str(pid) / "stat"
    if Path("/proc").is_dir():
        try:
            fields = proc_stat.read_text().rsplit(")", 1)[1].split()
            return f"linux-start-ticks:{fields[19]}"
        except (OSError, IndexError):
            return None
    result = subprocess.run(
        ["ps", "-o", "lstart=", "-p", str(pid)],
        capture_output=True,
        text=True,
        check=False,
        timeout=1,
    )
    return result.stdout.strip() or None


def test_process_is_running(pid: int, expected_identity: str) -> bool:
    if test_process_start_identity(pid) != expected_identity:
        return False
    result = subprocess.run(
        ["ps", "-o", "stat=", "-p", str(pid)],
        capture_output=True,
        text=True,
        check=False,
        timeout=1,
    )
    state = result.stdout.strip()
    return bool(state) and not state.startswith("Z")


def terminate_test_process(pid: int, expected_identity: str) -> None:
    pidfd_open = getattr(os, "pidfd_open", None)
    pidfd_send_signal = getattr(signal, "pidfd_send_signal", None)
    if not callable(pidfd_open) or not callable(pidfd_send_signal):
        return
    try:
        pidfd = pidfd_open(pid, 0)
    except OSError:
        return
    try:
        if test_process_start_identity(pid) == expected_identity:
            try:
                pidfd_send_signal(pidfd, signal.SIGKILL)
            except OSError:
                pass
    finally:
        os.close(pidfd)


def wait_for_test_process_exit(pid: int, expected_identity: str, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not test_process_is_running(pid, expected_identity):
            return True
        time.sleep(0.02)
    return not test_process_is_running(pid, expected_identity)


def cleanup_test_process_file(path: Path, timeout: float) -> None:
    if not path.exists():
        return
    pid_text, expected_identity = path.read_text().splitlines()
    pid = int(pid_text)
    terminate_test_process(pid, expected_identity)
    if not wait_for_test_process_exit(pid, expected_identity, timeout):
        raise AssertionError(f"fixture process {pid} did not exit after safe cleanup")


class ReviewerProcessTest(unittest.TestCase):
    def test_reviewer_receives_eof_while_parent_stdin_remains_open(self) -> None:
        child = (
            "import importlib.util, sys\n"
            f"spec = importlib.util.spec_from_file_location('runner', {str(SCRIPT)!r})\n"
            "runner = importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)\n"
            "result = runner.execute([sys.executable, '-c', "
            "'import sys; sys.stdin.read(); print(\"EOF\")'], '.', 'review', 1, 0.2)\n"
            "print('RESULT', result[0], result[1].strip(), result[3], flush=True)\n"
        )
        parent = subprocess.Popen(
            [sys.executable, "-c", child],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            parent.wait(timeout=8)
            output = parent.stdout.read()
            error = parent.stderr.read()
            self.assertEqual(parent.returncode, 0, error)
            self.assertIn("RESULT 0 EOF False", output)
        finally:
            if parent.poll() is None:
                parent.kill()
                parent.wait(timeout=2)
            parent.stdin.close()
            parent.stdout.close()
            parent.stderr.close()

    def test_process_snapshot_allows_ten_seconds_for_ps(self) -> None:
        runner = load_runner_module()
        result = subprocess.CompletedProcess(
            ["ps"], 0, stdout=" 123 1 Mon Oct 25 00:00:00 2026\n", stderr=""
        )
        with mock.patch.object(runner.subprocess, "run", return_value=result) as ps:
            self.assertEqual(runner.process_snapshot(), {123: (1, "Mon Oct 25 00:00:00 2026")})
        self.assertEqual(ps.call_args.kwargs["timeout"], 10.0)

    def test_supervisor_ignores_descendants_of_reused_cached_pid(self) -> None:
        runner = load_runner_module()
        snapshots = [
            {100: (1, "root-start"), 200: (100, "child-start")},
            {
                100: (1, "root-start"),
                200: (2, "reused-pid-start"),
                300: (200, "unrelated-descendant-start"),
            },
        ]
        supervisor = runner.ProcessTreeSupervisor(100)
        with mock.patch.object(runner, "process_snapshot", side_effect=snapshots), mock.patch.object(
            runner, "process_start_identity", side_effect=["root-start", "root-start", "reused-pid-start"]
        ), mock.patch.object(runner, "process_info", return_value=(100, "child-start")), mock.patch.object(
            supervisor, "_pidfd_matches_identity", return_value=True
        ):
            supervisor._sample()
            supervisor._sample()

        self.assertEqual(supervisor.discovered, {200: "child-start"})

    def test_supervisor_ignores_children_of_reused_reviewer_pid(self) -> None:
        runner = load_runner_module()
        snapshots = [
            {100: (1, "root-start")},
            {100: (2, "reused-root-pid-start"), 300: (100, "unrelated-child-start")},
        ]
        supervisor = runner.ProcessTreeSupervisor(100)
        with mock.patch.object(runner, "process_snapshot", side_effect=snapshots), mock.patch.object(
            runner, "process_start_identity", side_effect=["root-start", "reused-root-pid-start"]
        ), mock.patch.object(runner, "process_info", return_value=None):
            supervisor._sample()
            supervisor._sample()

        self.assertEqual(supervisor.discovered, {})
        self.assertTrue(any("root PID identity changed" in error for error in supervisor.errors))

    def test_supervisor_does_not_bind_reused_root_after_initial_probe_failure(self) -> None:
        runner = load_runner_module()
        supervisor = runner.ProcessTreeSupervisor(100)
        snapshots = [
            subprocess.TimeoutExpired(["ps"], 1),
            {100: (2, "reused-root-start"), 300: (100, "unrelated-child-start")},
        ]
        with mock.patch.object(runner, "process_snapshot", side_effect=snapshots), mock.patch.object(
            runner, "process_start_identity", return_value=None
        ), mock.patch.object(runner, "process_info", return_value=(100, "child-start")):
            supervisor._sample()
            supervisor._sample()

        self.assertEqual(supervisor.discovered, {})
        self.assertIsNone(supervisor.root_identity)
        self.assertTrue(supervisor._root_identity_initialized)

    @unittest.skipUnless(sys.platform.startswith("linux"), "requires Linux procfs parent identity checks")
    def test_supervisor_rechecks_parent_identity_after_reading_child_parent(self) -> None:
        runner = load_runner_module()
        supervisor = runner.ProcessTreeSupervisor(100)
        with mock.patch.object(
            runner, "process_snapshot", return_value={100: (1, "ps-root"), 300: (100, "ps-child")}
        ), mock.patch.object(
            runner, "process_start_identity", side_effect=["root-start", "reused-root-start"]
        ), mock.patch.object(
            runner, "process_info", return_value=(100, "child-start")
        ), mock.patch.object(
            runner, "pidfd_has_exited", return_value=False
        ), mock.patch.object(runner.os, "pidfd_open", return_value=77), mock.patch.object(
            runner.os, "close"
        ):
            supervisor._sample()

        self.assertEqual(supervisor.discovered, {})
        self.assertTrue(any("parent identity" in error for error in supervisor.errors))

    def test_supervisor_does_not_use_numeric_kill_without_pidfd(self) -> None:
        runner = load_runner_module()
        supervisor = runner.ProcessTreeSupervisor(100)
        supervisor.discovered = {200: "expected-start"}
        with mock.patch.object(
            supervisor, "_snapshot", return_value={200: (1, "expected-start")}
        ), mock.patch.object(runner.os, "pidfd_open", None, create=True), mock.patch.object(
            runner.signal, "pidfd_send_signal", None, create=True
        ), mock.patch.object(runner.os, "kill") as numeric_kill:
            self.assertEqual(supervisor.signal_active(signal.SIGTERM), [])

        numeric_kill.assert_not_called()
        self.assertEqual(supervisor.errors, [])

    def test_supervisor_signals_pidfd_only_after_identity_recheck(self) -> None:
        runner = load_runner_module()
        supervisor = runner.ProcessTreeSupervisor(100)
        supervisor.discovered = {200: "expected-start"}
        with mock.patch.object(
            supervisor, "_snapshot", return_value={200: (1, "expected-start")}
        ), mock.patch.object(
            runner, "pidfd_has_exited", return_value=False
        ), mock.patch.object(runner.os, "pidfd_open", return_value=77), mock.patch.object(
            runner, "process_start_identity", side_effect=["expected-start", "reused-start"]
        ), mock.patch.object(runner.signal, "pidfd_send_signal") as pidfd_signal, mock.patch.object(
            runner.os, "close"
        ):
            self.assertEqual(supervisor.signal_active(signal.SIGTERM), [])

        pidfd_signal.assert_not_called()
        self.assertTrue(any("identity changed" in error for error in supervisor.errors))

    def test_supervisor_uses_pidfd_for_verified_descendant_signal(self) -> None:
        runner = load_runner_module()
        supervisor = runner.ProcessTreeSupervisor(100)
        supervisor.discovered = {200: "expected-start"}
        with mock.patch.object(
            supervisor, "_snapshot", return_value={200: (1, "expected-start")}
        ), mock.patch.object(
            runner, "pidfd_has_exited", return_value=False
        ), mock.patch.object(runner.os, "pidfd_open", return_value=77), mock.patch.object(
            runner, "process_start_identity", return_value="expected-start"
        ), mock.patch.object(runner.signal, "pidfd_send_signal") as pidfd_signal, mock.patch.object(
            runner.os, "close"
        ) as close:
            self.assertEqual(supervisor.signal_active(signal.SIGTERM), [200])

        pidfd_signal.assert_called_once_with(77, signal.SIGTERM)
        close.assert_has_calls([mock.call(77), mock.call(77)])
        self.assertEqual(close.call_count, 2)

    @unittest.skipUnless(
        sys.platform.startswith("linux"), "requires Linux process snapshot semantics"
    )
    def test_child_exiting_before_identity_read_is_not_cleanup_error(self) -> None:
        runner = load_runner_module()
        child = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            start_new_session=True,
        )
        child.kill()
        child.wait(timeout=2)
        root_pid = os.getpid()
        supervisor = runner.ProcessTreeSupervisor(root_pid)
        snapshot = {
            root_pid: (1, "root-snapshot-identity"),
            child.pid: (root_pid, "child-snapshot-identity"),
        }

        def read_process_info(pid: int):
            if pid == root_pid:
                return (1, "root-start-identity")
            if pid == child.pid:
                return None
            return None

        with mock.patch.object(runner, "process_snapshot", return_value=snapshot), mock.patch.object(
            runner, "process_info", side_effect=read_process_info
        ):
            supervisor._sample()
            evidence = supervisor.evidence(set(), [])

        self.assertEqual(evidence["descendant_supervision_errors"], [])
        self.assertTrue(evidence["descendant_termination_verified"])

    @unittest.skipUnless(
        sys.platform.startswith("linux"), "requires Linux process snapshot semantics"
    )
    def test_child_identity_read_failure_before_admission_invalidates_cleanup(self) -> None:
        runner = load_runner_module()
        child = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            start_new_session=True,
        )
        try:
            identity = test_process_start_identity(child.pid)
            if identity is None:
                self.fail("fixture process identity was unavailable")
            root_pid = os.getpid()
            supervisor = runner.ProcessTreeSupervisor(root_pid)
            snapshot = {
                root_pid: (1, "root-snapshot-identity"),
                child.pid: (root_pid, "child-snapshot-identity"),
            }

            def read_process_info(pid: int):
                if pid == root_pid:
                    return (1, "root-start-identity")
                if pid == child.pid:
                    return None
                return None

            with mock.patch.object(runner, "process_snapshot", return_value=snapshot), mock.patch.object(
                runner, "process_info", side_effect=read_process_info
            ):
                supervisor._sample()
                evidence = supervisor.evidence(set(), [])

            self.assertTrue(test_process_is_running(child.pid, identity))
            self.assertFalse(
                evidence["descendant_termination_verified"],
                "an observed live descendant with unreadable identity is unverified",
            )
            self.assertTrue(evidence["descendant_supervision_errors"])
        finally:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=2)

    def test_live_descendant_absent_from_snapshot_is_not_verified_gone(self) -> None:
        runner = load_runner_module()
        child = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            start_new_session=True,
        )
        try:
            identity = test_process_start_identity(child.pid)
            if identity is None:
                self.fail("fixture process identity was unavailable")
            supervisor = runner.ProcessTreeSupervisor(os.getpid())
            supervisor.discovered = {child.pid: identity}
            with mock.patch.object(supervisor, "_snapshot", return_value={}):
                active = supervisor.active_discovered()
                evidence = supervisor.evidence(set(), active)

            if callable(getattr(os, "pidfd_open", None)):
                self.assertEqual(active, [child.pid])
            else:
                self.assertEqual(active, [])
            self.assertFalse(
                evidence["descendant_termination_verified"],
                "a live discovered descendant omitted from a snapshot is unverified",
            )
            self.assertTrue(test_process_is_running(child.pid, identity))
        finally:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=2)

    def test_unobservable_live_descendant_marks_cleanup_unverified(self) -> None:
        runner = load_runner_module()
        child = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            start_new_session=True,
        )
        try:
            identity = test_process_start_identity(child.pid)
            if identity is None:
                self.fail("fixture process identity was unavailable")
            supervisor = runner.ProcessTreeSupervisor(100)
            supervisor.discovered = {child.pid: identity}
            with mock.patch.object(
                supervisor,
                "_snapshot",
                return_value={child.pid: (os.getpid(), "observed-start")},
            ), mock.patch.object(
                runner, "process_start_identity", return_value=None
            ):
                active = supervisor.active_discovered()
                evidence = supervisor.evidence(set(), active)

            self.assertEqual(active, [])
            self.assertFalse(
                evidence["descendant_termination_verified"],
                "an unobservable but previously discovered live process is not proof of exit",
            )
            self.assertTrue(evidence["descendant_supervision_errors"])
            self.assertTrue(test_process_is_running(child.pid, identity))
        finally:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=2)

    def test_supervisor_startup_consumes_reviewer_timeout(self) -> None:
        runner = load_runner_module()

        def delayed_start(supervisor) -> None:
            time.sleep(0.1)

        with mock.patch.object(runner.ProcessTreeSupervisor, "start", delayed_start), \
                mock.patch.object(runner.ProcessTreeSupervisor, "stop"), \
                mock.patch.object(runner.ProcessTreeSupervisor, "active_discovered", return_value=[]), \
                mock.patch.object(runner.ProcessTreeSupervisor, "signal_active", return_value=[]), \
                mock.patch.object(runner.ProcessTreeSupervisor, "verify_gone", return_value=[]):
            result = runner.execute(
                [sys.executable, "-c", "print('VERDICT: APPROVED')"],
                Path(__file__).resolve().parent,
                "review",
                0.02,
                0.02,
            )

        self.assertTrue(result[3], "supervisor startup exceeded the reviewer deadline")

    def test_supervisor_start_failure_terminates_and_reaps_reviewer(self) -> None:
        runner = load_runner_module()
        with tempfile.TemporaryDirectory() as directory:
            pid_file = Path(directory) / "start-failure.pid"
            child_program = (
                "import os, pathlib, subprocess, time\n"
                "pid = os.getpid()\n"
                "proc = pathlib.Path(f'/proc/{pid}/stat')\n"
                "if proc.exists():\n"
                " fields = proc.read_text().rsplit(')', 1)[1].split()\n"
                " identity = f'linux-start-ticks:{fields[19]}'\n"
                "else:\n"
                " identity = subprocess.run(['ps', '-o', 'lstart=', '-p', str(pid)], capture_output=True, text=True, check=True).stdout.strip()\n"
                f"pathlib.Path({str(pid_file)!r}).write_text(f'{{pid}}\\n{{identity}}')\n"
                "time.sleep(30)\n"
            )

            def fail_after_child_launch(supervisor) -> None:
                deadline = time.monotonic() + 3
                while not pid_file.exists() and time.monotonic() < deadline:
                    time.sleep(0.01)
                if not pid_file.exists():
                    raise AssertionError("reviewer child did not start")
                raise RuntimeError("injected supervision startup failure")

            with mock.patch.object(
                runner.ProcessTreeSupervisor, "start", fail_after_child_launch
            ):
                with self.assertRaisesRegex(
                    RuntimeError, "injected supervision startup failure"
                ):
                    runner.execute(
                        [sys.executable, "-c", child_program],
                        Path(__file__).resolve().parent,
                        "prompt",
                        5,
                        0.1,
                    )

            pid_text, identity = pid_file.read_text().splitlines()
            self.assertTrue(
                wait_for_test_process_exit(int(pid_text), identity, 2),
                "reviewer survived supervision startup failure",
            )

    @unittest.skipUnless(
        sys.platform.startswith("linux")
        and callable(getattr(os, "pidfd_open", None))
        and callable(getattr(signal, "pidfd_send_signal", None)),
        "requires Linux pidfd signaling",
    )
    def test_post_deadline_pidfd_cleanup_can_verify_exited_descendant(self) -> None:
        runner = load_runner_module()
        child = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            start_new_session=True,
        )
        try:
            identity = test_process_start_identity(child.pid)
            if identity is None:
                self.fail("fixture process identity was unavailable")
            supervisor = runner.ProcessTreeSupervisor(
                os.getpid(), deadline=time.monotonic() + 0.02
            )
            supervisor.discovered = {child.pid: identity}
            time.sleep(0.05)
            supervisor.stop()

            signaled = supervisor.signal_active(signal.SIGKILL)
            self.assertEqual(signaled, [child.pid])
            self.assertTrue(wait_for_test_process_exit(child.pid, identity, 2))
            survivors = supervisor.verify_gone(0.5)
            evidence = supervisor.evidence(set(signaled), survivors)

            self.assertEqual(survivors, [])
            self.assertTrue(
                evidence["descendant_termination_verified"],
                evidence["descendant_supervision_errors"],
            )
        finally:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=2)

    @unittest.skipUnless(
        sys.platform.startswith("linux")
        and callable(getattr(os, "pidfd_open", None))
        and callable(getattr(signal, "pidfd_send_signal", None)),
        "requires Linux pidfd signaling",
    )
    def test_supervisor_signals_recorded_pidfd_targets_after_deadline_and_rejects_reuse(self) -> None:
        runner = load_runner_module()
        safe_child = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            start_new_session=True,
        )
        reused_child = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            start_new_session=True,
        )
        try:
            safe_identity = test_process_start_identity(safe_child.pid)
            reused_identity = test_process_start_identity(reused_child.pid)
            if safe_identity is None or reused_identity is None:
                self.fail("fixture process identity was unavailable")
            supervisor = runner.ProcessTreeSupervisor(
                os.getpid(), deadline=time.monotonic() + 0.02
            )
            supervisor.discovered = {
                safe_child.pid: safe_identity,
                reused_child.pid: f"stale-{reused_identity}",
            }
            time.sleep(0.05)

            signaled = supervisor.signal_active(signal.SIGKILL)

            self.assertEqual(signaled, [safe_child.pid])
            self.assertTrue(
                wait_for_test_process_exit(safe_child.pid, safe_identity, 2)
            )
            self.assertTrue(
                test_process_is_running(reused_child.pid, reused_identity),
                "a stale identity must not signal the unrelated current process",
            )
            self.assertTrue(
                any("identity changed before pidfd signal" in error for error in supervisor.errors)
            )
        finally:
            for child in (safe_child, reused_child):
                if child.poll() is None:
                    child.kill()
                child.wait(timeout=2)

    def test_supervisor_constructor_failure_precedes_reviewer_launch(self) -> None:
        runner = load_runner_module()
        with mock.patch.object(
            runner,
            "ProcessTreeSupervisor",
            side_effect=MemoryError("injected supervisor allocation failure"),
        ), mock.patch.object(runner.subprocess, "Popen") as popen:
            with self.assertRaisesRegex(
                MemoryError, "injected supervisor allocation failure"
            ):
                runner.execute(
                    [sys.executable, "-c", "import time; time.sleep(30)"],
                    Path(__file__).resolve().parent,
                    "prompt",
                    5,
                    0.2,
                )

        popen.assert_not_called()

    def test_reaped_leader_with_verified_children_does_not_fail_group_skip(self) -> None:
        runner = load_runner_module()

        class ReapedReviewer:
            pid = 123
            returncode = 0
            stdout = None
            stderr = None

            def poll(self):
                return 0

            def communicate(self, timeout=None):
                return "", ""

            def wait(self, timeout=None):
                return 0

            def kill(self):
                pass

        supervisor = runner.ProcessTreeSupervisor(
            os.getpid(), deadline=time.monotonic() + 5
        )
        with mock.patch.object(supervisor, "stop"), mock.patch.object(
            supervisor, "signal_active", side_effect=[[200], []]
        ), mock.patch.object(
            supervisor, "verify_gone", return_value=[]
        ), mock.patch.object(runner.os, "killpg") as killpg:
            result = runner.cleanup_reviewer_process(
                ReapedReviewer(), supervisor, 0.1
            )

        killpg.assert_not_called()
        self.assertTrue(result[4]["reviewer_leader_reaped"])
        self.assertTrue(result[4]["process_group_signal_skipped_after_leader_exit"])
        self.assertTrue(result[4]["descendant_termination_verified"])
        self.assertTrue(
            result[5], "verified descendants and a reaped leader should permit the peer vote"
        )
        self.assertEqual(
            runner.descendant_termination_failures(
                {"codex": {"attempts": [result[4]]}}
            ),
            [],
        )

    def test_supervisor_start_failure_cleans_detached_reviewer_descendant(self) -> None:
        runner = load_runner_module()
        with tempfile.TemporaryDirectory() as directory:
            child_file = Path(directory) / "detached-child.pid"
            reviewer_program = (
                "import pathlib, subprocess, sys, time\n"
                "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(2)'], start_new_session=True)\n"
                "proc = pathlib.Path(f'/proc/{child.pid}/stat')\n"
                "if proc.exists():\n"
                " fields = proc.read_text().rsplit(')', 1)[1].split()\n"
                " identity = f'linux-start-ticks:{fields[19]}'\n"
                "else:\n"
                " identity = subprocess.run(['ps', '-o', 'lstart=', '-p', str(child.pid)], capture_output=True, text=True, check=True).stdout.strip()\n"
                f"pathlib.Path({str(child_file)!r}).write_text(f'{{child.pid}}\\n{{identity}}')\n"
                "time.sleep(30)\n"
            )
            observed: dict[str, object] = {}

            def fail_before_initial_sample(supervisor) -> None:
                deadline = time.monotonic() + 3
                while not child_file.exists() and time.monotonic() < deadline:
                    time.sleep(0.01)
                if not child_file.exists():
                    raise AssertionError("detached reviewer child did not start")
                observed["supervisor"] = supervisor
                observed["leader_pid"] = supervisor.root_pid
                leader_identity = runner.process_start_identity(supervisor.root_pid)
                if leader_identity is None:
                    raise AssertionError("reviewer leader identity was unavailable")
                observed["leader_identity"] = leader_identity
                raise RuntimeError("injected failure before initial process sample")

            try:
                with mock.patch.object(
                    runner.ProcessTreeSupervisor, "start", fail_before_initial_sample
                ):
                    with self.assertRaisesRegex(
                        RuntimeError, "injected failure before initial process sample"
                    ):
                        runner.execute(
                            [sys.executable, "-c", reviewer_program],
                            Path(__file__).resolve().parent,
                            "prompt",
                            5,
                            0.2,
                        )

                child_text, child_identity = child_file.read_text().splitlines()
                child_pid = int(child_text)
                supervisor = observed["supervisor"]
                self.assertIn(child_pid, supervisor.discovered)
                self.assertFalse(
                    test_process_is_running(child_pid, child_identity),
                    "detached reviewer descendant survived supervisor startup failure",
                )
                self.assertFalse(
                    test_process_is_running(
                        observed["leader_pid"], observed["leader_identity"]
                    ),
                    "reviewer leader survived supervisor startup failure",
                )
            finally:
                cleanup_test_process_file(child_file, 3.0)

    def test_unreaped_reviewer_leader_invalidates_cleanup_evidence(self) -> None:
        runner = load_runner_module()

        class UnreapableReviewer:
            pid = 123
            returncode = None
            stdout = None
            stderr = None

            def poll(self):
                return None

            def communicate(self, timeout=None):
                raise subprocess.TimeoutExpired(["reviewer"], timeout or 0.01)

            def wait(self, timeout=None):
                raise subprocess.TimeoutExpired(["reviewer"], timeout or 0.01)

            def kill(self):
                pass

        evidence = {
            "descendant_termination_verified": True,
            "reviewer_leader_reaped": True,
            "descendants_surviving": [],
        }
        with mock.patch.object(
            runner.subprocess, "Popen", return_value=UnreapableReviewer()
        ), mock.patch.object(runner.ProcessTreeSupervisor, "start"), mock.patch.object(
            runner.ProcessTreeSupervisor, "stop"
        ), mock.patch.object(
            runner.ProcessTreeSupervisor, "signal_active", return_value=[]
        ), mock.patch.object(
            runner.ProcessTreeSupervisor, "verify_gone", return_value=[]
        ), mock.patch.object(
            runner.ProcessTreeSupervisor, "evidence", return_value=evidence
        ), mock.patch.object(runner.os, "killpg"):
            result = runner.execute(
                ["reviewer"], Path(__file__).resolve().parent, "prompt", 0.1, 0.01
            )

        self.assertIsNone(result[0], "an unreaped reviewer must not receive a synthetic exit code")
        self.assertFalse(result[5]["reviewer_leader_reaped"])
        self.assertEqual(
            runner.descendant_termination_failures(
                {"codex": {"attempts": [result[5]]}}
            ),
            ["codex"],
        )


class PrimaryPairTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.bin = self.root / "bin"
        self.sync = self.root / "sync"
        self.scratch = self.root / "scratch"
        self.output = self.root / "out"
        self.bin.mkdir()
        self.sync.mkdir()
        self.scratch.mkdir()
        run("git", "init", "-q", str(self.repo))
        run("git", "config", "user.email", "jleechan2015@users.noreply.github.com", cwd=self.repo)
        run("git", "config", "user.name", "Test", cwd=self.repo)
        (self.repo / "tracked.txt").write_text("original\n")
        run("git", "add", "tracked.txt", cwd=self.repo)
        run("git", "commit", "-qm", "fixture", cwd=self.repo)
        self.sha = run("git", "rev-parse", "HEAD", cwd=self.repo).stdout.strip()
        self.packet = self.root / "packet.txt"
        self.packet.write_text("DECISION:\nReview exact target.\n")
        self.env = os.environ.copy()
        self.env.pop("ADVICE_CODEX_MODEL", None)
        self.env["PATH"] = f"{self.bin}:{self.env['PATH']}"
        self.env["ADVICE_TEST_SYNC_DIR"] = str(self.sync)
        self.env["ADVICE_TEST_SCRATCH"] = str(self.scratch)
        self.executable(
            "diskm",
            'if [ "$1" = "scratch-dir" ]; then printf "%s\\n" "$ADVICE_TEST_SCRATCH"; else exit 2; fi\n',
        )
        self.env["DISK_MAGICIAN_DISKM_BIN"] = str(self.bin / "diskm")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def executable(self, name: str, body: str) -> None:
        path = self.bin / name
        path.write_text("#!/bin/sh\nset -eu\n" + body)
        path.chmod(0o755)

    def invoke_raw(self, *extra: str) -> subprocess.CompletedProcess[str]:
        return run(
            "python3",
            str(SCRIPT),
            "--repo",
            str(self.repo),
            "--ref",
            self.sha,
            "--packet-file",
            str(self.packet),
            "--output-dir",
            str(self.output),
            *extra,
            env=self.env,
        )

    def invoke(self, *extra: str) -> subprocess.CompletedProcess[str]:
        return self.invoke_raw(*self.with_queued_timestamps(list(extra)))

    def with_queued_timestamps(self, argv: list[str]) -> list[str]:
        queued = list(argv)
        if (
            "--queued-at-epoch-ns" not in queued
            or "--queued-at-monotonic-ns" not in queued
        ):
            epoch_ns = time.time_ns()
            monotonic_ns = time.monotonic_ns()
            if "--queued-at-epoch-ns" not in queued:
                queued.extend(("--queued-at-epoch-ns", str(epoch_ns)))
            if "--queued-at-monotonic-ns" not in queued:
                queued.extend(("--queued-at-monotonic-ns", str(monotonic_ns)))
        return queued

    def test_reviewers_do_not_accept_zero_exit_after_timeout(self) -> None:
        runner = load_runner_module()
        self.executable("codex", "exit 0\n")
        self.executable("claude", "exit 0\n")
        supervision = {
            "descendant_termination_verified": True,
            "reviewer_leader_reaped": True,
            "descendants_surviving": [],
        }
        timeout_result = (
            0,
            "VERDICT: APPROVED\nCOVERAGE: all\n",
            "",
            True,
            False,
            supervision,
        )
        deadline = time.monotonic() + 5
        with mock.patch.dict(os.environ, self.env), mock.patch.object(
            runner, "execute", return_value=timeout_result
        ):
            codex_result = runner.codex_lane(
                self.repo, "prompt", threading.Barrier(1), deadline, 0.1
            )
            opus_result = runner.opus_lane(
                self.repo, "prompt", threading.Barrier(1), deadline, 0.1
            )

        self.assertEqual(codex_result["status"], "error")
        self.assertEqual(opus_result["status"], "error")
        self.assertEqual(codex_result["attempts"][0]["failure"], "timeout")
        self.assertEqual(opus_result["attempts"][0]["failure"], "timeout")

    def test_timeout_does_not_signal_reused_group_after_reviewer_parent_exits(self) -> None:
        runner = load_runner_module()
        child_pid_file = self.sync / "pipe-holder.pid"
        child_program = (
            "import pathlib, subprocess, sys\n"
            "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(2)'])\n"
            "try:\n"
            " proc = pathlib.Path(f'/proc/{child.pid}/stat')\n"
            " if proc.exists():\n"
            "  fields = proc.read_text().rsplit(')', 1)[1].split()\n"
            "  identity = f'linux-start-ticks:{fields[19]}'\n"
            " else:\n"
            "  identity = subprocess.run(['ps', '-o', 'lstart=', '-p', str(child.pid)], capture_output=True, text=True, check=True).stdout.strip()\n"
            " if not identity:\n"
            "  raise RuntimeError('child identity unavailable')\n"
            f" pathlib.Path({str(child_pid_file)!r}).write_text(f'{{child.pid}}\\n{{identity}}')\n"
            "except BaseException:\n"
            " child.kill()\n"
            " child.wait()\n"
            " raise\n"
            "print('VERDICT: APPROVED')\n"
            "print('COVERAGE: all')\n"
        )

        try:
            def track_pipe_holder(supervisor) -> None:
                child_text, identity = child_pid_file.read_text().splitlines()
                supervisor.discovered[int(child_text)] = identity

            def report_survivor(grace_seconds: float) -> list[int]:
                child_text, identity = child_pid_file.read_text().splitlines()
                child_pid = int(child_text)
                return [child_pid] if test_process_is_running(child_pid, identity) else []

            with mock.patch.object(runner.ProcessTreeSupervisor, "start"), \
                    mock.patch.object(runner.ProcessTreeSupervisor, "stop", track_pipe_holder), \
                    mock.patch.object(runner.ProcessTreeSupervisor, "signal_active", return_value=[]), \
                    mock.patch.object(runner.ProcessTreeSupervisor, "verify_gone", side_effect=report_survivor), \
                    mock.patch.object(runner.os, "killpg") as killpg:
                result = runner.execute(
                    [sys.executable, "-c", child_program], self.root, "prompt", 0.1, 0.05
                )

            child_pid_text, child_identity = child_pid_file.read_text().splitlines()
            child_pid = int(child_pid_text)
            self.assertTrue(result[3], "pipe-holding descendant did not trigger timeout")
            killpg.assert_not_called()
            self.assertTrue(
                result[5]["process_group_signal_skipped_after_leader_exit"]
            )
            self.assertFalse(result[5]["descendant_termination_verified"])
            self.assertEqual(result[5]["descendants_surviving"], [child_pid])
            self.assertTrue(
                test_process_is_running(child_pid, child_identity),
                "fixture child should require its own cleanup",
            )
        finally:
            cleanup_test_process_file(child_pid_file, 3.0)

    def test_reviewers_accepts_codex_opus_subset_and_rejects_unknown_or_duplicates(self) -> None:
        self.executable("codex", "printf 'VERDICT: APPROVED\\nCOVERAGE: all\\n'\n")
        self.executable("claude", "printf 'VERDICT: APPROVED\\nCOVERAGE: all\\n'\n")

        for reviewers in ("", "codex,codex", "gemini"):
            result = self.invoke("--reviewers", reviewers)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("--reviewers", result.stderr)

    def test_single_reviewer_runs_one_clone_and_barrier_lane(self) -> None:
        self.executable("codex", "printf 'VERDICT: APPROVED\\nCOVERAGE: all\\n'\n")
        self.executable("claude", "touch \"$ADVICE_TEST_SYNC_DIR/unexpected-opus.ran\"\n")

        result = self.invoke("--reviewers", "codex")

        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads((self.output / "receipt.json").read_text())
        self.assertEqual(set(receipt["reviewers"]), {"codex"})
        self.assertEqual(receipt["clone_shas"], {"codex": self.sha})
        self.assertFalse(receipt["parallel_dispatch"])
        self.assertFalse(receipt["overlap_proven"])
        self.assertFalse((self.sync / "unexpected-opus.ran").exists())

    def test_opus_only_runs_only_opus_and_records_non_parallel_dispatch(self) -> None:
        self.executable("codex", "touch \"$ADVICE_TEST_SYNC_DIR/unexpected-codex.ran\"\n")
        self.executable(
            "claude",
            "printf '%s\\n' \"$@\" > \"$ADVICE_TEST_SYNC_DIR/opus.args\"\n"
            "printf 'VERDICT: APPROVED\\nCOVERAGE: all\\n'\n",
        )

        result = self.invoke("--reviewers", "opus")

        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads((self.output / "receipt.json").read_text())
        self.assertEqual(set(receipt["reviewers"]), {"opus"})
        self.assertEqual(receipt["clone_shas"], {"opus": self.sha})
        self.assertFalse(receipt["parallel_dispatch"])
        self.assertFalse(receipt["overlap_proven"])
        self.assertFalse((self.sync / "unexpected-codex.ran").exists())
        opus_args = (self.sync / "opus.args").read_text().splitlines()
        self.assertIn("--dangerously-skip-permissions", opus_args)
        self.assertIn("opus", opus_args)

    def test_rejects_reused_output_dir_before_subset_dispatch_and_preserves_receipts(self) -> None:
        self.executable(
            "codex",
            "touch \"$ADVICE_TEST_SYNC_DIR/codex.ran\"\n"
            "printf 'VERDICT: CODEX\\nCOVERAGE: all\\n'\n",
        )
        self.executable(
            "claude",
            "touch \"$ADVICE_TEST_SYNC_DIR/opus.ran\"\n"
            "printf 'VERDICT: OPUS\\nCOVERAGE: all\\n'\n",
        )

        first = self.invoke("--reviewers", "codex,opus")

        self.assertEqual(first.returncode, 0, first.stderr)
        original_files = {
            path.name: path.read_bytes() for path in self.output.iterdir()
        }
        second = self.invoke("--reviewers", "opus")

        self.assertEqual(second.returncode, 2, second.stderr)
        self.assertIn("fresh path", second.stderr.lower())
        self.assertEqual(
            {path.name: path.read_bytes() for path in self.output.iterdir()},
            original_files,
        )
        self.assertTrue((self.sync / "codex.ran").exists())
        self.assertEqual(
            len(list(self.sync.glob("opus.ran"))),
            1,
            "rejected subset rerun must not launch opus against stale output",
        )

    def test_runs_codex_and_opus_concurrently_in_independent_exact_sha_clones(self) -> None:
        peer_wait = """
touch "$ADVICE_TEST_SYNC_DIR/%s.started"
i=0
while [ ! -e "$ADVICE_TEST_SYNC_DIR/%s.started" ] && [ "$i" -lt 100 ]; do
  sleep 0.01
  i=$((i + 1))
done
[ -e "$ADVICE_TEST_SYNC_DIR/%s.started" ]
pwd > "$ADVICE_TEST_SYNC_DIR/%s.cwd"
printf 'VERDICT: APPROVED\\nCOVERAGE: all\\n'
"""
        self.executable("codex", peer_wait % ("codex", "opus", "opus", "codex"))
        self.executable("claude", peer_wait % ("opus", "codex", "codex", "opus"))

        result = self.invoke("--reviewers", "codex,opus")

        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads((self.output / "receipt.json").read_text())
        self.assertTrue(receipt["overlap_proven"])
        self.assertEqual(receipt["clone_shas"], {"codex": self.sha, "opus": self.sha})
        self.assertEqual(receipt["checkout_kind"], "independent_clone_no_local")
        self.assertEqual(receipt["reviewers"]["codex"]["status"], "success")
        self.assertEqual(receipt["reviewers"]["opus"]["status"], "success")
        self.assertNotEqual((self.sync / "codex.cwd").read_text(), (self.sync / "opus.cwd").read_text())
        self.assertEqual(receipt["original_checkout_unchanged"], True)

    def test_preserves_explicit_full_permission_flags_on_codex_and_opus(self) -> None:
        self.executable(
            "codex",
            "printf '%s\\n' \"$@\" > \"$ADVICE_TEST_SYNC_DIR/codex.args\"\n"
            "printf 'VERDICT: APPROVED\\nCOVERAGE: all\\n'\n",
        )
        self.executable(
            "claude",
            "printf '%s\\n' \"$@\" > \"$ADVICE_TEST_SYNC_DIR/opus.args\"\n"
            "printf 'VERDICT: APPROVED\\nCOVERAGE: all\\n'\n",
        )

        result = self.invoke()

        self.assertEqual(result.returncode, 0, result.stderr)
        codex_args = (self.sync / "codex.args").read_text().splitlines()
        opus_args = (self.sync / "opus.args").read_text().splitlines()
        self.assertIn("--yolo", codex_args)
        self.assertIn("gpt-6-sol", codex_args)
        self.assertIn("--dangerously-skip-permissions", opus_args)
        self.assertIn("opus", opus_args)

    def test_exit_zero_without_a_verdict_is_an_error_and_other_lane_can_succeed(self) -> None:
        self.executable("codex", "printf 'no structured verdict\\n'\n")
        self.executable("claude", "printf 'VERDICT: APPROVED\\nCOVERAGE: all\\n'\n")

        result = self.invoke()

        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads((self.output / "receipt.json").read_text())
        self.assertEqual(receipt["reviewers"]["codex"]["status"], "error")
        self.assertEqual(receipt["reviewers"]["codex"]["attempts"][0]["failure"], "missing_verdict")
        self.assertEqual(receipt["reviewers"]["opus"]["status"], "success")

    def test_fails_when_both_lanes_return_empty_or_malformed_output(self) -> None:
        self.executable("codex", "printf ''\n")
        self.executable("claude", "printf 'VERDICT:   \\n'\n")

        result = self.invoke()

        self.assertEqual(result.returncode, 4)
        self.assertIn("neither primary reviewer returned a verdict", result.stderr)
        receipt = json.loads((self.output / "receipt.json").read_text())
        self.assertEqual(receipt["reviewers"]["codex"]["status"], "error")
        self.assertEqual(receipt["reviewers"]["opus"]["status"], "error")

    def test_independent_clones_isolate_ref_and_config_mutations(self) -> None:
        mutation = (
            "git config reviewer.evil true\n"
            "git update-ref refs/heads/reviewer-evil HEAD\n"
            "printf 'VERDICT: APPROVED\\nCOVERAGE: all\\n'\n"
        )
        self.executable("codex", mutation)
        self.executable("claude", mutation)

        result = self.invoke()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotEqual(
            run("git", "config", "--get", "reviewer.evil", cwd=self.repo).returncode,
            0,
        )
        self.assertNotEqual(
            run("git", "show-ref", "--verify", "--quiet", "refs/heads/reviewer-evil", cwd=self.repo).returncode,
            0,
        )

    def test_document_review_accepts_all_git_states_without_changing_source(self) -> None:
        import shutil
        import hashlib
        doc = self.repo / "plan.md"
        doc.write_text("complete plan\n")
        self.executable("codex", "test \"$(cat .advice-review-documents/0.md)\" = \"complete plan\"\n"
                        "printf 'VERDICT: APPROVED\\nCOVERAGE: entire document\\n'\n")
        for state in ("untracked", "staged", "committed", "modified"):
            if state == "staged":
                run("git", "add", "plan.md", cwd=self.repo)
            if state == "committed":
                run("git", "commit", "-qm", "document", cwd=self.repo)
            if state == "modified":
                doc.write_text("older committed plan\n")
                run("git", "add", "plan.md", cwd=self.repo)
                run("git", "commit", "-qm", "older content", cwd=self.repo)
                doc.write_text("complete plan\n")
            self.sha = run("git", "rev-parse", "HEAD", cwd=self.repo).stdout.strip()
            before = run("git", "status", "--porcelain", cwd=self.repo).stdout
            result = self.invoke("--reviewers", "codex", "--document", "plan.md")
            self.assertEqual(0, result.returncode, (state, result.stderr))
            receipt = json.loads((self.output / "receipt.json").read_text())
            self.assertEqual("documents", receipt["review_kind"])
            self.assertEqual(hashlib.sha256(doc.read_bytes()).hexdigest(), receipt["document_hashes"]["plan.md"])
            self.assertEqual(before, run("git", "status", "--porcelain", cwd=self.repo).stdout)
            shutil.rmtree(self.output)

    def test_document_paths_refuse_escape_symlinks_and_ignored_files(self) -> None:
        (self.repo / "secret.md").write_text("not for review")
        (self.repo / ".gitignore").write_text("secret.md\n")
        (self.repo / "alias.md").symlink_to(self.repo / "tracked.txt")
        for index, name in enumerate(("../packet.md", "alias.md", "secret.md")):
            self.output = self.root / f"invalid-document-{index}"
            result = self.invoke("--document", name)
            self.assertEqual(2, result.returncode, result.stderr)
            receipt = json.loads((self.output / "receipt.json").read_text())
            self.assertFalse(receipt["operation"]["success"])
            self.assertNotIn("reviewers", receipt)

    def test_modified_reviewer_document_invalidates_review(self) -> None:
        (self.repo / "plan.md").write_text("original document")
        self.executable("codex", "printf 'changed' > .advice-review-documents/0.md\n"
                        "printf 'VERDICT: APPROVED\\nCOVERAGE: all\\n'\n")
        result = self.invoke("--reviewers", "codex", "--document", "plan.md")
        self.assertEqual(6, result.returncode, result.stderr)
        self.assertIn("review document copy changed", result.stderr)
        self.assertEqual("original document", (self.repo / "plan.md").read_text())

    def assert_completed_document_evidence_survives(self):
        receipt = json.loads((self.output / "receipt.json").read_text())
        self.assertFalse(receipt["operation"]["success"])
        self.assertTrue(receipt["cleanup"]["success"])
        self.assertEqual({"codex", "opus"}, set(receipt["reviewers"]))
        for name in ("codex", "opus"):
            self.assertIn("VERDICT:", (self.output / f"{name}.txt").read_text())
            self.assertGreater(receipt["reviewers"][name]["started_ns"], 0)
            self.assertGreaterEqual(
                receipt["reviewers"][name]["ended_monotonic_ns"],
                receipt["reviewers"][name]["started_monotonic_ns"],
            )

    def test_document_copy_mutation_preserves_completed_lanes(self):
        (self.repo / "plan.md").write_text("original document")
        self.executable("codex", "printf 'changed' > .advice-review-documents/0.md\n"
                        "printf 'VERDICT: APPROVED\\nCOVERAGE: all\\n'\n")
        self.executable("claude", "printf 'VERDICT: APPROVED\\nCOVERAGE: all\\n'\n")
        result = self.invoke("--reviewers", "codex,opus", "--document", "plan.md")
        self.assertEqual(6, result.returncode, result.stderr)
        self.assertIn("review document copy changed", result.stderr)
        self.assert_completed_document_evidence_survives()

    def test_source_document_mutation_preserves_completed_lanes(self):
        (self.repo / "plan.md").write_text("original document")
        self.env["ADVICE_TEST_ORIGINAL_REPO"] = str(self.repo)
        self.executable("codex", 'printf "changed" > "$ADVICE_TEST_ORIGINAL_REPO/plan.md"\n'
                        "printf 'VERDICT: APPROVED\\nCOVERAGE: all\\n'\n")
        self.executable("claude", "printf 'VERDICT: APPROVED\\nCOVERAGE: all\\n'\n")
        result = self.invoke("--reviewers", "codex,opus", "--document", "plan.md")
        self.assertEqual(6, result.returncode, result.stderr)
        self.assertIn("source documents changed", result.stderr)
        self.assert_completed_document_evidence_survives()

    def test_refuses_dirty_input_checkout_before_dispatch(self) -> None:
        (self.repo / "untracked.txt").write_text("not represented by the SHA\n")
        self.executable("codex", "touch \"$ADVICE_TEST_SYNC_DIR/codex.ran\"\n")
        self.executable("claude", "touch \"$ADVICE_TEST_SYNC_DIR/opus.ran\"\n")

        result = self.invoke()

        self.assertEqual(result.returncode, 2)
        self.assertIn("input checkout must be clean", result.stderr.lower())
        self.assertFalse((self.sync / "codex.ran").exists())
        self.assertFalse((self.sync / "opus.ran").exists())

    def test_refuses_tracked_input_changes_before_dispatch(self) -> None:
        (self.repo / "tracked.txt").write_text("dirty tracked state\n")
        self.executable("codex", "touch \"$ADVICE_TEST_SYNC_DIR/codex.ran\"\n")
        self.executable("claude", "touch \"$ADVICE_TEST_SYNC_DIR/opus.ran\"\n")

        result = self.invoke()

        self.assertEqual(result.returncode, 2)
        self.assertIn("input checkout must be clean", result.stderr.lower())
        self.assertFalse((self.sync / "codex.ran").exists())
        self.assertFalse((self.sync / "opus.ran").exists())

    def test_fails_closed_when_original_checkout_changes(self) -> None:
        self.env["ADVICE_TEST_ORIGINAL_REPO"] = str(self.repo)
        self.executable(
            "codex",
            "printf 'mutated\\n' >> \"$ADVICE_TEST_ORIGINAL_REPO/tracked.txt\"\n"
            "printf 'VERDICT: APPROVED\\nCOVERAGE: all\\n'\n",
        )
        self.executable("claude", "printf 'VERDICT: APPROVED\\nCOVERAGE: all\\n'\n")

        result = self.invoke()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("original checkout or repository metadata changed", result.stderr.lower())
        receipt = json.loads((self.output / "receipt.json").read_text())
        self.assertEqual(receipt["original_checkout_unchanged"], False)

    def test_fails_closed_when_an_ignored_file_changes_without_reading_its_content(self) -> None:
        (self.repo / ".gitignore").write_text(".env\n")
        run("git", "add", ".gitignore", cwd=self.repo)
        run("git", "commit", "-qm", "ignore local environment", cwd=self.repo)
        self.sha = run("git", "rev-parse", "HEAD", cwd=self.repo).stdout.strip()
        ignored = self.repo / ".env"
        ignored.write_text("SECRET=do-not-read\n")
        self.env["ADVICE_TEST_IGNORED_FILE"] = str(ignored)
        self.executable(
            "codex",
            "printf 'ordinary ignored-file mutation with a new size\\n' > \"$ADVICE_TEST_IGNORED_FILE\"\n"
            "printf 'VERDICT: APPROVED\\nCOVERAGE: all\\n'\n",
        )
        self.executable("claude", "printf 'VERDICT: APPROVED\\nCOVERAGE: all\\n'\n")

        result = self.invoke()

        self.assertEqual(result.returncode, 3)
        self.assertIn("original checkout or repository metadata changed", result.stderr.lower())
        receipt = json.loads((self.output / "receipt.json").read_text())
        self.assertEqual(receipt["original_repository_unchanged"], False)

    def test_ignored_file_fingerprint_does_not_require_content_access(self) -> None:
        (self.repo / ".gitignore").write_text(".env\n")
        run("git", "add", ".gitignore", cwd=self.repo)
        run("git", "commit", "-qm", "ignore local environment", cwd=self.repo)
        self.sha = run("git", "rev-parse", "HEAD", cwd=self.repo).stdout.strip()
        ignored = self.repo / ".env"
        ignored.write_text("SECRET=do-not-read\n")
        ignored.chmod(0)
        self.executable("codex", "printf 'VERDICT: APPROVED\\nCOVERAGE: all\\n'\n")
        self.executable("claude", "printf 'VERDICT: APPROVED\\nCOVERAGE: all\\n'\n")

        try:
            result = self.invoke()
        finally:
            ignored.chmod(0o600)

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_effective_hooks_path_detects_dangling_symlink_target_change(self) -> None:
        hooks = self.root / "configured-hooks"
        hooks.mkdir()
        hook = hooks / "pre-commit"
        hook.symlink_to("missing-hook-v1")
        run("git", "config", "core.hooksPath", str(hooks), cwd=self.repo)
        self.env["ADVICE_TEST_HOOK"] = str(hook)
        self.executable(
            "codex",
            "rm \"$ADVICE_TEST_HOOK\"\n"
            "ln -s missing-hook-v2 \"$ADVICE_TEST_HOOK\"\n"
            "printf 'VERDICT: APPROVED\\nCOVERAGE: all\\n'\n",
        )
        self.executable("claude", "printf 'VERDICT: APPROVED\\nCOVERAGE: all\\n'\n")

        result = self.invoke()

        self.assertEqual(result.returncode, 3)
        self.assertIn("repository metadata changed", result.stderr)

    def test_one_timed_out_lane_is_error_while_peer_succeeds(self) -> None:
        self.executable("codex", "exec sleep 2\n")
        self.executable("claude", "printf 'VERDICT: APPROVED\\nCOVERAGE: all\\n'\n")

        started = time.monotonic()
        result = self.invoke("--timeout-seconds", "0.5")
        elapsed = time.monotonic() - started

        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads((self.output / "receipt.json").read_text())
        codex_duration = (
            receipt["reviewers"]["codex"]["ended_monotonic_ns"]
            - receipt["reviewers"]["codex"]["started_monotonic_ns"]
        ) / 1_000_000_000
        self.assertLess(codex_duration, 1.5)
        self.assertEqual(receipt["reviewers"]["codex"]["status"], "error")
        self.assertEqual(receipt["reviewers"]["codex"]["attempts"][0]["failure"], "timeout")
        self.assertEqual(receipt["reviewers"]["opus"]["status"], "success")
        self.assertTrue(receipt["cleanup"]["success"])

    @unittest.skipUnless(sys.platform.startswith("linux"), "requires Linux pidfd supervision")
    def test_reaped_timed_out_lane_with_verified_descendant_keeps_peer_vote(self) -> None:
        runner = load_runner_module()
        child_file = self.sync / "late-child.pid"
        sample_marker = self.sync / "supervisor-observed-child"
        reviewer_code = (
            "python3 - <<'PY'\n"
            "import os, pathlib, subprocess, sys, time\n"
            "sync = pathlib.Path(os.environ['ADVICE_TEST_SYNC_DIR'])\n"
            "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'], start_new_session=True)\n"
            "proc = pathlib.Path(f'/proc/{child.pid}/stat')\n"
            "fields = proc.read_text().rsplit(')', 1)[1].split()\n"
            "identity = f'linux-start-ticks:{fields[19]}'\n"
            "(sync / 'late-child.pid').write_text(f'{child.pid}\\n{identity}')\n"
            "deadline = time.monotonic() + 2\n"
            "while not (sync / 'supervisor-observed-child').exists() and time.monotonic() < deadline:\n"
            " time.sleep(0.01)\n"
            "if not (sync / 'supervisor-observed-child').exists():\n"
            " raise SystemExit(9)\n"
            "print('VERDICT: APPROVED', flush=True)\n"
            "print('COVERAGE: all', flush=True)\n"
            "PY\n"
        )
        self.executable("codex", reviewer_code)
        self.executable("claude", "printf 'VERDICT: APPROVED\\nCOVERAGE: all\\n'\n")
        argv = self.with_queued_timestamps([
            "--repo", str(self.repo), "--ref", self.sha,
            "--packet-file", str(self.packet), "--output-dir", str(self.output),
            "--timeout-seconds", "1.5", "--attempt-timeout-seconds", "10",
            "--cleanup-budget-seconds", "1", "--timeout-grace-seconds", "0.5",
        ])
        original_sample = runner.ProcessTreeSupervisor._sample

        def sample_and_mark_child(supervisor) -> None:
            original_sample(supervisor)
            if child_file.exists():
                child_text, child_identity = child_file.read_text().splitlines()
                child_pid = int(child_text)
                if supervisor.discovered.get(child_pid) == child_identity:
                    sample_marker.touch(exist_ok=True)

        try:
            with mock.patch.dict(os.environ, self.env), mock.patch.object(
                runner.ProcessTreeSupervisor, "_sample", sample_and_mark_child
            ), mock.patch.object(runner.os, "killpg") as killpg:
                code = runner.main(argv)
                killpg.assert_not_called()

            receipt = json.loads((self.output / "receipt.json").read_text())
            self.assertEqual(code, 0, repr(receipt))
            self.assertTrue(sample_marker.exists(), "supervisor never observed the detached child")
            child_text, child_identity = child_file.read_text().splitlines()
            child_pid = int(child_text)
            codex = receipt["reviewers"]["codex"]
            attempt = codex["attempts"][0]
            self.assertEqual(attempt["failure"], "timeout")
            self.assertTrue(attempt["reviewer_leader_reaped"])
            self.assertTrue(attempt["process_group_signal_skipped_after_leader_exit"])
            self.assertTrue(attempt["descendant_termination_verified"])
            self.assertEqual(receipt["descendant_termination_failures"], [])
            self.assertEqual(receipt["reviewers"]["opus"]["status"], "success")
            self.assertTrue(wait_for_test_process_exit(child_pid, child_identity, 2))
        finally:
            cleanup_test_process_file(child_file, 3.0)

    def test_attempt_budget_labels_limited_lane_and_keeps_timely_peer_vote(self) -> None:
        runner = load_runner_module()
        self.executable("codex", "exit 0\n")
        self.executable("claude", "exit 0\n")
        argv = self.with_queued_timestamps([
            "--repo", str(self.repo), "--ref", self.sha,
            "--packet-file", str(self.packet), "--output-dir", str(self.output),
            "--attempt-timeout-seconds", "10", "--cleanup-budget-seconds", "0.2",
            "--timeout-grace-seconds", "0.1", "--timeout-seconds", "10",
        ])

        def deterministic_execute(command, cwd, prompt, timeout_seconds, timeout_grace_seconds, *, deadline=None):
            supervision = {
                "descendant_termination_verified": True,
                "reviewer_leader_reaped": True,
                "descendants_surviving": [],
            }
            if Path(command[0]).name == "codex":
                return -signal.SIGKILL, "", "", True, False, supervision
            return 0, "VERDICT: APPROVED\nCOVERAGE: all\n", "", False, False, supervision

        with mock.patch.dict(os.environ, self.env), mock.patch.object(
            runner, "execute", side_effect=deterministic_execute
        ), mock.patch.object(
            runner, "resolve_review_scratch_root", return_value=self.scratch
        ):
            code = runner.main(argv)

        receipt = json.loads((self.output / "receipt.json").read_text())
        self.assertEqual(code, 0)
        self.assertFalse(receipt["attempt_deadline_exceeded"])
        self.assertEqual(receipt["reviewers"]["codex"]["status"], "error")
        self.assertEqual(receipt["reviewers"]["codex"]["attempts"][0]["failure"], "attempt_timeout")
        self.assertEqual(receipt["reviewers"]["opus"]["status"], "success")
        self.assertTrue(receipt["cleanup"]["success"])

    def test_both_timed_out_lanes_exit_four_and_still_cleanup(self) -> None:
        self.executable("codex", "exec sleep 2\n")
        self.executable("claude", "exec sleep 2\n")

        result = self.invoke("--timeout-seconds", "0.5")

        self.assertEqual(result.returncode, 4)
        receipt = json.loads((self.output / "receipt.json").read_text())
        self.assertEqual(receipt["reviewers"]["codex"]["attempts"][0]["failure"], "timeout")
        self.assertEqual(receipt["reviewers"]["opus"]["attempts"][0]["failure"], "timeout")
        self.assertTrue(receipt["cleanup"]["success"])

    @unittest.skipUnless(
        sys.platform.startswith("linux"), "requires Linux pidfd supervision"
    )
    def test_normal_exit_terminates_discovered_detached_descendant(self) -> None:
        runner = load_runner_module()
        child_file = self.sync / "normal-exit-child.pid"
        sample_marker = self.sync / "normal-exit-child-observed"
        reviewer_code = (
            "python3 - <<'PY'\n"
            "import os, pathlib, subprocess, sys, time\n"
            "sync = pathlib.Path(os.environ['ADVICE_TEST_SYNC_DIR'])\n"
            "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'], "
            "start_new_session=True, stdin=subprocess.DEVNULL, "
            "stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
            "proc = pathlib.Path(f'/proc/{child.pid}/stat')\n"
            "fields = proc.read_text().rsplit(')', 1)[1].split()\n"
            "identity = f'linux-start-ticks:{fields[19]}'\n"
            "(sync / 'normal-exit-child.pid').write_text(f'{child.pid}\\n{identity}')\n"
            "deadline = time.monotonic() + 2\n"
            "while not (sync / 'normal-exit-child-observed').exists() and time.monotonic() < deadline:\n"
            " time.sleep(0.01)\n"
            "if not (sync / 'normal-exit-child-observed').exists():\n"
            " raise SystemExit(9)\n"
            "print('VERDICT: APPROVED', flush=True)\n"
            "print('COVERAGE: all', flush=True)\n"
            "PY\n"
        )
        self.executable("codex", reviewer_code)
        self.executable("claude", "printf 'VERDICT: APPROVED\\nCOVERAGE: all\\n'\\n")
        original_sample = runner.ProcessTreeSupervisor._sample

        def sample_and_mark_child(supervisor) -> None:
            original_sample(supervisor)
            if child_file.exists():
                child_text, child_identity = child_file.read_text().splitlines()
                if supervisor.discovered.get(int(child_text)) == child_identity:
                    sample_marker.touch(exist_ok=True)

        try:
            with mock.patch.dict(os.environ, self.env), mock.patch.object(
                runner.ProcessTreeSupervisor, "_sample", sample_and_mark_child
            ):
                code = runner.main(self.with_queued_timestamps([
                    "--repo", str(self.repo), "--ref", self.sha,
                    "--packet-file", str(self.packet), "--output-dir", str(self.output),
                    "--timeout-seconds", "5",
                ]))

            child_text, child_identity = child_file.read_text().splitlines()
            child_pid = int(child_text)
            receipt = json.loads((self.output / "receipt.json").read_text())
            attempt = receipt["reviewers"]["codex"]["attempts"][0]
            self.assertEqual(code, 0, repr(receipt))
            self.assertTrue(sample_marker.exists())
            self.assertIn(child_pid, attempt["descendants_terminated"])
            self.assertTrue(attempt["descendant_termination_verified"])
            self.assertTrue(wait_for_test_process_exit(child_pid, child_identity, 2))
        finally:
            cleanup_test_process_file(child_file, 3.0)

    def test_detached_descendant_pipe_cannot_extend_timeout_beyond_bounded_grace(self) -> None:
        self.executable(
            "codex",
            "python3 - \"$ADVICE_TEST_SYNC_DIR/detached.pid\" <<'PY'\n"
            "import pathlib, subprocess, sys, time\n"
            "child = subprocess.Popen(['sleep', '3'], start_new_session=True)\n"
            "try:\n"
            " proc = pathlib.Path(f'/proc/{child.pid}/stat')\n"
            " if proc.exists():\n"
            "  fields = proc.read_text().rsplit(')', 1)[1].split()\n"
            "  identity = f'linux-start-ticks:{fields[19]}'\n"
            " else:\n"
            "  identity = subprocess.run(['ps', '-o', 'lstart=', '-p', str(child.pid)], capture_output=True, text=True, check=True).stdout.strip()\n"
            " if not identity:\n"
            "  raise RuntimeError('child identity unavailable')\n"
            " pathlib.Path(sys.argv[1]).write_text(f'{child.pid}\\n{identity}')\n"
            "except BaseException:\n"
            " child.kill()\n"
            " child.wait()\n"
            " raise\n"
            "time.sleep(1)\n"
            "PY\n"
            "exec sleep 8\n",
        )
        self.executable("claude", "printf 'VERDICT: APPROVED\\nCOVERAGE: all\\n'\n")

        detached_pid_file = self.sync / "detached.pid"
        try:
            started = time.monotonic()
            result = self.invoke(
                "--timeout-seconds", "1.5", "--timeout-grace-seconds", "0.8"
            )
            elapsed = time.monotonic() - started

            detached_pid_text, detached_identity = detached_pid_file.read_text().splitlines()
            detached_pid = int(detached_pid_text)
            self.assertLess(elapsed, 6.0)
            receipt = json.loads((self.output / "receipt.json").read_text())
            codex_result = receipt["reviewers"]["codex"]
            attempt = codex_result["attempts"][0]
            attempt_duration = (
                codex_result["ended_monotonic_ns"]
                - codex_result["started_monotonic_ns"]
            ) / 1_000_000_000
            self.assertLess(attempt_duration, 6.0)
            self.assertEqual(attempt["failure"], "timeout")
            self.assertIsInstance(attempt["forced_pipe_close"], bool)
            pidfd_supported = callable(getattr(os, "pidfd_open", None)) and callable(
                getattr(signal, "pidfd_send_signal", None)
            )
            self.assertIn(detached_pid, attempt["descendants_discovered"])
            if pidfd_supported:
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(detached_pid, attempt["descendants_terminated"])
                self.assertTrue(attempt["descendant_termination_verified"])
                self.assertEqual(attempt["descendants_surviving"], [])
            else:
                self.assertEqual(result.returncode, 7, result.stderr)
                self.assertNotIn(detached_pid, attempt["descendants_terminated"])
                self.assertFalse(attempt["descendant_termination_verified"])
                self.assertIn(detached_pid, attempt["descendants_surviving"])
            self.assertTrue(receipt["cleanup"]["success"])
        finally:
            cleanup_test_process_file(detached_pid_file, 4.0)

    def test_timeout_grace_must_be_positive(self) -> None:
        result = self.invoke("--timeout-grace-seconds", "0")

        self.assertEqual(result.returncode, 2)
        self.assertIn("--timeout-grace-seconds must be greater than zero", result.stderr)

    def test_verdict_value_does_not_require_separator_whitespace(self) -> None:
        runner = load_runner_module()

        self.assertTrue(runner.has_verdict("VERDICT:APPROVED\n"))
        self.assertFalse(runner.has_verdict("VERDICT:   \n"))

    def test_cleanup_helper_reports_failure_instead_of_ignoring_it(self) -> None:
        runner = load_runner_module()
        disposable = self.root / "disposable"
        disposable.mkdir()

        with mock.patch.object(runner.shutil, "rmtree", side_effect=OSError("fixture denied")):
            cleanup = runner.cleanup_directory(disposable)

        self.assertEqual(cleanup["success"], False)
        self.assertIn("fixture denied", cleanup["error"])
        self.assertEqual(cleanup["path"], str(disposable))

    def test_operation_and_cleanup_failure_records_both_and_cleanup_exit_wins(self) -> None:
        runner = load_runner_module()
        argv = [
            "--repo", str(self.repo), "--ref", self.sha,
            "--packet-file", str(self.packet), "--output-dir", str(self.output),
        ]
        cleanup = {"success": False, "error": "cleanup denied", "path": "/fixture"}
        def cleanup_failure(path):
            runner.cleanup_directory(path)
            return cleanup
        stderr = io.StringIO()

        with mock.patch.dict(runner.os.environ, {
            "DISK_MAGICIAN_DISKM_BIN": str(self.bin / "diskm"),
            "ADVICE_TEST_SCRATCH": str(self.scratch),
        }), redirect_stderr(stderr):
            code = runner.main(
                self.with_queued_timestamps(argv),
                create_clone_fn=mock.Mock(side_effect=RuntimeError("clone setup failed")),
                cleanup_fn=mock.Mock(side_effect=cleanup_failure),
            )

        self.assertEqual(code, 5)
        receipt = json.loads((self.output / "receipt.json").read_text())
        self.assertEqual(receipt["operation"]["success"], False)
        self.assertIn("clone setup failed", receipt["operation"]["error"])
        self.assertEqual(receipt["cleanup"], cleanup)
        self.assertIn("failed to clean disposable clones", stderr.getvalue())

    def test_clone_setup_uses_attempt_budget_and_stops_before_review(self) -> None:
        runner = load_runner_module()
        argv = [
            "--repo", str(self.repo), "--ref", self.sha,
            "--packet-file", str(self.packet), "--output-dir", str(self.output),
            "--reviewers", "codex", "--attempt-timeout-seconds", "1.0",
            "--cleanup-budget-seconds", "0.1",
            "--timeout-grace-seconds", "0.05",
        ]
        observed = {}
        def slow_clone(source, destination, sha, *, deadline):
            remaining = deadline - time.monotonic()
            observed["timeout_seconds"] = remaining
            time.sleep(min(0.15, remaining))
            raise subprocess.TimeoutExpired(["git", "clone"], remaining)
        stderr = io.StringIO()

        with mock.patch.object(
            runner, "resolve_review_scratch_root", return_value=self.scratch
        ), redirect_stderr(stderr):
            code = runner.main(self.with_queued_timestamps(argv), create_clone_fn=slow_clone)

        self.assertEqual(code, 4)
        self.assertLessEqual(observed["timeout_seconds"], 0.91)
        receipt = json.loads((self.output / "receipt.json").read_text())
        self.assertFalse(receipt["operation"]["success"])
        self.assertIn("TimeoutExpired", receipt["operation"]["error"])
        self.assertEqual(receipt["timeout_stage"], "clone_setup")
        self.assertFalse(receipt["setup_process_cleanup_verified"])
        self.assertTrue(receipt["cleanup"]["success"])
        self.assertFalse(receipt["reviewers"] if "reviewers" in receipt else False)

    def test_missing_queued_timestamp_cannot_produce_a_countable_vote(self) -> None:
        self.executable("codex", "printf 'VERDICT: APPROVED\\nCOVERAGE: all\\n'\n")

        result = self.invoke_raw("--reviewers", "codex")

        self.assertNotEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.output.exists())

    def test_epoch_timestamp_alone_cannot_produce_a_countable_vote(self) -> None:
        self.executable("codex", "printf 'VERDICT: APPROVED\\nCOVERAGE: all\\n'\n")

        result = self.invoke_raw(
            "--reviewers", "codex", "--queued-at-epoch-ns", str(time.time_ns())
        )

        self.assertNotEqual(result.returncode, 0, result.stderr)
        self.assertIn("--queued-at-monotonic-ns", result.stderr)
        self.assertFalse(self.output.exists())

    def test_future_monotonic_queue_timestamp_is_rejected(self) -> None:
        self.executable("codex", "printf 'VERDICT: APPROVED\\nCOVERAGE: all\\n'\n")
        argv = self.with_queued_timestamps([
            "--repo", str(self.repo), "--ref", self.sha,
            "--packet-file", str(self.packet), "--output-dir", str(self.output),
            "--queued-at-monotonic-ns", str(time.monotonic_ns() + 10_000_000_000),
        ])

        result = self.invoke_raw(*argv)

        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("no later than now on this host", result.stderr)
        self.assertFalse(self.output.exists())

    def test_wall_clock_step_before_runner_does_not_reject_monotonic_queue(self) -> None:
        runner = load_runner_module()
        self.executable("codex", "printf 'VERDICT: APPROVED\\nCOVERAGE: all\\n'\n")
        self.executable("claude", "printf 'VERDICT: APPROVED\\nCOVERAGE: all\\n'\n")
        argv = self.with_queued_timestamps([
            "--repo", str(self.repo), "--ref", self.sha,
            "--packet-file", str(self.packet), "--output-dir", str(self.output),
            "--reviewers", "codex,opus", "--attempt-timeout-seconds", "5",
            "--cleanup-budget-seconds", "0.5",
            "--timeout-grace-seconds", "0.05", "--timeout-seconds", "10",
            "--queued-at-epoch-ns", "1000100000",
        ])
        supervision = {
            "descendant_termination_verified": True,
            "reviewer_leader_reaped": True,
            "descendants_surviving": [],
        }
        with mock.patch.dict(os.environ, self.env), mock.patch.object(
            runner.time, "time_ns", return_value=999100000
        ), mock.patch.object(
            runner, "execute",
            return_value=(
                0, "VERDICT: APPROVED\\nCOVERAGE: all\\n", "", False, False,
                supervision,
            ),
        ):
            code = runner.main(argv)

        receipt = json.loads((self.output / "receipt.json").read_text())
        self.assertEqual(code, 0, repr(receipt))
        self.assertFalse(receipt["attempt_deadline_exceeded"])
        self.assertTrue(all(
            result["status"] == "success"
            for result in receipt["reviewers"].values()
        ))

    def test_queued_timestamp_consumes_attempt_budget_before_process_entry(self) -> None:
        self.executable("codex", "printf 'VERDICT: APPROVED\\nCOVERAGE: all\\n'\n")
        queued_at_ns = time.time_ns() - 1_000_000_000
        queued_at_monotonic_ns = time.monotonic_ns() - 1_000_000_000
        started = time.monotonic()
        result = self.invoke(
            "--queued-at-epoch-ns", str(queued_at_ns),
            "--queued-at-monotonic-ns", str(queued_at_monotonic_ns),
            "--attempt-timeout-seconds", "0.5",
            "--cleanup-budget-seconds", "0.1",
        )

        self.assertEqual(result.returncode, 4, result.stderr)
        self.assertLess(time.monotonic() - started, 0.5)
        self.assertTrue(self.output.is_dir())
        receipt = json.loads((self.output / "receipt.json").read_text())
        self.assertEqual(receipt["timeout_stage"], "preflight")
        self.assertTrue(receipt["attempt_deadline_exceeded"])
        self.assertFalse(receipt["operation"]["success"])

    def test_successful_lane_with_unverified_supervision_is_not_countable(self) -> None:
        runner = load_runner_module()
        argv = self.with_queued_timestamps([
            "--repo", str(self.repo), "--ref", self.sha,
            "--packet-file", str(self.packet), "--output-dir", str(self.output),
            "--reviewers", "codex",
        ])
        now = time.monotonic_ns()
        review = {
            "status": "success",
            "transport": "test",
            "stdout": "VERDICT: APPROVED\nCOVERAGE: all\n",
            "attempts": [{
                "exit_code": 0,
                "failure": None,
                "descendant_termination_verified": False,
                "reviewer_leader_reaped": True,
                "descendant_supervision_errors": ["ps timed out"],
            }],
            "started_ns": time.time_ns(),
            "ended_ns": time.time_ns(),
            "started_monotonic_ns": now,
            "ended_monotonic_ns": now,
        }
        with mock.patch.object(
            runner, "resolve_review_scratch_root", return_value=self.scratch
        ), mock.patch.object(runner, "codex_lane", return_value=review):
            code = runner.main(argv)

        receipt = json.loads((self.output / "receipt.json").read_text())
        self.assertEqual(receipt["descendant_termination_failures"], ["codex"])
        self.assertEqual(code, 7)

    def test_review_execution_budget_uses_absolute_deadline_after_delayed_thread_start(self) -> None:
        runner = load_runner_module()
        self.executable("codex", "exit 0\n")
        self.executable("claude", "exit 0\n")
        queued_at_ns = time.time_ns()
        queued_at_monotonic_ns = time.monotonic_ns()
        argv = [
            "--repo", str(self.repo), "--ref", self.sha,
            "--packet-file", str(self.packet), "--output-dir", str(self.output),
            "--attempt-timeout-seconds", "4", "--cleanup-budget-seconds", "0.1",
            "--timeout-grace-seconds", "0.1", "--queued-at-epoch-ns", str(queued_at_ns),
            "--queued-at-monotonic-ns", str(queued_at_monotonic_ns),
        ]
        original_executor = runner.concurrent.futures.ThreadPoolExecutor
        release = threading.Event()
        both_ready = threading.Event()
        ready_count = 0
        ready_lock = threading.Lock()
        recorded_timeouts = []
        codes = []

        class DelayedStartExecutor(original_executor):
            def submit(self, function, *args, **kwargs):
                def gated_call(*call_args, **call_kwargs):
                    nonlocal ready_count
                    with ready_lock:
                        ready_count += 1
                        if ready_count == 2:
                            both_ready.set()
                    release.wait(timeout=2)
                    return function(*call_args, **call_kwargs)
                return super().submit(gated_call, *args, **kwargs)

        def instant_execute(command, cwd, prompt, timeout_seconds, timeout_grace_seconds, *, deadline=None):
            recorded_timeouts.append((time.monotonic_ns(), timeout_seconds))
            return 0, "VERDICT: APPROVED\nCOVERAGE: all\n", "", False, False, {
                "descendant_termination_verified": True,
                "reviewer_leader_reaped": True,
                "descendants_surviving": [],
            }

        def run_main():
            codes.append(runner.main(argv))

        with mock.patch.dict(os.environ, self.env), mock.patch.object(
            runner.concurrent.futures, "ThreadPoolExecutor", DelayedStartExecutor
        ), mock.patch.object(runner, "execute", side_effect=instant_execute), mock.patch.object(
            runner, "resolve_review_scratch_root", return_value=self.scratch
        ):
            worker = threading.Thread(target=run_main)
            worker.start()
            self.assertTrue(both_ready.wait(timeout=2), "review lanes did not reach the test gate")
            time.sleep(0.3)
            release.set()
            worker.join(timeout=2)

        self.assertFalse(worker.is_alive())
        self.assertEqual(codes, [0])
        self.assertEqual(len(recorded_timeouts), 2)
        for completed_ns, timeout_seconds in recorded_timeouts:
            remaining = 4 - 0.1 - 0.1 - (
                completed_ns - queued_at_monotonic_ns
            ) / 1_000_000_000
            self.assertLessEqual(timeout_seconds, remaining + 0.03)

    def test_codex_lane_dispatch_barrier_wait_is_bounded_by_lane_budget(self) -> None:
        runner = load_runner_module()
        barrier = threading.Barrier(2)
        result = []
        worker = threading.Thread(
            target=lambda: result.append(
                runner.codex_lane(
                    Path("."), "prompt", barrier, time.monotonic() + 0.05, 0.01
                )
            ),
            daemon=True,
        )

        worker.start()
        worker.join(timeout=0.5)

        self.assertFalse(worker.is_alive(), "reviewer lane waited forever at its barrier")
        self.assertEqual(result[0]["status"], "error")
        self.assertEqual(result[0]["attempts"][0]["failure"], "dispatch_timeout")

    def test_second_submit_failure_releases_first_reviewer_waiting_at_barrier(self) -> None:
        runner = load_runner_module()
        argv = self.with_queued_timestamps([
            "--repo", str(self.repo), "--ref", self.sha,
            "--packet-file", str(self.packet), "--output-dir", str(self.output),
            "--reviewers", "codex,opus", "--attempt-timeout-seconds", "60",
            "--cleanup-budget-seconds", "1", "--timeout-seconds", "30",
        ])
        original_executor = runner.concurrent.futures.ThreadPoolExecutor
        original_barrier = runner.threading.Barrier
        barriers = []
        codes = []
        errors = []

        class FailSecondSubmit(original_executor):
            submissions = 0

            def submit(self, *args, **kwargs):
                self.submissions += 1
                if self.submissions == 2:
                    raise RuntimeError("simulated second worker start failure")
                return super().submit(*args, **kwargs)

        def capture_barrier(parties):
            barrier = original_barrier(parties)
            barriers.append(barrier)
            return barrier

        def run_main():
            try:
                codes.append(runner.main(argv))
            except BaseException as error:
                errors.append(error)

        worker = threading.Thread(target=run_main)
        with mock.patch.object(
            runner, "resolve_review_scratch_root", return_value=self.scratch
        ), mock.patch.object(
            runner.concurrent.futures, "ThreadPoolExecutor", FailSecondSubmit
        ), mock.patch.object(runner.threading, "Barrier", side_effect=capture_barrier):
            worker.start()
            worker.join(timeout=5)
            completed_without_external_abort = not worker.is_alive()
            if worker.is_alive() and barriers:
                barriers[0].abort()
                worker.join(timeout=2)

        self.assertTrue(
            completed_without_external_abort,
            "runner shutdown waited on a reviewer that was never paired at the barrier",
        )
        self.assertFalse(errors)
        self.assertEqual(codes, [6])

    def test_reviewer_dispatch_deadline_is_admitted_for_all_lanes_before_submit(self) -> None:
        runner = load_runner_module()
        with mock.patch.object(runner.time, "monotonic", side_effect=[9.5, 10.0]):
            with self.assertRaisesRegex(TimeoutError, "before reviewer dispatch"):
                runner.reviewer_deadlines(["codex", "opus"], 10.0, 5.0, 0.1)

    def test_work_cutoff_invalidates_only_lane_that_finishes_after_cutoff(self) -> None:
        runner = load_runner_module()
        self.executable("codex", "exit 0\n")
        self.executable("claude", "exit 0\n")
        queued_at_ns = time.time_ns()
        attempt_timeout = 5.0
        cleanup_budget = 0.6
        argv = self.with_queued_timestamps([
            "--repo", str(self.repo), "--ref", self.sha,
            "--packet-file", str(self.packet), "--output-dir", str(self.output),
            "--attempt-timeout-seconds", str(attempt_timeout),
            "--cleanup-budget-seconds", str(cleanup_budget),
            "--timeout-grace-seconds", "0.05", "--timeout-seconds", "10",
        ])
        recorded = {}
        supervision = {
            "descendant_termination_verified": True,
            "reviewer_leader_reaped": True,
            "descendants_surviving": [],
        }

        def boundary_execute(command, cwd, prompt, timeout_seconds, timeout_grace_seconds, *, deadline=None):
            if Path(command[0]).name == "codex":
                work_deadline_ns = queued_at_ns + int(
                    (attempt_timeout - cleanup_budget) * 1_000_000_000
                )
                time.sleep(max(0, (work_deadline_ns - time.time_ns()) / 1_000_000_000) + 0.01)
                recorded["codex_end_ns"] = time.time_ns()
                return -signal.SIGKILL, "", "", True, False, supervision
            return 0, "VERDICT: APPROVED\nCOVERAGE: all\n", "", False, False, supervision

        with mock.patch.dict(os.environ, self.env), mock.patch.object(
            runner, "execute", side_effect=boundary_execute
        ), mock.patch.object(
            runner, "resolve_review_scratch_root", return_value=self.scratch
        ):
            code = runner.main(argv)

        receipt = json.loads((self.output / "receipt.json").read_text())
        self.assertLess(recorded["codex_end_ns"], queued_at_ns + int(attempt_timeout * 1_000_000_000))
        self.assertEqual(code, 0)
        self.assertFalse(receipt["attempt_deadline_exceeded"])
        self.assertEqual(receipt["reviewers"]["codex"]["status"], "error")
        self.assertEqual(receipt["reviewers"]["opus"]["status"], "success")

    def test_wall_clock_step_back_does_not_make_late_lane_timely(self) -> None:
        runner = load_runner_module()
        self.executable("codex", "exit 0\n")
        self.executable("claude", "exit 0\n")
        queued_at_monotonic_ns = time.monotonic_ns()
        attempt_timeout = 10.0
        cleanup_budget = 5.0
        argv = [
            "--repo", str(self.repo), "--ref", self.sha,
            "--packet-file", str(self.packet), "--output-dir", str(self.output),
            "--attempt-timeout-seconds", str(attempt_timeout),
            "--cleanup-budget-seconds", str(cleanup_budget),
            "--timeout-grace-seconds", "0.05", "--timeout-seconds", "10",
            "--queued-at-epoch-ns", "1000000000",
            "--queued-at-monotonic-ns", str(queued_at_monotonic_ns),
        ]
        wall_step_at_ns = queued_at_monotonic_ns + 5_020_000_000
        wall_before_step_ns = 1_000_100_000
        wall_after_step_ns = 999_000_000
        supervision = {
            "descendant_termination_verified": True,
            "reviewer_leader_reaped": True,
            "descendants_surviving": [],
        }

        def stepped_wall_clock_ns():
            if time.monotonic_ns() >= wall_step_at_ns:
                return wall_after_step_ns
            return wall_before_step_ns

        def delayed_success(command, cwd, prompt, timeout_seconds, timeout_grace_seconds, *, deadline=None):
            if Path(command[0]).name == "codex":
                delay = (wall_step_at_ns - time.monotonic_ns()) / 1_000_000_000
                time.sleep(max(0, delay))
            return 0, "VERDICT: APPROVED\nCOVERAGE: all\n", "", False, False, supervision

        with mock.patch.dict(os.environ, self.env), mock.patch.object(
            runner.time, "time_ns", side_effect=stepped_wall_clock_ns
        ), mock.patch.object(runner, "execute", side_effect=delayed_success):
            code = runner.main(argv)

        receipt = json.loads((self.output / "receipt.json").read_text())
        self.assertTrue(receipt["attempt_deadline_exceeded"] is False)
        self.assertEqual(receipt["reviewers"]["opus"]["status"], "success")
        self.assertEqual(receipt["reviewers"]["codex"]["status"], "error")
        self.assertEqual(code, 0)

    def test_cleanup_overrun_invalidates_successful_review_vote(self) -> None:
        runner = load_runner_module()
        self.executable("codex", "printf 'VERDICT: APPROVED\nCOVERAGE: all\n'\n")
        argv = [
            "--repo", str(self.repo), "--ref", self.sha,
            "--packet-file", str(self.packet), "--output-dir", str(self.output),
            "--reviewers", "codex", "--attempt-timeout-seconds", "2.0",
            "--cleanup-budget-seconds", "0.1",
            "--timeout-grace-seconds", "0.05",
        ]

        def slow_cleanup(path):
            result = runner.cleanup_directory(path)
            time.sleep(2.05)
            return result

        with mock.patch.dict(os.environ, self.env):
            code = runner.main(self.with_queued_timestamps(argv), cleanup_fn=slow_cleanup)

        receipt = json.loads((self.output / "receipt.json").read_text())
        self.assertEqual(code, 4)
        self.assertTrue(receipt["cleanup"]["success"])
        self.assertTrue(receipt["attempt_deadline_exceeded"])
        self.assertEqual(receipt["reviewers"]["codex"]["status"], "error")
        self.assertEqual(receipt["reviewers"]["codex"]["failure"], "attempt_timeout")

    def test_failed_late_receipt_rewrite_warns_that_stored_votes_are_stale(self) -> None:
        runner = load_runner_module()
        self.executable("codex", "printf 'VERDICT: APPROVED\\nCOVERAGE: all\\n'\n")
        argv = self.with_queued_timestamps([
            "--repo", str(self.repo), "--ref", self.sha,
            "--packet-file", str(self.packet), "--output-dir", str(self.output),
            "--reviewers", "codex", "--attempt-timeout-seconds", "5.0",
            "--cleanup-budget-seconds", "0.1", "--timeout-grace-seconds", "0.05",
        ])
        original_write_text = Path.write_text
        receipt_writes = 0

        def delayed_receipt_write(path, data, *args, **kwargs):
            nonlocal receipt_writes
            if path.name == "receipt.json":
                receipt_writes += 1
                if receipt_writes == 1:
                    return original_write_text(path, data, *args, **kwargs)
                if receipt_writes == 2:
                    result = original_write_text(path, data, *args, **kwargs)
                    time.sleep(5.05)
                    return result
                raise OSError("simulated late receipt rewrite failure")
            return original_write_text(path, data, *args, **kwargs)

        stderr = io.StringIO()
        with mock.patch.dict(os.environ, self.env), mock.patch.object(
            Path, "write_text", delayed_receipt_write
        ), mock.patch.object(
            runner, "resolve_review_scratch_root", return_value=self.scratch
        ), redirect_stderr(stderr):
            code = runner.main(argv)

        stored_receipt = json.loads((self.output / "receipt.json").read_text())
        self.assertEqual(code, 4)
        self.assertEqual(receipt_writes, 3)
        self.assertEqual(stored_receipt.get("reviewers", {}).get("codex", {}).get("status"), "success", repr(stored_receipt))
        self.assertIn("receipt write failed", stderr.getvalue())
        self.assertIn("do not use any reviewer vote", stderr.getvalue())

    def test_operation_failure_with_successful_cleanup_has_distinct_exit_and_receipt(self) -> None:
        runner = load_runner_module()
        argv = [
            "--repo", str(self.repo), "--ref", self.sha,
            "--packet-file", str(self.packet), "--output-dir", str(self.output),
        ]
        cleanup = {"success": True, "error": None, "path": "/fixture"}
        def cleanup_success(path):
            runner.cleanup_directory(path)
            return cleanup
        stderr = io.StringIO()

        with mock.patch.dict(runner.os.environ, {
            "DISK_MAGICIAN_DISKM_BIN": str(self.bin / "diskm"),
            "ADVICE_TEST_SCRATCH": str(self.scratch),
        }), redirect_stderr(stderr):
            code = runner.main(
                self.with_queued_timestamps(argv),
                create_clone_fn=mock.Mock(side_effect=RuntimeError("clone setup failed")),
                cleanup_fn=mock.Mock(side_effect=cleanup_success),
            )

        self.assertEqual(code, 6)
        receipt = json.loads((self.output / "receipt.json").read_text())
        self.assertEqual(receipt["operation"]["success"], False)
        self.assertEqual(receipt["cleanup"], cleanup)
        self.assertIn("primary reviewer operation failed", stderr.getvalue())

    def test_validate_codex_model_allows_gpt6_and_forbids_5_6_models(self) -> None:
        runner = load_runner_module()
        self.assertEqual(runner.validate_codex_model(), "gpt-6-sol")
        self.assertEqual(runner.validate_codex_model(None), "gpt-6-sol")
        self.assertEqual(runner.validate_codex_model(""), "gpt-6-sol")
        self.assertEqual(runner.validate_codex_model("   "), "gpt-6-sol")
        self.assertEqual(runner.validate_codex_model("gpt-6-sol"), "gpt-6-sol")
        self.assertEqual(runner.validate_codex_model("gpt-6-astra"), "gpt-6-astra")
        self.assertEqual(runner.validate_codex_model("gpt-6-luna"), "gpt-6-luna")
        self.assertEqual(runner.validate_codex_model("gpt-6.1-sol"), "gpt-6.1-sol")

        for invalid in (
            "gpt-6",
            "gpt-6.1",
            "gpt-6-not-a-real-model",
            "gpt-60-legacy",
            "gpt-6junk",
            "gpt-6-",
            "gpt-6.1-",
        ):
            with self.assertRaises(ValueError):
                runner.validate_codex_model(invalid)

        # Forbid all 5.6 models
        for forbidden in ("gpt-5.6-terra", "gpt-5.6-sol", "gpt-5.6-luna", "5.6", "my-5.6-model"):
            with self.assertRaises(ValueError) as ctx:
                runner.validate_codex_model(forbidden)
            self.assertIn("5.6", str(ctx.exception))

        # Reject non-gpt-6 / non-gpt-6.1 models
        for invalid in ("gpt-4o", "claude-3-opus", "gpt-5-mini", "o1"):
            with self.assertRaises(ValueError) as ctx:
                runner.validate_codex_model(invalid)
            self.assertIn("gpt-6", str(ctx.exception))

    def test_codex_model_cli_flag_accepts_valid_and_rejects_forbidden(self) -> None:
        self.executable(
            "codex",
            "printf '%s\\n' \"$@\" > \"$ADVICE_TEST_SYNC_DIR/codex.args\"\n"
            "printf 'VERDICT: APPROVED\\nCOVERAGE: all\\n'\n",
        )
        self.executable(
            "claude",
            "printf 'VERDICT: APPROVED\\nCOVERAGE: all\\n'\n",
        )

        # Valid custom gpt-6 model
        res_valid = self.invoke("--codex-model", "gpt-6-luna")
        self.assertEqual(res_valid.returncode, 0, res_valid.stderr)
        codex_args = (self.sync / "codex.args").read_text().splitlines()
        self.assertIn("gpt-6-luna", codex_args)

        # Forbidden 5.6 model rejected by CLI parser
        res_invalid = self.invoke("--codex-model", "gpt-5.6-terra")
        self.assertEqual(res_invalid.returncode, 2, res_invalid.stderr)
        self.assertIn("5.6", res_invalid.stderr)

    def test_codex_model_environment_default_is_validated_and_forwarded(self) -> None:
        self.executable(
            "codex",
            "printf '%s\\n' \"$@\" > \"$ADVICE_TEST_SYNC_DIR/codex.args\"\n"
            "printf 'VERDICT: APPROVED\\nCOVERAGE: all\\n'\n",
        )
        self.env["ADVICE_CODEX_MODEL"] = "gpt-6.1-sol"

        result = self.invoke("--reviewers", "codex")

        self.assertEqual(result.returncode, 0, result.stderr)
        codex_args = (self.sync / "codex.args").read_text().splitlines()
        self.assertIn("gpt-6.1-sol", codex_args)

        self.output = self.root / "invalid-env-out"
        self.env["ADVICE_CODEX_MODEL"] = "gpt-6-unknown"
        invalid = self.invoke("--reviewers", "codex")
        self.assertEqual(invalid.returncode, 2, invalid.stderr)
        self.assertIn("Codex model must be one of", invalid.stderr)
        self.assertIn("gpt-6-unknown", invalid.stderr)

    def test_codex_lane_rejects_invalid_model_before_waiting_at_barrier(self) -> None:
        runner = load_runner_module()
        barrier = mock.Mock()

        with self.assertRaisesRegex(ValueError, "Codex model must be one of"):
            runner.codex_lane(
                self.repo,
                "review prompt",
                barrier,
                1.0,
                0.1,
                "gpt-6-unknown",
            )

        barrier.wait.assert_not_called()


    def test_healthy_peer_result_survives_other_lane_exception(self) -> None:
        runner = load_runner_module()
        argv = self.with_queued_timestamps([
            "--repo", str(self.repo), "--ref", self.sha,
            "--packet-file", str(self.packet), "--output-dir", str(self.output),
            "--reviewers", "codex,opus",
        ])
        opus_done = threading.Event()
        started_ns = time.time_ns()
        started_monotonic_ns = time.monotonic_ns()
        opus_output = "VERDICT: APPROVED\nCOVERAGE: all\n"

        def fail_codex(*_args: object, **_kwargs: object) -> dict[str, object]:
            if not opus_done.wait(timeout=2):
                raise RuntimeError("Opus did not finish before simulated Codex launch failure")
            raise RuntimeError("simulated Codex launch failure")

        def complete_opus(*_args: object, **_kwargs: object) -> dict[str, object]:
            opus_done.set()
            return {
                "status": "success",
                "transport": "claude -p",
                "stdout": opus_output,
                "attempts": [{
                    "transport": "claude -p",
                    "exit_code": 0,
                    "failure": None,
                    "descendant_termination_verified": True,
                    "reviewer_leader_reaped": True,
                    "descendants_surviving": [],
                    "descendant_supervision_errors": [],
                }],
                "started_ns": started_ns,
                "ended_ns": time.time_ns(),
                "started_monotonic_ns": started_monotonic_ns,
                "ended_monotonic_ns": time.monotonic_ns(),
            }

        with mock.patch.dict(os.environ, self.env), mock.patch.object(
            runner, "resolve_review_scratch_root", return_value=self.scratch
        ), mock.patch.object(runner, "codex_lane", side_effect=fail_codex), mock.patch.object(
            runner, "opus_lane", side_effect=complete_opus
        ):
            code = runner.main(argv)

        receipt = json.loads((self.output / "receipt.json").read_text())
        self.assertEqual(code, 6)
        self.assertFalse(receipt["operation"]["success"])
        self.assertIn("simulated Codex launch failure", receipt["operation"]["error"])
        self.assertIn("codex", receipt["reviewer_future_errors"])
        self.assertEqual(receipt["descendant_termination_failures"], ["codex"])
        self.assertEqual(receipt["reviewers"]["opus"]["status"], "success")
        self.assertEqual((self.output / "opus.txt").read_text(), opus_output)

    def test_timeout_failure_is_not_relabelled_as_missing_verdict(self) -> None:
        runner = load_runner_module()
        self.executable("codex", "exit 0\n")
        self.executable("claude", "exit 0\n")
        supervision = {
            "descendant_termination_verified": True,
            "reviewer_leader_reaped": True,
            "descendants_surviving": [],
            "descendant_supervision_errors": [],
        }
        timed_out_partial_output = (
            0,
            "partial output without verdict",
            "partial stderr",
            True,
            False,
            supervision,
        )
        lanes = (
            ("codex", runner.codex_lane),
            ("opus", runner.opus_lane),
        )

        with mock.patch.dict(os.environ, self.env), mock.patch.object(
            runner, "execute", return_value=timed_out_partial_output
        ):
            for name, lane in lanes:
                with self.subTest(lane=name):
                    result = lane(
                        self.repo,
                        "review prompt",
                        threading.Barrier(1),
                        time.monotonic() + 1,
                        0.1,
                        "gpt-6-sol",
                    ) if name == "codex" else lane(
                        self.repo,
                        "review prompt",
                        threading.Barrier(1),
                        time.monotonic() + 1,
                        0.1,
                    )
                    self.assertEqual(result["status"], "error")
                    self.assertEqual(result["attempts"][0]["failure"], "timeout")


if __name__ == "__main__":
    unittest.main()
