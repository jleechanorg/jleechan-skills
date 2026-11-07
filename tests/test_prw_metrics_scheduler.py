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

    def test_locking_active_pid_exits_cleanly(self):
        """Tests that a concurrent invocation exits cleanly (0) when lock is held by an active PID."""
        self.assertTrue(RUN_SCRIPT.exists(), f"Missing run script: {RUN_SCRIPT}")
        lock_dir = self.state_dir / "lock"
        lock_dir.mkdir(parents=True, exist_ok=True)
        pid_file = lock_dir / "pid"
        comm_file = lock_dir / "comm"

        # Spawn a long-running background dummy process to simulate active lock holder
        proc = subprocess.Popen(["sleep", "30"])
        try:
            pid_file.write_text(str(proc.pid), encoding="utf-8")
            comm_file.write_text("sleep", encoding="utf-8")

            env = self._base_env(
                PRW_METRICS_COLLECTOR_CMD="exit 99",
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
                0,
                f"Concurrent run should exit 0 without colliding. Stderr: {result.stderr}",
            )
            self.assertIn(
                str(proc.pid),
                result.stdout,
                "Expected output to mention the active lock PID",
            )
        finally:
            proc.terminate()
            proc.wait()

    def test_locking_stale_pid_recovery(self):
        """Tests that a dead PID in lock file is safely recovered and collector proceeds."""
        self.assertTrue(RUN_SCRIPT.exists(), f"Missing run script: {RUN_SCRIPT}")
        lock_dir = self.state_dir / "lock"
        lock_dir.mkdir(parents=True, exist_ok=True)
        pid_file = lock_dir / "pid"
        comm_file = lock_dir / "comm"
        # 99999999 is guaranteed dead
        pid_file.write_text("99999999", encoding="utf-8")
        comm_file.write_text("bash", encoding="utf-8")

        output_marker = self.state_dir / "collector_ran.txt"
        env = self._base_env(
            PRW_METRICS_COLLECTOR_CMD=f"echo 'RAN' > '{output_marker}'",
        )
        result = subprocess.run(
            ["bash", str(RUN_SCRIPT)],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        self.assertEqual(result.returncode, 0, f"Failed stale recovery: {result.stderr}")
        self.assertTrue(output_marker.exists(), "Collector should have executed after stale lock recovery")
        self.assertIn("Stale lock detected", result.stdout)

    def test_recycled_pid_different_comm_treated_as_stale(self):
        """Existing PID belongs to a different process command name -> treated as stale and recovered."""
        self.assertTrue(RUN_SCRIPT.exists(), f"Missing run script: {RUN_SCRIPT}")
        lock_dir = self.state_dir / "lock"
        lock_dir.mkdir(parents=True, exist_ok=True)
        pid_file = lock_dir / "pid"
        comm_file = lock_dir / "comm"

        # Spawn a live process with command name 'sleep'
        proc = subprocess.Popen(["sleep", "30"])
        try:
            pid_file.write_text(str(proc.pid), encoding="utf-8")
            # Write a different command name that cannot match sleep
            comm_file.write_text("old_unrelated_daemon", encoding="utf-8")

            output_marker = self.state_dir / "recycled_recovered.txt"
            env = self._base_env(
                PRW_METRICS_FORCE_RUN="1",
                PRW_METRICS_COLLECTOR_CMD=f"echo 'RECOVERED' > '{output_marker}'",
            )
            result = subprocess.run(
                ["bash", str(RUN_SCRIPT)],
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            self.assertEqual(result.returncode, 0, f"Script failed: {result.stderr}")
            self.assertTrue(output_marker.exists(), "Collector should have executed after stale recovery")
            self.assertIn("Stale lock detected", result.stdout)
        finally:
            proc.terminate()
            proc.wait()

    def test_concurrent_lock_race_no_overlap(self):
        """Two processes racing on lock acquisition: exactly one runs, the other skips cleanly."""
        self.assertTrue(RUN_SCRIPT.exists(), f"Missing run script: {RUN_SCRIPT}")
        marker_file = self.state_dir / "ran_count.txt"
        collector_cmd = f"echo 1 >> '{marker_file}'; sleep 0.5"

        env = self._base_env(
            PRW_METRICS_FORCE_RUN="1",
            PRW_METRICS_COLLECTOR_CMD=collector_cmd,
        )

        p1 = subprocess.Popen(["bash", str(RUN_SCRIPT)], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        p2 = subprocess.Popen(["bash", str(RUN_SCRIPT)], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        out1, err1 = p1.communicate(timeout=15)
        out2, err2 = p2.communicate(timeout=15)

        self.assertEqual(p1.returncode, 0, f"P1 failed: {err1}")
        self.assertEqual(p2.returncode, 0, f"P2 failed: {err2}")

        self.assertTrue(marker_file.exists(), "At least one process should run collector")
        lines = marker_file.read_text().strip().splitlines()
        self.assertEqual(len(lines), 1, f"Expected exactly 1 run, got {len(lines)}")

        combined_out = out1 + out2
        self.assertIn("Another prw-metrics instance", combined_out)

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


# Alias for test discovery
TestSchedulerScript = PRWMetricsSchedulerTests


if __name__ == "__main__":
    unittest.main()
