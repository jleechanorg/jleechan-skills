#!/usr/bin/env python3
"""Focused integrity tests shipped beside the installed advice runner."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


RUNNER_PATH = Path(__file__).with_name("run_primary_pair.py")
SPEC = importlib.util.spec_from_file_location("advice_primary_pair", RUNNER_PATH)
assert SPEC is not None and SPEC.loader is not None
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class SourceRefIntegrityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.repo = self.root / "source"
        self.repo.mkdir()
        self.git("init", "--quiet")
        self.git("config", "user.email", "advice-test@example.invalid")
        self.git("config", "user.name", "Advice Test")
        (self.repo / "tracked.txt").write_text("original\n")
        self.git("add", "tracked.txt")
        self.git("commit", "--quiet", "-m", "base")
        self.sha = self.git("rev-parse", "HEAD").strip()
        self.packet = self.root / "packet.md"
        self.packet.write_text("Review the supplied tree.\n")

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_disk_admission_rejects_space_below_threshold(self) -> None:
        with mock.patch.object(
            runner.shutil,
            "disk_usage",
            return_value=mock.Mock(free=runner.MIN_CLONE_FREE_BYTES - 1),
        ):
            result = runner.check_clone_disk_space()

        self.assertFalse(result["sufficient"])

    def test_disk_admission_accepts_exact_threshold(self) -> None:
        with mock.patch.object(
            runner.shutil,
            "disk_usage",
            return_value=mock.Mock(free=runner.MIN_CLONE_FREE_BYTES),
        ):
            result = runner.check_clone_disk_space()

        self.assertTrue(result["sufficient"])

    def test_disk_admission_fails_closed_when_space_cannot_be_measured(self) -> None:
        with (
            mock.patch.object(
                runner.shutil, "disk_usage", side_effect=OSError("unavailable")
            ),
            self.assertRaises(runner.DiskAdmissionError),
        ):
            runner.check_clone_disk_space()

    def git(self, *args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(self.repo), *args],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
        ).stdout

    def review(self, ref: str, mutation) -> tuple[int, dict]:
        output = self.root / "output"

        def fake_lane(_cwd, _prompt, barrier, *_args):
            barrier.wait()
            mutation()
            started = time.time_ns()
            return {
                "status": "success",
                "transport": "test",
                "stdout": "VERDICT: APPROVED\n",
                "attempts": [],
                "started_ns": started,
                "ended_ns": started + 1,
            }

        with mock.patch.object(runner, "codex_lane", fake_lane):
            result = runner.main(
                [
                    "--repo",
                    str(self.repo),
                    "--ref",
                    ref,
                    "--packet-file",
                    str(self.packet),
                    "--output-dir",
                    str(output),
                    "--reviewers",
                    "codex",
                ]
            )
        receipt = json.loads((output / "receipt.json").read_text())
        return result, receipt

    def test_sibling_ref_movement_does_not_invalidate_pinned_sha(self) -> None:
        result, receipt = self.review(
            self.sha,
            lambda: self.git("update-ref", "refs/heads/sibling", self.sha),
        )

        self.assertEqual(result, 0)
        self.assertEqual(receipt["sha"], self.sha)
        self.assertTrue(receipt["original_repository_unchanged"])
        self.assertEqual(receipt["original_changed_components"], [])

    def test_requested_ref_movement_is_reported_without_changing_pinned_sha(self) -> None:
        tree = self.git("rev-parse", "HEAD^{tree}").strip()
        next_sha = subprocess.run(
            [
                "git",
                "-C",
                str(self.repo),
                "-c",
                "user.name=Advice Test",
                "-c",
                "user.email=advice-test@example.invalid",
                "commit-tree",
                tree,
                "-p",
                self.sha,
                "-m",
                "next ref target",
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
        ).stdout.strip()
        self.git("update-ref", "refs/heads/review", self.sha)

        result, receipt = self.review(
            "review",
            lambda: self.git("update-ref", "refs/heads/review", next_sha),
        )

        self.assertEqual(result, 0)
        self.assertEqual(receipt["sha"], self.sha)
        self.assertEqual(receipt["requested_ref"], "review")
        self.assertEqual(receipt["requested_ref_sha_before"], self.sha)
        self.assertEqual(receipt["requested_ref_sha_after"], next_sha)
        self.assertTrue(receipt["requested_ref_changed"])

    def test_source_checkout_mutation_still_invalidates_review(self) -> None:
        def mutate_checkout() -> None:
            (self.repo / "tracked.txt").write_text("mutated\n")

        result, receipt = self.review(self.sha, mutate_checkout)

        self.assertEqual(result, 3)
        self.assertFalse(receipt["original_repository_unchanged"])
        self.assertIn("checkout", receipt["original_changed_components"])

    def test_local_config_mutation_still_invalidates_review(self) -> None:
        result, receipt = self.review(
            self.sha,
            lambda: self.git("config", "--local", "review.test", "changed"),
        )

        self.assertEqual(result, 3)
        self.assertFalse(receipt["original_repository_unchanged"])
        self.assertIn("local_config", receipt["original_changed_components"])

    def test_effective_hook_mutation_still_invalidates_review(self) -> None:
        hooks = self.root / "hooks"
        hooks.mkdir()
        hook = hooks / "pre-commit"
        hook.write_text("#!/bin/sh\nexit 0\n")
        self.git("config", "--local", "core.hooksPath", str(hooks))

        def mutate_hook() -> None:
            hook.write_text("#!/bin/sh\nexit 1\n")

        result, receipt = self.review(self.sha, mutate_hook)

        self.assertEqual(result, 3)
        self.assertFalse(receipt["original_repository_unchanged"])
        self.assertIn("effective_hooks", receipt["original_changed_components"])


if __name__ == "__main__":
    unittest.main()
