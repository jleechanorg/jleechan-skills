"""workflows/README.md must not hardcode a count of the examples it ships.

The README claimed "21 GitHub Actions workflow examples" while the directory
held 56 — the count went stale as workflows were added and nothing caught it.
This mirrors the rule already applied to the root README by
`test_readme_skill_counts.py`: link to the directory, do not transcribe a
number that drifts the moment the directory changes.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS_README = REPO_ROOT / "workflows" / "README.md"

# "21 GitHub Actions workflow examples", "contains 40 workflows", etc.
HARDCODED_COUNT = re.compile(
    r"\b\d+\s+(?:GitHub\s+Actions\s+)?workflow(?:\s+example)?s\b", re.IGNORECASE
)


class WorkflowsReadmeNoStaleCountTest(unittest.TestCase):
    def test_readme_exists(self):
        self.assertTrue(
            WORKFLOWS_README.is_file(), f"Missing {WORKFLOWS_README}"
        )

    def test_readme_does_not_hardcode_a_workflow_count(self):
        text = WORKFLOWS_README.read_text(encoding="utf-8")
        found = [m.group(0) for m in HARDCODED_COUNT.finditer(text)]
        self.assertEqual(
            found,
            [],
            "workflows/README.md must not hardcode how many workflow examples "
            "it ships — the number goes stale silently. Describe the directory "
            "instead. Found: " + ", ".join(found),
        )


if __name__ == "__main__":
    unittest.main()
