"""Dispatch a PR reminder to the enrolled coding session."""
import fcntl
import json
import os
from pathlib import Path
import re
import select
import shutil
import stat
import subprocess
import tempfile
import time
from uuid import UUID

if __package__:
    from .pr_nudger_discovery import discover_owners, surface_claims, terminal_surfaces
else:
    from pr_nudger_discovery import discover_owners, surface_claims, terminal_surfaces


def _run(*args, **kwargs):
    return subprocess.run(
        args, capture_output=True, text=True, timeout=12, check=False, **kwargs
    )


def _checked(*args):
    result = _run(*args)
    result.check_returncode()
    return result.stdout


def _session(owner, cwd):
    cli = owner["cli"]
    key, default = ("CODEX_HOME", ".codex") if cli == "codex" else (
        "CLAUDE_CONFIG_DIR", ".claude"
    )
    root = Path(owner.get("profile_dir") or os.environ.get(key) or Path.home() / default).expanduser()
    if not root.is_absolute() or not root.is_dir():
        return None, None
    session = owner["session"]
    pattern = (
        f"sessions/*/*/*/*-{session}.jsonl" if cli == "codex"
        else f"projects/*/{session}.jsonl"
    )
    files = list(root.glob(pattern))
    if len(files) != 1:
        return None, None
    with files[0].open() as stream:
        for line in stream:
            row = json.loads(line)
            if cli == "codex":
                row = row.get("payload", {}) if row.get("type") == "session_meta" else {}
            if row.get("sessionId", row.get("id")) == session and row.get("cwd"):
                branch = row.get("gitBranch") or (row.get("git") or {}).get("branch")
                if Path(row["cwd"]).resolve() == cwd and (
                    not branch or not owner.get("branch") or
                    owner["branch"].removeprefix("refs/heads/") == branch.removeprefix("refs/heads/")
                ):
                    return files[0].resolve(), {**os.environ, key: str(root)}
                break
    return None, None


def _fields(*args):
    result = _run("lsof", "-w", "-Fn", *args)
    if result.stderr or result.returncode not in (0, 1):
        raise ValueError("process files unavailable")
    pid = None
    for line in result.stdout.splitlines():
        if line.startswith("p"):
            pid = line[1:]
        elif line.startswith("n") and pid:
            yield pid, line[1:]


def _writers(cwd, transcript):
    holders = {pid for pid, _ in _fields("--", str(transcript))}
    editors = {}
    for line in _checked("ps", "-xww", "-o", "pid=,tty=,stat=,comm=").splitlines():
        pid, tty, state, command = line.split(maxsplit=3)
        if state.startswith("Z"):
            continue
        binary = Path(command).name.split()[0]
        cli = re.fullmatch(r"(codex|claude|agy|pi|gemini|cursor)(?:\.exe|\.real)?", binary)
        if cli or pid in holders:
            editors[pid] = (tty, state, cli[1] if cli else "")
    if not editors:
        return []
    paths = dict(_fields("-a", "-p", ",".join(editors), "-d", "cwd"))
    if any(pid not in paths and _run("ps", "-p", pid, "-o", "pid=").returncode == 0
           for pid in editors):
        raise ValueError("live writer cwd unavailable")
    return [
        (pid, tty.removeprefix("/dev/"), state, cli, pid in holders and
         pid in paths and Path(paths[pid]).resolve() == cwd)
        for pid, (tty, state, cli) in editors.items()
        if pid in holders or (pid in paths and Path(paths[pid]).resolve() == cwd)
    ]


def _surfaces(cmux):
    return terminal_surfaces(cmux, strict=True)


def _matches_owner(cmux, item, cwd, owner):
    claims = list(surface_claims({cwd}, *item[:2], strict=True, cmux=cmux))
    return len(claims) == 1 and (claims[0]["cli"], claims[0]["session"]) == (
        owner["cli"], owner["session"]
    ) and claims[0].get("profile_dir", owner.get("profile_dir")) == owner.get("profile_dir")


def _rows(path, start=None):
    with path.open("rb") as stream:
        if start:
            if os.fstat(stream.fileno()).st_ino != start[0]:
                return
            stream.seek(start[1])
        else:
            size = stream.seek(0, os.SEEK_END)
            stream.seek(max(0, size - 131072))
            if size > 131072:
                stream.readline()
        for line in stream:
            if line.endswith(b"\n"):
                yield json.loads(line)


