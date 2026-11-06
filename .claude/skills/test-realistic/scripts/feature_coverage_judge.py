"""Feature Coverage Judge for the generalized /test-realistic skill.

Post-run model-delegated judgment evaluating whether captured player-swarm
turns actually touched and exercised the target feature described by
feature_summary.

This module is THE load-bearing anti-false-green gate of the whole skill.
It must never degrade or fall back to token/keyword heuristics on failure --
that is a ZFC violation and defeats the entire purpose of this tool. This is
a generalized port of a source harness's own coverage judge (see
../PROVENANCE.md for lineage): the batching, global-index-labeling, and
bounded-retry-then-hard-fail algorithm is preserved verbatim. What changed
to make it project-agnostic:
  - the LLM callable is always injected (no project-specific default import)
  - turn elision (stripping oversized blobs like screenshot base64 before
    they blow the prompt budget) is a pluggable function, defaulting to a
    generic "elide any long string value" rule instead of a hardcoded
    project-specific rendered-field name
"""

from __future__ import annotations

import json
from typing import Any, Callable, TypedDict

# Prompt size budget (chars) for a single judge call's captured-turns batch.
# Batching (rather than a silent captured_turns[:N] slice) ensures every
# captured turn is actually judged, never just a fixed-size prefix.
_PROMPT_BATCH_BUDGET_CHARS = 60_000

# Generic elision threshold: any string value longer than this (e.g. a
# base64 screenshot, a raw HTML dump) is replaced with a size marker before
# being shown to the judge model, so it doesn't dominate the prompt budget
# without adding judgment-relevant signal. Projects with a more precise
# elision rule (e.g. "only elide known binary-blob fields") should pass
# their own elide_turn_fn.
_DEFAULT_ELIDE_STRING_THRESHOLD_CHARS = 2000


class CoverageJudgeUnavailableError(RuntimeError):
    """Raised when feature coverage judgment fails or returns invalid output.

    Callers (e.g. target_scoped_run.py) must treat this exception as a hard
    failure and convert it to a non-zero process exit. Callers must NEVER
    catch this error to fabricate a verdict or fall back to keyword
    heuristics -- doing so silently reintroduces the exact false-green gap
    this module exists to close.
    """


class CoverageVerdict(TypedDict):
    exercised: bool
    evidence_turn_indices: list[int]
    rationale: str


FEATURE_COVERAGE_JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "exercised": {"type": "boolean"},
        "evidence_turn_indices": {
            "type": "array",
            "items": {"type": "integer"},
        },
        "rationale": {"type": "string"},
    },
    "required": ["exercised", "evidence_turn_indices", "rationale"],
    "additionalProperties": False,
}

# (prompt, json_schema) -> parsed dict. Callers pass a real model-call
# adapter (see agy_adapter.make_llm_callable) or their own.
LlmCallable = Callable[[str, dict[str, Any]], dict[str, Any]]


def _default_elide_turn(turn: dict[str, Any]) -> dict[str, Any]:
    """Generic elision: replace any oversized string value with a size marker.

    Recurses into nested dicts (e.g. a project's own `rendered`/`parsed`
    sub-objects) but not into lists of dicts beyond one level, matching the
    shallow turn-record shapes this skill expects captures to use.
    """

    def _elide_value(value: Any) -> Any:
        if isinstance(value, str) and len(value) > _DEFAULT_ELIDE_STRING_THRESHOLD_CHARS:
            return f"<elided:{len(value)}chars>"
        if isinstance(value, dict):
            return {k: _elide_value(v) for k, v in value.items()}
        return value

    return {k: _elide_value(v) for k, v in turn.items()}


