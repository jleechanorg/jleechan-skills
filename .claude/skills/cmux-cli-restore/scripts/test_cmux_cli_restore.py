#!/usr/bin/env python3
"""Regression tests for cmux-cli-restore.sh.

The dot-coordination reviewer found a fail-open: a failed `cmux capture-pane`
meant "no human gate", so the script would still send ctrl+c into a surface it
could not read. These tests pin the closed behaviour: if the surface cannot be
read, nothing is sent at all.
"""
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("cmux-cli-restore.sh")
WS = "workspace:1000120002"
SF = "surface:1000120005"


class StubCmux:
    """A stub `cmux` on PATH that records every invocation and replies per mode."""

    def __init__(self, mode: str):
        self.dir = Path(tempfile.mkdtemp(prefix="cmux-stub-"))
        self.marker = self.dir / "resumed"
        self.log = self.dir / "calls.log"
        self.log.write_text("")
        stub = self.dir / "cmux"
        body = (
            "#!/bin/bash\n"
            f'printf "%s\\n" "$*" >> "{self.log}"\n'
            'case "$*" in *"codex resume"*) : > "__MARK__" ;; esac\n'
            # in acceptfail mode the SECOND Enter (the goal accept) fails
            'case "$*" in *send-key*enter*)\n'
            '  if [ -f "__MARK__" ]; then\n'
            '    n=$(cat "__ECTR__" 2>/dev/null || echo 0); echo $((n+1)) > "__ECTR__"\n'
            f'    if [ "{mode}" = "acceptfail" ] && [ "$n" = "1" ]; then exit 1; fi\n'
            '    if [ "$n" -ge 1 ]; then : > "__ACCEPTED__"; fi\n'
            '  fi ;;\n'
            'esac\n'
            'case "$*" in\n'
            '  *top*)\n'
            '    printf "%s\\n" "  0.0% 0 B 0 surface ' + SF + ' [terminal] tty=ttys003"; exit 0 ;;\n'
            '  *capture-pane*)\n'
            f'    case "{mode}" in\n'
            '      fail) exit 1 ;;\n'
            '      empty) exit 0 ;;\n'
            '      gate) printf "%s\\n" "Goal remains blocked pending human merge approval"; exit 0 ;;\n'
            '      clean) printf "%s\\n" "user@host:~/work$"; exit 0 ;;\n'
            '      acceptreadfail) if [ -f "__ACCEPTED__" ]; then exit 1; fi;\n'
            '        if [ -f "__MARK__" ]; then printf "%s\\n" "  1. Resume goal   Mark it active and continue when idle"; else printf "%s\\n" "user@host:~/work$"; fi; exit 0 ;;\n'
            '      goal|goal2|acceptfail) if [ -f "__ACCEPTED__" ]; then\n'
            '          printf "%s\\n" "user@host:~/work$";\n'
            '        elif [ -f "__MARK__" ]; then\n'
            '          printf "%s\\n" "  1. Resume goal   Mark it active and continue when idle" "  2. Leave paused";\n'
            '        else\n'
            '          printf "%s\\n" "user@host:~/work$";\n'
            '        fi; exit 0 ;;\n'
            '    esac ;;\n'
            '  *) exit 0 ;;\n'
            'esac\n'
        ).replace("__MARK__", str(self.marker)).replace("__ACCEPTED__", str(self.dir / "accepted")).replace("__ECTR__", str(self.dir / "enters"))
        stub.write_text(body)
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    def calls(self) -> list[str]:
        return [line for line in self.log.read_text().splitlines() if line.strip()]

    def sent(self) -> list[str]:
        return [c for c in self.calls() if c.startswith(("send ", "send-key "))]


def run(stub: StubCmux) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PATH"] = f"{stub.dir}:{env.get('PATH', '')}"
    return subprocess.run(
        ["bash", str(SCRIPT), "--workspace", WS, "--surface", SF, "--cli", "codex"],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )


