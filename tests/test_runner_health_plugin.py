import os
from pathlib import Path
import subprocess
import unittest


SCRIPTS = (
    Path(__file__).resolve().parents[1]
    / "plugins/self-hosted-runners/skills/runner-health/scripts"
)


class RunnerHealthPluginTest(unittest.TestCase):
    def test_existing_shell_contracts(self):
        env = dict(os.environ, BASH_ENV="/dev/null")
        for name in (
            "test_check_runner_host.sh",
            "test_check_session_conflict.sh",
            "test_check_api.sh",
        ):
            with self.subTest(script=name):
                result = subprocess.run(
                    ["bash", str(SCRIPTS / name)],
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
