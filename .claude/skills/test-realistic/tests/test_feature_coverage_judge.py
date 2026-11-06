"""Unit tests for feature_coverage_judge.py -- the anti-false-green gate.

Fast, zero-network: the llm_callable seam is stubbed in every test here,
matching upstream's own "Step 1: unit-test gate, zero model calls" convention.
The real, non-stubbed model call is only exercised in the D2 real run, never
in this unit-test tier.

These tests are written RED-then-GREEN on purpose: several prove the module
correctly REFUSES to produce a false-positive verdict (malformed judge
output, an exercised=True claim with no evidence, evidence indices from the
wrong batch) before any test proves it can produce a correct GREEN verdict.
"""

from __future__ import annotations

import pytest
from feature_coverage_judge import (
    CoverageJudgeUnavailableError,
    _batch_indexed_turns,
    _default_elide_turn,
    _validate_and_normalize_verdict,
    judge_feature_exercised,
)


def _stub_callable(responses):
    """Return an llm_callable that yields each of `responses` in order, one per call."""
    it = iter(responses)

    def _call(prompt, schema):
        return next(it)

    return _call


class TestValidateAndNormalizeVerdict:
    def test_rejects_non_dict(self):
        with pytest.raises(ValueError, match="not a dictionary"):
            _validate_and_normalize_verdict("not a dict")

    def test_rejects_missing_fields(self):
        with pytest.raises(ValueError, match="missing required"):
            _validate_and_normalize_verdict({"exercised": True})

    def test_rejects_non_bool_exercised(self):
        with pytest.raises(ValueError, match="must be a bool"):
            _validate_and_normalize_verdict(
                {"exercised": "yes", "evidence_turn_indices": [0], "rationale": "r"}
            )

    def test_rejects_exercised_true_with_no_evidence(self):
        """A claim without evidence is malformed, not a pass -- the whole point of this gate."""
        with pytest.raises(ValueError, match="requires non-empty evidence"):
            _validate_and_normalize_verdict(
                {"exercised": True, "evidence_turn_indices": [], "rationale": "touched it"}
            )

    def test_rejects_exercised_false_with_empty_rationale(self):
        with pytest.raises(ValueError, match="requires a non-empty rationale"):
            _validate_and_normalize_verdict(
                {"exercised": False, "evidence_turn_indices": [], "rationale": "   "}
            )

    def test_accepts_well_formed_true(self):
        result = _validate_and_normalize_verdict(
            {"exercised": True, "evidence_turn_indices": [2, 4], "rationale": "seen in turn 2"}
        )
        assert result == (True, [2, 4], "seen in turn 2")

    def test_accepts_well_formed_false(self):
        result = _validate_and_normalize_verdict(
            {"exercised": False, "evidence_turn_indices": [], "rationale": "never appeared"}
        )
        assert result == (False, [], "never appeared")


class TestJudgeFeatureExercisedRed:
    """Prove the gate goes RED (hard failure) on known-broken model output."""

    def test_no_captured_turns_returns_false_without_calling_model(self):
        called = []

        def _call(prompt, schema):
            called.append(1)
            return {}

        result = judge_feature_exercised("some feature", [], _call)
        assert result["exercised"] is False
        assert called == []  # no model call for an empty capture

    def test_malformed_json_response_exhausts_retry_and_raises(self):
        callable_ = _stub_callable([{"garbage": "shape"}, {"garbage": "shape"}])
        with pytest.raises(CoverageJudgeUnavailableError):
            judge_feature_exercised("feature", [{"rendered": {"body_text": "hi"}}], callable_)

    def test_exercised_true_with_empty_evidence_is_treated_as_malformed_and_retried(self):
        """This is the exact false-green shape this gate exists to catch."""
        callable_ = _stub_callable(
            [
                {"exercised": True, "evidence_turn_indices": [], "rationale": "trust me"},
                {"exercised": True, "evidence_turn_indices": [], "rationale": "trust me again"},
            ]
        )
        with pytest.raises(CoverageJudgeUnavailableError):
            judge_feature_exercised("feature", [{"rendered": {"body_text": "hi"}}], callable_)

    def test_evidence_index_outside_batch_is_rejected(self):
        """A model echoing an index that isn't even in this batch must not be trusted."""
        callable_ = _stub_callable(
            [
                {"exercised": True, "evidence_turn_indices": [999], "rationale": "r"},
                {"exercised": True, "evidence_turn_indices": [999], "rationale": "r"},
            ]
        )
        with pytest.raises(CoverageJudgeUnavailableError):
            judge_feature_exercised("feature", [{"rendered": {"body_text": "hi"}}], callable_)

    def test_llm_callable_raising_is_retried_then_raises_coverage_error(self):
        def _always_raises(prompt, schema):
            raise RuntimeError("agy subprocess timed out")

        with pytest.raises(CoverageJudgeUnavailableError, match="RuntimeError"):
            judge_feature_exercised("feature", [{"rendered": {"body_text": "hi"}}], _always_raises)


