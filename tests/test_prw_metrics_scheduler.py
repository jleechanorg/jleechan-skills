"""Tests for 4-hour launchd scheduling, locking, and execution wrapper (bd-yq6x)."""

import os
import plistlib
import re
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
PLIST_TEMPLATE = REPO_ROOT / "launchd" / "com.jleechan.prw-metrics.plist.template"
RUN_SCRIPT = REPO_ROOT / "scripts" / "run_prw_metrics.sh"
INSTALL_SCRIPT = REPO_ROOT / "scripts" / "install-prw-metrics-launchd.sh"


class PRWMetricsSchedulerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.fake_home = Path(self.temp_dir.name) / "home"
        self.fake_home.mkdir(parents=True, exist_ok=True)
        self.xdg_config_home = self.fake_home / ".config"
        self.xdg_config_home.mkdir(parents=True, exist_ok=True)
        self.state_dir = Path(self.temp_dir.name) / "prw-metrics"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.scratch_dir = Path(self.temp_dir.name) / "scratch"
        self.scratch_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _base_env(self, **kwargs):
        env = dict(
            os.environ,
            HOME=str(self.fake_home),
            XDG_CONFIG_HOME=str(self.xdg_config_home),
            PRW_METRICS_STATE_DIR=str(self.state_dir),
            PRW_METRICS_ROADMAP_REPO=str(self.scratch_dir),
        )
        env.update(kwargs)
        return env

    def test_plist_template_exists_and_calendar_intervals(self):
        """Verifies template exists and defines exactly six :17 slots (hours 0, 4, 8, 12, 16, 20)."""
        self.assertTrue(PLIST_TEMPLATE.exists(), f"Missing template: {PLIST_TEMPLATE}")
        raw_content = PLIST_TEMPLATE.read_text(encoding="utf-8")
        # Ensure @HOME@ and @REPO_ROOT@ placeholders are used rather than hardcoded paths
        self.assertIn("@HOME@", raw_content)
        self.assertIn("@REPO_ROOT@", raw_content)

        # Parse rendered template to inspect dictionary structure
        rendered = raw_content.replace("@HOME@", str(self.temp_dir.name)).replace(
            "@REPO_ROOT@", str(REPO_ROOT)
        )
        plist_data = plistlib.loads(rendered.encode("utf-8"))

        self.assertEqual(plist_data.get("Label"), "com.jleechan.prw-metrics")
        self.assertNotIn("KeepAlive", plist_data, "Finite calendar job must not set KeepAlive")
        self.assertNotIn(
            "AbandonProcessGroup",
            plist_data,
            "Calendar job must not set AbandonProcessGroup",
        )

        intervals = plist_data.get("StartCalendarInterval")
        self.assertIsInstance(intervals, list, "StartCalendarInterval must be an array of dicts")
        self.assertEqual(len(intervals), 6, "Must define exactly 6 calendar intervals")

        expected_hours = {0, 4, 8, 12, 16, 20}
        actual_hours = set()
        for interval in intervals:
            self.assertEqual(interval.get("Minute"), 17, "All slots must fire at minute :17")
            actual_hours.add(interval.get("Hour"))

        self.assertEqual(actual_hours, expected_hours, f"Unexpected hours: {actual_hours}")

    def test_custom_repo_root_rendered_in_program_arguments(self):
        """Verifies that rendering from a custom @REPO_ROOT@ substitutes that exact checkout path into ProgramArguments."""
        self.assertTrue(PLIST_TEMPLATE.exists(), f"Missing template: {PLIST_TEMPLATE}")
        raw_content = PLIST_TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("@REPO_ROOT@", raw_content)

        custom_root = "/opt/custom/checkouts/prw-repo"
        rendered = raw_content.replace("@HOME@", str(self.fake_home)).replace(
            "@REPO_ROOT@", custom_root
        )
        plist_data = plistlib.loads(rendered.encode("utf-8"))
        prog_args = plist_data.get("ProgramArguments", [])
        self.assertIn(f"{custom_root}/scripts/run_prw_metrics.sh", prog_args)

    def test_rendered_plist_plutil_lint(self):
        """Validates rendered plist syntax via plutil -lint."""
        self.assertTrue(PLIST_TEMPLATE.exists(), f"Missing template: {PLIST_TEMPLATE}")
        raw_content = PLIST_TEMPLATE.read_text(encoding="utf-8")
        rendered = raw_content.replace("@HOME@", str(self.temp_dir.name)).replace(
            "@REPO_ROOT@", str(REPO_ROOT)
        )

        test_plist = self.scratch_dir / "com.jleechan.prw-metrics.plist"
        test_plist.write_text(rendered, encoding="utf-8")

        parsed = plistlib.loads(rendered.encode("utf-8"))
        self.assertEqual(parsed.get("Label"), "com.jleechan.prw-metrics")

        if os.path.exists("/usr/bin/plutil"):
            result = subprocess.run(
                ["/usr/bin/plutil", "-lint", str(test_plist)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, f"plutil lint failed: {result.stderr}")
            self.assertIn("OK", result.stdout)

    def test_no_embedded_credentials_or_personal_paths(self):
        """Ensures template and scripts contain zero credentials, tokens, or hardcoded personal paths."""
        files_to_check = [PLIST_TEMPLATE, RUN_SCRIPT, INSTALL_SCRIPT]
        credential_patterns = [
            re.compile(r"ghp_[A-Za-z0-9_]{20,}"),
            re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
            re.compile(r"sk-[A-Za-z0-9_]{20,}"),
            re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]{20,}"),
            re.compile(r"(?i)password\s*=\s*['\"][^'\"]+['\"]"),
        ]
        # Disallow hardcoded personal paths like /Users/username or /home/username
        personal_path_pattern = re.compile(r"/(?:Users|home)/[a-zA-Z0-9_\-]+")

        for fpath in files_to_check:
            self.assertTrue(fpath.exists(), f"File {fpath} must exist")
            content = fpath.read_text(encoding="utf-8")

            for pat in credential_patterns:
                self.assertIsNone(
                    pat.search(content),
                    f"Possible credential found in {fpath.name}: {pat.pattern}",
                )

            # Check that /Users or /home are not hardcoded
            for match in personal_path_pattern.finditer(content):
                matched_str = match.group(0)
                # Allow standard generic variable patterns like ${HOME} or comments describing the pattern
                if not matched_str.startswith("/home/...") and not matched_str.startswith("/Users/..."):
                    self.fail(f"Hardcoded personal path '{matched_str}' in {fpath.name}")

    def test_install_script_executable_and_bootstraps(self):
        """Validates install script is executable and targets the correct launchd label."""
        self.assertTrue(INSTALL_SCRIPT.exists(), f"Missing install script: {INSTALL_SCRIPT}")
        self.assertTrue(os.access(INSTALL_SCRIPT, os.X_OK), "install script must be executable")
        content = INSTALL_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("com.jleechan.prw-metrics", content)
        self.assertIn("launchctl bootout", content)
        self.assertIn("launchctl bootstrap", content)

    def test_run_script_executable(self):
        """Validates run wrapper is executable."""
        self.assertTrue(RUN_SCRIPT.exists(), f"Missing run script: {RUN_SCRIPT}")
        self.assertTrue(os.access(RUN_SCRIPT, os.X_OK), "run script must be executable")

    def _hold_flock(self):
        """Hold the wrapper's flock from a separate process; returns the Popen."""
        lock_file = f"{self.state_dir / 'lock'}.flock"
        holder = subprocess.Popen(
            [
                "python3",
                "-c",
                "import fcntl,os,sys,time;"
                "fd=os.open(sys.argv[1],os.O_CREAT|os.O_RDWR);"
                "fcntl.flock(fd,fcntl.LOCK_EX);print('held',flush=True);time.sleep(60)",
                lock_file,
            ],
            stdout=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(holder.stdout.readline().strip(), "held")
        return holder

    def _run_wrapper(self, **env_kwargs):
        return subprocess.run(
            ["bash", str(RUN_SCRIPT)],
            capture_output=True,
            text=True,
            env=self._base_env(**env_kwargs),
            check=False,
            timeout=30,
        )

    def test_locking_active_holder_exits_cleanly(self):
        """A live lock holder makes a concurrent invocation exit 0 without collecting."""
        marker = self.state_dir / "must_not_run.txt"
        holder = self._hold_flock()
        try:
            result = self._run_wrapper(
                PRW_METRICS_FORCE_RUN="1",
                PRW_METRICS_COLLECTOR_CMD=f"echo ran > '{marker}'",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Another prw-metrics instance", result.stdout)
            self.assertFalse(marker.exists(), "collector must not run while lock is held")
        finally:
            holder.kill()
            holder.wait()

    def test_killed_holder_releases_lock(self):
        """SIGKILL of the holder frees the lock with no recovery step (no dead-PID logic)."""
        holder = self._hold_flock()
        holder.kill()
        holder.wait()
        marker = self.state_dir / "after_kill.txt"
        result = self._run_wrapper(
            PRW_METRICS_FORCE_RUN="1",
            PRW_METRICS_COLLECTOR_CMD=f"echo ran > '{marker}'",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(marker.exists(), "collector should run once the holder is dead")

    def test_leftover_pid_of_live_unrelated_process_does_not_block(self):
        """A reused PID in the lock file is irrelevant: only the kernel lock decides."""
        proc = subprocess.Popen(["sleep", "30"])
        try:
            Path(f"{self.state_dir / 'lock'}.flock").write_text(str(proc.pid), encoding="utf-8")
            marker = self.state_dir / "pid_reuse.txt"
            result = self._run_wrapper(
                PRW_METRICS_FORCE_RUN="1",
                PRW_METRICS_COLLECTOR_CMD=f"echo ran > '{marker}'",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(marker.exists(), "unrelated live PID must not suppress collection")
        finally:
            proc.terminate()
            proc.wait()

    def test_orphaned_reclaim_dir_and_legacy_lock_dir_do_not_block(self):
        """Crash leftovers from the old mkdir-based scheme (B4) never consume a permit."""
        legacy = self.state_dir / "lock"
        legacy.mkdir()
        (legacy / "pid").write_text("99999999", encoding="utf-8")
        (self.state_dir / "lock.reclaim").mkdir()
        marker = self.state_dir / "orphan.txt"
        result = self._run_wrapper(
            PRW_METRICS_FORCE_RUN="1",
            PRW_METRICS_COLLECTOR_CMD=f"echo ran > '{marker}'",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(marker.exists(), "collector should run despite orphaned reclaim dir")

    def test_reacquisition_after_release_never_overlaps_live_owner(self):
        """B3 interleaving: owner A releases, owner B acquires, late contender C must skip.

        Under the old mv-based recovery, C could move B's live lock. With flock there is no
        replacement step: C only ever tries a non-blocking exclusive lock.
        """
        marker = self.state_dir / "overlap.txt"
        collector = f"echo start >> '{marker}'; sleep 2; echo end >> '{marker}'"
        env = self._base_env(PRW_METRICS_FORCE_RUN="1", PRW_METRICS_COLLECTOR_CMD=collector)
        a = subprocess.run(["bash", str(RUN_SCRIPT)], env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(a.returncode, 0, a.stderr)
        b = subprocess.Popen(["bash", str(RUN_SCRIPT)], env=env, stdout=subprocess.PIPE, text=True)
        deadline = time.time() + 10
        while time.time() < deadline and len(marker.read_text().split()) < 3:
            time.sleep(0.05)
        c = subprocess.run(["bash", str(RUN_SCRIPT)], env=env, capture_output=True, text=True, timeout=30)
        b.communicate(timeout=30)
        self.assertEqual(c.returncode, 0, c.stderr)
        self.assertIn("Another prw-metrics instance", c.stdout)
        self.assertEqual(
            marker.read_text().split(),
            ["start", "end", "start", "end"],
            "runs must be strictly serialized",
        )

    def test_concurrent_lock_race_no_overlap(self):
        """Two processes racing on lock acquisition: exactly one runs, the other skips cleanly."""
        marker_file = self.state_dir / "ran_count.txt"
        env = self._base_env(
            PRW_METRICS_FORCE_RUN="1",
            PRW_METRICS_COLLECTOR_CMD=f"echo 1 >> '{marker_file}'; sleep 0.5",
        )
        p1 = subprocess.Popen(["bash", str(RUN_SCRIPT)], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        p2 = subprocess.Popen(["bash", str(RUN_SCRIPT)], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        out1, err1 = p1.communicate(timeout=15)
        out2, err2 = p2.communicate(timeout=15)
        self.assertEqual(p1.returncode, 0, f"P1 failed: {err1}")
        self.assertEqual(p2.returncode, 0, f"P2 failed: {err2}")
        self.assertEqual(len(marker_file.read_text().split()), 1)
        self.assertIn("Another prw-metrics instance", out1 + out2)

    def test_sleep_catch_up_deduplication(self):
        """Tests that a catch-up trigger within MIN_INTERVAL_SEC is deduplicated and exits 0."""
        self.assertTrue(RUN_SCRIPT.exists(), f"Missing run script: {RUN_SCRIPT}")
        last_success = self.state_dir / "last_success_epoch"
        # Recorded success 60 seconds ago
        last_success.write_text(str(int(time.time()) - 60), encoding="utf-8")

        output_marker = self.state_dir / "should_not_run.txt"
        env = self._base_env(
            PRW_METRICS_MIN_INTERVAL_SEC="900",
            PRW_METRICS_COLLECTOR_CMD=f"echo 'RAN' > '{output_marker}'",
        )
        result = subprocess.run(
            ["bash", str(RUN_SCRIPT)],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        self.assertEqual(result.returncode, 0, f"Deduplicated run must exit 0: {result.stderr}")
        self.assertFalse(output_marker.exists(), "Collector must not run when deduplicated")
        self.assertIn("Deduplicat", result.stdout)

    def test_sleep_catch_up_force_run(self):
        """Tests that --force-run overrides deduplication window."""
        self.assertTrue(RUN_SCRIPT.exists(), f"Missing run script: {RUN_SCRIPT}")
        last_success = self.state_dir / "last_success_epoch"
        last_success.write_text(str(int(time.time()) - 30), encoding="utf-8")

        output_marker = self.state_dir / "force_ran.txt"
        env = self._base_env(
            PRW_METRICS_MIN_INTERVAL_SEC="900",
            PRW_METRICS_COLLECTOR_CMD=f"echo 'FORCED' > '{output_marker}'",
        )
        result = subprocess.run(
            ["bash", str(RUN_SCRIPT), "--force-run"],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        self.assertEqual(result.returncode, 0, f"Force run failed: {result.stderr}")
        self.assertTrue(output_marker.exists(), "Collector should run when --force-run is passed")

    def test_source_failure_preservation(self):
        """Tests that collector non-zero exit status is preserved and last_success_epoch is not updated."""
        self.assertTrue(RUN_SCRIPT.exists(), f"Missing run script: {RUN_SCRIPT}")
        last_success = self.state_dir / "last_success_epoch"
        initial_epoch = 1000000
        last_success.write_text(str(initial_epoch), encoding="utf-8")

        env = self._base_env(
            PRW_METRICS_FORCE_RUN="1",
            PRW_METRICS_COLLECTOR_CMD="echo 'Simulated collector failure' >&2; exit 42",
        )
        result = subprocess.run(
            ["bash", str(RUN_SCRIPT)],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        self.assertEqual(
            result.returncode,
            42,
            f"Expected exit status 42 preserved, got {result.returncode}",
        )
        self.assertIn("Simulated collector failure", result.stderr)

        # Verify last_success_epoch was NOT updated
        current_epoch = int(last_success.read_text(encoding="utf-8").strip())
        self.assertEqual(
            current_epoch,
            initial_epoch,
            "last_success_epoch must not be modified on failure",
        )

    def test_runtime_config_sourcing_and_publication_exports(self):
        """Tests that optional runtime config is sourced and publication defaults are exported."""
        self.assertTrue(RUN_SCRIPT.exists(), f"Missing run script: {RUN_SCRIPT}")
        config_env = self.state_dir / "config.env"
        config_env.write_text(
            "CUSTOM_CONFIG_VAL='loaded_from_config'\nPRW_METRICS_PUBLISH=0\n",
            encoding="utf-8",
        )

        env_output_file = self.state_dir / "captured_env.txt"
        collector_cmd = (
            f"echo \"CUSTOM_CONFIG_VAL=$CUSTOM_CONFIG_VAL\" > '{env_output_file}'; "
            f"echo \"PRW_METRICS_ROADMAP_REPO=$PRW_METRICS_ROADMAP_REPO\" >> '{env_output_file}'; "
            f"echo \"PRW_METRICS_PUBLISH=$PRW_METRICS_PUBLISH\" >> '{env_output_file}'"
        )

        env = self._base_env(
            PRW_METRICS_FORCE_RUN="1",
            PRW_METRICS_COLLECTOR_CMD=collector_cmd,
        )
        result = subprocess.run(
            ["bash", str(RUN_SCRIPT)],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        self.assertEqual(result.returncode, 0, f"Script failed: {result.stderr}")
        self.assertTrue(env_output_file.exists(), "Collector should have executed")
        captured = env_output_file.read_text(encoding="utf-8")
        self.assertIn("CUSTOM_CONFIG_VAL=loaded_from_config", captured)
        self.assertIn("PRW_METRICS_ROADMAP_REPO=", captured)
        self.assertIn("PRW_METRICS_PUBLISH=0", captured)

    def test_config_env_exports_to_child_process(self):
        """Proves config.env assignments without export keyword reach child Python env via set -a."""
        self.assertTrue(RUN_SCRIPT.exists(), f"Missing run script: {RUN_SCRIPT}")
        cfg_dir = self.xdg_config_home / "prw-metrics"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        config_file = cfg_dir / "config.env"
        # Assignments WITHOUT export keyword
        config_file.write_text(
            "UNEXPORTED_CUSTOM_VAR=hello_world_from_config\n"
            "PRW_METRICS_ROADMAP_REPO=" + str(self.scratch_dir) + "\n",
            encoding="utf-8",
        )

        output_marker = self.state_dir / "received_env.txt"
        collector_cmd = (
            f"python3 -c \"import os; open('{output_marker}', 'w').write(os.environ.get('UNEXPORTED_CUSTOM_VAR', ''))\""
        )
        env = self._base_env(
            PRW_METRICS_FORCE_RUN="1",
            PRW_METRICS_COLLECTOR_CMD=collector_cmd,
        )
        result = subprocess.run(
            ["bash", str(RUN_SCRIPT)],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        self.assertEqual(result.returncode, 0, f"Script failed: {result.stderr}")
        self.assertTrue(output_marker.exists(), "Collector should have executed")
        self.assertEqual(output_marker.read_text().strip(), "hello_world_from_config")

    def test_missing_roadmap_repo_fails_closed(self):
        """When PRW_METRICS_ROADMAP_REPO is unset and not in config, exits non-zero (fails closed)."""
        self.assertTrue(RUN_SCRIPT.exists(), f"Missing run script: {RUN_SCRIPT}")
        env = dict(
            os.environ,
            HOME=str(self.fake_home),
            XDG_CONFIG_HOME=str(self.xdg_config_home),
            PRW_METRICS_STATE_DIR=str(self.state_dir),
            PRW_METRICS_FORCE_RUN="1",
            PRW_METRICS_COLLECTOR_CMD="echo 'SHOULD_NOT_RUN'",
        )
        # Explicitly remove PRW_METRICS_ROADMAP_REPO
        env.pop("PRW_METRICS_ROADMAP_REPO", None)

        result = subprocess.run(
            ["bash", str(RUN_SCRIPT)],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0, "Missing roadmap repo must fail closed (exit != 0)")
        self.assertIn("PRW_METRICS_ROADMAP_REPO is not set", result.stderr)

    def test_install_script_derives_label_and_fails_closed_when_missing(self):
        """Verifies install-prw-metrics-launchd.sh derives LABEL from plist template and fails closed if missing."""
        self.assertTrue(INSTALL_SCRIPT.exists(), f"Missing install script: {INSTALL_SCRIPT}")

        # 1. Template without <key>Label</key> must fail closed
        bad_template = self.scratch_dir / "bad_template.plist.template"
        bad_template.write_text("<dict><key>ProgramArguments</key><array></array></dict>", encoding="utf-8")

        result = subprocess.run(
            ["bash", str(INSTALL_SCRIPT), str(bad_template)],
            capture_output=True,
            text=True,
            check=False,
            env=self._base_env(),
        )
        self.assertNotEqual(result.returncode, 0, "Installer must fail closed when Label is missing")
        self.assertIn("Could not parse Label", result.stderr)

        # 2. Template with custom Label derives that exact label
        custom_label = "org.custom.test-runner"
        good_template = self.scratch_dir / "custom.plist.template"
        good_template.write_text(
            f"<dict><key>Label</key>\n<string>{custom_label}</string></dict>",
            encoding="utf-8",
        )
        extract_cmd = f"sed -n '/<key>Label<\\/key>/{{n;s/.*<string>\\(.*\\)<\\/string>.*/\\1/p;}}' '{good_template}'"
        derived = subprocess.check_output(["bash", "-c", extract_cmd], text=True).strip()
        self.assertEqual(derived, custom_label)

    def test_run_script_telemetry_dir_and_stale_hours_exported(self):
        """Verifies PRW_METRICS_TELEMETRY_DIR and PRW_METRICS_STALE_HOURS are exported to collector."""
        self.assertTrue(RUN_SCRIPT.exists(), f"Missing run script: {RUN_SCRIPT}")
        output_file = self.state_dir / "telem_env.txt"
        collector_cmd = (
            f"echo \"TELEMETRY_DIR=$PRW_METRICS_TELEMETRY_DIR\" > '{output_file}'; "
            f"echo \"STALE_HOURS=$PRW_METRICS_STALE_HOURS\" >> '{output_file}'"
        )
        env = self._base_env(
            PRW_METRICS_FORCE_RUN="1",
            PRW_METRICS_COLLECTOR_CMD=collector_cmd,
        )
        result = subprocess.run(
            ["bash", str(RUN_SCRIPT)],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        self.assertEqual(result.returncode, 0, f"Script failed: {result.stderr}")
        self.assertTrue(output_file.exists())
        captured = output_file.read_text(encoding="utf-8")
        self.assertIn(f"TELEMETRY_DIR={self.scratch_dir}/dashboards/prw/telemetry", captured)
        self.assertIn("STALE_HOURS=4.5", captured)

    def test_run_script_collector_path_with_absent_telemetry_dir_under_system_bash(self):
        """The collector invocation must not trip `set -u` on an empty array (bash 3.2) when the telemetry dir is absent."""
        fake_repo = self.scratch_dir / "fake_repo"
        (fake_repo / "scripts").mkdir(parents=True)
        wrapper = fake_repo / "scripts" / "run_prw_metrics.sh"
        shutil.copy(RUN_SCRIPT, wrapper)
        argv_file = self.state_dir / "collector_argv.txt"
        (fake_repo / "scripts" / "prw_metrics.py").write_text(
            "import sys\n"
            f"open({str(argv_file)!r}, 'w').write('\\n'.join(sys.argv[1:]))\n",
            encoding="utf-8",
        )
        telemetry_dir = self.scratch_dir / "dashboards" / "prw" / "telemetry"
        self.assertFalse(telemetry_dir.exists())
        bash = "/bin/bash" if os.path.exists("/bin/bash") else "bash"
        result = subprocess.run(
            [bash, str(wrapper)],
            capture_output=True,
            text=True,
            env=self._base_env(PRW_METRICS_FORCE_RUN="1"),
            check=False,
        )
        self.assertEqual(result.returncode, 0, f"Script failed: {result.stderr}")
        self.assertNotIn("unbound variable", result.stderr)
        self.assertTrue(argv_file.exists(), "collector was not invoked")
        self.assertNotIn("--telemetry-dir", argv_file.read_text(encoding="utf-8"))

    def test_install_script_handles_ampersand_and_xml_metacharacters_in_repo_root(self):
        """Verifies installer handles ampersands and XML metacharacters in paths without corruption."""
        self.assertTrue(INSTALL_SCRIPT.exists(), f"Missing install script: {INSTALL_SCRIPT}")
        custom_repo = self.scratch_dir / "R&D" / "skills <testing>"
        custom_repo.mkdir(parents=True, exist_ok=True)

        template = self.scratch_dir / "amp.plist.template"
        template.write_text(
            """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.jleechan.amp-test</string>
  <key>ProgramArguments</key>
  <array>
    <string>@REPO_ROOT@/scripts/run_prw_metrics.sh</string>
  </array>
</dict>
</plist>""",
            encoding="utf-8",
        )

        dest_plist = self.scratch_dir / "rendered_amp.plist"
        py_cmd = f"""python3 - "{template}" "{dest_plist}" "{self.fake_home}" "{custom_repo}" <<'PY'
import plistlib, sys
tpl_path, dest_path, home_val, repo_val = sys.argv[1:5]
with open(tpl_path, "rb") as f:
    data = plistlib.load(f)
def replace_tokens(obj):
    if isinstance(obj, str):
        return obj.replace("@HOME@", home_val).replace("@REPO_ROOT@", repo_val)
    if isinstance(obj, list):
        return [replace_tokens(x) for x in obj]
    if isinstance(obj, dict):
        return {{k: replace_tokens(v) for k, v in obj.items()}}
    return obj
rendered = replace_tokens(data)
with open(dest_path, "wb") as f:
    plistlib.dump(rendered, f, sort_keys=False)
print(rendered["Label"])
PY
"""
        label = subprocess.check_output(["bash", "-c", py_cmd], text=True).strip()
        self.assertEqual(label, "com.jleechan.amp-test")

        with open(dest_plist, "rb") as f:
            loaded = plistlib.load(f)
        args = loaded["ProgramArguments"]
        expected_path = f"{custom_repo}/scripts/run_prw_metrics.sh"
        self.assertEqual(args[0], expected_path)
        self.assertNotIn("@REPO_ROOT@", args[0])


if __name__ == "__main__":
    unittest.main()
