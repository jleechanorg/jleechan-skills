"""Dispatch a PR reminder to the enrolled coding session."""
from contextlib import contextmanager, nullcontext
import fcntl
import json
import os
from pathlib import Path
import re
import select
import shutil
import socket
import sqlite3
import stat
import subprocess
import sys
import tempfile
import time
from urllib.parse import unquote, urlparse
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


def _agy_app_data():
    return Path(
        os.environ.get("ANTIGRAVITY_APP_DATA_DIR") or Path.home() / ".gemini" / "antigravity-cli"
    ).expanduser()


def _agy_summary(app_data, session):
    db_path = app_data / "conversation_summaries.db"
    if not db_path.is_file():
        return None
    try:
        with sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True) as con:
            row = con.execute(
                "SELECT workspace_uris, status, not_fully_idle, killed "
                "FROM conversation_summaries WHERE conversation_id=?",
                (session,),
            ).fetchone()
    except (OSError, sqlite3.Error):
        return None
    if not row:
        return None
    try:
        uris = json.loads(row[0] or "[]")
    except ValueError:
        return None
    paths = set()
    for uri in uris:
        parsed = urlparse(str(uri))
        if parsed.scheme == "file" and parsed.path:
            try:
                paths.add(Path(unquote(parsed.path)).resolve())
            except OSError:
                continue
    return paths, row[1], bool(row[2]), bool(row[3])


def _agy_idle(env, session):
    app_data = Path(env.get("ANTIGRAVITY_APP_DATA_DIR") or _agy_app_data()).expanduser()
    summary = _agy_summary(app_data, session)
    if summary is None:
        return False
    _, status, not_fully_idle, killed = summary
    return not killed and not not_fully_idle and status == "CASCADE_RUN_STATUS_IDLE"


_PROFILE_ENV_KEYS = {"codex": "CODEX_HOME", "claude": "CLAUDE_CONFIG_DIR"}


def _session(owner, cwd):
    cli = owner["cli"]
    session = owner["session"]
    if cli == "agy":
        if str(UUID(session)) != session:
            return None, None
        app_data = _agy_app_data()
        if not app_data.is_absolute() or not app_data.is_dir():
            return None, None
        transcript = app_data / "brain" / session / ".system_generated" / "logs" / "transcript.jsonl"
        if not transcript.is_file():
            return None, None
        resolved = transcript.resolve()
        if not resolved.is_relative_to((app_data / "brain").resolve()):
            return None, None
        summary = _agy_summary(app_data, session)
        if not summary or summary[3] or cwd not in summary[0]:
            return None, None
        return resolved, {**os.environ, "ANTIGRAVITY_APP_DATA_DIR": str(app_data)}
    key, default = ("CODEX_HOME", ".codex") if cli == "codex" else (
        "CLAUDE_CONFIG_DIR", ".claude"
    )
    root = Path(owner.get("profile_dir") or os.environ.get(key) or Path.home() / default).expanduser()
    if not root.is_absolute() or not root.is_dir():
        return None, None
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
    holders = {pid for pid, _ in _fields("--", str(transcript))} if transcript else set()
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


def _owner_surfaces(cmux, owner):
    try:
        return _surfaces(cmux) if cmux else []
    except (OSError, ValueError, subprocess.SubprocessError):
        if (owner.get("headless_only") is True
                and owner.get("host") == socket.gethostname()
                and sys.platform.startswith("linux")
                and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))):
            return []
        raise


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
        elif cli == "agy":
            if kind in {"USER_INPUT", "GENERIC"}:
                idle = False
            elif kind == "PLANNER_RESPONSE":
                model = row.get("model", model)
                idle = row.get("status") == "DONE" and not row.get("tool_calls")
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
        if cli == "agy":
            if kind != "USER_INPUT":
                continue
            content = row.get("content") or ""
            match = re.search(r"<USER_REQUEST>\n(.*?)\n</USER_REQUEST>", content, re.S)
            if (match.group(1) if match else content) == prompt:
                return True
            # agy stores only the head of a long request and replaces the rest, plus the
            # start of its own metadata, with a "<truncated N bytes>" marker. Accept that
            # row when its head is a prefix of the prompt (the PR and head SHA come first)
            # and the marker is large enough to have held the rest of the prompt.
            cut = re.fullmatch(r"<USER_REQUEST>\n(.*?)\n<truncated (\d+) bytes>\n.*", content, re.S)
            if cut:
                head, gone = cut.group(1), int(cut.group(2))
                rest = len(prompt.encode()) - len(head.encode())
                if len(head) >= 200 and prompt.startswith(head) and 0 <= rest <= gone:
                    return True
            continue
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


