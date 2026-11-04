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


if __name__ == "__main__":
    unittest.main()
