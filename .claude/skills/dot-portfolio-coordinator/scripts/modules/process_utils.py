"""Process execution utilities with bounded process-group lifetimes."""

import os
import selectors
import signal
import subprocess
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple, TypeVar, Union


class ProcessTimeoutError(Exception):
    """Raised when a subprocess exceeds its execution deadline."""


class ProcessExecutionError(Exception):
    """Raised when a subprocess or its private frame protocol fails."""


class ProcessCleanupError(ProcessExecutionError):
    """Raised when the owned process group cannot be proven stopped."""


class InteractiveChild:
    """Private newline-frame pipe access bounded by one absolute deadline."""

    def __init__(
        self, process: subprocess.Popen, deadline: float, max_frame_bytes: int
    ):
        if process.stdin is None or process.stdout is None:
            raise ProcessExecutionError("Interactive child pipes are unavailable")
        self._process = process
        self._stdin_fd = process.stdin.fileno()
        self._stdout_fd = process.stdout.fileno()
        self._deadline = deadline
        self._max_frame_bytes = max_frame_bytes
        self._read_buffer = bytearray()
        os.set_blocking(self._stdin_fd, False)
        os.set_blocking(self._stdout_fd, False)

    def send_frame(self, frame: Union[str, bytes]) -> None:
        """Write one UTF-8 or raw-byte frame, terminated by a single LF."""
        self._check_deadline("write")
        payload = frame.encode("utf-8") if isinstance(frame, str) else frame
        if not isinstance(payload, bytes):
            raise ProcessExecutionError("Frame must be text or bytes")
        if b"\n" in payload or b"\r" in payload:
            raise ProcessExecutionError("Frame contains a line delimiter")
        if len(payload) > self._max_frame_bytes:
            raise ProcessExecutionError("Frame exceeds configured byte limit")
        packet = memoryview(payload + b"\n")
        with selectors.DefaultSelector() as selector:
            selector.register(self._stdin_fd, selectors.EVENT_WRITE)
            while packet:
                self._wait(selector, "write")
                try:
                    written = os.write(self._stdin_fd, packet)
                except (BrokenPipeError, OSError) as exc:
                    raise ProcessExecutionError(
                        "Interactive child closed its input"
                    ) from exc
                if written <= 0:
                    raise ProcessExecutionError("Interactive child input made no progress")
                packet = packet[written:]

    def read_frame(self) -> bytes:
        """Read one LF-terminated frame without exceeding the configured bound."""
        with selectors.DefaultSelector() as selector:
            selector.register(self._stdout_fd, selectors.EVENT_READ)
            while True:
                self._check_deadline("read")
                delimiter = self._read_buffer.find(b"\n")
                if delimiter >= 0:
                    if delimiter > self._max_frame_bytes:
                        raise ProcessExecutionError(
                            "Child frame exceeds configured byte limit"
                        )
                    frame = bytes(self._read_buffer[:delimiter])
                    del self._read_buffer[: delimiter + 1]
                    return frame
                if len(self._read_buffer) > self._max_frame_bytes:
                    raise ProcessExecutionError(
                        "Child frame exceeds configured byte limit"
                    )
                self._wait(selector, "read")
                try:
                    chunk = os.read(self._stdout_fd, 4096)
                except OSError as exc:
                    raise ProcessExecutionError("Could not read child frame") from exc
                if not chunk:
                    raise ProcessExecutionError("Interactive child closed its output")
                self._read_buffer.extend(chunk)

    def read_remaining_output(self) -> bytes:
        """Drain through EOF, including buffered bytes, under the original deadline."""
        output = bytearray(self._read_buffer)
        self._read_buffer.clear()
        with selectors.DefaultSelector() as selector:
            selector.register(self._stdout_fd, selectors.EVENT_READ)
            while True:
                if len(output) > self._max_frame_bytes:
                    raise ProcessExecutionError("Trailing child output exceeds byte limit")
                self._wait(selector, "exit output")
                chunk = os.read(self._stdout_fd, 4096)
                if not chunk:
                    return bytes(output)
                output.extend(chunk)

    def _wait(self, selector: selectors.BaseSelector, operation: str) -> None:
        remaining = self._remaining(operation)
        if not selector.select(remaining):
            raise ProcessTimeoutError(f"Interactive child {operation} deadline expired")

    def _remaining(self, operation: str) -> float:
        remaining = self._deadline - time.monotonic()
        if remaining <= 0:
            raise ProcessTimeoutError(f"Interactive child {operation} deadline expired")
        return remaining

    def _check_deadline(self, operation: str) -> None:
        self._remaining(operation)


