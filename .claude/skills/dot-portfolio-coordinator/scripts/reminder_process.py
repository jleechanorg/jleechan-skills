"""Bounded trusted children; POSIX supervision, not malicious-process containment."""
import ctypes
import errno
import math
import os
import selectors
import signal
import subprocess
import sys
import time


class BSD(ctypes.Structure):
    """Darwin libproc PROC_PIDTBSDINFO, including microsecond start identity."""
    _fields_ = [('flags', ctypes.c_uint32), ('status', ctypes.c_uint32), ('exit_status', ctypes.c_uint32),
                ('pid', ctypes.c_uint32), ('ppid', ctypes.c_uint32), ('credentials', ctypes.c_uint32 * 7),
                ('comm', ctypes.c_char * 16), ('name', ctypes.c_char * 32), ('nfiles', ctypes.c_uint32),
                ('pgid', ctypes.c_uint32), ('job_control', ctypes.c_uint32 * 4),
                ('start_sec', ctypes.c_uint64), ('start_usec', ctypes.c_uint64)]


def mac_snapshot(deadline):
    lib = ctypes.CDLL('/usr/lib/libproc.dylib', use_errno=True)
    lib.proc_pidinfo.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint64, ctypes.c_void_p, ctypes.c_int]
    lib.proc_pidinfo.restype = ctypes.c_int
    lib.proc_listallpids.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.proc_listallpids.restype = ctypes.c_int
    if ctypes.sizeof(BSD) != 136 or BSD.start_sec.offset != 120 or BSD.start_usec.offset != 128:
        raise ValueError('unsupported libproc ABI')
    pids = (ctypes.c_int * 32768)()
    count = lib.proc_listallpids(pids, ctypes.sizeof(pids))
    if not 0 < count < len(pids):
        raise ValueError('process enumeration failed or exceeded limit')
    rows = {}
    for pid in pids[:count]:
        if time.monotonic() >= deadline:
            raise TimeoutError('process observation timeout')
        if pid <= 0:
            continue
        row = BSD()
        ctypes.set_errno(0)
        size = lib.proc_pidinfo(pid, 3, 0, ctypes.byref(row), ctypes.sizeof(row))
        if size == 0 and ctypes.get_errno() == errno.ESRCH:
            continue
        if size != ctypes.sizeof(row):
            raise OSError(ctypes.get_errno(), 'incomplete process identity')
        if row.pid != pid or row.start_sec <= 0 or row.start_usec >= 1000000:
            raise ValueError('invalid process identity')
        rows[pid] = (row.ppid, row.pgid, 'Z' if row.status == 5 else 'S', (row.start_sec, row.start_usec))
    own = rows.get(os.getpid())
    if own is None or own[:2] != (os.getppid(), os.getpgrp()):
        raise ValueError('libproc self identity mismatch')
    if time.monotonic() >= deadline:
        raise TimeoutError('process observation timeout')
    return rows


def kill_observed(pid, identity, deadline):
    # Darwin has no pidfd: recheck start identity immediately before signaling.
    descriptor = None if sys.platform == 'darwin' else os.pidfd_open(pid)
    try:
        fresh = snapshot(deadline).get(pid)
        if fresh is not None and fresh[3] == identity:
            if descriptor is None:
                os.kill(pid, signal.SIGKILL)
            else:
                signal.pidfd_send_signal(descriptor, signal.SIGKILL)
    finally:
        if descriptor is not None:
            os.close(descriptor)


def snapshot(deadline):
    """Complete bounded kernel-identity observation; unsupported hosts fail closed."""
    if time.monotonic() >= deadline:
        raise TimeoutError('process observation timeout')
    if sys.platform == 'darwin':
        return mac_snapshot(deadline)
    if not sys.platform.startswith('linux') or not os.path.isdir('/proc/self'):
        raise RuntimeError('tested process identity adapter unavailable')
    rows = {}
    with os.scandir('/proc') as entries:
        for count, entry in enumerate(entries):
            if time.monotonic() >= deadline:
                raise TimeoutError('process observation timeout')
            if count > 32768:
                raise ValueError('process observation limit')
            if not entry.name.isdigit():
                continue
            try:
                with open(entry.path+'/stat', 'rb') as source:
                    data = source.read(4097)
            except (ProcessLookupError, FileNotFoundError):
                continue
            if len(data) > 4096:
                raise ValueError('process identity limit')
            fields = data.rsplit(b')', 1)[1].split()
            rows[int(entry.name)] = (int(fields[1]), int(fields[2]), fields[0].decode(), fields[19])
    if time.monotonic() >= deadline:
        raise TimeoutError('process observation timeout')
    return rows


