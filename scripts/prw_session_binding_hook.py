#!/usr/bin/env python3
"""Hook that records session-to-PR bindings in a local JSONL ledger.

Reads one hook payload as JSON on stdin and appends zero or more records.
Always exits 0 and prints nothing. Command text is used in memory only.
"""

import json
import os
import re
import shlex
import subprocess
import sys
from datetime import datetime, timezone

SHELL_TOOLS = {"Bash", "shell", "exec_command", "local_shell"}
SESSION_RE = re.compile(r"[A-Za-z0-9_.:-]{1,128}")
REPO_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
SHA_RE = re.compile(r"[0-9a-fA-F]{7,64}")
PR_URL_RE = re.compile(r"github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/pull/([0-9]+)")
HEREDOC_RE = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1[^\n]*\n.*?(?:\n[ \t]*\2[ \t]*(?=\n|$)|\Z)", re.S)
SEP_CHARS = set(";&|()\n")
SHELLS = {"bash", "sh", "zsh", "dash", "ksh", "fish"}
MAX_BYTES = 1024
DEFAULT_LEDGER = "~/.local/share/prw-metrics/bindings/session-bindings.jsonl"
GIT_TIMEOUT = 2


def _valid_repo(v):
    return isinstance(v, str) and REPO_RE.fullmatch(v) is not None


def _valid_branch(v):
    return (isinstance(v, str) and 0 < len(v) <= 200
            and not any(ord(c) < 32 or ord(c) == 127 for c in v))


def _valid_sha(v):
    return isinstance(v, str) and SHA_RE.fullmatch(v) is not None


def _command_text(tool_input):
    if not isinstance(tool_input, dict):
        return ""
    cmd = tool_input.get("command")
    if cmd is None:
        cmd = tool_input.get("cmd")
    if isinstance(cmd, list):
        argv = [str(a) for a in cmd]
        if (len(argv) >= 3 and os.path.basename(argv[0]) in SHELLS
                and argv[1].startswith("-") and "c" in argv[1]):
            return argv[2]
        return shlex.join(argv)
    return cmd if isinstance(cmd, str) else ""


def _output_text(resp):
    if isinstance(resp, str):
        return resp
    if not isinstance(resp, dict):
        return ""
    parts = [resp.get(k) for k in ("output", "stdout")]
    return "\n".join(p for p in parts if isinstance(p, str))


def _failed(resp):
    if not isinstance(resp, dict):
        return False
    if resp.get("interrupted") is True:
        return True
    for k in ("exit_code", "returncode"):
        v = resp.get(k)
        if isinstance(v, int) and not isinstance(v, bool) and v != 0:
            return True
    return False


def _segments(command):
    """Yield (tokens, status_known) per command segment, ignoring quoted/heredoc text.

    status_known is False when a later `;`, `||`, `|`, `&` or newline means the
    command's exit status need not be this segment's.
    """
    command = HEREDOC_RE.sub("\n", command)
    lex = shlex.shlex(command, posix=True, punctuation_chars=";&|()\n")
    lex.whitespace = " \t\r"
    lex.whitespace_split = True
    segs, seps, seg = [], [], []
    for tok in lex:
        if tok and set(tok) <= SEP_CHARS:
            if seg:
                segs.append(seg)
                seps.append("")
            seg = []
            if seps:
                seps[-1] += tok
        else:
            seg.append(tok)
    if seg:
        segs.append(seg)
        seps.append("")
    for n, (seg, sep) in enumerate(zip(segs, seps)):
        sep = sep.replace("(", "").replace(")", "").replace("\n", "")
        yield seg, sep == "&&" or (n == len(segs) - 1 and sep in ("", ";"))


def _classify(seg):
    """Return (tool, verb, args) for a segment, or None."""
    i = 0
    while i < len(seg) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", seg[i]):
        i += 1
    if i >= len(seg):
        return None
    prog = seg[i]
    rest = seg[i + 1:]
    if prog == "gh":
        repo_flag = []
        while rest and (rest[0] in ("-R", "--repo") or rest[0].startswith("--repo=")):
            n = 1 if "=" in rest[0] else 2
            repo_flag, rest = rest[:n], rest[n:]
        if len(rest) >= 2 and rest[0] == "pr":
            return "gh", rest[1], rest[2:] + repo_flag
    elif prog == "git":
        while rest and rest[0].startswith("-"):
            if rest[0] in ("-C", "-c", "--git-dir", "--work-tree", "--namespace"):
                rest = rest[2:]
            else:
                rest = rest[1:]
        if rest:
            if rest[0] == "worktree" and len(rest) >= 2 and rest[1] == "add":
                return "git", "worktree add", rest[2:]
            return "git", rest[0], rest[1:]
    return None


def _checkout_args(args):
    """(first positional target, -R/--repo value) of `gh pr checkout` arguments."""
    target = repo = None
    i = 0
    while i < len(args):
        a = args[i]
        if a in ("-R", "--repo", "-b", "--branch"):
            if a in ("-R", "--repo") and i + 1 < len(args):
                repo = args[i + 1]
            i += 2
            continue
        if a.startswith("--repo="):
            repo = a.split("=", 1)[1]
        elif not a.startswith("-") and target is None:
            target = a
        i += 1
    return target, repo


