"""host-disk-guardian.sh resolves its cleanup roots without personal defaults."""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".claude" / "skills" / "host-disk-guardian" / "scripts" / "host-disk-guardian.sh"


class HostDiskGuardianEnvDefaultsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.home = self.tmp / "home"
        self.cwd = self.tmp / "cwd"
        stub_bin = self.tmp / "bin"
        for directory in (self.home, self.cwd, stub_bin):
            directory.mkdir()
        # PATH holds only the read-only tools the script needs. There is no rm,
        # gh, git, curl, or jq, so nothing can be deleted or contacted even if
        # the --dry-run guard regressed.
        for tool in ("date", "tee", "dirname", "awk", "find", "du", "id", "sed", "head", "cat"):
            found = shutil.which(tool, path="/usr/bin:/bin")
            self.assertIsNotNone(found, tool)
            (stub_bin / tool).symlink_to(found)
        # 5 GB free on / reaches the critical tier; --dry-run only reports candidates.
        stubs = {
            "df": "echo 'Filesystem 1G-blocks Used Available'; echo '/dev/stub 100 95 5'",
            "hostname": "echo stub-host",
        }
        for name, body in stubs.items():
            (stub_bin / name).write_text(f"#!/bin/sh\n{body}\n")
            (stub_bin / name).chmod(0o755)
        self.env = {
            "HOME": str(self.home),
            "PATH": str(stub_bin),
            "LANG": "C",
            "HOST_DISK_GUARDIAN_LOG": str(self.tmp / "guardian.log"),
        }

    def run_guardian(self, **extra):
        return subprocess.run(
            ["bash", str(SCRIPT), "--dry-run"],
            cwd=self.cwd,
            env={**self.env, **extra},
            capture_output=True,
            text=True,
            timeout=60,
        )

    def test_unset_roots_skip_with_not_configured_and_scratchpad_is_derived(self):
        proc = self.run_guardian()
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("HOST_DISK_GUARDIAN_EVIDENCE_DIR not configured", proc.stdout)
        self.assertIn("HOST_DISK_GUARDIAN_WORKTREE_GLOB not configured", proc.stdout)
        self.assertIn(f"/tmp/claude-{os.getuid()}", proc.stdout)

    def test_configured_roots_win(self):
        evidence = self.tmp / "evidence"
        scratch = self.tmp / "scratch"
        old_bundle = evidence / "bundle-1"
        old_scratch = scratch / "session-1"
        for directory in (old_bundle, old_scratch):
            directory.mkdir(parents=True)
            os.utime(directory, (0, 0))
        proc = self.run_guardian(
            HOST_DISK_GUARDIAN_EVIDENCE_DIR=str(evidence),
            HOST_DISK_GUARDIAN_SCRATCHPAD_DIR=str(scratch),
        )
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn(f"would delete evidence bundle: {old_bundle}", proc.stdout)
        self.assertIn(f"would delete scratchpad: {old_scratch}", proc.stdout)

    def test_worktree_cleanup_requires_repository(self):
        glob = str(self.tmp / "wt-*")
        proc = self.run_guardian(HOST_DISK_GUARDIAN_WORKTREE_GLOB=glob)
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("GITHUB_REPOSITORY not configured", proc.stdout)

        # With the repository set, cleanup proceeds to its next gate (gh is not on PATH).
        proc = self.run_guardian(HOST_DISK_GUARDIAN_WORKTREE_GLOB=glob, GITHUB_REPOSITORY="acme/widgets")
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertNotIn("GITHUB_REPOSITORY not configured", proc.stdout)
        self.assertIn("gh CLI not available", proc.stdout)


if __name__ == "__main__":
    unittest.main()
