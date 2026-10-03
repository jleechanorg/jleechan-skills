"""Exercise the real opt-in installer without touching a user's agent homes."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / "portable"


class PortableInstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.target = self.root / "package"

    def install(self, *flags, target=None):
        env = dict(os.environ, PORTABLE_HOME=str(target or self.target))
        return subprocess.run(["bash", str(REPO / "install-claude-commands.sh"),
                               "--portable", *flags], env=env, capture_output=True, text=True)

    def test_complete_package_and_references(self):
        manifest = json.loads((SOURCE / "manifest.json").read_text())
        self.assertEqual(set(manifest["skills"]), {p.name for p in (SOURCE / "skills").iterdir()})
        for relative, digest in manifest["files"].items():
            path = SOURCE / relative
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)
            if path.suffix == ".md":
                for link in re.findall(r"\]\(([^)]+)\)", path.read_text()):
                    if not link.startswith(("https:", "http:", "#")):
                        self.assertTrue((path.parent / link.split("#")[0]).exists(), (path, link))
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual({p.name for p in self.target.iterdir()}, {"skills", "manifest.json"})
        for relative, digest in manifest["files"].items():
            self.assertEqual(hashlib.sha256((self.target / relative).read_bytes()).hexdigest(), digest)

    def test_refusal_and_backup_preserve_local_changes(self):
        self.assertEqual(self.install().returncode, 0)
        local = self.target / "skills/advice/SKILL.md"
        local.write_text("local edit")
        (self.target / "unrelated.txt").write_text("preserve")
        self.assertNotEqual(self.install().returncode, 0)
        self.assertEqual(local.read_text(), "local edit")
        result = self.install("--backup", target=str(self.target) + "///")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        backups = list(self.root.glob("package.backup-*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual((backups[0] / "skills/advice/SKILL.md").read_text(), "local edit")
        self.assertEqual((backups[0] / "unrelated.txt").read_text(), "preserve")

    def test_unsafe_targets_and_merge_refused(self):
        self.assertNotEqual(self.install("--merge").returncode, 0)
        self.assertFalse(self.target.exists())
        self.target.mkdir()
        (self.target / "unrelated.txt").write_text("keep")
        self.assertNotEqual(self.install("--backup").returncode, 0)
        self.assertEqual((self.target / "unrelated.txt").read_text(), "keep")
        linked = self.root / "link"
        linked.symlink_to(self.target, target_is_directory=True)
        self.assertNotEqual(self.install(target=linked).returncode, 0)
        self.assertNotEqual(self.install(target=self.root / ".agents").returncode, 0)

    def test_corrupt_or_extra_package_files_fail_verification(self):
        copied = self.root / "copy"
        shutil.copytree(SOURCE, copied)
        command = ["python3", str(REPO / "scripts/verify_portable_skills.py"), str(copied)]
        file = copied / "skills/advice/SKILL.md"
        file.write_text("corrupted")
        self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
        shutil.copyfile(SOURCE / "skills/advice/SKILL.md", file)
        (copied / "skills/extra.txt").write_text("unlisted")
        self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)


if __name__ == "__main__":
    unittest.main()
