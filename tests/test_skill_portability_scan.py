"""Contract test for scripts/skill_portability_scan.py.

The scanner classifies every skill entry under a root directory into exactly
three buckets: "proper" (a directory holding a SKILL.md with name/description
frontmatter), "orphan" (a loose <name>.md with no sibling directory), and
"duplicate" (a loose <name>.md shadowed by a sibling directory of the same name).

The scanner is imported lazily so pytest can still collect these tests while
scripts/skill_portability_scan.py does not exist yet.
"""

import importlib
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

FRONTMATTER = "---\nname: {name}\ndescription: {name} does a thing\n---\n\n# {name}\n"


def scan(root: Path) -> dict:
    return importlib.import_module("scripts.skill_portability_scan").scan(root)


def make_proper(root: Path, name: str) -> None:
    directory = root / name
    directory.mkdir(parents=True)
    (directory / "SKILL.md").write_text(FRONTMATTER.format(name=name), encoding="utf-8")


def make_loose(root: Path, name: str) -> None:
    (root / f"{name}.md").write_text(FRONTMATTER.format(name=name), encoding="utf-8")


class SkillPortabilityScanTest(unittest.TestCase):
    def setUp(self):
        self.tmp_path = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp_path, ignore_errors=True)

    def test_directory_with_valid_frontmatter_is_proper(self):
        make_proper(self.tmp_path, "alpha")
        result = scan(self.tmp_path)
        self.assertEqual(result["proper"], ["alpha"])
        self.assertEqual(result["orphan"], [])
        self.assertEqual(result["duplicate"], [])

    def test_loose_md_without_sibling_directory_is_orphan(self):
        make_loose(self.tmp_path, "beta")
        result = scan(self.tmp_path)
        self.assertEqual(result["orphan"], ["beta"])
        self.assertEqual(result["duplicate"], [])
        self.assertNotIn("beta", result["proper"])

    def test_loose_md_shadowed_by_sibling_directory_is_duplicate(self):
        make_proper(self.tmp_path, "gamma")
        make_loose(self.tmp_path, "gamma")
        result = scan(self.tmp_path)
        self.assertEqual(result["duplicate"], ["gamma"])
        self.assertEqual(result["orphan"], [])
        self.assertEqual(result["proper"], ["gamma"])

    def test_mixed_tree_separates_all_three_buckets(self):
        make_proper(self.tmp_path, "alpha")
        make_proper(self.tmp_path, "gamma")
        make_loose(self.tmp_path, "gamma")
        make_loose(self.tmp_path, "beta")
        result = scan(self.tmp_path)
        self.assertEqual(result["proper"], ["alpha", "gamma"])
        self.assertEqual(result["orphan"], ["beta"])
        self.assertEqual(result["duplicate"], ["gamma"])

    def test_directory_without_frontmatter_is_not_proper(self):
        directory = self.tmp_path / "delta"
        directory.mkdir()
        (directory / "SKILL.md").write_text("# delta\n\nno frontmatter\n", encoding="utf-8")
        result = scan(self.tmp_path)
        self.assertNotIn("delta", result["proper"])

    def test_scanner_exposes_scan_entry_point(self):
        module = importlib.import_module("scripts.skill_portability_scan")
        self.assertTrue(callable(module.scan))


if __name__ == "__main__":
    unittest.main()
