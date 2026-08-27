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

LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

CANDIDATE_RE = re.compile(
    r"Hook PreToolUse:|requires confirmation for this tool|Do you want to\b"
    r"|Would you like to\b"
    r"|requires approval by policy|Allow this command|Allow this operation"
    r"|Tool call needs your approval|enter to submit \| esc to cancel"
    r"|written up a plan and is ready"
    r"|Are you sure\b|Proceed with this action\b|Do you want to delete\b"
    r"|Do you want to create\b|Do you want to run\b"
)
BOTTOM_APPROVAL_RE = re.compile(
    r"Do you want to\b|Would you like to run the following command\?"
    r"|Esc to cancel|Tab to amend|requires confirmation|Tool call needs your approval"
    r"|enter to submit \| esc to cancel|Are you sure\b"
)
SHELL_PROMPT_RE = re.compile(r"[$%#>]$")
NUMBERED_ALLOW_RE = re.compile(r"^[^\S\r\n]*(?:[›❯>→•][^\S\r\n]*)?1\.\s*(?:Allow|Yes|Proceed|Continue|Apply|Run)\b", re.IGNORECASE | re.MULTILINE)
NUMBERED_CANCEL_RE = re.compile(r"^[^\S\r\n]*2\.\s*(?:Cancel|No|Yes, and don't ask again)\b", re.IGNORECASE | re.MULTILINE)
# 3-option Codex dialog: 1=Yes  2=Yes allow all (session)  3=No
THREE_OPTION_CODEX_RE = re.compile(r"2\.\s*Yes,\s*allow\s+all\b.*?3\.\s*No\b", re.IGNORECASE | re.DOTALL)
YN_APPROVE_RE = re.compile(r"\b(?:\[y/N\]|\[Y/n\]|y/n|yes/no)\b", re.IGNORECASE)
OPTION1_Y_RE = re.compile(r"^[^\S\r\n]*(?:[›❯>][^\S\r\n]*)?1\.\s*Yes,?\s*proceed\s*\(y\)", re.IGNORECASE | re.MULTILINE)
SELECTED_OPTION_1_RE = re.compile(r"^[^\S\r\n]*[›❯>→•][^\S\r\n]*1\.", re.MULTILINE)
# cursor on option 2 that is also affirmative (e.g. "❯ 2. Yes, and allow Claude to edit...")
OPT2_AFFIRMATIVE_RE = re.compile(r"^[^\S\r\n]*[›❯>→•][^\S\r\n]*2\.\s*(?:Yes|Allow)\b", re.IGNORECASE | re.MULTILINE)
ENTER_SUBMIT_RE = re.compile(r"enter to submit\s*\|\s*esc to cancel", re.IGNORECASE)
# Second-round structural gate: confirms the surface is actually waiting for input,
# not just agent output that mentions approval-like phrases.
INTERACTIVE_PROMPT_RE = re.compile(
    r"(?:[›❯>→•]\s*1\.)"         # cursor on option 1 (multiple cursor symbols)
    r"|(?:[›❯>→•]\s*2\.\s*(?:Yes|Allow))"  # cursor on affirmative option 2
    r"|\[y/N\]|\[Y/n\]"           # y/n prompt (bracket form)
    r"|\(y/n\)|\(Y/n\)"           # y/n prompt (paren form)
    r"|\by/n\b|\byes/no\b"        # y/n prompt (bare/spelled-out form)
    r"|enter to submit.{0,15}esc to cancel"   # Claude/Codex standard footer
    r"|esc to cancel.{0,20}enter to submit"   # reversed footer order
    r"|^1\.\s*(?:Yes|Allow|No|Proceed|Continue|Apply|Run)\b"  # bare numbered list
    r"|requires confirmation|Hook PreToolUse"
    r"|^\s*3\.\s*No\b"            # 3-option dialog (1=Yes, 2=Yes+allow, 3=No)
    r"|esc to cancel\s*[·|·]\s*tab to amend",  # Codex footer variant
    re.IGNORECASE | re.MULTILINE,
)
EDIT_PROMPT_RE = re.compile(r"do you want to make this edit", re.IGNORECASE)
ESC_TAB_AMEND_RE = re.compile(r"esc to cancel\s*[·|]\s*tab to amend", re.IGNORECASE)
# "Esc to cancel · Enter to submit" — reversed order vs standard "enter to submit | esc to cancel"
ESC_CANCEL_ENTER_RE = re.compile(r"esc to cancel\s*[·|]\s*enter to submit", re.IGNORECASE)
VIEW_ALL_RE = re.compile(r"ctrl\s*\+\s*a\s+view\s+all", re.IGNORECASE)
ALLOW_CANCEL_PROMPT_RE = re.compile(
    r"tool call needs your approval.*?1\.\s*allow.*?2\.\s*cancel.*?enter to submit\s*\|\s*esc to cancel",
    re.IGNORECASE | re.DOTALL,
)
APPROVAL_BLOCK_ANCHOR_RE = re.compile(
    r"Tool call needs your approval|Would you like to run the following command\?"
    r"|Do you want to proceed\?|Would you like to proceed\?|Do you want to make this edit"
    r"|1\.\s*(?:Allow|Yes)"
    r"|2\.\s*(?:Cancel|No|Yes, and don't ask again)|enter to submit\s*\|\s*esc to cancel",
    re.IGNORECASE,
)


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
_clf_lock = threading.Lock()


