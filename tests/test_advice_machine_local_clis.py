"""The advice skill resolves reviewer commands from machine-local env values only."""
import re
import tempfile
import unittest
import unittest.mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".claude/skills/advice/SKILL.md"


class AdviceMachineLocalCliTest(unittest.TestCase):
    def setUp(self):
        self.text = SKILL.read_text(encoding="utf-8")

    def test_every_seat_resolves_from_an_env_variable_with_a_default(self):
        for name in ("ADVICE_CODEX_CMD", "ADVICE_CLAUDE_CMD", "ADVICE_CLAUDE_ALT_CMD", "ADVICE_EXTRA_CLIS"):
            self.assertIn(name, self.text, name)
        self.assertIn("falls back to the default", self.text)
        self.assertIn("so a bare machine still works", self.text)

    def test_extra_cli_registration_is_documented_with_safe_parsing(self):
        section = " ".join(self.text.split("### `ADVICE_EXTRA_CLIS`", 1)[1].split("## 3.", 1)[0].split())
        self.assertIn("seats separated by `|`", section)
        self.assertIn("Split on `|`, then on the **first** `=`", section)
        self.assertIn("{prompt}", section)
        self.assertIn("No shell evaluation", section)
        self.assertIn("makes that seat `UNAVAILABLE`", section)
        self.assertIn("never becomes a second vote from the same identity", section)

    def test_no_machine_specific_configuration_is_committed(self):
        self.assertIn("Machine-specific configuration never lives in this repository", self.text)
        self.assertIn("belongs in", self.text)
        self.assertIn("never in a skill file, a PR or a document", self.text)
        # concrete machine paths, credential-store dirs and profile names must not appear
        for forbidden in (".claude-wa", "/Users/", "/home/", "user_data_dir", "CLAUDE_CONFIG_DIR="):
            self.assertNotIn(forbidden, self.text, forbidden)
        self.assertIsNone(re.search(r"\b[A-Za-z0-9_.-]+/roadmap(?:/|\b)", self.text))

    def test_wrapper_alternate_is_named_as_a_shape_not_a_path(self):
        self.assertIn("claudewa", self.text)
        self.assertIn("the attempt records the\nactual model it ran", self.text)


class SeatCommandResolutionTest(unittest.TestCase):
    """The pair runner must honour the machine-local seat variables."""

    def setUp(self):
        import importlib.util
        script = ROOT / ".claude/skills/advice/scripts/run_primary_pair.py"
        spec = importlib.util.spec_from_file_location("run_primary_pair_seats", script)
        self.runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.runner)

    def test_unset_variable_uses_the_portable_default(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "default-reviewer"
            executable.write_text("#!/bin/sh\nexit 0\n")
            executable.chmod(0o700)
            with unittest.mock.patch.dict("os.environ", {}, clear=True):
                argv = self.runner.seat_command("ADVICE_TEST_CMD", [str(executable), "-p"])
        self.assertEqual(argv, [str(executable), "-p"])

    def test_configured_seat_never_falls_back(self):
        for value in ("", "   ", "/nonexistent/adif-reviewer --flag"):
            with unittest.mock.patch.dict("os.environ", {"ADVICE_TEST_CMD": value}, clear=True):
                self.assertIsNone(self.runner.seat_command("ADVICE_TEST_CMD", ["claude", "-p"]), value)

    def test_value_is_shlex_split_without_shell_evaluation(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "reviewer wrapper"
            executable.write_text("#!/bin/sh\nexit 0\n")
            executable.chmod(0o700)
            import shlex as _shlex
            value = f"{_shlex.quote(str(executable))} --model $HOME/x 'literal arg'"
            with unittest.mock.patch.dict("os.environ", {"ADVICE_TEST_CMD": value}, clear=True):
                argv = self.runner.seat_command("ADVICE_TEST_CMD", ["claude"])
            self.assertEqual(argv, [str(executable), "--model", "$HOME/x", "literal arg"])


if __name__ == "__main__":
    unittest.main()
