"""Structural contract for the /nextsteps command file."""

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
NEXTSTEPS_CMD = REPO_ROOT / ".claude" / "commands" / "nextsteps.md"


class NextstepsCommandContractTest(unittest.TestCase):
    def test_has_yaml_frontmatter(self):
        self.assertTrue(
            NEXTSTEPS_CMD.is_file(),
            f"nextsteps command file missing at {NEXTSTEPS_CMD}",
        )
        text = NEXTSTEPS_CMD.read_text(encoding="utf-8")
        self.assertTrue(
            text.startswith("---\n"),
            "nextsteps command file must start with YAML frontmatter",
        )
        end = text.find("\n---\n", 4)
        self.assertGreater(
            end,
            4,
            "nextsteps command YAML frontmatter must close with a second `---` line.",
        )


if __name__ == "__main__":
    unittest.main()
