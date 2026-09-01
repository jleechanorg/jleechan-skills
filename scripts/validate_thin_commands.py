"""Validate portable, thin slash-command dispatchers."""

from dataclasses import dataclass
from pathlib import Path
import re


MAX_DISPATCHER_LINES = 15
SKILL_REFERENCE = re.compile(
    r"(?:\$\{CLAUDE_HOME:-\$HOME/\.claude\}|~?/\.claude)"
    r"/skills/([a-z0-9][a-z0-9-]*)/SKILL\.md"
)
IGNORED_COMMAND_DOCS = frozenset(
    {
        "_shared/header.md",
        "backup-2026-06-27-team-claude-no-teamcreate/team-claude.md",
        "backup-2026-06-27-team-claude-no-teamcreate/team-mini.md",
        "extended-library/README_EXPORT_TEMPLATE.md",
        "extended-library/pair-examples.md",
    }
)


@dataclass(frozen=True)
class ValidationResult:
    command_count: int
    dispatcher_count: int
    errors: list[str]
    routable_count: int = 0
    ignored_count: int = 0
    ignored_paths: tuple[str, ...] = ()


def render_arguments(template: str, arguments: str) -> str:
    """Keep raw caller arguments intact, including quoted or stacked values."""
    return template.replace("$ARGUMENTS", arguments)


def validate_top_level_commands(commands_dir: Path, skills_dir: Path) -> ValidationResult:
    """Validate top-level commands (.claude/commands/*.md)."""
    errors: list[str] = []
    dispatcher_count = 0
    ignored_paths: list[str] = []
    commands = sorted(commands_dir.glob("*.md"))
    for command in commands:
        relative = command.relative_to(commands_dir).as_posix()
        if relative in IGNORED_COMMAND_DOCS:
            ignored_paths.append(relative)
            continue
        valid = True
        text = command.read_text(encoding="utf-8")
        lines = text.splitlines()
        if not text.startswith("---\n"):
            errors.append(f"{relative}: missing YAML frontmatter")
            valid = False
        if len(lines) > MAX_DISPATCHER_LINES:
            errors.append(
                f"{relative}: {len(lines)} lines exceeds {MAX_DISPATCHER_LINES}"
            )
            valid = False
        matches = SKILL_REFERENCE.findall(text)
        if len(matches) == 0:
            errors.append(f"{relative}: needs at least one local SKILL.md target")
            valid = False
            continue
        for match in matches:
            target = skills_dir / match / "SKILL.md"
            if not target.is_file():
                errors.append(
                    f"{relative}: unresolved target {target.relative_to(skills_dir)}"
                )
                valid = False
        if "$ARGUMENTS" not in text:
            errors.append(f"{relative}: does not forward $ARGUMENTS")
            valid = False
        if valid:
            dispatcher_count += 1
    return ValidationResult(
        len(commands),
        dispatcher_count,
        errors,
        len(commands) - len(ignored_paths),
        len(ignored_paths),
        tuple(ignored_paths),
    )


def validate_commands(commands_dir: Path, skills_dir: Path, top_level_only: bool = True) -> ValidationResult:
    """Validate slash commands. Defaults to top_level_only to keep extended-library commands intact and distinct."""
    if top_level_only:
        return validate_top_level_commands(commands_dir, skills_dir)
    errors: list[str] = []
    dispatcher_count = 0
    ignored_paths: list[str] = []
    commands = sorted(commands_dir.rglob("*.md"))
    for command in commands:
        relative = command.relative_to(commands_dir).as_posix()
        if relative in IGNORED_COMMAND_DOCS:
            ignored_paths.append(relative)
            continue
        valid = True
        text = command.read_text(encoding="utf-8")
        lines = text.splitlines()
        if not text.startswith("---\n"):
            errors.append(f"{relative}: missing YAML frontmatter")
            valid = False
        if len(lines) > MAX_DISPATCHER_LINES:
            errors.append(
                f"{relative}: {len(lines)} lines exceeds {MAX_DISPATCHER_LINES}"
            )
            valid = False
        matches = SKILL_REFERENCE.findall(text)
        if len(matches) == 0:
            errors.append(f"{relative}: needs at least one local SKILL.md target")
            valid = False
            continue
        for match in matches:
            target = skills_dir / match / "SKILL.md"
            if not target.is_file():
                errors.append(
                    f"{relative}: unresolved target {target.relative_to(skills_dir)}"
                )
                valid = False
        if "$ARGUMENTS" not in text:
            errors.append(f"{relative}: does not forward $ARGUMENTS")
            valid = False
        if valid:
            dispatcher_count += 1
    return ValidationResult(
        len(commands),
        dispatcher_count,
        errors,
        len(commands) - len(ignored_paths),
        len(ignored_paths),
        tuple(ignored_paths),
    )