class TestJudgeFeatureExercisedGreen:
    """Prove the gate correctly reports GREEN when the model gives well-formed evidence."""

    def test_single_turn_exercised(self):
        callable_ = _stub_callable(
            [{"exercised": True, "evidence_turn_indices": [0], "rationale": "clicked the button"}]
        )
        result = judge_feature_exercised(
            "the new button works", [{"rendered": {"body_text": "clicked"}}], callable_
        )
        assert result["exercised"] is True
        assert result["evidence_turn_indices"] == [0]

    def test_not_exercised(self):
        callable_ = _stub_callable(
            [{"exercised": False, "evidence_turn_indices": [], "rationale": "feature never appeared"}]
        )
        result = judge_feature_exercised(
            "the new button works", [{"rendered": {"body_text": "unrelated"}}], callable_
        )
        assert result["exercised"] is False

    def test_retry_recovers_after_one_malformed_attempt(self):
        callable_ = _stub_callable(
            [
                {"garbage": "shape"},
                {"exercised": True, "evidence_turn_indices": [0], "rationale": "second try worked"},
            ]
        )
        result = judge_feature_exercised("feature", [{"rendered": {}}], callable_)
        assert result["exercised"] is True


class TestBatching:
    def test_batches_by_char_budget(self):
        indexed = [(i, {"rendered": {"body_text": "x" * 100}}) for i in range(10)]
        batches = _batch_indexed_turns(indexed, budget=500)
        assert len(batches) > 1
        # order preserved across batches
        flat = [i for batch in batches for i, _ in batch]
        assert flat == list(range(10))

    def test_oversized_single_turn_gets_own_batch(self):
        indexed = [(0, {"rendered": {"body_text": "x" * 10_000}}), (1, {"rendered": {}})]
        batches = _batch_indexed_turns(indexed, budget=100)
        assert len(batches) == 2
        assert batches[0] == [indexed[0]]

    def test_global_index_labeling_survives_multi_batch_combination(self, monkeypatch):
        """Two batches, each reporting exercised=True with DIFFERENT global
        indices -- the combined verdict must OR them together and dedupe,
        never silently drop one batch's evidence."""
        import json as _json

        import feature_coverage_judge as fcj

        indexed = [(i, {"rendered": {"body_text": "x" * 100}}) for i in range(4)]
        # Force exactly 2 turns per batch: budget fits 2 turns but not 3.
        one_turn_size = len(_json.dumps(indexed[0][1]))
        budget = one_turn_size * 2 + 10
        batches = _batch_indexed_turns(indexed, budget=budget)
        assert len(batches) == 2

        # Override the module's real per-call budget so judge_feature_exercised
        # itself (not just the helper called directly above) actually splits
        # into 2 batches -- the module docstring documents this seam
        # explicitly for tests.
        monkeypatch.setattr(fcj, "_PROMPT_BATCH_BUDGET_CHARS", budget)

        responses = [
            {"exercised": True, "evidence_turn_indices": [0], "rationale": "batch1 hit"},
            {"exercised": True, "evidence_turn_indices": [2], "rationale": "batch2 hit"},
        ]
        callable_ = _stub_callable(responses)
        result = judge_feature_exercised(
            "feature", [t for _, t in indexed], callable_
        )
        assert result["exercised"] is True
        assert result["evidence_turn_indices"] == [0, 2]
        assert "batch1 hit" in result["rationale"]
        assert "batch2 hit" in result["rationale"]


class TestDefaultElideTurn:
    def test_elides_long_strings(self):
        turn = {"rendered": {"body_text": "x" * 5000, "short": "ok"}}
        elided = _default_elide_turn(turn)
        assert elided["rendered"]["body_text"].startswith("<elided:5000chars>")
        assert elided["rendered"]["short"] == "ok"

    def test_leaves_short_strings_untouched(self):
        turn = {"rendered": {"body_text": "hello"}}
        assert _default_elide_turn(turn) == turn
