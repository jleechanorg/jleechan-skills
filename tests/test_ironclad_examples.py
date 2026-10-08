from __future__ import annotations

import re
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".claude" / "skills" / "ironclad" / "SKILL.md"


class IroncladExamplesTests(unittest.TestCase):
    def test_files_identical_example_uses_shell_exit_status(self) -> None:
        text = SKILL.read_text()
        match = re.search(r"\| files identical .* \| `([^`]+)` \|", text)
        self.assertIsNotNone(match)
        command = match.group(1).replace(r"\|", "|")

        with tempfile.TemporaryDirectory() as directory:
            workdir = Path(directory)
            (workdir / "a").write_text("same\n")
            (workdir / "b").write_text("same\n")
            equal = subprocess.run(
                ["bash", "-c", command],
                cwd=workdir,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(equal.returncode, 0)
            self.assertEqual(equal.stdout, "PASS E4\n")

            (workdir / "b").write_text("different\n")
            unequal = subprocess.run(
                ["bash", "-c", command],
                cwd=workdir,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(unequal.returncode, 0)
            self.assertEqual(unequal.stdout, "FAIL E4\n")

    def test_published_failure_examples_exit_nonzero(self) -> None:
        text = SKILL.read_text()
        start = text.index("Canonical self-grading forms:")
        end = text.index("Never use `wc -l`")
        for line in text[start:end].splitlines():
            match = re.search(r"\| [^|]+ \| .* \| `([^`]+)` \|", line)
            if match and "echo FAIL" in match.group(1):
                self.assertIn("exit 1", match.group(1))
                self.assertIn("{ echo FAIL", match.group(1))
            elif line.strip().startswith("&& echo PASS") and "echo FAIL" in line:
                self.assertIn("exit 1", line)
                self.assertIn("{ echo FAIL", line)


if __name__ == "__main__":
    unittest.main()
