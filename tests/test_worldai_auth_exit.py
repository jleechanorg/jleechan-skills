import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


NODE = shutil.which("node") or "node"
WRAPPER = (
    Path(__file__).resolve().parents[1]
    / "plugins/worldarchitect/skills/worldai-auth/scripts/auth-worldai.mjs"
)


class WorldAIAuthExitTest(unittest.TestCase):
    def run_wrapper(self, child_source):
        with tempfile.TemporaryDirectory() as temp_dir:
            child = Path(temp_dir) / "fake-auth-cli.mjs"
            child.write_text(child_source)
            env = {
                "PATH": os.environ["PATH"],
                "HOME": temp_dir,
                "AUTH_CLI_PATH": str(child),
                "FIREBASE_PROJECT_ID": "fake-project-id",
                "FIREBASE_API_KEY": "fake-web-api-key",
            }
            return subprocess.run(
                [NODE, str(WRAPPER), "status"],
                check=False,
                capture_output=True,
                env=env,
                timeout=10,
            )

    def test_propagates_normal_child_exit_codes(self):
        for child_code in (0, 7):
            with self.subTest(child_code=child_code):
                result = self.run_wrapper(f"process.exit({child_code});\n")
                self.assertEqual(result.returncode, child_code, result.stderr.decode())

    def test_signal_terminated_child_is_not_reported_as_success(self):
        result = self.run_wrapper("process.kill(process.pid, 'SIGTERM');\n")
        self.assertNotEqual(result.returncode, 0, result.stderr.decode())


if __name__ == "__main__":
    unittest.main()