def _group_exists(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return _group_has_live_members(pgid)
    except OSError as exc:
        raise ProcessCleanupError("Could not verify owned process group") from exc


def _group_has_live_members(pgid: int) -> bool:
    """Treat zombies as stopped; they cannot execute and are reaped by their parent."""
    try:
        result = subprocess.run(
            ["ps", "-axo", "pgid=,stat="],
            check=False,
            capture_output=True,
            text=True,
            timeout=1,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProcessCleanupError("Could not inspect owned process group") from exc
    if result.returncode != 0:
        raise ProcessCleanupError("Could not inspect owned process group")
    for line in result.stdout.splitlines():
        fields = line.split(None, 1)
        if len(fields) == 2 and fields[0].isdigit() and int(fields[0]) == pgid:
            if not fields[1].startswith("Z"):
                return True
    return False


def _terminate_owned_group(proc: subprocess.Popen, grace_secs: float = 0.2) -> None:
    """Stop only the session/process group created for this child and verify it."""
    pgid = proc.pid
    if _group_exists(pgid):
        try:
            os.killpg(pgid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except OSError as exc:
            raise ProcessCleanupError("Could not terminate owned process group") from exc

        deadline = time.monotonic() + max(0.0, grace_secs)
        while _group_exists(pgid) and time.monotonic() < deadline:
            time.sleep(min(0.02, max(0.0, deadline - time.monotonic())))

        if _group_exists(pgid):
            try:
                os.killpg(pgid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except OSError as exc:
                raise ProcessCleanupError("Could not kill owned process group") from exc

            deadline = time.monotonic() + 1.0
            while _group_exists(pgid) and time.monotonic() < deadline:
                time.sleep(min(0.02, max(0.0, deadline - time.monotonic())))

            if _group_exists(pgid) and _group_has_live_members(pgid):
                raise ProcessCleanupError("Owned process group remains alive after SIGKILL")

    try:
        proc.wait(timeout=1)
    except subprocess.TimeoutExpired as exc:
        raise ProcessCleanupError("Owned process leader did not exit") from exc


def _close_pipe(pipe) -> None:
    if pipe is not None:
        try:
            pipe.close()
        except OSError:
            pass


def _close_process_pipes(proc: subprocess.Popen) -> None:
    for pipe in (proc.stdin, proc.stdout, proc.stderr):
        _close_pipe(pipe)


def run_bounded_command(
    cmd: List[str],
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    timeout_secs: int = 600,
    input_text: Optional[str] = None,
) -> Tuple[int, str, str]:
    """Run a command without a shell and clean its complete owned process group."""
    timeout = min(max(1, int(timeout_secs)), 3600)
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        env=env,
        stdin=subprocess.PIPE if input_text is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        stdout, stderr = proc.communicate(input=input_text, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        try:
            _terminate_owned_group(proc)
        except ProcessCleanupError as cleanup_error:
            _close_process_pipes(proc)
            raise cleanup_error from exc
        try:
            proc.communicate(timeout=1)
        except Exception:
            pass
        finally:
            _close_process_pipes(proc)
        raise ProcessTimeoutError(f"Command exceeded deadline of {timeout}s") from None
    except BaseException as exc:
        try:
            _terminate_owned_group(proc)
        except ProcessCleanupError as cleanup_error:
            _close_process_pipes(proc)
            raise cleanup_error from exc
        try:
            proc.communicate(timeout=1)
        except Exception:
            pass
        finally:
            _close_process_pipes(proc)
        if not isinstance(exc, Exception):
            raise
        raise ProcessExecutionError(f"Command execution error: {exc}") from exc

    try:
        _terminate_owned_group(proc)
    finally:
        _close_process_pipes(proc)
    return proc.returncode, stdout, stderr


Result = TypeVar("Result")


@dataclass(frozen=True)
class InteractiveCompletion:
    """Callback result and natural leader exit, before any forced cleanup."""

    result: object
    returncode: int
    trailing_output: bytes


def run_bounded_interactive_command(
    cmd: List[str],
    interaction: Callable[[InteractiveChild], Result],
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    timeout_secs: int = 180,
    max_frame_bytes: int = 65536,
    wait_for_exit: bool = False,
) -> Union[Result, InteractiveCompletion]:
    """Run bounded private newline-framed I/O, then clean the owned process group.

    The callback must do only bounded local work and use ``child`` for I/O. The
    absolute deadline bounds every pipe operation and is checked again on return;
    Python cannot preempt arbitrary blocking callback code. With ``wait_for_exit``,
    drain bounded trailing output and await natural exit using only the remaining
    deadline. A live descendant requiring forced cleanup invalidates completion.
    Legacy callers retain their callback-only result and cleanup behavior.
    """
    timeout = min(max(1, int(timeout_secs)), 3600)
    if max_frame_bytes < 1:
        raise ValueError("max_frame_bytes must be positive")
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=False,
        bufsize=0,
        start_new_session=True,
    )
    try:
        deadline = time.monotonic() + timeout
        child = InteractiveChild(proc, deadline, max_frame_bytes)
        result = interaction(child)
        if wait_for_exit:
            trailing_output = child.read_remaining_output()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ProcessTimeoutError("Interactive child deadline expired")
            try:
                returncode = proc.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                raise ProcessTimeoutError("Interactive child exit deadline expired") from None
            if _group_exists(proc.pid) and _group_has_live_members(proc.pid):
                raise ProcessExecutionError("Interactive child required forced cleanup")
            if time.monotonic() >= deadline:
                raise ProcessTimeoutError("Interactive child exit deadline expired")
            result = InteractiveCompletion(result, returncode, trailing_output)
        elif time.monotonic() > deadline:
            raise ProcessTimeoutError("Interactive child deadline expired")
    except BaseException as exc:
        try:
            _terminate_owned_group(proc)
        except ProcessCleanupError as cleanup_error:
            _close_process_pipes(proc)
            raise cleanup_error from exc
        _close_process_pipes(proc)
        raise
    try:
        if not wait_for_exit:
            _terminate_owned_group(proc)
    finally:
        _close_process_pipes(proc)
    return result