class FailClosedCaptureTest(unittest.TestCase):
    def test_unreadable_surface_aborts_without_any_keystroke(self):
        stub = StubCmux("fail")
        proc = run(stub)
        self.assertNotEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(proc.returncode, 7, "expected the capture-failure exit code")
        self.assertEqual(stub.sent(), [], f"sent despite unreadable surface: {stub.sent()}")
        self.assertIn("no keystroke sent", proc.stdout)

    def test_empty_capture_aborts_without_any_keystroke(self):
        stub = StubCmux("empty")
        proc = run(stub)
        self.assertNotEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(stub.sent(), [], f"sent on an empty capture: {stub.sent()}")

    def test_human_gate_refuses_without_any_keystroke(self):
        stub = StubCmux("gate")
        proc = run(stub)
        self.assertEqual(proc.returncode, 4, proc.stdout + proc.stderr)
        self.assertIn("human gate", proc.stdout)
        self.assertEqual(stub.sent(), [], f"sent into a human-gated lane: {stub.sent()}")

    def test_dry_run_never_sends(self):
        stub = StubCmux("clean")
        env = dict(os.environ)
        env["PATH"] = f"{stub.dir}:{env.get('PATH', '')}"
        proc = subprocess.run(
            ["bash", str(SCRIPT), "--dry-run", "--workspace", WS, "--surface", SF, "--cli", "codex"],
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
        )
        self.assertEqual(stub.sent(), [], f"dry-run sent: {stub.sent()}")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class RestartVerificationTest(unittest.TestCase):
    """dot review at 05cbaafe: verification accepted an OLD surviving process as a restart.

    A restart must be proven by a NEW pid, and a failed send must not be reported as success.
    """

    def _fake_ps(self, tmp: Path, pids_csv: str) -> Path:
        # Each call emits the next line of the CSV, so call 1 = pre-snapshot, call 2 = post.
        ps = tmp / "fakeps"
        ps.write_text(
            "#!/bin/bash\n"
            f'printf "%s\\n" "{pids_csv}"\n'
        )
        ps.chmod(0o755)
        return ps

    def _run_with(self, stub: StubCmux, fakeps: Path):
        env = dict(os.environ)
        env["PATH"] = f"{stub.dir}:{env.get('PATH', '')}"
        env["CMUX_CLI_RESTORE_PS"] = str(fakeps)
        return subprocess.run(
            ["bash", str(SCRIPT), "--workspace", WS, "--surface", SF, "--cli", "codex"],
            capture_output=True, text=True, env=env, timeout=180,
        )

    def test_old_process_surviving_is_not_a_restart(self):
        tmp = Path(tempfile.mkdtemp(prefix="fakeps-"))
        fakeps = self._fake_ps(
            tmp,
            "ttys003 100 00:10 /usr/bin/command codex resume 01a174a5-7202-7af3-831e-0bfb5ae8544a "
            "X X X X",
        )
        stub = StubCmux("clean")
        proc = self._run_with(stub, fakeps)
        self.assertEqual(proc.returncode, 6, proc.stdout + proc.stderr)
        self.assertIn("no NEW CLI process", proc.stderr)
        self.assertNotIn("RESTARTED", proc.stdout)

    def test_new_pid_after_restart_reports_success(self):
        tmp = Path(tempfile.mkdtemp(prefix="fakeps-"))
        ps = tmp / "fakeps2"
        ps.write_text(
            "#!/bin/bash\n"
            f'state="{tmp}/calls"\n'
            "n=$(cat \"$state\" 2>/dev/null || echo 0)\n"
            "echo $((n+1)) > \"$state\"\n"
            'if [ "$n" = "0" ]; then\n'
            '  echo "ttys003 100 00:10 /usr/bin/command codex resume 01a174a5-7202-7af3-831e-0bfb5ae8544a"\n'
            "else\n"
            '  echo "ttys003 200 00:01 /usr/bin/command codex resume 01a174a5-7202-7af3-831e-0bfb5ae8544a"\n'
            "fi\n"
        )
        ps.chmod(0o755)
        stub = StubCmux("clean")
        proc = self._run_with(stub, ps)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("RESTARTED", proc.stdout)

    def test_pre_snapshot_failure_aborts_before_any_send(self):
        """dot review at d2592291: an unreadable baseline made an old pid look NEW."""
        tmp = Path(tempfile.mkdtemp(prefix="fakeps-fail-"))
        ps = tmp / "fakeps_fail"
        ps.write_text("#!/bin/bash\nexit 1\n")
        ps.chmod(0o755)
        stub = StubCmux("clean")
        proc = self._run_with(stub, ps)
        self.assertEqual(proc.returncode, 9, proc.stdout + proc.stderr)
        self.assertIn("process listing failed before restart", proc.stdout)
        self.assertEqual(stub.sent(), [], f"sent without a baseline: {stub.sent()}")
        self.assertNotIn("RESTARTED", proc.stdout)

    def test_partial_baseline_output_with_nonzero_exit_aborts(self):
        """dot review at 8cf38c1c: non-empty output was accepted even when ps failed.

        A header-only listing plus a nonzero exit must not become a baseline.
        """
        tmp = Path(tempfile.mkdtemp(prefix="fakeps-partial-"))
        ps = tmp / "fakeps_partial"
        ps.write_text("#!/bin/bash\necho 'TTY PID ELAPSED COMMAND'\nexit 1\n")
        ps.chmod(0o755)
        stub = StubCmux("clean")
        proc = self._run_with(stub, ps)
        self.assertEqual(proc.returncode, 9, proc.stdout + proc.stderr)
        self.assertIn("process listing failed before restart", proc.stdout)
        self.assertEqual(stub.sent(), [], f"sent with a partial baseline: {stub.sent()}")
        self.assertNotIn("RESTARTED", proc.stdout)

    def test_partial_post_snapshot_with_nonzero_exit_never_reports_restarted(self):
        """Same rule after the restart: rc 0 is required, not just non-empty text."""
        tmp = Path(tempfile.mkdtemp(prefix="fakeps-post-"))
        ps = tmp / "fakeps_post"
        ps.write_text(
            "#!/bin/bash\n"
            f'state="{tmp}/calls"\n'
            'n=$(cat "$state" 2>/dev/null || echo 0)\n'
            'echo $((n+1)) > "$state"\n'
            'if [ "$n" = "0" ]; then\n'
            '  echo "TTY PID ELAPSED COMMAND"\n'
            '  echo "ttys003 100 00:10 /usr/bin/command codex resume 01a174a5-7202-7af3-831e-0bfb5ae8544a"\n'
            '  exit 0\n'
            "fi\n"
            'echo "ttys003 200 00:01 /usr/bin/command codex resume 01a174a5-7202-7af3-831e-0bfb5ae8544a"\n'
            "exit 1\n"
        )
        ps.chmod(0o755)
        stub = StubCmux("clean")
        proc = self._run_with(stub, ps)
        self.assertEqual(proc.returncode, 9, proc.stdout + proc.stderr)
        self.assertNotIn("RESTARTED", proc.stdout)

    def test_resume_picking_another_conversation_is_a_failure(self):
        """dot review at c15525f0: 'resume --last' can restore a DIFFERENT conversation.

        The lane is 01a174a5 before the restart; after it, the process shows another
        session id. That is a wrong-conversation restore, not a restart.
        """
        tmp = Path(tempfile.mkdtemp(prefix="fakeps-wrongconv-"))
        ps = tmp / "fakeps_wrong"
        ps.write_text(
            "#!/bin/bash\n"
            f'state="{tmp}/calls"\n'
            'n=$(cat "$state" 2>/dev/null || echo 0)\n'
            'echo $((n+1)) > "$state"\n'
            'if [ "$n" = "0" ]; then\n'
            '  echo "ttys003 100 00:10 /usr/bin/command codex resume 01a174a5-7202-7af3-831e-0bfb5ae8544a"\n'
            "else\n"
            '  echo "ttys003 200 00:01 /usr/bin/command codex resume 01a99999-dead-beef-0000-111122223333"\n'
            "fi\n"
        )
        ps.chmod(0o755)
        stub = StubCmux("clean")
        proc = self._run_with(stub, ps)
        self.assertEqual(proc.returncode, 10, proc.stdout + proc.stderr)
        self.assertIn("but the lane was", proc.stderr)
        self.assertNotIn("RESTARTED", proc.stdout)

    def test_no_workspace_wide_id_fallback(self):
        """dot review at b20c9c6b: never bind to an id taken from another surface.

        The stub's `cmux top` reports tty=ttys003 but carries no session tag, and the
        process listing for that tty shows no `resume <uuid>` (a plain node codex).
        The script must refuse (exit 11) instead of reaching for any id in the workspace.
        """
        tmp = Path(tempfile.mkdtemp(prefix="fakeps-noid-"))
        ps = tmp / "fakeps_noid"
        ps.write_text(
            "#!/bin/bash\n"
            'echo "ttys003 100 00:10 node /opt/codex/bin/codex.js"\n'
        )
        ps.chmod(0o755)
        stub = StubCmux("clean")
        proc = self._run_with(stub, ps)
        self.assertEqual(proc.returncode, 11, proc.stdout + proc.stderr)
        self.assertIn("cannot resolve this lane's conversation id", proc.stdout)
        self.assertEqual(stub.sent(), [], f"sent without an id: {stub.sent()}")

    def test_old_session_surviving_must_not_mask_a_new_wrong_session(self):
        """dot review at 56c7f904: old PID100/session A + new PID200/session B.

        Reading 'the first process on the tty' would see session A and call it a match.
        Identity must be read from the NEW pid only, so this must exit 10.
        """
        tmp = Path(tempfile.mkdtemp(prefix="fakeps-mask-"))
        ps = tmp / "fakeps_mask"
        ps.write_text(
            "#!/bin/bash\n"
            f'state="{tmp}/calls"\n'
            'n=$(cat "$state" 2>/dev/null || echo 0)\n'
            'echo $((n+1)) > "$state"\n'
            'if [ "$n" = "0" ]; then\n'
            '  echo "ttys003 100 00:10 /usr/bin/command codex resume 01a174a5-7202-7af3-831e-0bfb5ae8544a"\n'
            "else\n"
            '  echo "ttys003 100 00:20 /usr/bin/command codex resume 01a174a5-7202-7af3-831e-0bfb5ae8544a"\n'
            '  echo "ttys003 200 00:01 /usr/bin/command codex resume 01a99999-dead-beef-0000-111122223333"\n'
            "fi\n"
        )
        ps.chmod(0o755)
        stub = StubCmux("clean")
        proc = self._run_with(stub, ps)
        self.assertEqual(proc.returncode, 10, proc.stdout + proc.stderr)
        self.assertNotIn("RESTARTED", proc.stdout)


