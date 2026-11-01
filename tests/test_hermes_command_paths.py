"""Hermes discovery and real recursive-installer path regressions."""

import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMMANDS = ("commands/hermes.md", "commands/extended-library/hermes.md")
SKILL = "skills/hermes/SKILL.md"


class HermesCommandPathsTest(unittest.TestCase):
    def assert_commands(self, home):
        for relative in COMMANDS:
            with self.subTest(command=relative):
                path = home / relative
                self.assertTrue(path.is_file(), f"missing discoverable command: {relative}")
                text = path.read_text()
                links = re.findall(r"\]\(([^)]+/hermes/SKILL\.md)\)", text)
                self.assertEqual(1, len(links))
                self.assertEqual((home / SKILL).resolve(), (path.parent / links[0]).resolve())
                self.assertTrue((path.parent / links[0]).is_file())
                self.assertIn("$ARGUMENTS", text)
                self.assertNotIn("localhost:", text)
                self.assertNotIn("curl ", text)
                self.assertLessEqual(len(text.splitlines()), 15)

    def test_repository_discovery_and_paths(self):
        self.assert_commands(ROOT / ".claude")

    def test_real_installer_replaces_both_legacy_entries(self):
        # Exercise only real recursive-copy layout, not CLI safety, backups,
        # selective deployment, or live runtime command discovery.
        with tempfile.TemporaryDirectory(prefix="hermes paths ") as temporary:
            root = Path(temporary)
            source, home = root / "source", root / "custom claude home"
            source.mkdir()
            shutil.copy2(ROOT / "install-claude-commands.sh", source)
            for relative in (*COMMANDS, SKILL):
                origin = ROOT / ".claude" / relative
                if origin.is_file():
                    target = source / ".claude" / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(origin, target)
            for relative in COMMANDS:
                path = home / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("curl http://localhost:8643/v1/chat/completions\n")
            unrelated = home / "commands/unrelated.md"
            unrelated.write_text("preserve this local command\n")
            result = subprocess.run(
                ["bash", "-c", 'source "$1"; install_commands; install_skills',
                 "hermes-test", str(source / "install-claude-commands.sh")],
                env={**os.environ, "CLAUDE_HOME": str(home)},
                capture_output=True, text=True,
            )
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assert_commands(home)
            self.assertEqual("preserve this local command\n", unrelated.read_text())
            self.assertEqual((ROOT / ".claude" / SKILL).read_bytes(), (home / SKILL).read_bytes())

    def test_scoped_install_accounts_for_every_discoverable_entry(self):
        skill = " ".join((ROOT / ".claude" / SKILL).read_text().split())
        for relative in (*COMMANDS, SKILL):
            self.assertIn(f"`{relative}`", skill)
        self.assertIn("Do not flatten", skill)
        self.assertIn("outside the discoverable command tree", skill)
        self.assertIn("both `/hermes` and `/extended-library:hermes`", skill)
        for requirement in (
            "including symlinks and divergent content",
            "Reconcile differences first",
            "retain recoverable originals",
            "Do not overwrite Dot, Linux, or other installed packages",
            "preserve unrelated local changes",
            "report installation blocked",
        ):
            self.assertIn(requirement, skill)


if __name__ == "__main__":
    unittest.main()
