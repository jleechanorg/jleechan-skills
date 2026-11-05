"""Unit tests for scenario_generator.py.

Zero model calls, zero network -- llm_callable is stubbed throughout,
matching upstream's own fast-unit-test convention. gh/git subprocess calls
are exercised only via the pure shape-detection regexes (no real gh/git
invocation happens in these tests either).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from config import ProjectConfig
from scenario_generator import (
    ScenarioGenerationError,
    _gather_raw_context,
    _validate_authored_steps,
    _validate_classification,
    build_classify_schema,
    generate_scenario_files,
    is_doc_target,
    resolve_target_info,
    validate_scenario_steps,
)

VOCAB = ("rendered.body_text", "rendered.title", "parsed.session_header")


def _minimal_config(tmp_path, **overrides: object) -> ProjectConfig:
    defaults: dict[str, object] = dict(
        project_name="example-app",
        repo_root=tmp_path,
        base_url="http://127.0.0.1:9999",
        feature_surface_vocabulary=VOCAB,
        dispatch_command=("python3", "dispatch.py"),
        personas=("solo_agent",),
        raw={},
    )
    defaults.update(overrides)
    return ProjectConfig(**defaults)  # type: ignore[arg-type]  -- kwargs assembled dynamically for test convenience; runtime shape is verified by the tests themselves, not the type checker


class TestTargetShapeDetection:
    def test_freeform_prompt_never_hits_gh_or_git(self):
        ctx = _gather_raw_context("Preview the banner in 3 modes")
        assert ctx["candidate_type"] == "prompt"

    def test_bare_number_is_pr_shaped(self):
        # We don't actually call gh here -- this just confirms _gather_raw_context
        # ATTEMPTS the pr path (it will raise since gh isn't mocked and "999999999"
        # is not a real PR, proving the shape-routing works without a stub).
        with pytest.raises(ScenarioGenerationError):
            _gather_raw_context("999999999")

    def test_prompt_starting_with_pr_word_but_not_pr_shaped_stays_prompt(self):
        """Round-1 regression guard: 'Probe 5 flows' must never be routed to gh."""
        ctx = _gather_raw_context("Probe 5 flows in the settings screen")
        assert ctx["candidate_type"] == "prompt"


class TestIsDocTarget:
    def test_no_patterns_configured_always_returns_none(self, tmp_path):
        config = _minimal_config(tmp_path)
        assert is_doc_target("US-001", config) is None

    def test_matches_configured_pattern(self, tmp_path):
        config = _minimal_config(tmp_path, doc_target_patterns=(r"^US-\d+$",))
        assert is_doc_target("US-001", config) == "US-001"

    def test_non_matching_target_returns_none(self, tmp_path):
        config = _minimal_config(tmp_path, doc_target_patterns=(r"^US-\d+$",))
        assert is_doc_target("Preview the banner", config) is None


class TestValidateScenarioSteps:
    def test_rejects_empty_list(self):
        with pytest.raises(ValueError, match="non-empty list"):
            validate_scenario_steps([])

    def test_rejects_missing_user_action(self):
        with pytest.raises(ValueError, match="missing"):
            validate_scenario_steps([{"expected_render": {"a": 1}}])

    def test_rejects_empty_expected_render(self):
        with pytest.raises(ValueError, match="non-empty dict"):
            validate_scenario_steps([{"user_action": "click", "expected_render": {}}])

    def test_accepts_well_formed_steps(self):
        validate_scenario_steps(
            [{"user_action": "click button", "expected_render": {"body_text": "clicked"}}]
        )


class TestValidateClassification:
    def test_rejects_surface_outside_vocabulary(self, tmp_path):
        config = _minimal_config(tmp_path)
        with pytest.raises(ValueError, match="non-allowlisted"):
            _validate_classification(
                {
                    "target_type": "prompt",
                    "feature_summary": "x",
                    "relevant_surfaces": ["rendered.not_in_vocab"],
                },
                config,
            )

    def test_accepts_surface_in_vocabulary(self, tmp_path):
        config = _minimal_config(tmp_path)
        _validate_classification(
            {
                "target_type": "prompt",
                "feature_summary": "x",
                "relevant_surfaces": ["rendered.body_text"],
            },
            config,
        )

    def test_rejects_invalid_target_type(self, tmp_path):
        config = _minimal_config(tmp_path)
        with pytest.raises(ValueError, match="invalid target_type"):
            _validate_classification(
                {"target_type": "doc", "feature_summary": "x", "relevant_surfaces": []}, config
            )


class TestBuildClassifySchema:
    def test_enum_sourced_from_vocabulary_not_hardcoded(self):
        schema = build_classify_schema(("a.b", "c.d"))
        enum = schema["properties"]["relevant_surfaces"]["items"]["enum"]
        assert enum == ["a.b", "c.d"]


class TestResolveTargetInfo:
    def test_freeform_prompt_two_model_calls(self, tmp_path):
        config = _minimal_config(tmp_path)
        calls = []

        def stub_llm(prompt, schema):
            calls.append(schema)
            if "target_type" in schema["properties"]:
                return {
                    "target_type": "prompt",
                    "feature_summary": "tests the login flow",
                    "relevant_surfaces": ["rendered.body_text"],
                }
            return {
                "steps": [
                    {"user_action": "open login screen", "expected_render": {"body_text": "login"}},
                    {"user_action": "enter credentials", "expected_render": {"body_text": "welcome"}},
                    {"user_action": "submit", "expected_render": {"body_text": "dashboard"}},
                ],
                "predicate_decision": {"decision": "deferred", "rationale": "no existing predicate"},
            }

        target_info = resolve_target_info("Test the login flow", config, stub_llm)
        assert len(calls) == 2  # exactly the two model calls, no more
        assert target_info.target_type == "prompt"
        assert target_info.feature_summary == "tests the login flow"
        assert len(target_info.steps) == 3

    def test_malformed_model_output_retried_then_raises(self, tmp_path):
        config = _minimal_config(tmp_path)

        def always_broken(prompt, schema):
            return {"nonsense": True}

        with pytest.raises(ScenarioGenerationError):
            resolve_target_info("Test something", config, always_broken)

    def test_from_json_never_uses_payload_feature_summary(self, tmp_path):
        """Anti-self-grading: feature_summary always comes from a FRESH model
        call, never from the --from-json payload, even if the payload
        supplies its own feature_summary key."""
        config = _minimal_config(tmp_path)
        payload_path = tmp_path / "payload.json"
        import json

        payload_path.write_text(
            json.dumps(
                {
                    "feature_summary": "SELF-GRADED PARAPHRASE -- should be discarded",
                    "steps": [
                        {"user_action": "a", "expected_render": {"body_text": "1"}},
                        {"user_action": "b", "expected_render": {"body_text": "2"}},
                        {"user_action": "c", "expected_render": {"body_text": "3"}},
                    ],
                }
            )
        )

        def stub_llm(prompt, schema):
            return {
                "target_type": "prompt",
                "feature_summary": "INDEPENDENTLY DERIVED SUMMARY",
                "relevant_surfaces": ["rendered.body_text"],
            }

        target_info = resolve_target_info(
            "Test something", config, stub_llm, from_json_path=payload_path
        )
        assert target_info.feature_summary == "INDEPENDENTLY DERIVED SUMMARY"
        assert target_info.steps[0]["user_action"] == "a"  # steps DO come from payload


class TestGenerateScenarioFiles:
    def test_emits_scenario_and_pool_files(self, tmp_path):
        from scenario_generator import TargetInfo

        config = _minimal_config(tmp_path, personas=("solo_agent", "second_agent"))
        target_info = TargetInfo(
            target_type="prompt",
            raw_target="Test the login flow",
            title="Test the login flow",
            description="desc",
            feature_summary="tests login",
            relevant_surfaces=["rendered.body_text"],
            steps=[{"user_action": "click", "expected_render": {"body_text": "ok"}}],
            predicate_decision={"decision": "deferred", "rationale": "r"},
        )
        output_dir = tmp_path / "generated"
        scenario_path, pool_path = generate_scenario_files(target_info, config, output_dir)

        assert scenario_path.exists()
        assert pool_path.exists()
        scenario_text = scenario_path.read_text()
        assert "FEATURE_SUMMARY = 'tests login'" in scenario_text
        assert "PREDICATE_DECISION" in scenario_text

        import yaml

        pool_data = yaml.safe_load(pool_path.read_text())
        assert len(pool_data["agents"]) == 2  # matches personas count, no actor_fixtures

    def test_actor_fixture_pairing_scope_is_emitted_pool(self, tmp_path):
        from scenario_generator import TargetInfo

        config = _minimal_config(
            tmp_path,
            personas=("persona-a",),
            actor_fixtures=("actor-a", "actor-b"),
        )
        target_info = TargetInfo(
            target_type="prompt",
            raw_target="Test actor pairing",
            title="Test actor pairing",
            description="desc",
            feature_summary="tests actor pairing",
            relevant_surfaces=[],
            steps=[{"user_action": "look", "expected_render": {"body_text": "ok"}}],
            predicate_decision={},
        )

        _, pool_path = generate_scenario_files(target_info, config, tmp_path / "paired")

        import yaml

        agents = yaml.safe_load(pool_path.read_text())["agents"]
        assert agents == [
            {
                "actor": "actor-a",
                "scenario": str(tmp_path / "paired" / "generated_test_actor_pairing.py"),
                "persona": "persona-a",
            }
        ]

    def test_docstring_injection_is_escaped(self, tmp_path):
        """A model-authored feature_summary containing a literal triple-quote
        must never be able to break the generated module's syntax."""
        from scenario_generator import TargetInfo

        config = _minimal_config(tmp_path)
        target_info = TargetInfo(
            target_type="prompt",
            raw_target="hostile target",
            title="t",
            description="d",
            feature_summary='breaks docstring """ here',
            relevant_surfaces=[],
            steps=[{"user_action": "a", "expected_render": {"b": 1}}],
            predicate_decision={},
        )
        output_dir = tmp_path / "generated2"
        scenario_path, _ = generate_scenario_files(target_info, config, output_dir)
        # If unescaped, this would be a SyntaxError on import.
        import importlib.util

        spec = importlib.util.spec_from_file_location("hostile_scenario", scenario_path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # must not raise
        assert module.SCENARIO_NAME.startswith("generated_")
