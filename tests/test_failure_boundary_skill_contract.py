"""Instruction contracts only; these tests do not qualify any SDK or runner."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class FailureBoundarySkillContract(unittest.TestCase):
    def skill(self, name):
        return (ROOT / '.claude/skills' / name / 'SKILL.md').read_text()

    def require(self, text, phrases):
        text = ' '.join(text.split())
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_fixture_provenance_is_not_behavior_proof(self):
        self.require(self.skill('end2end-testing'), [
            'Fixture provenance is not SDK/transport behavior proof',
            'sanitized fixture SHA-256', 'original capture timestamp',
            'synthetic adapter', 'not a real SDK execution',
        ])

    def test_real_failure_boundary_and_negative_control(self):
        self.require(self.skill('end2end-testing'), [
            'body getter', 'shared buffer', 'single-consumption',
            'failing revision', 'same fixture', 'Release versus Debug',
            'require RED at the failing revision and GREEN at the candidate',
            'Retain a negative control for the precise behavior that escaped',
            'No new live capture or provider call is implied',
        ])

    def test_installed_cli_not_source_or_stub(self):
        self.require(self.skill('self-hosted-runner-preflight'), [
            'installed executable', 'resolved path', 'exact subcommand',
            'source checkout or capable stub is not installed capability proof',
        ])

    def test_negative_cli_and_cleanup_contract(self):
        self.require(self.skill('self-hosted-runner-preflight'), [
            'unsupported-command negative case', 'uninitialized cleanup path',
            'before checkout/build/upload', 'original exit status',
            'negative case that fails closed',
            'avoid cleanup against an unset or unowned path',
        ])

    def test_probe_side_effect_and_uncertain_upload_boundaries(self):
        self.require(self.skill('self-hosted-runner-preflight'), [
            'even a lookup can create state directories',
            'Do not change HOME/config/state', 'do not install a replacement',
            'reconcile the original upload receipt before any retry',
        ])

    def test_existing_ci_discovers_contract(self):
        workflow = (ROOT / '.github/workflows/tests.yml').read_text()
        self.assertIn('python3 -m unittest discover -s tests -p "test_*.py"', workflow)

    def test_candidate_skills_install_byte_identically_in_temporary_home(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root / 'source', root / 'target'
            source.mkdir()
            shutil.copyfile(ROOT / 'install-claude-commands.sh', source / 'install.sh')
            names = ('end2end-testing', 'self-hosted-runner-preflight')
            for name in names:
                destination = source / '.claude/skills' / name
                destination.mkdir(parents=True)
                shutil.copyfile(ROOT / '.claude/skills' / name / 'SKILL.md', destination / 'SKILL.md')
            try:
                result = subprocess.run(['bash', str(source / 'install.sh'), '--all'],
                                        cwd=source, env=os.environ | {'CLAUDE_HOME': str(target)},
                                        capture_output=True, text=True, timeout=30)
            except subprocess.TimeoutExpired as exc:
                self.fail(f'Isolated installer exceeded 30s: stdout={exc.stdout!r}; '
                          f'stderr={exc.stderr!r}')
            self.assertEqual(0, result.returncode, result.stderr)
            for name in names:
                self.assertEqual((source / '.claude/skills' / name / 'SKILL.md').read_bytes(),
                                 (target / 'skills' / name / 'SKILL.md').read_bytes())


if __name__ == '__main__':
    unittest.main()
