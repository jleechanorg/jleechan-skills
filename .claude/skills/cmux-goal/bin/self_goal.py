#!/usr/bin/env python3
"""Detect the terminal host and set Claude Code's builtin /goal for this session.

  self_goal.py host                 print cmux|tmux|warp|none
  self_goal.py status               print none|active|achieved|failed|cleared [TAB condition]
  self_goal.py set '<condition>'    tmux or cmux: type /goal into this session's own pane/surface, verify readback

Goal state is read from the session transcript's `goal_status` records and the
`Goal cleared:` /goal stdout, never from what was typed. No shell is involved.
"""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

MAX_LEN = 180


def host():
    """Innermost host wins: a tmux pane inside cmux/Warp is typed into via tmux."""
    env = os.environ
    if env.get("TMUX") and env.get("TMUX_PANE"):
        return "tmux"
    if env.get("CMUX_SURFACE_ID") or env.get("CMUX_SOCKET_PATH"):
        return "cmux"
    if env.get("TERM_PROGRAM") == "WarpTerminal":
        return "warp"
    return "none"


def config_dirs():
    dirs = [os.environ.get("CLAUDE_CONFIG_DIR"), "~/.claude-wa", "~/.claude"]
    return [Path(d).expanduser() for d in dirs if d]


def ancestor_pids():
    pids, pid = [], os.getpid()
    for _ in range(32):
        out = subprocess.run(
            ["ps", "-o", "ppid=", "-p", str(pid)], capture_output=True, text=True
        ).stdout.strip()
        if not out.isdigit() or int(out) <= 1:
            break
        pid = int(out)
        pids.append(pid)
    return pids


def session_jsonl(pids=None):
    """Transcript of THIS process's own claude session: the nearest ancestor pid with a
    sessions/<pid>.json. None (caller refuses) when absent or ambiguous."""
    pane = os.environ.get("TMUX_PANE", "")
    for pid in ancestor_pids() if pids is None else pids:
        found = set()
        for cfg in config_dirs():
            try:
                s = json.loads((cfg / "sessions" / f"{pid}.json").read_text())
            except (OSError, ValueError):
                continue
            if pane and not str(s.get("tmux", "")).endswith("." + pane):
                continue
            found.update((cfg / "projects").glob(f"*/{s.get('sessionId')}.jsonl"))
        if found:
            return found.pop() if len(found) == 1 else None
    return None


def goal_state(jsonl):
    return goal_state_text(jsonl.read_text(errors="replace"))


def goal_state_text(text):
    state, cond = "none", ""
    for line in text.splitlines():
        if '"goal_status"' not in line and "Goal cleared:" not in line:
            continue
        try:
            d = json.loads(line)
        except ValueError:
            continue
        a = d.get("attachment") or {}
        if a.get("type") == "goal_status":
            if a.get("sentinel") and not a.get("met"):
                state, cond = "active", a.get("condition", "")
            elif a.get("failed"):
                state, cond = "failed", a.get("condition", "")
            elif a.get("met") and not a.get("sentinel"):
                state, cond = "achieved", a.get("condition", "")
        elif d.get("type") in ("user", "system"):
            c = d.get("content") if d["type"] == "system" else (d.get("message") or {}).get("content")
            m = isinstance(c, str) and re.fullmatch(
                r"<local-command-stdout>Goal cleared: (.*)</local-command-stdout>", c.strip(), re.S
            )
            if m:
                state, cond = "cleared", m.group(1)
    return state, cond


def readback_ok(fresh, cond):
    """Fresh transcript bytes show this goal set and still set (or already met); not failed/cleared."""
    state, got = goal_state_text(fresh)
    return state in ("active", "achieved") and got == cond


def tmux(*args):
    return subprocess.run(
        ["tmux", *args], capture_output=True, text=True, timeout=10, check=True
    ).stdout


def cmux(*args):
    return subprocess.run(
        ["cmux", *args], capture_output=True, text=True, timeout=15, check=True
    ).stdout


