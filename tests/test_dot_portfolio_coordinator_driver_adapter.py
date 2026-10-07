import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / ".claude" / "skills" / "dot-portfolio-coordinator" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from modules.driver_adapter import DriverAdapter
from modules.process_utils import ProcessTimeoutError


class TestDriverAdapter(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()
        self.packet = {
            "task_id": "task-123",
            "event_id": "event-456",
            "authority": {"scope": "authorized task only"},
            "snapshot": {"status": "in progress", "evidence": []},
            "previous_dot_reply": "The first dialogue turn.",
            "dialogue_stage": "inventory",
        }
        self.decision = {
            "event_id": "event-456",
            "task_id": "task-123",
            "stage": "inventory",
            "blockers": [{
                "description": "None identified",
                "evidence": "The supplied snapshot shows no blocker.",
                "attempts": "No attempt is needed.",
                "missing_capability_or_approval": "None.",
                "independent_work": "Proceed with the authorized next step.",
            }],
            "message": "Please proceed with the authorized next step.",
        }
        self.response_text = json.dumps(self.decision)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _fake_driver(self, name, script):
        executable = self.bin_dir / name
        executable.write_text("#!/usr/bin/env python3\n" + script, encoding="utf-8")
        executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
        return executable

    def _path_env(self):
        return {"PATH": f"{self.bin_dir}{os.pathsep}{os.environ['PATH']}"}

    def test_agy_default_uses_real_stream_protocol_and_full_permission_mode(self):
        response = self.response_text
        self._fake_driver("agy", f'''import json, sys
args = sys.argv[1:]
assert "--dangerously-skip-permissions" in args
assert "--new-project" in args
assert ("--input-format" in args and
        args[args.index("--input-format") + 1] == "stream-json")
assert ("--output-format" in args and
        args[args.index("--output-format") + 1] == "stream-json")
message = json.loads(sys.stdin.readline())
assert message["event"] == "user"
assert isinstance(message["message"]["content"], str)
assert "Merge Integrity" in message["message"]["content"]
print(json.dumps({{"event": "result", "result": {{"status": "SUCCESS",
    "response": {response!r}}}}}))
''')
        with mock.patch.dict(os.environ, self._path_env()):
            result = DriverAdapter().decide(self.packet, self.workspace)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["decision"]["event_id"], "event-456")
        self.assertEqual(result["decision"]["message"], self.decision["message"])

    def test_claude_output_envelope_and_full_permission_mode(self):
        response = self.response_text
        self._fake_driver("claude", f'''import json, pathlib, sys
args = sys.argv[1:]
assert "--dangerously-skip-permissions" in args
assert "--output-format" in args and args[args.index("--output-format") + 1] == "json"
assert "ANTHROPIC_API_KEY" not in __import__("os").environ
assert "ANTHROPIC_BASE_URL" not in __import__("os").environ
prompt_arg = next(value for value in args if value.startswith("@"))
assert "dialogue_stage" in pathlib.Path(prompt_arg[1:]).read_text()
print(json.dumps({{"type": "result", "subtype": "success",
    "is_error": False, "result": {response!r}}}))
''')
        env = {
            **self._path_env(),
            "ANTHROPIC_API_KEY": "private-key",
            "ANTHROPIC_BASE_URL": "https://invalid.example",
        }
        with mock.patch.dict(os.environ, env):
            result = DriverAdapter("claude").decide(self.packet, self.workspace)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["decision"]["stage"], "inventory")

    def test_codex_reads_prompt_from_stdin_and_last_message_file(self):
        response = self.response_text
        self._fake_driver("codex", f'''import pathlib, sys
args = sys.argv[1:]
assert args[0] == "exec"
assert "--yolo" in args
assert "--skip-git-repo-check" in args
assert "OPENAI_API_KEY" not in __import__("os").environ
assert "--output-last-message" in args
prompt = sys.stdin.read()
assert "dialogue_stage" in prompt
out = pathlib.Path(args[args.index("--output-last-message") + 1])
out.write_text({response!r})
''')
        env = {**self._path_env(), "OPENAI_API_KEY": "private-key"}
        with mock.patch.dict(os.environ, env):
            result = DriverAdapter("codex").decide(self.packet, self.workspace)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["decision"]["task_id"], "task-123")

    def test_cli_failure_is_driver_failed_not_semantic_blocked(self):
        self._fake_driver(
            "agy", "import sys\nsys.stderr.write('private output')\nsys.exit(9)\n"
        )
        with mock.patch.dict(os.environ, self._path_env()):
            result = DriverAdapter().decide(self.packet, self.workspace)
        self.assertEqual(result, {"status": "driver_failed", "reason": "nonzero_exit"})

    def test_malformed_response_is_driver_failed(self):
        self._fake_driver("agy", "print('{bad json')\n")
        with mock.patch.dict(os.environ, self._path_env()):
            result = DriverAdapter().decide(self.packet, self.workspace)
        self.assertEqual(
            result, {"status": "driver_failed", "reason": "invalid_output"}
        )

    def test_missing_selected_cli_is_driver_failure(self):
        with mock.patch.dict(os.environ, {"PATH": str(self.bin_dir)}):
            result = DriverAdapter().decide(self.packet, self.workspace)
        self.assertEqual(
            result, {"status": "driver_failed", "reason": "driver_unavailable"}
        )

    def test_extra_packet_fields_are_rejected_without_prompt_leak(self):
        packet = dict(self.packet, access_token="secret-must-not-leak")
        result = DriverAdapter().decide(packet, self.workspace)
        self.assertEqual(
            result, {"status": "driver_failed", "reason": "invalid_packet"}
        )

    def test_full_previous_reply_is_passed_without_truncation(self):
        self.packet["previous_dot_reply"] = "private prior response " * 1000
        self.decision["message"] = "x" * 6000
        response = json.dumps(self.decision)
        self._fake_driver("agy", f'''import json, sys
message = json.loads(sys.stdin.readline())
assert {"private prior response "!r} * 1000 in message["message"]["content"]
print(json.dumps({{"event": "result", "result": {{
    "status": "SUCCESS", "response": {response!r}}}}}))
''')
        with mock.patch.dict(os.environ, self._path_env()):
            result = DriverAdapter().decide(self.packet, self.workspace)
        self.assertEqual(len(result["decision"]["message"]), 6000)

    def test_wrong_task_event_or_stage_output_is_rejected(self):
        decision = dict(self.decision, event_id="other-event")
        response = json.dumps(decision)
        self._fake_driver("agy", f'''import json
print(json.dumps({{"event": "result", "result": {{"status": "SUCCESS",
    "response": {response!r}}}}}))
''')
        with mock.patch.dict(os.environ, self._path_env()):
            result = DriverAdapter().decide(self.packet, self.workspace)
        self.assertEqual(
            result, {"status": "driver_failed", "reason": "invalid_output"}
        )

    def test_oversized_packet_fails_without_truncation(self):
        self.packet["previous_dot_reply"] = "x" * 100_000
        result = DriverAdapter().decide(self.packet, self.workspace)
        self.assertEqual(
            result, {"status": "driver_failed", "reason": "input_too_large"}
        )

    def test_timeout_is_driver_failure(self):
        self._fake_driver("agy", "raise SystemExit(0)\n")
        with mock.patch.dict(os.environ, self._path_env()), \
                mock.patch("modules.driver_adapter.run_bounded_command",
                           side_effect=ProcessTimeoutError("private timeout details")):
            result = DriverAdapter().decide(self.packet, self.workspace)
        self.assertEqual(result, {"status": "driver_failed", "reason": "timeout"})

    def test_challenge_stage_is_preserved(self):
        packet = dict(self.packet, dialogue_stage="challenge")
        decision = dict(self.decision, stage="challenge")
        response = json.dumps(decision)
        self._fake_driver("agy", f'''import json, sys
message = json.loads(sys.stdin.readline())
assert "Challenge stage:" in message["message"]["content"]
print(json.dumps({{"event": "result", "result": {{
    "status": "SUCCESS", "response": {response!r}}}}}))
''')
        with mock.patch.dict(os.environ, self._path_env()):
            result = DriverAdapter().decide(packet, self.workspace)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["decision"]["stage"], "challenge")


if __name__ == "__main__":
    unittest.main()