def verify_delivery_receipt(owner):
    """Check the original session beyond the checkpoint recorded before sending."""
    try:
        cli, session = owner["cli"], owner["session"]
        if cli not in {"codex", "claude", "agy"} or str(UUID(session)) != session:
            return False
        receipt = owner["receipt"]
        path, _ = _session(owner, Path(owner["cwd"]).resolve(strict=True))
        if path is None or path != Path(receipt["path"]):
            return False
        inode, offset = receipt["start"]
        if type(inode) is not int or type(offset) is not int or offset < 0:
            return False
        return _accepted(path, (inode, offset), cli, receipt["prompt"])
    except (AttributeError, KeyError, OSError, TypeError, ValueError):
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
    if not _managed_cmux_claim(cwd, owner, writer[0]):
        return "blocked_managed_writer_unverified"
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
            or not _managed_cmux_claim(cwd, owner, writer[0])
            or not _input_is(cmux, workspace, surface_id, "empty")):
        return "no_delivery"
    owner.get("checkpoint_receipt", lambda *_: None)(path, second[2])
    try:
        _checked(cmux, "send", *target, prompt)
        if not owner.get("revalidate", lambda: True)():
            return "attempted_delivery"
        drafted = _capture(cmux, target)
        if (not _matches_draft(_composer(drafted, owner["cli"]), prompt)
                or _writers(cwd, path) != [writer]
                or not _managed_cmux_claim(cwd, owner, writer[0])
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


def _verified_lock_dir(path):
    return path.is_dir() and not path.is_symlink() and path.stat().st_uid == os.getuid()




def _managed_claim_path(cwd):
    root, git_dir = _checked(
        "git", "-C", str(cwd), "rev-parse", "--show-toplevel", "--absolute-git-dir"
    ).splitlines()
    path = Path(git_dir)
    if (Path(root).resolve() != cwd or not path.is_absolute()
            or path.resolve(strict=True) != path or not _verified_lock_dir(path)):
        raise ValueError("managed worktree admin directory is unverified")
    return path / "pr-owner-nudger.writer.lock"


@contextmanager
def _managed_claim(path, *, create=True):
    mode = os.O_RDWR | os.O_CREAT if create else os.O_RDONLY
    fd = os.open(path, mode | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_uid != os.getuid() or info.st_nlink != 1):
            raise ValueError("invalid managed writer claim")
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield fd
    finally:
        # Closing the scheduler's copy preserves the flock inherited by its
        # child. LOCK_UN would also unlock the child's shared description.
        os.close(fd)


def _spawn_claimed(command, claim, **kwargs):
    if claim is None:
        return subprocess.Popen(command, **kwargs)
    # Some Codex wrappers spawn the native binary without forwarding extra
    # descriptors. The detached holder waits for the enrolled executable.
    hold = (
        "import subprocess, sys\n"
        "claim = int(sys.argv[1])\n"
        "raise SystemExit(subprocess.call(sys.argv[2:], pass_fds=(claim,)))"
    )
    return subprocess.Popen(
        (sys.executable, "-c", hold, str(claim), *command),
        pass_fds=(claim,), **kwargs,
    )


def _managed_cmux_claim(cwd, owner, pid):
    if owner.get("managed_exclusive") is not True:
        return True
    path = _managed_claim_path(cwd)
    try:
        with _managed_claim(path, create=False):
            return False
    except FileNotFoundError:
        return False
    except BlockingIOError:
        holder = None
        exclusive = set()
        report = _checked("lsof", "-w", "-Fpl", "--", str(path))
        for line in report.splitlines():
            if line.startswith("p"):
                holder = line[1:]
            elif line == "lW" and holder:
                exclusive.add(holder)
        return exclusive == {pid}


def _supported_codex(executable, cwd, env):
    version = _run(executable, "--version", cwd=cwd, env=env)
    match = re.fullmatch(r"codex-cli (\d+)\.(\d+)\.(\d+)\s*", version.stdout)
    return not version.returncode and bool(match and tuple(map(int, match.groups())) >= (0, 160, 0))


def _resume(cmux, surfaces, cwd, path, env, owner, prompt, apply):
    if owner.get("headless_resume", owner.get("headless_only")) is not True:
        return "blocked_headless_disabled"
    cli = owner["cli"]
    if cli not in {"codex", "agy"}:
        return "blocked_headless_exclusion_unverified"
    exe = owner.get("cli_bin") or shutil.which(cli)
    if not exe or not Path(exe).is_absolute() or not os.access(exe, os.X_OK):
        return "blocked_cli_unavailable"
    if apply and not owner.get("admit_launch", lambda: True)():
        return "blocked_launch_capacity"
    managed = owner.get("managed_exclusive") is True
    lock = None
    if cli == "codex":
        lock = Path(env["CODEX_HOME"]) / "thread-writer-locks" / f"{owner['session']}.lock"
        if not _verified_lock_dir(lock.parent) or not _supported_codex(exe, cwd, env):
            return "blocked_headless_exclusion_unverified"
        if not _native_writer_free(lock):
            return "busy"
        if _run(exe, "login", "status", cwd=cwd, env=env).returncode:
            return "blocked_cli_auth"
        _, recorded_model = _terminal_state(cli, path)
        model = owner.get("model") or recorded_model
        if not model:
            return "blocked_session_model"
        project_config = _PROJECT_DOC_CONFIG if managed else ()
        sandbox = owner.get("resume_sandbox")
        if sandbox is not None and (
            not managed or owner.get("launch_authorized") is not True
            or sandbox not in ("read-only", "workspace-write", "danger-full-access")
        ):
            return "blocked_resume_sandbox"
        sandbox_config = ("--sandbox", sandbox) if sandbox is not None else ()
        cmd = (
            exe, "exec", *sandbox_config, "resume", *project_config,
            "--model", model, owner["session"], "-",
        )
    else:
        if not managed or owner.get("launch_authorized") is not True:
            return "blocked_headless_exclusion_unverified"
        if not _agy_idle(env, owner["session"]):
            return "busy"
        _, recorded_model = _terminal_state(cli, path)
        model = owner.get("model") or recorded_model
        if not model:
            return "blocked_session_model"
        profile_dir = owner.get("profile_dir")
        add_dir = ("--add-dir", str(Path(profile_dir).resolve())) if profile_dir and Path(profile_dir).is_dir() else ()
        cmd = (
            exe, "--conversation", owner["session"], "-p", prompt,
            "--output-format", "stream-json", "--model", model,
            *add_dir, "--dangerously-skip-permissions",
        )
    stat = path.stat()
    if _writers(cwd, path):
        return "busy"
    if not apply:
        return "would_deliver"
    claim_context = _managed_claim(_managed_claim_path(cwd)) if managed else nullcontext(None)
    if managed and not callable(owner.get("recheck")):
        return "blocked_managed_writer_unverified"
    reserved = sent = False
    try:
        with claim_context as claim:
            if not owner.get("recheck", lambda *_: True)("headless"):
                return "stale_pr"
            reserved = True
            if (cmux and (_owner_surfaces(cmux, owner) != surfaces or _cwd_claimed(cmux, cwd, surfaces))
                    or _writers(cwd, path)
                    or (lock is not None and not _native_writer_free(lock))
                    or (cli == "agy" and not _agy_idle(env, owner["session"]))):
                return "no_delivery"
            with (tempfile.TemporaryFile() if cli == "codex" else nullcontext(None)) as incoming:
                if cli == "codex":
                    incoming.write(prompt.encode())
                    incoming.seek(0)
                owner.get("checkpoint_receipt", lambda *_: None)(path, (stat.st_ino, stat.st_size))
                sent = True
                child = _spawn_claimed(
                    cmd, claim, cwd=cwd, env=env,
                    stdin=incoming if cli == "codex" else subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
                )
        return _wait_for_receipt(path, (stat.st_ino, stat.st_size), cli, prompt, 20, child)
    except BlockingIOError:
        return "attempted_delivery" if sent else "busy"
    except (OSError, ValueError, subprocess.SubprocessError):
        if managed and not reserved:
            return "blocked_managed_writer_unverified"
        return "attempted_delivery" if sent else "no_delivery"


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
    if not owner.get("admit_launch", lambda: True)():
        return "blocked_launch_capacity"
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
        if cli not in {"codex", "claude", "agy"}:
            return "blocked_cli_unsupported"
        if owner.get("managed_exclusive") is True and (
            cli not in {"codex", "agy"} or owner.get("host") != socket.gethostname()
            or not Path(owner.get("profile_dir", "")).is_absolute()
        ):
            return "blocked_managed_writer_unverified"
        cwd = Path(owner["cwd"]).resolve(strict=True)
        path, env = _session(owner, cwd)
        if path is None:
            return "blocked_session_binding"
        cmux = shutil.which("cmux")
        if not cmux and owner.get("headless_only") is not True:
            return "blocked_cmux_unavailable"
        surfaces = _owner_surfaces(cmux, owner)
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
        profile_key = _PROFILE_ENV_KEYS.get(cli)
        profile_dir = str(Path(env[profile_key]).resolve()) if profile_key and profile_key in env else owner.get("profile_dir")
        owner.get("confirm_owner", lambda *_: None)(*matches[0][:2], profile_dir)
        return _cmux_route(cmux, matches[0], writers[0], cwd, path, owner, prompt, apply)
    except (KeyError, TypeError, ValueError, OSError, subprocess.SubprocessError):
        return "blocked_route_unverified"


# Keep the enrolled project's full instructions available on seed and resume.
_PROJECT_DOC_MAX_BYTES = 65536
_PROJECT_DOC_CONFIG = ("-c", f"project_doc_max_bytes={_PROJECT_DOC_MAX_BYTES}")
_BOOTSTRAP_ACK = "PR_NUDGER_BOOTSTRAP_ACK"
# Newer Codex reports oversize instructions as this one pre-turn error item.
_COMBINED_DOC_NOTICE = re.compile(
    r"Combined user instructions use \d+ bytes, above the \d+-byte `project_doc_max_bytes` "
    r"setting\. The total includes global and thread instructions\. The limit applies only "
    r"to project files\.")
_SKILLS_BUDGET_NOTICE = re.compile(r"Exceeded skills context budget\. All skill descriptions were removed "
                                  r"and \d+ additional skills were not included in the model-visible skills list\.")
_BOOTSTRAP_RECONCILE = "bootstrap_reconciliation_required"
# Intake design: a missing terminal receipt after one ten-minute tick remains
# unsettled. This horizon classifies evidence only; it never authorizes replay.
_BOOTSTRAP_RECEIPT_SECONDS = 600
_BOOTSTRAP_CONFIG = (
    "-c", 'approval_policy="never"', "-c", 'web_search="disabled"',
    "-c", "features.shell_tool=false", "-c", "features.shell_snapshot=false",
    "-c", "features.apps=false", "-c", "features.hooks=false",
    "-c", "features.plugins=false", "-c", "features.multi_agent=false",
    "-c", "features.goals=false", "-c", "features.view_image=false",
    *_PROJECT_DOC_CONFIG,
)


def _bootstrap_scope(enrollment, identity, expected_cli=None):
    repo, number, head_repo, branch, sha = identity
    # Operator-enrolled exclusive context; the local tick lock does not exclude
    # arbitrary editors. Each launch also rechecks live worktree and writers.
    cli = enrollment.get("cli")
    allowed = {expected_cli} if expected_cli else {"codex", "agy"}
    if (enrollment.get("launch_authorized") is not True
            or enrollment.get("managed_exclusive") is not True
            or enrollment.get("host") != socket.gethostname()
            or cli not in allowed
            or enrollment.get("head_repo") != head_repo or enrollment.get("branch") != branch
            or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo)
            or not re.fullmatch(r"[0-9a-f]{40}", sha)
            or type(number) is not int or number <= 0):
        raise ValueError("unverified bootstrap authority")
    cwd, profile, executable = (Path(enrollment[key]) for key in ("cwd", "profile_dir", "cli_bin"))
    if not all(path.is_absolute() for path in (cwd, profile, executable)):
        raise ValueError("bootstrap requires exact absolute paths")
    cwd, profile = cwd.resolve(strict=True), profile.resolve(strict=True)
    if not cwd.is_dir() or not profile.is_dir() or not enrollment.get("model"):
        raise ValueError("unverified bootstrap worktree, profile, or model")
    prompt = (f"Verify owner bootstrap for {repo}#{number} at {sha}. "
              f"Do not use tools or take any action. Reply exactly {_BOOTSTRAP_ACK}.")
    return cwd, profile, str(executable), prompt


