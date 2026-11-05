"""Model-delegated scenario generation for the generalized /test-realistic skill.

Generalized port of a source harness's own scenario generator module (see
../PROVENANCE.md for lineage). The pipeline shape and
the model-vs-code judgment boundary are preserved verbatim (see the
who-does-what table in ../SKILL.md); what moved to config.ProjectConfig:
  - the renderer/feature-surface vocabulary (was RENDERED_FIELD_ALLOWLIST,
    imported from a project-specific renderer_contract.py)
  - the actor fixture + persona list used to build pool.yaml
  - pattern-scenario example files used as style reference for step authoring
  - the repo root used for gh/git context fetching and relative-izing paths
  - the optional doc-target dispatch (a project's own docs->invariants tool,
    if it has one)

Two model calls in normal generation, never a template fallback:
  1. classify_and_summarize -- target_type (pr/commit/prompt) + feature_summary
     + relevant_surfaces (constrained to config.feature_surface_vocabulary)
  2. author_scenario_steps -- 3-5 concrete {user_action, expected_render} beats
     + a predicate reuse/author_new/deferred decision

The --from-json path skips author_scenario_steps and makes only the
classification+summary call; any supplied feature_summary is discarded.

PR-shape / commit-SHA-shape detection, gh/git context fetching, and JSON
structural validation are CODE (mechanics, not judgment) -- this matches
upstream's own ZFC classification and is unchanged here.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from config import ProjectConfig

MAX_MODEL_ATTEMPTS = 2

# (prompt, json_schema) -> parsed dict. Same shape as
# feature_coverage_judge.LlmCallable -- one injectable seam for every
# model-delegated call in this module.
LlmCallable = Callable[[str, dict[str, Any]], dict[str, Any]]


class ScenarioGenerationError(RuntimeError):
    """Raised when a model call returns malformed/invalid output after the
    bounded retry, or when a gh/git context-fetch subprocess fails.

    Callers (main()) must treat this as a hard failure and convert it to a
    non-zero process exit. Never caught to fabricate a template fallback.
    """


# --- CODE: pure shape checks (ZFC-allowed mechanics, not judgment) ----------

# Strict, anchored, full-string PR-shape check. This is the ONLY thing that
# decides whether `gh pr view` is attempted -- it must never match a
# freeform English prompt like "Preview the banner in 3 modes".
_PR_TARGET_SHAPE_RE = re.compile(r"^(?:#?\d+|pr[\s#-]*\d+)$", re.IGNORECASE)

# Hex-shape SHA check (7-40 hex chars, full string).
_COMMIT_TARGET_SHAPE_RE = re.compile(r"^[0-9a-f]{7,40}$")

_PR_DIFF_SUMMARY_MAX_CHARS = 4000
_PR_FILES_LIST_MAX = 50


@dataclass
class TargetInfo:
    target_type: str  # "pr", "commit", "prompt" (doc targets dispatch elsewhere)
    raw_target: str
    title: str
    description: str
    feature_summary: str = ""
    relevant_surfaces: list[str] = field(default_factory=list)
    steps: list[dict] = field(default_factory=list)
    predicate_decision: dict = field(default_factory=dict)

    @property
    def slug(self) -> str:
        s = self.raw_target.lower()
        s = re.sub(r"^[#/]+", "", s)
        s = re.sub(r"\W+", "_", s).strip("_")
        if not s:
            s = "target"
        return s[:40]


def _summarize_pr_diff(raw_files: object) -> tuple[str | None, str | None]:
    if not isinstance(raw_files, list) or not raw_files:
        return None, None
    lines = []
    for f in raw_files[:_PR_FILES_LIST_MAX]:
        if not isinstance(f, dict):
            continue
        path = f.get("path")
        if not isinstance(path, str) or not path:
            continue
        additions = f.get("additions", 0)
        deletions = f.get("deletions", 0)
        lines.append(f"{path} (+{additions}/-{deletions})")
    summary = "\n".join(lines)[:_PR_DIFF_SUMMARY_MAX_CHARS]
    note = None
    if len(raw_files) > _PR_FILES_LIST_MAX:
        note = f"(showing first {_PR_FILES_LIST_MAX} of {len(raw_files)} files)"
    return summary or None, note


def _format_pr_context_extras(context: dict) -> str:
    parts = []
    files = context.get("files")
    if files:
        parts.append(f"Changed files ({len(files)}): {', '.join(files[:_PR_FILES_LIST_MAX])}")
    diff_summary = context.get("diff_summary")
    if diff_summary:
        parts.append(f"Diff summary:\n{diff_summary}")
    diff_note = context.get("diff_note")
    if diff_note:
        parts.append(diff_note)
    return ("\n".join(parts) + "\n") if parts else ""


def fetch_raw_pr_context(pr_num: str) -> dict:
    """Fetch raw PR context using gh. Fails loud -- no local-diff fallback."""
    try:
        res = subprocess.run(
            ["gh", "pr", "view", pr_num, "--json", "title,body,headRefName,files"],
            capture_output=True,
            text=True,
            check=True,
        )
        data = json.loads(res.stdout)
    except (subprocess.CalledProcessError, OSError, json.JSONDecodeError) as exc:
        raise ScenarioGenerationError(f"gh pr view failed for PR #{pr_num}: {exc}") from exc
    raw_files = data.get("files", [])
    files = (
        [
            f["path"]
            for f in raw_files
            if isinstance(f, dict) and isinstance(f.get("path"), str) and f["path"]
        ]
        if isinstance(raw_files, list)
        else []
    )
    diff_summary, diff_note = _summarize_pr_diff(raw_files)
    return {
        "title": data.get("title", f"PR #{pr_num}"),
        "body": data.get("body", ""),
        "files": files,
        "head_ref": data.get("headRefName", ""),
        "diff_summary": diff_summary,
        "diff_note": diff_note,
    }


def fetch_raw_commit_context(commit_sha: str) -> dict:
    """Fetch raw commit context using git show. Fails loud."""
    try:
        res = subprocess.run(
            ["git", "show", "--stat", "--oneline", commit_sha],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, OSError) as exc:
        raise ScenarioGenerationError(f"git show failed for commit {commit_sha}: {exc}") from exc
    lines = res.stdout.splitlines()
    first_line = lines[0] if lines else commit_sha
    return {"title": first_line, "body": res.stdout[:500]}


def _gather_raw_context(target_s: str) -> dict:
    """Shape-based fetch selection (mechanics, never final target_type judgment)."""
    pr_shaped = bool(_PR_TARGET_SHAPE_RE.match(target_s))
    commit_shaped = bool(_COMMIT_TARGET_SHAPE_RE.match(target_s.lower()))

    if pr_shaped:
        pr_match = re.search(r"\d+", target_s)
        pr_num = pr_match.group(0) if pr_match else target_s
        try:
            ctx = fetch_raw_pr_context(pr_num)
            return {**ctx, "candidate_type": "pr", "candidate_id": pr_num}
        except ScenarioGenerationError as pr_exc:
            if not commit_shaped:
                raise
            try:
                commit_ctx = fetch_raw_commit_context(target_s)
                return {**commit_ctx, "candidate_type": "commit", "candidate_id": target_s}
            except ScenarioGenerationError as commit_exc:
                raise ScenarioGenerationError(
                    f"target {target_s!r} matches both PR and commit shape; "
                    f"both ordered fetch attempts failed -- gh pr view: "
                    f"{pr_exc}; git show: {commit_exc}"
                ) from commit_exc

    if commit_shaped:
        ctx = fetch_raw_commit_context(target_s)
        return {**ctx, "candidate_type": "commit", "candidate_id": target_s}

    return {
        "title": target_s[:60],
        "body": target_s,
        "candidate_type": "prompt",
        "candidate_id": target_s,
    }


def _derive_raw_target(target_type: str, target_s: str, context: dict) -> str:
    candidate_id = context.get("candidate_id", target_s)
    if target_type == "pr":
        return f"pr_{candidate_id}"
    if target_type == "commit":
        return f"commit_{candidate_id[:8]}"
    return target_s


# --- CODE: optional doc-target shape check + dispatch (project-supplied) ---


def is_doc_target(target_s: str, config: ProjectConfig) -> str | None:
    """Return the matched doc-target id if target_s matches one of
    config.doc_target_patterns, else None. Absent config -- a project with
    no docs-to-invariants equivalent -- this always returns None, so every
    target flows through the model-delegated path below. Pure structural
    regex match, never content inspection or judgment.
    """
    if not config.doc_target_patterns:
        return None
    s = target_s.strip()
    for pattern in config.doc_target_patterns:
        m = re.match(pattern, s)
        if m:
            return m.group(0)
    return None


def dispatch_doc_target(doc_id: str, config: ProjectConfig) -> int:
    """Dispatch a doc-shaped target to the project's own doc_dispatch_command.

    Thin, unmodified dispatch -- this module never re-implements a project's
    doc-to-invariants generation logic. Raises ScenarioGenerationError if a
    doc-shaped target was matched but no doc_dispatch_command is configured
    (a config bug, not a silent no-op).
    """
    if not config.doc_dispatch_command:
        raise ScenarioGenerationError(
            f"target {doc_id!r} matched doc_target_patterns but no "
            "doc_dispatch_command is configured"
        )
    cmd = [part.format(doc_id=doc_id) for part in config.doc_dispatch_command]
    result = subprocess.run(cmd, cwd=config.repo_root)
    return result.returncode


# --- MODEL: schema construction + the two injectable model calls ------------


def build_classify_schema(feature_surface_vocabulary: tuple[str, ...]) -> dict:
    return {
        "type": "object",
        "properties": {
            "target_type": {"type": "string", "enum": ["pr", "commit", "prompt"]},
            "feature_summary": {"type": "string"},
            "relevant_surfaces": {
                "type": "array",
                "items": {"type": "string", "enum": sorted(feature_surface_vocabulary)},
            },
        },
        "required": ["target_type", "feature_summary", "relevant_surfaces"],
        "additionalProperties": False,
    }


AUTHOR_STEPS_SCHEMA = {
    "type": "object",
    "properties": {
        "steps": {
            "type": "array",
            "minItems": 3,
            "maxItems": 5,
            "items": {
                "type": "object",
                "properties": {
                    "user_action": {"type": "string"},
                    "expected_render": {"type": "object"},
                },
                "required": ["user_action", "expected_render"],
                "additionalProperties": False,
            },
        },
        "predicate_decision": {
            "type": "object",
            "properties": {
                "decision": {"type": "string", "enum": ["reuse", "author_new", "deferred"]},
                "predicate_name": {"type": ["string", "null"]},
                "rationale": {"type": "string"},
            },
            "required": ["decision", "rationale"],
            "additionalProperties": False,
        },
    },
    "required": ["steps", "predicate_decision"],
    "additionalProperties": False,
}


def _load_pattern_scenarios(config: ProjectConfig) -> str:
    """Load a project's own example scenario files as style reference.

    config carries no built-in pattern-scenario paths -- a project supplies
    them via its own raw TOML under [pattern_scenarios] if it wants
    style-grounded step authoring; absent that, this returns a neutral
    placeholder and the model authors steps grounded only in the fetched
    context, matching upstream's own graceful-empty behavior.
    """
    pattern_files = config.raw.get("pattern_scenario_files", [])
    chunks = []
    for filename in pattern_files:
        path = config.repo_root / filename
        if path.exists():
            chunks.append(f"# {filename}\n{path.read_text()[:1500]}")
    return "\n\n".join(chunks) if chunks else "(no pattern scenarios configured)"


def classify_and_summarize(
    context: dict, target_s: str, config: ProjectConfig, llm_callable: LlmCallable
) -> dict:
    """MODEL call #1: classify target_type + derive feature_summary.

    relevant_surfaces is constrained to config.feature_surface_vocabulary --
    the project's own equivalent of a renderer-field allowlist, never a
    hardcoded import.
    """
    prompt = (
        "You are classifying a /test-realistic target and deriving a feature "
        "summary for later anti-false-green coverage judgment.\n\n"
        f"Target input: {target_s}\n"
        f"Context title: {context.get('title', '')}\n"
        f"Context body:\n{context.get('body', '')[:2000]}\n"
        f"{_format_pr_context_extras(context)}"
        "Classify target_type as one of pr/commit/prompt, write a concise "
        "feature_summary describing what user-visible feature this target "
        "exercises, and list relevant_surfaces drawn ONLY from this allowed "
        f"vocabulary: {sorted(config.feature_surface_vocabulary)}.\n"
        "Respond as JSON matching the required schema exactly."
    )
    schema = build_classify_schema(config.feature_surface_vocabulary)
    return llm_callable(prompt, schema)


def author_scenario_steps(
    context: dict, feature_summary: str, config: ProjectConfig, llm_callable: LlmCallable
) -> dict:
    """MODEL call #2: author 3-5 concrete steps + predicate reuse-vs-author decision."""
    pattern_text = _load_pattern_scenarios(config)
    prompt = (
        "You are authoring 3-5 concrete scenario steps for a /test-realistic "
        "player-swarm run.\n\n"
        f"Feature summary: {feature_summary}\n"
        f"Context title: {context.get('title', '')}\n"
        f"Context body:\n{context.get('body', '')[:2000]}\n"
        f"{_format_pr_context_extras(context)}"
        "Pattern scenarios for style reference only (ground your steps in the "
        "feature summary above, do not copy verbatim):\n"
        f"{pattern_text}\n\n"
        "Author 3-5 steps, each with a concrete user_action and an "
        "expected_render dict grounded in the feature. Also decide whether an "
        'existing invariant predicate can verify correctness ("reuse"), a new '
        'one should be authored ("author_new"), or this is deferred to a '
        'human follow-up ("deferred") -- record that as predicate_decision.\n'
        "Respond as JSON matching the required schema exactly."
    )
    return llm_callable(prompt, AUTHOR_STEPS_SCHEMA)


