"""workflows/README.md must exist."""

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS_README = REPO_ROOT / "workflows" / "README.md"


class WorkflowsReadmeNoStaleCountTest(unittest.TestCase):
    def test_readme_exists(self):
        self.assertTrue(
            WORKFLOWS_README.is_file(), f"Missing {WORKFLOWS_README}"
        )


if __name__ == "__main__":
    unittest.main()
