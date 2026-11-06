"""Default real-model-call adapter for the generalized /test-realistic skill.

This wraps the ``agy`` CLI (a general-purpose, user-level agentic CLI tool --
NOT specific to any one project; confirmed via ``which agy``). It is the
default ``llm_callable`` implementation used by scenario_generator.py and
feature_coverage_judge.py when a project config doesn't supply its own.

Every call here is a REAL subprocess invocation of a REAL model. There is no
mock mode, no offline stub, no template fallback in this module -- that is
the entire point of the tool this skill generalizes (see
scripts/feature_coverage_judge.py's module docstring). Unit tests exercise
this module's parsing/error-handling logic by injecting a fake subprocess
runner, never by adding a "if TESTING" branch here.

Live-validated invocation recipe (2026-08-13, see STATE.md progress log):
    agy --new-project --model "<model>" --output-format json \\
        --json-schema '<inline-json-schema>' --dangerously-skip-permissions \\
        --print-timeout <Ns>
with the prompt piped via stdin from a fresh tempdir cwd. ``--new-project``
is required -- without it, agy attempts a project-header-check preamble that
tries to read the caller's global CLAUDE.md and can hit a permission wall
under --dangerously-skip-permissions in some environments.

This adapter inherits the real environment (including HOME) rather than
replicating a sanitized/minimized subprocess env -- a known simplification
relative to a project that wants tighter secret isolation; such a project
should supply its own llm_callable via config instead of relying on this
default.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable

AGY_BINARY = shutil.which("agy") or "agy"


class AgyCallError(RuntimeError):
    """Raised when the agy subprocess fails, times out, or returns unusable output.

    Callers must never catch this to fabricate a fallback verdict -- it is
    the model-call-failed signal that scenario_generator.py and
    feature_coverage_judge.py convert into their own hard-failure exceptions
    after their bounded retry is exhausted.
    """


def build_agy_command(
    model: str,
    json_schema: dict[str, Any],
    *,
    agy_binary: str = AGY_BINARY,
    timeout_seconds: int = 120,
) -> list[str]:
    return [
        agy_binary,
        "--new-project",
        "--model",
        model,
        "--output-format",
        "json",
        "--json-schema",
        json.dumps(json_schema, separators=(",", ":")),
        "--dangerously-skip-permissions",
        "--print-timeout",
        f"{timeout_seconds}s",
    ]


# Injectable so unit tests can exercise agy_json_call's parsing/error paths
# without a real subprocess. Production code must never override this
# except via the explicit `runner=` parameter below (no module-level
# monkeypatch-only seam).
SubprocessRunner = Callable[..., "subprocess.CompletedProcess[str]"]


def _default_runner(
    cmd: list[str], *, cwd: str, prompt: str, timeout: int
) -> "subprocess.CompletedProcess[str]":
    return subprocess.run(
        cmd,
        input=prompt,
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=timeout,
    )


def agy_json_call(
    prompt: str,
    json_schema: dict[str, Any],
    *,
    model: str = "gemini-3.8-flash-high",
    timeout_seconds: int = 120,
    runner: SubprocessRunner = _default_runner,
) -> dict[str, Any]:
    """Make one real agy CLI call constrained to json_schema and return the parsed object.

    Raises AgyCallError on any subprocess failure, timeout, non-SUCCESS
    status, or unparseable/missing structured_output. Never returns a
    partial or best-effort guess.
    """
    cmd = build_agy_command(model, json_schema, timeout_seconds=timeout_seconds)
    with tempfile.TemporaryDirectory(prefix="test-realistic-agy-") as working_dir:
        try:
            proc = runner(
                cmd,
                cwd=working_dir,
                prompt=prompt,
                timeout=timeout_seconds + 10,
            )
        except subprocess.TimeoutExpired as exc:
            raise AgyCallError(
                f"agy subprocess timed out after {timeout_seconds}s"
            ) from exc
        except OSError as exc:
            raise AgyCallError(f"agy subprocess failed to start: {exc}") from exc

    if proc.returncode != 0:
        raise AgyCallError(
            f"agy exited {proc.returncode}: "
            f"stderr={proc.stderr[:500] if proc.stderr else '<empty>'} "
            f"stdout={proc.stdout[:500] if proc.stdout else '<empty>'}"
        )

    try:
        envelope = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise AgyCallError(
            f"agy stdout was not valid JSON: {proc.stdout[:500]!r}"
        ) from exc

    if not isinstance(envelope, dict):
        raise AgyCallError(f"agy JSON envelope was not an object: {envelope!r}")

    if envelope.get("status") != "SUCCESS":
        raise AgyCallError(
            f"agy call did not succeed: status={envelope.get('status')!r} "
            f"error={envelope.get('error')!r}"
        )

    structured_output = envelope.get("structured_output")
    if not isinstance(structured_output, dict):
        raise AgyCallError(
            f"agy SUCCESS envelope missing/malformed structured_output: {envelope!r}"
        )

    return structured_output


def make_llm_callable(
    *, model: str = "gemini-3.8-flash-high", timeout_seconds: int = 120
) -> Callable[[str, dict[str, Any]], dict[str, Any]]:
    """Build a (prompt, json_schema) -> dict callable bound to a specific model/timeout.

    This is the shape feature_coverage_judge.py and scenario_generator.py
    expect from their `llm_callable` parameter.
    """

    def _call(prompt: str, json_schema: dict[str, Any]) -> dict[str, Any]:
        return agy_json_call(
            prompt, json_schema, model=model, timeout_seconds=timeout_seconds
        )

    return _call
