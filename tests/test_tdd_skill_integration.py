"""Exercise TDD discovery, dependency closure, and real installation.

These check packaging invariants, not a model's semantic compliance with prose.
Behavioral forward-test evidence is reported separately.
"""

import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from scripts.validate_thin_commands import render_arguments, validate_commands

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / '.claude/skills'
RESOURCES = ('SKILL.md', 'tests.md', 'mocking.md', 'agents/openai.yaml')
DEPENDENCIES = ('4layer', 'pr-blocker-min-repro', 'integration-verification',
                'superpowers-writing-plans')


class TddSkillIntegrationTest(unittest.TestCase):
    def test_hermes_resources_project_one_canonical_source(self):
        for relative in RESOURCES:
            with self.subTest(resource=relative):
                canonical = SKILLS / 'tdd' / relative
                self.assertTrue(canonical.is_file(), canonical)
                hermes = ROOT / 'hermes/skills/tdd' / relative
                self.assertTrue(hermes.is_symlink(), hermes)
                self.assertEqual(hermes.resolve(), canonical.resolve())

    def test_both_command_routes_forward_arguments_to_canonical_skill(self):
        with tempfile.TemporaryDirectory() as directory:
            commands = Path(directory)
            for route in ('tdd.md', 'extended-library/tdd.md'):
                source = ROOT / '.claude/commands' / route
                self.assertTrue(source.is_file(), source)
                shutil.copy2(source, commands / route.replace('/', '-'))
            result = validate_commands(commands, SKILLS)
            self.assertEqual([], result.errors)
            self.assertEqual(2, result.dispatcher_count)
            for command in commands.glob('*.md'):
                self.assertIn('/skills/tdd/SKILL.md', command.read_text())
                raw = '"public checkout" --plan docs/plans/existing.md'
                self.assertIn(raw, render_arguments(command.read_text(), raw))

    def test_installed_skill_references_resolve_outside_the_checkout(self):
        # Run the real installer against a minimal distribution, then traverse
        # TDD's links in an unrelated installed home. Missing/renamed companions
        # fail because their target bytes cannot be reached, not a prose match.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / 'distribution'
            fixture.mkdir()
            installer = ROOT / 'install-claude-commands.sh'
            shutil.copy2(installer, fixture / installer.name)
            for name in ('tdd', *DEPENDENCIES):
                source = SKILLS / name
                self.assertTrue((source / 'SKILL.md').is_file(), source)
                shutil.copytree(source, fixture / '.claude/skills' / name)
            command = fixture / '.claude/commands/tdd.md'
            command.parent.mkdir(parents=True)
            shutil.copy2(ROOT / '.claude/commands/tdd.md', command)
            installed = root / 'installed'
            result = subprocess.run(
                ['bash', str(fixture / installer.name)], cwd=root,
                env={**os.environ, 'CLAUDE_HOME': str(installed)},
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(0, result.returncode, result.stderr + result.stdout)
            entry = installed / 'skills/tdd/SKILL.md'
            links = re.findall(r'\]\(([^)]+)\)', entry.read_text())
            local = [link for link in links if not re.match(r'https?://', link)]
            reached = {(entry.parent / link).resolve() for link in local}
            for dependency in ('4layer', 'superpowers-writing-plans'):
                target = installed / 'skills' / dependency / 'SKILL.md'
                self.assertIn(target.resolve(), reached)
            for target in reached:
                self.assertTrue(target.is_file(), target)
                self.assertTrue(target.is_relative_to(installed), target)
            for relative in RESOURCES:
                self.assertEqual((SKILLS/'tdd'/relative).read_bytes(),
                                 (installed/'skills/tdd'/relative).read_bytes())


if __name__ == '__main__':
    unittest.main()