def _bootstrap_events(path, write=False):
    path = Path(path)
    if not path.is_absolute() or path.resolve(strict=True) != path:
        raise ValueError("bootstrap receipt path must be exact")
    flags = os.O_WRONLY | os.O_APPEND if write else os.O_RDONLY
    stream = os.fdopen(os.open(path, flags | os.O_NOFOLLOW | os.O_NONBLOCK), "wb" if write else "rb")
    info = os.fstat(stream.fileno())
    if (not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_uid != os.getuid() or info.st_nlink != 1 or (write and info.st_size)):
        stream.close()
        raise ValueError("bootstrap receipt is not a private attempt file")
    return stream


def _bootstrap_writer_free(cwd, enrollment, transcript=None):
    cmux = shutil.which("cmux")
    if not cmux and enrollment.get("headless_only") is not True:
        raise ValueError("cmux inventory unavailable")
    return not _writers(cwd, transcript) and not (
        cmux and _cwd_claimed(cmux, cwd, _surfaces(cmux))
    )


def _launch_bootstrap(cwd, enrollment, command, recheck, begin_attempt, *, env=None, prompt_stdin=None):
    reserved = False
    try:
        with _managed_claim(_managed_claim_path(cwd)) as claim:
            if not recheck():
                return "stale_pr"
            events = begin_attempt()
            if events is None:
                return "blocked_bootstrap_reservation"
            reserved = True
            if not _bootstrap_writer_free(cwd, enrollment):
                return "no_bootstrap"
            with (tempfile.TemporaryFile() if prompt_stdin is not None else nullcontext(None)) as incoming, \
                 _bootstrap_events(events, write=True) as outgoing:
                if prompt_stdin is not None:
                    incoming.write(prompt_stdin.encode())
                    incoming.seek(0)
                _spawn_claimed(
                    command, claim, cwd=cwd, env=env,
                    stdin=incoming if prompt_stdin is not None else subprocess.DEVNULL,
                    stdout=outgoing, stderr=subprocess.DEVNULL, start_new_session=True,
                )
        return "bootstrap_started"
    except BlockingIOError:
        return _BOOTSTRAP_RECONCILE if reserved else "busy"
    except (KeyError, TypeError, ValueError, OSError, subprocess.SubprocessError) as error:
        print(f"bootstrap launch failed: {type(error).__name__}: {error}", file=sys.stderr)
        return _BOOTSTRAP_RECONCILE if reserved else "blocked_bootstrap_unverified"


