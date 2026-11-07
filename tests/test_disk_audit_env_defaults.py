"""disk-audit.sh finds the audit script through USER_SCOPE_ROOT, never a fixed checkout."""

import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".claude" / "skills" / "disk-audit" / "disk-audit.sh"


class DiskAuditEnvDefaultsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.env = {"HOME": str(self.home), "PATH": "/usr/bin:/bin", "LANG": "C"}

    def run_wrapper(self, *args, **extra):
        return subprocess.run(
            ["bash", str(SCRIPT), *args],
            cwd=self.tmp,
            env={**self.env, **extra},
            capture_output=True,
            text=True,
            timeout=30,
        )

    def test_unset_user_scope_root_fails_naming_variable(self):
        # Even a checkout at the old hardcoded location must not be picked up.
        legacy = self.home / "projects_other" / "user_scope" / "scripts" / "disk_audit.sh"
        legacy.parent.mkdir(parents=True)
        legacy.write_text("#!/bin/sh\necho legacy-ran\n")
        legacy.chmod(0o755)
        proc = self.run_wrapper()
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("USER_SCOPE_ROOT", proc.stderr)
        self.assertNotIn("legacy-ran", proc.stdout)

    def test_configured_root_runs_audit_with_default_args(self):
        root = self.tmp / "scope"
        audit = root / "scripts" / "disk_audit.sh"
        audit.parent.mkdir(parents=True)
        audit.write_text('#!/bin/sh\necho "audit:$*"\n')
        audit.chmod(0o755)
        proc = self.run_wrapper(USER_SCOPE_ROOT=str(root))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "audit:--clean --dry-run")


if __name__ == "__main__":
    unittest.main()
