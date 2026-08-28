#!/opt/homebrew/bin/python3
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import typing
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

try:
    import numpy as np
    _NUMPY_AVAILABLE = True
except Exception:
    np = None  # type: ignore[assignment]
    _NUMPY_AVAILABLE = False

_USER_SCOPE = "$HOME/projects_other/user_scope/scripts"
try:
    import sys as _sys
    if _USER_SCOPE not in _sys.path:
        _sys.path.insert(0, _USER_SCOPE)
    from semantic_classifier import SemanticClassifier as _SemanticClassifier
    _SEMANTIC_CLASSIFIER_AVAILABLE = True
except Exception:
    _SemanticClassifier = None  # type: ignore[assignment, misc]
    _SEMANTIC_CLASSIFIER_AVAILABLE = False


HOME = Path(os.environ.get("HOME", "$HOME"))
CLI_PATH = os.pathsep.join(
    [
        str(HOME / ".local" / "bin"),
        "/opt/homebrew/bin",
        "/usr/local/bin",
        "/usr/bin",
        "/bin",
        "/usr/sbin",
        "/sbin",
    ]
)
LOG_FILE = Path(os.environ.get("LOG_FILE", "/tmp/cmux-codex-autoapprove.log"))
STATE_FILE = Path(os.environ.get("STATE_FILE", HOME / ".claude/supervisor/cmux-codex-launchd-state.json"))
LINES = int(os.environ.get("LINES", "80"))
TAIL_LINES = int(os.environ.get("TAIL_LINES", "20"))
CLASSIFY_TIMEOUT = int(os.environ.get("CLASSIFY_TIMEOUT", "30"))
ESCALATION_TIMEOUT = int(os.environ.get("ESCALATION_TIMEOUT", "30"))
CODEX_MODEL = os.environ.get("CODEX_MODEL", "")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "")
WORKSPACE_FILTER = os.environ.get("WORKSPACE_FILTER", "")
SURFACE_FILTER = os.environ.get("SURFACE_FILTER", "")
SURFACE_TITLE_FILTER = os.environ.get("SURFACE_TITLE_FILTER", "")
POLL_INTERVAL = float(os.environ.get("POLL_INTERVAL", "10"))
WORKER_POOL_SIZE = max(1, int(os.environ.get("WORKER_POOL_SIZE", "5")))
CMUX_SUBPROCESS_LIMIT = max(1, int(os.environ.get("CMUX_SUBPROCESS_LIMIT", "2")))
DAEMON_MODE = os.environ.get("DAEMON_MODE", "").lower() in {"1", "true", "yes"}
POST_APPROVE_WATCH_SECONDS = float(os.environ.get("POST_APPROVE_WATCH_SECONDS", "6"))
POST_APPROVE_POLL_SECONDS = float(os.environ.get("POST_APPROVE_POLL_SECONDS", "0.75"))
STUCK_COOLDOWN_SECONDS = float(os.environ.get("STUCK_COOLDOWN_SECONDS", "45"))
SEARCH_LINES = int(os.environ.get("SEARCH_LINES", "28"))
CANDIDATE_WINDOW_LINES = int(os.environ.get("CANDIDATE_WINDOW_LINES", "20"))
APPROVAL_BLOCK_MAX_LINES = int(os.environ.get("APPROVAL_BLOCK_MAX_LINES", "18"))
TRAINING_DATA_FILE = Path(os.environ.get(
    "TRAINING_DATA_FILE",
    HOME / ".claude" / "supervisor" / "autoapprove-training.jsonl",
))
TRAINING_MAX_BYTES = 50 * 1024 * 1024  # 50 MB — rotate when exceeded

LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

# Keep a persistent file handle open for the log to avoid open/close churn with
# high-frequency writes. Rotate when the file exceeds 50 MB.
_LOG_FH: typing.TextIO | None = None
_LOG_ROTATE_BYTES = 50 * 1024 * 1024

# Approve-option pattern: any numbered option containing approve/yes/allow keywords.
# Simpler and more permissive — just look for affirmative option text.
# Match common bullet/numbering variants and tolerate wrapped/colored prompt noise
# by normalizing control characters before matching.
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
OPTION_MENU_RE = re.compile(
    r"(?im)^(?:\s|\x1b\[[0-9;]*[A-Za-z])*(?P<marker>[›❯>→•▸◦-]|\*)?\s*"
    r"(?P<num>[1-9]\d*)[.)]\s*(?P<label>.+?)\s*$",
)
APPROVE_OPTION_RE = re.compile(
    r"(?im)^(?:\s|\x1b\[[0-9;]*[A-Za-z])*(?:[›❯>→•▸◦-]|\*)?\s*"  # prefix
    r"(\d+)[\.)]\s*"
    r"(?:approve|yes|allow|do it|run it|create it|accept)\b",
    re.IGNORECASE,
)
# Approve-all pattern: "approve everything" or "always allow" style options.
APPROVE_ALL_RE = re.compile(
    r"(?:approve everything|allow all|always approve|always allow access to|"
    r"always allow this\b|yes, and?\s+\w+\s+for all|"
    r"yes, .* and don't ask|yes, .* and never ask|"
    r"yes,\s*and\s+allow\s+claude\b.*\bsettings\b|"
    r"yes,\s*and\s+allow\s+.*\bsettings?\s+for\s+this\s+session)",
    re.IGNORECASE,
)
SHELL_PROMPT_RE = re.compile(r"[$%#>]$")
YN_APPROVE_RE = re.compile(
    r"\b(?:Do you want to\b|Would you like to\b|Want to\b|Proceed\?|Continue\?|May I\b|Shall I\b|Confirm\b)\b",
    re.IGNORECASE | re.MULTILINE,
)
YN_OPTION_RE = re.compile(
    r"(?im)"
    r"(?<![A-Za-z0-9])(?:"
    r"\[(?:y|Y)/(?:n|N)\]"
    r"|\([yY]\)[eE]s\s*/\s*\([nN]\)[oO]"
    r"|\([yY]\)\s*/\s*\([nN]\)"
    r"|\b[yY]\s*/\s*[nN](?=\s|$|[)\]])"
    r"|\byes\s*/\s*no(?=\s|$|[)\]])"
    r")",
    re.IGNORECASE | re.MULTILINE,
)


