"""Contracts for recoverable skill and command archives."""

import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
ACTIVE_SKILLS = REPO_ROOT / ".claude" / "skills"
SKILL_ARCHIVE = (
    REPO_ROOT / ".claude" / "skills_archive" / "2026-08-27-historical-zero-use"
)
ACTIVE_COMMANDS = REPO_ROOT / ".claude" / "commands"
COMMAND_ARCHIVE = (
    REPO_ROOT / ".claude" / "commands_archive" / "2026-08-27-historical-zero-use"
)

RETAINED_DEPENDENCIES = {
    "babysit-openclaw",
    "claude-code-computer-use",
    "pair-benchmark-all-executors",
    "pr-quantity-control",
    "user-story-worldai",
}


class ArchiveDependencyContractTest(unittest.TestCase):
    def test_active_skills_have_discovery_frontmatter(self):
        missing = []
        for skill_file in ACTIVE_SKILLS.glob("*/SKILL.md"):
            header = skill_file.read_text(encoding="utf-8", errors="ignore")[:1024]
            if not header.startswith("---\n") or not re.search(
                r"^description:\s*\S", header, re.MULTILINE
            ):
                missing.append(skill_file.parent.name)
        self.assertEqual(missing, [])

    def test_active_skill_tree_contains_no_archive_containers(self):
        archive_containers = {
            path.name
            for path in ACTIVE_SKILLS.rglob("*")
            if path.is_dir()
            if path.name == "_archive" or path.name.startswith("_archived_")
        }
        self.assertEqual(archive_containers, set())

    def test_required_active_skill_dependencies_are_not_archived(self):
        for name in RETAINED_DEPENDENCIES:
            with self.subTest(skill=name):
                self.assertTrue((ACTIVE_SKILLS / name / "SKILL.md").is_file())
                self.assertFalse((SKILL_ARCHIVE / name).exists())

    def test_archived_commands_have_no_active_workflow_callers(self):
        archived = {
            path.stem for path in COMMAND_ARCHIVE.glob("*.md") if path.name != "README.md"
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
        called = {
            name
            for name in archived
            if re.search(
                rf"(?<![A-Za-z0-9_.-])/(?:extended-library:)?{re.escape(name)}(?![A-Za-z0-9_-])",
                active_text,
            )
        }
        self.assertEqual(called, set())


if __name__ == "__main__":
    unittest.main()