def start_codex_bootstrap(enrollment, identity, *, apply, recheck, begin_attempt):
    """Launch an acknowledgment-only seed after the caller durably reserves it."""
    try:
        cwd, profile, executable, prompt = _bootstrap_scope(enrollment, identity, "codex")
        if not os.access(executable, os.X_OK):
            return "blocked_cli_unavailable"
        if not _bootstrap_writer_free(cwd, enrollment):
            return "busy"
        if not apply:
            return "would_bootstrap"
        env = {**os.environ, "CODEX_HOME": str(profile)}
        if not _supported_codex(executable, cwd, env):
            return "blocked_headless_exclusion_unverified"
        if _run(executable, "login", "status", cwd=cwd, env=env).returncode:
            return "blocked_cli_auth"
        # Ask the CLI about enabled MCP servers. An empty TOML table does not
        # reliably replace servers inherited from project or machine config.
        inventory = _run(executable, *_BOOTSTRAP_CONFIG, "mcp", "list", "--json", cwd=cwd, env=env)
        if inventory.returncode:
            return "blocked_bootstrap_tools"
        servers = json.loads(inventory.stdout)
        if not isinstance(servers, list) or any(
            not isinstance(server, dict) or server.get("enabled") is not False for server in servers
        ):
            return "blocked_bootstrap_tools"
        # The seed uses a read-only sandbox, disabled side-effect tools and
        # no personal integrations. Acknowledgment is not PR delivery.
        command = (
            executable, "exec", "--json", "--ignore-user-config", "--sandbox", "read-only",
            *_BOOTSTRAP_CONFIG, "--model", enrollment["model"], "-",
        )
    except (KeyError, TypeError, ValueError, OSError, subprocess.SubprocessError) as error:
        print(f"bootstrap launch failed: {type(error).__name__}: {error}", file=sys.stderr)
        return "blocked_bootstrap_unverified"
    return _launch_bootstrap(cwd, enrollment, command, recheck, begin_attempt, env=env, prompt_stdin=prompt)


