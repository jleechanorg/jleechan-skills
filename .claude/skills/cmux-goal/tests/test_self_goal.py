"""Offline regressions for bin/self_goal.py (own-session binding, composer guard, readback)."""
import io
import contextlib
import json
import os
import pathlib
import stat
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "bin"))
import self_goal as g  # noqa: E402

BAR = "─" * 40


def rec(**kw):
    return json.dumps({"attachment": {"type": "goal_status", **kw}})


def screen(*composer):
    return "\n".join(["● done", BAR, *composer, BAR, "  status"])


class OwnSession(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.cfgs = [self.tmp / "a", self.tmp / "b"]
        self.old = dict(os.environ)
        os.environ.update(
            HOME=str(self.tmp), CLAUDE_CONFIG_DIR=str(self.cfgs[0]), TMUX_PANE="%1"
        )

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.old)

    def session(self, cfg, pid, sid, tmux="s:@1.%1"):
        (cfg / "sessions").mkdir(parents=True, exist_ok=True)
        (cfg / "projects" / "p").mkdir(parents=True, exist_ok=True)
        meta = {"pid": pid, "sessionId": sid, "tmux": tmux}
        (cfg / "sessions" / f"{pid}.json").write_text(json.dumps(meta))
        (cfg / "projects" / "p" / f"{sid}.jsonl").write_text("{}\n")

    def test_foreign_session_on_same_pane_id_is_never_used(self):
        self.session(self.cfgs[0], 111, "MINE")
        self.session(self.cfgs[0], 222, "FOREIGN")  # other tmux server, also %1
        self.assertEqual(g.session_jsonl([111]).stem, "MINE")
        self.assertIsNone(g.session_jsonl([]))
        self.assertIsNone(g.session_jsonl([333]))

    def test_nearest_ancestor_wins(self):
        self.session(self.cfgs[0], 111, "INNER")
        self.session(self.cfgs[0], 222, "OUTER")
        self.assertEqual(g.session_jsonl([111, 222]).stem, "INNER")

    def test_ambiguous_pid_across_config_dirs_refuses(self):
        os.environ["CLAUDE_CONFIG_DIR"] = str(self.cfgs[0])
        os.environ["HOME"] = str(self.tmp)
        (self.tmp / ".claude").symlink_to(self.cfgs[1], target_is_directory=True)
        self.session(self.cfgs[0], 111, "ONE")
        self.session(self.cfgs[1], 111, "TWO")
        self.assertIsNone(g.session_jsonl([111]))

    def test_no_tmux_pane_still_resolves_own_session(self):
        os.environ.pop("TMUX_PANE")  # cmux host: no tmux involved
        self.session(self.cfgs[0], 111, "MINE", tmux="")
        self.assertEqual(g.session_jsonl([111]).stem, "MINE")

    def test_pane_mismatch_refuses(self):
        self.session(self.cfgs[0], 111, "MINE", tmux="s:@1.%9")
        self.assertIsNone(g.session_jsonl([111]))


class Composer(unittest.TestCase):
    def test_empty(self):
        self.assertTrue(g.composer_empty(screen("❯ ")))
        self.assertTrue(g.composer_empty(screen("❯ Press up to edit queued messages")))

    def test_drafts_refused(self):
        self.assertFalse(g.composer_empty(screen("❯ one line")))
        self.assertFalse(g.composer_empty(screen("❯ ", "  second line only")))
        self.assertFalse(g.composer_empty(screen("❯ first", "  second")))
        self.assertFalse(g.composer_empty("no borders here"))


class Readback(unittest.TestCase):
    def state(self, *lines):
        return g.goal_state_text("\n".join(lines))

    SET = rec(met=False, sentinel=True, condition="c")
    CLEAR_TXT = "<local-command-stdout>Goal cleared: c</local-command-stdout>"
    SYS = json.dumps({"type": "system", "subtype": "local_command", "content": CLEAR_TXT})
    USR = json.dumps({"type": "user", "message": {"role": "user", "content": CLEAR_TXT}})
    QUOTE = json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": CLEAR_TXT}]}})

    def test_outcomes_separately(self):
        done = rec(met=True, condition="c")
        failed = rec(met=False, failed=True, condition="c", reason="r")
        sentinel_clear = rec(met=True, sentinel=True, condition="c")
        self.assertTrue(g.readback_ok(self.SET, "c"))
        self.assertTrue(g.readback_ok("\n".join([self.SET, done]), "c"))
        self.assertFalse(g.readback_ok("\n".join([self.SET, failed]), "c"))
        self.assertFalse(g.readback_ok("\n".join([self.SET, sentinel_clear, self.SYS]), "c"))
        self.assertFalse(g.readback_ok(self.SET, "other"))
        self.assertFalse(g.readback_ok("", "c"))

    def test_clear_only_from_real_command_output(self):
        self.assertEqual(self.state(self.SET, self.SYS), ("cleared", "c"))
        self.assertEqual(self.state(self.SET, self.USR), ("cleared", "c"))
        self.assertEqual(self.state(self.SET, self.QUOTE), ("active", "c"))


FAKE_CMUX = """#!/usr/bin/env python3
import json, os, sys
log, jl = os.environ["FAKE_LOG"], os.environ["FAKE_JSONL"]
open(log, "a").write(json.dumps(sys.argv[1:]) + "\\n")
cmd = sys.argv[1]
if cmd == "identify":
    print(json.dumps({"caller": {"workspace_ref": "workspace:1", "surface_ref": "surface:2"}}))
elif cmd == "send-key":
    open(jl, "a").write(os.environ["FAKE_RECORDS"] + "\\n")
elif cmd == "capture-pane":
    log2 = os.environ.get("FAKE_SCREEN")
    print(open(log2).read() if log2 else "\\n".join(["● x", "-" * 0 + "─" * 30, "❯ ", "─" * 30, "  status", "Goal set: c"]))
"""


