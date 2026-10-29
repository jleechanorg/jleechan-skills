"""Public integration contracts for install-claude-commands.sh."""

import json
import os
import re
import shutil
import stat
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
            "commands/newbranch.py": "#!/usr/bin/env python3\nprint('newbranch v2')\n",
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
        # Fixtures model the full library; profile tests pass their own selection.
        if not {"--all", "--profile", "--portable", "-h", "--help"}.intersection(args):
            args = (*args, "--all")
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
                Path("commands/sq.md"),
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
            for relative in relative_files:
                self.assertEqual(
                    (target / relative).read_bytes(),
                    (REPO_ROOT / ".claude" / relative).read_bytes(),
                )
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

    def install_then_edit_locally(self, temp_dir: Path, fixture: Path) -> Path:
        target = temp_dir / "claude-home"
        first = self.run_installer(fixture, target)
        self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
        (target / "skills/example/SKILL.md").write_text("# Local operator rules\n", encoding="utf-8")
        (target / "commands/command.md").write_text("local command\n", encoding="utf-8")
        return target

    def test_merge_backs_up_only_changed_colliding_paths_before_overwriting(self):
        with tempfile.TemporaryDirectory() as directory:
            temp_dir = Path(directory)
            fixture = self.make_fixture(temp_dir)
            target = self.install_then_edit_locally(temp_dir, fixture)
            (target / "skills/local-only/SKILL.md").parent.mkdir()
            (target / "skills/local-only/SKILL.md").write_text("mine\n", encoding="utf-8")

            result = self.run_installer(fixture, target, "--merge")

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            backups = list(temp_dir.glob("claude-home.merge-backup-*"))
            self.assertEqual(len(backups), 1, backups)
            self.assertIn(str(backups[0]), result.stdout)
            self.assertEqual(
                (backups[0] / "skills/example/SKILL.md").read_text(encoding="utf-8"),
                "# Local operator rules\n",
            )
            self.assertEqual(
                (backups[0] / "commands/command.md").read_text(encoding="utf-8"), "local command\n"
            )
            backed_up = sorted(
                str(path.relative_to(backups[0])) for path in backups[0].rglob("*") if path.is_file()
            )
            self.assertEqual(backed_up, ["commands/command.md", "skills/example/SKILL.md"])
            self.assertEqual((target / "skills/example/SKILL.md").read_text(encoding="utf-8"), "# Skill\n")
            self.assertEqual((target / "skills/local-only/SKILL.md").read_text(encoding="utf-8"), "mine\n")

    def test_merge_without_changes_writes_no_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            temp_dir = Path(directory)
            fixture = self.make_fixture(temp_dir)
            target = temp_dir / "claude-home"
            self.assertEqual(self.run_installer(fixture, target).returncode, 0)

            result = self.run_installer(fixture, target, "--merge")

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("no merge backup written", result.stdout)
            self.assertFalse(list(temp_dir.glob("claude-home.merge-backup-*")))

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root bypasses directory permissions")
    def test_merge_fails_closed_when_backup_cannot_be_written(self):
        with tempfile.TemporaryDirectory() as directory:
            temp_dir = Path(directory)
            fixture = self.make_fixture(temp_dir)
            parent = temp_dir / "locked"
            parent.mkdir()
            target = self.install_then_edit_locally(parent, fixture)
            parent.chmod(0o555)
            try:
                result = self.run_installer(fixture, target, "--merge")
            finally:
                parent.chmod(0o755)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Cannot create merge backup directory", result.stderr + result.stdout)
            self.assertEqual(
                (target / "skills/example/SKILL.md").read_text(encoding="utf-8"), "# Local operator rules\n"
            )
            self.assertEqual((target / "commands/command.md").read_text(encoding="utf-8"), "local command\n")

    def test_backup_mode_stays_outside_target_with_trailing_slash_home(self):
        for suffix in ("/", "//"):
            with self.subTest(suffix), tempfile.TemporaryDirectory() as directory:
                temp_dir = Path(directory)
                fixture = self.make_fixture(temp_dir)
                target = temp_dir / "claude-home"
                target.mkdir()
                (target / "local.txt").write_text("keep\n", encoding="utf-8")

                result = self.run_installer(
                    fixture, target, "--backup", extra_environment={"CLAUDE_HOME": f"{target}{suffix}"}
                )

                self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
                self.assertTrue((target / "commands/command.md").is_file())
                self.assertFalse(list(target.glob(".backup-*")) + list(target.glob(".staging.*")))
                backups = list(temp_dir.glob("claude-home.backup-*"))
                self.assertEqual(len(backups), 1, backups)
                self.assertEqual((backups[0] / "local.txt").read_text(encoding="utf-8"), "keep\n")

    def test_merge_skips_names_in_local_protected_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            temp_dir = Path(directory)
            fixture = self.make_fixture(temp_dir)
            target = self.install_then_edit_locally(temp_dir, fixture)
            (target / ".jleechan-skills-protected").write_text(
                "# operator-owned\n  example  \ncommand # trailing comment\n", encoding="utf-8"
            )

            result = self.run_installer(fixture, target, "--merge")

            output = result.stderr + result.stdout
            self.assertEqual(result.returncode, 0, output)
            self.assertIn(f"Skipping protected skills path (overwrite needs --include-protected): {target}/skills/example", output)
            self.assertIn(f"Skipping protected commands path (overwrite needs --include-protected): {target}/commands/command.md", output)
            self.assertEqual(
                (target / "skills/example/SKILL.md").read_text(encoding="utf-8"), "# Local operator rules\n"
            )
            self.assertEqual((target / "commands/command.md").read_text(encoding="utf-8"), "local command\n")
            self.assertIn("Source-derived manifest validation passed", result.stdout)
            self.assertFalse(list(temp_dir.glob("claude-home.merge-backup-*")))

    def test_merge_skips_names_in_source_retain_local_json(self):
        with tempfile.TemporaryDirectory() as directory:
            temp_dir = Path(directory)
            fixture = self.make_fixture(temp_dir)
            target = self.install_then_edit_locally(temp_dir, fixture)
            (fixture / "shared").mkdir()
            (fixture / "shared/retain-local.json").write_text(
                '{"example": "local operational variant"}\n', encoding="utf-8"
            )

            result = self.run_installer(fixture, target, "--merge")

            output = result.stderr + result.stdout
            self.assertEqual(result.returncode, 0, output)
            self.assertIn(f"{target}/skills/example", output)
            self.assertEqual(
                (target / "skills/example/SKILL.md").read_text(encoding="utf-8"), "# Local operator rules\n"
            )
            self.assertEqual((target / "commands/command.md").read_text(encoding="utf-8"), "command\n")

    def test_merge_fails_closed_on_unreadable_retain_local_json(self):
        with tempfile.TemporaryDirectory() as directory:
            temp_dir = Path(directory)
            fixture = self.make_fixture(temp_dir)
            target = self.install_then_edit_locally(temp_dir, fixture)
            (fixture / "shared").mkdir()
            (fixture / "shared/retain-local.json").write_text("{not json", encoding="utf-8")

            result = self.run_installer(fixture, target, "--merge")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Cannot parse protected list", result.stderr + result.stdout)
            self.assertEqual(
                (target / "skills/example/SKILL.md").read_text(encoding="utf-8"), "# Local operator rules\n"
            )

    def test_merge_fails_closed_when_retain_local_json_is_not_a_name_object(self):
        variants = {
            "directory": "Cannot read protected list",
            "dangling-symlink": "Cannot read protected list",
            "json-string": "Cannot parse protected list",
            "json-list": "Cannot parse protected list",
            "empty-object": "Cannot parse protected list",
        }
        for variant, expected in variants.items():
            with self.subTest(variant), tempfile.TemporaryDirectory() as directory:
                temp_dir = Path(directory)
                fixture = self.make_fixture(temp_dir)
                target = self.install_then_edit_locally(temp_dir, fixture)
                shared = fixture / "shared"
                shared.mkdir(parents=True, exist_ok=True)
                path = shared / "retain-local.json"
                if variant == "directory":
                    path.mkdir()
                elif variant == "dangling-symlink":
                    path.symlink_to(temp_dir / "absent.json")
                elif variant == "json-string":
                    path.write_text('"example"\n', encoding="utf-8")
                elif variant == "json-list":
                    path.write_text('["example"]\n', encoding="utf-8")
                else:
                    path.write_text("{}\n", encoding="utf-8")

                result = self.run_installer(fixture, target, "--merge")

                output = result.stderr + result.stdout
                self.assertNotEqual(result.returncode, 0, output)
                self.assertIn(expected, output)
                self.assertEqual(
                    (target / "skills/example/SKILL.md").read_text(encoding="utf-8"), "# Local operator rules\n"
                )
                self.assertEqual((target / "commands/command.md").read_text(encoding="utf-8"), "local command\n")
                self.assertFalse(list(temp_dir.glob("claude-home.merge-backup-*")))

    def test_merge_backup_stays_outside_target_with_double_trailing_slash_home(self):
        with tempfile.TemporaryDirectory() as directory:
            temp_dir = Path(directory)
            fixture = self.make_fixture(temp_dir)
            target = self.install_then_edit_locally(temp_dir, fixture)

            result = self.run_installer(
                fixture, target, "--merge", extra_environment={"CLAUDE_HOME": f"{target}//"}
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertFalse(list(target.glob(".merge-backup-*")))
            backups = list(temp_dir.glob("claude-home.merge-backup-*"))
            self.assertEqual(len(backups), 1, backups)
            self.assertEqual(
                (backups[0] / "skills/example/SKILL.md").read_text(encoding="utf-8"),
                "# Local operator rules\n",
            )

    def test_include_protected_overwrites_protected_paths_after_backing_them_up(self):
        with tempfile.TemporaryDirectory() as directory:
            temp_dir = Path(directory)
            fixture = self.make_fixture(temp_dir)
            target = self.install_then_edit_locally(temp_dir, fixture)
            (target / ".jleechan-skills-protected").write_text("example\n", encoding="utf-8")

            result = self.run_installer(fixture, target, "--merge", "--include-protected")

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertNotIn("Skipping protected", result.stdout)
            self.assertEqual((target / "skills/example/SKILL.md").read_text(encoding="utf-8"), "# Skill\n")
            backups = list(temp_dir.glob("claude-home.merge-backup-*"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(
                (backups[0] / "skills/example/SKILL.md").read_text(encoding="utf-8"),
                "# Local operator rules\n",
            )

    def test_include_protected_requires_merge(self):
        with tempfile.TemporaryDirectory() as directory:
            temp_dir = Path(directory)
            fixture = self.make_fixture(temp_dir)
            result = self.run_installer(fixture, temp_dir / "claude-home", "--include-protected")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--include-protected requires --merge", result.stderr + result.stdout)

    def test_fresh_install_installs_protected_names_and_writes_no_backup(self):
        for args in ((), ("--merge",)):
            with self.subTest(args=args), tempfile.TemporaryDirectory() as directory:
                temp_dir = Path(directory)
                fixture = self.make_fixture(temp_dir)
                (fixture / "shared").mkdir()
                (fixture / "shared/retain-local.json").write_text('{"example": "x"}\n', encoding="utf-8")
                target = temp_dir / "claude-home"

                result = self.run_installer(fixture, target, *args)

                self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
                self.assertNotIn("Skipping protected", result.stdout)
                self.assertEqual((target / "skills/example/SKILL.md").read_text(encoding="utf-8"), "# Skill\n")
                self.assertFalse(list(temp_dir.glob("claude-home.merge-backup-*")))

    def test_archive_migration_leaves_protected_paths_in_discovery(self):
        for args in ((), ("--include-protected",)):
            with self.subTest(args=args), tempfile.TemporaryDirectory() as directory:
                temp_dir = Path(directory)
                fixture = self.make_fixture(temp_dir)
                target = temp_dir / "claude-home"
                active_skill = target / "skills/retired-skill/SKILL.md"
                active_command = target / "commands/retired-command.md"
                active_extended = target / "commands/extended-library/retired-command.md"
                for path in (active_skill, active_command, active_extended):
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("operator copy\n", encoding="utf-8")
                (target / ".jleechan-skills-protected").write_text(
                    "retired-skill\nretired-command\n", encoding="utf-8"
                )

                result = self.run_installer(fixture, target, "--merge", "--migrate-archives", *args)

                self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
                archived_skill = target / "skills_archive/2026-retired/retired-skill/SKILL.md"
                archived_command = target / "commands_archive/2026-retired/top-level/retired-command.md"
                archived_extended = (
                    target / "commands_archive/2026-retired/extended-library/retired-command.md"
                )
                if args:
                    for path in (active_skill, active_command, active_extended):
                        self.assertFalse(path.exists())
                    for path in (archived_skill, archived_command, archived_extended):
                        self.assertTrue(path.is_file())
                else:
                    self.assertIn(f"Skipping protected skills path (overwrite needs --include-protected): {target}/skills/retired-skill", result.stdout)
                    self.assertIn(
                        "Skipping protected commands path (overwrite needs --include-protected): "
                        f"{target}/commands/extended-library/retired-command.md",
                        result.stdout,
                    )
                    for path in (active_skill, active_command, active_extended):
                        self.assertEqual(path.read_text(encoding="utf-8"), "operator copy\n")
                    for path in (archived_skill, archived_command, archived_extended):
                        self.assertFalse(path.exists())

    def test_merge_skips_protected_command_nested_in_extended_library(self):
        with tempfile.TemporaryDirectory() as directory:
            temp_dir = Path(directory)
            fixture = self.make_fixture(temp_dir)
            nested_source = fixture / ".claude/commands/extended-library/factory-spec.md"
            nested_source.parent.mkdir(parents=True)
            nested_source.write_text("source spec\n", encoding="utf-8")
            target = temp_dir / "claude-home"
            self.assertEqual(self.run_installer(fixture, target).returncode, 0)
            nested = target / "commands/extended-library/factory-spec.md"
            nested.write_text("local spec\n", encoding="utf-8")
            (target / ".jleechan-skills-protected").write_text("factory-spec\n", encoding="utf-8")

            kept = self.run_installer(fixture, target, "--merge")

            self.assertEqual(kept.returncode, 0, kept.stderr + kept.stdout)
            self.assertIn(
                f"Skipping protected commands path (overwrite needs --include-protected): {nested}",
                kept.stdout,
            )
            self.assertEqual(nested.read_text(encoding="utf-8"), "local spec\n")
            self.assertFalse(list(temp_dir.glob("claude-home.merge-backup-*")))

            overwritten = self.run_installer(fixture, target, "--merge", "--include-protected")

            self.assertEqual(overwritten.returncode, 0, overwritten.stderr + overwritten.stdout)
            self.assertEqual(nested.read_text(encoding="utf-8"), "source spec\n")
            backups = list(temp_dir.glob("claude-home.merge-backup-*"))
            self.assertEqual(len(backups), 1, backups)
            self.assertEqual(
                (backups[0] / "commands/extended-library/factory-spec.md").read_text(encoding="utf-8"),
                "local spec\n",
            )

    def test_history_helper_upgrade_backs_up_its_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            temp_dir = Path(directory)
            fixture = self.make_fixture(temp_dir)
            source = fixture / "scripts/history_search.py"
            source.write_text("print('version one')\n")
            target = temp_dir / "claude-home"
            self.assertEqual(self.run_installer(fixture, target).returncode, 0)
            receipt = target / "scripts/.history_search.py.sha256"
            v1_receipt = receipt.read_text()

            source.write_text("print('version two')\n")
            upgraded = self.run_installer(fixture, target, "--merge")

            self.assertEqual(upgraded.returncode, 0, upgraded.stdout + upgraded.stderr)
            backups = list(temp_dir.glob("claude-home.merge-backup-*"))
            self.assertEqual(len(backups), 1, backups)
            self.assertEqual(
                (backups[0] / "scripts/history_search.py").read_text(), "print('version one')\n"
            )
            self.assertEqual((backups[0] / "scripts/.history_search.py.sha256").read_text(), v1_receipt)

            # Restoring the backup pair keeps the helper recognisably installer-owned.
            for name in ("history_search.py", ".history_search.py.sha256"):
                shutil.copy2(backups[0] / "scripts" / name, target / "scripts" / name)
            source.write_text("print('version three')\n")
            restored = self.run_installer(fixture, target, "--merge")
            self.assertEqual(restored.returncode, 0, restored.stdout + restored.stderr)
            self.assertEqual(
                (target / "scripts/history_search.py").read_text(), "print('version three')\n"
            )

    def test_merge_backup_stays_outside_target_with_trailing_slash_home(self):
        with tempfile.TemporaryDirectory() as directory:
            temp_dir = Path(directory)
            fixture = self.make_fixture(temp_dir)
            target = self.install_then_edit_locally(temp_dir, fixture)

            result = self.run_installer(
                fixture, target, "--merge", extra_environment={"CLAUDE_HOME": f"{target}/"}
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertFalse(list(target.glob(".merge-backup-*")))
            backups = list(temp_dir.glob("claude-home.merge-backup-*"))
            self.assertEqual(len(backups), 1, backups)
            self.assertEqual(
                (backups[0] / "skills/example/SKILL.md").read_text(encoding="utf-8"),
                "# Local operator rules\n",
            )

    def test_merge_overwrites_stale_managed_files_including_readonly_and_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            temp_dir = Path(directory)
            fixture = self.make_fixture(temp_dir)
            target = temp_dir / "claude-home"
            target.mkdir()

            # 1. Stale managed python command (simulating bd-n38 newbranch.py) that is write-protected (0o444)
            stale_cmd_file = target / "commands/newbranch.py"
            stale_cmd_file.parent.mkdir(parents=True, exist_ok=True)
            stale_cmd_file.write_text(
                "#!/usr/bin/env python3\nprint('stale newbranch v1')\n",
                encoding="utf-8",
            )
            stale_cmd_file.chmod(0o444)

            # 2. Stale managed shell command inside a write-protected directory (0o555)
            nested_cmd_dir = target / "commands/nested"
            nested_cmd_dir.mkdir(parents=True, exist_ok=True)
            nested_cmd_file = nested_cmd_dir / "helper.sh"
            nested_cmd_file.write_text("#!/bin/sh\necho stale-helper\n", encoding="utf-8")
            nested_cmd_file.chmod(0o444)
            nested_cmd_dir.chmod(0o555)

            # 3. Stale managed command that was symlinked to an external file
            external_file = temp_dir / "external_command.md"
            external_file.write_text("external command\n", encoding="utf-8")
            symlink_cmd_file = target / "commands/command.md"
            symlink_cmd_file.symlink_to(external_file)

            # 4. Unrelated user files that should be preserved
            user_setting = target / "user-settings.txt"
            user_setting.write_text("retain user setting\n", encoding="utf-8")
            user_custom_cmd = target / "commands/user-custom.md"
            user_custom_cmd.write_text("retain custom command\n", encoding="utf-8")

            try:
                result = self.run_installer(fixture, target, "--merge")

                # Must succeed and validate manifest
                self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
                self.assertIn("Source-derived manifest validation passed", result.stdout)

                # 1. Stale managed file replaced with source content
                self.assertEqual(
                    stale_cmd_file.read_text(encoding="utf-8"),
                    "#!/usr/bin/env python3\nprint('newbranch v2')\n",
                )

                # 2. Nested managed file in protected directory replaced with source content
                self.assertEqual(
                    nested_cmd_file.read_text(encoding="utf-8"),
                    "#!/bin/sh\n",
                )

                # 3. Symlinked managed command replaced with real file and external target untouched
                self.assertFalse(symlink_cmd_file.is_symlink())
                self.assertEqual(symlink_cmd_file.read_text(encoding="utf-8"), "command\n")
                self.assertEqual(external_file.read_text(encoding="utf-8"), "external command\n")

                # 4. Unrelated user files preserved untouched
                self.assertEqual(user_setting.read_text(encoding="utf-8"), "retain user setting\n")
                self.assertEqual(user_custom_cmd.read_text(encoding="utf-8"), "retain custom command\n")
            finally:
                # Restore permissions for clean tempfile cleanup
                nested_cmd_dir.chmod(0o755)

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

    def test_install_prints_the_current_repository_url(self):
        with tempfile.TemporaryDirectory() as directory:
            temp_dir = Path(directory)
            fixture = self.make_fixture(temp_dir)
            result = self.run_installer(fixture, temp_dir / "claude-home")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("https://github.com/jleechanorg/jleechan-skills", result.stdout)
            self.assertNotIn("jleechanorg/claude-commands", result.stdout)

    def test_merge_and_backup_are_mutually_exclusive(self):
        for flags in (("--merge", "--backup"), ("--backup", "--merge")):
            with self.subTest(flags), tempfile.TemporaryDirectory() as directory:
                temp_dir = Path(directory)
                fixture = self.make_fixture(temp_dir)
                target = temp_dir / "claude-home"
                target.mkdir()
                (target / "mine.txt").write_text("keep\n", encoding="utf-8")

                result = self.run_installer(fixture, target, *flags)

                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("mutually exclusive", result.stderr + result.stdout)
                self.assertTrue((target / "mine.txt").is_file())
                self.assertEqual(list(temp_dir.glob("claude-home.backup-*")), [])

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

    def test_merge_migrate_archives_without_collisions_installs_under_bash32(self):
        bash32 = Path("/bin/bash")
        version = subprocess.run([str(bash32), "--version"], capture_output=True, text=True).stdout.split() \
            if bash32.exists() else []
        if len(version) < 4 or not version[3].startswith("3."):
            self.skipTest("/bin/bash is not 3.x")
        with tempfile.TemporaryDirectory() as directory:
            temp_dir = Path(directory)
            fixture = self.make_fixture(temp_dir)
            target = temp_dir / "claude-home"
            result = subprocess.run(
                [str(bash32), str(fixture / INSTALLER.name), "--merge", "--migrate-archives", "--all"],
                cwd=fixture, env=os.environ | {"CLAUDE_HOME": str(target)},
                text=True, capture_output=True, check=False,
            )
            output = result.stderr + result.stdout
            self.assertNotIn("unbound variable", output)
            self.assertEqual(result.returncode, 0, output)
            self.assertTrue((target / "skills/example/SKILL.md").is_file(), output)
            self.assertIn("Installation complete", output)

    def test_migrate_archives_keeps_skills_the_source_still_ships_active(self):
        with tempfile.TemporaryDirectory() as directory:
            temp_dir = Path(directory)
            fixture = self.make_fixture(temp_dir)
            stale = fixture / ".claude/skills_archive/legacy-pre/packages/example/SKILL.md"
            stale.parent.mkdir(parents=True)
            stale.write_text("# stale copy\n", encoding="utf-8")
            target = temp_dir / "claude-home"
            first = self.run_installer(fixture, target)
            self.assertEqual(first.returncode, 0, first.stderr + first.stdout)

            result = self.run_installer(fixture, target, "--merge", "--migrate-archives")

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertEqual((target / "skills/example/SKILL.md").read_text(encoding="utf-8"), "# Skill\n")
            self.assertFalse((target / "skills_archive/legacy-pre/packages/example").exists())

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
            leftover_staging = [
                p
                for p in temp_dir.glob("claude-home.staging.*")
                if ".failed-" not in p.name
            ]
            self.assertFalse(leftover_staging)
            # A failed run must leave the staging tree recoverable, renamed aside
            # instead of recursively deleted.
            failed = list(temp_dir.glob("claude-home.staging.*.failed-*"))
            self.assertEqual(len(failed), 1, [p.name for p in temp_dir.iterdir()])
            self.assertTrue(failed[0].is_dir())
            self.assertIn("kept for inspection", result.stdout + result.stderr)

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


class InstallerSymlinkModeSafetyTest(unittest.TestCase):
    def test_replacing_a_symlink_does_not_chmod_the_external_file(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        fixture = root / "fixture"
        (fixture / ".claude" / "commands").mkdir(parents=True)
        (fixture / ".claude" / "commands" / "cmd.md").write_text("managed\n", encoding="utf-8")
        (fixture / "scripts").mkdir()
        shutil.copy2(INSTALLER, fixture / INSTALLER.name)
        target = root / "target"
        (target / "commands").mkdir(parents=True)
        external = root / "external.md"
        external.write_text("external\n", encoding="utf-8")
        external.chmod(0o400)
        (target / "commands" / "cmd.md").symlink_to(external)

        result = subprocess.run(
            ["bash", str(fixture / INSTALLER.name), "--merge", "--all"],
            cwd=fixture,
            env=os.environ | {"CLAUDE_HOME": str(target)},
            text=True,
            capture_output=True,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(
            (target / "commands" / "cmd.md").read_text(encoding="utf-8"), "managed\n"
        )
        self.assertEqual(external.stat().st_mode & 0o777, 0o400)
        self.assertEqual(external.read_text(encoding="utf-8"), "external\n")


class InstallerShellPortabilityTest(unittest.TestCase):
    """The installer must work under bash 3.2 (macOS /bin/bash), not just bash 5."""

    def test_installs_under_bash32_when_available(self):
        bash32 = Path("/bin/bash")
        if not bash32.exists():
            self.skipTest("/bin/bash not present")
        version = subprocess.run(
            [str(bash32), "--version"], capture_output=True, text=True
        ).stdout.split()
        if len(version) < 4 or not version[3].startswith("3."):
            self.skipTest(f"/bin/bash is not 3.x ({' '.join(version[:4])})")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / "fixture"
            (fixture / ".claude" / "commands").mkdir(parents=True)
            (fixture / ".claude" / "commands" / "cmd.md").write_text(
                "managed\n", encoding="utf-8"
            )
            (fixture / "scripts").mkdir()
            shutil.copy2(INSTALLER, fixture / INSTALLER.name)
            target = root / "target"

            result = subprocess.run(
                [str(bash32), str(fixture / INSTALLER.name), "--all"],
                cwd=fixture,
                env=os.environ | {"CLAUDE_HOME": str(target)},
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(
                (target / "commands" / "cmd.md").read_text(encoding="utf-8"),
                "managed\n",
            )


class InstallerEntryKindsTest(unittest.TestCase):
    def build(self):
        import tempfile as tf

        temp = tf.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        fixture = root / "fixture"
        (fixture / ".claude" / "commands").mkdir(parents=True)
        (fixture / ".claude" / "commands" / "cmd.md").write_text("managed\n", encoding="utf-8")
        (fixture / "scripts").mkdir()
        shutil.copy2(INSTALLER, fixture / INSTALLER.name)
        return root, fixture, root / "target"

    def run_merge(self, fixture, target, timeout=120):
        return subprocess.run(
            ["bash", str(fixture / INSTALLER.name), "--merge", "--all"],
            cwd=fixture,
            env=os.environ | {"CLAUDE_HOME": str(target)},
            text=True,
            capture_output=True,
            timeout=timeout,
        )

    def test_read_only_hard_link_keeps_outside_mode_and_content(self):
        root, fixture, target = self.build()
        (target / "commands").mkdir(parents=True)
        external = root / "external.md"
        external.write_text("external\n", encoding="utf-8")
        external.chmod(0o400)
        os.link(external, target / "commands" / "cmd.md")

        result = self.run_merge(fixture, target)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(external.stat().st_mode & 0o777, 0o400)
        self.assertEqual(external.read_text(encoding="utf-8"), "external\n")
        self.assertEqual(
            (target / "commands" / "cmd.md").read_text(encoding="utf-8"), "managed\n"
        )

    def test_read_only_regular_file_is_replaced(self):
        root, fixture, target = self.build()
        (target / "commands").mkdir(parents=True)
        stale = target / "commands" / "cmd.md"
        stale.write_text("stale\n", encoding="utf-8")
        stale.chmod(0o444)

        result = self.run_merge(fixture, target)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(stale.read_text(encoding="utf-8"), "managed\n")

    def test_failed_move_aside_stops_the_install_and_preserves_the_directory(self):
        import tempfile as tf

        temp = tf.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        fixture = root / "fixture"
        (fixture / ".claude" / "skills" / "pkg").mkdir(parents=True)
        (fixture / ".claude" / "skills" / "pkg" / "SKILL.md").write_text("# S\n", encoding="utf-8")
        (fixture / "scripts").mkdir()
        shutil.copy2(INSTALLER, fixture / INSTALLER.name)
        target = root / "target"
        installed = target / "skills" / "pkg" / "SKILL.md"
        installed.mkdir(parents=True)
        (installed / "inner.txt").write_text("inner\n", encoding="utf-8")
        fake_bin = root / "fakebin"
        fake_bin.mkdir()
        fake_mv = fake_bin / "mv"
        fake_mv.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        fake_mv.chmod(0o755)

        result = subprocess.run(
            ["bash", str(fixture / INSTALLER.name), "--merge", "--all"],
            cwd=fixture,
            env=os.environ
            | {"CLAUDE_HOME": str(target), "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}"},
            text=True,
            capture_output=True,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Cannot replace directory", result.stdout + result.stderr)
        self.assertTrue(installed.is_dir())
        self.assertTrue((installed / "inner.txt").exists())

    def test_fifo_destination_is_replaced_without_hanging(self):
        root, fixture, target = self.build()
        (target / "commands").mkdir(parents=True)
        fifo = target / "commands" / "cmd.md"
        os.mkfifo(fifo)

        result = self.run_merge(fixture, target, timeout=60)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(fifo.is_file())
        self.assertFalse(stat.S_ISFIFO(fifo.stat().st_mode))
        self.assertEqual(fifo.read_text(encoding="utf-8"), "managed\n")


class InstallerMovesWrongKindEntryAsideTest(unittest.TestCase):
    """A directory where the source has a file is moved aside, never deleted."""

    def test_merge_replaces_directory_with_source_file(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        fixture = root / "fixture"
        (fixture / ".claude" / "skills" / "example").mkdir(parents=True)
        (fixture / ".claude" / "skills" / "example" / "SKILL.md").write_text(
            "# Skill\n", encoding="utf-8"
        )
        (fixture / "scripts").mkdir()
        shutil.copy2(INSTALLER, fixture / INSTALLER.name)
        target = root / "target"
        environment = os.environ | {"CLAUDE_HOME": str(target)}

        first = subprocess.run(
            ["bash", str(fixture / INSTALLER.name), "--merge", "--all"],
            cwd=fixture,
            env=environment,
            text=True,
            capture_output=True,
        )
        self.assertEqual(first.returncode, 0, first.stderr + first.stdout)

        installed = target / "skills" / "example" / "SKILL.md"
        installed.unlink()
        installed.mkdir()
        (installed / "stale.txt").write_text("stale\n", encoding="utf-8")

        second = subprocess.run(
            ["bash", str(fixture / INSTALLER.name), "--merge", "--all"],
            cwd=fixture,
            env=environment,
            text=True,
            capture_output=True,
        )
        # A directory where the source has a file is moved aside (never
        # recursively deleted) and the file is installed in its place.
        self.assertEqual(second.returncode, 0, second.stderr + second.stdout)
        self.assertTrue(installed.is_file())
        self.assertEqual(installed.read_text(encoding="utf-8"), "# Skill\n")
        replaced = list((target / "skills" / "example").glob("SKILL.md.replaced-*"))
        self.assertEqual(len(replaced), 1)
        self.assertTrue((replaced[0] / "stale.txt").exists())


class NewlinePathEscapeTest(unittest.TestCase):
    """A newline inside a directory name must not hide a symlinked parent."""

    def test_symlinked_parent_with_newline_cannot_escape_the_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outside = root / "outside"
            outside.mkdir()
            target = root / "target"
            linked_parent = target / "commands" / "evil\nlink"
            linked_parent.parent.mkdir(parents=True)
            linked_parent.symlink_to(outside)

            fixture = root / "fixture"
            src_parent = fixture / ".claude" / "commands" / "evil\nlink"
            src_parent.mkdir(parents=True)
            (src_parent / "pwn.md").write_text("pwned\n", encoding="utf-8")
            (fixture / "scripts").mkdir()
            shutil.copy2(INSTALLER, fixture / INSTALLER.name)

            result = subprocess.run(
                ["bash", str(fixture / INSTALLER.name), "--merge", "--all"],
                cwd=fixture,
                env=os.environ | {"CLAUDE_HOME": str(target)},
                text=True,
                capture_output=True,
            )

            self.assertFalse(
                (outside / "pwn.md").exists(),
                "install escaped the target through a newline-named symlinked parent\n"
                + result.stdout
                + result.stderr,
            )


if __name__ == "__main__":
    unittest.main()


class PathContainmentGuardTest(unittest.TestCase):
    """The installer refuses to write through a parent that resolves outside the root."""

    def _call_guard(self, parent, root):
        # argv, not interpolation: a path may contain quotes or newlines.
        script = 'source "$1" >/dev/null 2>&1; path_within_root "$2" "$3"'
        return subprocess.run(["bash", "-c", script, "_", str(INSTALLER), str(parent), str(root)],
                              capture_output=True, text=True)

    def test_relative_claude_home_installs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / "fixture"
            (fixture / ".claude" / "commands").mkdir(parents=True)
            (fixture / ".claude" / "commands" / "cmd.md").write_text("managed\n", encoding="utf-8")
            (fixture / "scripts").mkdir()
            shutil.copy2(INSTALLER, fixture / INSTALLER.name)
            result = subprocess.run(
                ["bash", INSTALLER.name, "--merge", "--all"],
                cwd=fixture,
                env=os.environ | {"CLAUDE_HOME": "target"},
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(
                (fixture / "target" / "commands" / "cmd.md").read_text(encoding="utf-8"),
                "managed\n",
            )

    def test_symlinked_parent_outside_the_root_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target"
            outside = root / "outside"
            (target / "commands").mkdir(parents=True)
            outside.mkdir()
            (target / "commands" / "link").symlink_to(outside)
            result = self._call_guard(str(target / "commands" / "link"), str(target))
            self.assertNotEqual(result.returncode, 0, "a symlinked parent must fail containment")

    def test_ordinary_path_inside_the_root_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target"
            (target / "commands").mkdir(parents=True)
            result = self._call_guard(str(target / "commands"), str(target))
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_newline_ending_directory_name_is_not_mangled(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target"
            (target / "commands" / "nl\n").mkdir(parents=True)
            result = self._call_guard(str(target / "commands" / "nl\n"), str(target))
            self.assertEqual(
                result.returncode, 0,
                "a directory whose name ends in a newline must still pass containment: "
                + result.stderr,
            )

    def test_installer_still_installs_a_normal_tree(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / "fixture"
            (fixture / ".claude" / "commands").mkdir(parents=True)
            (fixture / ".claude" / "commands" / "cmd.md").write_text("managed\n", encoding="utf-8")
            (fixture / "scripts").mkdir()
            shutil.copy2(INSTALLER, fixture / INSTALLER.name)
            target = root / "target"
            result = subprocess.run(
                ["bash", str(fixture / INSTALLER.name), "--merge", "--all"],
                cwd=fixture,
                env=os.environ | {"CLAUDE_HOME": str(target)},
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual((target / "commands" / "cmd.md").read_text(encoding="utf-8"), "managed\n")


PROFILE_SCRIPT = REPO_ROOT / "scripts" / "install_profiles.py"
PROFILE_DATA = REPO_ROOT / "shared" / "install-profiles.json"
SKILL_LINK = re.compile(r"(?:\.\./|skills/)([A-Za-z0-9_.-]+)/")
COMMAND_TARGET = re.compile(r"skills/([A-Za-z0-9_.-]+)/SKILL\.md")
DOT_FAMILY = {"dot", "dot-coordinator", "agy-dot-coordinator"}
CLOSURE_DENYLIST = DOT_FAMILY | {
    "web-advice", "browser-control", "slack-media-upload", "github-cli-reference",
    "claw-dispatch", "ao-operator-discipline", "aside-browser-default", "browser-testing",
}
COMMAND_COMPANION = re.compile(r"commands/([A-Za-z0-9_./-]+)")
RELATIVE_SKILL_LINK = re.compile(r"(?<![\w.])((?:\.\./)+[A-Za-z0-9_.-]+/SKILL\.md)")


def installed_tree(target: Path, component: str) -> set[str]:
    root = target / component
    if not root.is_dir():
        return set()
    return {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}


class InstallerProfileFixtureTest(unittest.TestCase):
    """Profiles select a dependency closure from a small synthetic library."""

    PROFILES = {
        "default_profile": "default",
        "closure_excluded": ["dot"],
        "profiles": {
            "default": {"description": "Alpha and its closure", "skills": ["alpha"]},
            "pair": {"description": "Beta plus one command", "skills": ["beta"], "commands": ["bc"]},
            "withdot": {"description": "Names dot explicitly", "skills": ["dot"]},
            "dangling": {"description": "A command aimed at a skill that is not in the library", "skills": ["beta"], "commands": ["missingcmd"]},
            "leaky": {"description": "A command aimed at an excluded skill", "skills": ["beta"], "commands": ["dotc"]},
        },
    }
    FILES = {
        "skills/alpha/SKILL.md": (
            "# Alpha\nSee [beta](../beta/SKILL.md) and ~/.claude/skills/dot/SKILL.md.\n"
            "Run `~/.claude/scripts/tool.py`; dispatch the `helper-agent` subagent.\n"
        ),
        "skills/alpha/scripts/run.sh": "#!/bin/sh\n",
        "skills/beta/SKILL.md": "# Beta\nLoad ${CLAUDE_HOME:-$HOME/.claude}/skills/gamma/SKILL.md.\n",
        "skills/gamma/SKILL.md": "# Gamma\n",
        "skills/delta/SKILL.md": "# Delta\n",
        "skills/dot/SKILL.md": "# Dot reads cookie databases\n",
        "commands/a.md": "Read `~/.claude/skills/alpha/SKILL.md`, then run `.claude/commands/helper.py`.\n",
        "commands/bc.md": "Read `~/.claude/skills/beta/SKILL.md`.\n",
        "commands/g.md": "Read `~/.claude/skills/gamma/SKILL.md` then skills/delta/SKILL.md.\n",
        "commands/d.md": "Read `~/.claude/skills/delta/SKILL.md`.\n",
        "commands/dotc.md": "Read `~/.claude/skills/dot/SKILL.md`.\n",
        "commands/missingcmd.md": "Read `~/.claude/skills/missing/SKILL.md`.\n",
        "commands/plain.md": "No skill target.\n",
        "commands/longcmd.md": (
            "---\ndescription: Run a long orchestration workflow\n---\n"
            "Read `~/.claude/skills/alpha/SKILL.md`, then run `.claude/commands/longhelper.py`.\n"
            + "step\n" * 16
        ),
        "commands/longhelper.py": "print('long helper')\n",
        "commands/described.md": (
            "---\ndescription: Thin ALIAS for the alpha skill\n---\n"
            "Read `~/.claude/skills/alpha/SKILL.md`.\n" + "note\n" * 16
        ),
        "commands/helper.py": "print('helper')\n",
        "commands/extended-library/al.md": "Read `~/.claude/skills/alpha/SKILL.md`.\n",
        "commands/extended-library/de.md": "Read `~/.claude/skills/delta/SKILL.md`.\n",
        "agents/helper-agent.md": "helper\n",
        "agents/other-agent.md": "other\n",
        "scripts/tool.py": "print('tool')\n",
        "scripts/other.py": "print('other')\n",
    }

    def make_fixture(self, temp_dir: Path) -> Path:
        fixture = temp_dir / "fixture"
        (fixture / "scripts").mkdir(parents=True)
        (fixture / "shared").mkdir()
        shutil.copy2(INSTALLER, fixture / INSTALLER.name)
        shutil.copy2(PROFILE_SCRIPT, fixture / "scripts" / PROFILE_SCRIPT.name)
        (fixture / "scripts/integrate.sh").write_text("#!/bin/sh\n", encoding="utf-8")
        (fixture / "shared/install-profiles.json").write_text(json.dumps(self.PROFILES), encoding="utf-8")
        for relative, content in self.FILES.items():
            path = fixture / ".claude" / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        return fixture

    def run_installer(self, fixture: Path, target: Path, *args: str, bash: str = "bash"):
        return subprocess.run(
            [bash, str(fixture / INSTALLER.name), *args],
            cwd=fixture, env=os.environ | {"CLAUDE_HOME": str(target)},
            text=True, capture_output=True, check=False,
        )

    def test_default_profile_installs_the_seed_closure_and_matching_aliases_only(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.make_fixture(Path(directory))
            target = Path(directory) / "home"
            result = self.run_installer(fixture, target)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertEqual(
                installed_tree(target, "skills"),
                {"alpha/SKILL.md", "alpha/scripts/run.sh", "beta/SKILL.md", "gamma/SKILL.md"},
            )
            # Aliases follow seeds only: beta and gamma arrive by closure, so bc.md and g.md stay out.
            # a.md's companion helper.py installs with it; unreferenced plain.md does not.
            self.assertEqual(
                installed_tree(target, "commands"),
                {"a.md", "helper.py", "extended-library/al.md", "described.md"},
            )
            self.assertEqual(installed_tree(target, "agents"), {"helper-agent.md"})
            self.assertEqual(installed_tree(target, "scripts"), {"tool.py"})
            self.assertIn("Profile: default", result.stdout)
            self.assertIn("Installed profile 'default': 3 skills, 3 commands, 1 agents", result.stdout)
            # longcmd.md targets the seed but is a long non-alias workflow; neither it nor its helper installs.
            self.assertFalse((target / "commands/longcmd.md").exists())
            self.assertFalse((target / "commands/longhelper.py").exists())
            self.assertIn("Source-derived manifest validation passed", result.stdout)

    def test_named_profile_adds_its_explicit_commands(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.make_fixture(Path(directory))
            target = Path(directory) / "home"
            result = self.run_installer(fixture, target, "--profile", "pair")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertEqual(installed_tree(target, "skills"), {"beta/SKILL.md", "gamma/SKILL.md"})
            self.assertEqual(installed_tree(target, "commands"), {"bc.md"})
            self.assertEqual(installed_tree(target, "agents"), set())
            self.assertIn("Installed profile 'pair': 2 skills, 1 commands, 0 agents", result.stdout)

    def test_dot_is_never_pulled_in_by_closure_but_installs_when_named(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.make_fixture(Path(directory))
            closure_home = Path(directory) / "closure"
            result = self.run_installer(fixture, closure_home)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertFalse((closure_home / "skills/dot").exists())
            self.assertFalse((closure_home / "commands/dotc.md").exists())
            named_home = Path(directory) / "named"
            result = self.run_installer(fixture, named_home, "--profile", "withdot")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertEqual(installed_tree(named_home, "skills"), {"dot/SKILL.md"})
            self.assertEqual(installed_tree(named_home, "commands"), {"dotc.md"})

    def test_with_adds_a_closure_excluded_skill_to_the_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.make_fixture(Path(directory))
            target = Path(directory) / "home"
            result = self.run_installer(fixture, target, "--with", "dot")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertEqual({p.name for p in (target / "skills").iterdir()}, {"alpha", "beta", "gamma", "dot"})
            self.assertTrue((target / "commands/dotc.md").is_file())
            self.assertIn("Installed profile 'default': 4 skills, 4 commands, 1 agents", result.stdout)

    def test_all_installs_the_whole_library(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.make_fixture(Path(directory))
            target = Path(directory) / "home"
            result = self.run_installer(fixture, target, "--all")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            for relative, content in self.FILES.items():
                self.assertEqual((target / relative).read_text(), content, relative)
            self.assertIn("Profile: --all (full library)", result.stdout)
            self.assertIn("Installed --all (full library): 5 skills, 11 commands, 2 agents", result.stdout)
            self.assertNotIn("profile 'all'", result.stdout)

    def test_profile_selection_errors_fail_before_writing(self):
        cases = {
            "unknown": (("--profile", "nope"), "Unknown install profile: nope"),
            "conflict": (("--all", "--profile", "pair"), "--all and --profile are mutually exclusive"),
            "missing": (("--profile",), "--profile requires a name"),
            "portable": (("--portable", "--profile", "pair"), "--portable installs its own manifest"),
            "with-all": (("--all", "--with", "dot"), "--with adds to a profile"),
            "with-missing": (("--with", "nosuch"), "names missing skills: nosuch"),
            "command-to-missing": (("--profile", "dangling"), "command missingcmd targets missing skill missing"),
            "command-to-excluded": (("--profile", "leaky"), "command dotc targets closure-excluded skill dot"),
        }
        for name, (args, message) in cases.items():
            with self.subTest(name), tempfile.TemporaryDirectory() as directory:
                fixture = self.make_fixture(Path(directory))
                target = Path(directory) / "home"
                result = self.run_installer(fixture, target, *args)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn(message, result.stdout + result.stderr)
                self.assertFalse(target.exists())

    def test_malformed_profile_data_fails_closed(self):
        broken = {
            "denylist-string": {"closure_excluded": "dot"},
            "denylist-non-string": {"closure_excluded": ["dot", 3]},
            "skills-string": {"profiles": {**self.PROFILES["profiles"], "default": {"skills": "alpha"}}},
            "commands-dict": {"profiles": {**self.PROFILES["profiles"], "pair": {"skills": ["beta"], "commands": {"bc": 1}}}},
            "include-non-string": {"profiles": {**self.PROFILES["profiles"], "pair": {"skills": ["beta"], "include": [None]}}},
        }
        for name, override in broken.items():
            with self.subTest(name), tempfile.TemporaryDirectory() as directory:
                fixture = self.make_fixture(Path(directory))
                (fixture / "shared/install-profiles.json").write_text(json.dumps({**self.PROFILES, **override}))
                target = Path(directory) / "home"
                result = self.run_installer(fixture, target)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("Malformed install profiles", result.stdout + result.stderr)
                self.assertFalse(target.exists())

    def test_omitted_or_empty_closure_excluded_fails_closed(self):
        variants = {
            "omitted": {key: value for key, value in self.PROFILES.items() if key != "closure_excluded"},
            "empty": {**self.PROFILES, "closure_excluded": []},
        }
        for name, data in variants.items():
            with self.subTest(name), tempfile.TemporaryDirectory() as directory:
                fixture = self.make_fixture(Path(directory))
                (fixture / "shared/install-profiles.json").write_text(json.dumps(data))
                target = Path(directory) / "home"
                result = self.run_installer(fixture, target)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("Malformed install profiles", result.stdout + result.stderr)
                self.assertFalse(target.exists())

    def test_help_lists_profiles(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.make_fixture(Path(directory))
            result = self.run_installer(fixture, Path(directory) / "home", "--help")
            self.assertEqual(result.returncode, 0, result.stderr)
            for line in ("default (default)", "Alpha and its closure", "pair", "withdot", "--all",
                         "--profile NAME", "--with SKILL"):
                self.assertIn(line, result.stdout)

    def test_merge_under_profile_backs_up_and_honours_protected_names(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.make_fixture(Path(directory))
            target = Path(directory) / "home"
            self.assertEqual(self.run_installer(fixture, target).returncode, 0)
            (target / "skills/alpha/SKILL.md").write_text("local alpha\n")
            (target / "skills/beta/SKILL.md").write_text("local beta\n")
            (target / "skills/delta").mkdir()
            (target / "skills/delta/SKILL.md").write_text("unmanaged delta\n")
            (target / ".jleechan-skills-protected").write_text("beta\n")

            result = self.run_installer(fixture, target, "--merge")

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertEqual((target / "skills/alpha/SKILL.md").read_text(), self.FILES["skills/alpha/SKILL.md"])
            self.assertEqual((target / "skills/beta/SKILL.md").read_text(), "local beta\n")
            self.assertEqual((target / "skills/delta/SKILL.md").read_text(), "unmanaged delta\n")
            self.assertIn("Skipping protected skills path", result.stdout + result.stderr)
            backups = list(Path(directory).glob("home.merge-backup-*"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(installed_tree(backups[0], "skills"), {"alpha/SKILL.md"})
            self.assertEqual((backups[0] / "skills/alpha/SKILL.md").read_text(), "local alpha\n")
            self.assertIn("Source-derived manifest validation passed", result.stdout)

    def test_backup_mode_under_profile_replaces_target_with_profile_only(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.make_fixture(Path(directory))
            target = Path(directory) / "home"
            target.mkdir()
            (target / "keep.txt").write_text("old\n")
            result = self.run_installer(fixture, target, "--backup", "--profile", "pair")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertEqual(installed_tree(target, "skills"), {"beta/SKILL.md", "gamma/SKILL.md"})
            backups = list(Path(directory).glob("home.backup-*"))
            self.assertEqual(len(backups), 1)
            self.assertEqual((backups[0] / "keep.txt").read_text(), "old\n")

    def test_profile_install_under_bash32(self):
        bash32 = Path("/bin/bash")
        version = subprocess.run([str(bash32), "--version"], capture_output=True, text=True).stdout.split() \
            if bash32.exists() else []
        if len(version) < 4 or not version[3].startswith("3."):
            self.skipTest("/bin/bash is not 3.x")
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.make_fixture(Path(directory))
            target = Path(directory) / "home"
            result = self.run_installer(fixture, target, bash=str(bash32))
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertEqual(installed_tree(target, "agents"), {"helper-agent.md"})


class InstallerRealProfileTest(unittest.TestCase):
    """Each shipped profile installs exactly its seed closure from this repository."""

    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(PROFILE_DATA.read_text())
        cls.skills_root = REPO_ROOT / ".claude/skills"
        cls.skill_names = {
            p.name for p in cls.skills_root.iterdir()
            if p.is_dir() and (p / "SKILL.md").is_file() and not p.name.startswith("_")
        }
        cls.links = {}
        for name in cls.skill_names:
            found = set()
            for path in (cls.skills_root / name).rglob("*"):
                if path.is_file() and not {"__pycache__", ".pytest_cache"}.intersection(path.parts):
                    try:
                        found |= set(SKILL_LINK.findall(path.read_text(encoding="utf-8")))
                    except (UnicodeDecodeError, OSError):
                        continue
            cls.links[name] = (found & cls.skill_names) - {name}

    def expected_skills(self, profile: str) -> set[str]:
        spec = self.data["profiles"][profile]
        seeds = set(spec.get("skills", []))
        for included in spec.get("include", []):
            seeds |= self.expected_skills(included)
        excluded = set(self.data.get("closure_excluded", []))
        result, stack = set(seeds), list(seeds)
        while stack:
            for dependency in self.links[stack.pop()]:
                if dependency not in result and (dependency not in excluded or dependency in seeds):
                    result.add(dependency)
                    stack.append(dependency)
        return result

    def install(self, target: Path, *args: str):
        result = subprocess.run(
            ["bash", str(INSTALLER), *args],
            env=os.environ | {"CLAUDE_HOME": str(target)},
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-4000:] + result.stdout[-4000:])
        self.assertIn("Source-derived manifest validation passed", result.stdout)
        return result

    def command_targets(self) -> dict[str, str]:
        targets = {}
        commands = REPO_ROOT / ".claude/commands"
        for path in [*commands.glob("*.md"), *(commands / "extended-library").glob("*.md")]:
            text = path.read_text(encoding="utf-8")
            match = COMMAND_TARGET.search(text)
            if match:
                targets[path.relative_to(commands).as_posix()] = match.group(1)
            elif re.search(r"^description:.*alias", text, re.I | re.M):
                # A described alias runs its skill as `/skill` instead of naming the skill path.
                named = [m for m in re.findall(r"`/([A-Za-z0-9_.-]+)`", text) if m in self.skill_names]
                if named:
                    targets[path.relative_to(commands).as_posix()] = named[0]
        return targets

    def test_default_profile_is_the_six_highlights_and_no_catalog_profile_exists(self):
        highlights = {"superpowers-quick", "advice", "redgreen", "4layer", "evidence-review", "harness-engineering"}
        self.assertEqual(self.data["default_profile"], "highlights")
        self.assertEqual(set(self.data["profiles"]), {"highlights", "highlights-prw", "prw", "web"})
        self.assertEqual(set(self.data["profiles"]["highlights"]["skills"]), highlights)
        self.assertEqual(self.data["profiles"]["highlights-prw"].get("skills", []), [])
        self.assertEqual(set(self.data["profiles"]["highlights-prw"]["include"]), {"highlights", "prw"})
        self.assertEqual(set(self.data["closure_excluded"]), CLOSURE_DENYLIST)

    def test_no_flag_install_equals_the_highlights_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            plain, named = Path(directory) / "plain", Path(directory) / "named"
            plain_result = self.install(plain)
            self.install(named, "--profile", "highlights")
            self.assertIn("Profile: highlights", plain_result.stdout)
            for component in ("skills", "commands", "agents", "scripts"):
                self.assertEqual(installed_tree(plain, component), installed_tree(named, component), component)

    def test_each_profile_installs_exactly_its_closure(self):
        targets = self.command_targets()
        for profile in self.data["profiles"]:
            with self.subTest(profile), tempfile.TemporaryDirectory() as directory:
                target = Path(directory) / "home"
                args = () if profile == self.data["default_profile"] else ("--profile", profile)
                result = self.install(target, *args)
                skills = {p.name for p in (target / "skills").iterdir()}
                expected = self.expected_skills(profile)
                self.assertEqual(skills, expected)
                self.assertFalse(DOT_FAMILY & skills)
                if profile != "web":
                    self.assertFalse(CLOSURE_DENYLIST & skills, profile)
                unavailable = self.dangling_links(target)
                self.assertLessEqual(set(unavailable.values()), CLOSURE_DENYLIST | {"<outside skills>"}, unavailable)
                installed_commands = installed_tree(target, "commands")
                commands = {c for c in installed_commands if c.endswith(".md")}
                explicit = self.profile_field(profile, "commands")
                # Aliases follow seeds (named skills and explicit-command targets), never closure-only skills.
                seeds = self.profile_field(profile, "skills") | {
                    targets[c] for c in targets if c.rsplit("/", 1)[-1][:-3] in explicit
                }
                for command in commands:
                    stem = command.rsplit("/", 1)[-1][:-3]
                    if stem not in explicit:
                        self.assertIn(targets.get(command), seeds, command)
                        self.assertTrue(self.is_alias(command, targets[command]), command)
                for command, skill in targets.items():
                    if skill in seeds and self.is_alias(command, skill):
                        self.assertIn(command, commands)
                for stem in explicit:
                    self.assertIn(f"{stem}.md", commands)
                commands_root = REPO_ROOT / ".claude/commands"
                for command in commands:
                    for reference in COMMAND_COMPANION.findall((commands_root / command).read_text()):
                        reference = reference.rstrip(".")
                        if (commands_root / reference).is_file():
                            self.assertIn(reference, installed_commands, f"{command} -> {reference}")
                self.assertIn(
                    f"Installed profile '{profile}': {len(skills)} skills, {len(commands)} commands,",
                    result.stdout,
                )
                agents = len(installed_tree(target, "agents"))
                key = "*(none)*" if profile == self.data["default_profile"] else f"`--profile {profile}`"
                for doc in ("README.md", "INSTALL.md"):
                    rows = [line for line in (REPO_ROOT / doc).read_text().splitlines() if line.startswith(f"| {key}")]
                    self.assertEqual(len(rows), 1, f"{doc} needs one {key} row")
                    self.assertTrue(
                        rows[0].endswith(f"| {len(skills)} / {len(commands)} / {agents} |"),
                        f"{doc} {key} row must state the measured counts: {rows[0]}",
                    )

    @staticmethod
    def is_alias(command: str, skill: str) -> bool:
        """Alias = stem names the skill, frontmatter says alias, or a file of at most 15 lines."""
        text = (REPO_ROOT / ".claude/commands" / command).read_text(encoding="utf-8")
        description = ""
        if text.startswith("---\n"):
            front = text[4:].split("\n---", 1)[0]
            description = next((l for l in front.splitlines() if l.startswith("description:")), "")
        return (Path(command).stem == skill or "alias" in description.lower()
                or len(text.splitlines()) <= 15)

    def profile_field(self, profile: str, field: str) -> set[str]:
        spec = self.data["profiles"][profile]
        values = set(spec.get(field, []))
        for included in spec.get("include", []):
            values |= self.profile_field(included, field)
        return values

    def dangling_links(self, target: Path) -> dict[str, str]:
        """Map each unresolved ../X/SKILL.md link in an installed tree to the missing skill."""
        skills_root = (target / "skills").resolve()
        missing = {}
        for path in skills_root.rglob("*"):
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for link in RELATIVE_SKILL_LINK.findall(text):
                resolved = Path(os.path.normpath(path.parent / link))
                if resolved.is_file():
                    continue
                try:
                    name = resolved.relative_to(skills_root).parts[0]
                except ValueError:
                    name = "<outside skills>"
                missing[f"{path.relative_to(skills_root)} -> {link}"] = name
        return missing

    def test_default_profile_installs_the_rg_alias_of_redgreen(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "home"
            self.install(target)
            self.assertTrue((target / "commands/extended-library/rg.md").is_file())
            self.assertTrue((target / "commands/extended-library/redgreen.md").is_file())

    def test_installed_skill_links_resolve_except_closure_excluded(self):
        excluded = set(self.data.get("closure_excluded", []))
        for profile in self.data["profiles"]:
            with self.subTest(profile), tempfile.TemporaryDirectory() as directory:
                target = Path(directory) / "home"
                args = () if profile == self.data["default_profile"] else ("--profile", profile)
                self.install(target, *args)
                skills_root = (target / "skills").resolve()
                unresolved = {}
                for skill_md in skills_root.glob("*/SKILL.md"):
                    for link in RELATIVE_SKILL_LINK.findall(skill_md.read_text(encoding="utf-8")):
                        resolved = Path(os.path.normpath(skill_md.parent / link))
                        if resolved.is_file():
                            continue
                        try:
                            name = resolved.relative_to(skills_root).parts[0]
                        except ValueError:
                            name = "<outside skills>"
                        if name not in excluded:
                            unresolved[f"{skill_md.parent.name} -> {link}"] = name
                self.assertEqual(unresolved, {})

    def test_usage_says_linked_dependencies_join_the_default_profile(self):
        result = subprocess.run(["bash", str(INSTALLER), "--help"], text=True, capture_output=True, check=False)
        default_line = next(line for line in result.stdout.splitlines() if "highlights profile" in line)
        self.assertIn("linked", default_line)
        self.assertNotIn("(six skills)", default_line)

    def test_web_profile_and_with_opt_in_to_browser_review_without_dot(self):
        for args in (("--profile", "web"), ("--profile", "prw", "--with", "web-advice", "--with", "browser-control")):
            with self.subTest(args), tempfile.TemporaryDirectory() as directory:
                target = Path(directory) / "home"
                self.install(target, *args)
                skills = {p.name for p in (target / "skills").iterdir()}
                self.assertTrue({"advice", "web-advice", "browser-control"} <= skills)
                self.assertFalse(DOT_FAMILY & skills)
                self.assertTrue((target / "commands/web-advice.md").is_file())

    def test_prw_profile_carries_the_pr_workflow_set(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "home"
            self.install(target, "--profile", "prw")
            for skill in ("prw", "pr-workflow", "pr-workflow-manager", "draft-first-pr", "pr-lifecycle",
                          "pr-green-definition", "ready", "advice", "evidence-standards",
                          "evidence-review", "testing-layers", "code-standards"):
                self.assertTrue((target / "skills" / skill / "SKILL.md").is_file(), skill)
            for command in ("es", "er", "green", "cs", "r.md", "smart-advisor.md", "extended-library/testing-layers.md"):
                name = command if command.endswith(".md") else f"{command}.md"
                self.assertTrue((target / "commands" / name).is_file(), command)
            for workflow in ("extended-library/polish.md", "extended-library/savetmp.md", "savetmp.py"):
                self.assertFalse((target / "commands" / workflow).exists(), workflow)
        self.assertLessEqual(self.expected_skills("prw"), self.expected_skills("highlights-prw"))

    def test_all_installs_every_skill_package(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "home"
            result = self.install(target, "--all")
            installed = {p.name for p in (target / "skills").iterdir()}
            self.assertEqual(installed, self.skill_names)
            self.assertTrue(DOT_FAMILY <= installed)
            self.assertIn(f"Installed --all (full library): {len(self.skill_names)} skills,", result.stdout)
            commands = len([c for c in installed_tree(target, "commands") if c.endswith(".md")])
            agents = len(installed_tree(target, "agents"))
            for doc in ("README.md", "INSTALL.md"):
                rows = [line for line in (REPO_ROOT / doc).read_text().splitlines() if line.startswith("| `--all`")]
                self.assertEqual(len(rows), 1, f"{doc} needs one --all row")
                self.assertTrue(
                    rows[0].endswith(f"| {len(self.skill_names)} / {commands} / {agents} |"),
                    f"{doc} --all row must state the measured counts: {rows[0]}",
                )
