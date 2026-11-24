import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / ".claude" / "skills" / "oneoff-deletes" / "scripts"


def _age(path: Path, hours: float) -> None:
    ts = time.time() - hours * 3600
    for p in [path, *path.rglob("*")]:
        os.utime(p, (ts, ts), follow_symlinks=False)


class OneOffDeletesScripts(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(os.path.realpath(self._tmp.name)) / "root"
        self.root.mkdir()
        self.work = Path(os.path.realpath(self._tmp.name)) / "work"
        self.work.mkdir()
        self.old_dir = self.root / "old-dir"
        (self.old_dir / "sub").mkdir(parents=True)
        (self.old_dir / "sub" / "f.txt").write_text("x")
        self.old_file = self.root / "old.log"
        self.old_file.write_text("x")
        self.new_dir = self.root / "new-dir"
        self.new_dir.mkdir()
        (self.new_dir / "f.txt").write_text("x")
        self.mixed = self.root / "mixed"
        self.mixed.mkdir()
        (self.mixed / "old-child").mkdir()
        (self.mixed / "new-child").mkdir()
        _age(self.old_dir, 10)
        _age(self.old_file, 10)
        _age(self.mixed / "old-child", 10)
        (self.work / "open.txt").write_text("")
        # ctime cannot be back-dated, so fixtures check mtime only
        self.env = {**os.environ, "ROOTS": str(self.root), "OPEN_LIST": str(self.work / "open.txt"), "CTIME": "0"}

    def _run(self, script, *args, **extra):
        env = {**self.env, **extra}
        return subprocess.run(["bash", str(SCRIPTS / script), *args], env=env, capture_output=True, text=True)

    def test_qualify_depth1_returns_only_old_entries(self):
        out = self._run("qualify.sh").stdout.split("\n")
        self.assertIn(str(self.old_dir), out)
        self.assertIn(str(self.old_file), out)
        self.assertNotIn(str(self.new_dir), out)
        self.assertNotIn(str(self.mixed), out)

    def test_qualify_depth2_finds_old_child_of_active_dir(self):
        out = self._run("qualify.sh", DEPTH="2").stdout.split("\n")
        self.assertIn(str(self.mixed / "old-child"), out)
        self.assertNotIn(str(self.mixed / "new-child"), out)
        self.assertNotIn(str(self.old_dir / "sub"), out)

    def test_delete_entry_removes_old_and_keeps_new(self):
        self.assertIn("DELETED", self._run("delete_entry.sh", str(self.old_dir)).stdout)
        self.assertFalse(self.old_dir.exists())
        self.assertIn("SKIP-new", self._run("delete_entry.sh", str(self.new_dir)).stdout)
        self.assertTrue(self.new_dir.exists())

    def test_delete_entry_refuses_paths_outside_roots(self):
        outside = Path(self._tmp.name) / "outside.txt"
        outside.write_text("x")
        _age(outside, 10)
        self.assertIn("SKIP-bad", self._run("delete_entry.sh", str(outside)).stdout)
        self.assertTrue(outside.exists())
        self.assertIn("SKIP-bad", self._run("delete_entry.sh", str(self.root) + "/../outside.txt").stdout)

    def test_delete_entry_honors_exclude(self):
        res = self._run("delete_entry.sh", str(self.old_file), EXCLUDE="*/old.log")
        self.assertIn("SKIP-excluded", res.stdout)
        self.assertTrue(self.old_file.exists())

    def test_delete_entry_skips_entry_with_open_file(self):
        holder = subprocess.Popen(["tail", "-f", str(self.old_dir / "sub" / "f.txt")], stdout=subprocess.DEVNULL)
        self.addCleanup(holder.wait)
        self.addCleanup(holder.kill)
        time.sleep(0.5)
        self.assertEqual(self._run("qualify.sh").returncode, 0)
        res = self._run("delete_entry.sh", str(self.old_dir))
        self.assertIn("SKIP-open", res.stdout)
        self.assertTrue(self.old_dir.exists())


if __name__ == "__main__":
    unittest.main()
