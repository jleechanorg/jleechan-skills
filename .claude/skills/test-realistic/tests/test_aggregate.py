"""Unit tests for aggregate.py's target-scoped verdict aggregation.

Report-layer contract: aggregate_target_scoped must NEVER raise, and must
report an explicit malformed_reason (not a truthy-string default pass) for
every shape its strict helpers reject.
"""

from __future__ import annotations

from aggregate import aggregate_target_scoped


class TestCoverageOnly:
    def test_exercised_true_no_predicates_passes(self):
        verdict = aggregate_target_scoped({"exercised": True, "evidence_turn_indices": [0]}, [])
        assert verdict["target_pass"] is True
        assert verdict["headline_gate"] is None

    def test_exercised_false_fails(self):
        verdict = aggregate_target_scoped({"exercised": False}, [])
        assert verdict["target_pass"] is False

    def test_none_coverage_fails_with_reason(self):
        verdict = aggregate_target_scoped(None, [])
        assert verdict["target_pass"] is False
        assert "missing" in verdict["coverage"]["reason"].lower()

    def test_coverage_missing_exercised_key_fails(self):
        verdict = aggregate_target_scoped({"some_other_field": 1}, [])
        assert verdict["target_pass"] is False

    def test_coverage_not_a_dict_fails(self):
        verdict = aggregate_target_scoped("exercised", [])
        assert verdict["target_pass"] is False

    def test_exercised_truthy_string_never_silently_passes(self):
        """'exercised': 'false' is truthy in Python -- must not silently pass."""
        verdict = aggregate_target_scoped({"exercised": "false"}, [])
        assert verdict["target_pass"] is False
        assert "not a boolean" in verdict["coverage"]["reason"]


class TestPredicates:
    def test_all_predicates_pass_and_coverage_exercised(self):
        verdict = aggregate_target_scoped(
            {"exercised": True, "evidence_turn_indices": [1]},
            [{"name": "p1", "passed": True}],
        )
        assert verdict["target_pass"] is True

    def test_one_predicate_fails_overrides_exercised_true(self):
        verdict = aggregate_target_scoped(
            {"exercised": True, "evidence_turn_indices": [1]},
            [{"name": "p1", "passed": True}, {"name": "p2", "passed": False}],
        )
        assert verdict["target_pass"] is False

    def test_predicates_not_a_list_fails_with_reason(self):
        verdict = aggregate_target_scoped({"exercised": True}, "not-a-list")
        assert verdict["target_pass"] is False
        assert verdict["predicates"][0]["malformed_reason"]

    def test_predicate_item_not_a_dict_does_not_crash(self):
        verdict = aggregate_target_scoped({"exercised": True}, [None, "str", 5])
        assert verdict["target_pass"] is False
        assert len(verdict["predicates"]) == 3
        for p in verdict["predicates"]:
            assert "malformed_reason" in p

    def test_predicate_truthy_non_bool_passed_never_silently_passes(self):
        verdict = aggregate_target_scoped(
            {"exercised": True}, [{"name": "p1", "passed": "yes"}]
        )
        assert verdict["target_pass"] is False
        assert "non-boolean" in verdict["predicates"][0]["malformed_reason"]

    def test_empty_predicate_list_passes_vacuously(self):
        verdict = aggregate_target_scoped({"exercised": True, "evidence_turn_indices": [0]})
        assert verdict["target_pass"] is True
        assert verdict["predicates"] == []
