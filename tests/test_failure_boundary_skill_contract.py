"""CI discovery and installer contracts for the failure-boundary skills."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class FailureBoundarySkillContract(unittest.TestCase):
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
