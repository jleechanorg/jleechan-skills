"""Target-scoped verdict aggregation for the generalized /test-realistic skill.

This is a generalized port of a source harness's own aggregation module
(see ../PROVENANCE.md) -- specifically only its target-scoped path
(``aggregate_target_scoped`` and its helpers). The source file also defines
a project-specific ``HEADLINE_INVARIANTS`` gate (four domain-specific
predicate names, a hardcoded agent x turn envelope) used by that source
project's own hand-authored regression scenarios -- that gate is NOT ported
here because it is entirely project-specific game logic, not part of the
universal pipeline. A project
that wants an equivalent "did every dispatched lane/turn complete and pass
its own domain invariants" gate should implement it via its own
``runner_excuse_predicate`` (see config.py) rather than this module growing
project-specific predicate names.

target_pass reduces to coverage["exercised"] is True whenever no predicate
results are supplied (an empty predicate list passes vacuously) -- matching
upstream's v1 "coverage-only" posture. Wiring authored-predicate correctness
signals into target_pass is supported (pass predicate_results) but is
project-authored, not something this module invents.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml


def _coverage_exercised_strict(coverage: dict) -> tuple[bool, str | None]:
    """Return (exercised, malformed_reason) for a coverage dict's 'exercised' field.

    'exercised' must be an actual bool. A truthy non-bool value (e.g. the
    string "false", which is truthy in Python) must never silently count as
    a pass, and a falsy non-bool value must never silently count as a fail
    without being flagged. Returns malformed_reason=None when well-formed.
    """
    exercised = coverage.get("exercised")
    if not isinstance(exercised, bool):
        return False, (
            "coverage.exercised is not a boolean "
            f"(got {type(exercised).__name__}: {exercised!r})"
        )
    return exercised, None


def _predicate_passed_strict(predicate: Any) -> tuple[bool, str | None]:
    """Return (passed, malformed_reason) for a single predicate result.

    'passed' must be an actual bool -- a truthy non-bool value (e.g. the
    string "no") must never silently count as a pass. A predicate item that
    is not even a dict (None, a string, an int, ...) is likewise malformed
    rather than raising an AttributeError on ``.get``. Returns
    malformed_reason=None when the predicate is well-formed.
    """
    if not isinstance(predicate, dict):
        return False, (
            f"predicate item is not a dict (got {type(predicate).__name__}: {predicate!r})"
        )
    passed = predicate.get("passed")
    if not isinstance(passed, bool):
        name = predicate.get("name", "<unnamed>")
        return False, (
            f"predicate '{name}' has non-boolean 'passed' field "
            f"(got {type(passed).__name__}: {passed!r})"
        )
    return passed, None


def _normalize_predicates(predicates: Any) -> tuple[list[dict], bool]:
    """Validate predicates strictly; never raises (this is the report layer).

    Exact behavior for every malformed shape the strict helpers reject:
    - ``predicates`` itself is not a list (e.g. a string or a dict): treated
      as a single malformed entry describing the whole value, and the run
      fails (``all_pass=False``).
    - An individual list item is not a dict (``None``, a string, an int, a
      nested list, ...): wrapped into a dict carrying ``original_value`` and
      ``malformed_reason``, counted as failing.
    - A well-formed dict item with a non-boolean ``passed`` field: annotated
      with ``malformed_reason`` on a shallow copy.

    Malformed predicates get an annotated dict; well-formed predicates are
    returned unmodified (same dict reference) so existing equality checks on
    well-formed input lists still hold.
    """
    if not isinstance(predicates, list):
        return (
            [
                {
                    "malformed_reason": (
                        "predicate_results is not a list "
                        f"(got {type(predicates).__name__}: {predicates!r})"
                    )
                }
            ],
            False,
        )

    normalized: list[dict] = []
    all_pass = True
    for predicate in predicates:
        passed, reason = _predicate_passed_strict(predicate)
        if not passed:
            all_pass = False
        if reason:
            if isinstance(predicate, dict):
                predicate = dict(predicate)
                predicate["malformed_reason"] = reason
            else:
                predicate = {
                    "original_value": repr(predicate),
                    "malformed_reason": reason,
                }
        normalized.append(predicate)
    return normalized, all_pass


def aggregate_target_scoped(
    coverage_result: Any, predicate_results: Any = None
) -> dict:
    """Aggregate target-scoped scenario results into a verdict dict.

    Parameter types are intentionally ``Any``, not ``dict | None`` -- this
    is the permissive REPORT layer and its own contract (below) is that it
    accepts and gracefully reports on every malformed shape a caller could
    hand it (a ``CoverageVerdict`` TypedDict, a plain dict, a non-dict
    value, ...), never raises, and never requires a caller to pre-validate.
    Narrowing the parameter type would misstate that contract and produce
    false type-checker errors at legitimate call sites (e.g. passing a
    ``feature_coverage_judge.CoverageVerdict`` result straight through).

    Never raises on malformed input (report layer). This covers every shape
    the strict helpers reject, not just a well-shaped dict with a wrong
    field type: a non-boolean ``coverage.exercised`` or ``predicate.passed``
    value, a non-dict ``coverage_result`` (string/int/list/...), a non-list
    ``predicate_results`` (string/dict/...), and a non-dict item inside an
    otherwise-list-shaped ``predicate_results`` (``None``, a string, an
    int, ...) all fail ``target_pass`` with an explicit reason naming the
    malformed field/value, instead of an exception or a truthy-string
    default pass.
    """
    predicates = predicate_results if predicate_results is not None else []
    if coverage_result is None:
        coverage = {
            "exercised": False,
            "reason": "Coverage result missing or unavailable",
        }
    elif not isinstance(coverage_result, dict) or "exercised" not in coverage_result:
        coverage = {
            "exercised": False,
            "reason": "Coverage result missing required 'exercised' key",
        }
        if isinstance(coverage_result, dict):
            coverage.update(coverage_result)
    else:
        coverage = dict(coverage_result)

    coverage_exercised, coverage_malformed_reason = _coverage_exercised_strict(
        coverage
    )
    if coverage_malformed_reason:
        coverage = dict(coverage)
        coverage["reason"] = coverage_malformed_reason

    predicates_normalized, predicates_pass = _normalize_predicates(predicates)
    target_pass = coverage_exercised and predicates_pass

    return {
        "target_pass": target_pass,
        "coverage": coverage,
        "predicates": predicates_normalized,
        "headline_gate": None,
    }


def write_verdict(verdict: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(yaml.safe_dump(verdict, sort_keys=False))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Aggregate a coverage-judge result (+ optional predicate results) "
        "into a target_scoped_verdict.yaml"
    )
    parser.add_argument("--coverage", required=True, help="Path to coverage result JSON")
    parser.add_argument("--predicates", default=None, help="Path to predicate results JSON list")
    parser.add_argument("--output", required=True, help="Path to write verdict YAML")
    args = parser.parse_args(argv)

    import json

    coverage_result = json.loads(Path(args.coverage).read_text())
    predicate_results = (
        json.loads(Path(args.predicates).read_text()) if args.predicates else None
    )
    verdict = aggregate_target_scoped(coverage_result, predicate_results)
    write_verdict(verdict, Path(args.output))
    print(f"target_pass={verdict['target_pass']} -> {args.output}")
    return 0 if verdict["target_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
