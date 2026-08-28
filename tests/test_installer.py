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
            "commands_archive/2026-retired/retired-command.md": "archived command\n",
            "scripts/nested/tool.py": "print('tool')\n",
            "skills/example/SKILL.md": "# Skill\n",
            "skills/example/scripts/helper.sh": "#!/bin/sh\n",
            "skills/example/scripts/__pycache__/helper.cpython-313.pyc": "compiled\n",
            "skills/example/scripts/.pytest_cache/CACHEDIR.TAG": "cache\n",
            "skills/example/_archived_future/legacy/SKILL.md": "# Nested legacy\n",
            "skills/_archive/legacy/SKILL.md": "# Legacy\n",
            "skills/_archive/2026-08-27-historical-zero-use/README.md": "archive rationale\n",
            "skills/_archived_loose_md/legacy.md": "legacy\n",
            "skills/_archived_loose_md_2026-08-23/legacy.md": "legacy\n",
            "skills_archive/2026-retired/retired-skill/SKILL.md": "archive rationale\n",
            "skills_archive/legacy-pre/packages/retired-legacy/SKILL.md": "legacy\n",
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
                in_archive_container = any(
                    part == "_archive" or part.startswith("_archived_")
                    for part in relative_parts
                )
                excluded_component = {
                    "skills_archive", "commands_archive", "__pycache__", ".pytest_cache"
                }.intersection(relative_parts)
                if source_file.is_file() and not in_archive_container and not excluded_component:
                    installed = target / source_file.relative_to(fixture / ".claude")
                    self.assertTrue(installed.is_file(), installed)
                    self.assertEqual(installed.read_bytes(), source_file.read_bytes())
            for archive_name in (
                "_archive",
                "_archived_loose_md",
                "_archived_loose_md_2026-08-23",
            ):
                self.assertFalse((target / "skills" / archive_name).exists())
            self.assertFalse((target / "skills/example/_archived_future").exists())
            self.assertFalse((target / "skills/example/scripts/__pycache__").exists())
            self.assertFalse((target / "skills/example/scripts/.pytest_cache").exists())
            self.assertFalse((target / "skills_archive").exists())
            self.assertFalse((target / "commands_archive").exists())

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

    def test_merge_migrates_retired_packages_out_of_discovery(self):
        with tempfile.TemporaryDirectory() as directory:
            temp_dir = Path(directory)
            fixture = self.make_fixture(temp_dir)
            target = temp_dir / "claude-home"
            active_skill = target / "skills/retired-skill/SKILL.md"
            active_top_command = target / "commands/retired-command.md"
            active_extended_command = target / "commands/extended-library/retired-command.md"
            for path in (active_skill, active_top_command, active_extended_command):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"installed {path.name}\n", encoding="utf-8")

            result = self.run_installer(
                fixture, target, "--merge", "--migrate-archives"
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertFalse(active_skill.exists())
            self.assertFalse(active_top_command.exists())
            self.assertFalse(active_extended_command.exists())
            self.assertTrue(
                (target / "skills_archive/2026-retired/retired-skill/SKILL.md").is_file()
            )
            self.assertTrue(
                (target / "commands_archive/2026-retired/top-level/retired-command.md").is_file()
            )
            self.assertTrue(
                (
                    target
                    / "commands_archive/2026-retired/extended-library/retired-command.md"
                ).is_file()
            )

    def test_merge_preserves_ambiguous_archived_names_without_explicit_migration(self):
        with tempfile.TemporaryDirectory() as directory:
            temp_dir = Path(directory)
            fixture = self.make_fixture(temp_dir)
            target = temp_dir / "claude-home"
            custom_skill = target / "skills/retired-skill/SKILL.md"
            custom_command = target / "commands/retired-command.md"
            custom_extended = target / "commands/extended-library/retired-command.md"
            for path in (custom_skill, custom_command, custom_extended):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"custom {path.name}\n", encoding="utf-8")

            result = self.run_installer(fixture, target, "--merge")

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            for path in (custom_skill, custom_command, custom_extended):
                self.assertEqual(path.read_text(encoding="utf-8"), f"custom {path.name}\n")
            self.assertIn("requires --migrate-archives", result.stderr + result.stdout)

    def test_archive_migration_requires_merge_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            temp_dir = Path(directory)
            fixture = self.make_fixture(temp_dir)
            target = temp_dir / "claude-home"

            result = self.run_installer(fixture, target, "--migrate-archives")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "--migrate-archives requires --merge", result.stderr + result.stdout
            )

    def test_merge_does_not_treat_archive_category_as_a_skill_name(self):
        with tempfile.TemporaryDirectory() as directory:
            temp_dir = Path(directory)
            fixture = self.make_fixture(temp_dir)
            target = temp_dir / "claude-home"
            active = target / "skills/packages/SKILL.md"
            active.parent.mkdir(parents=True, exist_ok=True)
            active.write_text("active user skill\n", encoding="utf-8")

            result = self.run_installer(fixture, target, "--merge")

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertEqual(active.read_text(encoding="utf-8"), "active user skill\n")
            self.assertFalse(
                (target / "skills_archive/legacy-pre/packages/SKILL.md").exists()
            )

    def test_merge_refuses_to_overwrite_existing_archive_target(self):
        with tempfile.TemporaryDirectory() as directory:
            temp_dir = Path(directory)
            fixture = self.make_fixture(temp_dir)
            target = temp_dir / "claude-home"
            earlier_active = target / "skills/retired-skill/SKILL.md"
            later_active = target / "commands/retired-command.md"
            later_archived = (
                target / "commands_archive/2026-retired/top-level/retired-command.md"
            )
            earlier_active.parent.mkdir(parents=True, exist_ok=True)
            later_active.parent.mkdir(parents=True, exist_ok=True)
            later_archived.parent.mkdir(parents=True, exist_ok=True)
            earlier_active.write_text("earlier active\n", encoding="utf-8")
            later_active.write_text("later active\n", encoding="utf-8")
            later_archived.write_text("existing archive\n", encoding="utf-8")

            result = self.run_installer(
                fixture, target, "--merge", "--migrate-archives"
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Refusing to overwrite existing archive target", result.stderr + result.stdout)
            self.assertEqual(earlier_active.read_text(encoding="utf-8"), "earlier active\n")
            self.assertEqual(later_active.read_text(encoding="utf-8"), "later active\n")
            self.assertEqual(later_archived.read_text(encoding="utf-8"), "existing archive\n")

    def test_merge_treats_dangling_symlinks_as_existing_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            temp_dir = Path(directory)
            fixture = self.make_fixture(temp_dir)
            target = temp_dir / "claude-home"
            active = target / "commands/retired-command.md"
            archived = target / "commands_archive/2026-retired/top-level/retired-command.md"
            active.parent.mkdir(parents=True, exist_ok=True)
            archived.parent.mkdir(parents=True, exist_ok=True)
            active.write_text("active\n", encoding="utf-8")
            archived.symlink_to("missing-command.md")

            result = self.run_installer(
                fixture, target, "--merge", "--migrate-archives"
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(active.read_text(encoding="utf-8"), "active\n")
            self.assertTrue(archived.is_symlink())

    def test_merge_migrates_a_dangling_active_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            temp_dir = Path(directory)
            fixture = self.make_fixture(temp_dir)
            target = temp_dir / "claude-home"
            active = target / "skills/retired-skill"
            archived = target / "skills_archive/2026-retired/retired-skill"
            active.parent.mkdir(parents=True, exist_ok=True)
            active.symlink_to("missing-skill")

            result = self.run_installer(
                fixture, target, "--merge", "--migrate-archives"
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertFalse(active.is_symlink())
            self.assertTrue(archived.is_symlink())

    def test_merge_validates_all_archive_parents_before_moving(self):
        with tempfile.TemporaryDirectory() as directory:
            temp_dir = Path(directory)
            fixture = self.make_fixture(temp_dir)
            target = temp_dir / "claude-home"
            earlier_active = target / "skills/retired-skill/SKILL.md"
            later_active = target / "commands/retired-command.md"
            blocked_parent = target / "commands_archive/2026-retired"
            earlier_active.parent.mkdir(parents=True, exist_ok=True)
            later_active.parent.mkdir(parents=True, exist_ok=True)
            blocked_parent.parent.mkdir(parents=True, exist_ok=True)
            earlier_active.write_text("earlier active\n", encoding="utf-8")
            later_active.write_text("later active\n", encoding="utf-8")
            blocked_parent.write_text("not a directory\n", encoding="utf-8")

            result = self.run_installer(
                fixture, target, "--merge", "--migrate-archives"
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(earlier_active.read_text(encoding="utf-8"), "earlier active\n")
            self.assertEqual(later_active.read_text(encoding="utf-8"), "later active\n")

    def test_merge_no_clobber_detects_destination_created_after_preflight(self):
        with tempfile.TemporaryDirectory() as directory:
            temp_dir = Path(directory)
            fixture = self.make_fixture(temp_dir)
            target = temp_dir / "claude-home"
            active = target / "skills/retired-skill/SKILL.md"
            active.parent.mkdir(parents=True, exist_ok=True)
            active.write_text("active\n", encoding="utf-8")
            fake_bin = temp_dir / "fake-bin"
            fake_bin.mkdir()
            fake_move = fake_bin / "mv"
            fake_move.write_text(
                "#!/bin/sh\n"
                "if [ \"$1\" = -n ] && [ ! -e \"$3\" ]; then\n"
                "  echo concurrent-writer > \"$3\"\n"
                "fi\n"
                "exec /bin/mv \"$@\"\n",
                encoding="utf-8",
            )
            fake_move.chmod(0o755)

            result = self.run_installer(
                fixture,
                target,
                "--merge",
                "--migrate-archives",
                extra_environment={"PATH": f"{fake_bin}:{os.environ['PATH']}"},
            )

            archived = target / "skills_archive/2026-retired/retired-skill"
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(active.read_text(encoding="utf-8"), "active\n")
            self.assertEqual(archived.read_text(encoding="utf-8"), "concurrent-writer\n")

    def test_merge_rolls_back_when_competing_directory_nests_package(self):
        with tempfile.TemporaryDirectory() as directory:
            temp_dir = Path(directory)
            fixture = self.make_fixture(temp_dir)
            target = temp_dir / "claude-home"
            active = target / "skills/retired-skill/SKILL.md"
            active.parent.mkdir(parents=True, exist_ok=True)
            active.write_text("active\n", encoding="utf-8")
            fake_bin = temp_dir / "fake-bin"
            fake_bin.mkdir()
            fake_move = fake_bin / "mv"
            fake_move.write_text(
                "#!/bin/sh\n"
                "if [ \"$1\" = -n ] && [ ! -e \"$3\" ]; then\n"
                "  mkdir \"$3\"\n"
                "  echo competing-skill > \"$3/SKILL.md\"\n"
                "fi\n"
                "exec /bin/mv \"$@\"\n",
                encoding="utf-8",
            )
            fake_move.chmod(0o755)

            result = self.run_installer(
                fixture,
                target,
                "--merge",
                "--migrate-archives",
                extra_environment={"PATH": f"{fake_bin}:{os.environ['PATH']}"},
            )

            archived = target / "skills_archive/2026-retired/retired-skill"
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(active.read_text(encoding="utf-8"), "active\n")
            self.assertTrue(archived.is_dir())
            self.assertEqual(
                (archived / "SKILL.md").read_text(encoding="utf-8"),
                "competing-skill\n",
            )
            self.assertFalse((archived / "retired-skill").exists())

    def test_merge_releases_lock_when_interrupted(self):
        with tempfile.TemporaryDirectory() as directory:
            temp_dir = Path(directory)
            fixture = self.make_fixture(temp_dir)
            target = temp_dir / "claude-home"
            active = target / "skills/retired-skill/SKILL.md"
            active.parent.mkdir(parents=True, exist_ok=True)
            active.write_text("active\n", encoding="utf-8")
            fake_bin = temp_dir / "fake-bin"
            fake_bin.mkdir()
            fake_move = fake_bin / "mv"
            fake_move.write_text(
                "#!/bin/sh\n"
                "kill -TERM \"$PPID\"\n"
                "sleep 1\n"
                "exit 1\n",
                encoding="utf-8",
            )
            fake_move.chmod(0o755)

            result = self.run_installer(
                fixture,
                target,
                "--merge",
                "--migrate-archives",
                extra_environment={"PATH": f"{fake_bin}:{os.environ['PATH']}"},
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((target / ".archive-migration.lock").exists())

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
