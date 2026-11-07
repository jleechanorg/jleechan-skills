"""CI discovery contract for the failure-boundary skills.

Installer copy fidelity in an isolated temporary CLAUDE_HOME is owned by
`tests/test_installer.py::InstallerIntegrationTest.test_clean_install_copies_every_source_file_and_validates_manifest`,
which drives the real installer over a synthetic source tree. The former
two-skill `shutil.copyfile` round-trip here only re-read the bytes it had just
copied, and it broke as soon as `self-hosted-runner-preflight` moved to an opt-in
plugin.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class FailureBoundarySkillContract(unittest.TestCase):
    def test_existing_ci_discovers_contract(self):
        workflow = (ROOT / '.github/workflows/tests.yml').read_text()
        self.assertIn('python3 -m unittest discover -s tests -p "test_*.py"', workflow)


if __name__ == '__main__':
    unittest.main()
