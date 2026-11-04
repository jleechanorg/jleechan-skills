"""The callpath dark-factory profile requires DARK_FACTORY_HOME instead of assuming a checkout."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CALLPATH = ROOT / ".claude" / "skills" / "callpath" / "bin" / "callpath.py"


class CallpathDarkFactoryEnvDefaultsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.home = self.tmp / "home"
        # A checkout at the old hardcoded location must not be picked up.
        (self.home / "projects" / "dark-factory").mkdir(parents=True)
        self.env = {"HOME": str(self.home), "PATH": "/usr/bin:/bin", "LANG": "C"}

    def run_profile(self, *args, **extra):
        return subprocess.run(
            [sys.executable, str(CALLPATH), "run", "dark-factory", *args],
            cwd=self.tmp,
            env={**self.env, **extra},
            capture_output=True,
            text=True,
            timeout=60,
        )

    def test_unset_home_fails_naming_variable(self):
        proc = self.run_profile()
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("DARK_FACTORY_HOME not configured", proc.stderr)

    def test_configured_home_is_used(self):
        df_home = self.tmp / "df"
        df_home.mkdir()
        proc = self.run_profile("--help", DARK_FACTORY_HOME=str(df_home))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn(f"DARK_FACTORY_HOME={df_home}", proc.stdout)


if __name__ == "__main__":
    unittest.main()
