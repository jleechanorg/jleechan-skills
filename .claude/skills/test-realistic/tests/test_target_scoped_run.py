"""Unit/integration tests for target_scoped_run.py -- the target-scoped orchestrator.

subprocess_runner and judge_fn are both injected (matching upstream's own
test seams) so these tests exercise the full main() flow -- pre-dispatch
refusal guard, capture collection, verdict artifact shape, exit codes --
without any real subprocess or model call.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import yaml
from feature_coverage_judge import CoverageJudgeUnavailableError, CoverageVerdict
from target_scoped_run import (
    build_dispatch_command,
    collect_pre_existing_artifacts,
    main,
)

CONFIG_TOML = """
project_name = "example-app"
repo_root = "{repo_root}"
base_url = "http://127.0.0.1:9999"
feature_surface_vocabulary = ["rendered.body_text"]
dispatch_command = ["python3", "dispatch.py", "--output-root", "{{output_root}}", "--mode", "{{mode}}"]
"""


def _setup_project(tmp_path: Path) -> Path:
    config_path = tmp_path / ".test-realistic.toml"
    config_path.write_text(CONFIG_TOML.format(repo_root=tmp_path))
    return config_path


def _write_pool(tmp_path: Path, n_agents: int = 1) -> Path:
    pool_path = tmp_path / "pool.yaml"
    pool_path.write_text(yaml.safe_dump({"agents": [{"persona": f"p{i}"} for i in range(n_agents)]}))
    return pool_path


def _write_scenario(tmp_path: Path, feature_summary: str = "tests the thing") -> Path:
    scenario_path = tmp_path / "generated_x.py"
    scenario_path.write_text(
        f'FEATURE_SUMMARY = {feature_summary!r}\nRELEVANT_SURFACES = ["rendered.body_text"]\n'
    )
    return scenario_path


def _write_capture(output_root: Path, agent_id: str, turns: list[dict]) -> None:
    agent_dir = output_root / f"agent-{agent_id}"
    agent_dir.mkdir(parents=True, exist_ok=True)
    capture_path = agent_dir / "capture.jsonl"
    capture_path.write_text("\n".join(json.dumps(t) for t in turns) + "\n")


class TestBuildDispatchCommand:
    def test_renders_template_placeholders(self, tmp_path):
        from config import load_config

        config_path = _setup_project(tmp_path)
        config = load_config(config_path)
        cmd = build_dispatch_command(
            config,
            pool_path=tmp_path / "pool.yaml",
            scenario_path=tmp_path / "s.py",
            output_root=tmp_path / "out",
            mode="headless",
            base_url="http://x",
            turns=5,
        )
        assert str(tmp_path / "out") in cmd
        assert "headless" in cmd


class TestCollectPreExistingArtifacts:
    def test_empty_output_root_has_none(self, tmp_path):
        assert collect_pre_existing_artifacts(tmp_path, "agent-*/capture.jsonl") == []

    def test_finds_stale_capture(self, tmp_path):
        _write_capture(tmp_path, "0", [{"rendered": {"body_text": "x"}}])
        found = collect_pre_existing_artifacts(tmp_path, "agent-*/capture.jsonl")
        assert len(found) == 1


class TestMainRed:
    """Prove the orchestrator refuses/fails loud on known-broken inputs."""

    def test_refuses_stale_output_root(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _setup_project(tmp_path)
        pool_path = _write_pool(tmp_path)
        scenario_path = _write_scenario(tmp_path)
        output_root = tmp_path / "out"
        _write_capture(output_root, "0", [{"rendered": {}}])  # stale artifact

        rc = main(
            [
                "--pool",
                str(pool_path),
                "--scenario",
                str(scenario_path),
                "--output-root",
                str(output_root),
            ],
            subprocess_runner=lambda *a, **k: pytest.fail("must not dispatch over stale output-root"),
            judge_fn=lambda *a, **k: pytest.fail("must not judge a stale run"),
        )
        assert rc == 1

    def test_no_captures_produced_fails(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _setup_project(tmp_path)
        pool_path = _write_pool(tmp_path)
        scenario_path = _write_scenario(tmp_path)
        output_root = tmp_path / "out2"

        def fake_dispatch(cmd, check=False, cwd=None):
            return subprocess.CompletedProcess(cmd, returncode=0)  # dispatched but wrote nothing

        rc = main(
            ["--pool", str(pool_path), "--scenario", str(scenario_path), "--output-root", str(output_root)],
            subprocess_runner=fake_dispatch,
            judge_fn=lambda *a, **k: pytest.fail("must not judge with zero captures"),
        )
        assert rc == 1

    def test_coverage_judge_unavailable_is_hard_failure(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _setup_project(tmp_path)
        pool_path = _write_pool(tmp_path)
        scenario_path = _write_scenario(tmp_path)
        output_root = tmp_path / "out3"

        def fake_dispatch(cmd, check=False, cwd=None):
            _write_capture(output_root, "0", [{"rendered": {"body_text": "hi"}}])
            return subprocess.CompletedProcess(cmd, returncode=0)

        def raising_judge(*a, **k):
            raise CoverageJudgeUnavailableError("model unreachable")

        rc = main(
            ["--pool", str(pool_path), "--scenario", str(scenario_path), "--output-root", str(output_root)],
            subprocess_runner=fake_dispatch,
            judge_fn=raising_judge,
        )
        assert rc == 1
        # No verdict artifact should exist -- a hard failure must not fabricate one.
        assert not (output_root / "target_scoped_verdict.json").exists()


class TestMainGreen:
    def test_missing_actor_capture_fails_before_coverage_judge(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _setup_project(tmp_path)
        pool_path = _write_pool(tmp_path, n_agents=3)
        scenario_path = _write_scenario(tmp_path)
        output_root = tmp_path / "out-missing-actor"
        judge_called = False

        def fake_dispatch(cmd, check=False, cwd=None):
            _write_capture(output_root, "0", [{"rendered": {"body_text": "hi"}}])
            return subprocess.CompletedProcess(cmd, returncode=0)

        def passing_judge(feature_summary, turns) -> CoverageVerdict:
            nonlocal judge_called
            judge_called = True
            return {"exercised": True, "evidence_turn_indices": [0], "rationale": "seen"}

        rc = main(
            [
                "--pool",
                str(pool_path),
                "--scenario",
                str(scenario_path),
                "--output-root",
                str(output_root),
            ],
            subprocess_runner=fake_dispatch,
            judge_fn=passing_judge,
        )

        assert rc == 1
        assert judge_called is False

    def test_complete_actor_pool_reaches_coverage_judge(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _setup_project(tmp_path)
        pool_path = _write_pool(tmp_path, n_agents=3)
        scenario_path = _write_scenario(tmp_path)
        output_root = tmp_path / "out-complete-pool"

        def fake_dispatch(cmd, check=False, cwd=None):
            for agent_id in ("0", "1", "2"):
                _write_capture(output_root, agent_id, [{"rendered": {"body_text": "hi"}}])
            return subprocess.CompletedProcess(cmd, returncode=0)

        def passing_judge(feature_summary, turns) -> CoverageVerdict:
            assert len(turns) == 3
            return {"exercised": True, "evidence_turn_indices": [0], "rationale": "seen"}

        rc = main(
            [
                "--pool",
                str(pool_path),
                "--scenario",
                str(scenario_path),
                "--output-root",
                str(output_root),
            ],
            subprocess_runner=fake_dispatch,
            judge_fn=passing_judge,
        )

        assert rc == 0
        artifact = json.loads((output_root / "target_scoped_verdict.json").read_text())
        assert artifact["target_scoped_verdict"]["target_pass"] is True

    def test_exercised_true_and_dispatch_ok_passes(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _setup_project(tmp_path)
        pool_path = _write_pool(tmp_path)
        scenario_path = _write_scenario(tmp_path)
        output_root = tmp_path / "out4"

        def fake_dispatch(cmd, check=False, cwd=None):
            _write_capture(output_root, "0", [{"rendered": {"body_text": "hi"}}])
            return subprocess.CompletedProcess(cmd, returncode=0)

        def passing_judge(feature_summary, turns) -> CoverageVerdict:
            return {"exercised": True, "evidence_turn_indices": [0], "rationale": "seen"}

        rc = main(
            ["--pool", str(pool_path), "--scenario", str(scenario_path), "--output-root", str(output_root)],
            subprocess_runner=fake_dispatch,
            judge_fn=passing_judge,
        )
        assert rc == 0
        artifact = json.loads((output_root / "target_scoped_verdict.json").read_text())
        assert artifact["target_scoped_verdict"]["target_pass"] is True
        assert artifact["project_name"] == "example-app"

    def test_exercised_false_fails_even_if_dispatch_ok(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _setup_project(tmp_path)
        pool_path = _write_pool(tmp_path)
        scenario_path = _write_scenario(tmp_path)
        output_root = tmp_path / "out5"

        def fake_dispatch(cmd, check=False, cwd=None):
            _write_capture(output_root, "0", [{"rendered": {"body_text": "unrelated"}}])
            return subprocess.CompletedProcess(cmd, returncode=0)

        def failing_judge(feature_summary, turns) -> CoverageVerdict:
            return {"exercised": False, "evidence_turn_indices": [], "rationale": "never touched"}

        rc = main(
            ["--pool", str(pool_path), "--scenario", str(scenario_path), "--output-root", str(output_root)],
            subprocess_runner=fake_dispatch,
            judge_fn=failing_judge,
        )
        assert rc == 1

    def test_nonzero_dispatch_fails_without_excuse_flag(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _setup_project(tmp_path)
        pool_path = _write_pool(tmp_path)
        scenario_path = _write_scenario(tmp_path)
        output_root = tmp_path / "out6"

        def fake_dispatch(cmd, check=False, cwd=None):
            _write_capture(output_root, "0", [{"rendered": {"body_text": "hi"}}])
            return subprocess.CompletedProcess(cmd, returncode=1)  # dispatcher itself crashed

        def passing_judge(feature_summary, turns) -> CoverageVerdict:
            return {"exercised": True, "evidence_turn_indices": [0], "rationale": "seen"}

        rc = main(
            ["--pool", str(pool_path), "--scenario", str(scenario_path), "--output-root", str(output_root)],
            subprocess_runner=fake_dispatch,
            judge_fn=passing_judge,
        )
        assert rc == 1  # even a passing judge doesn't excuse a crashed dispatcher by default
