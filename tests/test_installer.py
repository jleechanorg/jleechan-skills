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
        exported_script = fixture / "scripts" / "integrate.sh"
        exported_script.parent.mkdir(parents=True, exist_ok=True)
        exported_script.write_text("#!/bin/sh\necho installed-integrate\n", encoding="utf-8")
        exported_script.chmod(0o755)
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
            installed_integrate = target / "scripts/integrate.sh"
            self.assertTrue(installed_integrate.is_file())
            self.assertEqual(installed_integrate.read_bytes(), (fixture / "scripts/integrate.sh").read_bytes())
            self.assertTrue(os.access(installed_integrate, os.X_OK))

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

    def test_history_helper_runs_outside_source_checkout_after_install(self):
        with tempfile.TemporaryDirectory() as directory:
            temp_dir = Path(directory)
            fixture = self.make_fixture(temp_dir)
            shutil.copy2(REPO_ROOT / "scripts/history_search.py", fixture / "scripts/history_search.py")
            target = temp_dir / "claude-home"
            result = self.run_installer(fixture, target)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            helper = target / "scripts/history_search.py"
            self.assertTrue(helper.is_file())
            result = subprocess.run(
                ["python3", str(helper), "--help"], cwd=temp_dir,
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("--codex-home", result.stdout)

    def test_history_helper_collisions_fail_before_component_writes(self):
        for kind in ("file", "helper_symlink", "scripts_symlink"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                temp_dir = Path(directory)
                fixture = self.make_fixture(temp_dir)
                (fixture / "scripts/history_search.py").write_text(
                    "print('new helper')\n"
                )
                target = temp_dir / "claude-home"
                target.mkdir()
                external = temp_dir / "external"
                external.mkdir()
                original = external / "history_search.py"
                original.write_text("user-owned helper\n")
                scripts = target / "scripts"
                if kind == "scripts_symlink":
                    scripts.symlink_to(external, target_is_directory=True)
                else:
                    scripts.mkdir()
                    if kind == "helper_symlink":
                        (scripts / "history_search.py").symlink_to(original)
                    else:
                        (scripts / "history_search.py").write_text(
                            "user-owned helper\n"
                        )

                result = self.run_installer(fixture, target, "--merge")

                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn(
                    "history helper", (result.stderr + result.stdout).lower()
                )
                self.assertEqual(
                    (scripts / "history_search.py").read_text(), "user-owned helper\n"
                )
                self.assertEqual(original.read_text(), "user-owned helper\n")
                self.assertFalse((target / "agents/nested/agent.md").exists())
                if kind == "helper_symlink":
                    self.assertTrue((scripts / "history_search.py").is_symlink())
                if kind == "scripts_symlink":
                    self.assertTrue(scripts.is_symlink())
                    self.assertFalse((external / "nested/tool.py").exists())

    def test_history_helper_source_upgrade_succeeds_on_merge_and_rejects_local_edits(self):
        with tempfile.TemporaryDirectory() as directory:
            temp_dir = Path(directory)
            fixture = self.make_fixture(temp_dir)
            source = fixture / "scripts/history_search.py"
            source.write_text("print('version one')\n")
            target = temp_dir / "claude-home"
            installed = self.run_installer(fixture, target)
            self.assertEqual(
                installed.returncode, 0, installed.stdout + installed.stderr
            )
            self.assertEqual(
                (target / "scripts/history_search.py").read_text(),
                "print('version one')\n",
            )
            identical = self.run_installer(fixture, target, "--merge")
            self.assertEqual(
                identical.returncode, 0, identical.stdout + identical.stderr
            )

            # Upgraded source should safely upgrade on --merge
            source.write_text("print('version two')\n")
            upgraded = self.run_installer(fixture, target, "--merge")
            self.assertEqual(
                upgraded.returncode, 0, upgraded.stdout + upgraded.stderr
            )
            self.assertEqual(
                (target / "scripts/history_search.py").read_text(),
                "print('version two')\n",
            )

            # Local modifications must be protected from overwrite
            (target / "scripts/history_search.py").write_text("print('locally modified')\n")
            source.write_text("print('version three')\n")
            refused = self.run_installer(fixture, target, "--merge")
            self.assertNotEqual(refused.returncode, 0)
            self.assertIn("history helper", (refused.stderr + refused.stdout).lower())
            self.assertEqual(
                (target / "scripts/history_search.py").read_text(),
                "print('locally modified')\n",
            )

            # --backup deliberately backs up and replaces the entire target
            backup_run = self.run_installer(fixture, target, "--backup")
            self.assertEqual(backup_run.returncode, 0, backup_run.stdout + backup_run.stderr)
            self.assertEqual(
                (target / "scripts/history_search.py").read_text(), source.read_text()
            )
            backups = list(temp_dir.glob("claude-home.backup-*"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(
                (backups[0] / "scripts/history_search.py").read_text(),
                "print('locally modified')\n",
            )

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

    def test_failed_merge_does_not_migrate_retired_packages(self):
        with tempfile.TemporaryDirectory() as directory:
            temp_dir = Path(directory)
            fixture = self.make_fixture(temp_dir)
            target = temp_dir / "claude-home"
            active = target / "skills/retired-skill/SKILL.md"
            active.parent.mkdir(parents=True, exist_ok=True)
            active.write_text("active\n", encoding="utf-8")
            fake_bin = temp_dir / "fake-bin"
            fake_bin.mkdir()
            fake_copy = fake_bin / "cp"
            fake_copy.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
            fake_copy.chmod(0o755)

            result = self.run_installer(
                fixture,
                target,
                "--merge",
                "--migrate-archives",
                extra_environment={"PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}"},
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(active.read_text(encoding="utf-8"), "active\n")
            self.assertFalse(
                (target / "skills_archive/2026-retired/retired-skill").exists()
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

    def test_merge_migrates_nested_archived_skill_package(self):
        with tempfile.TemporaryDirectory() as directory:
            temp_dir = Path(directory)
            fixture = self.make_fixture(temp_dir)
            target = temp_dir / "claude-home"
            active = target / "skills/retired-legacy/SKILL.md"
            active.parent.mkdir(parents=True, exist_ok=True)
            active.write_text("active legacy skill\n", encoding="utf-8")

            result = self.run_installer(
                fixture, target, "--merge", "--migrate-archives"
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertFalse(active.exists())
            archived = (
                target
                / "skills_archive/legacy-pre/packages/retired-legacy/SKILL.md"
            )
            self.assertEqual(
                archived.read_text(encoding="utf-8"), "active legacy skill\n"
            )

    def test_merge_rejects_duplicate_archive_mappings_before_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            temp_dir = Path(directory)
            fixture = self.make_fixture(temp_dir)
            duplicate = (
                fixture
                / ".claude/skills_archive/other-retired/packages/retired-skill/SKILL.md"
            )
            duplicate.parent.mkdir(parents=True, exist_ok=True)
            duplicate.write_text("different archived skill\n", encoding="utf-8")
            target = temp_dir / "claude-home"
            active = target / "skills/retired-skill/SKILL.md"
            managed_file = target / "commands/command.md"
            active.parent.mkdir(parents=True, exist_ok=True)
            managed_file.parent.mkdir(parents=True, exist_ok=True)
            active.write_text("active skill\n", encoding="utf-8")
            managed_file.write_text("outdated command\n", encoding="utf-8")

            result = self.run_installer(
                fixture, target, "--merge", "--migrate-archives"
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "Ambiguous archive migration for active path",
                result.stderr + result.stdout,
            )
            self.assertEqual(active.read_text(encoding="utf-8"), "active skill\n")
            self.assertEqual(
                managed_file.read_text(encoding="utf-8"), "outdated command\n"
            )
            self.assertFalse((target / "skills_archive/2026-retired").exists())
            self.assertFalse((target / "skills_archive/other-retired").exists())

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
            managed_file = target / "commands/command.md"
            managed_file.parent.mkdir(parents=True, exist_ok=True)
            managed_file.write_text("outdated command\n", encoding="utf-8")

            result = self.run_installer(
                fixture, target, "--merge", "--migrate-archives"
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Refusing to overwrite existing archive target", result.stderr + result.stdout)
            self.assertEqual(earlier_active.read_text(encoding="utf-8"), "earlier active\n")
            self.assertEqual(later_active.read_text(encoding="utf-8"), "later active\n")
            self.assertEqual(later_archived.read_text(encoding="utf-8"), "existing archive\n")
            self.assertEqual(
                managed_file.read_text(encoding="utf-8"), "outdated command\n"
            )

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

    def test_merge_preserves_symlinked_skill_directory_and_does_not_write_target(self):
        with tempfile.TemporaryDirectory() as directory:
            temp_dir = Path(directory)
            fixture = self.make_fixture(temp_dir)
            target = temp_dir / "claude-home"
            target.mkdir()

            external_repo = temp_dir / "external-repo" / "dark-factory"
            external_repo.mkdir(parents=True)
            external_skill = external_repo / "SKILL.md"
            external_bytes = b"# External Dark Factory Skill\n"
            external_skill.write_bytes(external_bytes)

            skills_target = target / "skills"
            skills_target.mkdir()
            linked_skill = skills_target / "dark-factory"
            linked_skill.symlink_to(external_repo)

            fixture_dark = fixture / ".claude/skills/dark-factory"
            fixture_dark.mkdir(parents=True)
            (fixture_dark / "SKILL.md").write_text("# Repo Managed Dark Factory\n")

            # Also check source symlink entries copy appropriately
            source_symlink = fixture / ".claude/skills/example/source-symlink.txt"
            source_symlink_target = fixture / ".claude/skills/example/SKILL.md"
            source_symlink.symlink_to(source_symlink_target.name)

            result = self.run_installer(fixture, target, "--merge")

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            # Topology: must remain the exact same symlink pointing to external_repo
            self.assertTrue(linked_skill.is_symlink())
            self.assertEqual(os.readlink(linked_skill), str(external_repo))
            # External target must not be written
            self.assertEqual(external_skill.read_bytes(), external_bytes)
            # Regular skill still updated appropriately
            self.assertTrue((skills_target / "example/SKILL.md").is_file())
            self.assertEqual((skills_target / "example/SKILL.md").read_text(), "# Skill\n")
            installed_symlink = skills_target / "example/source-symlink.txt"
            self.assertTrue(installed_symlink.is_symlink())
            # Meaningful log assertion: external owner link skip and preserved count are logged
            self.assertIn(f"Preserving externally owned skills link ({linked_skill}); skipping {linked_skill / 'SKILL.md'}", result.stdout)
            self.assertIn("preserved 1 externally owned path", result.stdout)

    def test_merge_preserves_component_root_symlink_and_does_not_write_target(self):
        with tempfile.TemporaryDirectory() as directory:
            temp_dir = Path(directory)
            fixture = self.make_fixture(temp_dir)
            target = temp_dir / "claude-home"
            target.mkdir()

            external_skills = temp_dir / "external-skills"
            external_skills.mkdir(parents=True)
            external_skill = external_skills / "example/SKILL.md"
            external_skill.parent.mkdir(parents=True)
            external_bytes = b"# Separately Owned Skill Content\n"
            external_skill.write_bytes(external_bytes)

            skills_target = target / "skills"
            skills_target.symlink_to(external_skills)

            result = self.run_installer(fixture, target, "--merge")

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            # Topology: skills_target must remain the exact symlink pointing to external_skills
            self.assertTrue(skills_target.is_symlink())
            self.assertEqual(os.readlink(skills_target), str(external_skills))
            # External target must not be written or overwritten
            self.assertEqual(external_skill.read_bytes(), external_bytes)
            # Other components (e.g. commands/agents) still update
            self.assertTrue((target / "commands").exists())
            self.assertIn("Preserving externally owned skills directory link", result.stdout)

    def test_installer_refuses_unsafe_receipt_symlink_even_when_helper_is_identical(self):
        with tempfile.TemporaryDirectory() as directory:
            temp_dir = Path(directory)
            fixture = self.make_fixture(temp_dir)
            source_helper = fixture / "scripts/history_search.py"
            source_helper.write_text("print('identical helper')\n")

            target = temp_dir / "claude-home"
            target.mkdir()
            scripts = target / "scripts"
            scripts.mkdir()
            (scripts / "history_search.py").write_text("print('identical helper')\n")

            external = temp_dir / "external"
            external.mkdir()
            protected = external / "protected.txt"
            protected.write_text("unrelated protected data\n")

            receipt = scripts / ".history_search.py.sha256"
            receipt.symlink_to(protected)

            result = self.run_installer(fixture, target, "--merge")
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(protected.read_text(), "unrelated protected data\n")
            self.assertFalse((target / "agents/nested/agent.md").exists())

    def test_installer_rejects_unowned_helper_matching_unrelated_git_blob(self):
        with tempfile.TemporaryDirectory() as directory:
            temp_dir = Path(directory)
            fixture = self.make_fixture(temp_dir)
            source_helper = fixture / "scripts/history_search.py"
            source_helper.write_text("print('new helper')\n")

            # Initialize git in fixture and commit an unrelated file with specific bytes
            env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
            subprocess.run(["git", "init"], cwd=fixture, env=env, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@test.local"], cwd=fixture, env=env, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=fixture, env=env, check=True, capture_output=True)
            (fixture / "unrelated.txt").write_text("user-owned unrelated repository bytes\n")
            subprocess.run(["git", "add", "."], cwd=fixture, env=env, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=fixture, env=env, check=True, capture_output=True)

            target = temp_dir / "claude-home"
            target.mkdir()
            scripts = target / "scripts"
            scripts.mkdir()
            # Destination has the bytes of unrelated.txt, not history_search.py
            (scripts / "history_search.py").write_text("user-owned unrelated repository bytes\n")

            result = self.run_installer(fixture, target, "--merge")
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(
                (scripts / "history_search.py").read_text(),
                "user-owned unrelated repository bytes\n",
            )
            self.assertFalse((target / "agents/nested/agent.md").exists())

    def test_installer_git_worktree_source_allows_legitimate_owned_history_upgrade(self):
        with tempfile.TemporaryDirectory() as directory:
            temp_dir = Path(directory)
            main_repo = temp_dir / "main_repo"
            main_repo.mkdir()
            fixture = self.make_fixture(main_repo)
            source_helper = fixture / "scripts/history_search.py"
            source_helper.write_text("print('version 1')\n")

            env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
            subprocess.run(["git", "init"], cwd=fixture, env=env, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@test.local"], cwd=fixture, env=env, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=fixture, env=env, check=True, capture_output=True)
            subprocess.run(["git", "add", "."], cwd=fixture, env=env, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "v1"], cwd=fixture, env=env, check=True, capture_output=True)

            # Create a git worktree from main_repo
            worktree_dir = temp_dir / "worktree"
            subprocess.run(["git", "worktree", "add", str(worktree_dir), "-b", "feat"], cwd=fixture, env=env, check=True, capture_output=True)

            # In worktree, .git is a file
            self.assertTrue((worktree_dir / ".git").is_file())

            # Update history_search.py in worktree to version 2
            (worktree_dir / "scripts/history_search.py").write_text("print('version 2')\n")

            # Target has version 1 without receipt
            target = temp_dir / "claude-home"
            target.mkdir()
            scripts = target / "scripts"
            scripts.mkdir()
            (scripts / "history_search.py").write_text("print('version 1')\n")

            # Running installer from worktree should recognize version 1 as historical and upgrade
            result = self.run_installer(worktree_dir, target, "--merge")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(
                (scripts / "history_search.py").read_text(),
                "print('version 2')\n",
            )


if __name__ == "__main__":
    unittest.main()