def _terminal_state(cli, path):
    idle, model = False, None
    for row in _rows(path):
        kind = row.get("type")
        if cli == "codex":
            event = row.get("payload", {})
            if kind == "turn_context":
                model = event.get("model")
            elif kind == "event_msg" and event.get("type") in (
                "task_complete", "turn_aborted", "task_started"
            ):
                idle = event["type"] != "task_started"
        elif kind == "assistant":
            message = row["message"]
            reason = message.get("stop_reason")
            idle = reason == "end_turn" or (reason == "stop_sequence" and any(
                part.get("type") == "text" and (part.get("text") or "").strip()
                for part in message.get("content") or []
            ))
            model = message.get("model", model)
        elif kind == "user":
            idle = False
    return idle, model


def _composer(screen, cli):
    lines = [line.strip() for line in screen.splitlines()[-15:] if line.strip()]
    glyph = "›" if cli == "codex" else "❯"
    for index in range(len(lines) - 1, -1, -1):
        if not lines[index].startswith(glyph):
            continue
        footer = r"─{5,}$" if cli == "claude" else r"% (?:context )?left\b|\bgpt-[\w.-]+\b|\bcontext window\b"
        for end in range(index + 1, len(lines)):
            if not re.search(footer, lines[end], re.I):
                continue
            if cli == "claude" and not any(
                re.search(r"bypass permissions|accept edits|\? for shortcuts|shift\+tab", line, re.I)
                for line in lines[end + 1:]
            ):
                return None
            return [lines[index][len(glyph):].strip(), *lines[index + 1:end]]
        break
    return None


def _matches_draft(lines, prompt):
    return bool(lines) and bool(re.fullmatch(r" ?".join(map(re.escape, lines)), prompt))


def _input_is(cmux, workspace, surface, state):
    target = {"workspace_id": workspace, "surface_id": surface}
    result = json.loads(_checked(cmux, "rpc", "surface.input_state", json.dumps(target)))
    return (
        all(result.get(key) == value for key, value in target.items())
        and result.get("terminal") is True and result.get("agent") is True
        and result.get("waiting_on_human") is False
        and result.get("lifecycle") in {"running", "idle"}
        and result.get("state") == state
        and (state != "empty" or result.get("blocks_typing") is False)
    )


def _capture(cmux, target):
    return _checked(cmux, "capture-pane", *target, "--scrollback", "--lines", "1500")


def _snapshot(cmux, target, ref, path, pid):
    with tempfile.TemporaryFile(mode="w+t") as receipt:
        receipt.write(_capture(cmux, target))
        receipt.seek(0)
        screen = receipt.read()
    top = _checked(cmux, "top", *target[:2], "--processes", "--flat", "--format", "tsv")
    rows = [line.split("\t") for line in top.splitlines()]
    surface = [row for row in rows if len(row) >= 5 and row[3:5] == ["surface", ref]]
    if len(surface) != 1 or not screen.strip():
        raise ValueError("cmux observation unavailable")
    cpu = float(surface[0][0])
    if int(surface[0][2]) == 0:
        cpu = float(_checked("ps", "-p", pid, "-o", "%cpu=").strip())
    stat = path.stat()
    return screen, cpu, (stat.st_ino, stat.st_size, stat.st_mtime_ns)


def _accepted(path, start, cli, prompt):
    for row in _rows(path, start):
        kind = row.get("type")
        if cli == "codex":
            msg = row.get("payload", {})
            if kind != "response_item" or msg.get("role") != "user":
                continue
        elif kind == "user":
            msg = row.get("message", {})
        else:
            continue
        content = msg.get("content")
        if isinstance(content, list):
            content = "".join(item.get("text", "") for item in content)
        if content == prompt:
            return True
    return False


def _wait_for_receipt(path, start, cli, prompt, seconds, child=None):
    for _ in range(seconds):
        exited = child is not None and child.poll() is not None
        if _accepted(path, start, cli, prompt):
            return "delivered"
        if exited:
            break
        time.sleep(1)
    return "attempted_delivery"


