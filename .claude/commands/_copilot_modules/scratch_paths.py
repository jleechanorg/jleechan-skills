"""Canonical Scratch paths for the comment producer/consumer pair."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path


SCRATCH_RESOLVER = (
    Path(__file__).resolve().parents[2]
    / "skills"
    / "scratch-space"
    / "scripts"
    / "scratch-dir.sh"
)


def resolve_scratch_root() -> Path:
    result = subprocess.run(
        [str(SCRATCH_RESOLVER)],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or f"exit {result.returncode}"
        raise RuntimeError(f"canonical Scratch resolver failed: {detail}")
    value = result.stdout.strip()
    if not value:
        raise RuntimeError("canonical Scratch resolver returned no path")
    root = Path(value)
    if not root.is_absolute():
        raise RuntimeError("canonical Scratch resolver returned a relative path")
    return root.resolve()


def _safe_name(value: str, fallback: str) -> str:
    sanitized = re.sub(r"[^a-zA-Z0-9._-]", "", value or "")
    return sanitized or fallback


def copilot_cache_dir(repo_name: str, branch_name: str) -> Path:
    root = resolve_scratch_root()
    candidate = (root / _safe_name(repo_name, "unknown-repo") /
                 _safe_name(branch_name, "unknown-branch") / "copilot").resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise RuntimeError("comment cache escaped canonical Scratch root") from error
    return candidate
