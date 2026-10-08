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

from modules.driver_adapter import DriverAdapter, _validate_decision, _validate_packet
from modules.process_utils import ProcessTimeoutError


class TestDriverAdapter(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()
        self.packet = self._schema_v1_packet()
        self.packet["previous_dot_reply"] = "The first dialogue turn."
        self.decision = self._schema_v1_decision(self.packet)
        self.decision["blockers"] = [{
            "description": "None identified",
            "evidence": "The supplied snapshot shows no blocker.",
            "attempts": "No attempt is needed.",
            "missing_capability_or_approval": "None.",
            "independent_work": "Proceed with the authorized next step.",
        }]
        self.decision["message"] = "Please proceed with the authorized next step."
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

    def _schema_v1_packet(self, stage="inventory", candidates=None):
        source_binding = {
            "source_id": "roadmap",
            "task_composite_key": ["github.com", "org/repo", "beads", "wa-1"],
            "record_version": "17",
            "record_digest": "a" * 64,
        }
        grant_binding = {"grant_version": 2, "grant_sha256": "b" * 64}
        correlation = None if stage == "inventory" else {
            "parent_event_id": "parent-1",
            "user_message_id": "user-1",
            "assistant_message_id": "assistant-1",
            "start_cursor": "cursor-a",
            "end_cursor": "cursor-b",
            "complete": True,
        }
        candidates = candidates if candidates is not None else [{
            "task_id": "task-123", "source_binding": source_binding,
        }]
        return {
            "schema_version": 1,
            "task_id": "task-123" if stage != "inventory" else None,
            "event_id": "event-456",
            "authority": {"scope": "authorized task only"},
            "snapshot": {"status": "in progress", "evidence": []},
            "previous_dot_reply": "private correlated reply",
            "dialogue_stage": stage,
            "phase": {"inventory": "inventory_due", "challenge": "challenge_reply_due",
                      "final_judgment": "challenge_reply_due"}[stage],
            "candidate_bindings": candidates,
            "source_binding": source_binding if stage != "inventory" else None,
            "grant_binding": grant_binding,
            "correlation": correlation,
        }

    def _schema_v1_decision(self, packet, outcome="send_proposal", action="send"):
        stage = packet["dialogue_stage"]
        if outcome == "no_eligible_task":
            task_id = source_binding = None
        else:
            task_id = packet["task_id"] or packet["candidate_bindings"][0]["task_id"]
            source_binding = packet["source_binding"] or packet["candidate_bindings"][0]["source_binding"]
        return {
            "schema_version": 1,
            "event_id": packet["event_id"],
            "task_id": task_id,
            "outcome": outcome,
            "stage": stage,
            "source_binding": source_binding,
            "grant_binding": packet["grant_binding"],
            "correlation": packet["correlation"],
            "judgment": {"assessment": "unknown", "safe_next_action": "continue safely"},
            "blockers": [],
            "action": action,
            "message": "Please report blockers." if action == "send" else None,
        }

    def test_schema_v1_accepts_exact_inventory_binding(self):
        packet = self._schema_v1_packet()
        decision = self._schema_v1_decision(packet)
        self.assertEqual(_validate_decision(json.dumps(decision), packet), decision)

    def test_schema_v1_packet_rejects_unknown_version_and_unapproved_fields(self):
        packet = self._schema_v1_packet()
        self.assertEqual(_validate_packet(packet)[1], "ok")
        for changed in (dict(packet, schema_version=2),
                        dict(packet, api_key="must not enter model packet")):
            with self.subTest(keys=set(changed)):
                self.assertEqual(_validate_packet(changed), (None, "invalid_packet"))

    def test_schema_v1_rejects_missing_or_unknown_version_and_wrong_stage(self):
        packet = self._schema_v1_packet()
        valid = self._schema_v1_decision(packet)
        for field, value in (("schema_version", None), ("schema_version", 2),
                             ("stage", "challenge")):
            decision = dict(valid)
            if value is None:
                decision.pop(field)
            else:
                decision[field] = value
            with self.subTest(field=field, value=value):
                self.assertIsNone(_validate_decision(json.dumps(decision), packet))

    def test_schema_v1_rejects_binding_and_action_mismatches(self):
        packet = self._schema_v1_packet()
        valid = self._schema_v1_decision(packet)
        for field, value in (("source_binding", {**valid["source_binding"], "record_version": "18"}),
                             ("grant_binding", {**valid["grant_binding"], "grant_version": 3}),
                             ("correlation", {"parent_event_id": "wrong"}),
                             ("action", "no_action"), ("message", None),
                             ("outcome", "cycle_complete")):
            decision = dict(valid)
            decision[field] = value
            with self.subTest(field=field):
                self.assertIsNone(_validate_decision(json.dumps(decision), packet))

    def test_schema_v1_no_eligible_task_is_typed_for_empty_or_nonempty_candidates(self):
        for candidates in ([], self._schema_v1_packet()["candidate_bindings"]):
            packet = self._schema_v1_packet(candidates=candidates)
            decision = self._schema_v1_decision(packet, "no_eligible_task", "no_action")
            self.assertIsNotNone(_validate_decision(json.dumps(decision), packet))

    def test_schema_v1_requires_exactly_one_matching_inventory_candidate(self):
        packet = self._schema_v1_packet(candidates=[])
        valid_packet = self._schema_v1_packet()
        decision = self._schema_v1_decision(valid_packet)
        self.assertIsNone(_validate_decision(json.dumps(decision), packet))
        packet = self._schema_v1_packet(candidates=[
            self._schema_v1_packet()["candidate_bindings"][0],
            self._schema_v1_packet()["candidate_bindings"][0],
        ])
        decision = self._schema_v1_decision(valid_packet)
        self.assertIsNone(_validate_decision(json.dumps(decision), packet))

    def test_schema_v1_challenge_and_final_judgment_are_distinct(self):
        challenge = self._schema_v1_packet(stage="challenge")
        self.assertIsNotNone(_validate_decision(
            json.dumps(self._schema_v1_decision(challenge)), challenge))
        final = self._schema_v1_packet(stage="final_judgment")
        decision = self._schema_v1_decision(final, "cycle_complete", "no_action")
        self.assertIsNotNone(_validate_decision(json.dumps(decision), final))
        self.assertIsNone(_validate_decision(
            json.dumps(self._schema_v1_decision(final)), final))

    def test_guidance_contains_exact_compact_work_prompt(self):
        guidance = (
            SCRIPTS_DIR.parent / "references" / "dot-self-unblock.md"
        ).read_text(encoding="utf-8")
        compact_prompt = (
            "What is blocking your current work? Unblock yourself where you can. "
            "What tasks should you work on next? Continue with those tasks within "
            "your existing authority, and report what you did and any blockers "
            "that remain."
        )
        secret_rule = (
            "Do not publish API keys, credentials, tokens, or other secrets to github.com."
        )
        self.assertEqual(guidance, f"{compact_prompt}\n\n{secret_rule}\n")

    def test_agy_default_uses_real_stream_protocol_and_full_permission_mode(self):
        response = self.response_text
        guidance = (
            SCRIPTS_DIR.parent / "references" / "dot-self-unblock.md"
        ).read_text(encoding="utf-8")
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
assert {guidance!r} in message["message"]["content"]
assert "Do not call dot transport or send messages" in message["message"]["content"]
assert "do not edit repositories, access credentials" in message["message"]["content"]
assert "perform any proposed action" in message["message"]["content"]
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

    def test_claude_verbose_json_array_uses_terminal_result(self):
        response = self.response_text
        self._fake_driver("claude", f'''import json
print(json.dumps([
  {{"type":"system","subtype":"init"}},
  {{"type":"assistant","message":{{"role":"assistant","content":[{{"type":"text","text":"working"}}]}}}},
  {{"type":"rate_limit_event"}},
  {{"type":"result","subtype":"success","is_error":False,"result":{response!r}}}
]))
''')
        with mock.patch.dict(os.environ, self._path_env()):
            result = DriverAdapter("claude").decide(self.packet, self.workspace)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["decision"]["event_id"], "event-456")

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

    def test_receipts_redact_secrets_communications_and_oversized_prompt_echo(self):
        # Synthetic fixtures only; unknown/private prose must be redacted too.
        self._fake_driver("agy", "import sys\nprompt = sys.stdin.read()\nsys.stdout.write(prompt + 'Bearer synthetic-token ' + 'x' * 1000000)\nsys.stderr.write('password=synthetic-secret private personal communication')\nsys.exit(23)\n")
        with mock.patch.dict(os.environ, self._path_env()):
            first = DriverAdapter().decide(self.packet, self.workspace)
            second = DriverAdapter().decide(self.packet, self.workspace)
        self.assertEqual(first, {"status": "driver_failed", "reason": "nonzero_exit"})
        self.assertEqual(second, first)
        receipts = list(self.workspace.glob(".driver-diagnostic-*.json"))
        self.assertEqual(len(receipts), 2)
        for path in receipts:
            raw = path.read_text()
            receipt = json.loads(raw)
            self.assertGreater(receipt["stdout"]["bytes"], 1000000)
            self.assertEqual(receipt["stdout"]["text"], "[REDACTED]")
            self.assertEqual(receipt["stderr"]["text"], "[REDACTED]")
            self.assertLessEqual(path.stat().st_size, 2048)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            for private in ("synthetic-token", "synthetic-secret", "personal communication",
                            self.packet["previous_dot_reply"], "Packet JSON", "event-456"):
                self.assertNotIn(private, raw)
        self.assertEqual(set(self.workspace.iterdir()), set(receipts))

    def test_receipt_write_failure_preserves_driver_failure(self):
        self._fake_driver("agy", "raise SystemExit(23)\n")
        with mock.patch.dict(os.environ, self._path_env()), mock.patch(
                "modules.driver_adapter.tempfile.mkstemp", side_effect=OSError("private path")):
            result = DriverAdapter().decide(self.packet, self.workspace)
        self.assertEqual(result, {"status": "driver_failed", "reason": "nonzero_exit"})
        self.assertEqual(list(self.workspace.iterdir()), [])

    def test_execution_error_retains_stage_without_exception_text(self):
        self._fake_driver("agy", "raise SystemExit(0)\n")
        with mock.patch.dict(os.environ, self._path_env()), mock.patch(
                "modules.driver_adapter.run_bounded_command",
                side_effect=OSError("synthetic secret and private path")):
            result = DriverAdapter().decide(self.packet, self.workspace)
        self.assertEqual(result, {"status": "driver_failed", "reason": "execution_failed"})
        receipts = list(self.workspace.glob(".driver-diagnostic-*.json"))
        self.assertEqual(len(receipts), 1)
        receipt = json.loads(receipts[0].read_text())
        self.assertEqual(receipt["failure_stage"], "execution")
        self.assertIsNone(receipt["exit_code"])
        self.assertNotIn("synthetic secret", receipts[0].read_text())

    def test_timeout_retains_receipt_without_inventing_exit_or_output(self):
        self._fake_driver("agy", "import sys, time\nsys.stdin.read()\nprint('private partial text', flush=True)\ntime.sleep(30)\n")
        with mock.patch.dict(os.environ, self._path_env()):
            result = DriverAdapter().decide(self.packet, self.workspace, timeout_secs=1)
        self.assertEqual(result, {"status": "driver_failed", "reason": "timeout"})
        receipts = list(self.workspace.glob(".driver-diagnostic-*.json"))
        self.assertEqual(len(receipts), 1)
        receipt = json.loads(receipts[0].read_text())
        self.assertEqual(receipt["failure_stage"], "timeout")
        self.assertIsNone(receipt["exit_code"])
        self.assertEqual(receipt["stdout"], {"bytes": None, "text": None})
        self.assertEqual(receipt["stderr"], {"bytes": None, "text": None})
        self.assertNotIn("private partial text", receipts[0].read_text())

    def test_failed_attempt_distinguishes_envelope_and_decision(self):
        for output, stage in [
            ("not json", "envelope_parse"),
            (json.dumps({"event": "result", "result": {
                "status": "SUCCESS", "response": "{}"}}), "decision_validation"),
        ]:
            with self.subTest(stage=stage):
                self._fake_driver("agy", f"print({output!r})\n")
                before = set(self.workspace.glob(".driver-diagnostic-*.json"))
                with mock.patch.dict(os.environ, self._path_env()):
                    result = DriverAdapter().decide(self.packet, self.workspace)
                self.assertEqual(result, {"status": "driver_failed", "reason": "invalid_output"})
                created = set(self.workspace.glob(".driver-diagnostic-*.json")) - before
                self.assertEqual(len(created), 1)
                receipt = json.loads(created.pop().read_text())
                self.assertEqual(receipt["failure_stage"], stage)
                self.assertEqual(receipt["exit_code"], 0)
                self.assertEqual(receipt["stderr"], {"bytes": 0, "text": ""})

    def test_failed_attempt_retains_private_exit_receipt(self):
        self._fake_driver("agy", "import sys\nsys.stdin.read()\nprint('known stdout')\nprint('known stderr', file=sys.stderr)\nsys.exit(23)\n")
        with mock.patch.dict(os.environ, self._path_env()):
            result = DriverAdapter().decide(self.packet, self.workspace)
        self.assertEqual(result, {"status": "driver_failed", "reason": "nonzero_exit"})
        receipts = list(self.workspace.glob(".driver-diagnostic-*.json"))
        self.assertEqual(len(receipts), 1)
        receipt = json.loads(receipts[0].read_text())
        self.assertEqual(receipt["exit_code"], 23)
        self.assertEqual(receipt["failure_stage"], "process_exit")
        self.assertEqual(receipt["stdout"], {"bytes": 13, "text": "[REDACTED]"})
        self.assertEqual(receipt["stderr"], {"bytes": 13, "text": "[REDACTED]"})
        self.assertEqual(stat.S_IMODE(receipts[0].stat().st_mode), 0o600)
        self.assertLessEqual(receipts[0].stat().st_size, 2048)

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

    def test_unknown_driver_is_configuration_error_without_fallback(self):
        with mock.patch("modules.driver_adapter.shutil.which") as which:
            result = DriverAdapter("unconfigured").decide(self.packet, self.workspace)
        self.assertEqual(
            result, {"status": "configuration_error", "reason": "unsupported_driver"}
        )
        which.assert_not_called()

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
        packet = self._schema_v1_packet(stage="challenge")
        decision = self._schema_v1_decision(packet)
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