def _validate_and_normalize_verdict(data: Any) -> tuple[bool, list[int], str]:
    """Strictly validate one raw judge response dict.

    Raises ValueError on any malformed shape. Never coerces a non-bool
    ``exercised`` value in either direction, and treats an ``exercised: True``
    claim with no supporting evidence indices as malformed (a claim without
    evidence), not as a pass. ``exercised: False`` requires a non-empty
    rationale but evidence may legitimately be empty.
    """
    if not isinstance(data, dict):
        raise ValueError("Response JSON is not a dictionary")

    if (
        "exercised" not in data
        or "evidence_turn_indices" not in data
        or "rationale" not in data
    ):
        raise ValueError("Response missing required schema fields")

    exercised = data.get("exercised")
    if not isinstance(exercised, bool):
        raise ValueError(
            f"'exercised' must be a bool, got {type(exercised).__name__}: {exercised!r}"
        )

    evidence_indices = data.get("evidence_turn_indices")
    if not isinstance(evidence_indices, list) or not all(
        isinstance(i, int) and not isinstance(i, bool) for i in evidence_indices
    ):
        raise ValueError("evidence_turn_indices must be a list of ints")

    rationale = data.get("rationale")
    if not isinstance(rationale, str):
        raise ValueError("rationale must be a string")

    if exercised and not evidence_indices:
        raise ValueError(
            "exercised=True requires non-empty evidence_turn_indices "
            "(a claim without evidence is malformed)"
        )

    if not exercised and not rationale.strip():
        raise ValueError("exercised=False requires a non-empty rationale")

    return exercised, evidence_indices, rationale


def _call_judge_once(
    feature_summary: str,
    batch: list[tuple[int, dict]],
    total_turn_count: int,
    llm_callable: LlmCallable,
) -> tuple[bool, list[int], str]:
    """Run the bounded-retry judge call for one batch of (global_index, elided_turn) pairs.

    Every turn shown to the model is labeled with its own true GLOBAL
    capture index, and the model must echo that same global index back in
    evidence_turn_indices. Any response whose evidence indices are not a
    subset of THIS batch's own global indices is treated as malformed
    (never silently filtered), consuming the bounded retry -- this closes
    the ambiguity where a naive "0-based position within this batch"
    contract let a model return global indices that got silently dropped by
    a batch-local range filter, producing exercised=True with empty
    evidence.
    """
    valid_global_indices = {global_idx for global_idx, _ in batch}
    labeled_turns = [
        {"global_capture_index": global_idx, "turn": turn} for global_idx, turn in batch
    ]
    prompt = (
        f"Feature Summary:\n{feature_summary}\n\n"
        f"Captured Turns batch ({len(batch)} of {total_turn_count} "
        "total captured turns). Each entry below is labeled with its "
        "GLOBAL capture index (global_capture_index field) -- its index "
        "in the FULL run capture, not this batch's own list order:\n"
        f"{json.dumps(labeled_turns, indent=2)}\n\n"
        "Determine if the captured turns exercised the target feature. "
        "evidence_turn_indices MUST be the global_capture_index value(s) of "
        "each supporting turn shown above -- copy the labeled "
        "global_capture_index verbatim, never a list-order offset. "
        "Respond in JSON format with fields: exercised (bool), "
        "evidence_turn_indices (list of int), rationale (string)."
    )

    last_exc: Exception | None = None
    for _attempt in range(2):
        try:
            data = llm_callable(prompt, FEATURE_COVERAGE_JUDGE_SCHEMA)
            exercised, evidence_indices, rationale = _validate_and_normalize_verdict(
                data
            )
            if exercised:
                out_of_batch = [
                    i for i in evidence_indices if i not in valid_global_indices
                ]
                if out_of_batch:
                    raise ValueError(
                        "evidence_turn_indices contains indices outside "
                        f"this batch's own global capture indices "
                        f"{sorted(valid_global_indices)}: {out_of_batch} -- "
                        "the model must echo the labeled global_capture_index, "
                        "never a batch-local position or an index from a "
                        "different batch"
                    )
            return exercised, evidence_indices, rationale
        except Exception as exc:  # noqa: BLE001 -- intentionally broad, converted below
            last_exc = exc

    raise CoverageJudgeUnavailableError(
        f"Feature coverage judge failed after 2 attempts. Last error "
        f"({type(last_exc).__name__}): {last_exc!r}"
    ) from last_exc


