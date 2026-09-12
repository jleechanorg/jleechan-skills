"""Exercise the canonical code-review projection through the Hermes export pass."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
EXPORTER = ROOT / ".claude/commands/exportcommands.sh"


class CodeReviewExportTest(unittest.TestCase):
    def test_export_preserves_canonical_skill_and_find_discovery(self):
        source = EXPORTER.read_text()
        helper_start = source.index("COMMON_RSYNC_EXCLUDES=(")
        helper_end = source.index("# Compute Hermes-side file counts", helper_start)
        loop_start = source.index('for dir in "${HERMES_DIRS[@]}"; do')
        loop_end = source.index("\ndone", loop_start) + len("\ndone")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            canonical = root / ".claude/skills/code-review"
            shutil.copytree(ROOT / ".claude/skills/code-review", canonical)
            projected = root / "hermes/skills/code-review"
            projected.parent.mkdir(parents=True)
            original = ROOT / "hermes/skills/code-review"
            if original.is_symlink():
                projected.symlink_to(os.readlink(original), target_is_directory=True)
            else:
                shutil.copytree(original, projected, symlinks=True)
            upstream = root / "upstream/skills/code-review"
            upstream.mkdir(parents=True)
            (upstream / "SKILL.md").write_text("stale upstream skill\n")
            unrelated = upstream.parent / "other-skill"
            unrelated.mkdir()
            (unrelated / "SKILL.md").write_text("other skill\n")
            script = (
                "set -euo pipefail\nHERMES_DIRS=(skills)\n"
                + source[helper_start:helper_end]
                + source[loop_start:loop_end]
            )
            result = subprocess.run(
                ["bash", "-c", script], cwd=root,
                env={**os.environ, "HERMES_HOME": str(root / "upstream")},
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(
                (projected / "SKILL.md").resolve(), (canonical / "SKILL.md").resolve()
            )
            self.assertEqual(
                (projected / "SKILL.md").read_bytes(),
                (ROOT / ".claude/skills/code-review/SKILL.md").read_bytes(),
            )
            found = subprocess.check_output(
                ["find", "hermes/skills", "-name", "SKILL.md"],
                cwd=root, text=True, timeout=10,
            ).splitlines()
            self.assertIn("hermes/skills/code-review/SKILL.md", found)
            self.assertEqual(
                (root / "hermes/skills/other-skill/SKILL.md").read_text(),
                "other skill\n",
            )