def _cmux_route(cmux, surface, writer, cwd, path, owner, prompt, apply):
    _, ref, workspace, surface_id, _ = surface
    target = ("--workspace", workspace, "--surface", surface_id)
    first = _snapshot(cmux, target, ref, path, writer[0])
    time.sleep(25)
    second = _snapshot(cmux, target, ref, path, writer[0])
    if first != second or second[1] or not _terminal_state(owner["cli"], path)[0]:
        return "busy"
    if not _input_is(cmux, workspace, surface_id, "empty"):
        return "blocked_composer"
    if _writers(cwd, path) != [writer]:
        return "blocked_writer_changed"
    if not apply:
        return "would_deliver"
    if not owner.get("recheck", lambda *_: True)("cmux"):
        return "stale_pr"
    if (_snapshot(cmux, target, ref, path, writer[0]) != second
            or _writers(cwd, path) != [writer]
            or not _input_is(cmux, workspace, surface_id, "empty")):
        return "no_delivery"
    try:
        _checked(cmux, "send", *target, prompt)
        if not owner.get("revalidate", lambda: True)():
            return "attempted_delivery"
        drafted = _capture(cmux, target)
        if (not _matches_draft(_composer(drafted, owner["cli"]), prompt)
                or _writers(cwd, path) != [writer]
                or not _input_is(cmux, workspace, surface_id, "draft")):
            return "attempted_delivery"
        _checked(cmux, "send-key", *target, "enter")
        return _wait_for_receipt(path, second[2], owner["cli"], prompt, 8)
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return "attempted_delivery"


