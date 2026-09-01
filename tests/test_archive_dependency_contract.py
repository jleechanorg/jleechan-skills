"""Contracts for recoverable skill and command archives."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from scripts.skill_portability_scan import parse_frontmatter

REPO_ROOT = Path(__file__).resolve().parent.parent
ACTIVE_SKILLS = REPO_ROOT / ".claude" / "skills"
SKILL_ARCHIVES = REPO_ROOT / ".claude" / "skills_archive"
ACTIVE_COMMANDS = REPO_ROOT / ".claude" / "commands"
COMMAND_ARCHIVES = REPO_ROOT / ".claude" / "commands_archive"


def _active_caller_text() -> str:
    """Concatenated text of every active command/skill markdown file.

    Scans *.md under .claude/skills (not just SKILL.md) so dangling
    references living in reference/doc files alongside a skill's SKILL.md
    are caught, not just references inside SKILL.md itself.
    """
    active_command_text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in ACTIVE_COMMANDS.rglob("*.md")
    )
    active_skill_text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in ACTIVE_SKILLS.rglob("*.md")
    )
    return f"{active_command_text}\n{active_skill_text}"


class ArchiveDependencyContractTest(unittest.TestCase):
    def test_active_skills_have_discovery_frontmatter(self) -> None:
        invalid = []
        for skill_file in ACTIVE_SKILLS.glob("*/SKILL.md"):
            fields = parse_frontmatter(
                skill_file.read_text(encoding="utf-8", errors="ignore")
            )
            name = fields.get("name", "")
            if (
                name != skill_file.parent.name
                or re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) is None
                or not fields.get("description")
            ):
                invalid.append(skill_file.parent.name)
        self.assertEqual(invalid, [])

    def test_active_skill_tree_contains_no_archive_containers(self) -> None:
        archive_containers = {
            path.name
            for path in ACTIVE_SKILLS.rglob("*")
            if path.is_dir()
            if path.name == "_archive" or path.name.startswith("_archived_")
        }
        self.assertEqual(archive_containers, set())

    def test_archived_skills_have_no_active_path_callers(self) -> None:
        """Dynamic contract: no active skill or command may reference an archived skill by path."""
        # Recursive: archive batches nest at varying depths (e.g.
        # legacy-pre-2026-08-27/packages/<name>/SKILL.md is 3 levels deep), so a
        # fixed "*/*" glob silently misses deeper archives and would also treat
        # an intermediate container dir like "packages" as a bogus skill name.
        active_skill_names = {path.parent.name for path in ACTIVE_SKILLS.glob("*/SKILL.md")}
        # A name can appear in an old archive snapshot (e.g. a superseded
        # duplicate under legacy-pre-2026-08-27/packages/) while ALSO being
        # currently active under .claude/skills/ today. The active copy wins;
        # only flag names with no active counterpart as "archived."
        archived_skills = {
            skill_md.parent.name
            for skill_md in SKILL_ARCHIVES.rglob("SKILL.md")
        } - active_skill_names
        active_text = _active_caller_text()

        broken_skills = {}
        for skill_name in sorted(archived_skills):
            path_pattern = (
                rf"(?:(?:\.claude|~/\.claude)?/skills/){re.escape(skill_name)}"
                rf"(?:/|/SKILL\.md(?![A-Za-z0-9_-])|(?![A-Za-z0-9_-]))"
            )
            # Bare filename prose mentions (e.g. "Related Skills" bullets:
            # `dice-authenticity-standards.md`, See dice-authenticity-standards.md,
            # or a markdown link [x](dice-authenticity-standards.md)) don't
            # include a /skills/ path prefix, so they slip past path_pattern
            # above. Match the filename with or without backticks/markdown-link
            # parens, requiring a non-identifier boundary on both sides so we
            # don't match a longer skill/file name that merely contains this one.
            bare_filename_pattern = (
                rf"(?<![A-Za-z0-9_-]){re.escape(skill_name)}\.md(?![A-Za-z0-9_-])"
            )
            matches = re.findall(path_pattern, active_text) + re.findall(
                bare_filename_pattern, active_text
            )
            if matches:
                broken_skills[skill_name] = len(matches)

        self.assertEqual(
            broken_skills,
            {},
            f"Archived skills are still referenced by path in active commands/skills: {broken_skills}",
        )

    def test_archived_commands_have_no_active_workflow_callers(self) -> None:
        """Dynamic contract: no active skill or command may invoke or link to an archived command."""
        archived = {
            path.stem
            for path in COMMAND_ARCHIVES.glob("*/*.md")
            if path.name != "README.md"
        }
        active_text = _active_caller_text()

        broken_commands = {}
        for name in sorted(archived):
            slash_pattern = rf"(?<![A-Za-z0-9_.-])/(?:extended-library:)?{re.escape(name)}(?![A-Za-z0-9_-])"
            md_link_pattern = rf"\([^)]*?\b{re.escape(name)}\.md\)"
            matches = len(re.findall(slash_pattern, active_text)) + len(re.findall(md_link_pattern, active_text))
            if matches > 0:
                broken_commands[name] = matches

        self.assertEqual(
            broken_commands,
            {},
            f"Archived commands are still referenced in active commands/skills: {broken_commands}",
        )


if __name__ == "__main__":
    unittest.main()
