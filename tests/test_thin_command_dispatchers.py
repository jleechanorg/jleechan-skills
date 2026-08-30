"""Conformance tests for exported Claude slash-command dispatchers."""

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
COMMANDS = REPO_ROOT / ".claude" / "commands"


class ThinCommandDispatchersTest(unittest.TestCase):
    def test_inventory_resolves_to_local_skills_with_argument_forwarding(self):
        from scripts.validate_thin_commands import validate_commands

        result = validate_commands(COMMANDS, REPO_ROOT / ".claude" / "skills")
        self.assertEqual([], result.errors, "\n".join(result.errors))
        self.assertEqual(43, result.command_count)
        self.assertEqual(43, result.dispatcher_count)

    def test_dispatchers_preserve_empty_quoted_positional_and_stacked_arguments(self):
        from scripts.validate_thin_commands import render_arguments

        cases = {
            "": "",
            '"two words"': '"two words"',
            "PR-42": "PR-42",
            "one two --mode=real": "one two --mode=real",
        }
        for supplied, expected in cases.items():
            with self.subTest(arguments=supplied):
                self.assertEqual(expected, render_arguments("$ARGUMENTS", supplied))

    def test_factory_is_a_thin_local_dispatcher(self):
        command = (COMMANDS / "factory.md").read_text(encoding="utf-8")
        self.assertEqual(1, command.count("/skills/dark-factory/SKILL.md"))
        self.assertTrue((REPO_ROOT / ".claude/skills/dark-factory/SKILL.md").is_file())
        self.assertLessEqual(len(command.splitlines()), 15)
        self.assertIn("$ARGUMENTS", command)

    def test_legacy_aliases_use_native_thin_dispatcher_metadata(self):
        aliases = {
            "smart-advisor": ("advice.md", "advice", "aliases: [smart-advisor]"),
            "webadvice": ("web-advice.md", "web-advice", "aliases: [webadvice]"),
            "df": ("factory.md", "dark-factory", "aliases: [f, df]"),
        }
        for alias, (command_name, skill_name, declaration) in aliases.items():
            with self.subTest(alias=alias):
                command = (COMMANDS / command_name).read_text(encoding="utf-8")
                frontmatter = command.split("---", 2)[1]
                self.assertIn(declaration, frontmatter)
                self.assertIn(f"/skills/{skill_name}/SKILL.md", command)
                self.assertIn("$ARGUMENTS", command)
                self.assertLessEqual(len(command.splitlines()), 15)

    def test_dispatcher_count_counts_valid_commands_not_errors(self):
        from tempfile import TemporaryDirectory

        from scripts.validate_thin_commands import validate_commands

        with TemporaryDirectory() as temp:
            root = Path(temp)
            commands = root / "commands"
            skills = root / "skills" / "dark-factory"
            commands.mkdir()
            skills.mkdir(parents=True)
            (skills / "SKILL.md").write_text("skill\n", encoding="utf-8")
            (commands / "valid.md").write_text(
                "---\ndescription: valid\n---\n"
                "Read ~/.claude/skills/dark-factory/SKILL.md with $ARGUMENTS.\n",
                encoding="utf-8",
            )
            (commands / "invalid.md").write_text(
                "---\ndescription: invalid\n---\n" + "extra\n" * 16,
                encoding="utf-8",
            )
            result = validate_commands(commands, root / "skills")

        self.assertEqual((2, 1, 2), (result.command_count, result.dispatcher_count, len(result.errors)))


if __name__ == "__main__":
    unittest.main()