def _has_adjacent_yn_choice(normalized_text: str) -> bool:
    """Require a question phrase near a y/n choice line to avoid false positives.

    A line containing confirmation wording must be near a y/n token (or vice versa)
    before treating the screen as an interactive y/n prompt.
    """
    lines = [line.strip() for line in normalized_text.splitlines() if line.strip()]
    if not lines:
        return False

    for idx, line in enumerate(lines):
        if YN_APPROVE_RE.search(line):
            for option_line in lines[max(0, idx - 1) : min(len(lines), idx + 3)]:
                if YN_OPTION_RE.search(option_line):
                    return True
        if YN_OPTION_RE.search(line):
            for context_line in lines[max(0, idx - 2) : min(len(lines), idx + 2)]:
                if YN_APPROVE_RE.search(context_line):
                    return True
    return False


def _extract_option_menu_choices(normalized_text: str) -> list[tuple[int, str, int, bool]]:
    lines = [line.strip() for line in normalized_text.splitlines() if line.strip()]
    choices: list[tuple[int, str, int, bool]] = []
    for idx, line in enumerate(lines):
        m = OPTION_MENU_RE.match(line)
        if not m:
            continue
        try:
            num = int(m.group("num"))
        except (TypeError, ValueError):
            continue
        marker = (m.group("marker") or "").strip()
        choices.append((num, m.group("label").strip(), idx, bool(marker)))
    return choices


def _has_approval_option_menu(normalized_text: str) -> bool:
    """True when approval text includes an explicit numbered option menu."""
    choices = _extract_option_menu_choices(normalized_text)
    if len(choices) < 2:
        return False

    lines = [line.strip() for line in normalized_text.splitlines() if line.strip()]
    menu_indices = [idx for _, _, idx, _ in choices]

    for idx in menu_indices:
        context = lines[max(0, idx - 3) : min(len(lines), idx + 3)]
        if any(APPROVAL_BLOCK_ANCHOR_RE.search(context_line) for context_line in context):
            return True
        if any(YN_APPROVE_RE.search(context_line) for context_line in context):
            return True

    return any(
        OPTION_MENU_AFFIRMATIVE_RE.search(choice_label)
        or OPTION_MENU_YES_ALLOW_CLAUDE_RE.search(choice_label)
        for _, choice_label, _, _ in choices
    )
# Decision selector must appear as an explicit interactive choice line, not just
# a token buried in prose.
APPROVAL_CHOICE_LINE_RE = re.compile(
    r"(?im)^(?:\s|\x1b\[[0-9;]*[A-Za-z])*(?:[›❯>→•▸◦-]|\*|\-)?\s*"
    r"(?:"
    r"\d+[.)]\s*(?:approve|yes|allow|do it|run it|create it|accept|continue|proceed|delete|remove|apply|keep|skip|never|agree|no)\b"
    r"|"
    r"\[(?:y|Y)/(?:n|N)\]"
    r"|\([yY]\)[eE]s\s*/\s*\([nN]\)[oO]"
    r"|\([yY]\)\s*/\s*\([nN]\)"
    r"|\b[yY]\s*/\s*[nN](?=\s|$|[)\]])"
    r"|\byes\s*/\s*no(?=\s|$|[)\]])"
    r")",
    re.IGNORECASE | re.MULTILINE,
)

OPTION_MENU_AFFIRMATIVE_RE = re.compile(
    r"(?i)^(?:yes|approve|allow|continue|proceed|create|edit|write|apply|keep|remove|accept|confirm|start|deploy|install)\b",
)
OPTION_MENU_YES_ALLOW_CLAUDE_RE = re.compile(
    r"(?i)^(?:"
    r"yes,\s*and\s+allow\s+claude\b.*(?:settings|permissions|edit)\b"
    r"|allow\s+claude\sto\s+edit\b.*settings\b"
    r"|yes,\s*and\s+always\s+allow\s+.*\b(claude|settings|permissions)\b"
    r")",
)
OPTION_MENU_SESSION_ALLOW_ALL_RE = re.compile(
    r"(?i)^(?:yes,\s*)?(?:and\s+)?allow\s+all\b.*\b(?:during|for)\s+this\s+session\b",
)
OPTION_MENU_NEGATIVE_RE = re.compile(
    r"(?i)^(?:no|cancel|reject|decline|deny|abort|stop|skip|disconnect)\b",
)
# Second-round structural gate: confirms the surface is actually waiting for input.
# Uses generic numbered list detection instead of specific phrase matching.
INTERACTIVE_PROMPT_RE = re.compile(
    r"(?im)^(?:\s|\x1b\[[0-9;]*[A-Za-z])*[›❯>→•▸◦-]?\s*"
    r"1[.)]\s*"  # generic numbered option 1
    r"(?:Yes|Allow|Proceed|Continue|Do|Run|Create|Approve|OK|Go|Accept|Sure|Confirm|Okay|"
    r"No|Cancel|Disconnect|Remove|Delete|Stop|Decline|Reject|Never|Apply)\b"
    r"|\[y/N\]|\[Y/n\]"           # y/n prompt (bracket form)
    r"|\(y/n\)|\(Y/n\)"           # y/n prompt (paren form)
    r"|\by/n\b|\byes/no\b"        # y/n prompt (bare/spelled-out form)
    r"|\(y\)es.*\(n\)o"
    r"|enter to submit.{0,15}esc to cancel"   # Claude/Codex standard footer
    r"|esc to cancel.{0,20}enter to submit"   # reversed footer order
    r"|requires confirmation|requires confirmation for this tool|requires approval by policy|Hook PreToolUse"
    r"|Allow this command|Allow this operation|written up a plan and is ready|Do you want to delete\b|Do you want to create\b|Do you want to run\b|bypass permissions"
    r"|esc to cancel\s*[·|·]\s*tab to amend",  # Codex footer variant
    re.IGNORECASE | re.MULTILINE,
)
APPROVAL_BLOCK_ANCHOR_RE = re.compile(
    r"Tool call needs your approval|Would you like to\b"
    r"|Do you want to\b|Are you sure\b|requires confirmation|requires confirmation for this tool|requires approval by policy"
    r"|Allow this command|Allow this operation|written up a plan and is ready|Do you want to delete\b|Do you want to create\b|Do you want to run\b|bypass permissions"
    r"|Confirm\b"
    r"|Want to\b"
    r"|Proceed\?|Continue\?|May I|Shall I"
    r"|1\.\s*(?:Allow|Yes)"
    r"|2\.\s*(?:Cancel|No|Yes, and don't ask again)|enter to submit\s*\|\s*esc to cancel",
    re.IGNORECASE,
)
CMUX_SOCKET_DISCOVER_RE = re.compile(r"cmux.*\.sock$", re.IGNORECASE)


