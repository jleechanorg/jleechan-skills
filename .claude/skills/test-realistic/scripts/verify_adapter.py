"""Onboarding conformance self-test for a project's dispatch_command adapter.

Run this ONCE when wiring a new project's .test-realistic.toml, before
trusting any real scenario run: it dispatches config.dispatch_command
against a trivial fixture pool+scenario, then checks that the REAL output
satisfies the actual contract the rest of this skill depends on -- not a
stricter, invented contract. The true contract (verified against
feature_coverage_judge.py and target_scoped_run.py's own code, not assumed):

  1. After the dispatcher exits, config.capture_glob matches at least one
     file under --output-root.
  2. Every non-blank line in every matching file parses as JSON.
  3. Every parsed line is a JSON object (dict) -- feature_coverage_judge.py
     accepts `list[dict[str, Any]]` with NO required key names; it treats
     each turn as an opaque dict handed to the model. This script does NOT
     require specific keys like "turn"/"action_taken" -- a project is free
     to name its own fields however it likes (e.g. turn_index/action_text
     is equally valid) as long as each line is a non-empty JSON object.
  4. At least one turn's dict is non-empty (an all-empty-dict capture is a
     dispatcher that ran but captured nothing meaningful -- a red flag
     worth surfacing at onboarding time, before it's mistaken for a working
     integration).

This is intentionally NOT a full scenario/coverage-judge run -- it never
calls the coverage judge itself. The configured dispatch command is still the
project's real command and may boot real services, browsers, and models; this
check does not replace that command with a fake one. It only proves the
adapter's OWN half of the contract (argv in, capture.jsonl out) and fails if
that real dispatch exits non-zero.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from config import ProjectConfig, find_config_path, load_config
from target_scoped_run import build_dispatch_command, collect_capture_paths


class AdapterVerificationError(RuntimeError):
    """Raised when a project's dispatch_command fails this conformance check.

    Never caught to report a false pass -- an adapter that fails this check
    must not be reported as ready.
    """


def _write_fixture_pool_and_scenario(tmp_dir: Path, config: ProjectConfig) -> tuple[Path, Path]:
    import yaml

    scenario_path = tmp_dir / "fixture_scenario.py"
    scenario_path.write_text(
        "FEATURE_SUMMARY = 'verify_adapter.py fixture target -- not a real feature'\n"
        "RELEVANT_SURFACES = []\n"
    )
    pool_path = tmp_dir / "fixture_pool.yaml"
    pool_path.write_text(
        yaml.safe_dump({"agents": [{"persona": p} for p in config.personas[:1]]})
    )
    return pool_path, scenario_path


def verify_adapter(
    config: ProjectConfig,
    *,
    turns: int = 1,
    mode: str = "headless",
    subprocess_runner=None,
) -> dict:
    """Run the fixture dispatch and check the real output. Returns a report
    dict; raises AdapterVerificationError on any contract violation."""
    import subprocess as _subprocess

    subprocess_runner = subprocess_runner or _subprocess.run

    with tempfile.TemporaryDirectory(prefix="verify-adapter-") as tmp:
        tmp_dir = Path(tmp)
        pool_path, scenario_path = _write_fixture_pool_and_scenario(tmp_dir, config)
        output_root = tmp_dir / "output"
        output_root.mkdir()

        cmd = build_dispatch_command(
            config,
            pool_path=pool_path,
            scenario_path=scenario_path,
            output_root=output_root,
            mode=mode,
            base_url=config.base_url,
            turns=turns,
        )
        proc = subprocess_runner(cmd, check=False, cwd=str(config.repo_root))
        if proc.returncode != 0:
            raise AdapterVerificationError(
                f"dispatch_command exited {proc.returncode}; adapter verification "
                "cannot pass even when capture files happen to be well-formed. "
                f"Command run: {cmd}"
            )

        capture_paths = collect_capture_paths(output_root, config.capture_glob)
        if not capture_paths:
            raise AdapterVerificationError(
                f"dispatch_command exited {proc.returncode} but produced no files matching "
                f"capture_glob={config.capture_glob!r} under {output_root}. Command run: {cmd}"
            )

        total_turns = 0
        non_empty_turns = 0
        for capture_path in capture_paths:
            for line_no, line in enumerate(capture_path.read_text().splitlines(), start=1):
                if not line.strip():
                    continue
                try:
                    parsed = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise AdapterVerificationError(
                        f"{capture_path}:{line_no} is not valid JSON: {exc}"
                    ) from exc
                if not isinstance(parsed, dict):
                    raise AdapterVerificationError(
                        f"{capture_path}:{line_no} parsed to a {type(parsed).__name__}, "
                        "not a JSON object -- every turn record must be a dict "
                        "(feature_coverage_judge.py requires list[dict])"
                    )
                total_turns += 1
                if parsed:
                    non_empty_turns += 1

        if total_turns == 0:
            raise AdapterVerificationError(
                f"capture file(s) matched but contained zero parseable turn lines: {capture_paths}"
            )
        if non_empty_turns == 0:
            raise AdapterVerificationError(
                f"all {total_turns} captured turn(s) were empty dicts ({{}}) -- the dispatcher "
                "ran and wrote output, but captured no actual content. Check that your adapter "
                "is really reading rendered state, not writing placeholder records."
            )

        return {
            "dispatch_returncode": proc.returncode,
            "capture_files": [str(p) for p in capture_paths],
            "total_turns": total_turns,
            "non_empty_turns": non_empty_turns,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Onboarding conformance check for a project's dispatch_command adapter "
        "(argv in, capture.jsonl out) -- no real model call, no coverage judgment."
    )
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--turns", type=int, default=1)
    parser.add_argument("--mode", default="headless")
    args = parser.parse_args(argv)

    config_path = args.config or find_config_path(Path.cwd())
    config = load_config(config_path)

    try:
        report = verify_adapter(config, turns=args.turns, mode=args.mode)
    except AdapterVerificationError as exc:
        print(f"ADAPTER VERIFICATION FAILED: {exc}", file=sys.stderr)
        return 1

    print(f"Adapter verification PASSED for {config.project_name!r}:")
    print(f"  dispatch returncode: {report['dispatch_returncode']}")
    print(f"  capture files: {report['capture_files']}")
    print(f"  turns captured: {report['total_turns']} ({report['non_empty_turns']} non-empty)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
