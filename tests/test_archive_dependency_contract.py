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
        archived_skills = {
            path.name
            for path in SKILL_ARCHIVES.glob("*/*")
            if path.is_dir()
        }
        active_command_text = "\n".join(
            path.read_text(encoding="utf-8", errors="ignore")
            for path in ACTIVE_COMMANDS.rglob("*.md")
        )
        active_skill_text = "\n".join(
            path.read_text(encoding="utf-8", errors="ignore")
            for path in ACTIVE_SKILLS.rglob("SKILL.md")
        )
        active_text = f"{active_command_text}\n{active_skill_text}"

        broken_skills = {}
        for skill_name in sorted(archived_skills):
            pattern = rf"(?:(?:\.claude|~/\.claude)?/skills/){re.escape(skill_name)}(?:/|/SKILL\.md|\b)"
            matches = re.findall(pattern, active_text)
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
        active_command_text = "\n".join(
            path.read_text(encoding="utf-8", errors="ignore")
            for path in ACTIVE_COMMANDS.rglob("*.md")
        )
        active_skill_text = "\n".join(
            path.read_text(encoding="utf-8", errors="ignore")
            for path in ACTIVE_SKILLS.rglob("SKILL.md")
        )
        active_text = f"{active_command_text}\n{active_skill_text}"

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
