"""collect_repro.py expands environment paths and derives incident details from inputs."""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".claude" / "skills" / "repro-developer" / "scripts" / "collect_repro.py"


class ReproDeveloperEnvDefaultsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.home = self.tmp / "home"
        self.repo = self.tmp / "widgets"
        self.out = self.tmp / "out"
        for directory in (self.home, self.repo, self.out):
            directory.mkdir()
        self.env = {
            "HOME": str(self.home),
            "PATH": "/usr/bin:/bin",
            "LANG": "C",
            "GIT_CONFIG_NOSYSTEM": "1",
        }
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True, env=self.env)
        subprocess.run(
            ["git", "-C", str(self.repo), "remote", "add", "origin", "https://example.com/acme/widgets.git"],
            check=True,
            env=self.env,
        )
        self.session = self.home / ".claude" / "projects" / "p" / "s.jsonl"
        self.session.parent.mkdir(parents=True)
        self.session.write_text('{"type":"user"}\n')

    def collect(self, *args, **extra):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--repo", str(self.repo), "--out", str(self.out), *args],
            cwd=self.tmp,
            env={**self.env, **extra},
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        output = json.loads(proc.stdout)
        bundle = Path(output["bundle_dir"])
        manifest = json.loads((bundle / "manifest.json").read_text())
        return output, bundle, manifest

    def copied_sources(self, manifest):
        return {entry["source"]: entry for entry in manifest["copied"]}

    def make_session(self, claude_home, name):
        session = claude_home / "projects" / "p" / name
        session.parent.mkdir(parents=True, exist_ok=True)
        session.write_text('{"type":"user"}\n')
        return session

    def tree_blob(self, root):
        return b"\n".join(p.read_bytes() for p in Path(root).rglob("*") if p.is_file())

    def archive_blob(self, archive):
        archive = Path(archive)
        if archive.suffix == ".zst":
            return subprocess.run(
                ["zstd", "-dc", str(archive)], capture_output=True, check=True
            ).stdout
        return archive.read_bytes()

    def test_session_path_with_env_variable_is_expanded(self):
        _, _, manifest = self.collect(
            "--incident", "t1", "--claude-session", "$CLAUDE_HOME/projects/p/s.jsonl",
            CLAUDE_HOME=str(self.home / ".claude"),
        )
        entry = self.copied_sources(manifest)[str(self.session)]
        self.assertNotIn("missing", entry)

    def test_profile_file_supplies_incident_and_reading_order(self):
        profile = self.tmp / "profile.json"
        profile.write_text(json.dumps({
            "incident": "t2",
            "claude_sessions": ["$HOME/.claude/projects/p/s.jsonl"],
        }))
        _, bundle, manifest = self.collect("--incident-profile", str(profile))
        entry = self.copied_sources(manifest)[str(self.session)]
        self.assertNotIn("missing", entry)
        self.assertIn(entry["bundle_path"], (bundle / "REPLAY.md").read_text())

    def test_publish_readme_clones_the_repo_origin(self):
        output, _, _ = self.collect("--incident", "t3", "--publish-dir", str(self.tmp / "pub"))
        readme = (Path(output["publish_dir"]) / "README.md").read_text()
        self.assertIn("git clone https://example.com/acme/widgets.git", readme)

    def test_sanitizer_redacts_configured_holdouts_path(self):
        spec = importlib.util.spec_from_file_location("collect_repro", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with mock.patch.dict(os.environ, {"DARK_FACTORY_HOLDOUTS": "/srv/sealed-scenarios"}):
            cleaned = module.sanitize_text("read /srv/sealed-scenarios/holdouts/a.yaml")
        self.assertNotIn("/srv/sealed-scenarios", cleaned)

    def test_documented_session_store_defaults_apply_to_arguments_and_profiles(self):
        session = self.make_session(self.home / ".claude", "default.jsonl")
        _, _, manifest = self.collect(
            "--incident", "t4", "--claude-session", "$CLAUDE_HOME/projects/p/default.jsonl"
        )
        self.assertNotIn("missing", self.copied_sources(manifest)[str(session)])

        profile = self.tmp / "profile-defaults.json"
        profile.write_text(json.dumps({
            "incident": "t4b",
            "claude_sessions": ["$CLAUDE_HOME/projects/p/default.jsonl"],
        }))
        _, _, profile_manifest = self.collect("--incident-profile", str(profile))
        self.assertNotIn("missing", self.copied_sources(profile_manifest)[str(session)])

    def test_explicit_claude_home_still_overrides_the_documented_default(self):
        alt_home = self.tmp / "alt-claude"
        alt_session = self.make_session(alt_home, "alt.jsonl")
        _, _, manifest = self.collect(
            "--incident", "t5",
            "--claude-session", "$CLAUDE_HOME/projects/p/alt.jsonl",
            CLAUDE_HOME=str(alt_home),
        )
        sources = self.copied_sources(manifest)
        self.assertNotIn("missing", sources[str(alt_session)])
        self.assertNotIn(str(self.session), sources)

    def test_published_handoff_never_contains_origin_credentials(self):
        subprocess.run(
            [
                "git", "-C", str(self.repo), "remote", "set-url", "origin",
                "https://synthetic-user:synthetic-token@example.com/acme/widgets.git",
            ],
            check=True,
            env=self.env,
        )
        output, bundle, _ = self.collect(
            "--incident", "t6", "--sanitize", "--publish-dir", str(self.tmp / "pub")
        )
        publish_dir = Path(output["publish_dir"])
        readme = (publish_dir / "README.md").read_text()
        self.assertIn("https://example.com/acme/widgets.git", readme)
        self.assertNotIn("synthetic-user", readme)
        self.assertNotIn("synthetic-token", readme)

        for root in (bundle, Path(output["sanitized_bundle_dir"])):
            blob = self.tree_blob(root)
            self.assertNotIn(b"synthetic-user", blob, str(root))
            self.assertNotIn(b"synthetic-token", blob, str(root))

        for archive in (output["sanitized_archive"], output["archive"]):
            blob = self.archive_blob(archive)
            self.assertNotIn(b"synthetic-user", blob, archive)
            self.assertNotIn(b"synthetic-token", blob, archive)

    def test_profile_does_not_force_dirty_beads_or_env_capture(self):
        profile = self.tmp / "profile-min.json"
        profile.write_text(json.dumps({"incident": "t7", "claim": "minimal claim"}))
        _, bundle, _ = self.collect("--incident-profile", str(profile))
        self.assertFalse((bundle / "repo" / "dirty-state").exists())
        self.assertFalse((bundle / "repo" / "beads").exists())
        self.assertFalse((bundle / "repo" / "environment.json").exists())

    def test_explicit_capture_flags_still_apply_with_a_profile(self):
        profile = self.tmp / "profile-flags.json"
        profile.write_text(json.dumps({"incident": "t8"}))
        _, bundle, _ = self.collect(
            "--incident-profile", str(profile), "--include-dirty-diff", "--write-env-report"
        )
        self.assertTrue((bundle / "repo" / "dirty-state").exists())
        self.assertTrue((bundle / "repo" / "environment.json").exists())

    def test_explicit_cli_selection_replaces_only_that_profile_list(self):
        profile_session = self.make_session(self.home / ".claude", "profile-only.jsonl")
        repo_file = self.repo / "profile-note.md"
        repo_file.write_text("profile repo evidence\n")
        profile = self.tmp / "profile-lists.json"
        profile.write_text(json.dumps({
            "incident": "t9",
            "claude_sessions": [str(profile_session)],
            "repo_files": ["profile-note.md"],
        }))
        _, _, manifest = self.collect(
            "--incident-profile", str(profile),
            "--claude-session", "$HOME/.claude/projects/p/s.jsonl",
        )
        sources = self.copied_sources(manifest)
        self.assertNotIn("missing", sources[str(self.session)])
        self.assertNotIn(str(profile_session), sources)
        self.assertNotIn("missing", sources[str(repo_file)])


if __name__ == "__main__":
    unittest.main()