def start_agy_bootstrap(enrollment, identity, *, apply, recheck, begin_attempt):
    """Launch an acknowledgment-only agy seed after the caller durably reserves it."""
    try:
        cwd, profile, executable, prompt = _bootstrap_scope(enrollment, identity, "agy")
        if not os.access(executable, os.X_OK):
            return "blocked_cli_unavailable"
        if not _bootstrap_writer_free(cwd, enrollment):
            return "busy"
        if not apply:
            return "would_bootstrap"
        command = (
            executable, "-p", prompt, "--output-format", "stream-json",
            "--model", enrollment["model"], "--disable-slash-commands",
            "--add-dir", str(profile), "--dangerously-skip-permissions",
        )
    except (KeyError, TypeError, ValueError, OSError, subprocess.SubprocessError) as error:
        print(f"bootstrap launch failed: {type(error).__name__}: {error}", file=sys.stderr)
        return "blocked_bootstrap_unverified"
    return _launch_bootstrap(cwd, enrollment, command, recheck, begin_attempt)


def _legacy_project_doc_warning(frame, cwd):
    """Recognize the exact pre-turn truncation diagnostic from old ACK-only seeds."""
    item = frame.get("item", {})
    if frame["type"] != "item.completed" or item.get("type") != "error":
        return False
    path = cwd / "AGENTS.md"
    if not path.is_file():
        return False
    size = path.stat().st_size
    if not 32768 < size <= _PROJECT_DOC_MAX_BYTES:
        return False
    return item.get("message") == (
        f"Loaded only 32768 of {size} bytes from `{path}` in environment `local` "
        "under the 32768-byte project instruction budget. Trim your project "
        "instructions to fit the budget. If you need to keep them all, "
        "increase `project_doc_max_bytes`."
    )


