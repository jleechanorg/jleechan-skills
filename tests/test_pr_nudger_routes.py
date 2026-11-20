"""Exercise route selection and submit boundaries with disposable sessions."""
import fcntl
import json
import sys
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


def test_late_cmux_appearance_blocks_resume(tmp_path):
    owner, _ = binding(tmp_path)
    owner["headless_resume"] = True
    with patch.object(router.shutil, "which", return_value="/bin/true"), \
         patch.object(router, "_surfaces", side_effect=[[], [SURFACE]]), \
         patch.object(router, "_writers", return_value=[]), \
         patch.object(router, "discover_owners", return_value={}), \
         patch.object(router, "_run", return_value=SimpleNamespace(
             returncode=0, stdout="codex-cli 0.160.0")), \
         patch.object(router.subprocess, "Popen") as popen:
        assert router.route(owner, PROMPT, True) == "no_delivery"
        popen.assert_not_called()


def test_headless_requires_cmux_absence_or_explicit_headless_host(tmp_path):
    owner, _ = binding(tmp_path)
    with patch.object(router.shutil, "which", return_value=None):
        assert router.route(owner, PROMPT, True) == "blocked_cmux_unavailable"


def test_exact_owner_detected_and_unrelated_draft_never_submitted(tmp_path):
    owner, transcript = binding(tmp_path)
    idle = "previous turn\n›\nfixture-gpt-6 · 92% left\n"
    snapshot = (idle, 0.0, (transcript.stat().st_ino, transcript.stat().st_size, 100))
    send = Mock(side_effect=["", "› Human draft\nfixture-gpt-6 · 92% left"])
    with patch.object(router.shutil, "which", return_value="/bin/true"), \
         patch.object(router, "_surfaces", return_value=[SURFACE]), \
         patch.object(router, "_writers", return_value=[WRITER]), \
         patch.object(router, "_matches_owner", return_value=True), \
         patch.object(router, "_snapshot", return_value=snapshot), \
         patch.object(router.time, "sleep"), patch.object(router, "_checked", send):
        assert router.route(owner, PROMPT, True) == "attempted_delivery"
        assert [call.args[1] for call in send.call_args_list] == ["send", "capture-pane"]


def test_new_transcript_user_turn_proves_delivery(tmp_path):
    _, transcript = binding(tmp_path)
    stat = transcript.stat()
    assert not router._accepted(transcript, (stat.st_ino, stat.st_size), "codex", PROMPT)
    with transcript.open("a") as stream:
        stream.write(json.dumps({"type": "response_item", "payload": {
            "role": "user", "content": [{"text": PROMPT}]}}) + "\n")
    assert router._accepted(transcript, (stat.st_ino, stat.st_size), "codex", PROMPT)



def test_headless_submits_exact_resume_and_finds_receipt(tmp_path):
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



def test_native_active_lock_blocks_even_without_a_visible_writer(tmp_path):
    owner, _ = binding(tmp_path)
    owner.update(headless_only=True, cli_bin="/bin/true")
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



def test_claude_stop_sequence_requires_a_completed_text_reply(tmp_path):
    transcript = tmp_path / "claude.jsonl"
    for reason, part, idle in [
        ("stop_sequence", {"type": "text", "text": "Finished."}, True),
        ("stop_sequence", {"type": "thinking"}, False),
        ("tool_use", {"type": "text", "text": "Working."}, False),
    ]:
        message = {"stop_reason": reason, "content": [part]}
        transcript.write_text(json.dumps({"type": "assistant", "message": message}) + "\n")
        assert router._terminal_state("claude", transcript)[0] is idle