def _get_approval_classifier():
    global _approval_clf
    if _approval_clf is not None:
        return _approval_clf
    with _clf_lock:
        if _approval_clf is not None:
            return _approval_clf
        if not _SEMANTIC_CLASSIFIER_AVAILABLE:
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


def is_approval_candidate_semantic(tail_text: str) -> bool:
    """Structural-first gate. Regexp decides immediately; semantic observes in background.

    The semantic classifier was previously the primary gate but suffered from
    score dilution when dialog windows also contained diff content or UI chrome.
    Now regexp (CANDIDATE_RE + INTERACTIVE_PROMPT_RE) is the authoritative signal.
    The classifier runs in a daemon thread, logs divergences, and saves training
    data so we can retrain it on real captures later.
    """
    structural_pass = bool(CANDIDATE_RE.search(tail_text) and INTERACTIVE_PROMPT_RE.search(tail_text))
    threading.Thread(
        target=_semantic_observe,
        args=(tail_text, structural_pass),
        daemon=True,
        name="semantic-observe",
    ).start()
    return structural_pass


def log(message: str) -> None:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(f"[{timestamp}] {message}\n")


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
            state[key] = {"digest": value, "cooldown_until": 0.0}
        elif isinstance(value, dict):
            digest = value.get("digest", "")
            cooldown_until = value.get("cooldown_until", 0.0)
            if isinstance(digest, str):
                try:
                    cooldown = float(cooldown_until)
                except (TypeError, ValueError):
                    cooldown = 0.0
                state[key] = {"digest": digest, "cooldown_until": cooldown}
    return state


def save_state(state: dict[str, dict[str, float | str]]) -> None:
    STATE_FILE.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
    env = kwargs.pop("env", None)
    return subprocess.run(cmd, text=True, capture_output=True, env=env, **kwargs)


def find_cli(name: str) -> str | None:
    return shutil.which(name, path=CLI_PATH)


def cmux_tree() -> list[dict[str, str]]:
    proc = run(["cmux", "--json", "tree", "--all"], check=True, timeout=5)
    data = json.loads(proc.stdout)
    rows: list[dict[str, str]] = []
    for window in data.get("windows", []):
        for workspace in window.get("workspaces", []):
            for pane in workspace.get("panes", []):
                for surface in pane.get("surfaces", []):
                    if surface.get("type") != "terminal":
                        continue
                    rows.append(
                        {
                            "workspace": workspace.get("ref", ""),
                            "title": workspace.get("title", ""),
                            "surface": surface.get("ref", ""),
                            "surface_title": surface.get("title", ""),
                        }
                    )
    return rows


def matches_filter(value: str, flt: str) -> bool:
    return not flt or flt in value