class GoalAcceptanceOrderingTest(unittest.TestCase):
    """dot review at 34b11e7c: a goal accept Enter fired BEFORE identity verification.

    Accepting a goal lets the lane start work, so a wrong or unknown session must be
    rejected with no acceptance at all. The only Enter allowed on a failure path is the
    one that submits the resume command itself.
    """

    def _run(self, pids_script: str, mode: str = "goal"):
        tmp = Path(tempfile.mkdtemp(prefix="fakeps-goal-"))
        ps = tmp / "fakeps"
        ps.write_text(pids_script.replace("__TMP__", str(tmp)))
        ps.chmod(0o755)
        stub = StubCmux(mode)
        env = dict(os.environ)
        env["PATH"] = f"{stub.dir}:{env.get('PATH', '')}"
        env["CMUX_CLI_RESTORE_PS"] = str(ps)
        proc = subprocess.run(
            ["bash", str(SCRIPT), "--workspace", WS, "--surface", SF, "--cli", "codex"],
            capture_output=True, text=True, env=env, timeout=180,
        )
        enters = [c for c in stub.calls() if "send-key" in c and c.rstrip().endswith("enter")]
        return proc, enters

    def test_wrong_session_with_visible_goal_is_never_accepted(self):
        script = (
            "#!/bin/bash\n"
            'state="__TMP__/calls"\n'
            'n=$(cat "$state" 2>/dev/null || echo 0)\n'
            'echo $((n+1)) > "$state"\n'
            'if [ "$n" = "0" ]; then\n'
            '  echo "ttys003 100 00:10 /usr/bin/command codex resume 01a174a5-7202-7af3-831e-0bfb5ae8544a"\n'
            "else\n"
            '  echo "ttys003 200 00:01 /usr/bin/command codex resume 01a99999-dead-beef-0000-111122223333"\n'
            "fi\n"
        )
        proc, enters = self._run(script, mode="goal2")
        self.assertEqual(proc.returncode, 10, proc.stdout + proc.stderr)
        self.assertEqual(len(enters), 1, f"goal was accepted before identity check: {enters}")
        self.assertNotIn("goal dialog accepted", proc.stdout)

    def test_unknown_session_with_visible_goal_is_never_accepted(self):
        script = (
            "#!/bin/bash\n"
            'echo "ttys003 100 00:10 node /opt/codex/bin/codex.js"\n'
        )
        proc, enters = self._run(script, mode="goal2")
        self.assertEqual(proc.returncode, 11, proc.stdout + proc.stderr)
        self.assertEqual(enters, [], f"keys sent without an id: {enters}")

    def test_correct_session_then_accepts_goal(self):
        script = (
            "#!/bin/bash\n"
            'state="__TMP__/calls"\n'
            'n=$(cat "$state" 2>/dev/null || echo 0)\n'
            'echo $((n+1)) > "$state"\n'
            'if [ "$n" = "0" ]; then\n'
            '  echo "ttys003 100 00:10 /usr/bin/command codex resume 01a174a5-7202-7af3-831e-0bfb5ae8544a"\n'
            "else\n"
            '  echo "ttys003 200 00:01 /usr/bin/command codex resume 01a174a5-7202-7af3-831e-0bfb5ae8544a"\n'
            "fi\n"
        )
        proc, enters = self._run(script, mode="goal2")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("goal dialog accepted after identity check", proc.stdout)
        self.assertEqual(len(enters), 2, f"expected resume Enter + goal Enter: {enters}")


    def test_failed_goal_accept_is_not_reported_as_accepted(self):
        """dot review at 29718cee: a failed accept Enter printed 'goal dialog accepted'."""
        script = (
            "#!/bin/bash\n"
            'state="__TMP__/calls"\n'
            'n=$(cat "$state" 2>/dev/null || echo 0)\n'
            'echo $((n+1)) > "$state"\n'
            'if [ "$n" = "0" ]; then\n'
            '  echo "ttys003 100 00:10 /usr/bin/command codex resume 01a174a5-7202-7af3-831e-0bfb5ae8544a"\n'
            "else\n"
            '  echo "ttys003 200 00:01 /usr/bin/command codex resume 01a174a5-7202-7af3-831e-0bfb5ae8544a"\n'
            "fi\n"
        )
        tmp = Path(tempfile.mkdtemp(prefix="fakeps-acceptfail-"))
        ps = tmp / "fakeps"
        ps.write_text(script.replace("__TMP__", str(tmp))); ps.chmod(0o755)
        stub = StubCmux("acceptfail")
        env = dict(os.environ)
        env["PATH"] = f"{stub.dir}:{env.get('PATH', '')}"
        env["CMUX_CLI_RESTORE_PS"] = str(ps)
        proc = subprocess.run(
            ["bash", str(SCRIPT), "--workspace", WS, "--surface", SF, "--cli", "codex"],
            capture_output=True, text=True, env=env, timeout=180,
        )
        self.assertEqual(proc.returncode, 8, proc.stdout + proc.stderr)
        self.assertIn("accept Enter failed", proc.stderr)
        self.assertNotIn("goal dialog accepted", proc.stdout)


    def test_failed_readback_after_accept_is_not_reported_as_accepted(self):
        """dot review at afcbf5bf: a failed readback grepped as 'dialog cleared'."""
        script = (
            "#!/bin/bash\n"
            'state="__TMP__/calls"\n'
            'n=$(cat "$state" 2>/dev/null || echo 0)\n'
            'echo $((n+1)) > "$state"\n'
            'if [ "$n" = "0" ]; then\n'
            '  echo "ttys003 100 00:10 /usr/bin/command codex resume 01a174a5-7202-7af3-831e-0bfb5ae8544a"\n'
            "else\n"
            '  echo "ttys003 200 00:01 /usr/bin/command codex resume 01a174a5-7202-7af3-831e-0bfb5ae8544a"\n'
            "fi\n"
        )
        tmp = Path(tempfile.mkdtemp(prefix="fakeps-readback-"))
        ps = tmp / "fakeps"
        ps.write_text(script.replace("__TMP__", str(tmp))); ps.chmod(0o755)
        stub = StubCmux("acceptreadfail")
        env = dict(os.environ)
        env["PATH"] = f"{stub.dir}:{env.get('PATH', '')}"
        env["CMUX_CLI_RESTORE_PS"] = str(ps)
        proc = subprocess.run(
            ["bash", str(SCRIPT), "--workspace", WS, "--surface", SF, "--cli", "codex"],
            capture_output=True, text=True, env=env, timeout=180,
        )
        self.assertEqual(proc.returncode, 8, proc.stdout + proc.stderr)
        self.assertIn("could not read the surface after the accept Enter", proc.stderr)
        self.assertNotIn("goal dialog accepted", proc.stdout)