# --- CODE: structural validation (pure mechanics) ----------------------------


def _is_primitive_or_dict(value: object) -> bool:
    if isinstance(value, dict):
        return all(isinstance(k, str) and _is_primitive_or_dict(v) for k, v in value.items())
    if isinstance(value, list):
        return all(_is_primitive_or_dict(v) for v in value)
    return isinstance(value, (str, int, float, bool)) or value is None


def validate_scenario_steps(steps: list[dict]) -> None:
    if not isinstance(steps, list) or len(steps) == 0:
        raise ValueError("Scenario must contain a non-empty list of steps.")
    for idx, step in enumerate(steps):
        if "user_action" not in step or "expected_render" not in step:
            raise ValueError(f"Step {idx} missing 'user_action' or 'expected_render'")
        expected_render = step["expected_render"]
        if not isinstance(expected_render, dict) or not expected_render:
            raise ValueError(f"Step {idx} 'expected_render' must be a non-empty dict")
        if not _is_primitive_or_dict(expected_render):
            raise ValueError(
                f"Step {idx} 'expected_render' values must be primitives or nested dicts"
            )


def _validate_classification(result: dict, config: ProjectConfig) -> None:
    if not isinstance(result, dict):
        raise ValueError("classification result must be a dict")
    for key in ("target_type", "feature_summary", "relevant_surfaces"):
        if key not in result:
            raise ValueError(f"classification result missing '{key}'")
    if result["target_type"] not in ("pr", "commit", "prompt"):
        raise ValueError(f"invalid target_type: {result['target_type']!r}")
    for surface in result.get("relevant_surfaces", []):
        if surface not in config.feature_surface_vocabulary:
            raise ValueError(f"relevant_surfaces contains non-allowlisted field: {surface!r}")