def read_screen(workspace: str, surface: str) -> str:
    try:
        proc = run(
            ["cmux", "read-screen", "--workspace", workspace, "--surface", surface, "--lines", str(LINES)],
            timeout=3,
        )
        return proc.stdout
    except subprocess.TimeoutExpired:
        log(f"READ_TIMEOUT workspace={workspace} surface={surface}")
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
        if is_approval_candidate_semantic(block_text) or (
            VIEW_ALL_RE.search(block_text)
            and OPTION1_Y_RE.search(block_text)
            and NUMBERED_CANCEL_RE.search(block_text)
        ):
            return block_text

    # Secondary anchor path: anchor is near the bottom (Claude Code TUI has input box BELOW
    # the dialog, so anchor_index != last_nonempty_index). When the anchor is within
    # CANDIDATE_WINDOW_LINES of the bottom AND the block passes structural, return it without
    # requiring semantic (semantic gets diluted by surrounding diff content and UI elements).
    if anchor_index >= 0 and (last_nonempty_index - anchor_index) < CANDIDATE_WINDOW_LINES:
        block_start = max(0, anchor_index - 3)  # include a few lines above for question context
        block_lines = region[block_start : last_nonempty_index + 1]
        block_text = "\n".join(line for line in block_lines if line.strip())
        if INTERACTIVE_PROMPT_RE.search(block_text):
            return block_text
        if is_approval_candidate_semantic(block_text) or (
            VIEW_ALL_RE.search(block_text)
            and OPTION1_Y_RE.search(block_text)
            and NUMBERED_CANCEL_RE.search(block_text)
        ):
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
            if is_approval_candidate_semantic(window_text) or (
                VIEW_ALL_RE.search(window_text)
                and OPTION1_Y_RE.search(window_text)
                and NUMBERED_CANCEL_RE.search(window_text)
            ) or (
                # Structural-only fallback: semantic gets diluted by surrounding noise
                # (diff content, UI boxes). If the window has both an approval trigger
                # phrase AND approval UI patterns, accept without semantic confirmation.
                CANDIDATE_RE.search(window_text)
                and INTERACTIVE_PROMPT_RE.search(window_text)
            ):
                latest_match = window_text
                break
    return latest_match


def heuristic_decision(tail_text: str) -> str:
    if SELECTED_OPTION_1_RE.search(tail_text) and ENTER_SUBMIT_RE.search(tail_text):
        return "ENTER"
    if EDIT_PROMPT_RE.search(tail_text) and SELECTED_OPTION_1_RE.search(tail_text) and ESC_TAB_AMEND_RE.search(tail_text):
        return "ENTER"
    # "Esc to cancel · Enter to submit" reversed-order footer — cursor already on option 1.
    if SELECTED_OPTION_1_RE.search(tail_text) and ESC_CANCEL_ENTER_RE.search(tail_text):
        return "ENTER"
    # Cursor is already on option 1 (❯ 1.) and that option is Yes/Allow — press Enter.
    # Covers 2-option AND 3-option dialogs (e.g. "3. No" instead of "2. No").
    if SELECTED_OPTION_1_RE.search(tail_text) and NUMBERED_ALLOW_RE.search(tail_text):
        return "ENTER"
    if OPTION1_Y_RE.search(tail_text) and NUMBERED_CANCEL_RE.search(tail_text):
        return "y"
    if NUMBERED_ALLOW_RE.search(tail_text) and ENTER_SUBMIT_RE.search(tail_text):
        return "ENTER"
    if ALLOW_CANCEL_PROMPT_RE.search(tail_text):
        return "ENTER"
    if NUMBERED_ALLOW_RE.search(tail_text) and NUMBERED_CANCEL_RE.search(tail_text):
        return "1"
    # 3-option Codex dialog: cursor defaults to option 1, so Enter confirms it.
    # send "1" via cmux send just types a character and doesn't confirm.
    if THREE_OPTION_CODEX_RE.search(tail_text):
        return "ENTER"
    # Cursor on option 2 and that option is affirmative (e.g. "❯ 2. Yes, and allow Claude...")
    # Option 2 is still a "Yes" — pressing Enter selects it, which is fine.
    if OPT2_AFFIRMATIVE_RE.search(tail_text):
        return "ENTER"
    if YN_APPROVE_RE.search(tail_text):
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
        if find_cli("codex"):
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
                if exc.returncode == 127 or "command not found" in exec_log.lower():
                    log(f"CLASSIFY_UNAVAILABLE workspace={workspace} surface={surface} provider={provider_name} exit={exc.returncode}")
                    continue
                if "not logged in" in exec_log.lower():
                    log(f"CLASSIFY_UNAVAILABLE workspace={workspace} surface={surface} provider={provider_name} reason=not_logged_in")
                    continue
                if "rate_limit_error" in exec_log.lower() or "rate limit" in exec_log.lower():
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


