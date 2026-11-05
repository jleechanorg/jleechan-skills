"""Unit tests for agy_adapter.py -- the default real-model-call adapter.

The subprocess is stubbed via the injectable `runner` parameter so these
tests are fast/offline; the real subprocess path is exercised only in the
D2 real run and the live smoke test documented in STATE.md.
"""

from __future__ import annotations

import subprocess

import pytest
from agy_adapter import AgyCallError, agy_json_call, build_agy_command


def _completed(stdout="", stderr="", returncode=0):
    return subprocess.CompletedProcess(args=["agy"], returncode=returncode, stdout=stdout, stderr=stderr)


class TestBuildAgyCommand:
    def test_includes_new_project_flag(self):
        """--new-project is required -- without it agy attempts a project-header
        preamble that can hit a permission wall (see agy_adapter.py module docstring)."""
        cmd = build_agy_command("some-model", {"type": "object"})
        assert "--new-project" in cmd

    def test_includes_dangerously_skip_permissions(self):
        cmd = build_agy_command("some-model", {"type": "object"})
        assert "--dangerously-skip-permissions" in cmd

    def test_embeds_schema_as_json(self):
        cmd = build_agy_command("some-model", {"type": "object", "properties": {}})
        idx = cmd.index("--json-schema")
        assert '"type":"object"' in cmd[idx + 1]


class TestAgyJsonCall:
    def test_happy_path_returns_structured_output(self):
        def stub_runner(cmd, *, cwd, prompt, timeout):
            return _completed(
                stdout='{"status":"SUCCESS","structured_output":{"answer":4}}'
            )

        result = agy_json_call("2+2?", {"type": "object"}, runner=stub_runner)
        assert result == {"answer": 4}

    def test_nonzero_exit_raises(self):
        def stub_runner(cmd, *, cwd, prompt, timeout):
            return _completed(stderr="boom", returncode=1)

        with pytest.raises(AgyCallError, match="agy exited 1"):
            agy_json_call("x", {"type": "object"}, runner=stub_runner)

    def test_non_json_stdout_raises(self):
        def stub_runner(cmd, *, cwd, prompt, timeout):
            return _completed(stdout="not json at all")

        with pytest.raises(AgyCallError, match="not valid JSON"):
            agy_json_call("x", {"type": "object"}, runner=stub_runner)

    def test_status_error_raises(self):
        def stub_runner(cmd, *, cwd, prompt, timeout):
            return _completed(stdout='{"status":"ERROR","error":"auth failed"}')

        with pytest.raises(AgyCallError, match="did not succeed"):
            agy_json_call("x", {"type": "object"}, runner=stub_runner)

    def test_missing_structured_output_raises(self):
        def stub_runner(cmd, *, cwd, prompt, timeout):
            return _completed(stdout='{"status":"SUCCESS"}')

        with pytest.raises(AgyCallError, match="missing/malformed structured_output"):
            agy_json_call("x", {"type": "object"}, runner=stub_runner)

    def test_timeout_raises(self):
        def stub_runner(cmd, *, cwd, prompt, timeout):
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=timeout)

        with pytest.raises(AgyCallError, match="timed out"):
            agy_json_call("x", {"type": "object"}, runner=stub_runner, timeout_seconds=5)