# --- SemanticClassifier candidate gate ---
# Uses SemanticClassifier from user_scope/scripts/semantic_classifier.py
# (same strategy as $PROJECT_ROOT/intent_classifier.py).
_APPROVAL_ANCHORS = {
    "approval": [
        "do you want to proceed?",
        "would you like to proceed?",
        "claude has written up a plan and is ready to execute",
        "do you want to create this?",
        "do you want to create this file?",
        "do you want to make this change?",
        "would you like to run the following command?",
        "tool call needs your approval",
        "allow this command?",
        "enter to submit esc to cancel",
        "esc to cancel enter to submit",
        "requires confirmation",
        "1. yes 2. yes and allow claude to edit 3. no",
        "yes and allow claude to edit settings for this session",
        "yes and don't ask again for this session",
        "approve this action 1. yes 2. no",
        "confirm would you like to allow",
        "confirm? [y/n]",
        "hook pretooluse",
        "do you want to delete this file?",
        "do you want to run this command?",
        "are you sure you want to proceed?",
        "1. yes 2. no",
        "1. allow 2. cancel",
        "1. proceed 2. cancel",
    ],
}
_EMBED_SIMILARITY_THRESHOLD = 0.72

_approval_clf = None
_approval_clf_failed = False
_clf_lock = threading.Lock()
_cmux_subprocess_sem = threading.BoundedSemaphore(CMUX_SUBPROCESS_LIMIT)


def _get_approval_classifier():
    global _approval_clf, _approval_clf_failed
    if _approval_clf is not None:
        return _approval_clf
    if _approval_clf_failed:
        return None
    with _clf_lock:
        if _approval_clf is not None:
            return _approval_clf
        if _approval_clf_failed:
            return None
        if not _SEMANTIC_CLASSIFIER_AVAILABLE:
            _approval_clf_failed = True
            return None
        try:
            clf = _SemanticClassifier(
                anchor_phrases=_APPROVAL_ANCHORS,
                default_label="SKIP",
                similarity_threshold=_EMBED_SIMILARITY_THRESHOLD,
            )
            clf.initialize_async()
            _approval_clf = clf
            log(f"EMBED_CLASSIFIER_INIT anchors={len(_APPROVAL_ANCHORS['approval'])}")
        except Exception as exc:
            _approval_clf_failed = True
            log(f"EMBED_CLASSIFIER_INIT_ERROR {exc}")
    return _approval_clf


def _semantic_observe(tail_text: str, structural_pass: bool) -> None:
    """Background: run semantic classifier, log divergences, save training data.

    Never blocks the caller.  The structural result is ground truth for now;
    the classifier is a trainee observed in parallel.
    """
    clf = _get_approval_classifier()
    if clf is None:
        return
    try:
        label, score = clf.predict(tail_text)
        semantic_pass = label == "approval"
        log(
            f"EMBED_SIM score={score:.3f} threshold={_EMBED_SIMILARITY_THRESHOLD}"
            f" semantic={semantic_pass} structural={structural_pass}"
        )
        if semantic_pass != structural_pass:
            snippet = tail_text.replace("\n", " | ")[:120]
            log(f"CLASSIFIER_DIVERGE structural={structural_pass} semantic={semantic_pass} snippet={snippet!r}")
        # Save every example (agreement + divergence) — both are useful for training.
        try:
            TRAINING_DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
            if TRAINING_DATA_FILE.exists() and TRAINING_DATA_FILE.stat().st_size > TRAINING_MAX_BYTES:
                try:
                    lines = TRAINING_DATA_FILE.read_text(encoding="utf-8", errors="ignore").splitlines()
                    keep = lines[-10000:]
                    TRAINING_DATA_FILE.write_text("\n".join(keep) + "\n", encoding="utf-8")
                    log(f"TRAINING_ROTATE kept last {len(keep)} of {len(lines)} lines")
                except Exception as rot_exc:
                    log(f"TRAINING_ROTATE_ERROR {rot_exc}")
            record = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "text": tail_text,
                "label": structural_pass,          # regexp ground truth
                "semantic_pass": semantic_pass,
                "semantic_score": round(score, 4),
                "diverge": semantic_pass != structural_pass,
            }
            with TRAINING_DATA_FILE.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as exc:
            log(f"TRAINING_WRITE_ERROR {exc}")
    except Exception as exc:
        log(f"EMBED_SIM_ERROR {exc}")


def _normalize_approval_text(tail_text: str) -> str:
    normalized = ANSI_ESCAPE_RE.sub("", tail_text)
    # Normalize odd spacing from wrapped/compact terminal output.
    normalized = normalized.replace("\r", "\n").replace("\u00a0", " ")
    normalized = re.sub(r"[ \t]+", " ", normalized)
    return normalized.strip()


def is_approval_candidate(tail_text: str) -> bool:
    """Approval detection: numbered approve/yes/allow option OR bare y/n confirmation phrase.

    Does not reject based on denial options — only checks for affirmative presence.
    Also matches "approve everything" style options.
    """
    normalized = _normalize_approval_text(tail_text)

    has_affirmative = bool(APPROVE_OPTION_RE.search(normalized))
    has_approve_all = bool(APPROVE_ALL_RE.search(normalized))
    has_yn = _has_adjacent_yn_choice(normalized)
    has_menu = _has_approval_option_menu(normalized)

    # Run semantic observer in background for training data collection
    threading.Thread(
        target=_semantic_observe,
        args=(tail_text, has_affirmative or has_approve_all or has_yn or has_menu),
        daemon=True,
        name="semantic-observe",
    ).start()

    return has_affirmative or has_approve_all or has_yn or has_menu


