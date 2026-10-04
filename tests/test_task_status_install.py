"""Verify the task-status package through the real installer in a temporary home."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TaskStatusInstallTest(unittest.TestCase):
    def test_selected_package_and_command_install_without_other_skills(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            shutil.copy2(ROOT / "install-claude-commands.sh", source)
            skill = Path(".claude/skills/task-status/SKILL.md")
            command = Path(".claude/commands/task-status.md")
            for relative in (skill, command):
                destination = source / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / relative, destination)
            target = root / "home"
            result = subprocess.run(
                ["bash", str(source / "install-claude-commands.sh")],
                env=os.environ | {"CLAUDE_HOME": str(target)},
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for relative in (skill, command):
                self.assertEqual(
                    (target / relative.relative_to(".claude")).read_bytes(),
                    (ROOT / relative).read_bytes(),
                )
            self.assertEqual([p.name for p in (target / "skills").iterdir()], ["task-status"])
