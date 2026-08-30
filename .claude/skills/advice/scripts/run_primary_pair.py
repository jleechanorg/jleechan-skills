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
import shutil
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
    """Hash HEAD plus all tracked changes and untracked file content."""
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


def repository_fingerprint(repo: Path) -> str:
    """Hash checkout state plus local configuration and refs."""
    digest = hashlib.sha256()
    digest.update(checkout_fingerprint(repo).encode())
    digest.update(git(repo, "config", "--local", "--null", "--list").stdout)
    digest.update(git(repo, "show-ref", "--head", check=False).stdout)
    common_dir_raw = git(repo, "rev-parse", "--git-common-dir").stdout.decode().strip()
    common_dir = Path(common_dir_raw)
    if not common_dir.is_absolute():
        common_dir = repo / common_dir
    hooks = common_dir.resolve() / "hooks"
    if hooks.is_dir():
        for path in sorted(item for item in hooks.rglob("*") if item.is_file()):
            digest.update(str(path.relative_to(hooks)).encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def command_path(name: str) -> str | None:
    return shutil.which(name)


def execute(command: list[str], cwd: Path, prompt: str) -> tuple[int, str, str]:
    completed = subprocess.run(
        [*command, prompt],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return completed.returncode, completed.stdout, completed.stderr


def has_verdict(output: str) -> bool:
    return re.search(r"(?m)^VERDICT:[ \t]+\S.*$", output) is not None


def codex_lane(cwd: Path, prompt: str, barrier: threading.Barrier) -> dict[str, Any]:
    barrier.wait()
    started = time.time_ns()
    attempts: list[dict[str, Any]] = []
    codex = command_path("codex")
    if codex:
        code, stdout, stderr = execute(
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
        )
        failure = "nonzero_exit" if code != 0 else None
        if code == 0 and not has_verdict(stdout):
            failure = "missing_verdict"
        attempts.append(
            {
                "transport": "codex exec --yolo",
                "exit_code": code,
                "stderr": stderr,
                "failure": failure,
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


def opus_lane(cwd: Path, prompt: str, barrier: threading.Barrier) -> dict[str, Any]:
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
    code, stdout, stderr = execute(command, cwd, prompt)
    failure = "nonzero_exit" if code != 0 else None
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
            }
        ],
        "started_ns": started,
        "ended_ns": time.time_ns(),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--ref", required=True)
    parser.add_argument("--packet-file", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo = Path(git(args.repo.resolve(), "rev-parse", "--show-toplevel").stdout.decode().strip())
    output_dir = args.output_dir.resolve()
    if output_dir == repo or repo in output_dir.parents:
        print("output directory must be outside the original checkout", file=sys.stderr)
        return 2
    if git(repo, "status", "--porcelain=v1", "--untracked-files=all").stdout:
        print("input checkout must be clean; dirty state is not represented by an exact SHA", file=sys.stderr)
        return 2
    sha = git(repo, "rev-parse", f"{args.ref}^{{commit}}").stdout.decode().strip()
    before = repository_fingerprint(repo)
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
    }
    try:
        for path in clones.values():
            subprocess.run(
                ["git", "clone", "--quiet", "--no-local", "--no-checkout", str(repo), str(path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
            git(path, "remote", "remove", "origin")
            git(path, "checkout", "--quiet", "--detach", sha)
        receipt["clone_shas"] = {
            name: git(path, "rev-parse", "HEAD").stdout.decode().strip()
            for name, path in clones.items()
        }
        if any(clone_sha != sha for clone_sha in receipt["clone_shas"].values()):
            raise RuntimeError("review clone did not resolve to the requested SHA")
        barrier = threading.Barrier(2)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = {
                "codex": executor.submit(codex_lane, clones["codex"], prompt, barrier),
                "opus": executor.submit(opus_lane, clones["opus"], prompt, barrier),
            }
            results = {name: future.result() for name, future in futures.items()}
        for name, result in results.items():
            (output_dir / f"{name}.txt").write_text(result.pop("stdout"))
        receipt["reviewers"] = results
        receipt["overlap_proven"] = max(r["started_ns"] for r in results.values()) <= min(
            r["ended_ns"] for r in results.values()
        )
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)
        receipt["original_repository_unchanged"] = repository_fingerprint(repo) == before
        receipt["original_checkout_unchanged"] = receipt["original_repository_unchanged"]
        (output_dir / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")

    if not receipt["original_repository_unchanged"]:
        print("original checkout or repository metadata changed while reviewers were running", file=sys.stderr)
        return 3
    if not any(result["status"] == "success" for result in receipt["reviewers"].values()):
        print("neither primary reviewer returned a verdict", file=sys.stderr)
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
