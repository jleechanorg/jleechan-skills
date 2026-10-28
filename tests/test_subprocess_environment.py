"""Tests for fake-home subprocess environment setup."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.subprocess_environment import isolated_home_environment


class IsolatedHomeEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.host_home = self.root / "host"
        self.fake_home = self.root / "fake"
        self.user_bin = self.host_home / ".local" / "bin"
        self.user_bin.mkdir(parents=True)
        self.fake_home.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def test_relative_user_bin_entry_is_fallback_from_child_cwd(self):
        child_cwd = self.root / "child"
        child_cwd.mkdir()
        relative_user_bin = os.path.relpath(self.user_bin, child_cwd)
        path = os.pathsep.join((relative_user_bin, "/usr/bin"))

        with patch.dict(os.environ, {"HOME": str(self.host_home), "PATH": path}):
            environment = isolated_home_environment(self.fake_home, cwd=child_cwd)

        self.assertEqual(
            environment["PATH"].split(os.pathsep), ["/usr/bin", relative_user_bin]
        )

    def test_empty_entry_is_classified_against_child_cwd(self):
        path = os.pathsep.join(("", "/usr/bin"))

        with patch.dict(os.environ, {"HOME": str(self.host_home), "PATH": path}):
            environment = isolated_home_environment(self.fake_home, cwd=self.user_bin)

        self.assertEqual(environment["PATH"].split(os.pathsep), ["/usr/bin", ""])

    def test_relative_symlink_to_user_bin_is_fallback(self):
        child_cwd = self.root / "child"
        child_cwd.mkdir()
        alias = child_cwd / "wrapper-bin"
        alias.symlink_to(os.path.relpath(self.user_bin, child_cwd), target_is_directory=True)

        with patch.dict(
            os.environ,
            {"HOME": str(self.host_home), "PATH": os.pathsep.join((alias.name, "/usr/bin"))},
        ):
            environment = isolated_home_environment(self.fake_home, cwd=child_cwd)

        self.assertEqual(environment["PATH"].split(os.pathsep), ["/usr/bin", alias.name])

    def test_absent_path_remains_absent(self):
        with patch.dict(os.environ, {"HOME": str(self.host_home)}, clear=True):
            environment = isolated_home_environment(self.fake_home)

        self.assertNotIn("PATH", environment)


if __name__ == "__main__":
    unittest.main()