class FakeBase(unittest.TestCase):
    """Offline: fake `cmux`/`tmux` on PATH record argv; no real terminal is involved."""

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        (self.tmp / "bin").mkdir()
        exe = self.tmp / "bin" / "cmux"
        exe.write_text(FAKE_CMUX)
        exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
        self.jsonl = self.tmp / "s.jsonl"
        self.jsonl.write_text("")
        self.log = self.tmp / "argv.log"
        self.old = dict(os.environ)
        os.environ.update(
            PATH=f"{self.tmp / 'bin'}:{os.environ['PATH']}", CMUX_SURFACE_ID="U",
            FAKE_LOG=str(self.log), FAKE_JSONL=str(self.jsonl),
        )
        os.environ.pop("TMUX", None)
        self.saved = (g.session_jsonl, g.time.sleep)
        g.session_jsonl = lambda pids=None: self.jsonl
        g.time.sleep = lambda s: None

    def tearDown(self):
        g.session_jsonl, g.time.sleep = self.saved
        os.environ.clear()
        os.environ.update(self.old)

    def deep_screen(self, tail):
        """Scrollback >200 lines: an old draft composer at the top, filler, then `tail`."""
        old = [BAR, "❯ OLD DRAFT", BAR]
        scr = self.tmp / "screen.txt"
        scr.write_text("\n".join(old + ["filler"] * 300 + tail + ["Goal set: c"]))
        os.environ["FAKE_SCREEN"] = str(scr)

    def run_set(self, cond, records):
        os.environ["FAKE_RECORDS"] = "\n".join(records)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = g.do_set(cond, False)
        calls = [json.loads(x) for x in self.log.read_text().splitlines()] if self.log.exists() else []
        return rc, out.getvalue(), calls


class CmuxPath(FakeBase):
    def test_full_scrollback_captured_and_tail_decides(self):
        self.deep_screen([BAR, "❯ ", BAR, "  status"])
        rc, out, calls = self.run_set("c", [rec(met=False, sentinel=True, condition="c")])
        self.assertEqual(rc, 0)
        first = [c for c in calls if c[0] == "capture-pane"][0]
        self.assertEqual(first[-3:], ["--scrollback", "--lines", "1500"])

    def test_dialog_at_bottom_refuses_even_if_deep_buffer_has_empty_composer(self):
        self.deep_screen(["Allow this tool call? (y/n)"])
        rc, out, calls = self.run_set("c", [])
        self.assertEqual(rc, 6)
        self.assertFalse([c for c in calls if c[0] in ("send", "send-key")])

    def test_overlong_condition_refused_nothing_typed(self):
        rc, out, calls = self.run_set("x" * (g.MAX_LEN + 1), [])
        self.assertEqual(rc, 1)
        self.assertFalse(calls)

    def test_types_into_own_surface_and_reads_back(self):
        rc, out, calls = self.run_set("c", [rec(met=False, sentinel=True, condition="c")])
        self.assertEqual(rc, 0)
        self.assertIn("activated via cmux (readback ok)", out)
        base = ["--workspace", "workspace:1", "--surface", "surface:2"]
        self.assertIn(["send", *base, "/goal c"], calls)
        self.assertIn(["send-key", *base, "enter"], calls)
        self.assertLess(calls.index(["send", *base, "/goal c"]), calls.index(["send-key", *base, "enter"]))

    def test_failed_goal_is_not_activation(self):
        recs = [rec(met=False, sentinel=True, condition="c"), rec(met=False, failed=True, condition="c")]
        rc, out, _ = self.run_set("c", recs)
        self.assertEqual(rc, 1)
        self.assertIn("unverified", out)

    def test_active_different_goal_preserved_nothing_typed(self):
        self.jsonl.write_text(rec(met=False, sentinel=True, condition="other") + "\n")
        rc, out, calls = self.run_set("c", [])
        self.assertEqual(rc, 4)
        self.assertFalse([c for c in calls if c[0] in ("send", "send-key")])

    def test_backslash_condition_refused_nothing_typed(self):
        rc, out, calls = self.run_set("a\\nb", [])
        self.assertEqual(rc, 1)
        self.assertFalse(calls)


FAKE_TMUX = FAKE_CMUX.replace('cmd == "identify"', 'cmd == "never"').replace(
    'cmd == "send-key"', 'cmd == "send-keys" and sys.argv[-1] == "Enter"').replace(
    'cmd == "capture-pane"', 'cmd == "capture-pane"').replace("FAKE_LOG", "FAKE_TLOG")


class TmuxInsideCmux(FakeBase):
    def test_innermost_tmux_wins_over_inherited_cmux(self):
        exe = self.tmp / "bin" / "tmux"
        exe.write_text(FAKE_TMUX)
        exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
        tlog = self.tmp / "tmux-argv.log"
        os.environ.update(TMUX="sock,1,0", TMUX_PANE="%7", FAKE_TLOG=str(tlog))
        rc, out, cm = self.run_set("c", [rec(met=False, sentinel=True, condition="c")])
        calls = [json.loads(x) for x in tlog.read_text().splitlines()]
        self.assertEqual(rc, 0)
        self.assertIn("activated via tmux", out)
        self.assertEqual(cm, [])  # the outer cmux surface is never touched
        self.assertIn(["send-keys", "-t", "%7", "-l", "/goal c"], calls)
        self.assertTrue(all(c[c.index("-t") + 1] == "%7" for c in calls))
        first = [c for c in calls if c[0] == "capture-pane"][0]
        self.assertEqual(first, ["capture-pane", "-p", "-t", "%7", "-J", "-S", "-"])


if __name__ == "__main__":
    unittest.main()
