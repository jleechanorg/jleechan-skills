"""Exercise canonical skill projections through the Hermes export pass."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
EXPORTER = ROOT / ".claude/commands/exportcommands.sh"


class CodeReviewExportTest(unittest.TestCase):
    skill = "code-review"

    def test_export_preserves_canonical_skill_and_find_discovery(self):
        for initial in (
            "projection", "legacy", "empty", "directory_alias", "unknown_alias",
            "nested_alias", "hermes_alias", "skills_alias",
        ):
            with self.subTest(initial=initial):
                self.exercise_export(initial)

    def test_hermes_only_export_still_imports_legacy_skill(self):
        self.exercise_export("empty", canonical_present=False)

    def test_projection_survives_missing_hermes_installation(self):
        source = EXPORTER.read_text()
        start = source.index("# ── Rsync ~/.hermes")
        end = source.index("# ── Rsync ~/.codex", start)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            canonical = root / f".claude/skills/{self.skill}"
            shutil.copytree(ROOT / f".claude/skills/{self.skill}", canonical)
            # No Hermes installation: exercise real projection code without
            # rsync, rather than mocking the export's byte-copy behavior.
            result = subprocess.run(
                ["bash", "-c", "set -euo pipefail\nHERMES_DIRS=()\n" + source[start:end]],
                cwd=root, capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            for resource in canonical.rglob("*"):
                if resource.is_file():
                    projected = root / f"hermes/skills/{self.skill}" / resource.relative_to(canonical)
                    self.assertTrue(projected.is_symlink(), projected)
                    self.assertEqual(resource.resolve(), projected.resolve())

    def test_resource_directory_is_preserved_and_refused_before_writes(self):
        source = EXPORTER.read_text()
        start = source.index("# ── Rsync ~/.hermes")
        end = source.index("# ── Rsync ~/.codex", start)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / f".claude/skills/{self.skill}",
                            root / f".claude/skills/{self.skill}")
            collision = root / f"hermes/skills/{self.skill}/SKILL.md"
            collision.mkdir(parents=True)
            (collision / 'local.md').write_text('retain local work\n')
            result = subprocess.run(
                ["bash", "-c", "set -euo pipefail\nHERMES_DIRS=()\n" + source[start:end]],
                cwd=root, capture_output=True, text=True, timeout=10,
            )
            self.assertNotEqual(0, result.returncode)
            self.assertEqual('retain local work\n', (collision / 'local.md').read_text())
            self.assertEqual(['local.md'], [path.name for path in collision.iterdir()])
            self.assertFalse((collision.parent / 'agents').exists())

    def exercise_export(self, initial, canonical_present=True):
        skill = self.skill
        self.assertTrue((ROOT / f".claude/skills/{skill}/SKILL.md").is_file())
        source = EXPORTER.read_text()
        helper_start = source.index("COMMON_RSYNC_EXCLUDES=(")
        helper_end = source.index("# Compute Hermes-side file counts", helper_start)
        loop_start = source.index("# ── Rsync ~/.hermes")
        loop_end = source.index("# ── Rsync ~/.codex", loop_start)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            canonical = root / f".claude/skills/{skill}"
            if canonical_present:
                shutil.copytree(ROOT / f".claude/skills/{skill}", canonical)
            projected = root / f"hermes/skills/{skill}"
            projected.parent.mkdir(parents=True)
            original = ROOT / f"hermes/skills/{skill}"
            if initial == "projection":
                shutil.copytree(original, projected, symlinks=True)
            elif initial == "legacy":
                projected.mkdir()
                (projected / "SKILL.md").write_text("legacy target skill\n")
            elif initial == "directory_alias":
                projected.symlink_to(
                    f"../../.claude/skills/{skill}", target_is_directory=True
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
            upstream = root / f"upstream/skills/{skill}"
            upstream.mkdir(parents=True)
            (upstream / "SKILL.md").write_text("stale upstream skill\n")
            unrelated = upstream.parent / "other-skill"
            unrelated.mkdir()
            (unrelated / "SKILL.md").write_text("other skill\n")
            command = root / f"upstream/commands/{skill}"
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
                (root / f"hermes/commands/{skill}/command.md").read_text(),
                "command content\n",
            )
            if canonical_present:
                self.assertEqual(
                    (projected / "SKILL.md").resolve(),
                    (canonical / "SKILL.md").resolve(),
                )
                self.assertEqual(
                    (projected / "SKILL.md").read_bytes(),
                    (ROOT / f".claude/skills/{skill}/SKILL.md").read_bytes(),
                )
                self.assertEqual(
                    (projected / "agents/openai.yaml").resolve(),
                    (canonical / "agents/openai.yaml").resolve(),
                )
            else:
                self.assertEqual(
                    (projected / "SKILL.md").read_text(), "stale upstream skill\n"
                )
            if canonical_present:
                for resource in canonical.rglob("*"):
                    if resource.is_file():
                        projection = projected / resource.relative_to(canonical)
                        self.assertEqual(projection.resolve(), resource.resolve())
            found = subprocess.check_output(
                ["find", "hermes/skills", "-name", "SKILL.md"],
                cwd=root, text=True, timeout=10,
            ).splitlines()
            self.assertIn(f"hermes/skills/{skill}/SKILL.md", found)
            self.assertEqual(
                (root / "hermes/skills/other-skill/SKILL.md").read_text(),
                "other skill\n",
            )


class TddExportTest(CodeReviewExportTest):
    skill = "tdd"
