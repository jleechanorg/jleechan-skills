"""Contract test for scripts/skill_portability_scan.py.

The scanner classifies every skill entry under a root directory into four
buckets: "proper" (a directory holding a SKILL.md with name/description
frontmatter), "improper" (a directory holding a SKILL.md with invalid or
missing name/description frontmatter, mapped to a reason string), "orphan"
(a loose <name>.md with no sibling directory), and "duplicate" (a loose
<name>.md shadowed by a sibling directory of the same name). A directory
with a SKILL.md must land in "proper" or "improper" -- never neither.

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

    def test_directory_without_frontmatter_is_improper_not_silently_dropped(self):
        directory = self.tmp_path / "delta"
        directory.mkdir()
        (directory / "SKILL.md").write_text("# delta\n\nno frontmatter\n", encoding="utf-8")
        result = scan(self.tmp_path)
        self.assertNotIn("delta", result["proper"])
        self.assertIn("delta", result["improper"])
        self.assertIn("missing name", result["improper"]["delta"])
        self.assertIn("missing description", result["improper"]["delta"])

    def test_skill_md_missing_name_is_improper_with_reason(self):
        directory = self.tmp_path / "epsilon"
        directory.mkdir()
        (directory / "SKILL.md").write_text(
            "---\ndescription: epsilon does a thing\n---\n\n# epsilon\n", encoding="utf-8"
        )
        result = scan(self.tmp_path)
        self.assertNotIn("epsilon", result["proper"])
        self.assertEqual(result["improper"]["epsilon"], "missing name")

    def test_skill_md_missing_description_is_improper_with_reason(self):
        directory = self.tmp_path / "zeta"
        directory.mkdir()
        (directory / "SKILL.md").write_text(
            "---\nname: zeta\n---\n\n# zeta\n", encoding="utf-8"
        )
        result = scan(self.tmp_path)
        self.assertNotIn("zeta", result["proper"])
        self.assertEqual(result["improper"]["zeta"], "missing description")

    def test_skill_md_empty_name_is_improper_with_reason(self):
        directory = self.tmp_path / "eta"
        directory.mkdir()
        (directory / "SKILL.md").write_text(
            "---\nname: \ndescription: eta does a thing\n---\n\n# eta\n", encoding="utf-8"
        )
        result = scan(self.tmp_path)
        self.assertNotIn("eta", result["proper"])
        self.assertEqual(result["improper"]["eta"], "empty name")

    def test_proper_directory_is_not_also_improper(self):
        make_proper(self.tmp_path, "alpha")
        result = scan(self.tmp_path)
        self.assertNotIn("alpha", result["improper"])

    def test_scanner_exposes_scan_entry_point(self):
        module = importlib.import_module("scripts.skill_portability_scan")
        self.assertTrue(callable(module.scan))


class RealSkillsRootValidityContractTest(unittest.TestCase):
    """Repository-wide contract: no active SKILL.md package is silently dropped."""

    def test_every_skill_md_directory_lands_in_proper_or_improper(self):
        real_root = REPO_ROOT / ".claude" / "skills"
        result = scan(real_root)
        classified = set(result["proper"]) | set(result["improper"])
        skill_md_dirs = {
            entry.name
            for entry in real_root.iterdir()
            if entry.is_dir() and (entry / "SKILL.md").is_file()
        }
        self.assertEqual(
            skill_md_dirs - classified,
            set(),
            msg="every directory with a SKILL.md must classify as proper or improper",
        )

    def test_improper_packages_carry_nonempty_reasons_when_present(self):
        # Any package the scanner marks improper must have an explicit, non-empty
        # reason -- it must never be silently dropped. The count itself is not
        # asserted here: it legitimately reaches zero once every active package
        # is repaired (see acceptance criteria for bd-skill-catalog-optimization-tsg.3).
        real_root = REPO_ROOT / ".claude" / "skills"
        result = scan(real_root)
        for name, reason in result["improper"].items():
            self.assertIsInstance(reason, str)
            self.assertTrue(reason, msg=f"{name} improper reason must not be empty")


if __name__ == "__main__":
    unittest.main()