def _read_bootstrap_frames(cwd, attempt, age, pending):
    with _bootstrap_events(attempt["events_path"]) as stream:
        payload = stream.read(131073)
    if len(payload) > 131072:
        return _BOOTSTRAP_RECONCILE, None
    if not payload and age >= _BOOTSTRAP_RECEIPT_SECONDS:
        # A seed that never wrote a frame and holds no claim was never launched.
        try:
            with _managed_claim(_managed_claim_path(cwd)):
                return "bootstrap_abandoned", None
        except BlockingIOError:
            return _BOOTSTRAP_RECONCILE, None
    if not payload.endswith(b"\n"):
        return pending
    return "frames", [json.loads(line) for line in payload.splitlines()]


def inspect_codex_bootstrap(enrollment, identity, attempt, *, bind=None):
    """Verify one completed seed without sending any prompt or claiming delivery."""
    uncertain = (_BOOTSTRAP_RECONCILE, None)
    pending = uncertain
    if not callable(bind):
        return uncertain
    try:
        cwd, profile, _, prompt = _bootstrap_scope(enrollment, identity, "codex")
        age = time.time() - attempt["started_at"]
        if attempt["sha"] != identity[4] or not 0 <= age:
            return uncertain
        pending = ("bootstrap_pending", None) if age < _BOOTSTRAP_RECEIPT_SECONDS else uncertain
        state, frames = _read_bootstrap_frames(cwd, attempt, age, pending)
        if state != "frames":
            return state, frames
        kinds = [frame["type"] for frame in frames]
        if (kinds[:3] == ["thread.started", "item.completed", "turn.started"]
                and (_legacy_project_doc_warning(frames[1], cwd)
                     or _COMBINED_DOC_NOTICE.fullmatch(str(frames[1]["item"].get("message", ""))))):
            del frames[1]
            del kinds[1]
        # Codex reports a truncated skills list as one error item; the ACK below still decides.
        notices = [i for i, frame in enumerate(frames) if frame["type"] == "item.completed"
                   and frame["item"].get("type") == "error"
                   and _SKILLS_BUDGET_NOTICE.fullmatch(str(frame["item"].get("message", "")))]
        if len(notices) == 1:
            del frames[notices[0]]
            del kinds[notices[0]]
        if any(kind not in {"thread.started", "turn.started", "turn.completed",
                            "item.started", "item.updated", "item.completed"} for kind in kinds):
            return uncertain
        items = [frame["item"] for frame in frames if frame["type"].startswith("item.")]
        if any(item["type"] not in {"agent_message", "reasoning"} for item in items):
            return uncertain
        if kinds.count("thread.started") > 1 or kinds.count("turn.completed") > 1:
            return uncertain
        if "turn.completed" not in kinds:
            return pending
        if kinds[0] != "thread.started" or kinds[-1] != "turn.completed":
            return uncertain
        replies = [frame["item"]["text"] for frame in frames if frame["type"] == "item.completed"
                   and frame["item"]["type"] == "agent_message"]
        session = frames[0]["thread_id"]
        if replies != [_BOOTSTRAP_ACK] or str(UUID(session)) != session:
            return uncertain
        path, _ = _session(dict(enrollment, session=session), cwd)
        if path is None:
            return pending
        if not path.is_relative_to(profile / "sessions"):
            return uncertain
        info = path.stat()
        first = next(_rows(path, (info.st_ino, 0)), {})
        git = first.get("payload", {}).get("git", {}) if first.get("type") == "session_meta" else {}
        if git.get("commit_hash") != identity[4] or not _accepted(path, (info.st_ino, 0), "codex", prompt):
            return uncertain
        lock = profile / "thread-writer-locks" / f"{session}.lock"
        if not _verified_lock_dir(lock.parent):
            return uncertain
        with _managed_claim(_managed_claim_path(cwd)):
            if (not _terminal_state("codex", path)[0] or not _native_writer_free(lock)
                    or not _bootstrap_writer_free(cwd, enrollment, path)):
                return pending
            bind(session)
        return "bootstrapped", session
    except BlockingIOError:
        return pending
    except (AttributeError, KeyError, TypeError, ValueError, OSError, subprocess.SubprocessError):
        return uncertain


