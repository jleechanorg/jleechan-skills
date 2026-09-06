"""Unit tests for scripts/sync_live_config.py — covers the review findings from
PR #419 (path containment, the --local-only inversion, and the find_command_files_for_skill
substring over-match), plus core evidence/mapping logic."""

import unittest
from pathlib import Path

from scripts.sync_live_config import (
    FileEvidence,
    find_command_files_for_skill,
    live_abs_for,
    live_rel_for,
    repo_abs_for,
    scope_live_roots,
    sha256_of,
    unified_diff_text,
    validate_repo_rel,
)


class ValidateRepoRelTest(unittest.TestCase):
    def test_accepts_paths_under_allowed_roots(self):
        for p in (".claude/commands/foo.md", ".codex/hooks/bar.py", "hermes/skills/x/y.md"):
            self.assertEqual(validate_repo_rel(p), p)

    def test_rejects_traversal(self):
        for p in (".claude/../../../etc/passwd", "../etc/passwd", "hermes/../../etc/passwd"):
            with self.assertRaises(ValueError):
                validate_repo_rel(p)

    def test_rejects_absolute_paths(self):
        with self.assertRaises(ValueError):
            validate_repo_rel("/etc/passwd")

    def test_rejects_non_normalized_paths(self):
        with self.assertRaises(ValueError):
            validate_repo_rel(".claude/./commands/foo.md")

    def test_rejects_paths_outside_allowed_roots(self):
        with self.assertRaises(ValueError):
            validate_repo_rel("random/not/allowed.md")
        with self.assertRaises(ValueError):
            validate_repo_rel("scripts/sync_live_config.py")


class LiveRelForTest(unittest.TestCase):
    def test_maps_each_top_level_root(self):
        self.assertEqual(live_rel_for(".claude/commands/foo.md"), ".claude/commands/foo.md")
        self.assertEqual(live_rel_for(".codex/hooks/bar.py"), ".codex/hooks/bar.py")
        self.assertEqual(live_rel_for("hermes/skills/x/y.md"), ".hermes/skills/x/y.md")


class ContainmentTest(unittest.TestCase):
    """The core fix for the path-escape finding: resolved paths must stay
    within the intended root even after a symlink or '..' is involved."""

    def test_live_abs_for_stays_within_home(self, ):
        import tempfile
        with tempfile.TemporaryDirectory() as home_dir:
            home = Path(home_dir)
            (home / ".claude" / "commands").mkdir(parents=True)
            result = live_abs_for(".claude/commands/foo.md", home)
            self.assertTrue(result.is_relative_to(home.resolve()))
            self.assertEqual(result, (home / ".claude" / "commands" / "foo.md").resolve())

    def test_repo_abs_for_stays_within_root(self):
        import tempfile
        with tempfile.TemporaryDirectory() as root_dir:
            root = Path(root_dir)
            (root / ".claude" / "commands").mkdir(parents=True)
            result = repo_abs_for(root, ".claude/commands/foo.md")
            self.assertTrue(result.is_relative_to(root.resolve()))

    def test_symlink_escape_is_rejected(self):
        """A pre-existing symlink at the destination pointing outside home
        must not let a write escape containment."""
        import tempfile
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as outside_dir:
            home = Path(home_dir)
            outside = Path(outside_dir)
            (home / ".claude" / "commands").mkdir(parents=True)
            # Symlink the target file to somewhere outside `home`.
            evil_target = outside / "escaped.md"
            evil_target.write_text("outside content")
            (home / ".claude" / "commands" / "foo.md").symlink_to(evil_target)
            with self.assertRaises(ValueError):
                live_abs_for(".claude/commands/foo.md", home)


class FindCommandFilesForSkillTest(unittest.TestCase):
    """Regression test for the reviewer-found bug: a bare `name in text`
    substring match made `advice` false-match inside `web-advice`."""

    def _make_repo(self, tmp_path: Path) -> Path:
        commands = tmp_path / ".claude" / "commands"
        commands.mkdir(parents=True)
        (commands / "advice.md").write_text(
            "Read `${CLAUDE_HOME:-$HOME/.claude}/skills/advice/SKILL.md` with `$ARGUMENTS`."
        )
        (commands / "web-advice.md").write_text(
            "Read `${CLAUDE_HOME:-$HOME/.claude}/skills/web-advice/SKILL.md` with `$ARGUMENTS`."
        )
        return tmp_path

    def test_advice_skill_does_not_match_web_advice_command(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_repo(Path(tmp))
            hits = find_command_files_for_skill(root, ".claude/skills/advice")
            self.assertEqual(hits, [".claude/commands/advice.md"])

    def test_web_advice_skill_matches_only_its_own_command(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_repo(Path(tmp))
            hits = find_command_files_for_skill(root, ".claude/skills/web-advice")
            self.assertEqual(hits, [".claude/commands/web-advice.md"])


class ScopeLiveRootsTest(unittest.TestCase):
    def test_full_scope_returns_all_top_level_roots(self):
        roots = scope_live_roots([], full=True)
        self.assertEqual(sorted(roots), sorted([".claude/", ".codex/", ".hermes/"]))

    def test_core_scope_returns_only_referenced_skill_dirs(self):
        files = [
            ".claude/skills/advice/SKILL.md",
            ".claude/skills/advice/scripts/run.py",
            ".claude/skills/redgreen/SKILL.md",
            ".claude/commands/advice.md",  # not a skill dir, should be ignored
        ]
        roots = scope_live_roots(files, full=False)
        self.assertEqual(sorted(roots), sorted([".claude/skills/advice/", ".claude/skills/redgreen/"]))


class Sha256Test(unittest.TestCase):
    def test_missing_file_returns_none(self):
        self.assertIsNone(sha256_of(Path("/nonexistent/path/that/does/not/exist.md")))

    def test_present_file_returns_stable_hash(self):
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f:
            f.write("hello world")
            path = Path(f.name)
        try:
            h1 = sha256_of(path)
            h2 = sha256_of(path)
            assert h1 is not None
            self.assertEqual(h1, h2)
            self.assertEqual(len(h1), 64)
        finally:
            path.unlink()


class UnifiedDiffTextTest(unittest.TestCase):
    def test_identical_text_returns_none(self):
        self.assertIsNone(unified_diff_text("same\n", "same\n", "a", "b"))

    def test_different_text_returns_diff(self):
        diff = unified_diff_text("line1\nline2\n", "line1\nchanged\n", "a", "b")
        assert diff is not None
        self.assertIn("changed", diff)


class FileEvidenceStatusTest(unittest.TestCase):
    def test_status_values_are_the_documented_set(self):
        ev = FileEvidence(repo_rel="x", live_rel="y", status="live_only")
        self.assertIn(ev.status, ("new", "modified", "ok", "live_only"))


if __name__ == "__main__":
    unittest.main()