def approve(workspace: str, surface: str, decision: str) -> None:
    if decision == "ENTER":
        subprocess.run(["cmux", "send-key", "--workspace", workspace, "--surface", surface, "Enter"], check=True, timeout=3)
    elif decision == "1":
        subprocess.run(["cmux", "send", "--workspace", workspace, "--surface", surface, "1"], check=True, timeout=3)
    elif decision == "y":
        subprocess.run(["cmux", "send", "--workspace", workspace, "--surface", surface, "y"], check=True, timeout=3)
    log(f"APPROVE_SENT workspace={workspace} surface={surface} decision={decision}")


def digest_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def monitor_after_approve(
    workspace: str,
    title: str,
    surface: str,
    surface_title: str,
    prior_tail_text: str,
    prior_decision: str,
) -> tuple[str, float]:
    deadline = time.time() + POST_APPROVE_WATCH_SECONDS
    prior_digest = digest_text(prior_tail_text)
    latest_tail = prior_tail_text
    latest_digest = prior_digest

    while time.time() < deadline:
        time.sleep(POST_APPROVE_POLL_SECONDS)
        screen = read_screen(workspace, surface)
        if not screen:
            log(f"POST_APPROVE_PROGRESS workspace={workspace} surface={surface} status=screen_unreadable")
            return "", 0.0

        latest_tail = extract_candidate_tail(screen)
        if not latest_tail:
            log(f"POST_APPROVE_PROGRESS workspace={workspace} surface={surface} status=prompt_cleared")
            return "", 0.0

        latest_digest = digest_text(latest_tail)
        if latest_digest != prior_digest:
            log(f"POST_APPROVE_PROGRESS workspace={workspace} surface={surface} status=prompt_changed")
            return latest_tail, 0.0

    log(
        f"POST_APPROVE_STUCK workspace={workspace} surface={surface} "
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
        f"POST_APPROVE_ESCALATION workspace={workspace} surface={surface} decision={followup_decision}"
    )
    if followup_decision in {"ENTER", "1", "y"} and followup_decision != prior_decision:
        approve(workspace, surface, followup_decision)
        return latest_tail, time.time() + STUCK_COOLDOWN_SECONDS

    return latest_tail, time.time() + STUCK_COOLDOWN_SECONDS


def process_surface(
    row: dict[str, str],
    state_entry: dict[str, float | str],
    now: float,
) -> tuple[str, dict[str, float | str] | None]:
    state_key = f'{row["workspace"]}:{row["surface"]}'

    screen = read_screen(row["workspace"], row["surface"])
    if not screen:
        return state_key, None

    # Strip ANSI before candidate extraction so ❯ cursor patterns match correctly.
    screen = re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', screen)

    tail_text = extract_candidate_tail(screen)
    if not tail_text:
        return state_key, None

    digest = digest_text(tail_text)
    cooldown_until = float(state_entry.get("cooldown_until", 0.0) or 0.0)
    if state_entry.get("digest") == digest and cooldown_until > now:
        return state_key, {
            "digest": str(state_entry.get("digest", "")),
            "cooldown_until": cooldown_until,
        }

    log(
        f'CANDIDATE workspace={row["workspace"]} title={row["title"]} '
        f'surface={row["surface"]} surface_title={row["surface_title"]}'
    )
    decision = heuristic_decision(tail_text)
    if decision:
        log(f'HEURISTIC workspace={row["workspace"]} surface={row["surface"]} decision={decision}')
    else:
        # Classifier already confirmed this is an approval dialog (gate passed above).
        # Heuristic couldn't determine the key — ENTER is the safe default since
        # the cursor is on option 1 in all standard approval dialogs.
        decision = "ENTER"
        log(f'HEURISTIC_FALLBACK workspace={row["workspace"]} surface={row["surface"]} decision=ENTER')
    log(
        f'DECISION workspace={row["workspace"]} surface={row["surface"]} decision={decision}'
    )
    if decision in {"ENTER", "1", "y"}:
        approve(row["workspace"], row["surface"], decision)
        watched_tail, updated_cooldown_until = monitor_after_approve(
            row["workspace"],
            row["title"],
            row["surface"],
            row["surface_title"],
            tail_text,
            decision,
        )
        return state_key, {
            "digest": digest_text(watched_tail) if watched_tail else digest,
            "cooldown_until": updated_cooldown_until,
        }

    return state_key, {
        "digest": digest,
        "cooldown_until": time.time() + STUCK_COOLDOWN_SECONDS,
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
    rows_to_process: list[tuple[dict[str, str], dict[str, float | str]]] = []
    for row in cmux_tree():
        state_key = f'{row["workspace"]}:{row["surface"]}'
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
            state_key, state_update = future.result()
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