def log(message: str) -> None:
    global _LOG_FH
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"[{timestamp}] {message}\n"
    try:
        if _LOG_FH is None:
            _LOG_FH = LOG_FILE.open("a", encoding="utf-8")
        # Rotate if over size limit
        if _LOG_FH.tell() > _LOG_ROTATE_BYTES:
            _LOG_FH.close()
            # Archive: rename old log with timestamp
            archive_path = LOG_FILE.parent / f"cmux-codex-launchd.{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}.log"
            LOG_FILE.rename(archive_path)
            _LOG_FH = LOG_FILE.open("w", encoding="utf-8")
        _LOG_FH.write(line)
        _LOG_FH.flush()
    except Exception:
        # Fallback: one-shot write if persistent handle fails
        try:
            with LOG_FILE.open("a", encoding="utf-8") as fh:
                fh.write(line)
        except Exception:
            pass


def load_state() -> dict[str, dict[str, float | str]]:
    if not STATE_FILE.exists():
        return {}
    try:
        raw = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    state: dict[str, dict[str, float | str]] = {}
    if not isinstance(raw, dict):
        return state
    for key, value in raw.items():
        if isinstance(value, str):
            state[key] = {"digest": value, "cooldown_until": 0.0, "last_decision": ""}
        elif isinstance(value, dict):
            digest = value.get("digest", "")
            cooldown_until = value.get("cooldown_until", 0.0)
            last_decision = value.get("last_decision", "")
            if isinstance(digest, str):
                try:
                    cooldown = float(cooldown_until)
                except (TypeError, ValueError):
                    cooldown = 0.0
                state[key] = {
                    "digest": digest,
                    "cooldown_until": cooldown,
                    "last_decision": last_decision if isinstance(last_decision, str) else "",
                }
    return state


def save_state(state: dict[str, dict[str, float | str]]) -> None:
    STATE_FILE.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
    env = kwargs.pop("env", None)
    return subprocess.run(cmd, text=True, capture_output=True, env=env, **kwargs)


def run_cmux(
    cmd: list[str],
    socket_path: str | None = None,
    **kwargs,
) -> subprocess.CompletedProcess[str]:
    env = kwargs.pop("env", None)
    run_env = dict(os.environ)
    if env:
        run_env.update(env)
    if socket_path:
        run_env["CMUX_SOCKET_PATH"] = socket_path
    else:
        run_env.pop("CMUX_SOCKET_PATH", None)
    with _cmux_subprocess_sem:
        return run(cmd, env=run_env, **kwargs)


def discover_cmux_sockets() -> list[str]:
    configured = os.environ.get("CMUX_SOCKET_PATH", "").strip()
    candidates: list[str] = []
    seen: set[str] = set()

    def _add(path: str) -> None:
        expanded = os.path.expanduser(path)
        if not expanded:
            return
        try:
            resolved = str(Path(expanded).resolve())
        except OSError:
            resolved = expanded
        if resolved in seen:
            return
        if not Path(expanded).exists():
            return
        seen.add(resolved)
        candidates.append(expanded)

    if configured:
        _add(configured)
    for base in (
        "/tmp",
        "/private/tmp",
        str(HOME / "Library/Application Support/cmux"),
    ):
        base_path = Path(base)
        if not base_path.is_dir():
            continue
        try:
            for candidate in base_path.glob("cmux*.sock"):
                if not CMUX_SOCKET_DISCOVER_RE.search(candidate.name):
                    continue
                try:
                    if candidate.is_socket():
                        _add(str(candidate))
                    else:
                        _add(str(candidate))
                except OSError:
                    _add(str(candidate))
        except OSError:
            continue

    if not candidates:
        candidates.append("")
    log(f"CMUX_SOCKETS discovered={candidates}")
    return candidates


def _rows_from_cmux_tree(data: dict[str, typing.Any], socket_path: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for window in data.get("windows", []):
        for workspace in window.get("workspaces", []):
            for pane in workspace.get("panes", []):
                for surface in pane.get("surfaces", []):
                    if surface.get("type") != "terminal":
                        continue
                    rows.append(
                        {
                            "socket": socket_path,
                            "workspace": workspace.get("ref", ""),
                            "title": workspace.get("title", ""),
                            "surface": surface.get("ref", ""),
                            "surface_title": surface.get("title", ""),
                        }
                    )
    return rows


def find_cli(name: str) -> str | None:
    return shutil.which(name, path=CLI_PATH)


def cmux_tree() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for socket_path in discover_cmux_sockets():
        data: dict[str, typing.Any] | None = None
        # --all enumerates ALL surfaces across ALL workspaces but can time out with many
        # surfaces open. Fall back to focused-window-only tree when that happens.
        try:
            proc = run_cmux(["cmux", "--json", "tree", "--all"], socket_path=socket_path, check=True, timeout=5)
            data = json.loads(proc.stdout)
        except subprocess.TimeoutExpired:
            # Fallback: enumerate only the focused window's workspaces.
            # This is much faster and still catches most active terminals.
            log(f"CMUX_TREE_TIMEOUT socket={socket_path or '(default)'} falling back to focused-window tree")
            try:
                proc = run_cmux(["cmux", "--json", "tree"], socket_path=socket_path, check=True, timeout=3)
                data = json.loads(proc.stdout)
            except subprocess.TimeoutExpired:
                log(f"CMUX_TREE_FALLBACK_TIMEOUT socket={socket_path or '(default)'} cannot enumerate surfaces")
                continue
        except subprocess.CalledProcessError as exc:
            # cmux returns exit 1 when the socket is not ready or it is not fully running.
            # Fall back to focused-window tree rather than crashing the daemon.
            log(
                f"CMUX_TREE_CALLED_PROCESS_ERROR socket={socket_path or '(default)'} "
                f"exit={exc.returncode} falling back to focused-window tree"
            )
            try:
                proc = run_cmux(["cmux", "--json", "tree"], socket_path=socket_path, check=True, timeout=3)
                data = json.loads(proc.stdout)
            except subprocess.TimeoutExpired:
                log(f"CMUX_TREE_FALLBACK_TIMEOUT socket={socket_path or '(default)'} cannot enumerate surfaces")
                continue
            except subprocess.CalledProcessError:
                log(f"CMUX_TREE_FALLBACK_CALLED_PROCESS_ERROR socket={socket_path or '(default)'} cannot enumerate surfaces")
                continue
            except OSError as fallback_exc:
                log(f"CMUX_TREE_FALLBACK_OS_ERROR socket={socket_path or '(default)'} error={fallback_exc}")
                continue
        except OSError as exc:
            log(f"CMUX_TREE_OS_ERROR socket={socket_path or '(default)'} error={exc}")
            continue
        if data is None:
            continue
        rows.extend(_rows_from_cmux_tree(data, socket_path))

    deduped_rows: list[dict[str, str]] = []
    seen_keys: set[tuple[str, str, str]] = set()
    for row in rows:
        dedupe_key = (row["socket"], row["workspace"], row["surface"])
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)
        deduped_rows.append(row)
    if rows:
        log(
            f"CMUX_TREE socket_rows={len(rows)} unique_rows={len(deduped_rows)} "
            f"sockets={len({row['socket'] for row in rows})}"
        )
    return deduped_rows


