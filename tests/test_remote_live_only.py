"""Focused executable tests for PR #703's remote live-only scan."""

import argparse
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.sync_live_config import FileEvidence, cmd_report, evidence_remote_live_only


class RemoteLiveOnlyTest(unittest.TestCase):
    def _scan(self, remote_home: Path, environment: dict[str, str] | None = None):
        rows, _warnings = self._scan_full(remote_home, environment)
        return rows

    def _scan_full(self, remote_home: Path, environment: dict[str, str] | None = None,
                   files: list[str] | None = None, full: bool = False,
                   exclude: set[str] | None = None):
        actual_run = subprocess.run

        def fake_ssh_run(command, **kwargs):
            if command[0] == "ssh" and "printf" in command:
                return subprocess.CompletedProcess(command, 0, stdout=str(remote_home), stderr="")
            if command[0] == "ssh" and "bash" in command:
                result = actual_run(
                    ["/bin/bash", "-s"],
                    input=kwargs["input"],
                    capture_output=True,
                    text=True,
                    env=environment,
                )
                return result
            raise AssertionError(f"unexpected subprocess call: {command}")

        warnings: list[str] = []
        with patch("scripts.sync_live_config.subprocess.run", side_effect=fake_ssh_run):
            rows = evidence_remote_live_only(
                Path("."),
                files or [".claude/skills/fixture/SKILL.md"],
                "testhost", full, set(exclude or ()), warnings,
            )
        return rows, warnings

    def test_root_symlink_is_reported_without_enumerating_target_children(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            remote = root / "remote-home"
            target = root / "private-target"
            (remote / ".claude" / "skills").mkdir(parents=True)
            target.mkdir()
            (target / "PRIVATE_TARGET_NAME.md").write_text("private name\n")
            (remote / ".claude" / "skills" / "fixture").symlink_to(target, target_is_directory=True)

            results = self._scan(remote)

        self.assertEqual([(item.status, item.live_rel) for item in results], [
            ("symlink", ".claude/skills/fixture")
        ])

    def test_symlinked_parent_is_reported_without_enumerating_target_children(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            remote = root / "remote-home"
            target = root / "private-target"
            (remote / ".claude").mkdir(parents=True)
            (target / "fixture").mkdir(parents=True)
            (target / "fixture" / "PRIVATE_TARGET_NAME.md").write_text("private name\n")
            (remote / ".claude" / "skills").symlink_to(target, target_is_directory=True)

            results = self._scan(remote)

        self.assertEqual([(item.status, item.live_rel) for item in results], [
            ("symlink", ".claude/skills/fixture")
        ])

    def test_find_failure_warns_and_preserves_partial_rows_and_tracked_results(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            remote = root / "remote-home"
            base = remote / ".claude" / "skills" / "fixture"
            base.mkdir(parents=True)
            (root / "README.md").write_text("# Fixture skills\n")
            (base / "partial.md").write_text("partial\n")
            fake_bin = root / "bin"
            fake_bin.mkdir()
            fake_find = fake_bin / "find"
            fake_find.write_text("#!/bin/sh\nprintf '%s\\0' \"$1/partial.md\"\nexit 1\n")
            fake_find.chmod(0o755)
            env = dict(os.environ)
            env["PATH"] = f"{fake_bin}:/usr/bin:/bin"

            output = io.StringIO()
            errors = io.StringIO()
            tracked = FileEvidence(
                repo_rel=".claude/skills/fixture/SKILL.md",
                live_rel=".claude/skills/fixture/SKILL.md",
                status="ok",
            )
            with (
                patch("scripts.sync_live_config.repo_root", return_value=root),
                patch("scripts.sync_live_config.collect_core_scope", return_value=[".claude/skills/fixture/SKILL.md"]),
                patch("scripts.sync_live_config.parse_highlighted_skill_dirs", return_value=[]),
                patch("scripts.sync_live_config.evidence_remote", return_value=[tracked]),
                patch("scripts.sync_live_config.subprocess.run", side_effect=self._fake_find_ssh(remote, env)),
                patch("sys.stdout", output),
                patch("sys.stderr", errors),
            ):
                status = cmd_report(
                    argparse.Namespace(home=None, full=False, remote_only=True, remote=["testhost"], json=True)
                )
            data = json.loads(output.getvalue())
            rows = data["targets"]["remote:testhost"]

        self.assertEqual(status, 0)
        self.assertIn('"status": "ok"', json.dumps(rows))
        self.assertIn('"status": "live_only"', json.dumps(rows))
        self.assertIn("warning: remote live_only scan incomplete on testhost", errors.getvalue())

    def _fake_find_ssh(self, remote_home: Path, environment: dict[str, str]):
        actual_run = subprocess.run

        def fake_ssh_run(command, **kwargs):
            if command[0] == "ssh" and "printf" in command:
                return subprocess.CompletedProcess(command, 0, stdout=str(remote_home), stderr="")
            if command[0] == "ssh" and "bash" in command:
                return actual_run(
                    ["/bin/bash", "-s"],
                    input=kwargs["input"],
                    capture_output=True,
                    text=True,
                    env=environment,
                )
            raise AssertionError(f"unexpected subprocess call: {command}")

        return fake_ssh_run

    def test_live_only_file_in_nested_repo_includes_remote_history(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            remote = root / "remote-home"
            nested_repo = remote / ".claude" / "skills" / "fixture"
            nested_repo.mkdir(parents=True)
            live_file = nested_repo / "live-only.md"
            live_file.write_text("independently committed live file\n")
            subprocess.run(["git", "init", str(nested_repo)], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(nested_repo), "config", "user.name", "Fixture"], check=True)
            subprocess.run(["git", "-C", str(nested_repo), "config", "user.email", "fixture@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(nested_repo), "add", "live-only.md"], check=True)
            subprocess.run(["git", "-C", str(nested_repo), "commit", "-m", "fixture live file"], check=True, capture_output=True)
            expected_commit = subprocess.check_output(
                ["git", "-C", str(nested_repo), "rev-parse", "HEAD"], text=True
            ).strip()[:12]

            results = self._scan(remote)

        result = next(item for item in results if item.live_rel == ".claude/skills/fixture/live-only.md")
        self.assertEqual(result.status, "live_only")
        self.assertEqual(result.live_repo_root, f"testhost:{nested_repo}")
        self.assertEqual(result.live_last_commit["sha"], expected_commit)

    def test_full_scan_prunes_runtime_dirs_without_traversing_them(self):
        """--full must not walk RUNTIME_DIRS subtrees at all, exactly like local.

        The `projects` subtree is made unreadable: a walk that descends into it
        fails and surfaces an incomplete-scan warning, while a walk that prunes
        it never opens the directory. The `node_modules` sentinel catches a
        filter-after-traversal implementation on hosts that ignore the mode.
        """
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            remote = root / "remote-home"
            claude = remote / ".claude"
            claude.mkdir(parents=True)
            (claude / "CLAUDE.md").write_text("ordinary live config\n")
            runtime = claude / "projects"
            runtime.mkdir()
            (runtime / "TRANSCRIPT_SENTINEL.jsonl").write_text("sentinel\n")
            modules = claude / "node_modules"
            modules.mkdir()
            (modules / "MODULE_SENTINEL.js").write_text("sentinel\n")
            os.chmod(runtime, 0)
            try:
                rows, warnings = self._scan_full(remote, full=True)
            finally:
                os.chmod(runtime, 0o755)

        self.assertEqual([(item.status, item.live_rel) for item in rows], [
            ("live_only", ".claude/CLAUDE.md")
        ])
        self.assertEqual(warnings, [])

    def test_live_only_names_with_newline_and_framing_bytes_round_trip_exactly(self):
        """A live filename is opaque bytes: newline / FS / RS / GS in a name must
        survive as one exact row, never split into fabricated rows or records."""
        names = [
            "plain.md",
            "line\nbreak.md",
            "field\x1fsep.md",
            "record\x1esep.md",
            "group\x1dsep.md",
        ]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            remote = root / "remote-home"
            fixture = remote / ".claude" / "skills" / "fixture"
            fixture.mkdir(parents=True)
            for name in names:
                (fixture / name).write_text("live\n")
            secret = root / "SECRET_TARGET_NAME"
            secret.write_text("secret\n")
            (fixture / "link\nsym").symlink_to(secret)

            rows, warnings = self._scan_full(remote)

        live_only = sorted(item.live_rel for item in rows if item.status == "live_only")
        symlinks = sorted(item.live_rel for item in rows if item.status == "symlink")
        self.assertEqual(live_only, sorted(f".claude/skills/fixture/{name}" for name in names))
        self.assertEqual(symlinks, [".claude/skills/fixture/link\nsym"])
        self.assertEqual(warnings, [])


if __name__ == "__main__":
    unittest.main()
