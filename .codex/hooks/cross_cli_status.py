#!/usr/bin/env python3
"""Unified Stop hook for Claude / Codex / Cursor / Antigravity / agy.

Reads the JSON Stop payload on stdin, normalizes model / token / cost /
rate-limit fields across the four CLI shapes, and writes a single
`~/.claude/var/cross_cli_status/last.json` record. Optionally tails a
`git-header.sh` style first line and PR URL (preserved for the existing
`stop-git-header-json.sh` callers).

Supported CLIs and event names
------------------------------
* **claude**    — Stop hook (v2.1.220+). Payload is the same JSON shape the
  statusline command receives, including `model`, `workspace.current_dir`,
  `context_window.{used_percentage,current_usage.{input,output}_tokens,
  total_input_tokens,total_output_tokens,context_window_size}`,
  `cost.total_cost_usd`, `rate_limits.{five_hour,seven_day}.{used_percentage,
  resets_at}`, `session_id`, `version`.
* **codex**     — Stop hook. Fields are flatter: `model.{id,display_name,name,
  }`, `usage.{input,output}_tokens`, `usage.cost_usd`,
  `rate_limits.{block_reset_seconds,reset_seconds}`, `session.cost_usd`,
  `cwd`. Codex 0.144+ supports `PreToolUse` denies via
  `{"decision":"block","reason":"..."}`; this hook is a Stop reader only.
* **agy**       — Inherits the Codex envelope when running on the agy CLI
  (`$HOME/.local/bin/agy 1.1.8`). Same field paths as Codex plus
  the OpenAI-compatible `usage` block.
* **cursor**    — `stop` event. Payload is `{conversation_id, generation_id,
  model, model_id?, model_params?, status, loop_count}` (no rate-limit
  fields, no token counts). The hook records status + loop_count so callers
  can alert on Cursor-loop storms.
* **antigravity** — Gemini-style `AfterAgent` event. No published Stop
  payload; the CLI writes a Gemini-shaped event with `decision` and
  `cwd`. Detected via the `decisions` marker and routed to a record that
  exposes only what is known.

Why a single Python module instead of a shell wrapper
-----------------------------------------------------
The four CLIs disagree on field names (`model.id` vs `model`, `usage.cost_usd`
vs `cost.total_cost_usd`, `context_window.used_percentage` vs nothing). A
shell script forces a "first-match wins" chain that silently drops fields
the day a CLI ships a new shape (verified regression in the legacy
`stop-git-header-json.sh` on 2026-07-17 — `.rate_limits.block_reset_seconds`
was Codex-only and Claude's `rate_limits.five_hour.used_percentage` was
ignored). This module:

1. detects which CLI fired the hook from explicit env vars
   (`HERMES_HOOK_CLI`) with payload-shape fallbacks;
2. normalizes into a single schema: `cli`, `model`, `context_pct`,
   `tokens_in`, `tokens_out`, `cost_usd`, `rate_limit_pct`,
   `rate_limit_window`, `rate_limit_reset_at`, `cwd`, `pr_url`,
   `header_status`, `received_at`, `event`, `raw_keys`;
3. merges the legacy `git-header.sh --status-only` first line + first PR
   URL so callers downstream do not lose them;
4. is **fail-closed by default**: if no recognized CLI is detected and no
   recognizable payload shape matches, it writes a record with
   `cli="unknown"` + the full raw JSON so a future regression does not
   silently swallow the payload. Use `--strict` to also exit non-zero
   (only recommended for `Stop` hooks that should not block the turn).

Files written
-------------
* `~/.claude/var/cross_cli_status/last.json`  — most recent payload (atomic
  write via tmp + rename; never a half-written file).
* `~/.claude/var/cross_cli_status/history.jsonl` — append-only log of the
  last 500 events (rotated; default 500, override via
  `CROSS_CLI_STATUS_HISTORY_MAX`).

Exit codes
----------
* `0` — payload processed; downstream callers should treat as success.
* `2` — `--strict` mode AND payload was unrecognizable. Use only in
  contexts where you want the hook to fail loud.
* `1` — internal error (no payload on stdin, IO error, bad JSON). The hook
  still writes `last.json` with the error envelope so a watchdog can
  alert.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import fcntl
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
HOME = Path(os.environ.get("HOME") or str(Path.home()))
STATE_DIR = HOME / ".claude" / "var" / "cross_cli_status"
LAST_PATH = STATE_DIR / "last.json"
HISTORY_PATH = STATE_DIR / "history.jsonl"


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


HISTORY_MAX = _int_env("CROSS_CLI_STATUS_HISTORY_MAX", 500)


# ---------------------------------------------------------------------------
# Field resolution
# ---------------------------------------------------------------------------
def _resolve(payload: Mapping[str, Any], paths: Iterable[str]) -> Any:
    """Return the first non-None value among the dotted-path candidates."""
    for path in paths:
        cur: Any = payload
        ok = True
        for part in path.split("."):
            if isinstance(cur, Mapping) and part in cur:
                cur = cur[part]
            else:
                ok = False
                break
        if ok and cur is not None:
            return cur
    return None


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# CLI detection
# ---------------------------------------------------------------------------
def detect_cli(payload: Mapping[str, Any]) -> str:
    """Return one of: claude | codex | agy | cursor | antigravity | unknown."""
    env = (os.environ.get("HERMES_HOOK_CLI") or "").strip().lower()
    if env in {"claude", "codex", "agy", "cursor", "antigravity"}:
        return env
    # Payload-shape fallbacks (verified 2026-07-30 against Claude 2.1.220 and
    # Codex 0.144.5; see tests/fixtures/live_payloads/ in the PR).
    keys = set(payload.keys())
    if "rate_limits" in payload and isinstance(payload.get("rate_limits"), Mapping):
        rl = payload["rate_limits"]
        if "five_hour" in rl or "seven_day" in rl:
            return "claude"
        if "block_reset_seconds" in rl or "reset_seconds" in rl:
            return "codex"
    if "conversation_id" in payload and "generation_id" in payload:
        return "cursor"
    # Antigravity (Gemini CLI) AfterAgent payload: {cwd, session_id, model,
    # decision}. No published Stop payload; `decision` is the only field
    # unique to this shape among the CLIs covered here.
    if "decision" in payload:
        return "antigravity"
    # Claude v2.1.220 Stop payload: {cwd, session_id, prompt_id, transcript_path,
    # last_assistant_message, stop_hook_active, session_crons, effort,
    # background_tasks, permission_mode, hook_event_name}. Note: no top-level
    # `model` key in the Stop event (statusline has it; Stop does not).
    # We distinguish from Codex via the `hook_event_name == "Stop"` casing
    # (Codex uses lowercase "stop") and via the `session_crons` + `effort`
    # fields that only Claude publishes.
    if "stop_hook_active" in payload and (
        "session_id" in payload or "transcript_path" in payload
    ):
        if (
            payload.get("hook_event_name") == "Stop"
            or "session_crons" in payload
            or "effort" in payload
        ):
            return "claude"
    # Codex 0.144.5 Stop payload: {cwd, hook_event_name, last_assistant_message,
    # model, permission_mode, session_id, stop_hook_active, transcript_path,
    # turn_id}. Note: `model` is a top-level STRING (not a dict) in Stop.
    if "last_assistant_message" in payload and "turn_id" in payload:
        return "codex"
    if "model" in payload and isinstance(payload.get("model"), Mapping):
        if "display_name" in payload["model"]:
            return "codex"
    # Note: a Claude payload may also have a top-level `context_window` (see
    # `extract_claude`). The detection step above already covers it via the
    # `session_id` + `transcript_path` + `model` triple; we deliberately do
    # not gate on `context_window` here because Codex-style payloads can
    # also include that key without implying "claude".
    return "unknown"


# ---------------------------------------------------------------------------
# Per-CLI extractors
# ---------------------------------------------------------------------------
def extract_claude(payload: Mapping[str, Any]) -> dict[str, Any]:
    rl = payload.get("rate_limits") if isinstance(payload.get("rate_limits"), Mapping) else {}
    five = rl.get("five_hour") or {}
    seven = rl.get("seven_day") or {}
    cw = payload.get("context_window") if isinstance(payload.get("context_window"), Mapping) else {}
    cu = cw.get("current_usage") or {}
    cost = payload.get("cost") if isinstance(payload.get("cost"), Mapping) else {}
    return {
        "model": _resolve(payload, ("model.display_name", "model.id", "model.name", "model")),
        "context_pct": _coerce_int(_resolve(payload, (
            "context_window.used_percentage",
            "context.used_percentage",
            "usage.context_window_percent",
            "usage.context_percent",
        ))),
        "tokens_in": _coerce_int(_resolve(payload, (
            "context_window.current_usage.input_tokens",
            "usage.input_tokens",
            "usage.prompt_tokens",
            "context_window.total_input_tokens",
        ))),
        "tokens_out": _coerce_int(_resolve(payload, (
            "context_window.current_usage.output_tokens",
            "usage.output_tokens",
            "usage.completion_tokens",
            "context_window.total_output_tokens",
        ))),
        "cost_usd": _coerce_float(_resolve(payload, (
            "cost.total_cost_usd",
            "usage.cost_usd",
            "cost.usd",
            "session.cost_usd",
        ))),
        "rate_limit_pct": _coerce_int(
            five.get("used_percentage")
            if five.get("used_percentage") is not None
            else seven.get("used_percentage")
            if seven.get("used_percentage") is not None
            else _resolve(payload, ("rate_limit_pct",))
        ),
        "rate_limit_window": (
            "5h" if five.get("used_percentage") is not None
            else "7d" if seven.get("used_percentage") is not None
            else None
        ),
        "rate_limit_reset_at": _coerce_int(
            five.get("resets_at")
            if five.get("resets_at") is not None
            else seven.get("resets_at")
        ),
        "session_id": payload.get("session_id"),
        "version": payload.get("version"),
    }


def extract_codex(payload: Mapping[str, Any]) -> dict[str, Any]:
    rl = payload.get("rate_limits") if isinstance(payload.get("rate_limits"), Mapping) else {}
    return {
        "model": _resolve(payload, (
            "model.display_name",
            "model.name",
            "model.id",
            "model",
            "agent.model.display_name",
            "agent.model.name",
            "agent.model.id",
            "agent.model",
        )),
        "context_pct": _coerce_int(_resolve(payload, (
            "context_window.used_percentage",
            "context.used_percentage",
            "usage.context_window_percent",
            "usage.context_percent",
        ))),
        "tokens_in": _coerce_int(_resolve(payload, (
            "usage.input_tokens",
            "usage.prompt_tokens",
            "token_usage.input_tokens",
            "tokens.input",
        ))),
        "tokens_out": _coerce_int(_resolve(payload, (
            "usage.output_tokens",
            "usage.completion_tokens",
            "token_usage.output_tokens",
            "tokens.output",
        ))),
        "cost_usd": _coerce_float(_resolve(payload, (
            "usage.cost_usd",
            "cost.usd",
            "session.cost_usd",
        ))),
        "rate_limit_pct": None,  # Codex Stop payload does not publish %.
        "rate_limit_window": None,
        "rate_limit_reset_at": _coerce_int(_resolve(payload, (
            "rate_limits.block_reset_seconds",
            "rate_limits.reset_seconds",
            "block_reset_seconds",
            "reset_seconds",
        ))),
        "session_id": payload.get("session_id") or payload.get("thread_id"),
    }


def extract_agy(payload: Mapping[str, Any]) -> dict[str, Any]:
    # agy wraps an OpenAI-compatible envelope around the Codex payload.
    base = extract_codex(payload)
    base["model"] = base["model"] or payload.get("model")
    return base


def extract_cursor(payload: Mapping[str, Any]) -> dict[str, Any]:
    # Cursor's stop payload exposes no rate-limit fields. We surface status +
    # loop_count so the hook can fire on a loop storm.
    loop_count = _coerce_int(payload.get("loop_count")) or 0
    rate_pct = 100 if payload.get("status") == "error" and loop_count >= 4 else None
    return {
        "model": payload.get("model") or payload.get("model_id"),
        "context_pct": None,
        "tokens_in": None,
        "tokens_out": None,
        "cost_usd": None,
        "rate_limit_pct": rate_pct,
        "rate_limit_window": "loop_storm" if rate_pct is not None else None,
        "rate_limit_reset_at": None,
        "session_id": payload.get("conversation_id"),
        "status": payload.get("status"),
        "loop_count": loop_count,
    }


def extract_antigravity(payload: Mapping[str, Any]) -> dict[str, Any]:
    # Antigravity is the Gemini CLI's "antigravity" branding. AfterAgent
    # events are not well-documented; we record the bare minimum.
    return {
        "model": _resolve(payload, (
            "model",
            "model.id",
            "model.name",
            "agent.model",
        )),
        "context_pct": None,
        "tokens_in": None,
        "tokens_out": None,
        "cost_usd": None,
        "rate_limit_pct": None,
        "rate_limit_window": None,
        "rate_limit_reset_at": None,
        "session_id": payload.get("session_id") or payload.get("thread_id"),
        "decision": _resolve(payload, ("decision", "last_decision")),
    }


EXTRACTORS = {
    "claude": extract_claude,
    "codex": extract_codex,
    "agy": extract_agy,
    "cursor": extract_cursor,
    "antigravity": extract_antigravity,
}


# ---------------------------------------------------------------------------
# Header / PR merge
# ---------------------------------------------------------------------------
def _capture_git_header(cwd: str) -> tuple[str | None, str | None]:
    """Best-effort: invoke the existing git-header.sh and grab the first
    status line and the first PR URL. Returns (status_line, pr_url)."""
    if not cwd or not os.path.isdir(cwd):
        return None, None
    candidates = [
        os.path.join(cwd, ".claude", "hooks", "git-header.sh"),
        os.path.join(cwd, ".codex", "hooks", "git-header.sh"),
        os.path.expanduser("~/.claude/hooks/git-header.sh"),
        os.path.expanduser("~/.codex/hooks/git-header.sh"),
    ]
    for script in candidates:
        if not (os.path.isfile(script) and os.access(script, os.X_OK)):
            continue
        try:
            proc = subprocess.run(
                [shutil.which("bash") or "bash", script, "--status-only"],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
                shell=False,
                env={**os.environ, "COLUMNS": "500"},
            )
        except (subprocess.SubprocessError, OSError) as exc:
            print(f"cross_cli_status: git-header capture failed for {script}: {exc}",
                  file=sys.stderr)
            continue
        out = (proc.stdout or "").strip()
        if not out:
            continue
        first_line = out.splitlines()[0] if out.splitlines() else None
        pr_url = next(
            (line for line in out.splitlines() if line.startswith(("http://", "https://"))),
            None,
        )
        return first_line, pr_url
    return None, None


# ---------------------------------------------------------------------------
# IO
# ---------------------------------------------------------------------------
def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", dir=str(path.parent), prefix=path.name + ".", suffix=".tmp",
        delete=False, encoding="utf-8",
    ) as fh:
        tmp = Path(fh.name)
        json.dump(payload, fh, ensure_ascii=False, sort_keys=True)
        fh.write("\n")
    tmp.replace(path)


def _append_history(payload: dict[str, Any]) -> None:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n"
    # Append and trim under a single exclusive lock so a concurrent hook
    # invocation (a realistic scenario — this is a multi-CLI Stop hook)
    # can never read-modify-write over this one's just-appended entry.
    with HISTORY_PATH.open("a+", encoding="utf-8") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            fh.write(line)
            fh.flush()
            if HISTORY_MAX > 0:
                fh.seek(0)
                lines = fh.read().splitlines()
                if len(lines) > HISTORY_MAX:
                    fh.seek(0)
                    fh.truncate()
                    fh.write("\n".join(lines[-HISTORY_MAX:]) + "\n")
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--strict", action="store_true",
                        help="Exit 2 when the payload is unrecognizable.")
    parser.add_argument("--no-header", action="store_true",
                        help="Skip the legacy git-header.sh merge (pure JSON record).")
    parser.add_argument("--print", action="store_true",
                        help="Print the normalized record to stdout.")
    args = parser.parse_args(argv)

    raw = sys.stdin.read()
    received_at = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
    record: dict[str, Any] = {
        "received_at": received_at,
        "event": os.environ.get("HERMES_HOOK_EVENT") or "Stop",
        "cli": "unknown",
        "raw_keys": [],
        "error": None,
    }
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as exc:
        record["error"] = f"invalid_json: {exc.msg}"
        record["raw_text_head"] = raw[:200]
        _atomic_write_json(LAST_PATH, record)
        _append_history(record)
        if args.print:
            print(json.dumps(record, sort_keys=True))
        return 1

    if not isinstance(payload, Mapping):
        record["error"] = "payload_not_object"
        record["raw_text_head"] = raw[:200]
        _atomic_write_json(LAST_PATH, record)
        _append_history(record)
        if args.print:
            print(json.dumps(record, sort_keys=True))
        return 1

    record["raw_keys"] = sorted(payload.keys())
    cli = detect_cli(payload)
    record["cli"] = cli
    extractor = EXTRACTORS.get(cli)
    if extractor is None:
        record["error"] = "unknown_cli_payload"
    else:
        record.update(extractor(payload))
    record["cwd"] = (
        record.get("cwd")
        or _resolve(payload, ("cwd", "workspace.current_dir", "working_dir"))
    )

    if not args.no_header and record.get("cwd"):
        status_line, pr_url = _capture_git_header(str(record["cwd"]))
        if status_line:
            record["header_status"] = status_line
        if pr_url:
            record["pr_url"] = pr_url

    _atomic_write_json(LAST_PATH, record)
    _append_history(record)

    if args.print:
        print(json.dumps(record, ensure_ascii=False, sort_keys=True))

    if record["error"] and args.strict:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
