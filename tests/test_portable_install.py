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

    def test_manifest_skill_scope_survives_optimization(self):
        for optimize in ("0", "1"):
            for case in ("added", "omitted", "missing_entry"):
                with self.subTest(optimize=optimize, case=case):
                    copied = self.root / ("copy-" + optimize + case)
                    shutil.copytree(SOURCE, copied)
                    path = copied / "manifest.json"
                    manifest = json.loads(path.read_text())
                    if case == "added":
                        manifest["skills"].append("nonexistent")
                    elif case == "omitted":
                        manifest["skills"].remove("advice")
                    else:
                        (copied / "skills/advice/SKILL.md").unlink()
                        del manifest["files"]["skills/advice/SKILL.md"]
                    path.write_text(json.dumps(manifest))
                    result = subprocess.run(
                        ["python3", str(REPO / "scripts/verify_portable_skills.py"), str(copied)],
                        env=dict(os.environ, PYTHONOPTIMIZE=optimize), capture_output=True, text=True)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("Missing SKILL.md" if case == "missing_entry" else "Skill list differs",
                                  result.stderr)

    def test_custom_canonical_home_is_preserved_under_optimization(self):
        shutil.copytree(SOURCE, self.target)
        sentinel = self.target / "local.txt"
        sentinel.write_text("keep canonical home")
        alias = self.root / "canonical-alias"
        alias.symlink_to(self.target, target_is_directory=True)
        for optimize in ("0", "1"):
            for canonical in (self.target, alias):
                with self.subTest(optimize=optimize, canonical=canonical):
                    result = subprocess.run(
                        ["bash", str(REPO / "install-claude-commands.sh"), "--portable", "--backup"],
                        env=dict(os.environ, PYTHONOPTIMIZE=optimize, CLAUDE_HOME=str(canonical),
                                 PORTABLE_HOME=str(self.target)), capture_output=True, text=True)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("equals configured CLAUDE_HOME", result.stderr)
                    self.assertEqual(sentinel.read_text(), "keep canonical home")
                    self.assertEqual(list(self.root.glob("package.backup-*")), [])

    def test_integrity_and_target_gates_survive_optimization(self):
        fixture = self.root / "fixture"
        (fixture / "scripts").mkdir(parents=True)
        shutil.copyfile(REPO / "install-claude-commands.sh", fixture / "install-claude-commands.sh")
        shutil.copyfile(REPO / "scripts/verify_portable_skills.py",
                        fixture / "scripts/verify_portable_skills.py")
        shutil.copytree(SOURCE, fixture / "portable")
        skill = fixture / "portable/skills/advice/SKILL.md"
        original = skill.read_bytes()
        extra = fixture / "portable/skills/unlisted.txt"
        for optimize in ("0", "1"):
            for case in ("corruption", "inventory", "target"):
                with self.subTest(optimize=optimize, case=case):
                    skill.write_bytes(original)
                    if extra.exists():
                        extra.unlink()
                    target = self.root / (".agents" if case == "target" else "output")
                    if case == "corruption":
                        skill.write_text("corrupted")
                    elif case == "inventory":
                        extra.write_text("unlisted")
                    env = dict(os.environ, PYTHONOPTIMIZE=optimize, PORTABLE_HOME=str(target))
                    result = subprocess.run(
                        ["bash", str(fixture / "install-claude-commands.sh"), "--portable"],
                        env=env, capture_output=True, text=True)
                    self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn("Portable verification failed", result.stderr)
                    self.assertFalse(target.exists(), "Rejected install must not create its target")


if __name__ == "__main__":
    unittest.main()
