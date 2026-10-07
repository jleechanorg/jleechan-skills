"""Process execution utilities with process-group isolation and bounded timeouts."""
import os
import signal
import subprocess
import time
from typing import Dict, List, Optional, Tuple


class ProcessTimeoutError(Exception):
    """Raised when a subprocess exceeds its execution deadline."""
    pass


class ProcessExecutionError(Exception):
    """Raised when a subprocess fails execution."""
    pass


def run_bounded_command(
    cmd: List[str],
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    timeout_secs: int = 600,
    input_text: Optional[str] = None
) -> Tuple[int, str, str]:
    """Runs a command in a new session / process group with bounded timeout.

    Guarantees:
    - start_new_session=True (new process group)
    - Clean termination of the entire process group (including grandchildren) on timeout or interrupt
    - No shell execution
    - No raw credentials printed
    - Maximum timeout ceiling of 600s by default
    """
    timeout = min(max(1, int(timeout_secs)), 3600)  # bounded positive timeout

    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        env=env,
        stdin=subprocess.PIPE if input_text is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True
    )

    try:
        stdout, stderr = proc.communicate(input=input_text, timeout=timeout)
        return proc.returncode, stdout, stderr
    except subprocess.TimeoutExpired:
        # Terminate the entire process group
        try:
            os.killpg(proc.pid, signal.SIGTERM)
            time.sleep(0.2)
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, OSError):
            pass
        # Drain buffers to prevent resource leaks
        try:
            proc.communicate(timeout=1)
        except Exception:
            pass
        raise ProcessTimeoutError(f"Command exceeded deadline of {timeout}s")
    except BaseException as e:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except Exception:
            pass
        try:
            proc.communicate(timeout=1)
        except Exception:
            pass
        if not isinstance(e, Exception):
            raise
        raise ProcessExecutionError(f"Command execution error: {e}")
