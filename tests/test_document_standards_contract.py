"""Focused contract tests for document-standards thin commands and canonical skill."""

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
COMMANDS = REPO_ROOT / ".claude" / "commands"
SKILLS = REPO_ROOT / ".claude" / "skills"


class DocumentStandardsContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.cmd_path = COMMANDS / "document-standards.md"
        self.alias_path = COMMANDS / "ds.md"
        self.skill_path = SKILLS / "document-standards" / "SKILL.md"

    def test_document_standards_command_is_thin_dispatcher(self) -> None:
        self.assertTrue(self.cmd_path.is_file(), f"Missing {self.cmd_path}")
        content = self.cmd_path.read_text(encoding="utf-8")
        lines = content.splitlines()

        # Must be thin: <= 15 lines
        self.assertLessEqual(
            len(lines),
            15,
            f"document-standards.md must be <= 15 lines, got {len(lines)} lines",
        )

        # Must contain frontmatter
        self.assertTrue(content.startswith("---\n"), "Missing frontmatter")
        self.assertIn("description:", content)

        # Must cleanly forward $ARGUMENTS to canonical skill path
        self.assertIn(
            "${CLAUDE_HOME:-$HOME/.claude}/skills/document-standards/SKILL.md",
            content,
        )
        self.assertIn("$ARGUMENTS", content)

        # Must NOT duplicate bulky lane logic inline
        self.assertNotIn("## Universal lanes", content)
        self.assertNotIn("AI-tell sub-pass", content)
        self.assertNotIn("## Supporting skills", content)

    def test_ds_alias_is_thin_dispatcher(self) -> None:
        self.assertTrue(self.alias_path.is_file(), f"Missing {self.alias_path}")
        content = self.alias_path.read_text(encoding="utf-8")
        lines = content.splitlines()

        # Must be thin: <= 15 lines
        self.assertLessEqual(
            len(lines),
            15,
            f"ds.md must be <= 15 lines, got {len(lines)} lines",
        )

        # Must contain frontmatter
        self.assertTrue(content.startswith("---\n"), "Missing frontmatter")
        self.assertIn("description:", content)

        # Must cleanly forward $ARGUMENTS to canonical skill path
        self.assertIn(
            "${CLAUDE_HOME:-$HOME/.claude}/skills/document-standards/SKILL.md",
            content,
        )
        self.assertIn("$ARGUMENTS", content)

        # Must NOT duplicate bulky lane logic inline
        self.assertNotIn("## Universal lanes", content)
        self.assertNotIn("AI-tell sub-pass", content)

    def test_document_standards_skill_contains_full_canonical_specification(self) -> None:
        self.assertTrue(self.skill_path.is_file(), f"Missing {self.skill_path}")
        content = self.skill_path.read_text(encoding="utf-8")

        # Frontmatter assertions
        self.assertTrue(content.startswith("---\n"), "Missing frontmatter in SKILL.md")
        self.assertIn("name: document-standards", content)
        self.assertIn("revision_marker: DOCUMENT_STANDARDS_COMMAND_V1", content)

        # 5 Universal Lanes
        for lane in (
            "1. **Truth & contract**",
            "2. **Economy (ponytail for prose)**",
            "3. **Readability & structure**",
            "4. **Thermo-style document audit**",
            "5. **Output & operability**",
        ):
            with self.subTest(lane=lane):
                self.assertIn(lane, content)

        # Supporting skills
        for sup in ("Ponytail", "Thermo-nuclear code quality", "Writer", "gdocs-access", "pr-description-sections"):
            with self.subTest(supporting_skill=sup):
                self.assertIn(sup, content)

        # AI-tell sub-pass requirements
        self.assertIn("## AI-tell sub-pass (runs inside lane 3)", content)
        self.assertIn("### Discriminator — run before flagging anything", content)
        self.assertIn("1. **Deletion test**", content)
        self.assertIn("2. **Referent test**", content)
        self.assertIn("3. **Evidence test**", content)
        self.assertIn("### Protected class: Honesty qualifiers", content)
        self.assertIn("### Catalogue", content)
        self.assertIn("Negative parallelism", content)
        self.assertIn("Significance inflation", content)
        self.assertIn("Magic adverbs", content)

        # Workflow, Report, Smoke-test, Relationship to code-standards
        self.assertIn("## Workflow", content)
        self.assertIn("## Report format", content)
        self.assertIn("## Smoke-test mode", content)
        self.assertIn("DOCUMENT_STANDARDS_COMMAND_V1", content)
        self.assertIn("## Relationship to /code-standards", content)

    def test_portability_and_claude_home_resolution(self) -> None:
        for path in (self.cmd_path, self.alias_path, self.skill_path):
            content = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertNotIn("/Users/jleechan", content)
                self.assertNotIn("/home/", content)


if __name__ == "__main__":
    unittest.main()
