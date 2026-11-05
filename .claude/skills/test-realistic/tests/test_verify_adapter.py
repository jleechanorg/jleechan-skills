"""Unit tests for verify_adapter.py -- the onboarding conformance self-test.

subprocess_runner is injected (same pattern as target_scoped_run tests) so
these tests never spawn a real dispatcher. Since verify_adapter() picks its
own output_root internally (a fresh tempdir), tests spy on
build_dispatch_command to learn that path before writing fixture captures
into it from within the stub runner.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import verify_adapter as va_module
from config import ProjectConfig
from verify_adapter import (
    AdapterVerificationError,
    _write_fixture_pool_and_scenario,
    verify_adapter,
)

VOCAB = ("rendered.body_text",)


def _minimal_config(tmp_path: Path, **overrides: object) -> ProjectConfig:
    defaults: dict[str, object] = dict(
        project_name="example-app",
        repo_root=tmp_path,
        base_url="http://127.0.0.1:9999",
        feature_surface_vocabulary=VOCAB,
        dispatch_command=("python3", "dispatch.py"),
        personas=("solo_agent",),
        capture_glob="agent-*/capture.jsonl",
        raw={},
    )
    defaults.update(overrides)
    return ProjectConfig(**defaults)  # type: ignore[arg-type]


def _spy_on_output_root(monkeypatch, holder: dict) -> None:
    """Record verify_adapter's internally-chosen output_root into `holder`
    so a stub subprocess_runner knows where to write fixture captures."""
    real_build = va_module.build_dispatch_command

    def spying_build(cfg, *, pool_path, scenario_path, output_root, mode, base_url, turns):
        holder["output_root"] = output_root
        return real_build(
            cfg,
            pool_path=pool_path,
            scenario_path=scenario_path,
            output_root=output_root,
            mode=mode,
            base_url=base_url,
            turns=turns,
        )

    monkeypatch.setattr(va_module, "build_dispatch_command", spying_build)


def _write_capture(holder: dict, content: str) -> None:
    agent_dir = holder["output_root"] / "agent-0"
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "capture.jsonl").write_text(content)


class TestVerifyAdapterGreen:
    def test_fixture_pool_preserves_actor_shape(self, tmp_path):
        import yaml

        config = _minimal_config(
            tmp_path,
            personas=("persona-a",),
            actor_fixtures=("actor-a",),
        )
        pool_path, scenario_path = _write_fixture_pool_and_scenario(tmp_path, config)

        agents = yaml.safe_load(pool_path.read_text())["agents"]
        assert agents == [
            {
                "actor": "actor-a",
                "persona": "persona-a",
                "scenario": str(scenario_path),
            }
        ]

    def test_well_formed_captures_pass(self, tmp_path, monkeypatch):
        holder: dict = {}
        _spy_on_output_root(monkeypatch, holder)

        def runner(cmd, check=False, cwd=None):
            _write_capture(holder, '{"turn_index": 0, "rendered": {"body_text": "hello"}}\n')
            return subprocess.CompletedProcess(cmd, returncode=0)

        report = verify_adapter(_minimal_config(tmp_path), subprocess_runner=runner)
        assert report["total_turns"] == 1
        assert report["non_empty_turns"] == 1

    def test_arbitrary_top_level_keys_are_accepted(self, tmp_path, monkeypatch):
        """No key-name requirement -- feature_coverage_judge.py accepts any
        dict shape, so a project's own naming (e.g. turn/action_taken
        instead of turn_index/action_text) must pass equally."""
        holder: dict = {}
        _spy_on_output_root(monkeypatch, holder)

        def runner(cmd, check=False, cwd=None):
            _write_capture(holder, '{"turn": 1, "action_taken": "looked around"}\n')
            return subprocess.CompletedProcess(cmd, returncode=0)

        report = verify_adapter(_minimal_config(tmp_path), subprocess_runner=runner)
        assert report["total_turns"] == 1


class TestVerifyAdapterRed:
    def test_nonzero_dispatch_fails_even_with_valid_capture(self, tmp_path, monkeypatch):
        holder: dict = {}
        _spy_on_output_root(monkeypatch, holder)

        def runner(cmd, check=False, cwd=None):
            _write_capture(holder, '{"turn_index": 0, "rendered": {"body_text": "hello"}}\n')
            return subprocess.CompletedProcess(cmd, returncode=7)

        with pytest.raises(AdapterVerificationError, match="exited 7"):
            verify_adapter(_minimal_config(tmp_path), subprocess_runner=runner)

    def test_no_captures_produced_raises(self, tmp_path):
        def runner(cmd, check=False, cwd=None):
            return subprocess.CompletedProcess(cmd, returncode=0)  # writes nothing

        with pytest.raises(AdapterVerificationError, match="produced no files"):
            verify_adapter(_minimal_config(tmp_path), subprocess_runner=runner)

    def test_malformed_json_line_raises(self, tmp_path, monkeypatch):
        holder: dict = {}
        _spy_on_output_root(monkeypatch, holder)

        def runner(cmd, check=False, cwd=None):
            _write_capture(holder, "{not valid json\n")
            return subprocess.CompletedProcess(cmd, returncode=0)

        with pytest.raises(AdapterVerificationError, match="not valid JSON"):
            verify_adapter(_minimal_config(tmp_path), subprocess_runner=runner)

    def test_non_dict_turn_raises(self, tmp_path, monkeypatch):
        holder: dict = {}
        _spy_on_output_root(monkeypatch, holder)

        def runner(cmd, check=False, cwd=None):
            _write_capture(holder, '["not", "a", "dict"]\n')
            return subprocess.CompletedProcess(cmd, returncode=0)

        with pytest.raises(AdapterVerificationError, match="not a JSON object"):
            verify_adapter(_minimal_config(tmp_path), subprocess_runner=runner)

    def test_all_empty_dicts_raises(self, tmp_path, monkeypatch):
        holder: dict = {}
        _spy_on_output_root(monkeypatch, holder)

        def runner(cmd, check=False, cwd=None):
            _write_capture(holder, "{}\n{}\n")
            return subprocess.CompletedProcess(cmd, returncode=0)

        with pytest.raises(AdapterVerificationError, match="all 2 captured turn"):
            verify_adapter(_minimal_config(tmp_path), subprocess_runner=runner)
