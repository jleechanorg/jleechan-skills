import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SchedulerTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.stage = Path(temp.name)
        self.config = self.stage / "seat %H $HOME & \"config\".json"

    def render(self, scheduler, *args):
        subprocess.run(
            [sys.executable, ROOT / "scripts/render_pr_owner_nudger.py", scheduler,
             "--config", self.config, "--output", self.stage, *args],
            check=True, timeout=15,
        )

    def test_launchd_preserves_config_arg_and_defaults_to_inspection(self):
        self.render("launchd")
        path = self.stage / "org.prw.pr-owner-nudger.plist"
        job = plistlib.loads(path.read_bytes())
        self.assertEqual(job["StartInterval"], 300)
        self.assertTrue(job["AbandonProcessGroup"])
        self.assertEqual(job["ProgramArguments"][2:], ["--config", str(self.config)])
        self.render("launchd", "--apply")
        self.assertEqual(plistlib.loads(path.read_bytes())["ProgramArguments"][-1], "--apply")
        if sys.platform == "darwin":
            subprocess.run(["/usr/bin/plutil", "-lint", path], check=True, timeout=15)

    @unittest.skipUnless(shutil.which("systemd-analyze"), "systemd tools unavailable")
    def test_native_timer_validates_and_dispatch_is_explicit(self):
        self.render("systemd")
        service = self.stage / "pr-owner-nudger.service"
        timer = self.stage / "pr-owner-nudger.timer"
        self.assertNotIn("--apply", service.read_text())
        self.render("systemd", "--apply")
        self.assertIn("--apply", service.read_text())
        env = dict(os.environ, HOME=str(self.stage), XDG_CONFIG_HOME=str(self.stage),
                   XDG_RUNTIME_DIR=str(self.stage))
        subprocess.run(
            ["systemd-analyze", "--user", "verify", service, timer],
            check=True, env=env, timeout=15,
        )