def _clean_git(info):
    out = {}
    if not isinstance(info, dict):
        return out
    if _valid_repo(info.get("repo")):
        out["repo"] = info["repo"]
    if _valid_branch(info.get("branch")):
        out["branch"] = info["branch"]
    if _valid_sha(info.get("sha")):
        out["sha"] = info["sha"]
    return out


def records_for(payload, runtime, git, now=None):
    """Return ledger records (list of dicts) for one hook payload."""
    if not isinstance(payload, dict):
        return []
    sid = payload.get("session_id")
    if not isinstance(sid, str) or not SESSION_RE.fullmatch(sid):
        return []
    event = payload.get("hook_event_name")
    cwd = payload.get("cwd") if isinstance(payload.get("cwd"), str) else None
    ts = (now or datetime.now(timezone.utc)).isoformat(timespec="milliseconds").replace("+00:00", "Z")

    def make(kind, info, **extra):
        rec = {"v": 1, "ts": ts, "runtime": runtime, "session_id": sid, "kind": kind}
        rec.update(_clean_git(info))
        rec.update(extra)
        return rec

    def state():
        try:
            return git(cwd) if cwd else {}
        except Exception:
            return {}

    if event == "SessionStart":
        return [make("session_start", state(), source="session_start")]
    if event in ("Stop", "SubagentStop"):
        return [make("stop", state())]
    if event != "PostToolUse" or payload.get("tool_name") not in SHELL_TOOLS:
        return []

    command = _command_text(payload.get("tool_input"))
    if "gh" not in command and "git" not in command:
        return []
    resp = payload.get("tool_response")
    if _failed(resp):
        return []
    output = _output_text(resp)

    pr = source = None
    branch_source = None
    try:
        segs = list(_segments(command))
    except ValueError:
        return []
    for seg, status_known in segs:
        c = _classify(seg)
        if not c:
            continue
        tool, verb, args = c
        if tool == "gh" and verb == "create" and pr is None:
            urls = {f"{m[1]}/{m[2]}#{int(m[3])}" for m in PR_URL_RE.finditer(output)}
            if len(urls) == 1:
                pr, source = urls.pop(), "gh_pr_create"
        elif tool == "gh" and verb == "checkout" and pr is None:
            target, flag_repo = _checkout_args(args)
            if target is None or not status_known:
                continue
            m = PR_URL_RE.search(target)
            if m:
                pr, source = f"{m[1]}/{m[2]}#{int(m[3])}", "gh_pr_checkout"
            elif target.isdigit() and int(target) > 0:
                if flag_repo is not None and not _valid_repo(flag_repo):
                    continue
                pr, source = (f"{flag_repo}#{int(target)}" if flag_repo else int(target)), "gh_pr_checkout"
        elif tool == "git" and branch_source is None:
            if verb == "push":
                branch_source = "git_push"
            elif verb in ("switch", "checkout", "worktree add"):
                branch_source = "git_switch"

    if pr is None and branch_source is None:
        return []
    info = state()
    if isinstance(pr, int):
        repo = _clean_git(info).get("repo")
        if not repo:
            pr = None
        else:
            pr = f"{repo}#{pr}"
    if pr is not None:
        return [make("pr_binding", info, pr=pr, source=source)]
    if branch_source:
        return [make("branch", info, source=branch_source)]
    return []


def _parse_origin(url):
    url = url.strip()
    m = re.search(r"[:/]([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$", url)
    return f"{m[1]}/{m[2]}" if m else None


def real_git(cwd):
    def run(*args):
        r = subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True,
                           timeout=GIT_TIMEOUT, stdin=subprocess.DEVNULL)
        return r.stdout.strip() if r.returncode == 0 else None

    info = {}
    for key, args in (("sha", ("rev-parse", "HEAD")),
                      ("branch", ("rev-parse", "--abbrev-ref", "HEAD")),
                      ("repo", ("remote", "get-url", "origin"))):
        try:
            val = run(*args)
        except Exception:
            val = None
        if not val:
            continue
        if key == "repo":
            val = _parse_origin(val)
        elif key == "branch" and val == "HEAD":
            continue
        if val:
            info[key] = val
    return info


def ledger_path():
    return os.environ.get("PRW_BINDING_LEDGER") or os.path.expanduser(DEFAULT_LEDGER)


def append(records, path):
    dirname = os.path.dirname(path)
    if dirname:
        os.makedirs(dirname, mode=0o700, exist_ok=True)
    for rec in records:
        line = (json.dumps(rec, separators=(",", ":")) + "\n").encode()
        if len(line) > MAX_BYTES:
            continue
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            os.write(fd, line)
        finally:
            os.close(fd)


def main():
    try:
        runtime = "claude"
        argv = sys.argv[1:]
        for i, a in enumerate(argv):
            if a == "--runtime" and i + 1 < len(argv):
                runtime = argv[i + 1]
            elif a.startswith("--runtime="):
                runtime = a.split("=", 1)[1]
        if runtime not in ("claude", "codex"):
            return 0
        payload = json.loads(sys.stdin.read())
        records = records_for(payload, runtime, real_git)
        if records:
            append(records, ledger_path())
    except BaseException:
        pass
    return 0


if __name__ == "__main__":
    try:
        main()
    finally:
        try:
            sys.stdout.flush()
        except Exception:
            pass
    os._exit(0)