def target(kind):
    """(type_text, press_enter, read_screen) bound to this session's own pane/surface, or None."""
    if kind == "tmux":
        pane = os.environ["TMUX_PANE"]
        return (
            lambda t: tmux("send-keys", "-t", pane, "-l", t),
            lambda: tmux("send-keys", "-t", pane, "Enter"),
            lambda: tmux("capture-pane", "-p", "-t", pane, "-S", "-200"),
        )
    caller = json.loads(cmux("identify")).get("caller") or {}
    ws, sf = caller.get("workspace_ref"), caller.get("surface_ref")
    if not (ws and sf):
        return None
    base = ["--workspace", ws, "--surface", sf]
    return (
        lambda t: cmux("send", *base, t),
        lambda: cmux("send-key", *base, "enter"),
        lambda: cmux("capture-pane", *base, "--scrollback", "--lines", "200"),
    )


def composer_empty(screen):
    """True only if every line between the last two composer borders is blank."""
    lines = screen.splitlines()
    bars = [i for i, ln in enumerate(lines) if len(ln.strip()) >= 10 and set(ln.strip()) == {"─"}]
    if len(bars) < 2:
        return False
    region = [ln.strip() for ln in lines[bars[-2] + 1 : bars[-1]]]
    if not region or not region[0].startswith("❯"):
        return False
    region[0] = region[0][1:]
    return " ".join(x.strip() for x in region if x.strip()) in ("", "Press up to edit queued messages")


def do_set(cond, force_after_clear):
    kind = host()
    if kind not in ("tmux", "cmux"):
        hint = " - agent-side route: cmux-goal/SKILL.md section Warp" if kind == "warp" else ""
        return report("unsupported (host is %s; self-typing is tmux/cmux only here)%s" % (kind, hint))
    if not cond or len(cond) > MAX_LEN or re.search(r"[\x00-\x1f\x7f]", cond):
        return report("unsupported (condition must be one line, 1-%d chars)" % MAX_LEN)
    if kind == "cmux" and "\\" in cond:
        return report("unsupported (cmux send expands backslash escapes; drop them from the condition)")
    tgt = target(kind)
    if tgt is None:
        return report("unsupported (no caller surface from cmux identify)")
    type_text, press_enter, read_screen = tgt
    jsonl = session_jsonl()
    if jsonl is None:
        return report("unsupported (no session transcript found for this session)")
    state, current = goal_state(jsonl)
    if state == "active":
        verdict = "reused" if current == cond else "preserved-different"
        print("Goal: already active (%s) %s" % (verdict, current))
        return 0 if current == cond else 4
    if state == "cleared" and not force_after_clear:
        return report("not set (user cleared a goal; never revive without a fresh instruction)", 5)
    if not composer_empty(read_screen()):
        return report("not set (composer holds a draft; refusing to append)", 6)
    offset = jsonl.stat().st_size
    type_text("/goal " + cond)
    time.sleep(0.4)
    press_enter()
    for _ in range(30):
        time.sleep(1)
        with jsonl.open("rb") as f:
            f.seek(offset)
            fresh = f.read().decode(errors="replace")
        persisted = readback_ok(fresh, cond)
        pane_text = read_screen()
        shown = "/goal active" in pane_text or "Goal set: " + cond in pane_text
        if persisted and shown:
            print("Goal: activated via %s (readback ok)" % kind)
            return 0
    return report("unverified (typed but no matching persisted goal_status and footer)", 1)


def report(msg, code=1):
    print("Goal: " + msg)
    return code


def main(argv):
    force = "--force-after-clear" in argv
    argv = [a for a in argv if a != "--force-after-clear"]
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "host":
        print(host())
        return 0
    if cmd == "status":
        jsonl = session_jsonl()
        if jsonl is None:
            return report("unsupported (no session transcript found)")
        print("\t".join(goal_state(jsonl)))
        return 0
    if cmd == "set" and len(argv) == 3:
        try:
            return do_set(argv[2], force)
        except (subprocess.SubprocessError, OSError, ValueError) as e:
            return report("unverified (%s call failed: %s)" % (host(), e))
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
