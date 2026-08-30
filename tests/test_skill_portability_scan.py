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
import os
import shutil
import subprocess
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
        # Prove the universal contract invariant: tolerates zero improper packages
        # (empty mapping) as well as any populated mapping of string reasons.
        def assert_improper_mapping_contract(mapping: dict) -> None:
            self.assertIsInstance(mapping, dict)
            for name, reason in mapping.items():
                self.assertIsInstance(reason, str)
                self.assertTrue(reason, msg=f"{name} improper reason must not be empty")

        with tempfile.TemporaryDirectory() as empty_dir:
            empty_result = scan(Path(empty_dir))
            self.assertEqual(empty_result["improper"], {})
            assert_improper_mapping_contract(empty_result["improper"])

        real_root = REPO_ROOT / ".claude" / "skills"
        result = scan(real_root)
        assert_improper_mapping_contract(result["improper"])


class PolicyFilesContractTest(unittest.TestCase):
    """Regression test for command and skill policy files."""

    def test_er_command_and_draft_first_pr_skill_contracts(self):
        er_path = REPO_ROOT / ".claude" / "commands" / "er.md"
        er_content = er_path.read_text(encoding="utf-8")
        self.assertIn("evidence-review/SKILL.md", er_content)
        self.assertIn("draft-first-pr/SKILL.md", er_content)
        self.assertNotIn("Two-Tier Verdicts", er_content)

        draft_pr_path = REPO_ROOT / ".claude" / "skills" / "draft-first-pr" / "SKILL.md"
        draft_pr_content = draft_pr_path.read_text(encoding="utf-8")
        self.assertIn("gh api", draft_pr_content)
        self.assertIn("clone_url", draft_pr_content)
        self.assertIn("${BASE_REMOTE}/${BASE_BRANCH}...HEAD", draft_pr_content)
        self.assertNotIn("origin/$BASE_BRANCH...HEAD", draft_pr_content)
        self.assertNotIn("origin/${BASE_BRANCH}...HEAD", draft_pr_content)
        self.assertNotIn("origin/main...HEAD", draft_pr_content)

    def test_documented_base_resolution_works_without_origin_or_main(self):
        skill_path = REPO_ROOT / ".claude" / "skills" / "draft-first-pr" / "SKILL.md"
        skill_content = skill_path.read_text(encoding="utf-8")
        section = skill_content.split("### Documentation-only exception", 1)[1]
        script = section.split("```bash\n", 1)[1].split("\n```", 1)[0]

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            remote_path = root / "example" / "skills.git"
            remote_path.parent.mkdir()
            subprocess.run(["git", "init", "--bare", remote_path], check=True, capture_output=True)

            repo = root / "repo"
            subprocess.run(["git", "init", repo], check=True, capture_output=True)
            for key, value in (("user.email", "fixture@localhost"), ("user.name", "Test User")):
                subprocess.run(["git", "-C", repo, "config", key, value], check=True, capture_output=True)
            (repo / "README.md").write_text("base\n", encoding="utf-8")
            subprocess.run(["git", "-C", repo, "add", "README.md"], check=True, capture_output=True)
            subprocess.run(["git", "-C", repo, "commit", "-m", "base"], check=True, capture_output=True)
            subprocess.run(["git", "-C", repo, "remote", "add", "upstream", remote_path], check=True, capture_output=True)
            subprocess.run(["git", "-C", repo, "push", "upstream", "HEAD:release"], check=True, capture_output=True)
            (repo / "README.md").write_text("feature\n", encoding="utf-8")
            subprocess.run(["git", "-C", repo, "commit", "-am", "feature"], check=True, capture_output=True)

            bin_dir = root / "bin"
            bin_dir.mkdir()
            fake_gh = bin_dir / "gh"
            fake_gh.write_text(
                "#!/usr/bin/env bash\n"
                "case \"$*\" in\n"
                "  *baseRepository*) exit 64 ;;\n"
                f"  api\\ *) printf 'release\\t{remote_path}\\t{remote_path}\\n' ;;\n"
                "  *) printf '42\\n' ;;\n"
                "esac\n",
                encoding="utf-8",
            )
            fake_gh.chmod(0o755)
            env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"}
            result = subprocess.run(
                ["bash", "-c", script, "base-resolution", "42"],
                cwd=repo,
                env=env,
                text=True,
                capture_output=True,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "README.md")

    def test_documented_base_resolution_rejects_same_repo_on_foreign_host(self):
        skill_path = REPO_ROOT / ".claude" / "skills" / "draft-first-pr" / "SKILL.md"
        skill_content = skill_path.read_text(encoding="utf-8")
        section = skill_content.split("### Documentation-only exception", 1)[1]
        script = section.split("```bash\n", 1)[1].split("\n```", 1)[0]

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            approved_root = root / "approved.example"
            foreign_root = root / "foreign.example"
            approved_bare = approved_root / "example" / "skills.git"
            foreign_bare = foreign_root / "example" / "skills.git"
            approved_bare.parent.mkdir(parents=True)
            foreign_bare.parent.mkdir(parents=True)
            subprocess.run(["git", "init", "--bare", approved_bare], check=True, capture_output=True)
            subprocess.run(["git", "init", "--bare", foreign_bare], check=True, capture_output=True)

            repo = root / "repo"
            subprocess.run(["git", "init", repo], check=True, capture_output=True)
            for key, value in (
                ("user.email", "fixture@localhost"),
                ("user.name", "Test User"),
                (f"url.file://{approved_root}/.insteadOf", "https://approved.example/"),
                (f"url.file://{foreign_root}/.insteadOf", "https://foreign.example/"),
            ):
                subprocess.run(["git", "-C", repo, "config", key, value], check=True, capture_output=True)
            (repo / "README.md").write_text("base\n", encoding="utf-8")
            subprocess.run(["git", "-C", repo, "add", "README.md"], check=True, capture_output=True)
            subprocess.run(["git", "-C", repo, "commit", "-m", "base"], check=True, capture_output=True)
            subprocess.run(
                ["git", "-C", repo, "remote", "add", "a-foreign", "https://foreign.example/example/skills.git"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", repo, "remote", "add", "z-upstream", "https://approved.example/example/skills.git"],
                check=True,
                capture_output=True,
            )
            subprocess.run(["git", "-C", repo, "push", "z-upstream", "HEAD:release"], check=True, capture_output=True)
            (repo / "README.md").write_text("feature\n", encoding="utf-8")
            subprocess.run(["git", "-C", repo, "commit", "-am", "feature"], check=True, capture_output=True)

            bin_dir = root / "bin"
            bin_dir.mkdir()
            fake_gh = bin_dir / "gh"
            fake_gh.write_text(
                "#!/usr/bin/env bash\n"
                "case \"$*\" in\n"
                "  *baseRepository*) exit 64 ;;\n"
                "  api\\ *) printf 'release\\thttps://approved.example/example/skills.git"
                "\\tgit@approved.example:example/skills.git\\n' ;;\n"
                "  *) printf '42\\n' ;;\n"
                "esac\n",
                encoding="utf-8",
            )
            fake_gh.chmod(0o755)
            env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"}
            result = subprocess.run(
                ["bash", "-c", script, "base-resolution", "42"],
                cwd=repo,
                env=env,
                text=True,
                capture_output=True,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "README.md")


if __name__ == "__main__":
    unittest.main()
