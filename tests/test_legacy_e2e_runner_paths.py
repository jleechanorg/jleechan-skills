import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
COMMANDS_DIR = REPO_ROOT / ".claude" / "commands" / "extended-library"
SCRIPTS_DIR = REPO_ROOT / ".claude" / "scripts"
LEGACY_DIR = REPO_ROOT / "claude_command_scripts"


class LegacyE2ERunnerPathTests(unittest.TestCase):
    def test_e2e_commands_reference_installed_wrappers_only(self):
        for command in ("teste", "tester", "testerc"):
            installed_script = SCRIPTS_DIR / f"{command}.sh"
            legacy_script = LEGACY_DIR / f"{command}.sh"
            command_doc = (COMMANDS_DIR / f"{command}.md").read_text(encoding="utf-8")
            command_reference = (
                REPO_ROOT / ".claude/skills/extended-library/references/extended-library"
                / f"{command}.md"
            ).read_text(encoding="utf-8")

            self.assertTrue(installed_script.is_file(), installed_script)
            self.assertTrue(os.access(installed_script, os.X_OK), installed_script)
            self.assertFalse(legacy_script.exists(), legacy_script)
            self.assertIn(f"references/extended-library/{command}.md", command_doc)
            self.assertIn(f".claude/scripts/{command}.sh", command_reference)
            self.assertNotIn(f"claude_command_scripts/{command}.sh", command_reference)

    def test_real_wrappers_fail_before_prompt_when_required_key_is_missing(self):
        cases = (
            ("tester", "GEMINI_API_KEY"),
            ("testerc", "TEST_GEMINI_API_KEY"),
        )
        for command, required_key in cases:
            with self.subTest(command=command):
                environment = os.environ.copy()
                environment.pop(required_key, None)
                with tempfile.TemporaryDirectory() as temporary_directory:
                    result = subprocess.run(
                        [str(SCRIPTS_DIR / f"{command}.sh")],
                        cwd=temporary_directory,
                        env=environment,
                        capture_output=True,
                        text=True,
                        check=False,
                    )

                self.assertEqual(result.returncode, 1, result)
                self.assertIn(f"ERROR: {required_key} not set", result.stdout)
                self.assertNotIn("Continue with real service testing?", result.stdout)
                self.assertNotIn("run_e2e_tests.sh not found", result.stdout)

    def test_testerc_sets_timestamped_capture_directory_on_safe_cancel(self):
        environment = os.environ.copy()
        environment["TEST_GEMINI_API_KEY"] = "test-only-placeholder"
        with tempfile.TemporaryDirectory() as temporary_directory:
            Path(temporary_directory, "run_e2e_tests.sh").touch()
            result = subprocess.run(
                [str(SCRIPTS_DIR / "testerc.sh")],
                cwd=temporary_directory,
                env=environment,
                input="n\n",
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1, result)
        self.assertRegex(
            result.stdout,
            r"Capture Directory: /tmp/test_captures/\d{8}_\d{6}\n",
        )
        self.assertIn("Capture mode testing cancelled", result.stdout)

    def test_docs_match_wrapper_environment_contracts(self):
        reference_dir = REPO_ROOT / ".claude/skills/extended-library/references/extended-library"
        teste_doc = (reference_dir / "teste.md").read_text(encoding="utf-8")
        tester_doc = (reference_dir / "tester.md").read_text(encoding="utf-8")
        testerc_doc = (reference_dir / "testerc.md").read_text(encoding="utf-8")

        self.assertIn("TEST_MODE=mock", teste_doc)
        self.assertNotIn("TESTING=true", teste_doc)

        self.assertIn("GEMINI_API_KEY", tester_doc)
        self.assertIn("TEST_FIRESTORE_PROJECT", tester_doc)
        for stale_name in (
            "REAL_GEMINI_API_KEY",
            "REAL_FIREBASE_PROJECT",
            "FIREBASE_PROJECT_ID",
        ):
            self.assertNotIn(stale_name, tester_doc)

        self.assertIn("TEST_GEMINI_API_KEY", testerc_doc)
        self.assertIn("TEST_FIRESTORE_PROJECT", testerc_doc)
        self.assertRegex(
            testerc_doc,
            re.compile(r"/tmp/test_captures/<YYYYMMDD_HHMMSS>/"),
        )
        self.assertIn("TEST_CAPTURE_DIR", testerc_doc)
        for stale_name in (
            "REAL_GEMINI_API_KEY",
            "REAL_FIREBASE_PROJECT",
            "FIREBASE_PROJECT_ID",
            "CAPTURE_OUTPUT_DIR",
            "./test_data_capture/",
        ):
            self.assertNotIn(stale_name, testerc_doc)


if __name__ == "__main__":
    unittest.main(verbosity=2)
