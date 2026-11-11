"""Behavioural tests for the session-to-PR binding hook."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scripts.prw_session_binding_hook import records_for
from scripts.prw_session_bindings import binding_at, load

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "prw_session_binding_hook.py"
SID = "sess-1"
GIT_OK = {"repo": "me/origin", "branch": "feat/x", "sha": "a" * 40}
ALLOWED = {"v", "ts", "runtime", "session_id", "kind", "repo", "branch", "sha", "pr", "source"}


class FakeGit:
    def __init__(self, result=None):
        self.result = GIT_OK if result is None else result
        self.calls = []

    def __call__(self, cwd):
        self.calls.append(cwd)
        return dict(self.result)


def post(command, stdout="", tool="Bash", **response):
    resp = {"stdout": stdout, "stderr": "", "interrupted": False}
    resp.update(response)
    return {
        "session_id": SID,
        "cwd": "/somewhere",
        "hook_event_name": "PostToolUse",
        "tool_name": tool,
        "tool_input": {"command": command},
        "tool_response": resp,
    }


def run(payload, runtime="claude", git=None):
    git = git or FakeGit()
    return records_for(payload, runtime, git), git


class TestRecords(unittest.TestCase):
    def test_session_start(self):
        recs, _ = run({"session_id": SID, "cwd": "/x", "hook_event_name": "SessionStart"})
        self.assertEqual(len(recs), 1)
        r = recs[0]
        self.assertEqual(r["kind"], "session_start")
        self.assertEqual(r["v"], 1)
        self.assertEqual(r["runtime"], "claude")
        self.assertEqual(r["session_id"], SID)
        self.assertEqual((r["repo"], r["branch"], r["sha"]), ("me/origin", "feat/x", "a" * 40))
        self.assertRegex(r["ts"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$")

    def test_pr_create(self):
        recs, _ = run(post("gh pr create --fill", "https://github.com/acme/app/pull/42\n"))
        self.assertEqual([(r["kind"], r["pr"], r["source"]) for r in recs],
                         [("pr_binding", "acme/app#42", "gh_pr_create")])

    def test_pr_create_without_one_url_gives_nothing(self):
        for out in ("error: something",
                    "https://github.com/acme/app/pull/7\nhttps://github.com/acme/app/pull/8\n"):
            with self.subTest(out=out):
                self.assertEqual(run(post("gh pr create --fill", out))[0], [])

    def test_checkout_url(self):
        for cmd in ("gh pr checkout https://github.com/acme/web/pull/9",
                    "gh pr checkout github.com/acme/web/pull/9 --force",
                    "gh pr checkout https://github.com/acme/web/pull/9;"):
            with self.subTest(cmd=cmd):
                recs, _ = run(post(cmd))
                self.assertEqual([(r["pr"], r["source"]) for r in recs], [("acme/web#9", "gh_pr_checkout")])

    def test_checkout_failed_or_interrupted(self):
        url = "gh pr checkout https://github.com/acme/web/pull/9"
        self.assertEqual(run(post(url, interrupted=True))[0], [])
        self.assertEqual(run(post(url, exit_code=1))[0], [])
        self.assertEqual(run(post(url, returncode=2))[0], [])
        self.assertEqual(len(run(post(url, exit_code=0))[0]), 1)

    def test_only_one_simple_fully_qualified_command_binds(self):
        u = "https://github.com/acme/app/pull/42"
        for cmd in ("gh pr checkout 42", "gh pr checkout 42 -R acme/app", "gh -R acme/app pr checkout " + u,
                    "gh pr checkout " + u + " -R acme/app", "gh pr checkout " + u + "/files",
                    "gh co " + u, "/usr/bin/gh pr checkout " + u, "GH_REPO=a/b gh pr checkout " + u,
                    "gh pr create --dry-run --fill", "gh pr create --web", "gh pr create --fill > out.txt",
                    'gh pr create --body "$(cat f)"', "cd x && gh pr checkout " + u,
                    "gh pr checkout " + u + " && git log", "gh pr checkout " + u + " || true",
                    "(gh pr checkout " + u + ")", "echo " + u + "; gh pr create --fill",
                    "true || gh pr checkout " + u, "if true; then gh pr checkout " + u + "; fi",
                    "gh pr checkout " + u + " | tee log", "gh pr view 42", "gh pr merge 42"):
            with self.subTest(cmd=cmd):
                self.assertEqual(run(post(cmd, u))[0], [])

    def test_branch_commands(self):
        for cmd, where in (("git switch other", "/somewhere"), ("git checkout -b x", "/somewhere"),
                           ("git push", "/somewhere"), ("git push -u origin feat/x", "/somewhere"),
                           ("git worktree add ../w y", "/somewhere"), ("git -C /srv/r push", "/srv/r")):
            with self.subTest(cmd=cmd):
                recs, git = run(post(cmd))
                self.assertEqual([r["kind"] for r in recs], ["branch"])
                self.assertEqual((recs[0]["branch"], recs[0]["sha"]), ("feat/x", "a" * 40))
                self.assertEqual(recs[0]["source"], "git_push" if "push" in cmd else "git_switch")
                self.assertEqual(git.calls, [where])

    def test_compound_or_unresolved_branch_commands_give_nothing(self):
        for cmd in ("git fetch && git switch x", "cd x && git push", "git --git-dir=.git switch x",
                    "git -C $R push", "git -C ~/r push", "GIT_DIR=x git switch y", "git switch x || true"):
            with self.subTest(cmd=cmd):
                self.assertEqual(run(post(cmd))[0], [])

    def test_failed_branch_command_gives_nothing(self):
        self.assertEqual(run(post("git push", exit_code=1))[0], [])

    def test_read_only_and_quoted_commands_give_nothing(self):
        cmds = [
            "gh pr view 42",
            "gh pr list",
            "gh pr checks 42",
            'gh pr comment 42 -b "see https://github.com/acme/app/pull/7"',
            'echo "gh pr create"',
            "cat <<EOF\ngh pr checkout 3\nEOF",
            "cat <<'EOF' > notes.md\ngit push\nEOF",
            "git status",
            "git log --oneline",
        ]
        for cmd in cmds:
            with self.subTest(cmd=cmd):
                out = "https://github.com/acme/app/pull/7"
                self.assertEqual(run(post(cmd, out))[0], [])

    def test_same_second_switch_keeps_earlier_request_bound(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        idx_path = Path(tmp.name) / "ledger.jsonl"
        bound = records_for(post("gh pr checkout https://github.com/me/origin/pull/5"), "claude", FakeGit(),
                            now=datetime(2026, 11, 9, 10, 0, 1, 500000, tzinfo=timezone.utc))
        switched = records_for(post("git switch other"), "claude", FakeGit(GIT_OK | {"branch": "other"}),
                               now=datetime(2026, 11, 9, 10, 0, 3, 700000, tzinfo=timezone.utc))
        idx_path.write_text("".join(json.dumps(r) + "\n" for r in bound + switched))
        idx, _ = load([idx_path])
        at = lambda ms: datetime(2026, 11, 9, 10, 0, ms // 1000, (ms % 1000) * 1000, tzinfo=timezone.utc)
        self.assertIsNone(binding_at(idx, SID, at(1200)))
        self.assertEqual(binding_at(idx, SID, at(3300)), "me/origin#5")
        self.assertIsNone(binding_at(idx, SID, at(3800)))

    def test_stop_events(self):
        for ev in ("Stop", "SubagentStop"):
            recs, _ = run({"session_id": SID, "cwd": "/x", "hook_event_name": ev})
            self.assertEqual([r["kind"] for r in recs], ["stop"])

    def test_unknown_event(self):
        self.assertEqual(run({"session_id": SID, "hook_event_name": "UserPromptSubmit",
                              "prompt": "gh pr create"})[0], [])

    def test_no_git_for_non_shell_or_irrelevant(self):
        git = FakeGit()
        self.assertEqual(records_for(post("git push", tool="Edit"), "claude", git), [])
        self.assertEqual(records_for(post("ls -la && npm test"), "claude", git), [])
        self.assertEqual(git.calls, [])

    def test_invalid_values_dropped(self):
        bad = {"repo": "not a repo", "branch": "bad\x07branch", "sha": "zzzz"}
        recs, _ = run({"session_id": SID, "cwd": "/x", "hook_event_name": "SessionStart"},
                      git=FakeGit(bad))
        self.assertEqual(len(recs), 1)
        for k in ("repo", "branch", "sha"):
            self.assertNotIn(k, recs[0])
        long_branch = FakeGit({"branch": "b" * 201})
        recs, _ = run({"session_id": SID, "hook_event_name": "Stop"}, git=long_branch)
        self.assertNotIn("branch", recs[0])

    def test_invalid_session_id_drops_record(self):
        for sid in ("", "has space", "x" * 129, "a/b", None, 5):
            with self.subTest(sid=sid):
                self.assertEqual(run({"session_id": sid, "hook_event_name": "Stop"})[0], [])
        self.assertEqual(run({"hook_event_name": "Stop"})[0], [])

    def test_no_command_text_or_extra_fields(self):
        marker = "SECRETMARKER123"
        recs, _ = run(post(f"gh pr create --title {marker}",
                           f"{marker} https://github.com/acme/app/pull/42"))
        recs += run(post(f"git push origin {marker}"))[0]
        self.assertTrue(recs)
        for r in recs:
            self.assertLessEqual(set(r), ALLOWED)
            self.assertNotIn(marker, json.dumps(r))
            self.assertNotIn("/somewhere", json.dumps(r))

    def test_codex_runtime_label(self):
        recs, _ = run({"session_id": SID, "hook_event_name": "Stop"}, runtime="codex")
        self.assertEqual(recs[0]["runtime"], "codex")


class TestCodexUnverifiedPayloadShape(unittest.TestCase):
    """Codex payload shape is UNVERIFIED; these pin the tolerant parsing only."""

    def test_unverified_payload_shape_argv_list(self):
        p = post("")
        p["tool_name"] = "shell"
        p["tool_input"] = {"command": ["bash", "-lc", "gh pr create --fill"]}
        p["tool_response"] = {"output": "https://github.com/acme/app/pull/8"}
        recs, _ = run(p, "codex")
        self.assertEqual(recs[0]["pr"], "acme/app#8")

    def test_unverified_payload_shape_plain_argv(self):
        p = post("")
        p["tool_name"] = "local_shell"
        p["tool_input"] = {"command": ["git", "push"]}
        recs, _ = run(p, "codex")
        self.assertEqual([r["kind"] for r in recs], ["branch"])

    def test_unverified_payload_shape_cmd_field(self):
        p = post("")
        p["tool_name"] = "exec_command"
        p["tool_input"] = {"cmd": "gh pr checkout https://github.com/acme/app/pull/4"}
        recs, _ = run(p, "codex")
        self.assertEqual(recs[0]["pr"], "acme/app#4")

    def test_unverified_payload_shape_output_field_failed(self):
        p = post("")
        p["tool_name"] = "shell"
        p["tool_input"] = {"command": "gh pr checkout https://github.com/acme/app/pull/4"}
        p["tool_response"] = {"output": "boom", "exit_code": 1}
        self.assertEqual(run(p, "codex")[0], [])


class TestSubprocess(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ledger = Path(self.tmp.name) / "sub" / "ledger.jsonl"
        self.cwd = tempfile.mkdtemp(dir=self.tmp.name)

    def _env(self, ledger=None):
        env = dict(os.environ)
        env["PRW_BINDING_LEDGER"] = str(ledger or self.ledger)
        env["HOME"] = self.tmp.name
        return env

    def _popen(self, data, ledger=None, runtime="claude"):
        return subprocess.Popen(
            [sys.executable, str(SCRIPT), "--runtime", runtime],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=self._env(ledger), cwd=ROOT,
        ), data

    def _run(self, data, ledger=None):
        p, data = self._popen(data, ledger)
        out, err = p.communicate(data)
        return p.returncode, out, err

    def _payload(self, **kw):
        d = {"session_id": SID, "cwd": self.cwd, "hook_event_name": "SessionStart"}
        d.update(kw)
        return json.dumps(d).encode()

    def test_writes_record_with_modes(self):
        rc, out, err = self._run(self._payload())
        self.assertEqual((rc, out, err), (0, b"", b""))
        lines = self.ledger.read_text().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(json.loads(lines[0])["kind"], "session_start")
        self.assertEqual(self.ledger.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.ledger.parent.stat().st_mode & 0o777, 0o700)

    def test_bad_input_is_silent_and_writes_nothing(self):
        for data in (b"", b"{not json", b"[]", b'{"hook_event_name":"Stop"}'):
            with self.subTest(data=data):
                rc, out, err = self._run(data)
                self.assertEqual((rc, out, err), (0, b"", b""))
        self.assertFalse(self.ledger.exists())

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root ignores modes")
    def test_unwritable_ledger(self):
        ro = Path(self.tmp.name) / "ro"
        ro.mkdir()
        ro.chmod(0o500)
        self.addCleanup(ro.chmod, 0o700)
        rc, out, err = self._run(self._payload(), ledger=ro / "d" / "l.jsonl")
        self.assertEqual((rc, out, err), (0, b"", b""))
        self.assertFalse((ro / "d").exists())

    def test_concurrent_appends(self):
        procs = []
        for i in range(20):
            p, data = self._popen(self._payload(session_id=f"s{i}"))
            p.stdin.write(data)
            p.stdin.close()
            procs.append(p)
        for p in procs:
            p.stdout.read()
            p.stderr.read()
            self.assertEqual(p.wait(), 0)
            p.stdout.close()
            p.stderr.close()
        lines = self.ledger.read_text().splitlines()
        self.assertEqual(len(lines), 20)
        self.assertEqual({json.loads(l)["session_id"] for l in lines}, {f"s{i}" for i in range(20)})

    def test_default_path_uses_home(self):
        env = self._env()
        del env["PRW_BINDING_LEDGER"]
        p = subprocess.run([sys.executable, str(SCRIPT), "--runtime", "claude"],
                           input=self._payload(), capture_output=True, env=env, cwd=ROOT)
        self.assertEqual((p.returncode, p.stdout, p.stderr), (0, b"", b""))
        default = Path(self.tmp.name) / ".local/share/prw-metrics/bindings/session-bindings.jsonl"
        self.assertTrue(default.exists())


if __name__ == "__main__":
    unittest.main()
