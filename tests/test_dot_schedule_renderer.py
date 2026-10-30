import importlib.util
import json
import os
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / ".claude/skills/dot-coordinator/scripts/render_native_schedule.py"
spec = importlib.util.spec_from_file_location("schedule_renderer", SCRIPT)
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)


class ScheduleRendererTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir="/tmp")
        self.root = Path(self.temp.name)
        self.dot = self.root / "dot.json"
        self.dot.write_text(json.dumps({"accounts": {f"account-{x}": {"user_data_dir": "/tmp/profile"} for x in "abc"}}))
        self.dot.chmod(0o600)
        self.pi = self.root / "pi"
        self.pi.write_text("#!/bin/sh\nexit 0\n")
        self.pi.chmod(0o700)
        self.package_root = self.root / "node_modules/chrome-devtools-mcp"
        entry = self.package_root / "build/src/bin/chrome-devtools-mcp.js"
        entry.parent.mkdir(parents=True)
        entry.write_text("// test\n")
        (self.package_root / "package.json").write_text('{"version":"1.6.0"}')
        self.mcp = entry
        self.config = self.root / "schedule.json"
        self.write_config("macos")

    def tearDown(self):
        self.temp.cleanup()

    def write_config(self, host, minutes=None, proceed=None):
        minutes = minutes or (renderer.MAC_MINUTES if host == "macos" else renderer.LINUX_MINUTES)
        proceed = proceed or {}
        self.config.write_text(json.dumps({
            "version": 1, "host_role": host, "dot_config_file": str(self.dot),
            "pi_bin": str(self.pi), "chrome_devtools_mcp_js": str(self.mcp),
            "accounts": [{"key": f"account-{x}", "minute": minutes[i], "identity_sha256": f"{i:064x}", "task": "Read-only check",
                          **(({"proceed_minutes": proceed[f"account-{x}"]}) if f"account-{x}" in proceed else {})} for i, x in enumerate("abc")],
        }))
        self.config.chmod(0o600)

    def test_macos_renders_three_inactive_private_plists_with_ordered_minutes(self):
        fake_home = self.root / "mac-home"
        node_bin = fake_home / ".nvm/versions/node/v22.22.0/bin"
        node_bin.mkdir(parents=True)
        (node_bin / "node").write_text("node fixture")
        with patch.object(renderer.Path, "home", return_value=fake_home):
            out = renderer.render(self.config, self.root / "mac-stage", "macos")
        self.assertEqual(len(list(out.glob("*.plist"))), 3)
        self.assertEqual(stat.S_IMODE(out.stat().st_mode), 0o700)
        plists = [renderer.plistlib.loads(p.read_bytes()) for p in sorted(out.glob("*.plist"))]
        self.assertEqual([p["StartCalendarInterval"]["Minute"] for p in plists], [0, 20, 40])
        self.assertTrue(all(p["ProgramArguments"][-2:] == ["--account", p["ProgramArguments"][-1]] for p in plists))
        self.assertTrue(all(stat.S_IMODE(p.stat().st_mode) == 0o600 for p in out.iterdir()))

    def test_configurable_cli_and_arguments_round_trip_without_shell(self):
        data = json.loads(self.config.read_text())
        data.pop('pi_bin')
        args = ['--thinking', 'medium', 'literal spaces; $HOME $(never-run)']
        data['cli'] = {'executable': str(self.pi), 'args': args}
        self.config.write_text(json.dumps(data))
        with patch.object(renderer, 'node22_bins', return_value=[self.root / 'node-bin']):
            out = renderer.render(self.config, self.root / 'cli-stage', 'macos')
        env = renderer.plistlib.loads(next(out.glob('*.plist')).read_bytes())['EnvironmentVariables']
        self.assertEqual(env['PI_BIN'], str(self.pi))
        self.assertEqual(json.loads(env['COORDINATOR_CLI_ARGS']), args)

    def test_cli_schema_rejects_ambiguous_or_non_array_arguments(self):
        original = json.loads(self.config.read_text())
        for cli in ({'executable': str(self.pi), 'args': '--thinking medium'},
                    {'executable': str(self.pi), 'args': [4]},
                    {'executable': str(self.pi), 'args': ['bad\x00arg']}):
            data = dict(original)
            data.pop('pi_bin')
            data['cli'] = cli
            self.config.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, 'CLI arguments'):
                renderer.render(self.config, self.root / 'invalid-cli-stage', 'macos')
        data = dict(original)
        data['cli'] = {'executable': str(self.pi), 'args': []}
        self.config.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'either cli or pi_bin'):
            renderer.render(self.config, self.root / 'ambiguous-stage', 'macos')

    def test_linux_renders_ordered_timer_service_and_private_env(self):
        self.write_config("linux")
        fake_home = self.root / "home"
        preferred = fake_home / ".nvm/versions/node/v22.22.0/bin"
        other = fake_home / ".nvm/versions/node/v22.23.1/bin"
        for node_bin in (preferred, other):
            node_bin.mkdir(parents=True)
            (node_bin / "node").write_text("node fixture")
        session = {"DISPLAY": ":1", "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1000/bus", "XDG_RUNTIME_DIR": "/run/user/1000"}
        with patch.dict(os.environ, session), patch.object(renderer.Path, "home", return_value=fake_home):
            out = renderer.render(self.config, self.root / "linux-stage", "linux")
        timers = sorted(out.glob("*.timer"))
        self.assertEqual({"10", "30", "50"}, {p.stem.rsplit("-", 1)[1] for p in timers})
        self.assertTrue(all(f"OnCalendar=*-*-* *:{p.stem.rsplit('-', 1)[1]}:00" in p.read_text() for p in timers))
        self.assertIn("--account account-a", (out / "ai.dot-coordinator-30.service").read_text())
        service = (out / "ai.dot-coordinator-30.service").read_text()
        self.assertIn("TimeoutStartSec=800", service)
        self.assertIn("WorkingDirectory=%h", service)
        self.assertIn("DOT_EXPECTED_IDENTITY_SHA256=\"", (out / "ai.dot-coordinator-30.env").read_text())
        self.assertIn('DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/1000/bus"', (out / "ai.dot-coordinator-30.env").read_text())
        self.assertIn('XDG_RUNTIME_DIR="/run/user/1000"', (out / "ai.dot-coordinator-30.env").read_text())
        path = next(line.removeprefix("PATH=") for line in (out / "ai.dot-coordinator-30.env").read_text().splitlines() if line.startswith("PATH="))
        self.assertTrue(path.startswith(f'"{preferred}:{other}:'))

    def test_rejects_overlapping_or_malformed_proceed_minutes_before_writing(self):
        for proceed in ({"account-a": [20]}, {"account-a": [21, 21]}, {"account-a": [60]},
                        {"account-a": ["21"]}, {"account-a": 21}):
            self.write_config("macos", proceed=proceed)
            with self.assertRaisesRegex(ValueError, "minute"):
                renderer.render(self.config, self.root / "bad-proceed-stage", "macos")
            self.assertFalse((self.root / "bad-proceed-stage").exists())

    def test_proceed_minutes_render_hourly_main_plus_twenty_minute_nudges(self):
        proceed = {"account-a": [21, 41], "account-b": [1, 42], "account-c": [2, 22]}
        self.write_config("macos", proceed=proceed)
        with patch.object(renderer, "node22_bins", return_value=[self.root / "node-bin"]):
            out = renderer.render(self.config, self.root / "proceed-stage", "macos")
        plists = {path.stem: renderer.plistlib.loads(path.read_bytes()) for path in out.glob("*.plist")}
        self.assertEqual(len(plists), 9)
        self.assertEqual(sorted(plist["StartCalendarInterval"]["Minute"] for plist in plists.values()),
                         [0, 1, 2, 20, 21, 22, 40, 41, 42])
        nudges = {name: plist for name, plist in plists.items() if name.endswith("-proceed")}
        self.assertEqual(len(nudges), 6)
        for name, plist in nudges.items():
            minute = plist["StartCalendarInterval"]["Minute"]
            env = plist["EnvironmentVariables"]
            self.assertEqual(name, f"ai.dot-coordinator.{minute:02d}-proceed")
            self.assertEqual(plist["Label"], name)
            self.assertEqual(env["COORDINATOR_MODE"], "proceed")
            self.assertTrue(env["COORDINATOR_TASK"].startswith("Coordination mode: proceed."))
            self.assertTrue(env["COORDINATOR_TASK"].endswith("Read-only check"))
            self.assertTrue(plist["StandardOutPath"].endswith(f"/{minute:02d}-proceed.out.log"))
        for name, plist in plists.items():
            if not name.endswith("-proceed"):
                self.assertEqual(plist["EnvironmentVariables"]["COORDINATOR_MODE"], "main")
                self.assertEqual(plist["EnvironmentVariables"]["COORDINATOR_TASK"],
                                 "Coordination mode: main. Use the periodic reminder for this mode. Read-only check")

    def test_operator_three_nudge_cadence_renders_twelve_disjoint_runs(self):
        self.write_config("macos", proceed={"account-a": [15, 30, 45], "account-b": [5, 35, 50],
                                            "account-c": [10, 25, 55]})
        with patch.object(renderer, "node22_bins", return_value=[self.root / "node-bin"]):
            out = renderer.render(self.config, self.root / "three-nudge-stage", "macos")
        plists = {path.stem: renderer.plistlib.loads(path.read_bytes()) for path in out.glob("*.plist")}
        self.assertEqual(len(plists), 12)
        self.assertEqual(sorted(p["StartCalendarInterval"]["Minute"] for p in plists.values()),
                         [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55])
        self.assertEqual(len({p["Label"] for p in plists.values()}), 12)
        self.assertEqual(len({p["StandardOutPath"] for p in plists.values()}), 12)
        self.assertEqual(sum(1 for name in plists if name.endswith("-proceed")), 9)
        for account in ("account-a", "account-b", "account-c"):
            own = sorted(p["StartCalendarInterval"]["Minute"] for p in plists.values()
                         if p["ProgramArguments"][-1] == account)
            gaps = [b - a for a, b in zip(own, own[1:])] + [own[0] + 60 - own[-1]]
            self.assertEqual(len(own), 4, account)
            self.assertGreaterEqual(min(gaps), 15, (account, own))

    def test_linux_proceed_runs_use_their_own_unit_and_mode(self):
        self.write_config("linux", proceed={"account-a": [51]})
        with patch.object(renderer, "node22_bins", return_value=[self.root / "node-bin"]):
            out = renderer.render(self.config, self.root / "linux-proceed-stage", "linux")
        self.assertIn("Description=Dot coordinator account account-a (proceed run)",
                      (out / "ai.dot-coordinator-51-proceed.service").read_text())
        self.assertIn("OnCalendar=*-*-* *:51:00", (out / "ai.dot-coordinator-51-proceed.timer").read_text())
        self.assertIn("COORDINATOR_MODE=\"proceed\"", (out / "ai.dot-coordinator-51-proceed.env").read_text())

    def test_every_run_declares_its_mode_in_the_first_task_sentence(self):
        self.assertEqual(set(renderer.DIRECTIVES), {"main", "proceed"})
        for mode, directive in renderer.DIRECTIVES.items():
            self.assertTrue(directive.startswith(f"Coordination mode: {mode}."), mode)
            self.assertNotIn("\n", directive)
        self.assertIn("SKILL.md", renderer.DIRECTIVES["proceed"])
        self.assertIn("last 20 rendered messages", renderer.DIRECTIVES["proceed"])

    def test_rejects_wrong_cadence_or_host_before_output(self):
        self.write_config("macos", (10, 20, 40))
        output = self.root / "bad-stage"
        with self.assertRaisesRegex(ValueError, "ordered host cadence"):
            renderer.render(self.config, output, "macos")
        self.assertFalse(output.exists())

    def test_rejects_missing_dot_account_and_unpinned_mcp(self):
        config = json.loads(self.config.read_text())
        config["accounts"][0]["key"] = "not-configured"
        self.config.write_text(json.dumps(config))
        with self.assertRaisesRegex(ValueError, "missing from Dot configuration"):
            renderer.render(self.config, self.root / "missing-stage", "macos")
        config["accounts"][0]["key"] = "account-a"
        self.config.write_text(json.dumps(config))
        self.config.chmod(0o600)
        self.package_root.joinpath("package.json").write_text('{"version":"1.5.0"}')
        with self.assertRaisesRegex(ValueError, "version 1.6.0"):
            renderer.render(self.config, self.root / "version-stage", "macos")

    def test_refuses_existing_destination_and_insecure_config(self):
        output = self.root / "existing"
        output.mkdir()
        with self.assertRaisesRegex(ValueError, "already exists"):
            renderer.render(self.config, output, "macos")
        self.config.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "mode 0600"):
            renderer.render(self.config, self.root / "insecure-stage", "macos")

    def test_staging_output_must_be_under_tmp(self):
        with self.assertRaisesRegex(ValueError, "under /tmp"):
            renderer.render(self.config, Path.home() / "not-a-stage", "macos")

    def test_staging_rejects_parent_symlink_outside_tmp_before_writing(self):
        with tempfile.TemporaryDirectory(dir="/var/tmp") as outside:
            target = Path(outside).resolve()
            link = self.root / 'outside-link'
            link.symlink_to(target, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'under /tmp'):
                renderer.render(self.config, link / 'new-parent' / 'stage', 'macos')
            self.assertFalse((target / 'new-parent').exists())

    def test_systemd_environment_escapes_shell_metacharacters(self):
        encoded = renderer.systemd_value('a"b$PATH`x\\y')
        self.assertEqual(encoded, '"a\\"b\\$PATH\\`x\\\\y"')

    def test_legacy_installer_entrypoints_refuse_activation_without_render_flag(self):
        scripts = SCRIPT.parent
        for name in ("install-service.sh", "install-launchagent.sh", "install-systemd.sh"):
            result = subprocess.run(["/bin/bash", str(scripts / name)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn("Activation is not performed", result.stderr)


if __name__ == "__main__":
    unittest.main()
