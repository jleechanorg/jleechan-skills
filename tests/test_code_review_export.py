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
        for initial in (
            "projection", "legacy", "empty", "directory_alias", "unknown_alias",
            "nested_alias", "hermes_alias", "skills_alias",
        ):
            with self.subTest(initial=initial):
                self.exercise_export(initial)

    def test_hermes_only_export_still_imports_legacy_skill(self):
        self.exercise_export("empty", canonical_present=False)

    def exercise_export(self, initial, canonical_present=True):
        source = EXPORTER.read_text()
        helper_start = source.index("COMMON_RSYNC_EXCLUDES=(")
        helper_end = source.index("# Compute Hermes-side file counts", helper_start)
        loop_start = source.index("# ── Rsync ~/.hermes")
        loop_end = source.index("# ── Rsync ~/.codex", loop_start)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            canonical = root / ".claude/skills/code-review"
            if canonical_present:
                shutil.copytree(ROOT / ".claude/skills/code-review", canonical)
            projected = root / "hermes/skills/code-review"
            projected.parent.mkdir(parents=True)
            original = ROOT / "hermes/skills/code-review"
            if initial == "projection":
                shutil.copytree(original, projected, symlinks=True)
            elif initial == "legacy":
                projected.mkdir()
                (projected / "SKILL.md").write_text("legacy target skill\n")
            elif initial == "directory_alias":
                projected.symlink_to(
                    "../../.claude/skills/code-review", target_is_directory=True
                )
            elif initial == "unknown_alias":
                outside = root / "unrelated"
                outside.mkdir()
                (outside / "SKILL.md").write_text("preserve me\n")
                projected.symlink_to("../../unrelated", target_is_directory=True)
            elif initial in ("nested_alias", "hermes_alias", "skills_alias"):
                outside = root / "unrelated"
                outside.mkdir()
                (outside / "openai.yaml").write_text("preserve me\n")
                if initial == "nested_alias":
                    projected.mkdir()
                    alias = projected / "agents"
                    target = "../../../unrelated"
                elif initial == "hermes_alias":
                    (root / "hermes").rename(root / "saved-hermes")
                    alias = root / "hermes"
                    target = "unrelated"
                else:
                    projected.parent.rename(root / "saved-skills")
                    alias = root / "hermes/skills"
                    target = "../unrelated"
                alias.symlink_to(target, target_is_directory=True)
            upstream = root / "upstream/skills/code-review"
            upstream.mkdir(parents=True)
            (upstream / "SKILL.md").write_text("stale upstream skill\n")
            unrelated = upstream.parent / "other-skill"
            unrelated.mkdir()
            (unrelated / "SKILL.md").write_text("other skill\n")
            command = root / "upstream/commands/code-review"
            command.mkdir(parents=True)
            (command / "command.md").write_text("command content\n")
            script = (
                "set -euo pipefail\nHERMES_DIRS=(skills commands)\n"
                + source[helper_start:helper_end]
                + source[loop_start:loop_end]
            )
            result = subprocess.run(
                ["bash", "-c", script], cwd=root,
                env={**os.environ, "HERMES_HOME": str(root / "upstream")},
                capture_output=True, text=True, timeout=30,
            )
            if initial in ("nested_alias", "hermes_alias", "skills_alias"):
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(os.readlink(alias), target)
                self.assertEqual((outside / "openai.yaml").read_text(), "preserve me\n")
                self.assertEqual(list(outside.iterdir()), [outside / "openai.yaml"])
                return
            if initial == "unknown_alias":
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(os.readlink(projected), "../../unrelated")
                self.assertEqual((outside / "SKILL.md").read_text(), "preserve me\n")
                return
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(
                (root / "hermes/commands/code-review/command.md").read_text(),
                "command content\n",
            )
            if canonical_present:
                self.assertEqual(
                    (projected / "SKILL.md").resolve(),
                    (canonical / "SKILL.md").resolve(),
                )
                self.assertEqual(
                    (projected / "SKILL.md").read_bytes(),
                    (ROOT / ".claude/skills/code-review/SKILL.md").read_bytes(),
                )
                self.assertEqual(
                    (projected / "agents/openai.yaml").resolve(),
                    (canonical / "agents/openai.yaml").resolve(),
                )
            else:
                self.assertEqual(
                    (projected / "SKILL.md").read_text(), "stale upstream skill\n"
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
