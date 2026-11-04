"""host-disk-guardian.sh resolves its cleanup roots without personal defaults."""

import os
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
        # 5 GB free on / forces the critical (auto-clean) path; --dry-run deletes nothing.
        df = stub_bin / "df"
        df.write_text("#!/bin/sh\necho 'Filesystem 1G-blocks Used Available'\necho '/dev/stub 100 95 5'\n")
        df.chmod(0o755)
        self.env = {"HOME": str(self.home), "PATH": f"{stub_bin}:/usr/bin:/bin", "LANG": "C"}

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
