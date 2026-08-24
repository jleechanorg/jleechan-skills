"""Contract test for scripts/skill_portability_scan.py.

The scanner classifies every skill entry under a root directory into exactly
three buckets: "proper" (a directory holding a SKILL.md with name/description
frontmatter), "orphan" (a loose <name>.md with no sibling directory), and
"duplicate" (a loose <name>.md shadowed by a sibling directory of the same name).

The scanner is imported lazily so pytest can still collect these tests while
scripts/skill_portability_scan.py does not exist yet.
"""

import importlib
import sys
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


def test_directory_with_valid_frontmatter_is_proper(tmp_path):
    make_proper(tmp_path, "alpha")
    result = scan(tmp_path)
    assert result["proper"] == ["alpha"]
    assert result["orphan"] == []
    assert result["duplicate"] == []


def test_loose_md_without_sibling_directory_is_orphan(tmp_path):
    make_loose(tmp_path, "beta")
    result = scan(tmp_path)
    assert result["orphan"] == ["beta"]
    assert result["duplicate"] == []
    assert "beta" not in result["proper"]


def test_loose_md_shadowed_by_sibling_directory_is_duplicate(tmp_path):
    make_proper(tmp_path, "gamma")
    make_loose(tmp_path, "gamma")
    result = scan(tmp_path)
    assert result["duplicate"] == ["gamma"]
    assert result["orphan"] == []
    assert result["proper"] == ["gamma"]


def test_mixed_tree_separates_all_three_buckets(tmp_path):
    make_proper(tmp_path, "alpha")
    make_proper(tmp_path, "gamma")
    make_loose(tmp_path, "gamma")
    make_loose(tmp_path, "beta")
    result = scan(tmp_path)
    assert result["proper"] == ["alpha", "gamma"]
    assert result["orphan"] == ["beta"]
    assert result["duplicate"] == ["gamma"]


def test_directory_without_frontmatter_is_not_proper(tmp_path):
    directory = tmp_path / "delta"
    directory.mkdir()
    (directory / "SKILL.md").write_text("# delta\n\nno frontmatter\n", encoding="utf-8")
    result = scan(tmp_path)
    assert "delta" not in result["proper"]


def test_scanner_exposes_scan_entry_point():
    module = importlib.import_module("scripts.skill_portability_scan")
    assert callable(module.scan)
