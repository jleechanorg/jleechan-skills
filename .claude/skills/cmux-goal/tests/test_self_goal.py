"""Offline regressions for bin/self_goal.py (own-session binding, composer guard, readback)."""
import json
import os
import pathlib
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

    clear = '{"m":"<local-command-stdout>Goal cleared: c</local-command-stdout>"}'

    def test_set_then_clear_is_not_ok(self):
        st = self.state(rec(met=False, sentinel=True, condition="c"), rec(met=True, sentinel=True, condition="c"), self.clear)
        self.assertEqual(st, ("cleared", "c"))

    def test_set_then_instant_achieve_is_ok(self):
        st = self.state(rec(met=False, sentinel=True, condition="c"), rec(met=True, condition="c"))
        self.assertEqual(st, ("achieved", "c"))


if __name__ == "__main__":
    unittest.main()
