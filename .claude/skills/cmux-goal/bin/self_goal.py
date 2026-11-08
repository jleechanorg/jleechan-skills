#!/usr/bin/env python3
"""Detect the terminal host and set Claude Code's builtin /goal for this session.

  self_goal.py host                 print cmux|tmux|warp|none
  self_goal.py status               print none|active|achieved|failed|cleared [TAB condition]
  self_goal.py set '<condition>'    tmux only: type /goal into this pane, verify readback

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
    env = os.environ
    if env.get("CMUX_SURFACE_ID") or env.get("CMUX_SOCKET_PATH"):
        return "cmux"
    if env.get("TMUX") and env.get("TMUX_PANE"):
        return "tmux"
    if env.get("TERM_PROGRAM") == "WarpTerminal":
        return "warp"
    return "none"


def config_dirs():
    dirs = [os.environ.get("CLAUDE_CONFIG_DIR"), "~/.claude-wa", "~/.claude"]
    return [Path(d).expanduser() for d in dirs if d]


def session_jsonl():
    """Transcript of the claude process attached to this tmux pane."""
    pane = os.environ.get("TMUX_PANE", "")
    best = None
    for cfg in config_dirs():
        for f in (cfg / "sessions").glob("*.json"):
            try:
                s = json.loads(f.read_text())
            except (OSError, ValueError):
                continue
            if not pane or not str(s.get("tmux", "")).endswith("." + pane):
                continue
            if best is None or s.get("updatedAt", 0) > best[1].get("updatedAt", 0):
                best = (cfg, s)
    if best is None:
        return None
    cfg, s = best
    hits = list((cfg / "projects").glob(f"*/{s['sessionId']}.jsonl"))
    return hits[0] if hits else None


def goal_state(jsonl):
    state, cond = "none", ""
    for line in jsonl.read_text(errors="replace").splitlines():
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
        else:
            m = re.search(r"<local-command-stdout>Goal cleared: (.*)</local", line)
            if m:
                state, cond = "cleared", m.group(1)
    return state, cond


def tmux(*args):
    return subprocess.run(
        ["tmux", *args], capture_output=True, text=True, timeout=10, check=True
    ).stdout


def composer_is_empty(pane):
    for line in reversed(tmux("capture-pane", "-p", "-t", pane).splitlines()):
        if line.startswith("❯"):
            rest = line[1:].strip()
            return rest in ("", "Press up to edit queued messages")
    return False


def do_set(cond, force_after_clear):
    if host() != "tmux":
        return report("unsupported (host is %s; self-typing is tmux-only here)" % host())
    pane = os.environ["TMUX_PANE"]
    if not cond or len(cond) > MAX_LEN or re.search(r"[\x00-\x1f\x7f]", cond):
        return report("unsupported (condition must be one line, 1-%d chars)" % MAX_LEN)
    jsonl = session_jsonl()
    if jsonl is None:
        return report("unsupported (no session transcript found for pane %s)" % pane)
    state, current = goal_state(jsonl)
    if state == "active":
        verdict = "reused" if current == cond else "preserved-different"
        print("Goal: already active (%s) %s" % (verdict, current))
        return 0 if current == cond else 4
    if state == "cleared" and not force_after_clear:
        return report("not set (user cleared a goal; never revive without a fresh instruction)", 5)
    if not composer_is_empty(pane):
        return report("not set (composer holds a draft; refusing to append)", 6)
    offset = jsonl.stat().st_size
    tmux("send-keys", "-t", pane, "-l", "/goal " + cond)
    time.sleep(0.4)
    tmux("send-keys", "-t", pane, "Enter")
    for _ in range(30):
        time.sleep(1)
        with jsonl.open("rb") as f:
            f.seek(offset)
            fresh = f.read().decode(errors="replace")
        persisted = any(
            '"sentinel":true' in ln.replace(" ", "")
            and '"met":false' in ln.replace(" ", "")
            and json.dumps(cond, ensure_ascii=False) in ln
            for ln in fresh.splitlines()
            if '"goal_status"' in ln
        )
        pane_text = tmux("capture-pane", "-p", "-t", pane, "-S", "-200")
        shown = "/goal active" in pane_text or "Goal set: " + cond in pane_text
        if persisted and shown:
            print("Goal: activated via tmux (readback ok)")
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
        except (subprocess.SubprocessError, OSError) as e:
            return report("unverified (tmux call failed: %s)" % e)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