def matches_filter(value: str, flt: str) -> bool:
    return not flt or flt in value


def read_screen(workspace: str, surface: str, socket_path: str | None = None) -> str:
    # Retry on timeout — transient cmux busyness shouldn't cause us to skip a surface.
    for attempt in range(3):
        try:
            proc = run_cmux(
                ["cmux", "read-screen", "--workspace", workspace, "--surface", surface, "--lines", str(LINES)],
                socket_path=socket_path,
                timeout=3,
            )
            return proc.stdout
        except subprocess.TimeoutExpired:
            if attempt < 2:
                time.sleep(0.5)  # brief pause before retry
                continue
            log(f"READ_TIMEOUT socket={socket_path or '(default)'} workspace={workspace} surface={surface}")
            return ""
        except OSError as exc:
            log(f"READ_OS_ERROR socket={socket_path or '(default)'} workspace={workspace} surface={surface} error={exc}")
            return ""
    return ""


def is_idle_prompt(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if re.match(r"^❯\s*(?:1\.|Yes\b)", stripped):
        return False
    if stripped in {"❯", ">", ">>"}:
        return True
    return bool(SHELL_PROMPT_RE.search(stripped))


def extract_candidate_tail(screen: str) -> str:
    lines = [line.rstrip() for line in screen.splitlines()]
    non_empty = [line for line in lines if line.strip()]
    if not non_empty:
        return ""

    if is_idle_prompt(non_empty[-1]):
        return ""

    region = lines[-SEARCH_LINES:]
    last_nonempty_index = -1
    for index, line in enumerate(region):
        if line.strip():
            last_nonempty_index = index

    anchor_index = -1
    for index, line in enumerate(region):
        if APPROVAL_BLOCK_ANCHOR_RE.search(line):
            anchor_index = index

    if anchor_index >= 0 and anchor_index == last_nonempty_index:
        start = anchor_index
        while start > 0 and region[start - 1].strip():
            start -= 1
        start = max(start, anchor_index - APPROVAL_BLOCK_MAX_LINES + 1)
        block_lines = region[start : anchor_index + 1]
        block_text = "\n".join(line for line in block_lines if line.strip())
        if is_approval_candidate(block_text):
            return block_text

    # Secondary anchor path: anchor is near the bottom (Claude Code TUI has input box BELOW
    # the dialog, so anchor_index != last_nonempty_index). When the anchor is within
    # CANDIDATE_WINDOW_LINES of the bottom AND the block passes structural, return it.
    if anchor_index >= 0 and (last_nonempty_index - anchor_index) < CANDIDATE_WINDOW_LINES:
        block_start = max(0, anchor_index - 3)  # include a few lines above for question context
        block_lines = region[block_start : last_nonempty_index + 1]
        block_text = "\n".join(line for line in block_lines if line.strip())
        if is_approval_candidate(block_text):
            return block_text

    latest_match = ""
    for start in range(len(region)):
        max_end = min(len(region), start + CANDIDATE_WINDOW_LINES)
        for end in range(max_end, start + 1, -1):
            if end - 1 != last_nonempty_index:
                continue
            window_lines = region[start:end]
            window_text = "\n".join(line for line in window_lines if line.strip())
            if not window_text:
                continue
            if is_approval_candidate(window_text):
                latest_match = window_text
                break
    return latest_match


def heuristic_decision(tail_text: str) -> str:
    """Simple heuristic: if we see an approve/yes option, return the key to press.

    Takes the FIRST matching numbered approval option (numerically lowest) to avoid
    picking "Yes, and don't ask again" / "always approve" style options that have
    persistent side-effects. Falls back to "y" for bare y/n prompts. Never rejects —
    only approves.
    """
    normalized = _normalize_approval_text(tail_text)

    menu_choices = _extract_option_menu_choices(normalized)

    # If an affirmative option is explicitly selected in the dialog, pressing
    # Enter is the fastest/most reliable interaction.
    selected_affirmative = [
        num for num, choice_label, _, is_selected in menu_choices if is_selected
        and (
            OPTION_MENU_AFFIRMATIVE_RE.search(choice_label)
            or OPTION_MENU_YES_ALLOW_CLAUDE_RE.search(choice_label)
        )
        and num == 1
        and not OPTION_MENU_NEGATIVE_RE.search(choice_label)
        and not OPTION_MENU_SESSION_ALLOW_ALL_RE.search(choice_label)
    ]
    if selected_affirmative:
        # The visible selected option in this UI uses Enter to confirm.
        return "ENTER"

    if len(menu_choices) >= 2:
        session_allow_all = sorted(
            (
                num for num, choice_label, _, _ in menu_choices
                if OPTION_MENU_SESSION_ALLOW_ALL_RE.search(choice_label)
            ),
            key=int,
        )
        if session_allow_all:
            return str(session_allow_all[0])

    matches = list(APPROVE_OPTION_RE.finditer(normalized))
    if matches:
        # Extract the numeric key from each match and return the lowest one.
        # This avoids picking "3. Yes, and don't ask again" over "1. Yes".
        digits = [re.search(r'\d+', m.group()) for m in matches]
        keys = [int(d.group()) for d in digits if d]
        if keys:
            return str(min(keys))

    if len(menu_choices) >= 2 and _has_approval_option_menu(normalized):
        sorted_choices = sorted(
            (num for num, choice_label, _, _ in menu_choices if not OPTION_MENU_NEGATIVE_RE.search(choice_label)),
            key=int,
        )
        if sorted_choices:
            return str(sorted_choices[0])
        return str(min(num for num, _, _, _ in menu_choices))

    # y/n prompt → send "y" only when a y/n token is present
    if _has_adjacent_yn_choice(normalized):
        return "y"
    return ""


def extract_decision_token(text: str) -> str:
    for token in text.split():
        if token in {"ENTER", "1", "y", "SKIP", "DENY"}:
            return token
    return "SKIP"


def classify_with_codex(
    prompt_path: str,
    out_path: str,
    exec_log_path: str,
    env: dict[str, str],
    timeout_seconds: int,
) -> str:
    codex_bin = find_cli("codex")
    if not codex_bin:
        raise FileNotFoundError("codex")
    cmd = [
        "/opt/homebrew/bin/timeout",
        str(timeout_seconds),
        codex_bin,
        "exec",
        "--skip-git-repo-check",
        "--ephemeral",
        "-s",
        "read-only",
        "--color",
        "never",
    ]
    if CODEX_MODEL:
        cmd.extend(["-m", CODEX_MODEL])
    cmd.extend(["-o", out_path, "-"])

    with open(prompt_path, "r", encoding="utf-8") as prompt_in, open(exec_log_path, "w", encoding="utf-8") as exec_log:
        subprocess.run(
            cmd,
            stdin=prompt_in,
            stdout=exec_log,
            stderr=subprocess.STDOUT,
            env=env,
            timeout=timeout_seconds + 2,
            check=True,
        )
    out_text = Path(out_path).read_text(encoding="utf-8").strip()
    return extract_decision_token(out_text)


def classify_with_claude(
    prompt_path: str,
    exec_log_path: str,
    env: dict[str, str],
    timeout_seconds: int,
) -> str:
    claude_bin = find_cli("claude")
    if not claude_bin:
        raise FileNotFoundError("claude")
    cmd = [
        "/opt/homebrew/bin/timeout",
        str(timeout_seconds),
        claude_bin,
        "--disable-slash-commands",
        "-p",
        "--output-format",
        "text",
        "--permission-mode",
        "dontAsk",
        "--tools",
        "",
    ]
    if CLAUDE_MODEL:
        cmd.extend(["--model", CLAUDE_MODEL])

    with open(prompt_path, "r", encoding="utf-8") as prompt_in, open(exec_log_path, "w+", encoding="utf-8") as exec_log:
        subprocess.run(
            cmd,
            stdin=prompt_in,
            stdout=exec_log,
            stderr=subprocess.STDOUT,
            env=env,
            timeout=timeout_seconds + 2,
            check=True,
        )
        exec_log.seek(0)
        return extract_decision_token(exec_log.read().strip())


def classify_tail(
    workspace: str,
    title: str,
    surface: str,
    surface_title: str,
    tail_text: str,
    extra_context: str = "",
    timeout_seconds: int | None = None,
) -> str:
    effective_timeout = timeout_seconds or CLASSIFY_TIMEOUT
    prompt = f"""You are classifying a live cmux terminal screen for an approval bot.

Return exactly one token from this set:
ENTER
1
y
SKIP
DENY

Decision rules:
- Return ENTER when the screen is an approval dialog and the affirmative choice is already highlighted or selected.
- Return 1 when the screen is an approval dialog with a numbered affirmative option but Enter is not clearly the right key.
- Return y when the screen expects a y/n style approval.
- Return DENY only for clearly dangerous or destructive requests.
- Return SKIP if this is not an approval dialog or if you are unsure.
- Do not explain.

Context:
workspace_ref: {workspace}
workspace_title: {title}
surface_ref: {surface}
surface_title: {surface_title}

{extra_context}

Screen:
{tail_text}
"""

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as prompt_fh, \
        tempfile.NamedTemporaryFile("w+", encoding="utf-8", delete=False) as out_fh, \
        tempfile.NamedTemporaryFile("w+", encoding="utf-8", delete=False) as log_fh:
        prompt_fh.write(prompt)
        prompt_path = prompt_fh.name
        out_path = out_fh.name
        exec_log_path = log_fh.name

    try:
        env = {
            "HOME": str(HOME),
            "PATH": CLI_PATH,
            "SSH_AUTH_SOCK": os.environ.get("SSH_AUTH_SOCK", ""),
        }
        if CODEX_MODEL:
            env["CODEX_MODEL"] = CODEX_MODEL
        if CLAUDE_MODEL:
            env["CLAUDE_MODEL"] = CLAUDE_MODEL

        providers: list[tuple[str, Callable[[], str]]] = []

        codex_bin = find_cli("codex")
        if codex_bin:
            codex_login_status = ""
            try:
                status_proc = subprocess.run(
                    [codex_bin, "login", "status"],
                    text=True,
                    capture_output=True,
                    env=env,
                    timeout=5,
                    check=False,
                )
                codex_login_status = (status_proc.stdout or "") + "\n" + (status_proc.stderr or "")
            except Exception:
                codex_login_status = ""

            # Hard guard: never use codex classification when API-key auth is active.
            if "api key" in codex_login_status.lower():
                log(f"CLASSIFY_UNAVAILABLE workspace={workspace} surface={surface} provider=codex reason=api_key_auth_disabled")
            else:
                providers.append(
                    ("codex", lambda: classify_with_codex(prompt_path, out_path, exec_log_path, env, effective_timeout))
                )
        if find_cli("claude"):
            providers.append(
                ("claude", lambda: classify_with_claude(prompt_path, exec_log_path, env, effective_timeout))
            )
        if not providers:
            log(f"CLASSIFY_UNAVAILABLE workspace={workspace} surface={surface} providers=none")
            return "SKIP"

        for provider_name, provider in providers:
            try:
                decision = provider()
                log(f"CLASSIFY_PROVIDER workspace={workspace} surface={surface} provider={provider_name}")
                return decision
            except FileNotFoundError:
                log(f"CLASSIFY_UNAVAILABLE workspace={workspace} surface={surface} provider={provider_name}")
                continue
            except subprocess.TimeoutExpired:
                log(f"CLASSIFY_TIMEOUT workspace={workspace} surface={surface} provider={provider_name}")
                return "SKIP"
            except subprocess.CalledProcessError as exc:
                exec_log = Path(exec_log_path).read_text(encoding="utf-8", errors="ignore")
                exec_log_lower = exec_log.lower()
                if exc.returncode == 127 or "command not found" in exec_log.lower():
                    log(f"CLASSIFY_UNAVAILABLE workspace={workspace} surface={surface} provider={provider_name} exit={exc.returncode}")
                    continue
                # Codex auth failures can show up as "not logged in" or HTTP 401 variants.
                if (
                    "not logged in" in exec_log_lower
                    or "401 unauthorized" in exec_log_lower
                    or "missing bearer" in exec_log_lower
                    or "invalid access token" in exec_log_lower
                ):
                    log(f"CLASSIFY_UNAVAILABLE workspace={workspace} surface={surface} provider={provider_name} reason=not_logged_in")
                    continue
                if "rate_limit_error" in exec_log_lower or "rate limit" in exec_log_lower:
                    log(f"CLASSIFY_RATE_LIMIT workspace={workspace} surface={surface} provider={provider_name}")
                    return "SKIP"
                log(f"CLASSIFY_ERROR workspace={workspace} surface={surface} provider={provider_name} exit={exc.returncode}")
                return "SKIP"

        return "SKIP"
    finally:
        for path in (prompt_path, out_path, exec_log_path):
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass


def approve(
    socket_path: str,
    workspace: str,
    surface: str,
    decision: str,
) -> None:
    try:
        if decision == "ENTER":
            run_cmux(
                ["cmux", "send-key", "--workspace", workspace, "--surface", surface, "Enter"],
                socket_path=socket_path,
                timeout=3,
                check=True,
            )
        elif decision == "1":
            run_cmux(
                ["cmux", "send", "--workspace", workspace, "--surface", surface, "1"],
                socket_path=socket_path,
                timeout=3,
                check=True,
            )
        elif decision == "y":
            run_cmux(
                ["cmux", "send", "--workspace", workspace, "--surface", surface, "y"],
                socket_path=socket_path,
                timeout=3,
                check=True,
            )
        else:
            # Fallback: send the decision value as-is (handles numeric keys like "2", "8", etc.)
            run_cmux(
                ["cmux", "send", "--workspace", workspace, "--surface", surface, decision],
                socket_path=socket_path,
                timeout=3,
                check=True,
            )
        log(
            f"APPROVE_SENT socket={socket_path or '(default)'} "
            f"workspace={workspace} surface={surface} decision={decision}"
        )
    except subprocess.TimeoutExpired:
        log(
            f"APPROVE_TIMEOUT socket={socket_path or '(default)'} "
            f"workspace={workspace} surface={surface} decision={decision}"
        )
    except OSError as exc:
        log(
            f"APPROVE_OS_ERROR socket={socket_path or '(default)'} "
            f"workspace={workspace} surface={surface} decision={decision} error={exc}"
        )


def digest_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def monitor_after_approve(
    workspace: str,
    title: str,
    surface: str,
    surface_title: str,
    prior_tail_text: str,
    prior_decision: str,
    socket_path: str,
) -> tuple[str, float]:
    deadline = time.time() + POST_APPROVE_WATCH_SECONDS
    prior_digest = digest_text(prior_tail_text)
    latest_tail = prior_tail_text
    latest_digest = prior_digest

    while time.time() < deadline:
        time.sleep(POST_APPROVE_POLL_SECONDS)
        screen = read_screen(workspace, surface, socket_path)
        if not screen:
            log(
                f"POST_APPROVE_PROGRESS socket={socket_path or '(default)'} "
                f"workspace={workspace} surface={surface} status=screen_unreadable"
            )
            return "", 0.0

        latest_tail = extract_candidate_tail(screen)
        if not latest_tail:
            log(
                f"POST_APPROVE_PROGRESS socket={socket_path or '(default)'} "
                f"workspace={workspace} surface={surface} status=prompt_cleared"
            )
            return "", 0.0

        latest_digest = digest_text(latest_tail)
        if latest_digest != prior_digest:
            log(
                f"POST_APPROVE_PROGRESS socket={socket_path or '(default)'} "
                f"workspace={workspace} surface={surface} status=prompt_changed"
            )
            return latest_tail, 0.0

    log(
        f"POST_APPROVE_STUCK socket={socket_path or '(default)'} workspace={workspace} surface={surface} "
        f"previous_decision={prior_decision}"
    )
    followup_decision = classify_tail(
        workspace,
        title,
        surface,
        surface_title,
        latest_tail,
        extra_context=(
            "Important follow-up context:\n"
            f"- The bot already sent: {prior_decision}\n"
            "- The terminal did not continue after that action.\n"
            "- Choose the next key to try, or SKIP if human attention is required.\n"
        ),
        timeout_seconds=ESCALATION_TIMEOUT,
    )
    log(
        f"POST_APPROVE_ESCALATION socket={socket_path or '(default)'} "
        f"workspace={workspace} surface={surface} decision={followup_decision}"
    )
    if followup_decision in {"ENTER", "1", "y"} and followup_decision != prior_decision:
        approve(socket_path, workspace, surface, followup_decision)
        return latest_tail, time.time() + STUCK_COOLDOWN_SECONDS

    return latest_tail, time.time() + STUCK_COOLDOWN_SECONDS


def process_surface(
    row: dict[str, str],
    state_entry: dict[str, float | str],
    now: float,
) -> tuple[str, dict[str, float | str] | None]:
    socket_path = row["socket"]
    state_key = f'{socket_path}:{row["workspace"]}:{row["surface"]}'

    screen = read_screen(row["workspace"], row["surface"], socket_path)
    if not screen:
        log(
            f'SCREEN_EMPTY socket={socket_path or "(default)"} '
            f'workspace={row["workspace"]} surface={row["surface"]}'
        )
        return state_key, None

    # Strip ANSI before candidate extraction so ❯ cursor patterns match correctly.
    screen = re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', screen)

    tail_text = extract_candidate_tail(screen)
    if not tail_text:
        log(
            f'TAIL_EMPTY socket={socket_path or "(default)"} '
            f'workspace={row["workspace"]} surface={row["surface"]} screen_snippet={screen[:80]!r}'
        )
        return state_key, None

    digest = digest_text(tail_text)
    cooldown_until = float(state_entry.get("cooldown_until", 0.0) or 0.0)
    last_decision = str(state_entry.get("last_decision", "") or "")
    if state_entry.get("digest") == digest and cooldown_until > now:
        return state_key, {
            "digest": str(state_entry.get("digest", "")),
            "cooldown_until": cooldown_until,
            "last_decision": last_decision,
        }

    log(
        f'CANDIDATE socket={socket_path or "(default)"} workspace={row["workspace"]} title={row["title"]} '
        f'surface={row["surface"]} surface_title={row["surface_title"]}'
    )
    decision = heuristic_decision(tail_text)
    if decision:
        log(
            f'HEURISTIC socket={socket_path or "(default)"} '
            f'workspace={row["workspace"]} surface={row["surface"]} decision={decision}'
        )
    else:
        # Heuristic missed — re-read the screen once before calling the slow classifier.
        # The dialog may have been mid-transition when first captured.
        re_read = read_screen(row["workspace"], row["surface"], socket_path)
        if re_read:
            re_read = re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', re_read)
            re_tail = extract_candidate_tail(re_read)
            if re_tail and re_tail != tail_text:
                decision = heuristic_decision(re_tail)
                if decision:
                    log(
                        f'HEURISTIC_REREAD socket={socket_path or "(default)"} '
                        f'workspace={row["workspace"]} surface={row["surface"]} decision={decision}'
                    )
                    tail_text = re_tail
        if not decision:
            # Still empty after re-read — call the classifier as last resort.
            log(
                f'HEURISTIC_FALLBACK socket={socket_path or "(default)"} '
                f'workspace={row["workspace"]} surface={row["surface"]} calling_classifier'
            )
            decision = classify_tail(
                row["workspace"],
                row["title"],
                row["surface"],
                row["surface_title"],
                tail_text,
            )
            log(
                f'CLASSIFIER_RESULT socket={socket_path or "(default)"} '
                f'workspace={row["workspace"]} surface={row["surface"]} decision={decision}'
            )
    log(
        f'DECISION socket={socket_path or "(default)"} workspace={row["workspace"]} surface={row["surface"]} decision={decision}'
    )
    if decision in {"ENTER", "1", "y"} or decision.isdigit():
        # Skip if same decision was already sent for this surface (within cooldown window)
        if last_decision == decision and cooldown_until > now:
            log(
                f'DECISION_SKIPPED_SAME socket={socket_path or "(default)"} '
                f'workspace={row["workspace"]} surface={row["surface"]} decision={decision} prior_sent_within_cooldown'
            )
            return state_key, {
                "digest": digest,
                "cooldown_until": cooldown_until,
                "last_decision": decision,
            }
        approve(socket_path, row["workspace"], row["surface"], decision)
        watched_tail, updated_cooldown_until = monitor_after_approve(
            row["workspace"],
            row["title"],
            row["surface"],
            row["surface_title"],
            tail_text,
            decision,
            socket_path,
        )
        return state_key, {
            "digest": digest_text(watched_tail) if watched_tail else digest,
            "cooldown_until": updated_cooldown_until,
            "last_decision": decision,
        }

    return state_key, {
        "digest": digest,
        "cooldown_until": time.time() + STUCK_COOLDOWN_SECONDS,
        "last_decision": last_decision,
    }


def run_scan() -> int:
    log(
        "cmux-codex-launchd-python start "
        f"lines={LINES} tail_lines={TAIL_LINES} timeout={CLASSIFY_TIMEOUT}s "
        f"model={CODEX_MODEL or 'default'} workspace_filter={WORKSPACE_FILTER or '*'} "
        f"surface_filter={SURFACE_FILTER or '*'} surface_title_filter={SURFACE_TITLE_FILTER or '*'} "
        f"workers={WORKER_POOL_SIZE} escalation_timeout={ESCALATION_TIMEOUT}s"
    )
    state = load_state()
    now = time.time()
    rows = cmux_tree()
    sockets = sorted({row["socket"] for row in rows})
    log(
        f"CMUX_SCAN_ROWS rows={len(rows)} sockets={len(sockets)} "
        f"socket_names={','.join([Path(s).name or 'default' for s in sockets])}"
    )
    rows_to_process: list[tuple[dict[str, str], dict[str, float | str]]] = []
    for row in rows:
        state_key = f'{row["socket"]}:{row["workspace"]}:{row["surface"]}'
        if not (matches_filter(row["workspace"], WORKSPACE_FILTER) or matches_filter(row["title"], WORKSPACE_FILTER)):
            continue
        if not matches_filter(row["surface"], SURFACE_FILTER):
            continue
        if not matches_filter(row["surface_title"], SURFACE_TITLE_FILTER):
            continue
        rows_to_process.append((row, state.get(state_key, {"digest": "", "cooldown_until": 0.0})))

    next_state: dict[str, dict[str, float | str]] = {}
    with ThreadPoolExecutor(max_workers=min(WORKER_POOL_SIZE, max(1, len(rows_to_process)))) as executor:
        futures = [executor.submit(process_surface, row, state_entry, now) for row, state_entry in rows_to_process]
        for future in as_completed(futures):
            try:
                state_key, state_update = future.result()
            except Exception as exc:
                log(f"PROCESS_SURFACE_ERROR type={type(exc).__name__} detail={exc}")
                continue
            if state_update is not None:
                next_state[state_key] = state_update

    save_state(next_state)
    return 0


def main() -> int:
    if not DAEMON_MODE:
        return run_scan()

    log(
        "cmux-codex-launchd-python daemon "
        f"poll_interval={POLL_INTERVAL}s"
    )
    while True:
        try:
            run_scan()
        except Exception as exc:
            log(f"LOOP_ERROR type={type(exc).__name__} detail={exc}")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    raise SystemExit(main())
