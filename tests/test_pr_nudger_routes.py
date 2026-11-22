"""Exercise route selection and submit boundaries with disposable sessions."""
import fcntl
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from scripts import pr_nudger_routes as router


SESSION = "00000000-0000-4000-8000-000000000001"
SURFACE = ("workspace:1", "surface:2", "workspace-id", "surface-id", "tty123")
WRITER = ("123", "tty123", "S+", "codex", True)
PROMPT = "Synthetic PR reminder"


def binding(cwd):
    file = cwd / f"sessions/2026/01/01/rollout-{SESSION}.jsonl"
    file.parent.mkdir(parents=True)
    rows = [{"type": "session_meta", "payload": {"id": SESSION, "cwd": str(cwd)}},
            {"type": "turn_context", "payload": {"model": "fixture-model"}},
            {"type": "event_msg", "payload": {"type": "task_complete"}}]
    file.write_text("".join(json.dumps(row) + "\n" for row in rows))
    lock = cwd / f"thread-writer-locks/{SESSION}.lock"
    lock.parent.mkdir()
    return dict(cwd=str(cwd), profile_dir=str(cwd), cli="codex", session=SESSION), file


BOOTSTRAP_IDENTITY = ("owned/repo", 12, "owned/head", "feature-branch", "a" * 40)
BOOTSTRAP_ACK = "PR_NUDGER_BOOTSTRAP_ACK"


def bootstrap_enrollment(cwd):
    return {
        "cwd": str(cwd), "cli": "codex", "cli_bin": sys.executable,
        "profile_dir": str(cwd), "model": "fixture-model", "headless_only": True,
        "host": socket.gethostname(), "managed_exclusive": True,
        "launch_authorized": True, "head_repo": "owned/head", "branch": "feature-branch",
    }


def bootstrap_cli_probe(*args, **kwargs):
    output = "[]" if args[-3:] == ("mcp", "list", "--json") else "codex-cli 0.160.0"
    return SimpleNamespace(returncode=0, stdout=output)


class RouteTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.tmp_path = Path(directory.name).resolve()

    def test_late_cmux_appearance_blocks_resume(self):
        tmp_path = self.tmp_path
        owner, _ = binding(tmp_path)
        owner["headless_resume"] = True
        with patch.object(router.shutil, "which", return_value=sys.executable), \
             patch.object(router, "_surfaces", side_effect=[[], [SURFACE]]), \
             patch.object(router, "_writers", return_value=[]), \
             patch.object(router, "discover_owners", return_value={}), \
             patch.object(router, "_run", return_value=SimpleNamespace(
                 returncode=0, stdout="codex-cli 0.160.0")), \
             patch.object(router.subprocess, "Popen") as popen:
            assert router.route(owner, PROMPT, True) == "no_delivery"
            popen.assert_not_called()

    def test_headless_requires_cmux_absence_or_explicit_headless_host(self):
        tmp_path = self.tmp_path
        owner, _ = binding(tmp_path)
        with patch.object(router.shutil, "which", return_value=None):
            assert router.route(owner, PROMPT, True) == "blocked_cmux_unavailable"


    def test_unreachable_cmux_can_resume_only_on_enrolled_headless_host(self):
        owner, transcript = binding(self.tmp_path)
        owner.update(headless_only=True, host=socket.gethostname())
        with patch.object(router.shutil, "which", return_value=sys.executable), \
             patch.object(router, "_surfaces", side_effect=ValueError("cmux unavailable")), \
             patch.object(router, "_writers", return_value=[]), \
             patch.object(router, "_resume", return_value="would_deliver") as resume, \
             patch.object(router.sys, "platform", "linux"), patch.dict(router.os.environ, {}, clear=True):
            assert router.route(owner, PROMPT, False) == "would_deliver"
            assert resume.call_args.args[:4] == (sys.executable, [], self.tmp_path, transcript)
            resume.reset_mock()
            with patch.dict(router.os.environ, {"DISPLAY": ":0"}):
                assert router.route(owner, PROMPT, False) == "blocked_route_unverified"
            with patch.object(router.sys, "platform", "darwin"):
                assert router.route(owner, PROMPT, False) == "blocked_route_unverified"
            owner["host"] = "another-host"
            assert router.route(owner, PROMPT, False) == "blocked_route_unverified"
            resume.assert_not_called()

    def test_exact_owner_detected_and_unrelated_draft_never_submitted(self):
        tmp_path = self.tmp_path
        owner, transcript = binding(tmp_path)
        idle = "previous turn\n› Ask Codex to do anything\nfixture-gpt-6 · 92% left\n"
        snapshot = (idle, 0.0, (transcript.stat().st_ino, transcript.stat().st_size, 100))
        send = Mock(side_effect=["", "› Human draft\nfixture-gpt-6 · 92% left"])
        with patch.object(router.shutil, "which", return_value=sys.executable), \
             patch.object(router, "_surfaces", return_value=[SURFACE]), \
             patch.object(router, "_writers", return_value=[WRITER]), \
             patch.object(router, "_matches_owner", return_value=True), \
             patch.object(router, "_snapshot", return_value=snapshot), \
             patch.object(router, "_input_is", return_value=True), \
             patch.object(router.time, "sleep"), patch.object(router, "_checked", send):
            assert router.route(owner, PROMPT, True) == "attempted_delivery"
            assert [call.args[1] for call in send.call_args_list] == ["send", "capture-pane"]

    def test_new_transcript_user_turn_proves_delivery(self):
        tmp_path = self.tmp_path
        _, transcript = binding(tmp_path)
        stat = transcript.stat()
        assert not router._accepted(transcript, (stat.st_ino, stat.st_size), "codex", PROMPT)
        with transcript.open("a") as stream:
            stream.write(json.dumps({"type": "response_item", "payload": {
                "role": "user", "content": [{"text": PROMPT}]}}) + "\n")
        assert router._accepted(transcript, (stat.st_ino, stat.st_size), "codex", PROMPT)

    def test_headless_submits_exact_resume_and_finds_receipt(self):
        tmp_path = self.tmp_path
        owner, transcript = binding(tmp_path)
        fake = tmp_path / "fixture-codex"
        fake.write_text(rf"""#!{sys.executable}
import json
import os
import sys
if sys.argv[1:]==["--version"]:
    print("codex-cli 0.160.0")
elif sys.argv[1:]==["login", "status"]:
    pass
else:
    assert sys.argv[1:] == ["exec", "resume", "--model", "fixture-model", "{SESSION}", "-"]
    assert os.getcwd() == os.environ["CODEX_HOME"] == {str(tmp_path)!r}
    with open({str(transcript)!r}, "a") as stream:
        stream.write(json.dumps({{"type": "response_item", "payload": {{
            "role": "user", "content": sys.stdin.read()}}}}) + "\n")
""")
        fake.chmod(0o700)
        owner.update(headless_only=True, cli_bin=str(fake))
        with patch.object(router.shutil, "which", return_value=None):
            assert router.route(owner, PROMPT, True) == "delivered"

    def test_native_active_lock_blocks_even_without_a_visible_writer(self):
        tmp_path = self.tmp_path
        owner, _ = binding(tmp_path)
        owner.update(headless_only=True, cli_bin=sys.executable)
        lock = tmp_path / f"thread-writer-locks/{SESSION}.lock"
        with lock.open("wb") as stream, \
             patch.object(router.shutil, "which", return_value=None), \
             patch.object(router, "_writers", return_value=[]), \
             patch.object(router, "_run", return_value=SimpleNamespace(
                 returncode=0, stdout="codex-cli 0.160.0")), \
             patch.object(router.subprocess, "Popen") as spawn:
            fcntl.flock(stream, fcntl.LOCK_EX)
            assert router.route(owner, PROMPT, True) == "busy"
            spawn.assert_not_called()

    def test_claude_stop_sequence_requires_a_completed_text_reply(self):
        tmp_path = self.tmp_path
        transcript = tmp_path / "claude.jsonl"
        for reason, part, idle in [
            ("stop_sequence", {"type": "text", "text": "Finished."}, True),
            ("stop_sequence", {"type": "thinking"}, False),
            ("tool_use", {"type": "text", "text": "Working."}, False),
        ]:
            message = {"stop_reason": reason, "content": [part]}
            transcript.write_text(json.dumps({"type": "assistant", "message": message}) + "\n")
            assert router._terminal_state("claude", transcript)[0] is idle

    def test_cmux_native_input_empty_attests_exact_owner_and_rejects_draft(self):
        workspace, surface = SURFACE[2:4]
        empty = dict(workspace_id=workspace, surface_id=surface, state="empty",
                     terminal=True, agent=True, lifecycle="running",
                     waiting_on_human=False, blocks_typing=False)
        with patch.object(router, "_checked", return_value=json.dumps(empty)) as rpc:
            assert router._input_is("cmux", workspace, surface, "empty")
            cmux, command, method, target = rpc.call_args.args
            assert (cmux, command, method) == ("cmux", "rpc", "surface.input_state")
            assert json.loads(target) == {"workspace_id": workspace, "surface_id": surface}
        for row in (dict(empty, state="draft"), dict(empty, state="dialog"),
                    dict(empty, surface_id="changed"), dict(empty, blocks_typing=True)):
            with patch.object(router, "_checked", return_value=json.dumps(row)):
                assert not router._input_is("cmux", workspace, surface, "empty")

    def test_dot_reply_binding_requires_resolved_conversation_and_parent(self):
        owner = dict(cli="dot", session=SESSION, account="fixture", identity_sha256="1" * 64)
        feed = f"https://chatgpt.com/dots/{SESSION}"
        owner["destination"] = f"{feed}~" + "a" * 32
        assert router.route(owner, PROMPT, apply=False) == "blocked_dot_binding"
        owner["parent_message_id"] = "~".join(("b" * 32, "b" * 32, "CalpicoMessage", "Sentinel_" + "c" * 32))
        assert router.route(owner, PROMPT, apply=False) == "would_deliver"
        owner["destination"] = feed
        assert router.route(owner, PROMPT, apply=False) == "blocked_dot_binding"

    def test_dot_requires_nonce_bound_zero_exit_to_prove_no_delivery(self):
        owner = dict(cli="dot", session=SESSION, account="fixture", identity_sha256="1" * 64,
                     destination=f"https://chatgpt.com/c/{SESSION}")
        nonce = b"a" * 32
        for receipt, returncode, status in [
            (b"aborted " + nonce, 0, "no_delivery"),
            (b"aborted " + b"b" * 32, 0, "attempted_delivery"),
            (b"aborted " + nonce, 10, "attempted_delivery"),
            (b"aborted " + nonce + b"\nDOT_SEND_UNVERIFIED", 0, "attempted_delivery"),
            (b"DOT_SEND_UNVERIFIED", 10, "attempted_delivery"),
            (b"DOT_SENT_VERIFIED", 0, "delivered"),
        ]:
            child = Mock(returncode=returncode)
            child.poll.return_value = returncode
            child.communicate.return_value = (receipt, b"")
            with patch.object(router.subprocess, "Popen", return_value=child), \
                 patch.object(router.select, "select", return_value=([child.stdout], [], [])), \
                 patch.object(router.os, "read", return_value=b"prepared-exact " + nonce + b"\n"):
                assert router.route(owner, PROMPT, apply=True) == status
            child.communicate.assert_called_once_with(b"commit " + nonce + b"\n", timeout=18)

    def test_fresh_bootstrap_reserves_before_detached_seed_spawn(self):
        tmp_path = self.tmp_path
        enrollment = dict(bootstrap_enrollment(tmp_path), resume_sandbox="danger-full-access")
        events = tmp_path / "attempt.jsonl"
        events.touch(mode=0o600)
        order = []

        def reserve():
            order.append("reserve")
            return events

        def spawn(command, **kwargs):
            order.append("spawn")
            assert command[4:7] == (sys.executable, "exec", "--json")
            assert len(kwargs["pass_fds"]) == 1
            with self.assertRaises(BlockingIOError), router._managed_claim(tmp_path / "managed.lock"):
                self.fail("bootstrap launched without the shared claim")
            assert command[-1] == "-"
            assert "read-only" in command and "features.shell_tool=false" in command
            assert "project_doc_max_bytes=65536" in command
            assert "danger-full-access" not in command
            assert kwargs["stdin"].read().decode() == (
                f"Verify owner bootstrap for owned/repo#12 at {'a' * 40}. "
            f"Do not use tools or take any action. Reply exactly {BOOTSTRAP_ACK}."
            )
            assert os.fstat(kwargs["stdout"].fileno()).st_ino == events.stat().st_ino
            assert kwargs["start_new_session"] is True

        with patch.object(router, "_managed_claim_path", return_value=tmp_path / "managed.lock"), \
             patch.object(router.shutil, "which", return_value=None), \
             patch.object(router, "_writers", return_value=[]), \
             patch.object(router, "_run", side_effect=bootstrap_cli_probe), \
             patch.object(router.subprocess, "Popen", side_effect=spawn):
            assert router.start_codex_bootstrap(
                enrollment, BOOTSTRAP_IDENTITY, apply=True, recheck=lambda: True,
                begin_attempt=reserve,
            ) == "bootstrap_started"
        assert order == ["reserve", "spawn"]

    def test_fresh_bootstrap_blocks_stale_and_competing_owners(self):
        tmp_path = self.tmp_path
        enrollment = bootstrap_enrollment(tmp_path)
        reserve = Mock()
        with patch.object(router, "_managed_claim_path", return_value=tmp_path / "managed.lock"), \
             patch.object(router.shutil, "which", return_value=None), \
             patch.object(router, "_writers", side_effect=[[], [WRITER]]), \
             patch.object(router, "_run", side_effect=bootstrap_cli_probe), \
             patch.object(router.subprocess, "Popen") as spawn:
            assert router.start_codex_bootstrap(
                enrollment, BOOTSTRAP_IDENTITY, apply=True, recheck=lambda: False,
                begin_attempt=reserve,
            ) == "stale_pr"
            assert router.start_codex_bootstrap(
                enrollment, BOOTSTRAP_IDENTITY, apply=True, recheck=lambda: True,
                begin_attempt=reserve,
            ) == "busy"
            reserve.assert_not_called()
            spawn.assert_not_called()

    def test_fresh_bootstrap_does_not_launch_with_unverified_tool_inventory(self):
        tmp_path = self.tmp_path
        enrollment = bootstrap_enrollment(tmp_path)
        reserve = Mock()

        def cli_probe(*args, **kwargs):
            output = '[{"name":"connector","enabled":true}]' if "list" in args else "codex-cli 0.160.0"
            return SimpleNamespace(returncode=0, stdout=output)

        with patch.object(router, "_managed_claim_path", return_value=tmp_path / "managed.lock"), \
             patch.object(router.shutil, "which", return_value=None), \
             patch.object(router, "_writers", return_value=[]), \
             patch.object(router, "_run", side_effect=cli_probe), \
             patch.object(router.subprocess, "Popen") as spawn:
            assert router.start_codex_bootstrap(
                enrollment, BOOTSTRAP_IDENTITY, apply=True, recheck=lambda: True,
                begin_attempt=reserve,
            ) == "blocked_bootstrap_tools"
            reserve.assert_not_called()
            spawn.assert_not_called()

    def test_bootstrap_inspection_requires_exact_ack_and_persisted_transcript(self):
        tmp_path = self.tmp_path
        enrollment = bootstrap_enrollment(tmp_path)
        _, transcript = binding(tmp_path)
        prompt = (
            f"Verify owner bootstrap for owned/repo#12 at {'a' * 40}. "
        f"Do not use tools or take any action. Reply exactly {BOOTSTRAP_ACK}."
        )
        rows = [
            {"type": "session_meta", "payload": {
                "id": SESSION, "cwd": str(tmp_path),
                "git": {"branch": "feature-branch", "commit_hash": "a" * 40},
            }},
            {"type": "response_item", "payload": {"role": "user", "content": prompt}},
            {"type": "event_msg", "payload": {"type": "task_complete"}},
        ]
        transcript.write_text("".join(json.dumps(row) + "\n" for row in rows))
        events = tmp_path / "attempt.jsonl"
        events.touch(mode=0o600)
        attempt = {"id": "attempt", "events_path": str(events), "sha": "a" * 40, "started_at": 60}
        frames = [
            {"type": "thread.started", "thread_id": SESSION},
            {"type": "item.completed", "item": {"type": "agent_message", "text": BOOTSTRAP_ACK}},
            {"type": "turn.completed"},
        ]
        instructions = tmp_path / "AGENTS.md"
        instructions.write_bytes(b"x" * 34413)
        diagnostic = {
            "type": "item.completed",
            "item": {
                "type": "error",
                "message": (
                    f"Loaded only 32768 of 34413 bytes from `{instructions}` in environment "
                    "`local` under the 32768-byte project instruction budget. Trim your "
                    "project instructions to fit the budget. If you need to keep them all, "
                    "increase `project_doc_max_bytes`."
                ),
            },
        }
        started = {"type": "turn.started"}
        bound = []

        def bind_owner(session):
            with self.assertRaises(BlockingIOError), router._managed_claim(tmp_path / "managed.lock"):
                self.fail("durable bind ran without the shared claim")
            bound.append(session)

        with patch.object(router, "_managed_claim_path", return_value=tmp_path / "managed.lock"), \
             patch.object(router.shutil, "which", return_value=None), \
             patch.object(router, "_writers", return_value=[]), \
             patch.object(router.time, "time", return_value=61):
            events.write_text("".join(json.dumps(row) + "\n" for row in frames))
            assert router.inspect_codex_bootstrap(enrollment, BOOTSTRAP_IDENTITY, attempt, bind=bind_owner) == (
                "bootstrapped", SESSION,
            )
            recovered = [frames[0], diagnostic, started, *frames[1:]]
            events.write_text("".join(json.dumps(row) + "\n" for row in recovered))
            assert router.inspect_codex_bootstrap(
                enrollment, BOOTSTRAP_IDENTITY, attempt, bind=bind_owner,
            ) == ("bootstrapped", SESSION)
            # Codex reports a truncated skills list as an error item; the ACK still decides.
            skills_notice = {"type": "item.completed", "item": {"type": "error", "message": (
                "Exceeded skills context budget. All skill descriptions were removed and 125 "
                "additional skills were not included in the model-visible skills list.")}}
            events.write_text("".join(json.dumps(row) + "\n" for row in
                                      [frames[0], started, skills_notice, *frames[1:]]))
            assert router.inspect_codex_bootstrap(
                enrollment, BOOTSTRAP_IDENTITY, attempt, bind=bind_owner,
            ) == ("bootstrapped", SESSION)
            events.write_text("".join(json.dumps(row) + "\n" for row in
                                      [frames[0], started, skills_notice, skills_notice, *frames[1:]]))
            assert router.inspect_codex_bootstrap(
                enrollment, BOOTSTRAP_IDENTITY, attempt, bind=bind_owner,
            ) == ("bootstrap_reconciliation_required", None)
            assert router.inspect_codex_bootstrap(
                enrollment, BOOTSTRAP_IDENTITY, dict(attempt, sha="b" * 40), bind=bind_owner,
            ) == ("bootstrap_reconciliation_required", None)
            events.write_text("")
            assert router.inspect_codex_bootstrap(
                enrollment, BOOTSTRAP_IDENTITY, attempt, bind=bind_owner
            ) == ("bootstrap_pending", None)
            with patch.object(router.time, "time", return_value=661):
                assert router.inspect_codex_bootstrap(
                    enrollment, BOOTSTRAP_IDENTITY, attempt, bind=bind_owner,
                ) == ("bootstrap_reconciliation_required", None)
            for bad_frames in (
                frames[:1] + frames[-1:],
                frames + [frames[0]],
                [frames[0], started, diagnostic, *frames[1:]],
                [frames[0], diagnostic, diagnostic, started, *frames[1:]],
                [frames[0], diagnostic, *frames[1:]],
                [frames[0], dict(diagnostic, item={"type": "error", "message": "unknown error"}), started, *frames[1:]],
                [
                    frames[0],
                    dict(diagnostic, item=dict(diagnostic["item"], message=diagnostic["item"]["message"].replace("34413", "99999"))),
                    started, *frames[1:],
                ],
                frames[:1] + [{"type": "item.started", "item": {"type": "command_execution"}}] + frames[1:],
            ):
                events.write_text("".join(json.dumps(row) + "\n" for row in bad_frames))
                assert router.inspect_codex_bootstrap(enrollment, BOOTSTRAP_IDENTITY, attempt, bind=bind_owner) == (
                    "bootstrap_reconciliation_required", None,
                )
        assert bound == [SESSION, SESSION, SESSION]

    def test_existing_headless_resume_honors_process_admission(self):
        tmp_path = self.tmp_path
        owner, _ = binding(tmp_path)
        reserve = Mock()
        owner.update(headless_only=True, cli_bin=sys.executable, admit_launch=lambda: False, recheck=reserve)
        with patch.object(router.shutil, "which", return_value=None), \
             patch.object(router, "_writers", return_value=[]), \
             patch.object(router, "_run", return_value=SimpleNamespace(
                 returncode=0, stdout="codex-cli 0.160.0")), \
             patch.object(router.subprocess, "Popen") as spawn:
            assert router.route(owner, PROMPT, True) == "blocked_launch_capacity"
            reserve.assert_not_called()
            spawn.assert_not_called()

    def test_managed_resume_keeps_full_project_instruction_budget(self):
        owner, _ = binding(self.tmp_path)
        owner.update(bootstrap_enrollment(self.tmp_path), recheck=lambda _: True)
        with patch.object(router, "_managed_claim_path", return_value=self.tmp_path / "managed.lock"), \
             patch.object(router.shutil, "which", return_value=None), \
             patch.object(router, "_writers", return_value=[]), \
             patch.object(router, "_run", side_effect=bootstrap_cli_probe), \
             patch.object(router, "_spawn_claimed") as spawn, \
             patch.object(router, "_wait_for_receipt", return_value="delivered"):
            assert router.route(owner, PROMPT, True) == "delivered"
            assert spawn.call_args.args[0] == (
                sys.executable, "exec", "resume", "-c", "project_doc_max_bytes=65536",
                "--model", "fixture-model", SESSION, "-",
            )

            owner["resume_sandbox"] = "danger-full-access"
            assert router.route(owner, PROMPT, True) == "delivered"
            assert spawn.call_args.args[0] == (
                sys.executable, "exec", "--sandbox", "danger-full-access", "resume",
                "-c", "project_doc_max_bytes=65536", "--model", "fixture-model", SESSION, "-",
            )
            spawn.reset_mock()
            assert router.route(dict(owner, launch_authorized=False), PROMPT, True) == "blocked_resume_sandbox"
            assert router.route(dict(owner, resume_sandbox="unknown"), PROMPT, True) == "blocked_resume_sandbox"
            spawn.assert_not_called()

    def test_managed_claim_blocks_competing_resume(self):
        tmp_path = self.tmp_path
        owner, _ = binding(tmp_path)
        subprocess.run(("git", "init", "-q", str(tmp_path)), check=True)
        owner.update(bootstrap_enrollment(tmp_path))
        reserve = Mock(return_value=True)
        owner["recheck"] = reserve
        claim_path = tmp_path / ".git/pr-owner-nudger.writer.lock"
        with claim_path.open("wb") as independent_writer:
            claim_path.chmod(0o600)
            fcntl.flock(independent_writer, fcntl.LOCK_EX)
            with patch.object(router, "_managed_claim_path", return_value=claim_path), \
                 patch.object(router.shutil, "which", return_value=None), \
                 patch.object(router, "_writers", return_value=[]), \
                 patch.object(router, "_run", side_effect=bootstrap_cli_probe), \
                 patch.object(router.subprocess, "Popen") as spawn:
                assert router.route(owner, PROMPT, True) == "busy"
                assert router.start_codex_bootstrap(
                    owner, BOOTSTRAP_IDENTITY, apply=True, recheck=lambda: True,
                    begin_attempt=reserve,
                ) == "busy"
                reserve.assert_not_called()
                spawn.assert_not_called()

    def test_managed_claim_lives_past_scheduler_exit(self):
        tmp_path = self.tmp_path
        subprocess.run(("git", "init", "-q", str(tmp_path)), check=True)
        release = tmp_path / "release"
        writer = """
import os
import sys
import time
from pathlib import Path
marker = Path(sys.argv[1])
os.close(int(sys.argv[2]))
stop = time.monotonic() + 10
while not marker.exists() and time.monotonic() < stop:
    time.sleep(0.01)
"""
        scheduler = """
import subprocess
import sys
from pathlib import Path
from scripts import pr_nudger_routes as r
cwd, release, writer = sys.argv[1:]
cwd = Path(cwd)
with r._managed_claim(r._managed_claim_path(cwd)) as claim:
    r._spawn_claimed(
        (sys.executable, "-c", writer, release, str(claim)), claim, cwd=cwd,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
    )
"""
        try:
            subprocess.run(
                (sys.executable, "-c", scheduler, str(tmp_path), str(release), writer),
                check=True, timeout=10,
            )
            claim_path = tmp_path / ".git/pr-owner-nudger.writer.lock"
            with claim_path.open("rb") as independent_reader, self.assertRaises(BlockingIOError):
                fcntl.flock(independent_reader, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            release.touch()
        deadline = time.monotonic() + 5
        while True:
            with claim_path.open("rb") as reader:
                try:
                    fcntl.flock(reader, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        self.fail("managed claim remained held after the child exited")
            time.sleep(0.01)

    def test_managed_cmux_steers_only_the_bound_claim_holder(self):
        tmp_path = self.tmp_path
        owner, transcript = binding(tmp_path)
        owner.update(bootstrap_enrollment(tmp_path))
        claim_path = tmp_path / "managed.lock"
        screen = ("idle", 0.0, (transcript.stat().st_ino, transcript.stat().st_size, 0))
        with router._managed_claim(claim_path), \
             patch.object(router, "_managed_claim_path", return_value=claim_path), \
             patch.object(router.shutil, "which", return_value=sys.executable), \
             patch.object(router, "_surfaces", return_value=[SURFACE]), \
             patch.object(router, "_writers", return_value=[WRITER]), \
             patch.object(router, "_matches_owner", return_value=True), \
             patch.object(router, "_snapshot", return_value=screen), \
             patch.object(router, "_input_is", return_value=True), \
             patch.object(router.time, "sleep"), \
             patch.object(router, "_checked", return_value="p456\nlW\n") as holders:
            assert router.route(owner, PROMPT, False) == "blocked_managed_writer_unverified"
            holders.return_value = f"p{WRITER[0]}\nl \n"
            assert router.route(owner, PROMPT, False) == "blocked_managed_writer_unverified"
            holders.return_value = f"p{WRITER[0]}\nlW\n"
            assert router.route(owner, PROMPT, False) == "would_deliver"