def _batch_indexed_turns(
    indexed_turns: list[tuple[int, dict]],
    budget: int | None = None,
) -> list[list[tuple[int, dict]]]:
    """Split (global_index, elided_turn) pairs into size-bounded batches.

    Preserves original order across and within batches. A single oversized
    turn still gets its own batch rather than being dropped or truncated.
    """
    if budget is None:
        budget = _PROMPT_BATCH_BUDGET_CHARS
    batches: list[list[tuple[int, dict]]] = []
    current: list[tuple[int, dict]] = []
    current_size = 0
    for idx, turn in indexed_turns:
        turn_size = len(json.dumps(turn))
        if current and current_size + turn_size > budget:
            batches.append(current)
            current = []
            current_size = 0
        current.append((idx, turn))
        current_size += turn_size
    if current:
        batches.append(current)
    return batches


def judge_feature_exercised(
    feature_summary: str,
    captured_turns: list[dict[str, Any]],
    llm_callable: LlmCallable,
    elide_turn_fn: Callable[[dict[str, Any]], dict[str, Any]] = _default_elide_turn,
) -> CoverageVerdict:
    """Evaluate whether captured turns exercised the target feature.

    Every captured turn is judged -- turns are elided (oversized blobs
    replaced with a size marker) and batched to stay within a per-call
    prompt size budget, never silently windowed to a fixed prefix. Each
    batch is judged independently (under a bounded 2-attempt retry);
    ``exercised`` is OR-combined across batches. Every batch's rationale
    survives combination, labeled with that batch's own verdict, so a
    dissenting batch's rationale is never silently discarded just because
    another batch passed.

    Args:
        feature_summary: Summary of the target feature, derived at
            scenario-generation time by its OWN model call -- callers must
            never derive this from the same session that will later grade
            the run (anti-self-grading requirement carried over from the
            source design).
        captured_turns: List of turn record dictionaries from the real
            swarm dispatcher's capture (project-defined shape; any dict is
            accepted, elide_turn_fn controls what gets shown to the judge).
        llm_callable: REQUIRED (prompt, json_schema) -> dict callable making
            a real model call. There is no built-in default here -- callers
            must explicitly choose (see agy_adapter.make_llm_callable for
            the shipped default adapter). This module never silently picks
            a project-specific import.

    Returns:
        CoverageVerdict with exercised boolean, turn indices (indexing the
        caller's original captured_turns list), and rationale.

    Raises:
        CoverageJudgeUnavailableError: If LLM judgment fails after bounded retry.
    """
    if not captured_turns:
        return {
            "exercised": False,
            "evidence_turn_indices": [],
            "rationale": "No turns captured during run.",
        }

    indexed_turns = [
        (i, elide_turn_fn(turn)) for i, turn in enumerate(captured_turns)
    ]
    batches = _batch_indexed_turns(indexed_turns)
    total_turn_count = len(captured_turns)

    overall_exercised = False
    combined_evidence: list[int] = []
    labeled_rationales: list[str] = []

    for batch_number, batch in enumerate(batches, start=1):
        exercised, global_indices, rationale = _call_judge_once(
            feature_summary, batch, total_turn_count, llm_callable
        )
        verdict_label = "exercised" if exercised else "not exercised"
        labeled_rationales.append(f"[batch {batch_number}: {verdict_label}] {rationale}")
        if exercised:
            overall_exercised = True
            combined_evidence.extend(global_indices)

    if overall_exercised:
        deduped_evidence = sorted(set(combined_evidence))
        if not deduped_evidence:
            # Post-combination invariant, defense-in-depth: every
            # contributing batch's evidence is already validated non-empty
            # and in-batch by _call_judge_once, so this should be
            # unreachable through the public API -- but a combined
            # exercised=True claim must never silently return with no
            # evidence, even if a future refactor bypasses per-batch
            # validation.
            raise CoverageJudgeUnavailableError(
                "internal invariant violated: combined exercised=True verdict "
                "has empty evidence_turn_indices after batch validation -- "
                "refusing to return a claim without evidence"
            )
        return {
            "exercised": True,
            "evidence_turn_indices": deduped_evidence,
            "rationale": " | ".join(labeled_rationales),
        }

    return {
        "exercised": False,
        "evidence_turn_indices": [],
        "rationale": " | ".join(labeled_rationales),
    }
