"""Unit tests for scripts/sync_live_config.py — covers the review findings from
PR #419 (path containment, the --local-only inversion, and the find_command_files_for_skill
substring over-match), plus core evidence/mapping logic."""

import shlex
import subprocess
import sys
import tarfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.sync_live_config import (
    FS,
    GS,
    RS,
    FileEvidence,
    _SYMLINK_GUARD_FN,
    _apply_remote_repo_to_live,
    _validate_host,
    evidence_remote,
    find_command_files_for_skill,
    live_abs_for,
    live_rel_for,
    last_commit,
    prime_last_commit_cache,
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

    def test_rejects_paths_outside_the_tools_actual_scope(self):
        """Regression test: TOP_LEVEL_MAP previously allowed the broad `.codex/`
        and `hermes/` prefixes even though the tool's real scope (collect_full_scope)
        is `.codex/hooks/` and `hermes/skills/` -- a caller-supplied --paths value
        like `.codex/config.toml` passed validation despite being out of scope."""
        with self.assertRaises(ValueError):
            validate_repo_rel(".codex/config.toml")
        with self.assertRaises(ValueError):
            validate_repo_rel("hermes/scripts/something.py")
        # In-scope subpaths still pass.
        self.assertEqual(validate_repo_rel(".codex/hooks/foo.py"), ".codex/hooks/foo.py")
        self.assertEqual(validate_repo_rel("hermes/skills/x/y.md"), "hermes/skills/x/y.md")


class LiveRelForTest(unittest.TestCase):
    def test_maps_each_top_level_root(self):
        self.assertEqual(live_rel_for(".claude/commands/foo.md"), ".claude/commands/foo.md")
        self.assertEqual(live_rel_for(".codex/hooks/bar.py"), ".codex/hooks/bar.py")
        self.assertEqual(live_rel_for("hermes/skills/x/y.md"), ".hermes/skills/x/y.md")


class ContainmentTest(unittest.TestCase):
    """The core fix for the path-escape finding: resolved paths must stay
    within the intended root even after a symlink or '..' is involved."""

    def _commit_paths(self, root: Path, *paths: str) -> None:
        subprocess.run(["git", "init"], cwd=root, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Probe"], cwd=root, check=True)
        subprocess.run(
            ["git", "config", "user.email", "probe@example.invalid"],
            cwd=root,
            check=True,
        )
        subprocess.run(["git", "add", "--", *paths], cwd=root, check=True)
        subprocess.run(
            ["git", "commit", "-m", "symlink fixture"],
            cwd=root,
            capture_output=True,
            check=True,
        )

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

    def test_symlink_to_a_different_sensitive_path_still_within_home_is_rejected(self):
        """Regression test: a home-wide containment check is not enough --
        `~/secret/keys.txt` and `~/.ssh/id_rsa` are both "relative to $HOME"
        and would pass a check scoped that broadly. Reproduced in review:
        `apply` overwrote a secret file through a symlink at a skill path.
        Containment must be scoped to the specific mapped root (e.g.
        home/.claude), not the whole home directory."""
        import tempfile
        with tempfile.TemporaryDirectory() as home_dir:
            home = Path(home_dir)
            (home / ".claude" / "skills" / "foo").mkdir(parents=True)
            (home / "secret").mkdir()
            secret = home / "secret" / "keys.txt"
            secret.write_text("super secret")
            (home / ".claude" / "skills" / "foo" / "SKILL.md").symlink_to(secret)
            with self.assertRaises(ValueError):
                live_abs_for(".claude/skills/foo/SKILL.md", home)

    def test_repo_abs_for_rejects_symlink_to_sibling_top_level_dir(self):
        """Mirror test for the repo side: a symlink inside .claude/ pointing
        at another top-level repo directory (e.g. .git/) must be rejected,
        not just a symlink pointing entirely outside the repo."""
        import tempfile
        with tempfile.TemporaryDirectory() as root_dir:
            root = Path(root_dir)
            (root / ".claude" / "commands").mkdir(parents=True)
            (root / "other_top_level").mkdir()
            sensitive = root / "other_top_level" / "secret.txt"
            sensitive.write_text("secret")
            (root / ".claude" / "commands" / "foo.md").symlink_to(sensitive)
            with self.assertRaises(ValueError):
                repo_abs_for(root, ".claude/commands/foo.md")

    def test_repo_abs_for_rejects_tracked_symlink_to_outside_mapped_roots(self):
        import tempfile

        with tempfile.TemporaryDirectory() as root_dir:
            root = Path(root_dir)
            (root / ".claude" / "commands").mkdir(parents=True)
            sensitive = root / "other_top_level" / "secret.md"
            sensitive.parent.mkdir()
            sensitive.write_text("secret")
            (root / ".claude" / "commands" / "foo.md").symlink_to(sensitive)
            self._commit_paths(root, ".claude/commands/foo.md")

            with self.assertRaises(ValueError):
                repo_abs_for(root, ".claude/commands/foo.md")

    def test_repo_abs_for_allows_tracked_symlink_within_mapped_root(self):
        import tempfile

        with tempfile.TemporaryDirectory() as root_dir:
            root = Path(root_dir)
            commands = root / ".claude" / "commands"
            commands.mkdir(parents=True)
            target = commands / "target.md"
            target.write_text("internal fixture")
            link = commands / "alias.md"
            link.symlink_to(target)
            self._commit_paths(
                root, ".claude/commands/alias.md", ".claude/commands/target.md"
            )

            self.assertEqual(repo_abs_for(root, ".claude/commands/alias.md"), link)

    def test_repo_abs_for_allows_tracked_hermes_link_to_claude_skill(self):
        import tempfile

        with tempfile.TemporaryDirectory() as root_dir:
            root = Path(root_dir)
            target = root / ".claude" / "skills" / "foo" / "SKILL.md"
            target.parent.mkdir(parents=True)
            target.write_text("canonical skill fixture")
            link = root / "hermes" / "skills" / "foo" / "SKILL.md"
            link.parent.mkdir(parents=True)
            link.symlink_to(target)
            self._commit_paths(root, "hermes/skills/foo/SKILL.md")

            self.assertEqual(repo_abs_for(root, "hermes/skills/foo/SKILL.md"), link)

    def test_repo_abs_for_rejects_tracked_link_to_other_mapped_root(self):
        import tempfile

        with tempfile.TemporaryDirectory() as root_dir:
            root = Path(root_dir)
            commands = root / ".claude" / "commands"
            hooks = root / ".codex" / "hooks"
            commands.mkdir(parents=True)
            hooks.mkdir(parents=True)
            target = hooks / "target.py"
            target.write_text("hook fixture")
            (commands / "foo.md").symlink_to(target)
            self._commit_paths(root, ".claude/commands/foo.md", ".codex/hooks/target.py")

            with self.assertRaises(ValueError):
                repo_abs_for(root, ".claude/commands/foo.md")

    def test_repo_abs_for_rejects_cross_root_parent_symlink(self):
        import tempfile

        with tempfile.TemporaryDirectory() as root_dir:
            root = Path(root_dir)
            claude_root = root / ".claude"
            codex_hooks = root / ".codex" / "hooks"
            claude_root.mkdir()
            codex_hooks.mkdir(parents=True)
            target = codex_hooks / "target.py"
            target.write_text("hook fixture")
            (claude_root / "commands").symlink_to(
                codex_hooks, target_is_directory=True
            )

            with self.assertRaises(ValueError):
                repo_abs_for(root, ".claude/commands/target.py")


    def test_repo_abs_for_rejects_untracked_hermes_parent_link(self):
        import tempfile

        with tempfile.TemporaryDirectory() as root_dir:
            root = Path(root_dir)
            target = root / ".claude" / "skills" / "foo" / "SKILL.md"
            target.parent.mkdir(parents=True)
            target.write_text("canonical skill fixture")
            link = root / "hermes" / "skills" / "foo"
            link.parent.mkdir(parents=True)
            link.symlink_to(target.parent, target_is_directory=True)
            self._commit_paths(root, ".claude/skills/foo/SKILL.md")

            with self.assertRaises(ValueError):
                repo_abs_for(root, "hermes/skills/foo/SKILL.md")


    def test_repo_abs_for_rejects_tracked_hermes_alias_to_external_canonical_target(self):
        import tempfile

        with tempfile.TemporaryDirectory() as root_dir, tempfile.TemporaryDirectory() as outside_dir:
            root = Path(root_dir)
            outside = Path(outside_dir) / "outside.md"
            outside.write_text("owned external fixture")
            canonical = root / ".claude" / "skills" / "foo" / "SKILL.md"
            canonical.parent.mkdir(parents=True)
            canonical.symlink_to(outside)
            alias = root / "hermes" / "skills" / "foo" / "SKILL.md"
            alias.parent.mkdir(parents=True)
            alias.symlink_to("../../../.claude/skills/foo/SKILL.md")
            self._commit_paths(
                root,
                ".claude/skills/foo/SKILL.md",
                "hermes/skills/foo/SKILL.md",
            )

            staged = subprocess.run(
                [
                    "git",
                    "ls-files",
                    "--stage",
                    "--",
                    ".claude/skills/foo/SKILL.md",
                    "hermes/skills/foo/SKILL.md",
                ],
                cwd=root,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.splitlines()
            self.assertEqual(len(staged), 2)
            self.assertTrue(all(line.startswith("120000 ") for line in staged))

            with self.assertRaises(ValueError):
                repo_abs_for(root, "hermes/skills/foo/SKILL.md")


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
        self.assertEqual(sorted(roots), sorted([".claude/", ".codex/hooks/", ".hermes/skills/"]))

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


class PrimeLastCommitCacheTest(unittest.TestCase):
    def test_regression_pr711_commit_metadata_cache_preserves_field_alignment(self):
        import tempfile

        with tempfile.TemporaryDirectory() as root_dir:
            root = Path(root_dir)
            subprocess.run(["git", "init"], cwd=root, capture_output=True, check=True)
            subprocess.run(["git", "config", "user.name", "Probe"], cwd=root, check=True)
            subprocess.run(
                ["git", "config", "user.email", "probe@example.invalid"],
                cwd=root,
                check=True,
            )
            (root / "tracked.md").write_text("fixture\n", encoding="utf-8")
            subprocess.run(["git", "add", "tracked.md"], cwd=root, check=True)
            subprocess.run(
                ["git", "commit", "-m", "known probe commit"],
                cwd=root,
                capture_output=True,
                check=True,
            )
            expected_raw = subprocess.run(
                [
                    "git",
                    "log",
                    "-1",
                    "--format=%H%x1f%aI%x1f%an%x1f%s",
                    "--",
                    "tracked.md",
                ],
                cwd=root,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            sha, date, author, subject = expected_raw.split("\x1f", 3)

            with patch(
                "scripts.sync_live_config.subprocess.run",
                wraps=subprocess.run,
            ) as run:
                prime_last_commit_cache(root, ["tracked.md"])
                actual = last_commit(root, "tracked.md")

            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.args[0][-2:], ["--", "tracked.md"])
            self.assertEqual(
                actual,
                {
                    "sha": sha[:12],
                    "date": date,
                    "author": author,
                    "subject": subject,
                },
            )


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


class ApplyDryRunOutputTest(unittest.TestCase):
    def test_reports_full_hashes_and_preserves_fixture_targets(self):
        import tempfile

        root = Path(__file__).resolve().parents[1]
        script = root / "scripts" / "sync_live_config.py"
        create_path = ".claude/commands/.ruff.toml"
        same_path = ".claude/skills/sync-live-config/SKILL.md"
        overwrite_path = ".claude/commands/advice.md"

        with tempfile.TemporaryDirectory() as home_dir:
            home = Path(home_dir)
            create_dest = home / create_path
            same_dest = home / same_path
            overwrite_dest = home / overwrite_path
            same_dest.parent.mkdir(parents=True)
            overwrite_dest.parent.mkdir(parents=True)
            same_source = root / same_path
            same_dest.write_bytes(same_source.read_bytes())
            overwrite_dest.write_text("old fixture", encoding="utf-8")
            same_before = (sha256_of(same_dest), same_dest.stat().st_mtime_ns)
            overwrite_before = (
                sha256_of(overwrite_dest),
                overwrite_dest.stat().st_mtime_ns,
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "apply",
                    "--direction",
                    "repo-to-live",
                    "--paths",
                    create_path,
                    same_path,
                    overwrite_path,
                    "--dry-run",
                    "--home",
                    str(home),
                ],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=30,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(f"CREATE {create_path}", result.stdout)
            self.assertIn(
                f"src={sha256_of(root / create_path)} dst=missing",
                result.stdout,
            )
            self.assertIn(f"SAME   {same_path}", result.stdout)
            self.assertIn(f"{same_source} -> {same_dest}", result.stdout)
            same_hash = sha256_of(same_source)
            self.assertIn(f"src={same_hash} dst={same_hash}", result.stdout)
            self.assertIn(f"OVERWRITE {overwrite_path}", result.stdout)
            self.assertIn(
                f"src={sha256_of(root / overwrite_path)} "
                f"dst={overwrite_before[0]}",
                result.stdout,
            )
            self.assertFalse(create_dest.exists())
            self.assertEqual(
                (sha256_of(same_dest), same_dest.stat().st_mtime_ns),
                same_before,
            )
            self.assertEqual(
                (sha256_of(overwrite_dest), overwrite_dest.stat().st_mtime_ns),
                overwrite_before,
            )


    def test_reports_effective_destination_when_target_is_directory(self):
        import tempfile

        root = Path(__file__).resolve().parents[1]
        script = root / "scripts" / "sync_live_config.py"
        repo_rel = ".claude/commands/advice.md"
        source = root / repo_rel

        with tempfile.TemporaryDirectory() as home_dir:
            home = Path(home_dir)
            destination_dir = home / repo_rel
            destination_dir.mkdir(parents=True)
            effective_destination = destination_dir / source.name
            effective_destination.write_text("directory target fixture")
            before = (
                sha256_of(effective_destination),
                effective_destination.stat().st_mtime_ns,
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "apply",
                    "--direction",
                    "repo-to-live",
                    "--paths",
                    repo_rel,
                    "--dry-run",
                    "--home",
                    str(home),
                ],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=30,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(f"OVERWRITE {repo_rel}", result.stdout)
            self.assertIn(f"{source}\n      -> {effective_destination}", result.stdout)
            self.assertIn(
                f"src={sha256_of(source)} dst={before[0]}",
                result.stdout,
            )
            self.assertEqual(
                (
                    sha256_of(effective_destination),
                    effective_destination.stat().st_mtime_ns,
                ),
                before,
            )


class RemoteApplyArchiveTest(unittest.TestCase):
    def test_archives_tracked_hermes_link_contents_under_requested_path(self):
        import tempfile

        with tempfile.TemporaryDirectory() as root_dir:
            root = Path(root_dir)
            repo_rel = "hermes/skills/foo/SKILL.md"
            target = root / ".claude" / "skills" / "foo" / "SKILL.md"
            target.parent.mkdir(parents=True)
            payload = b"canonical skill fixture\n"
            target.write_bytes(payload)
            link = root / repo_rel
            link.parent.mkdir(parents=True)
            link.symlink_to(target)
            subprocess.run(["git", "init"], cwd=root, capture_output=True, check=True)
            subprocess.run(["git", "config", "user.name", "Probe"], cwd=root, check=True)
            subprocess.run(
                ["git", "config", "user.email", "probe@example.invalid"],
                cwd=root,
                check=True,
            )
            subprocess.run(
                ["git", "add", "--", repo_rel, ".claude/skills/foo/SKILL.md"],
                cwd=root,
                check=True,
            )
            subprocess.run(
                ["git", "commit", "-m", "remote tar fixture"],
                cwd=root,
                capture_output=True,
                check=True,
            )
            captured = {}
            real_run = subprocess.run

            def fake_run(cmd, *args, **kwargs):
                if cmd[0] == "scp":
                    with tarfile.open(cmd[3], "r:gz") as archive:
                        member = archive.getmember(repo_rel)
                        captured["regular_file"] = member.isfile()
                        stream = archive.extractfile(member) if member.isfile() else None
                        captured["payload"] = stream.read() if stream is not None else None
                    return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
                if cmd[0] == "ssh":
                    return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
                return real_run(cmd, *args, **kwargs)

            with (
                patch(
                    "scripts.sync_live_config._remote_home",
                    return_value="/remote/home",
                ),
                patch(
                    "scripts.sync_live_config.subprocess.run",
                    side_effect=fake_run,
                ),
            ):
                _apply_remote_repo_to_live(root, [repo_rel], "fixture-host")

            self.assertTrue(captured["regular_file"])
            self.assertEqual(captured["payload"], payload)


class EvidenceRemoteTest(unittest.TestCase):
    """Regression coverage for the exact bug found in review: the remote batch
    protocol nested a 4-part git commit tuple inside an FS-delimited record
    using the SAME separator, so `record.split(FS)` silently misparsed every
    field after the commit (content_b64 ended up holding the commit date)."""

    def _fake_run(self, remote_home: str, batch_stdout: str):
        def run(cmd, **kwargs):
            del kwargs  # signature-compatible stand-in for subprocess.run; args unused
            if cmd[0] == "git":
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
            if cmd[0] == "ssh" and "printf" in cmd:
                return subprocess.CompletedProcess(cmd, 0, stdout=remote_home, stderr="")
            if cmd[0] == "ssh" and "bash" in cmd:
                return subprocess.CompletedProcess(cmd, 0, stdout=batch_stdout, stderr="")
            raise AssertionError(f"unexpected subprocess.run call in test: {cmd}")
        return run

    def test_modified_file_with_commit_metadata_parses_correctly(self):
        import base64
        import tempfile

        with tempfile.TemporaryDirectory() as root_dir:
            root = Path(root_dir)
            (root / ".claude" / "commands").mkdir(parents=True)
            repo_file = root / ".claude" / "commands" / "foo.md"
            repo_file.write_text("repo version\n")

            remote_content = base64.b64encode(b"live version\n").decode()
            commit_tuple = GS.join(["abc123def456", "2026-01-01T00:00:00-08:00", "Someone", "a commit subject"])
            record = FS.join(["FOUND", "deadbeef" * 8, "/home/testuser/somerepo", commit_tuple, remote_content])
            batch_stdout = record + RS

            with patch("scripts.sync_live_config.subprocess.run", side_effect=self._fake_run("/home/testuser", batch_stdout)):
                results = evidence_remote(root, [".claude/commands/foo.md"], "testhost")

            self.assertEqual(len(results), 1)
            ev = results[0]
            self.assertEqual(ev.status, "modified")
            self.assertEqual(ev.live_repo_root, "testhost:/home/testuser/somerepo")
            assert ev.live_last_commit is not None
            self.assertEqual(ev.live_last_commit["sha"], "abc123def456"[:12])
            self.assertEqual(ev.live_last_commit["date"], "2026-01-01T00:00:00-08:00")
            self.assertEqual(ev.live_last_commit["author"], "Someone")
            self.assertEqual(ev.live_last_commit["subject"], "a commit subject")
            # This is the exact field the bug corrupted: it must be the real
            # diff, not the commit date leaking in from a misparsed field.
            assert ev.diff_snippet is not None
            self.assertIn("live version", ev.diff_snippet)
            self.assertNotIn("2026-01-01", ev.diff_snippet)

    def test_missing_file_reports_new(self):
        import tempfile

        with tempfile.TemporaryDirectory() as root_dir:
            root = Path(root_dir)
            (root / ".claude" / "commands").mkdir(parents=True)
            (root / ".claude" / "commands" / "foo.md").write_text("x\n")
            batch_stdout = "MISSING" + RS

            with patch("scripts.sync_live_config.subprocess.run", side_effect=self._fake_run("/home/testuser", batch_stdout)):
                results = evidence_remote(root, [".claude/commands/foo.md"], "testhost")

            self.assertEqual(results[0].status, "new")

    def test_symlinked_path_withholds_all_metadata_not_just_content(self):
        """Regression test: an earlier version only gated content_b64, so a
        symlinked remote path's exact hash/size/commit metadata still leaked
        as a confirmation oracle. The SYMLINK record kind must withhold
        everything -- the parsed evidence should carry no hash-derived status,
        no live_repo_root, no live_last_commit, no diff_snippet."""
        import tempfile

        with tempfile.TemporaryDirectory() as root_dir:
            root = Path(root_dir)
            (root / ".claude" / "commands").mkdir(parents=True)
            (root / ".claude" / "commands" / "foo.md").write_text("x\n")
            batch_stdout = "SYMLINK" + RS

            with patch("scripts.sync_live_config.subprocess.run", side_effect=self._fake_run("/home/testuser", batch_stdout)):
                results = evidence_remote(root, [".claude/commands/foo.md"], "testhost")

            ev = results[0]
            self.assertEqual(ev.status, "symlink")
            self.assertIsNone(ev.live_repo_root)
            self.assertIsNone(ev.live_last_commit)
            self.assertIsNone(ev.diff_snippet)

    def test_malformed_record_raises_instead_of_silently_misparsing(self):
        """A field count other than 5 must fail loudly, not guess."""
        import tempfile

        with tempfile.TemporaryDirectory() as root_dir:
            root = Path(root_dir)
            (root / ".claude" / "commands").mkdir(parents=True)
            (root / ".claude" / "commands" / "foo.md").write_text("x\n")
            # Only 3 fields after "FOUND" instead of 4 -- simulates a protocol drift.
            malformed = FS.join(["FOUND", "hash", "extra"]) + RS

            with patch("scripts.sync_live_config.subprocess.run", side_effect=self._fake_run("/home/testuser", malformed)):
                with self.assertRaises(RuntimeError):
                    evidence_remote(root, [".claude/commands/foo.md"], "testhost")


class ValidateHostTest(unittest.TestCase):
    """Regression coverage: OpenSSH's own argument parser does not reliably
    treat a `-`-prefixed value as "not an option" just because of where it
    appears on the command line -- `--remote=-oProxyCommand=...` was
    confirmed (via `ssh -G`) to be interpreted as a real ssh option even in
    the hostname position."""

    def test_accepts_ordinary_hostnames(self):
        for h in ("jeff-ubuntu", "example.com", "10.0.0.1", "user@host"):
            self.assertEqual(_validate_host(h), h)

    def test_rejects_option_like_values(self):
        for h in ("-oProxyCommand=touch /tmp/pwned", "-x", "--", ""):
            with self.assertRaises(ValueError):
                _validate_host(h)


class SymlinkGuardFnTest(unittest.TestCase):
    """Executes `_SYMLINK_GUARD_FN` for real via `bash -c`, not a mock.

    Every remote code path in this file is exercised through mocked
    `subprocess.run`, which means the bash function that actually performs
    the security-critical check (path_has_symlink_component) has zero
    coverage from the LLM's/test's perspective — a future edit to that
    function could silently reopen the exact exfiltration bug this file's
    other tests were written to catch, while every mocked test stays green.
    This test runs the real bash source against a real symlink tree."""

    def _run_guard(self, base: str, target: str) -> int:
        script = _SYMLINK_GUARD_FN + f'\npath_has_symlink_component {shlex.quote(base)} {shlex.quote(target)}\n'
        result = subprocess.run(["bash", "-c", script])
        return result.returncode

    def test_plain_in_scope_path_is_allowed(self):
        import tempfile
        with tempfile.TemporaryDirectory() as base:
            target = f"{base}/skills/foo/SKILL.md"
            Path(target).parent.mkdir(parents=True)
            Path(target).write_text("x")
            # returncode 1 == function returned 1 (false) == no symlink found == safe
            self.assertEqual(self._run_guard(base, target), 1)

    def test_symlinked_leaf_is_rejected(self):
        import tempfile
        with tempfile.TemporaryDirectory() as base, tempfile.TemporaryDirectory() as outside:
            Path(f"{base}/skills/foo").mkdir(parents=True)
            secret = Path(outside) / "secret.txt"
            secret.write_text("secret")
            target = f"{base}/skills/foo/SKILL.md"
            Path(target).symlink_to(secret)
            # returncode 0 == function returned 0 (true) == symlink found == refuse
            self.assertEqual(self._run_guard(base, target), 0)

    def test_symlinked_parent_directory_is_rejected(self):
        import tempfile
        with tempfile.TemporaryDirectory() as base, tempfile.TemporaryDirectory() as outside:
            Path(f"{base}/skills").mkdir(parents=True)
            Path(f"{base}/skills/foo").symlink_to(outside)
            target = f"{base}/skills/foo/SKILL.md"
            Path(f"{outside}/SKILL.md").write_text("x")
            self.assertEqual(self._run_guard(base, target), 0)

    def test_target_outside_base_entirely_is_rejected(self):
        import tempfile
        with tempfile.TemporaryDirectory() as base, tempfile.TemporaryDirectory() as outside:
            self.assertEqual(self._run_guard(base, f"{outside}/whatever.md"), 0)


if __name__ == "__main__":
    unittest.main()
