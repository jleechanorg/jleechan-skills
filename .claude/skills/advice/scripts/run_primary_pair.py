#!/usr/bin/env python3
"""Run the /advice Codex and Opus reviewers concurrently at one exact SHA.

The reviewers intentionally retain their full-permission flags. Repository
mutation risk is reduced by giving each process its own independent clone; this
is not an operating-system sandbox.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import functools
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


def git(
    repo: Path,
    *args: str,
    check: bool = True,
    timeout: float | None = None,
    deadline: float | None = None,
) -> subprocess.CompletedProcess[bytes]:
    if deadline is not None:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired(["git", *args], 0)
        timeout = remaining if timeout is None else min(timeout, remaining)
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
        timeout=timeout,
    )


def checkout_fingerprint(repo: Path, deadline: float | None = None) -> str:
    """Hash HEAD, tracked state, and nonignored untracked file content."""
    digest = hashlib.sha256()
    digest.update(git(repo, "rev-parse", "HEAD", deadline=deadline).stdout)
    digest.update(git(repo, "diff", "--binary", "HEAD", "--", deadline=deadline).stdout)
    untracked = git(
        repo, "ls-files", "--others", "--exclude-standard", "-z", deadline=deadline
    ).stdout
    for raw_path in sorted(filter(None, untracked.split(b"\0"))):
        digest.update(raw_path)
        path = repo / os.fsdecode(raw_path)
        if path.is_symlink():
            digest.update(b"symlink\0" + os.fsencode(os.readlink(path)))
        elif path.is_file():
            digest.update(path.read_bytes())
    return digest.hexdigest()


def ignored_path_metadata(repo: Path, deadline: float | None = None) -> bytes:
    """Serialize ignored-path metadata without opening regular-file content."""
    serialized = bytearray()
    ignored = git(
        repo,
        "ls-files",
        "--others",
        "--ignored",
        "--exclude-standard",
        "-z",
        deadline=deadline,
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


def repository_snapshot(repo: Path, deadline: float | None = None) -> dict[str, str]:
    """Return component hashes for mutation detection and useful diagnostics."""
    effective_hooks = Path(
        git(
            repo,
            "rev-parse",
            "--path-format=absolute",
            "--git-path",
            "hooks",
            deadline=deadline,
        ).stdout.decode().strip()
    )
    return {
        "checkout": checkout_fingerprint(repo, deadline),
        "ignored_metadata": digest_bytes(ignored_path_metadata(repo, deadline)),
        "local_config": digest_bytes(
            git(repo, "config", "--local", "--null", "--list", deadline=deadline).stdout
        ),
        "refs": digest_bytes(
            git(repo, "show-ref", "--head", check=False, deadline=deadline).stdout
        ),
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
        timeout=2.0,
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

    def __init__(self, root_pid: int, interval_seconds: float = 0.25) -> None:
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
        except (ProcessLookupError, PermissionError):
            pass
        try:
            process.kill()
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
    # Reviewers routinely wrap the VERDICT line in markdown (**VERDICT:**,
    # ## VERDICT, an em/en dash instead of a colon) — a literal `^VERDICT:`
    # anchor misclassifies those as missing_verdict even though the verdict is
    # present and readable. Accept an optional leading **/*/# marker and any
    # of the common separators between the word VERDICT and its content.
    return (
        re.search(
            r"(?mi)^\s*(?:\*{1,2}|#{1,6}\s*)?VERDICT(?:\s*[:—–-]\s*|\s+)\S.*$",
            output,
        )
        is not None
    )


DEFAULT_CODEX_MODEL = "gpt-6-sol"
CODEX_MODEL_ALLOWLIST = frozenset(
    {"gpt-6-astra", "gpt-6-luna", "gpt-6-sol", "gpt-6.1-sol"}
)


def validate_codex_model(model: str | None = None) -> str:
    """Return a supported Codex model ID, defaulting to the primary model."""
    if model is None or not str(model).strip():
        return DEFAULT_CODEX_MODEL
    cleaned = str(model).strip()
    if "5.6" in cleaned:
        raise ValueError(f"Codex 5.6 models are forbidden: {cleaned}")
    if cleaned not in CODEX_MODEL_ALLOWLIST:
        raise ValueError(
            "Codex model must be one of "
            f"{', '.join(sorted(CODEX_MODEL_ALLOWLIST))}: {cleaned}"
        )
    return cleaned


def wait_for_dispatch_barrier(
    barrier: threading.Barrier, timeout_seconds: float
) -> float:
    started = time.monotonic()
    try:
        barrier.wait(timeout=timeout_seconds)
    except threading.BrokenBarrierError as error:
        if time.monotonic() - started >= timeout_seconds:
            raise TimeoutError("reviewer dispatch barrier timed out") from error
        raise
    remaining = timeout_seconds - (time.monotonic() - started)
    if remaining <= 0:
        raise TimeoutError("reviewer dispatch budget expired")
    return remaining


def dispatch_failure_result(
    transport: str, started_ns: int, error: Exception
) -> dict[str, Any]:
    failure = "dispatch_timeout" if isinstance(error, TimeoutError) else "dispatch_aborted"
    return {
        "status": "error",
        "transport": None,
        "stdout": "",
        "attempts": [
            {
                "transport": transport,
                "exit_code": None,
                "stderr": str(error),
                "failure": failure,
            }
        ],
        "started_ns": started_ns,
        "ended_ns": time.time_ns(),
    }


def codex_lane(
    cwd: Path,
    prompt: str,
    barrier: threading.Barrier,
    timeout_seconds: float,
    timeout_grace_seconds: float,
    model: str | None = None,
) -> dict[str, Any]:
    resolved_model = validate_codex_model(
        model or os.environ.get("ADVICE_CODEX_MODEL") or DEFAULT_CODEX_MODEL
    )
    started = time.time_ns()
    try:
        timeout_seconds = wait_for_dispatch_barrier(barrier, timeout_seconds)
    except (TimeoutError, threading.BrokenBarrierError) as error:
        return dispatch_failure_result("codex exec --yolo", started, error)
    attempts: list[dict[str, Any]] = []
    codex = command_path("codex")
    if codex:
        code, stdout, stderr, timed_out, forced_pipe_close, supervision = execute(
            [
                codex,
                "exec",
                "--yolo",
                "-m",
                resolved_model,
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
    started = time.time_ns()
    try:
        timeout_seconds = wait_for_dispatch_barrier(barrier, timeout_seconds)
    except (TimeoutError, threading.BrokenBarrierError) as error:
        return dispatch_failure_result(
            "claude -p --model opus --dangerously-skip-permissions", started, error
        )
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
    parser.add_argument("--document", action="append", default=[],
                        help="saved Markdown document relative to repo; repeat for document-only review")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--reviewers",
        default="codex,opus",
        metavar="REVIEWER",
        help="reviewer subset (codex and/or opus, comma-separated; default: codex,opus)",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=1200.0,
        help="maximum runtime for each primary reviewer (default: 1200)",
    )
    parser.add_argument(
        "--attempt-timeout-seconds",
        type=float,
        default=600.0,
        help="shared setup, review, and cleanup deadline (default: 600)",
    )
    parser.add_argument(
        "--queued-at-epoch-ns",
        type=int,
        required=True,
        help="required UTC epoch nanoseconds when this reviewer attempt was queued or sent",
    )
    parser.add_argument(
        "--cleanup-budget-seconds",
        type=float,
        default=10.0,
        help="portion of the attempt deadline reserved for cleanup (default: 10)",
    )
    parser.add_argument(
        "--timeout-grace-seconds",
        type=float,
        default=2.0,
        help="bounded output-drain grace after a timeout (default: 2)",
    )
    parser.add_argument(
        "--codex-model",
        default=os.environ.get("ADVICE_CODEX_MODEL", "gpt-6-sol"),
        help="Codex model for primary review (default: gpt-6-sol; 5.6 models forbidden, only gpt 6 or 6.1 allowed)",
    )
    args = parser.parse_args(argv)
    try:
        args.codex_model = validate_codex_model(args.codex_model)
    except ValueError as err:
        parser.error(str(err))
    reviewers = args.reviewers.split(",")
    if not reviewers or any(name not in {"codex", "opus"} for name in reviewers):
        parser.error("--reviewers must contain only codex and opus")
    if len(set(reviewers)) != len(reviewers):
        parser.error("--reviewers must not contain duplicates")
    args.reviewers = reviewers
    return args


def cleanup_directory(path: Path) -> dict[str, Any]:
    try:
        shutil.rmtree(path)
    except FileNotFoundError:
        return {"success": True, "error": None, "path": str(path)}
    except OSError as error:
        return {"success": False, "error": str(error), "path": str(path)}
    return {"success": True, "error": None, "path": str(path)}


def create_clone(
    source: Path, destination: Path, sha: str, *, deadline: float
) -> None:
    def remaining() -> float:
        value = deadline - time.monotonic()
        if value <= 0:
            raise subprocess.TimeoutExpired(["git", "clone"], 0)
        return value

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
        timeout=remaining(),
    )
    git(destination, "remote", "remove", "origin", timeout=remaining())
    git(destination, "checkout", "--quiet", "--detach", sha, timeout=remaining())


def reviewer_timeouts(
    names: list[str], work_deadline: float, process_cap: float, drain_grace: float
) -> dict[str, float]:
    timeouts = {}
    for name in names:
        remaining = work_deadline - time.monotonic()
        timeout = min(process_cap, remaining - drain_grace)
        if timeout <= 0:
            raise TimeoutError("attempt_timeout before reviewer dispatch")
        timeouts[name] = timeout
    return timeouts


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


def read_review_documents(
    repo: Path, names: list[str], deadline: float | None = None
) -> dict[str, bytes]:
    """Read only explicitly selected, non-ignored Markdown files inside this repo."""
    documents = {}
    for name in names:
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts or ".git" in relative.parts:
            raise ValueError("--document must be a repository-relative document path")
        path = repo / relative
        if relative.suffix.lower() != ".md" or not path.is_file():
            raise ValueError("--document must name an existing Markdown file")
        if any(p.is_symlink() for p in (path, *path.parents) if p != repo and repo in p.parents):
            raise ValueError("linked document paths are not supported")
        if git(
            repo, "check-ignore", "--no-index", "--", str(relative),
            check=False, deadline=deadline,
        ).returncode == 0:
            raise ValueError("ignored documents must not be submitted implicitly")
        documents[relative.as_posix()] = path.read_bytes()
    return documents


def main(
    argv: list[str] | None = None,
    *,
    create_clone_fn=create_clone,
    cleanup_fn=cleanup_directory,
) -> int:
    process_started = time.monotonic()
    process_started_ns = time.time_ns()
    args = parse_args(argv)
    queued_at_ns = args.queued_at_epoch_ns
    if queued_at_ns <= 0 or queued_at_ns > process_started_ns:
        print("--queued-at-epoch-ns must be a positive timestamp no later than now", file=sys.stderr)
        return 2
    queue_elapsed = (process_started_ns - queued_at_ns) / 1_000_000_000
    attempt_started = process_started - queue_elapsed
    attempt_started_ns = queued_at_ns
    if args.timeout_seconds <= 0:
        print("--timeout-seconds must be greater than zero", file=sys.stderr)
        return 2
    if args.attempt_timeout_seconds <= 0:
        print("--attempt-timeout-seconds must be greater than zero", file=sys.stderr)
        return 2
    if args.cleanup_budget_seconds <= 0 or args.cleanup_budget_seconds >= args.attempt_timeout_seconds:
        print("--cleanup-budget-seconds must be positive and less than the attempt timeout", file=sys.stderr)
        return 2
    if args.timeout_grace_seconds <= 0:
        print("--timeout-grace-seconds must be greater than zero", file=sys.stderr)
        return 2
    attempt_deadline = attempt_started + args.attempt_timeout_seconds
    try:
        repo = Path(
            git(
                args.repo.resolve(),
                "rev-parse",
                "--show-toplevel",
                deadline=attempt_deadline,
            ).stdout.decode().strip()
        )
        output_dir = args.output_dir.resolve()
        if output_dir == repo or repo in output_dir.parents:
            print("output directory must be outside the original checkout", file=sys.stderr)
            return 2
        if not args.document and git(
            repo,
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            deadline=attempt_deadline,
        ).stdout:
            print(
                "input checkout must be clean; dirty state is not represented by an exact SHA",
                file=sys.stderr,
            )
            return 2
        sha = git(
            repo, "rev-parse", f"{args.ref}^{{commit}}", deadline=attempt_deadline
        ).stdout.decode().strip()
        before = repository_snapshot(repo, attempt_deadline)
        documents = read_review_documents(repo, args.document, attempt_deadline)
    except subprocess.TimeoutExpired as error:
        print(f"attempt_timeout during preflight: {error}", file=sys.stderr)
        return 4
    except (ValueError, OSError) as error:
        print(f"document review refused: {error}", file=sys.stderr)
        return 2
    document_hashes = {name: hashlib.sha256(data).hexdigest() for name, data in documents.items()}
    document_bundle_sha256 = hashlib.sha256(
        json.dumps(document_hashes, sort_keys=True).encode()
    ).hexdigest() if documents else None
    packet = args.packet_file.read_text()
    prompt = (
        f"EXACT REVIEW SHA: {sha}\n"
        "The current directory is an independent detached clone at that SHA. Review only this checkout.\n\n"
        f"{packet}"
    )
    if documents:
        prompt = (
            "DOCUMENT-ONLY REVIEW; repository HEAD is context, not the document identity.\n"
            f"CONTEXT SHA: {sha}\nDOCUMENT BUNDLE SHA256: {document_bundle_sha256}\n"
            "Read the complete selected files under .advice-review-documents in this clone.\n"
            "The mapping below identifies their original repository paths and exact SHA256 values.\n"
            "Do not approve code, a PR, or HEAD from this document review.\n"
            + json.dumps({f"{i}.md": {"source": name, "sha256": document_hashes[name]}
                          for i, name in enumerate(documents)}, sort_keys=True)
            + "\n\n" + packet
        )
    try:
        # Reserve the result path before dispatch. Reusing a directory could
        # leave an unselected review artifact beside a fresh receipt.
        output_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        print(
            "output directory must be a fresh path per invocation; "
            "refusing to reuse existing reviewer artifacts",
            file=sys.stderr,
        )
        return 2
    temp_root = Path(tempfile.mkdtemp(prefix="advice-primary-pair-"))
    work_deadline = attempt_deadline - args.cleanup_budget_seconds
    receipt: dict[str, Any] = {
        "sha": sha,
        "review_kind": "documents" if documents else "revision",
        "document_hashes": document_hashes,
        "document_bundle_sha256": document_bundle_sha256,
        "parallel_dispatch": len(args.reviewers) > 1,
        "checkout_kind": "independent_clone_no_local",
        "timeout_seconds": args.timeout_seconds,
        "attempt_started_ns": attempt_started_ns,
        "attempt_timeout_seconds": args.attempt_timeout_seconds,
        "cleanup_budget_seconds": args.cleanup_budget_seconds,
        "timeout_grace_seconds": args.timeout_grace_seconds,
        "codex_model": args.codex_model,
        "operation": {"success": False, "error": "operation did not complete"},
    }
    operational_error: str | None = None
    timeout_stage: str | None = None
    operation_stage = "clone_setup"
    try:
        reviewer_names = args.reviewers
        clones = {name: temp_root / name for name in reviewer_names}
        for path in clones.values():
            remaining = work_deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("attempt_timeout during clone setup")
            create_clone_fn(repo, path, sha, deadline=work_deadline)
            if time.monotonic() >= work_deadline:
                raise TimeoutError("attempt_timeout during clone setup")
            if documents:
                document_root = path / ".advice-review-documents"
                document_root.mkdir(exist_ok=False)
                for i, data in enumerate(documents.values()):
                    (document_root / f"{i}.md").write_bytes(data)
        receipt["clone_shas"] = {
            name: git(path, "rev-parse", "HEAD", deadline=work_deadline).stdout.decode().strip()
            for name, path in clones.items()
        }
        if any(clone_sha != sha for clone_sha in receipt["clone_shas"].values()):
            raise RuntimeError("review clone did not resolve to the requested SHA")
        operation_stage = "reviewer_execution"
        barrier = threading.Barrier(len(reviewer_names))
        lane_functions = {
            "codex": codex_lane,
            "opus": opus_lane,
        }
        reviewer_limits = reviewer_timeouts(
            reviewer_names,
            work_deadline,
            args.timeout_seconds,
            args.timeout_grace_seconds,
        )
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(reviewer_names)) as executor:
            futures = {}
            try:
                for name in reviewer_names:
                    reviewer_timeout = reviewer_limits[name]
                    if name == "codex":
                        futures[name] = executor.submit(
                            codex_lane,
                            clones[name],
                            prompt,
                            barrier,
                            reviewer_timeout,
                            args.timeout_grace_seconds,
                            args.codex_model,
                        )
                    else:
                        futures[name] = executor.submit(
                            opus_lane,
                            clones[name],
                            prompt,
                            barrier,
                            reviewer_timeout,
                            args.timeout_grace_seconds,
                        )
            except BaseException:
                barrier.abort()
                raise
            results = {name: future.result() for name, future in futures.items()}
        for name, result in results.items():
            (output_dir / f"{name}.txt").write_text(result.pop("stdout"))
        if time.monotonic() > work_deadline:
            for result in results.values():
                result["status"] = "error"
                result["failure"] = "attempt_timeout"
                for attempt in result.get("attempts", []):
                    attempt["failure"] = "attempt_timeout"
        receipt["reviewers"] = results
        receipt["descendant_termination_failures"] = descendant_termination_failures(
            results
        )
        receipt["overlap_proven"] = len(results) > 1 and max(
            r["started_ns"] for r in results.values()
        ) <= min(r["ended_ns"] for r in results.values())
        # Preserve every completed lane before integrity checks invalidate approval.
        for path in clones.values():
            for i, data in enumerate(documents.values()):
                if (path / ".advice-review-documents" / f"{i}.md").read_bytes() != data:
                    raise RuntimeError("review document copy changed during review")
        if documents and read_review_documents(repo, args.document, attempt_deadline) != documents:
            raise RuntimeError("source documents changed during review")
        receipt["operation"] = {"success": True, "error": None}
    except Exception as error:
        operational_error = f"{type(error).__name__}: {error}"
        receipt["operation"] = {"success": False, "error": operational_error}
        if isinstance(error, (subprocess.TimeoutExpired, TimeoutError)):
            timeout_stage = operation_stage
            receipt["timeout_stage"] = timeout_stage
    finally:
        cleanup_started = time.monotonic()
        receipt["cleanup"] = cleanup_fn(temp_root)
        receipt["cleanup"]["elapsed_seconds"] = time.monotonic() - cleanup_started
        receipt["cleanup"]["started_before_deadline"] = cleanup_started <= attempt_deadline
        receipt["elapsed_seconds"] = time.monotonic() - attempt_started
        receipt["attempt_deadline_exceeded"] = time.monotonic() > attempt_deadline
        if receipt["attempt_deadline_exceeded"]:
            for result in receipt.get("reviewers", {}).values():
                result["status"] = "error"
                result["failure"] = "attempt_timeout"
                for attempt in result.get("attempts", []):
                    attempt["failure"] = "attempt_timeout"
        try:
            after = repository_snapshot(repo, attempt_deadline)
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
        receipt["elapsed_seconds"] = time.monotonic() - attempt_started
        receipt["attempt_deadline_exceeded"] = time.monotonic() > attempt_deadline
        if receipt["attempt_deadline_exceeded"]:
            for result in receipt.get("reviewers", {}).values():
                result["status"] = "error"
                result["failure"] = "attempt_timeout"
                for attempt in result.get("attempts", []):
                    attempt["failure"] = "attempt_timeout"
        try:
            receipt_path = output_dir / "receipt.json"
            receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
            receipt["elapsed_seconds"] = time.monotonic() - attempt_started
            receipt["attempt_deadline_exceeded"] = time.monotonic() > attempt_deadline
            if receipt["attempt_deadline_exceeded"]:
                for result in receipt.get("reviewers", {}).values():
                    result["status"] = "error"
                    result["failure"] = "attempt_timeout"
                    for attempt in result.get("attempts", []):
                        attempt["failure"] = "attempt_timeout"
                receipt_path.write_text(
                    json.dumps(receipt, indent=2, sort_keys=True) + "\n"
                )
        except Exception as error:
            if operational_error is None:
                operational_error = f"{type(error).__name__}: {error}"

    if not receipt["cleanup"]["success"]:
        print(f"failed to clean disposable clones: {receipt['cleanup']['error']}", file=sys.stderr)
        return 5
    if receipt["attempt_deadline_exceeded"] or timeout_stage is not None:
        print("primary reviewer attempt exceeded its deadline", file=sys.stderr)
        return 4
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
