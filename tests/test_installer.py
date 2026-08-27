"""Public integration contracts for install-claude-commands.sh."""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALLER = REPO_ROOT / "install-claude-commands.sh"


class InstallerIntegrationTest(unittest.TestCase):
    def make_fixture(self, temp_dir: Path) -> Path:
        fixture = temp_dir / "fixture"
        fixture.mkdir()
        shutil.copy2(INSTALLER, fixture / INSTALLER.name)
        source = fixture / ".claude"
        files = {
            "agents/nested/agent.md": "agent\n",
            "commands/command.md": "command\n",
            "commands/nested/helper.sh": "#!/bin/sh\n",
            "scripts/nested/tool.py": "print('tool')\n",
            "skills/example/SKILL.md": "# Skill\n",
            "skills/example/scripts/helper.sh": "#!/bin/sh\n",
            "skills/example/scripts/__pycache__/helper.cpython-313.pyc": "compiled\n",
            "skills/example/scripts/.pytest_cache/CACHEDIR.TAG": "cache\n",
            "skills/_archive/legacy/SKILL.md": "# Legacy\n",
            "skills/_archived_loose_md/legacy.md": "legacy\n",
            "skills/_archived_loose_md_2026-08-23/legacy.md": "legacy\n",
        }
        for relative, content in files.items():
            path = source / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        return fixture

    def run_installer(
        self, fixture: Path, target: Path, *args: str, extra_environment: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        environment = os.environ | {"CLAUDE_HOME": str(target)}
        if extra_environment:
            environment |= extra_environment
        return subprocess.run(
            ["bash", str(fixture / INSTALLER.name), *args],
            cwd=fixture,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_clean_install_copies_every_source_file_and_validates_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            temp_dir = Path(directory)
            fixture = self.make_fixture(temp_dir)
            target = temp_dir / "claude-home"

            result = self.run_installer(fixture, target)

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("Source-derived manifest validation passed", result.stdout)
            self.assertIn("Start Claude Code to use the installed commands and skills.", result.stdout)
            self.assertNotIn("/help, /list, /execute", result.stdout)
            self.assertNotIn("claude-bot-commands/README.md", result.stdout)
            self.assertNotIn("Checking prerequisites", result.stdout)
            for source_file in (fixture / ".claude").rglob("*"):
                relative_parts = source_file.relative_to(fixture / ".claude").parts
                if source_file.is_file() and not {
                    "_archive",
                    "_archived_loose_md",
                    "_archived_loose_md_2026-08-23",
                    "__pycache__",
                    ".pytest_cache",
                }.intersection(relative_parts):
                    installed = target / source_file.relative_to(fixture / ".claude")
                    self.assertTrue(installed.is_file(), installed)
                    self.assertEqual(installed.read_bytes(), source_file.read_bytes())
            for archive_name in (
                "_archive",
                "_archived_loose_md",
                "_archived_loose_md_2026-08-23",
            ):
                self.assertFalse((target / "skills" / archive_name).exists())
            self.assertFalse((target / "skills/example/scripts/__pycache__").exists())
            self.assertFalse((target / "skills/example/scripts/.pytest_cache").exists())

    def test_superpowers_quick_installs_with_bundled_subskills(self):
        with tempfile.TemporaryDirectory() as directory:
            temp_dir = Path(directory)
            fixture = self.make_fixture(temp_dir)
            relative_files = (
                Path("commands/superpowers-quick.md"),
                Path("skills/superpowers-quick/SKILL.md"),
                Path("skills/superpowers-brainstorming/SKILL.md"),
                Path("skills/superpowers-writing-plans/SKILL.md"),
            )
            for relative in relative_files:
                source = REPO_ROOT / ".claude" / relative
                destination = fixture / ".claude" / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)

            target = temp_dir / "claude-home"
            result = self.run_installer(fixture, target)

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            quick = (target / "skills/superpowers-quick/SKILL.md").read_text()
            for dependency in ("superpowers-brainstorming", "superpowers-writing-plans"):
                installed_dependency = target / f"skills/{dependency}/SKILL.md"
                self.assertTrue(installed_dependency.is_file(), installed_dependency)
                self.assertIn(f"~/.claude/skills/{dependency}/SKILL.md", quick)

    def test_boundary_commands_resolve_skills_under_nondefault_claude_home(self):
        with tempfile.TemporaryDirectory() as directory:
            temp_dir = Path(directory)
            fixture = self.make_fixture(temp_dir)
            skill_names = (
                "root-cause-first",
                "llm-first",
                "backend-first",
                "end2end-testing",
            )
            for name in skill_names:
                for relative in (
                    Path(f"commands/{name}.md"),
                    Path(f"skills/{name}/SKILL.md"),
                ):
                    source = REPO_ROOT / ".claude" / relative
                    destination = fixture / ".claude" / relative
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, destination)

            target = temp_dir / "nondefault-claude-home"
            result = self.run_installer(fixture, target)

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            home_expression = "${CLAUDE_HOME:-$HOME/.claude}"
            for name in skill_names:
                with self.subTest(command=name):
                    command = (target / f"commands/{name}.md").read_text(
                        encoding="utf-8"
                    )
                    self.assertIn(home_expression, command)
                    resolved = command.replace(home_expression, str(target))
                    installed_skill = target / f"skills/{name}/SKILL.md"
                    self.assertIn(str(installed_skill), resolved)
                    self.assertTrue(installed_skill.is_file(), installed_skill)

    def test_second_default_run_refuses_to_overwrite_an_existing_install(self):
        with tempfile.TemporaryDirectory() as directory:
            temp_dir = Path(directory)
            fixture = self.make_fixture(temp_dir)
            target = temp_dir / "claude-home"
            first = self.run_installer(fixture, target)
            original = (target / "commands/command.md").read_text(encoding="utf-8")

            second = self.run_installer(fixture, target)

            self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
            self.assertNotEqual(second.returncode, 0)
            self.assertIn("Refusing to modify nonempty target", second.stderr + second.stdout)
            self.assertEqual((target / "commands/command.md").read_text(encoding="utf-8"), original)

    def test_nonempty_target_requires_explicit_backup_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            temp_dir = Path(directory)
            fixture = self.make_fixture(temp_dir)
            target = temp_dir / "claude-home"
            target.mkdir()
            (target / "user-file.txt").write_text("preserve me", encoding="utf-8")

            refused = self.run_installer(fixture, target)
            installed = self.run_installer(fixture, target, "--backup")

            self.assertNotEqual(refused.returncode, 0)
            self.assertEqual(installed.returncode, 0, installed.stderr + installed.stdout)
            backups = list(temp_dir.glob("claude-home.backup-*"))
            self.assertEqual(len(backups), 1)
            self.assertEqual((backups[0] / "user-file.txt").read_text(encoding="utf-8"), "preserve me")
            self.assertTrue((target / "skills/example/SKILL.md").is_file())
            self.assertFalse((target / "skills/_archive").exists())

    def test_backup_mode_stages_and_replaces_an_empty_target(self):
        with tempfile.TemporaryDirectory() as directory:
            temp_dir = Path(directory)
            fixture = self.make_fixture(temp_dir)
            target = temp_dir / "claude-home"
            target.mkdir()

            result = self.run_installer(fixture, target, "--backup")

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertTrue((target / "commands/command.md").is_file())
            backups = list(temp_dir.glob("claude-home.backup-*"))
            self.assertEqual(len(backups), 1)
            self.assertFalse(list(temp_dir.glob("claude-home.staging-*")))

    def test_merge_updates_managed_files_and_retains_unrelated_files(self):
        with tempfile.TemporaryDirectory() as directory:
            temp_dir = Path(directory)
            fixture = self.make_fixture(temp_dir)
            target = temp_dir / "claude-home"
            target.mkdir()
            managed_file = target / "commands/command.md"
            managed_file.parent.mkdir()
            managed_file.write_text("outdated command\n", encoding="utf-8")
            user_file = target / "user-settings.txt"
            user_file.write_text("retain me\n", encoding="utf-8")

            result = self.run_installer(fixture, target, "--merge")

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertEqual(managed_file.read_text(encoding="utf-8"), "command\n")
            self.assertEqual(user_file.read_text(encoding="utf-8"), "retain me\n")
            self.assertFalse((target / "skills/_archive").exists())

    def test_backup_failure_preserves_original_target(self):
        with tempfile.TemporaryDirectory() as directory:
            temp_dir = Path(directory)
            fixture = self.make_fixture(temp_dir)
            target = temp_dir / "claude-home"
            target.mkdir()
            original = target / "user-file.txt"
            original.write_text("preserve me\n", encoding="utf-8")
            fake_bin = temp_dir / "fake-bin"
            fake_bin.mkdir()
            fake_copy = fake_bin / "cp"
            fake_copy.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
            fake_copy.chmod(0o755)

            result = self.run_installer(
                fixture,
                target,
                "--backup",
                extra_environment={"PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}"},
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(original.read_text(encoding="utf-8"), "preserve me\n")
            self.assertFalse(list(temp_dir.glob("claude-home.backup-*")))
            self.assertFalse(list(temp_dir.glob("claude-home.staging-*")))


if __name__ == "__main__":
    unittest.main()
