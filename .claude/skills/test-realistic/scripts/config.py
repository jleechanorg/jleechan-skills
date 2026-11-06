"""Per-project config contract for the generalized /test-realistic skill.

This module owns ZERO project names, ports, or paths. Every value a project
needs (base URL, feature-surface vocabulary, how to dispatch a real player
swarm, personas, repo root, ...) is supplied by a project-local
``.test-realistic.toml`` file, loaded here and validated for required shape.

Design note: this generalizes an existing production /test-realistic harness
(see ../PROVENANCE.md for lineage). The universal pipeline shape (model-delegated scenario
generation -> real player-agent swarm -> anti-false-green coverage judge ->
target-scoped verdict) is preserved verbatim; everything that told the
harness *which app* to test is moved into this config contract instead.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class ConfigError(RuntimeError):
    """Raised when a project's .test-realistic.toml is missing or malformed.

    Callers must treat this as a hard failure -- never silently fall back to
    a default that masks a missing required field, since a missing
    feature_surface_vocabulary or dispatch_command means the generated
    scenarios/judge calls would be grounded in nothing real.
    """


# Fields every project config MUST supply. There is no built-in default for
# any of these -- a project without them is a project this skill cannot yet
# run against, and that must fail loud at load time, not partway through a
# run.
REQUIRED_FIELDS = (
    "project_name",
    "repo_root",
    "base_url",
    "feature_surface_vocabulary",
    "dispatch_command",
)

# Fields with sane, genuinely project-agnostic defaults. These are generic
# QA-persona archetypes (not tied to any game/domain vocabulary) -- a project
# may override or shrink the list (e.g. to run a single-agent swarm) but is
# not required to.
DEFAULT_PERSONAS = (
    "aggressive_power_user",
    "story_focused",
    "completionist",
    "casual_user",
    "new_user",
)

DEFAULT_CAPTURE_GLOB = "agent-*/capture.jsonl"
DEFAULT_TURNS = 15
DEFAULT_MODEL = "gemini-3.8-flash-high"
DEFAULT_AGY_TIMEOUT_SECONDS = 120


@dataclass(frozen=True)
class ProjectConfig:
    """Validated view of a project's .test-realistic.toml.

    Every field here traces back to a config key -- nothing is hardcoded
    from a specific project. See examples/test-realistic.example.toml for
    the full annotated contract.
    """

    project_name: str
    repo_root: Path
    base_url: str
    feature_surface_vocabulary: tuple[str, ...]
    dispatch_command: tuple[str, ...]
    backend_url: str | None = None
    personas: tuple[str, ...] = DEFAULT_PERSONAS
    actor_fixtures: tuple[str, ...] = ()
    capture_glob: str = DEFAULT_CAPTURE_GLOB
    output_root_default: Path | None = None
    doc_target_patterns: tuple[str, ...] = ()
    doc_dispatch_command: tuple[str, ...] | None = None
    turns_default: int = DEFAULT_TURNS
    agy_model: str = DEFAULT_MODEL
    agy_timeout_seconds: int = DEFAULT_AGY_TIMEOUT_SECONDS
    runner_excuse_predicate: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


def _require_str_list(value: Any, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(
        isinstance(v, str) and v.strip() for v in value
    ):
        raise ConfigError(
            f"{field_name} must be a list of non-empty strings, got {value!r}"
        )
    return tuple(value)


def _require_nonempty_str_list(value: Any, field_name: str) -> tuple[str, ...]:
    result = _require_str_list(value, field_name)
    if not result:
        raise ConfigError(f"{field_name} must be a non-empty list, got {value!r}")
    return result


def load_config(config_path: Path) -> ProjectConfig:
    """Load and validate a project's .test-realistic.toml.

    Raises ConfigError on any missing required field or malformed shape.
    Never fills in a silent default for a REQUIRED_FIELDS entry.
    """
    if not config_path.exists():
        raise ConfigError(
            f"No project config found at {config_path}. Every project using "
            "this skill must supply one -- see "
            "~/.claude/skills/test-realistic/examples/test-realistic.example.toml"
        )

    try:
        raw = tomllib.loads(config_path.read_text())
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{config_path} is not valid TOML: {exc}") from exc

    missing = [f for f in REQUIRED_FIELDS if f not in raw]
    if missing:
        raise ConfigError(
            f"{config_path} is missing required field(s): {', '.join(missing)}"
        )

    project_name = raw["project_name"]
    if not isinstance(project_name, str) or not project_name.strip():
        raise ConfigError("project_name must be a non-empty string")

    repo_root = Path(raw["repo_root"]).expanduser()
    if not repo_root.is_absolute():
        # Resolve relative to the config file's own directory, never CWD --
        # CWD is whatever the caller happened to be in.
        repo_root = (config_path.parent / repo_root).resolve()
    if not repo_root.is_dir():
        raise ConfigError(f"repo_root {repo_root} does not exist or is not a directory")

    base_url = raw["base_url"]
    if not isinstance(base_url, str) or not base_url.strip():
        raise ConfigError("base_url must be a non-empty string")

    feature_surface_vocabulary = _require_nonempty_str_list(
        raw["feature_surface_vocabulary"], "feature_surface_vocabulary"
    )

    dispatch_command = raw["dispatch_command"]
    if not isinstance(dispatch_command, list) or not dispatch_command or not all(
        isinstance(v, str) for v in dispatch_command
    ):
        raise ConfigError(
            "dispatch_command must be a non-empty list of strings (argv-style "
            f"command template), got {dispatch_command!r}"
        )

    backend_url = raw.get("backend_url")
    if backend_url is not None and not isinstance(backend_url, str):
        raise ConfigError("backend_url must be a string if present")

    personas = (
        _require_nonempty_str_list(raw["personas"], "personas")
        if "personas" in raw
        else DEFAULT_PERSONAS
    )

    # actor_fixtures may legitimately be an explicit empty list (a project
    # with no "character"/actor-preset concept at all) -- only reject a
    # wrong TYPE, never an empty-but-present list.
    actor_fixtures = (
        _require_str_list(raw["actor_fixtures"], "actor_fixtures")
        if "actor_fixtures" in raw
        else ()
    )

    capture_glob = raw.get("capture_glob", DEFAULT_CAPTURE_GLOB)
    if not isinstance(capture_glob, str) or not capture_glob:
        raise ConfigError("capture_glob must be a non-empty string")

    output_root_default = raw.get("output_root_default")
    output_root_path = (
        Path(output_root_default).expanduser() if output_root_default else None
    )
    if output_root_path is not None and not output_root_path.is_absolute():
        output_root_path = (config_path.parent / output_root_path).resolve()

    doc_target_patterns = (
        _require_str_list(raw["doc_target_patterns"], "doc_target_patterns")
        if "doc_target_patterns" in raw
        else ()
    )

    doc_dispatch_command = raw.get("doc_dispatch_command")
    if doc_dispatch_command is not None:
        if not isinstance(doc_dispatch_command, list) or not all(
            isinstance(v, str) for v in doc_dispatch_command
        ):
            raise ConfigError("doc_dispatch_command must be a list of strings if present")
        doc_dispatch_command = tuple(doc_dispatch_command)

    turns_default = raw.get("turns_default", DEFAULT_TURNS)
    if not isinstance(turns_default, int) or turns_default <= 0:
        raise ConfigError("turns_default must be a positive integer")

    agy_model = raw.get("agy_model", DEFAULT_MODEL)
    if not isinstance(agy_model, str) or not agy_model:
        raise ConfigError("agy_model must be a non-empty string")

    agy_timeout_seconds = raw.get("agy_timeout_seconds", DEFAULT_AGY_TIMEOUT_SECONDS)
    if not isinstance(agy_timeout_seconds, int) or agy_timeout_seconds <= 0:
        raise ConfigError("agy_timeout_seconds must be a positive integer")

    runner_excuse_predicate = raw.get("runner_excuse_predicate")
    if runner_excuse_predicate is not None and not isinstance(
        runner_excuse_predicate, str
    ):
        raise ConfigError("runner_excuse_predicate must be a string (module:function) if present")

    return ProjectConfig(
        project_name=project_name,
        repo_root=repo_root,
        base_url=base_url,
        feature_surface_vocabulary=feature_surface_vocabulary,
        dispatch_command=tuple(dispatch_command),
        backend_url=backend_url,
        personas=personas,
        actor_fixtures=actor_fixtures,
        capture_glob=capture_glob,
        output_root_default=output_root_path,
        doc_target_patterns=doc_target_patterns,
        doc_dispatch_command=doc_dispatch_command,
        turns_default=turns_default,
        agy_model=agy_model,
        agy_timeout_seconds=agy_timeout_seconds,
        runner_excuse_predicate=runner_excuse_predicate,
        raw=raw,
    )


def find_config_path(start_dir: Path) -> Path:
    """Walk up from start_dir looking for .test-realistic.toml.

    Mirrors how git/pytest find their own root config -- this lets the CLI
    entrypoints be invoked from any subdirectory of a project.
    """
    current = start_dir.resolve()
    for candidate in (current, *current.parents):
        config_path = candidate / ".test-realistic.toml"
        if config_path.exists():
            return config_path
    raise ConfigError(
        f"No .test-realistic.toml found in {start_dir} or any parent directory."
    )