def run(argv, input_bytes=b'', *, timeout=180, max_input=65536, max_output=65536, cwd=None, env=None):
    """Run budget plus at most one second cleanup; do not externally reap children."""
    if not math.isfinite(timeout) or timeout <= 0 or not isinstance(max_input, int) or not isinstance(max_output, int) or min(max_input, max_output) < 1:
        raise ValueError('positive finite timeout and integer byte limits required')
    if not isinstance(input_bytes, bytes) or len(input_bytes) > max_input:
        raise ValueError('input limit or type')
    if signal.getsignal(signal.SIGCHLD) != signal.SIG_DFL:
        raise ValueError('supervisor requires exclusive child reaping')
    deadline = time.monotonic() + timeout
    proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            cwd=cwd, env=env, start_new_session=True, bufsize=0)
    output = {'stdout': bytearray(), 'stderr': bytearray()}
    observed, reason, forced, cleanup = {}, 'exited', False, False
    natural, selector, cancellation, drain_end = False, None, None, deadline
    pending = memoryview(input_bytes)

    def observe(end):
        table = snapshot(end)
        roots = {proc.pid} | {pid for pid, identity in observed.items() if pid in table and table[pid][3] == identity}
        roots |= {pid for pid, row in table.items() if row[1] == proc.pid}
        while True:
            if time.monotonic() >= end:
                raise TimeoutError('process observation timeout')
            children = {pid for pid, row in table.items() if row[0] in roots}
            if children <= roots:
                break
            roots |= children
        observed.update({pid: table[pid][3] for pid in roots if pid in table})
        return {pid: row for pid, row in table.items() if pid in observed and row[3] == observed[pid]}

    try:
        selector = selectors.DefaultSelector()
        for name in ('stdin', 'stdout', 'stderr'):
            pipe = getattr(proc, name)
            os.set_blocking(pipe.fileno(), False)
            if name != 'stdin' or pending:
                selector.register(pipe, selectors.EVENT_WRITE if name == 'stdin' else selectors.EVENT_READ, name)
            else:
                pipe.close()
        while True:
            if time.monotonic() >= deadline:
                raise TimeoutError('timeout')
            table = observe(drain_end)
            if proc.pid in table and table[proc.pid][2].startswith('Z') and not natural:
                natural, drain_end = True, min(deadline, time.monotonic()+.2)
            if not selector.get_map() and natural:
                break
            if time.monotonic() >= drain_end:
                raise TimeoutError('pipe_drain')
            for key, _ in selector.select(min(.02, max(0, drain_end-time.monotonic()))):
                try:
                    if key.data == 'stdin':
                        try:
                            pending = pending[os.write(key.fd, pending[:65536]):]
                        except BrokenPipeError:
                            pending = pending[:0]
                        chunk = pending
                    else:
                        remaining = max_output-sum(map(len, output.values()))
                        chunk = os.read(key.fd, min(65536, remaining+1))
                        output[key.data].extend(chunk[:remaining])
                        if len(chunk) > remaining:
                            raise OverflowError('output_limit')
                    if not chunk:
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
                except BlockingIOError:
                    continue
    except BaseException as error:
        if not isinstance(error, Exception):
            cancellation = error
        reason = str(error) if isinstance(error, (TimeoutError, OverflowError)) else 'observation_or_io_failed'
        if isinstance(error, TimeoutError):
            reason = 'timeout' if time.monotonic() >= deadline else 'pipe_drain' if natural else reason
    finally:
        cleanup_end = time.monotonic()+1
        # Never poll/reap before the last group signal: the leader reserves its PID.
        try:
            table = observe(cleanup_end)
            forced = any(not row[2].startswith('Z') for row in table.values())
        except BaseException as error:
            forced = True
            if not isinstance(error, Exception):
                cancellation = error
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except OSError:
            reason = 'group_cleanup_failed'
        try:
            while time.monotonic() < cleanup_end:
                table = observe(cleanup_end)
                live = {pid: row for pid, row in table.items() if not row[2].startswith('Z')}
                if not live:
                    cleanup = reason != 'group_cleanup_failed'
                    break
                forced = True
                for pid, row in live.items():
                    try:
                        kill_observed(pid, row[3], cleanup_end)
                    except ProcessLookupError:
                        pass
                    except OSError:
                        reason = 'descendant_cleanup_failed'
                time.sleep(min(.02, max(0, cleanup_end-time.monotonic())))
        except BaseException as error:
            cleanup = False
            if not isinstance(error, Exception):
                cancellation = error
        try:
            proc.wait(timeout=max(0, cleanup_end-time.monotonic()))
        except BaseException as error:
            cleanup = False
            if not isinstance(error, Exception):
                cancellation = error
        for handle in (selector, proc.stdin, proc.stdout, proc.stderr):
            try:
                if handle is not None:
                    handle.close()
            except Exception:
                cleanup = False
    if cancellation is not None:
        raise cancellation
    if forced and reason == 'exited':
        reason = 'descendants_required_cleanup'
    return dict(returncode=proc.returncode, stdout=bytes(output['stdout']), stderr=bytes(output['stderr']),
                reason=reason, natural_exit=natural, forced_cleanup=forced, cleanup_ok=cleanup)