def inspect_agy_bootstrap(enrollment, identity, attempt, *, bind=None):
    """Verify one completed agy seed without sending any prompt or claiming delivery."""
    uncertain = (_BOOTSTRAP_RECONCILE, None)
    pending = uncertain
    if not callable(bind):
        return uncertain
    try:
        cwd, _, _, prompt = _bootstrap_scope(enrollment, identity, "agy")
        age = time.time() - attempt["started_at"]
        if attempt["sha"] != identity[4] or not 0 <= age:
            return uncertain
        pending = ("bootstrap_pending", None) if age < _BOOTSTRAP_RECEIPT_SECONDS else uncertain
        state, frames = _read_bootstrap_frames(cwd, attempt, age, pending)
        if state != "frames":
            return state, frames
        events = [frame["event"] for frame in frames]
        if any(ev not in {"init", "step_update", "result"} for ev in events):
            return uncertain
        if events.count("init") > 1 or events.count("result") > 1:
            return uncertain
        if "result" not in events:
            return pending
        if events[-1] != "result":
            return uncertain
        init_cid = None
        if events[0] == "init":
            init_cid = frames[0].get("conversation_id")
            init_cwd = (frames[0].get("init") or {}).get("cwd")
            if init_cwd and Path(init_cwd).resolve() != cwd:
                return uncertain
        for frame in frames:
            if frame["event"] == "step_update":
                step = frame["step_update"]
                if (step.get("step_type") not in {"user_input", "agent_response", "system_message", "thinking", "thought"}
                        or step.get("tool_calls")):
                    return uncertain
        result = frames[-1]["result"]
        session = result.get("conversation_id") or frames[-1].get("conversation_id")
        if (not isinstance(session, str) or str(UUID(session)) != session
                or (init_cid and init_cid != session)
                or result.get("status") != "SUCCESS"
                or (result.get("response") or "").strip() != _BOOTSTRAP_ACK):
            return uncertain
        path, env = _session(dict(enrollment, session=session), cwd)
        if path is None:
            return pending
        info = path.stat()
        if not _accepted(path, (info.st_ino, 0), "agy", prompt):
            return uncertain
        with _managed_claim(_managed_claim_path(cwd)):
            if (not _terminal_state("agy", path)[0] or not _agy_idle(env, session)
                    or not _bootstrap_writer_free(cwd, enrollment, path)):
                return pending
            bind(session)
        return "bootstrapped", session
    except BlockingIOError:
        return pending
    except (AttributeError, KeyError, TypeError, ValueError, OSError, subprocess.SubprocessError):
        return uncertain