def _native_writer_free(lock):
    # The lock may be absent after a clean exit. Codex owns acquisition at resume.
    try:
        descriptor = os.open(lock, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    except FileNotFoundError:
        return True
    with os.fdopen(descriptor, "rb") as stream:
        metadata = os.fstat(stream.fileno())
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid():
            raise ValueError("invalid native session lock")
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
    return True


def _resume(cmux, surfaces, cwd, path, env, owner, prompt, apply):
    if owner.get("headless_resume", owner.get("headless_only")) is not True:
        return "blocked_headless_disabled"
    cli = owner["cli"]
    if cli != "codex":
        return "blocked_headless_exclusion_unverified"
    exe = owner.get("cli_bin") or shutil.which(cli)
    if not exe or not Path(exe).is_absolute() or not os.access(exe, os.X_OK):
        return "blocked_cli_unavailable"
    lock = Path(env["CODEX_HOME"]) / "thread-writer-locks" / f"{owner['session']}.lock"
    version = _run(exe, "--version", cwd=cwd, env=env)
    match = re.fullmatch(r"codex-cli (\d+)\.(\d+)\.(\d+)\s*", version.stdout)
    if (not lock.parent.is_dir() or lock.parent.is_symlink()
            or lock.parent.stat().st_uid != os.getuid()
            or version.returncode or not match or tuple(map(int, match.groups())) < (0, 160, 0)):
        return "blocked_headless_exclusion_unverified"
    if not _native_writer_free(lock):
        return "busy"
    if _run(exe, "login", "status", cwd=cwd, env=env).returncode:
        return "blocked_cli_auth"
    _, recorded_model = _terminal_state(cli, path)
    model = owner.get("model") or recorded_model
    if not model:
        return "blocked_session_model"
    cmd = (exe, "exec", "resume", "--model", model, owner["session"], "-")
    stat = path.stat()
    if _writers(cwd, path):
        return "busy"
    if not apply:
        return "would_deliver"
    if not owner.get("recheck", lambda *_: True)("headless"):
        return "stale_pr"
    if (cmux and (_surfaces(cmux) != surfaces or discover_owners([cwd], strict=True, surfaces=surfaces, cmux=cmux))
            or _writers(cwd, path) or not _native_writer_free(lock)):
        return "no_delivery"
    try:
        with tempfile.TemporaryFile() as incoming:
            incoming.write(prompt.encode())
            incoming.seek(0)
            child = subprocess.Popen(
                cmd, cwd=cwd, env=env, stdin=incoming, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, start_new_session=True,
            )
        return _wait_for_receipt(path, (stat.st_ino, stat.st_size), cli, prompt, 20, child)
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return "attempted_delivery"


def _dot(owner, prompt, apply):
    destination = owner.get("destination", "")
    account = owner.get("account", "")
    identity = owner.get("identity_sha256", "")
    parent = owner.get("parent_message_id")
    if not re.fullmatch(r"[a-f0-9]{64}", identity) or not re.fullmatch(r"[A-Za-z0-9_.@-]+", account):
        return "blocked_dot_binding"
    if parent is None:
        bound = re.fullmatch(
            rf"https://chatgpt\.com/(?:g/g-[A-Za-z0-9-]+/)?c/{owner['session']}", destination
        )
    else:
        bound = isinstance(parent, str) and re.fullmatch(
            r"[a-f0-9]{32}~[a-f0-9]{32}~CalpicoMessage~Sentinel_[a-f0-9]{32}", parent
        ) and re.fullmatch(
            r"https://chatgpt\.com/dots/[a-f0-9-]{36}~[a-f0-9]{32}", destination
        )
    if not bound:
        return "blocked_dot_binding"
    helper = Path(__file__).resolve().parents[1] / ".claude/skills/dot/scripts/dot.sh"
    if not helper.is_file():
        return "blocked_dot_unavailable"
    if not apply:
        return "would_deliver"
    if not owner.get("recheck", lambda *_: True)("dot"):
        return "stale_pr"
    try:
        with tempfile.NamedTemporaryFile(mode="w") as draft:
            draft.write(prompt)
            draft.flush()
            command = ["bash", str(helper), "--account", account]
            if parent is None:
                command += ["--url", destination, "send-prepared", draft.name,
                            "--exact-destination", identity]
            else:
                command += ["send-prepared", draft.name, "--exact-dot-reply",
                            identity, destination, parent, owner["session"]]
            child = subprocess.Popen(
                command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                env={key: value for key, value in os.environ.items() if key not in
                     {"DOT_CHROME_USER_DATA", "DOT_PROFILE_DIRECTORY", "DOT_DRY_RUN", "DOT_URL"}},
            )
            try:
                if not select.select([child.stdout], [], [], 120)[0]:
                    return "attempted_delivery"
                offer = os.read(child.stdout.fileno(), 4096)
                nonce = re.fullmatch(rb"prepared-exact ([0-9a-f]{32})\n", offer)
                if not nonce:
                    child.communicate(timeout=12)
                    return "no_delivery"
                if not owner.get("revalidate", lambda: True)():
                    child.communicate(timeout=12)
                    return "attempted_delivery"
                receipt, _ = child.communicate(b"commit " + nonce[1] + b"\n", timeout=18)
                frames = receipt.splitlines()
                if child.returncode == 0 and frames == [b"aborted " + nonce[1]]:
                    return "no_delivery"
                return "delivered" if b"DOT_SENT_VERIFIED" in frames else "attempted_delivery"
            finally:
                if child.poll() is None:
                    child.terminate()
                    child.communicate(timeout=12)
    except (OSError, ValueError, subprocess.SubprocessError):
        return "attempted_delivery"


def _cwd_claimed(cmux, cwd, surfaces):
    return bool(discover_owners([cwd], strict=True, surfaces=surfaces, cmux=cmux))


def route(owner, prompt, apply):
    try:
        cli = owner["cli"]
        if str(UUID(owner["session"])) != owner["session"]:
            return "blocked_session_binding"
        # The display proof requires one printable line and rejects terminal controls.
        if not prompt or not prompt.isprintable() or prompt != prompt.strip():
            return "blocked_prompt"
        if cli == "dot":
            return _dot(owner, prompt, apply)
        if cli not in {"codex", "claude"}:
            return "blocked_cli_unsupported"
        cwd = Path(owner["cwd"]).resolve(strict=True)
        path, env = _session(owner, cwd)
        if path is None:
            return "blocked_session_binding"
        cmux = shutil.which("cmux")
        if not cmux and owner.get("headless_only") is not True:
            return "blocked_cmux_unavailable"
        surfaces = _surfaces(cmux) if cmux else []
        writers = _writers(cwd, path)
        if not writers:
            if cmux and discover_owners([cwd], strict=True, surfaces=surfaces, cmux=cmux):
                return "blocked_surface_present"
            if any(item[:2] == (owner.get("workspace"), owner.get("surface")) for item in surfaces):
                return "blocked_surface_present"
            return _resume(cmux, surfaces, cwd, path, env, owner, prompt, apply)
        if len(writers) != 1 or writers[0][3:] != (cli, True):
            return "busy"
        _, tty, state, _, _ = writers[0]
        matches = [item for item in surfaces if item[-1] == tty]
        if len(matches) != 1 or not all(matches[0][2:4]) or "+" not in state:
            return "busy"
        if owner.get("cmux_discovered") and matches[0][:2] != (owner["workspace"], owner["surface"]):
            return "blocked_surface_changed"
        if not _matches_owner(cmux, matches[0], cwd, owner):
            return "blocked_surface_binding"
        owner.get("confirm_owner", lambda *_: None)(*matches[0][:2])
        return _cmux_route(cmux, matches[0], writers[0], cwd, path, owner, prompt, apply)
    except (KeyError, TypeError, ValueError, OSError, subprocess.SubprocessError):
        return "blocked_route_unverified"
