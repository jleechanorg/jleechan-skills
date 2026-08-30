"""Validate portable, thin slash-command dispatchers."""

from dataclasses import dataclass
from pathlib import Path
import re


MAX_DISPATCHER_LINES = 15
SKILL_REFERENCE = re.compile(
    r"(?:\$\{CLAUDE_HOME:-\$HOME/\.claude\}|~?/\.claude)"
    r"/skills/([a-z0-9][a-z0-9-]*)/SKILL\.md"
)


@dataclass(frozen=True)
class ValidationResult:
    command_count: int
    dispatcher_count: int
    errors: list[str]


def render_arguments(template: str, arguments: str) -> str:
    """Keep raw caller arguments intact, including quoted or stacked values."""
    return template.replace("$ARGUMENTS", arguments)


def validate_commands(commands_dir: Path, skills_dir: Path) -> ValidationResult:
    errors: list[str] = []
    dispatcher_count = 0
    commands = sorted(commands_dir.glob("*.md"))
    for command in commands:
        valid = True
        text = command.read_text(encoding="utf-8")
        lines = text.splitlines()
        if not text.startswith("---\n"):
            errors.append(f"{command.name}: missing YAML frontmatter")
            valid = False
        if len(lines) > MAX_DISPATCHER_LINES:
            errors.append(
                f"{command.name}: {len(lines)} lines exceeds {MAX_DISPATCHER_LINES}"
            )
            valid = False
        matches = SKILL_REFERENCE.findall(text)
        if len(matches) != 1:
            errors.append(f"{command.name}: needs exactly one local SKILL.md target")
            continue
        target = skills_dir / matches[0] / "SKILL.md"
        if not target.is_file():
            errors.append(f"{command.name}: unresolved target {target.relative_to(skills_dir)}")
            valid = False
        if "$ARGUMENTS" not in text:
            errors.append(f"{command.name}: does not forward $ARGUMENTS")
            valid = False
        if valid:
            dispatcher_count += 1
    return ValidationResult(len(commands), dispatcher_count, errors)