def _validate_authored_steps(result: dict) -> None:
    if not isinstance(result, dict):
        raise ValueError("authored steps result must be a dict")
    if "steps" not in result:
        raise ValueError("authored steps result missing 'steps'")
    validate_scenario_steps(result["steps"])
    if not (3 <= len(result["steps"]) <= 5):
        raise ValueError(f"expected 3-5 steps, got {len(result['steps'])}")


def _invoke_with_retry(call_fn, validate_fn) -> dict:
    """One bounded retry on malformed output. Never falls back to a template."""
    last_exc: Exception | None = None
    for _attempt in range(MAX_MODEL_ATTEMPTS):
        try:
            result = call_fn()
            validate_fn(result)
            return result
        except (ScenarioGenerationError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            last_exc = exc
            continue
    raise ScenarioGenerationError(
        f"Model call failed validation after {MAX_MODEL_ATTEMPTS} attempts: {last_exc}"
    )


# --- Orchestration: context -> model calls -> validation --------------------


def resolve_target_info(
    target_input: str,
    config: ProjectConfig,
    llm_callable: LlmCallable,
    from_json_path: Path | None = None,
) -> TargetInfo:
    """Resolve target info via model-delegated classification + step authoring.

    feature_summary is ALWAYS derived by its own fresh model call, even when
    --from-json supplies pre-authored steps -- the interactive short-circuit
    is explicitly forbidden from supplying feature_summary itself, closing
    the "model grades its own paraphrase" hole the coverage judge depends on
    staying closed.
    """
    target_s = target_input.strip()

    if from_json_path is not None:
        if not from_json_path.exists():
            raise ScenarioGenerationError(f"--from-json payload not found: {from_json_path}")
        try:
            payload = json.loads(from_json_path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise ScenarioGenerationError(
                f"--from-json payload unreadable: {from_json_path}: {exc}"
            ) from exc

        steps = payload.get("steps", [])
        try:
            _validate_authored_steps({"steps": steps})
        except (ValueError, TypeError) as exc:
            raise ScenarioGenerationError(
                f"--from-json payload 'steps' failed validation: {exc}"
            ) from exc

        context = _gather_raw_context(target_s)
        classification = _invoke_with_retry(
            lambda: classify_and_summarize(context, target_s, config, llm_callable),
            lambda r: _validate_classification(r, config),
        )

        return TargetInfo(
            target_type=payload.get("target_type", classification["target_type"]),
            raw_target=payload.get("raw_target", target_s),
            title=payload.get("title", target_s),
            description=payload.get("description", target_s),
            feature_summary=classification["feature_summary"],
            relevant_surfaces=classification.get("relevant_surfaces", []),
            steps=steps,
            predicate_decision=payload.get("predicate_decision", {}),
        )

    context = _gather_raw_context(target_s)
    classification = _invoke_with_retry(
        lambda: classify_and_summarize(context, target_s, config, llm_callable),
        lambda r: _validate_classification(r, config),
    )
    feature_summary = classification["feature_summary"]

    authored = _invoke_with_retry(
        lambda: author_scenario_steps(context, feature_summary, config, llm_callable),
        _validate_authored_steps,
    )
    steps = authored["steps"]
    validate_scenario_steps(steps)

    target_type = classification["target_type"]
    return TargetInfo(
        target_type=target_type,
        raw_target=_derive_raw_target(target_type, target_s, context),
        title=context.get("title", target_s[:60]),
        description=context.get("body", target_s)[:300],
        feature_summary=feature_summary,
        relevant_surfaces=classification.get("relevant_surfaces", []),
        steps=steps,
        predicate_decision=authored.get("predicate_decision", {}),
    )


# --- CODE: file emission (deterministic templating, zero judgment) ----------


def _escape_for_generated_docstring(value: str) -> str:
    r"""Escape a string for safe interpolation into a generated module's docstring.

    A literal run of three double-quote characters (or a backslash right
    before one) in model/user-derived text must never be able to
    prematurely close the generated file's module docstring and break its
    syntax. repr() alone is NOT sufficient -- it doesn't neutralize an
    unescaped triple-double-quote sequence embedded inside an otherwise
    plain string when interpolated raw into a triple-quoted docstring -- so
    this collapses any such run down to an escaped form.
    """
    return value.replace('"""', '\\"\\"\\"')


def generate_scenario_files(
    target_info: TargetInfo, config: ProjectConfig, output_dir: Path
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    slug = target_info.slug
    scenario_filename = f"generated_{slug}.py"
    scenario_path = output_dir / scenario_filename

    scenario_name = f"generated_{slug}"
    scenario_key = f"{scenario_name.upper()}_SCENARIO"

    safe_raw_target = _escape_for_generated_docstring(str(target_info.raw_target))
    safe_target_type = _escape_for_generated_docstring(str(target_info.target_type))
    safe_title = _escape_for_generated_docstring(str(target_info.title))
    safe_feature_summary = _escape_for_generated_docstring(str(target_info.feature_summary))
    scenario_code = f'''"""Generated Scenario for /test-realistic target: {safe_raw_target}

Target Type: {safe_target_type}
Title: {safe_title}
Feature Summary: {safe_feature_summary}
"""
from __future__ import annotations
from typing import TypedDict


class ScenarioStep(TypedDict):
    user_action: str
    expected_render: dict


{scenario_key}: list[ScenarioStep] = {target_info.steps!r}

SCENARIO_NAME = "{scenario_name}"
FEATURE_SUMMARY = {target_info.feature_summary!r}
RELEVANT_SURFACES = {target_info.relevant_surfaces!r}
PREDICATE_DECISION = {target_info.predicate_decision!r}
'''
    scenario_path.write_text(scenario_code)

    pool_path = output_dir / f"generated_pool_{slug}.yaml"
    personas = list(config.personas)
    actor_fixtures = list(config.actor_fixtures)

    agents = []
    if actor_fixtures:
        # Actor fixtures and personas are paired only where both are present.
        # The generalized contract has no policy for synthesizing an actor or
        # persona when the configured lists differ, so the existing zip
        # shortest-sequence behavior is intentionally retained. The emitted
        # pool is authoritative for expected-agent completeness checks.
        for actor, persona in zip(actor_fixtures, personas):
            agents.append({"actor": actor, "scenario": str(scenario_path), "persona": persona})
    else:
        # No actor fixtures configured -- an app without a "character"
        # concept (e.g. no player-selectable roster) still gets one agent
        # per persona, scenario-only.
        for persona in personas:
            agents.append({"scenario": str(scenario_path), "persona": persona})

    import yaml

    pool_data = {"agents": agents}
    pool_path.write_text(yaml.safe_dump(pool_data, sort_keys=False))

    return scenario_path, pool_path


def main(argv: list[str] | None = None) -> int:
    import argparse

    from agy_adapter import make_llm_callable
    from config import find_config_path, load_config

    parser = argparse.ArgumentParser(
        description="Generate scenario + pool.yaml from PR, commit, doc, or freeform prompt"
    )
    parser.add_argument("target", nargs="?", default="general_verification")
    parser.add_argument("--from-json", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=None, help="Path to .test-realistic.toml")
    args = parser.parse_args(argv)

    config_path = args.config or find_config_path(Path.cwd())
    config = load_config(config_path)
    llm_callable = make_llm_callable(model=config.agy_model, timeout_seconds=config.agy_timeout_seconds)

    doc_id = is_doc_target(args.target, config)
    if doc_id:
        if args.from_json:
            print(
                f"ERROR: --from-json is not supported for doc-shaped targets "
                f"({args.target!r} -> {doc_id!r}) -- doc-shaped targets dispatch "
                "unchanged to the project's own doc_dispatch_command.",
                file=sys.stderr,
            )
            return 1
        return dispatch_doc_target(doc_id, config)

    try:
        target_info = resolve_target_info(
            args.target, config, llm_callable, from_json_path=args.from_json
        )
    except ScenarioGenerationError as exc:
        print(f"ERROR: scenario generation failed: {exc}", file=sys.stderr)
        return 1

    scenario_path, pool_path = generate_scenario_files(target_info, config, args.output_dir)

    print(f"Generated scenario for target '{args.target}' ({target_info.target_type}):")
    print(f"  Title: {target_info.title}")
    print(f"  Feature Summary: {target_info.feature_summary}")
    print(f"  Predicate Decision: {target_info.predicate_decision}")
    print(f"  Scenario file: {scenario_path}")
    print(f"  Pool YAML file: {pool_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
