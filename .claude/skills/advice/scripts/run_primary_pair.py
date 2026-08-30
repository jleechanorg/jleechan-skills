#!/usr/bin/env python3
"""Run the /advice Codex and Opus reviewers concurrently at one exact SHA.

The reviewers intentionally retain their full-permission flags. Repository
mutation risk is reduced by giving each process its own independent clone; this
is not an operating-system sandbox.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import signal
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def checkout_fingerprint(repo: Path) -> str:
    """Hash HEAD, tracked state, and nonignored untracked file content."""
    digest = hashlib.sha256()
    digest.update(git(repo, "rev-parse", "HEAD").stdout)
    digest.update(git(repo, "diff", "--binary", "HEAD", "--").stdout)
    untracked = git(repo, "ls-files", "--others", "--exclude-standard", "-z").stdout
    for raw_path in sorted(filter(None, untracked.split(b"\0"))):
        digest.update(raw_path)
        path = repo / os.fsdecode(raw_path)
        if path.is_symlink():
            digest.update(b"symlink\0" + os.fsencode(os.readlink(path)))
        elif path.is_file():
            digest.update(path.read_bytes())
    return digest.hexdigest()


def ignored_path_metadata(repo: Path) -> bytes:
    """Serialize ignored-path metadata without opening regular-file content."""
    serialized = bytearray()
    ignored = git(
        repo,
        "ls-files",
        "--others",
        "--ignored",
        "--exclude-standard",
        "-z",
    ).stdout
    for raw_path in sorted(filter(None, ignored.split(b"\0"))):
        path = repo / os.fsdecode(raw_path)
        serialized.extend(raw_path)
        serialized.extend(b"\0")
        try:
            metadata = path.lstat()
        except FileNotFoundError:
            serialized.extend(b"missing\0")
            continue
        serialized.extend(
            f"{metadata.st_mode}:{metadata.st_size}:{metadata.st_mtime_ns}".encode()
        )
        serialized.extend(b"\0")
        if path.is_symlink():
            serialized.extend(b"symlink-target\0")
            serialized.extend(os.fsencode(os.readlink(path)))
            serialized.extend(b"\0")
    return bytes(serialized)


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def hook_tree_fingerprint(hooks: Path) -> str:
    """Hash an effective hook tree without following symlinks."""
    digest = hashlib.sha256()
    digest.update(os.fsencode(hooks))

    def visit(path: Path, relative: Path) -> None:
        digest.update(os.fsencode(relative))
        try:
            metadata = path.lstat()
        except FileNotFoundError:
            digest.update(b"\0missing\0")
            return
        digest.update(
            f"\0{metadata.st_mode}:{metadata.st_size}:{metadata.st_mtime_ns}\0".encode()
        )
        if stat.S_ISLNK(metadata.st_mode):
            digest.update(b"symlink-target\0")
            digest.update(os.fsencode(os.readlink(path)))
            return
        if stat.S_ISREG(metadata.st_mode):
            digest.update(b"regular-content\0")
            digest.update(path.read_bytes())
            return
        if stat.S_ISDIR(metadata.st_mode):
            try:
                children = sorted(path.iterdir(), key=lambda child: os.fsencode(child.name))
            except FileNotFoundError:
                digest.update(b"directory-disappeared\0")
                return
            for child in children:
                visit(child, relative / child.name)

    visit(hooks, Path("."))
    return digest.hexdigest()


def repository_snapshot(repo: Path) -> dict[str, str]:
    """Return component hashes for mutation detection and useful diagnostics."""
    effective_hooks = Path(
        git(
            repo,
            "rev-parse",
            "--path-format=absolute",
            "--git-path",
            "hooks",
        ).stdout.decode().strip()
    )
    return {
        "checkout": checkout_fingerprint(repo),
        "ignored_metadata": digest_bytes(ignored_path_metadata(repo)),
        "local_config": digest_bytes(git(repo, "config", "--local", "--null", "--list").stdout),
        "refs": digest_bytes(git(repo, "show-ref", "--head", check=False).stdout),
        "effective_hooks": hook_tree_fingerprint(effective_hooks),
    }


def command_path(name: str) -> str | None:
    return shutil.which(name)


def process_snapshot() -> dict[int, tuple[int, str]]:
    """Return PID -> (PPID, start identity) using portable macOS/Linux ps fields."""
    completed = subprocess.run(
        ["ps", "-axo", "pid=,ppid=,lstart="],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
        timeout=0.5,
    )
    snapshot: dict[int, tuple[int, str]] = {}
    for line in completed.stdout.splitlines():
        fields = line.strip().split(None, 2)
        if len(fields) != 3:
            continue
        try:
            pid, ppid = int(fields[0]), int(fields[1])
        except ValueError:
            continue
        snapshot[pid] = (ppid, fields[2])
    return snapshot


class ProcessTreeSupervisor:
    """Best-effort descendant tracker that retains identities after reparenting."""

    def __init__(self, root_pid: int, interval_seconds: float = 0.02) -> None:
        self.root_pid = root_pid
        self.interval_seconds = interval_seconds
        self.discovered: dict[int, str] = {}
        self.errors: list[str] = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._sample()
        self._thread.start()

    def _sample(self) -> None:
        try:
            snapshot = process_snapshot()
        except (OSError, subprocess.SubprocessError) as error:
            with self._lock:
                self.errors.append(f"{type(error).__name__}: {error}")
            return
        with self._lock:
            roots = {self.root_pid, *self.discovered}
            changed = True
            while changed:
                changed = False
                for pid, (ppid, started) in snapshot.items():
                    if pid not in roots and ppid in roots:
                        roots.add(pid)
                        self.discovered[pid] = started
                        changed = True

    def _run(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            self._sample()

    def stop(self) -> None:
        self._sample()
        self._stop.set()
        self._thread.join(timeout=max(0.1, self.interval_seconds * 5))

    def active_discovered(self) -> list[int]:
        try:
            snapshot = process_snapshot()
        except (OSError, subprocess.SubprocessError) as error:
            with self._lock:
                self.errors.append(f"{type(error).__name__}: {error}")
            return sorted(self.discovered)
        with self._lock:
            return sorted(
                pid
                for pid, started in self.discovered.items()
                if pid in snapshot and snapshot[pid][1] == started
            )

    def signal_active(self, signal_number: int) -> list[int]:
        signaled: list[int] = []
        for pid in self.active_discovered():
            try:
                os.kill(pid, signal_number)
            except ProcessLookupError:
                continue
            except OSError as error:
                with self._lock:
                    self.errors.append(f"PID {pid}: {type(error).__name__}: {error}")
            else:
                signaled.append(pid)
        return signaled

    def verify_gone(self, grace_seconds: float) -> list[int]:
        deadline = time.monotonic() + grace_seconds
        survivors = self.active_discovered()
        while survivors and time.monotonic() < deadline:
            time.sleep(min(0.02, max(0.0, deadline - time.monotonic())))
            survivors = self.active_discovered()
        return survivors

    def evidence(self, terminated: set[int], survivors: list[int]) -> dict[str, Any]:
        with self._lock:
            return {
                "descendants_discovered": sorted(self.discovered),
                "descendants_terminated": sorted(terminated),
                "descendants_surviving": survivors,
                "descendant_termination_verified": not survivors and not self.errors,
                "descendant_supervision_errors": list(self.errors),
            }


def execute(
    command: list[str],
    cwd: Path,
    prompt: str,
    timeout_seconds: float,
    timeout_grace_seconds: float,
) -> tuple[int, str, str, bool, bool, dict[str, Any]]:
    process = subprocess.Popen(
        [*command, prompt],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    supervisor = ProcessTreeSupervisor(process.pid)
    supervisor.start()
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
        supervisor.stop()
        return (
            process.returncode,
            stdout,
            stderr,
            False,
            False,
            supervisor.evidence(set(), supervisor.active_discovered()),
        )
    except subprocess.TimeoutExpired:
        supervisor.stop()
        terminated = set(supervisor.signal_active(signal.SIGTERM))
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        forced_pipe_close = False
        try:
            stdout, stderr = process.communicate(timeout=timeout_grace_seconds)
        except subprocess.TimeoutExpired as drain_timeout:
            forced_pipe_close = True

            def partial_text(value: str | bytes | None) -> str:
                if value is None:
                    return ""
                if isinstance(value, bytes):
                    return value.decode(errors="replace")
                return value

            stdout = partial_text(drain_timeout.output)
            stderr = partial_text(drain_timeout.stderr)
            for pipe in (process.stdout, process.stderr):
                if pipe is not None:
                    pipe.close()
        try:
            process.wait(timeout=timeout_grace_seconds)
        except subprocess.TimeoutExpired:
            process.kill()
            try:
                process.wait(timeout=timeout_grace_seconds)
            except subprocess.TimeoutExpired:
                pass
        terminated.update(supervisor.signal_active(signal.SIGKILL))
        survivors = supervisor.verify_gone(timeout_grace_seconds)
        return (
            process.returncode or -signal.SIGKILL,
            stdout,
            stderr,
            True,
            forced_pipe_close,
            supervisor.evidence(terminated, survivors),
        )


def has_verdict(output: str) -> bool:
    return re.search(r"(?m)^VERDICT:[ \t]*\S.*$", output) is not None


def codex_lane(
    cwd: Path,
    prompt: str,
    barrier: threading.Barrier,
    timeout_seconds: float,
    timeout_grace_seconds: float,
) -> dict[str, Any]:
    barrier.wait()
    started = time.time_ns()
    attempts: list[dict[str, Any]] = []
    codex = command_path("codex")
    if codex:
        code, stdout, stderr, timed_out, forced_pipe_close, supervision = execute(
            [
                codex,
                "exec",
                "--yolo",
                "-m",
                "gpt-5.6-terra",
                "--config",
                "model_reasoning_effort=high",
            ],
            cwd,
            prompt,
            timeout_seconds,
            timeout_grace_seconds,
        )
        failure = "timeout" if timed_out else ("nonzero_exit" if code != 0 else None)
        if code == 0 and not has_verdict(stdout):
            failure = "missing_verdict"
        attempts.append(
            {
                "transport": "codex exec --yolo",
                "exit_code": code,
                "stderr": stderr,
                "failure": failure,
                "forced_pipe_close": forced_pipe_close,
                **supervision,
            }
        )
        if code == 0 and has_verdict(stdout):
            return {
                "status": "success",
                "transport": "codex exec --yolo",
                "stdout": stdout,
                "attempts": attempts,
                "started_ns": started,
                "ended_ns": time.time_ns(),
            }
    return {
        "status": "unavailable" if not attempts else "error",
        "transport": None,
        "stdout": stdout if attempts else "",
        "attempts": attempts,
        "started_ns": started,
        "ended_ns": time.time_ns(),
    }


def opus_lane(
    cwd: Path,
    prompt: str,
    barrier: threading.Barrier,
    timeout_seconds: float,
    timeout_grace_seconds: float,
) -> dict[str, Any]:
    barrier.wait()
    started = time.time_ns()
    claude = command_path("claude")
    if not claude:
        return {
            "status": "unavailable",
            "transport": None,
            "stdout": "",
            "attempts": [],
            "started_ns": started,
            "ended_ns": time.time_ns(),
        }
    command = [claude, "-p", "--model", "opus", "--dangerously-skip-permissions"]
    code, stdout, stderr, timed_out, forced_pipe_close, supervision = execute(
        command, cwd, prompt, timeout_seconds, timeout_grace_seconds
    )
    failure = "timeout" if timed_out else ("nonzero_exit" if code != 0 else None)
    if code == 0 and not has_verdict(stdout):
        failure = "missing_verdict"
    return {
        "status": "success" if code == 0 and has_verdict(stdout) else "error",
        "transport": "claude -p --model opus --dangerously-skip-permissions",
        "stdout": stdout,
        "attempts": [
            {
                "transport": "claude -p",
                "exit_code": code,
                "stderr": stderr,
                "failure": failure,
                "forced_pipe_close": forced_pipe_close,
                **supervision,
            }
        ],
        "started_ns": started,
        "ended_ns": time.time_ns(),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--ref", required=True)
    parser.add_argument("--packet-file", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=1200.0,
        help="maximum runtime for each primary reviewer (default: 1200)",
    )
    parser.add_argument(
        "--timeout-grace-seconds",
        type=float,
        default=2.0,
        help="bounded output-drain grace after a timeout (default: 2)",
    )
    return parser.parse_args(argv)


def cleanup_directory(path: Path) -> dict[str, Any]:
    try:
        shutil.rmtree(path)
    except FileNotFoundError:
        return {"success": True, "error": None, "path": str(path)}
    except OSError as error:
        return {"success": False, "error": str(error), "path": str(path)}
    return {"success": True, "error": None, "path": str(path)}


def create_clone(source: Path, destination: Path, sha: str) -> None:
    subprocess.run(
        [
            "git",
            "clone",
            "--quiet",
            "--no-local",
            "--no-checkout",
            str(source),
            str(destination),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    git(destination, "remote", "remove", "origin")
    git(destination, "checkout", "--quiet", "--detach", sha)


def descendant_termination_failures(reviewers: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    for reviewer, result in reviewers.items():
        for attempt in result.get("attempts", []):
            if attempt.get("failure") == "timeout" and not attempt.get(
                "descendant_termination_verified", False
            ):
                failures.append(reviewer)
                break
    return sorted(failures)


def main(
    argv: list[str] | None = None,
    *,
    create_clone_fn=create_clone,
    cleanup_fn=cleanup_directory,
) -> int:
    args = parse_args(argv)
    if args.timeout_seconds <= 0:
        print("--timeout-seconds must be greater than zero", file=sys.stderr)
        return 2
    if args.timeout_grace_seconds <= 0:
        print("--timeout-grace-seconds must be greater than zero", file=sys.stderr)
        return 2
    repo = Path(git(args.repo.resolve(), "rev-parse", "--show-toplevel").stdout.decode().strip())
    output_dir = args.output_dir.resolve()
    if output_dir == repo or repo in output_dir.parents:
        print("output directory must be outside the original checkout", file=sys.stderr)
        return 2
    if git(repo, "status", "--porcelain=v1", "--untracked-files=all").stdout:
        print("input checkout must be clean; dirty state is not represented by an exact SHA", file=sys.stderr)
        return 2
    sha = git(repo, "rev-parse", f"{args.ref}^{{commit}}").stdout.decode().strip()
    before = repository_snapshot(repo)
    packet = args.packet_file.read_text()
    prompt = (
        f"EXACT REVIEW SHA: {sha}\n"
        "The current directory is an independent detached clone at that SHA. Review only this checkout.\n\n"
        f"{packet}"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    temp_root = Path(tempfile.mkdtemp(prefix="advice-primary-pair-"))
    clones = {"codex": temp_root / "codex", "opus": temp_root / "opus"}
    receipt: dict[str, Any] = {
        "sha": sha,
        "parallel_dispatch": True,
        "checkout_kind": "independent_clone_no_local",
        "timeout_seconds": args.timeout_seconds,
        "timeout_grace_seconds": args.timeout_grace_seconds,
        "operation": {"success": False, "error": "operation did not complete"},
    }
    operational_error: str | None = None
    try:
        for path in clones.values():
            create_clone_fn(repo, path, sha)
        receipt["clone_shas"] = {
            name: git(path, "rev-parse", "HEAD").stdout.decode().strip()
            for name, path in clones.items()
        }
        if any(clone_sha != sha for clone_sha in receipt["clone_shas"].values()):
            raise RuntimeError("review clone did not resolve to the requested SHA")
        barrier = threading.Barrier(2)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = {
                "codex": executor.submit(
                    codex_lane,
                    clones["codex"],
                    prompt,
                    barrier,
                    args.timeout_seconds,
                    args.timeout_grace_seconds,
                ),
                "opus": executor.submit(
                    opus_lane,
                    clones["opus"],
                    prompt,
                    barrier,
                    args.timeout_seconds,
                    args.timeout_grace_seconds,
                ),
            }
            results = {name: future.result() for name, future in futures.items()}
        for name, result in results.items():
            (output_dir / f"{name}.txt").write_text(result.pop("stdout"))
        receipt["reviewers"] = results
        receipt["descendant_termination_failures"] = descendant_termination_failures(
            results
        )
        receipt["overlap_proven"] = max(r["started_ns"] for r in results.values()) <= min(
            r["ended_ns"] for r in results.values()
        )
        receipt["operation"] = {"success": True, "error": None}
    except Exception as error:
        operational_error = f"{type(error).__name__}: {error}"
        receipt["operation"] = {"success": False, "error": operational_error}
    finally:
        receipt["cleanup"] = cleanup_fn(temp_root)
        try:
            after = repository_snapshot(repo)
            receipt["original_changed_components"] = sorted(
                component for component in before if before[component] != after[component]
            )
            receipt["original_repository_unchanged"] = not receipt["original_changed_components"]
            receipt["original_checkout_unchanged"] = receipt["original_repository_unchanged"]
        except Exception as error:
            if operational_error is None:
                operational_error = f"{type(error).__name__}: {error}"
                receipt["operation"] = {"success": False, "error": operational_error}
            receipt["original_repository_unchanged"] = False
            receipt["original_checkout_unchanged"] = False
            receipt["original_changed_components"] = ["fingerprint_error"]
        try:
            (output_dir / "receipt.json").write_text(
                json.dumps(receipt, indent=2, sort_keys=True) + "\n"
            )
        except Exception as error:
            if operational_error is None:
                operational_error = f"{type(error).__name__}: {error}"

    if not receipt["cleanup"]["success"]:
        print(f"failed to clean disposable clones: {receipt['cleanup']['error']}", file=sys.stderr)
        return 5
    if operational_error is not None:
        print(f"primary reviewer operation failed: {operational_error}", file=sys.stderr)
        return 6
    if receipt.get("descendant_termination_failures"):
        print(
            "descendant termination could not be verified for: "
            + ", ".join(receipt["descendant_termination_failures"]),
            file=sys.stderr,
        )
        return 7
    if not receipt["original_repository_unchanged"]:
        print("original checkout or repository metadata changed while reviewers were running", file=sys.stderr)
        return 3
    if not any(result["status"] == "success" for result in receipt["reviewers"].values()):
        print("neither primary reviewer returned a verdict", file=sys.stderr)
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
