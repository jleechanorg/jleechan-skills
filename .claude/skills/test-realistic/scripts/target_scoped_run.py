"""Target-scoped orchestrator for the generalized /test-realistic skill.

Generalized port of a source harness's own orchestrator module (see
../PROVENANCE.md for lineage). Dispatches a project's OWN real player-swarm
command (config.dispatch_command
-- never a hardcoded runner.py import or subprocess target), loads the
generated scenario's independently-model-derived FEATURE_SUMMARY, judges
whether the real captured swarm turns exercised it
(feature_coverage_judge.judge_feature_exercised), and reports one
target_scoped_verdict.json combining the dispatcher's own exit status with
the coverage verdict. `target_pass` is a feature-coverage result only;
it is never an assertion that the application behaved correctly. A
project dispatcher that detects an invariant violation must exit non-zero,
which remains fatal even when the coverage model says the feature was
exercised.

What generalized relative to upstream:
  - the swarm dispatcher is invoked via config.dispatch_command (a templated
    argv), not a hardcoded `python -m ...agent_pool.runner` subprocess. This
    module defines the CAPTURE CONTRACT a dispatcher must satisfy (turn
    records collectible via config.capture_glob under --output-root) but
    never vendors or reimplements any project's actual browser/agent
    plumbing.
  - the runner-envelope excuse logic (the source harness's `--allow-runner-
    envelope-fail`, which is hardwired to its own domain-specific
    HEADLINE_INVARIANTS semantics) is replaced by an OPTIONAL config.runner_excuse_predicate
    hook: a "module:function" string resolving to a
    (dispatch_returncode, output_root) -> (applied: bool, reason: str)
    callable. Absent that config key, a non-zero dispatch exit is ALWAYS
    fatal -- this is a deliberate simplification, not a silent weakening of
    upstream's specific excuse math (which this module does not attempt to
    replicate for an arbitrary project's own domain invariants).

What is unchanged (verbatim algorithm, just re-hosted):
  - pre-dispatch refusal to run over a reused --output-root that already
    has capture/verdict artifacts in it (never grade a stale run's leftovers)
  - capture collection + turn loading, coverage judge invocation with its
    hard-fail-never-fabricate contract, and the target_scoped_verdict.json
    artifact shape.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import cast

import yaml

from aggregate import aggregate_target_scoped
from feature_coverage_judge import (
    CoverageJudgeUnavailableError,
    CoverageVerdict,
    judge_feature_exercised,
)
from config import ProjectConfig, find_config_path, load_config

RunnerInvoker = Callable[..., "subprocess.CompletedProcess[str]"]
JudgeFn = Callable[..., CoverageVerdict]
ExcuseFn = Callable[[int, Path], tuple[bool, str]]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python target_scoped_run.py",
        description=(
            "Dispatch a project's real player-swarm command, judge whether the "
            "real captured turns exercised the generated scenario's "
            "FEATURE_SUMMARY, and write one target_scoped_verdict.json report."
        ),
    )
    parser.add_argument("--pool", required=True, help="Path to generated pool.yaml")
    parser.add_argument(
        "--scenario",
        required=True,
        help="Path to the generated scenario .py file (source of FEATURE_SUMMARY)",
    )
    parser.add_argument("--mode", default="headless", help="Execution mode passed to dispatch_command")
    parser.add_argument("--base-url", default=None, help="Overrides config.base_url for this run")
    parser.add_argument("--turns", type=int, default=None, help="Overrides config.turns_default")
    parser.add_argument("--output-root", default=None, help="Root dir for captures + this artifact")
    parser.add_argument("--config", type=Path, default=None, help="Path to .test-realistic.toml")
    parser.add_argument(
        "--allow-dispatch-excuse",
        action="store_true",
        help="Consult config.runner_excuse_predicate to potentially excuse a non-zero "
        "dispatch exit. Without this flag, a non-zero dispatch exit is always fatal "
        "regardless of config.",
    )
    return parser


def load_scenario_feature_summary(scenario_path: Path) -> tuple[str, list[str]]:
    """Load FEATURE_SUMMARY (and RELEVANT_SURFACES, if present) from a generated scenario file."""
    spec = importlib.util.spec_from_file_location("target_scoped_run_scenario", scenario_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load scenario: {scenario_path}")
    scenario_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scenario_mod)

    feature_summary = getattr(scenario_mod, "FEATURE_SUMMARY", None)
    if not isinstance(feature_summary, str) or not feature_summary.strip():
        raise RuntimeError(f"scenario has no non-empty FEATURE_SUMMARY: {scenario_path}")
    relevant_surfaces = getattr(scenario_mod, "RELEVANT_SURFACES", [])
    if not isinstance(relevant_surfaces, list):
        relevant_surfaces = []
    return feature_summary, relevant_surfaces


def build_dispatch_command(
    config: ProjectConfig,
    *,
    pool_path: Path,
    scenario_path: Path,
    output_root: Path,
    mode: str,
    base_url: str,
    turns: int,
) -> list[str]:
    """Render config.dispatch_command's template against this run's real values.

    Template placeholders: {pool} {scenario} {output_root} {mode} {base_url}
    {turns} {backend_url} {repo_root}. A project's dispatch script receives
    these as plain argv -- it owns everything about how it drives a real
    browser + real LLM agent(s) and where within output_root it writes
    agent-*/... captures (config.capture_glob controls how they're found
    afterward).
    """
    substitutions = {
        "pool": str(pool_path),
        "scenario": str(scenario_path),
        "output_root": str(output_root),
        "mode": mode,
        "base_url": base_url,
        "turns": str(turns),
        "backend_url": config.backend_url or "",
        "repo_root": str(config.repo_root),
    }
    return [part.format(**substitutions) for part in config.dispatch_command]


def collect_capture_paths(output_root: Path, capture_glob: str) -> list[Path]:
    return sorted(output_root.glob(capture_glob))


_PRE_DISPATCH_ARTIFACT_NAMES = ("target_scoped_verdict.json",)


def collect_pre_existing_artifacts(output_root: Path, capture_glob: str) -> list[Path]:
    """Refuse to reuse an --output-root that already has captures/verdicts in it.

    Without this, a crashed/degenerate run this time could silently ride on
    stale captures (or an excuse decision could be made against a stale
    verdict) left behind by an earlier run under the same output_root.
    """
    artifacts: set[Path] = set(output_root.glob(capture_glob))
    for name in _PRE_DISPATCH_ARTIFACT_NAMES:
        candidate = output_root / name
        if candidate.exists():
            artifacts.add(candidate)
    return sorted(artifacts)


def load_capture_turns(capture_path: Path) -> list[dict]:
    """Parse one capture.jsonl file, failing loud with file:line on malformed JSON."""
    turns: list[dict] = []
    for line_no, line in enumerate(capture_path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"malformed capture line in {capture_path}:{line_no}: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ValueError(
                f"capture line in {capture_path}:{line_no} is not a JSON object "
                f"(got {type(parsed).__name__})"
            )
        turns.append(parsed)
    return turns


def _load_pool_agent_count(pool_path: Path) -> int:
    raw = yaml.safe_load(pool_path.read_text())
    if not isinstance(raw, dict):
        raise ValueError(f"pool file is not a mapping: {pool_path}")
    agents = raw.get("agents")
    if not isinstance(agents, list):
        raise ValueError(f"pool file has no 'agents' list: {pool_path}")
    return len(agents)


def _resolve_excuse_fn(runner_excuse_predicate: str | None) -> ExcuseFn | None:
    """Resolve config.runner_excuse_predicate ("module:function") to a callable.

    Raises RuntimeError on an unresolvable reference -- a configured but
    broken excuse hook must fail loud, never be silently skipped (which
    would make --allow-dispatch-excuse a no-op the operator can't detect).
    """
    if not runner_excuse_predicate:
        return None
    module_name, _, func_name = runner_excuse_predicate.partition(":")
    if not module_name or not func_name:
        raise RuntimeError(
            f"runner_excuse_predicate must be 'module:function', got {runner_excuse_predicate!r}"
        )
    module = importlib.import_module(module_name)
    fn = getattr(module, func_name, None)
    if fn is None or not callable(fn):
        raise RuntimeError(f"{runner_excuse_predicate!r} did not resolve to a callable")
    # A dynamically imported callable's actual signature can't be verified
    # statically -- this cast documents that the (returncode, output_root)
    # -> (bool, str) contract is enforced at RUNTIME by how
    # _dispatch_excuse_decision calls it (and by config.py's own docstring
    # requirement on runner_excuse_predicate), not by the type checker.
    return cast(ExcuseFn, fn)


def _dispatch_excuse_decision(
    dispatch_returncode: int,
    allow_dispatch_excuse: bool,
    excuse_fn: ExcuseFn | None,
    output_root: Path,
) -> dict:
    if dispatch_returncode == 0:
        return {"applied": False, "reason": "dispatch exited 0, no excuse needed"}
    if not allow_dispatch_excuse:
        return {"applied": False, "reason": "--allow-dispatch-excuse not set"}
    if excuse_fn is None:
        return {"applied": False, "reason": "no runner_excuse_predicate configured"}
    try:
        result = excuse_fn(dispatch_returncode, output_root)
    except Exception as exc:  # noqa: BLE001 -- a broken excuse hook must never silently excuse
        return {"applied": False, "reason": f"runner_excuse_predicate raised: {exc!r}"}
    if (
        not isinstance(result, tuple)
        or len(result) != 2
        or type(result[0]) is not bool
        or not isinstance(result[1], str)
    ):
        return {
            "applied": False,
            "reason": "runner_excuse_predicate returned an invalid result; "
            "expected (bool, str)",
        }
    applied, reason = result
    return {"applied": applied, "reason": reason}


def main(
    argv: list[str] | None = None,
    *,
    subprocess_runner: RunnerInvoker | None = None,
    judge_fn: JudgeFn | None = None,
    llm_callable=None,
) -> int:
    subprocess_runner = subprocess_runner or subprocess.run
    args = _build_parser().parse_args(argv)

    config_path = args.config or find_config_path(Path.cwd())
    config = load_config(config_path)

    judge_fn_to_use: JudgeFn
    if judge_fn is not None:
        judge_fn_to_use = judge_fn
    else:
        if llm_callable is None:
            from agy_adapter import make_llm_callable

            llm_callable = make_llm_callable(
                model=config.agy_model, timeout_seconds=config.agy_timeout_seconds
            )
        bound_llm_callable = llm_callable

        def _default_judge_fn(feature_summary: str, all_turns: list[dict]) -> CoverageVerdict:
            return judge_feature_exercised(feature_summary, all_turns, bound_llm_callable)

        judge_fn_to_use = _default_judge_fn

    pool_path = Path(args.pool)
    if not pool_path.exists():
        print(f"ERROR: pool file not found: {pool_path}", file=sys.stderr, flush=True)
        return 1

    try:
        expected_agents = _load_pool_agent_count(pool_path)
    except Exception as exc:  # noqa: BLE001 -- fail loud with the real cause
        print(f"ERROR: could not load pool {pool_path}: {exc}", file=sys.stderr, flush=True)
        return 1

    scenario_path = Path(args.scenario)
    try:
        feature_summary, relevant_surfaces = load_scenario_feature_summary(scenario_path)
    except Exception as exc:  # noqa: BLE001 -- fail loud with the real cause
        print(f"ERROR: could not load scenario {scenario_path}: {exc}", file=sys.stderr, flush=True)
        return 1

    output_root = Path(args.output_root) if args.output_root else Path(
        tempfile.mkdtemp(prefix="test-realistic-run-")
    )
    output_root.mkdir(parents=True, exist_ok=True)

    pre_existing = collect_pre_existing_artifacts(output_root, config.capture_glob)
    if pre_existing:
        listed = "\n".join(f"  {p}" for p in pre_existing)
        print(
            "ERROR: refusing to run over pre-existing artifacts under "
            f"{output_root} -- always use a FRESH --output-root:\n{listed}",
            file=sys.stderr,
            flush=True,
        )
        return 1

    base_url = args.base_url or config.base_url
    turns = args.turns or config.turns_default

    cmd = build_dispatch_command(
        config,
        pool_path=pool_path,
        scenario_path=scenario_path,
        output_root=output_root,
        mode=args.mode,
        base_url=base_url,
        turns=turns,
    )
    proc = subprocess_runner(cmd, check=False, cwd=str(config.repo_root))
    dispatch_returncode = proc.returncode

    capture_paths = collect_capture_paths(output_root, config.capture_glob)
    if not capture_paths:
        print(
            f"ERROR: no captures found under {output_root} matching "
            f"{config.capture_glob!r} -- cannot judge feature coverage "
            f"(dispatch subprocess exit code: {dispatch_returncode})",
            file=sys.stderr,
            flush=True,
        )
        return 1
    if len(capture_paths) != expected_agents:
        print(
            f"ERROR: incomplete actor pool captures under {output_root}: "
            f"expected {expected_agents} capture file(s) for the requested "
            f"pool, found {len(capture_paths)} matching {config.capture_glob!r}; "
            "refusing to invoke the coverage judge",
            file=sys.stderr,
            flush=True,
        )
        return 1

    capture_records: list[dict] = []
    all_turns: list[dict] = []
    try:
        for capture_path in capture_paths:
            turns_loaded = load_capture_turns(capture_path)
            if not any(turns_loaded):
                print(
                    f"ERROR: capture {capture_path} contains no non-empty JSON "
                    "object; refusing to invoke the coverage judge",
                    file=sys.stderr,
                    flush=True,
                )
                return 1
            capture_records.append({"path": str(capture_path), "turn_count": len(turns_loaded)})
            all_turns.extend(turns_loaded)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        return 1

    try:
        coverage_result = judge_fn_to_use(feature_summary, all_turns)
    except CoverageJudgeUnavailableError as exc:
        # NEVER caught to fabricate a verdict or fall back to a heuristic --
        # this is a hard, loud, non-zero process exit.
        print(f"ERROR: feature coverage judge unavailable -- {exc}", file=sys.stderr, flush=True)
        return 1

    verdict = aggregate_target_scoped(coverage_result, [])

    excuse_fn = _resolve_excuse_fn(config.runner_excuse_predicate)
    dispatch_excused = _dispatch_excuse_decision(
        dispatch_returncode, args.allow_dispatch_excuse, excuse_fn, output_root
    )

    artifact = {
        "project_name": config.project_name,
        "target_scoped_verdict": verdict,
        "feature_summary": feature_summary,
        "relevant_surfaces": relevant_surfaces,
        "dispatch": {
            "command": cmd,
            "returncode": dispatch_returncode,
        },
        "dispatch_excused": dispatch_excused,
        "expected_agents": expected_agents,
        "captures": capture_records,
    }
    artifact_path = output_root / "target_scoped_verdict.json"
    artifact_path.write_text(json.dumps(artifact, indent=2) + "\n")
    print(json.dumps(artifact, indent=2), flush=True)

    dispatch_ok = dispatch_returncode == 0 or dispatch_excused["applied"]
    target_pass = verdict.get("target_pass") is True
    return 0 if (dispatch_ok and target_pass) else 1


if __name__ == "__main__":
    sys.exit(main())
