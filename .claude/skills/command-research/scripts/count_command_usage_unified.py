#!/usr/bin/env python3
"""
Unified Command Usage & Invocation Research Scanner.

Queries across all three primary AI session stores:
  1. Hermes SQLite database (~/.hermes/state.db)
  2. Claude Code session JSONL logs (~/.claude/projects/*/*.jsonl)
  3. Codex SQLite database (~/.codex/state_5.sqlite)

Classifies invocations into:
  - Human-Typed (interactive operator prompts)
  - Agentic / Subagent (autonomous delegator lanes, Stop-hook loops, cron/daemon triggers)

Usage:
    python count_command_usage_unified.py [--days N] [--top N] [--human-only] [--agent-only] [--json]
"""

import argparse
import json
import math
import os
import re
import sqlite3
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

PATH_PREFIXES = {
    "/Users", "/tmp", "/dev", "/null", "/api", "/src", "/lib", "/bin",
    "/etc", "/var", "/usr", "/opt", "/home", "/root", "/proc", "/sys",
    "/boot", "/projects", "/backend", "/frontend", "/tests", "/test",
    "/docs", "/scripts", "/config", "/utils", "/services", "/agents",
    "/models", "/tools", "/hooks", "/commands", "/github", "/mvp_site",
    "/site-packages", "/localhost", "/www", "/auth", "/oauth2", "/repos",
    "/pulls", "/issues", "/v1", "/v2", "/venv", "/python3", "/json",
    "/design", "/jleechan", "/jleechanorg", "/worldarchitect", "/firebase",
}

FILE_SUFFIXES = (
    ".md", ".py", ".ts", ".js", ".sh", ".json", ".yaml", ".yml",
    ".txt", ".log", ".html", ".css", ".go", ".rs",
)

AUTOMATION_MARKERS = (
    "Files touched in the latest Write operation",
    "You are an AI coding agent managed by",
    "You are an AI agent",
    "Session Lifecycle",
    "UserPromptSubmit hook",
    "OpenClaw operator note",
    "This session is being continued from a previous conversation",
    "<observed_from_primary_session>",
    "You are updating the README",
    "<EXTREMELY_IMPORTANT>",
    "<skill_listing>",
    "Base directory for this skill:",
    "[ASYNC DELEGATION",
    "[CONTEXT COMPACTION",
)

ALIAS_MAP = {
    'memory_search': 'ms',
    'evidence_review': 'er',
    'evidence-standards': 'es',
    'factory': 'f',
    'af': 'f',
    'web_advice': 'web-advice',
    'harness_engineering': 'harness',
    'repro_developer': 'repro',
}


def _skill_scan_result() -> dict[str, object]:
    """Create the stable result shape used by the explicit skill scanners."""
    return {
        "human": Counter(),
        "agent": Counter(),
        "unknown": Counter(),
        "record_types": Counter(),
        "malformed": Counter(),
        "records_scanned": 0,
        "supported": True,
        "status": "supported",
        "diagnostic": None,
    }


def _begin_skill_scan(cutoff, result: dict[str, object]) -> float | None:
    """Validate query bounds before reading a store; invalid bounds fail closed."""
    try:
        normalized = float(cutoff)
    except (TypeError, ValueError):
        normalized = math.nan
    if not math.isfinite(normalized):
        result["malformed"]["cutoff"] += 1
        result["status"] = "invalid-input"
        result["diagnostic"] = "invalid non-finite cutoff; scan skipped"
        return None
    return normalized


def _add_diagnostic(result: dict[str, object], message: str) -> None:
    if result["diagnostic"]:
        result["diagnostic"] += f"; {message}"
    else:
        result["diagnostic"] = message


def _mark_store_error(result: dict[str, object], store_name: str, exc) -> None:
    result["supported"] = False
    result["status"] = "error"
    _add_diagnostic(result, f"{store_name} history read error: {exc}")


def _is_schema_incompatibility(exc) -> bool:
    message = str(exc).lower()
    return any(
        marker in message
        for marker in ("no such table", "no such column", "has no column named")
    )


def _finish_skill_scan(result: dict[str, object], store_name: str) -> dict[str, object]:
    if result["status"] in {"invalid-input", "error"}:
        return result
    if not result["supported"]:
        result["status"] = "unsupported"
        return result
    total = sum(
        sum(bucket.values())
        for bucket in (result["human"], result["agent"], result["unknown"])
    )
    if total == 0:
        result["status"] = "supported-empty"
        _add_diagnostic(
            result,
            f"supported {store_name} store scanned; no explicit Skill tool calls found",
        )
    else:
        result["status"] = "supported"
    return result


def _skill_from_value(value) -> str | None:
    """Extract a skill name from a tool input without treating prose as use."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return None
    if not isinstance(value, dict):
        return None
    skill = value.get("skill")
    if not isinstance(skill, str):
        for key in ("arguments", "input", "parameters"):
            nested = value.get(key)
            if isinstance(nested, dict):
                skill = nested.get("skill")
                if isinstance(skill, str):
                    break
    if not isinstance(skill, str):
        return None
    skill = skill.strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", skill):
        return None
    return skill


def _record_skill_call(record: dict, known_skills: set[str]) -> tuple[str, str] | None:
    """Return (skill, record type) for one explicit Skill tool-call record."""
    payload = record.get("payload") or {}
    item = payload.get("item") if isinstance(payload, dict) else None
    if not isinstance(item, dict):
        item = payload if isinstance(payload, dict) else {}
    record_type = record.get("type")
    payload_type = payload.get("type") if isinstance(payload, dict) else None

    name = item.get("name") or item.get("tool_name")
    is_skill_item = str(item.get("type", "")).lower() == "skill"
    is_skill_tool = str(name).lower() == "skill"
    if not (is_skill_item or is_skill_tool):
        return None

    value = item.get("input")
    if value is None:
        value = item.get("arguments")
    if value is None:
        value = item
    skill = _skill_from_value(value)
    if skill is None or skill not in known_skills:
        return None
    label = ".".join(
        str(part)
        for part in (record_type, payload_type, name if is_skill_tool else "Skill")
        if part
    )
    return skill, label


def _record_skill_calls(record: dict, known_skills: set[str]) -> list[tuple[str, str, dict]]:
    """Find explicit Skill calls nested in Codex response/event records."""
    found = []

    def walk(value):
        if isinstance(value, dict):
            name = value.get("name") or value.get("tool_name")
            is_skill_item = str(value.get("type", "")).lower() == "skill"
            is_skill_tool = str(name).lower() == "skill"
            if is_skill_item or is_skill_tool:
                candidate = {"type": record.get("type"), "payload": value}
                parsed = _record_skill_call(candidate, known_skills)
                if parsed is not None:
                    found.append((parsed[0], parsed[1], value))
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(record)
    return found


def _call_identity(value, *, origin: str, timestamp=None, fallback_id=None) -> tuple:
    """Build a stable key for duplicate durable call records."""
    if not isinstance(value, dict):
        return origin, "record", timestamp, repr(value)
    call_id = value.get("call_id") or value.get("tool_call_id") or value.get("id") or fallback_id
    if call_id:
        return origin, "id", str(call_id)
    return origin, "record", timestamp, json.dumps(value, sort_keys=True, default=str)


def _classify_skill_destination(*, human: bool | None) -> str:
    if human is True:
        return "human"
    if human is False:
        return "agent"
    return "unknown"


def scan_claude_skill_invocations(
    known_skills: set[str], cutoff: float, projects_dir: str | None = None
) -> dict[str, object]:
    """Count Claude's explicit ``assistant.tool_use(name=Skill)`` records.

    Slash text, SKILL.md contents, and assistant prose are intentionally not
    inputs to this scanner. A missing ``isSidechain`` flag remains unknown so
    the human/agent split does not silently invent provenance.
    """
    result = _skill_scan_result()
    cutoff = _begin_skill_scan(cutoff, result)
    if cutoff is None:
        return result
    if projects_dir is None:
        projects_dir = os.path.expanduser("~/.claude/projects")
    if not os.path.exists(projects_dir):
        result["supported"] = False
        result["diagnostic"] = f"projects directory not found: {projects_dir}"
        return _finish_skill_scan(result, "Claude")
    if not os.path.isdir(projects_dir):
        result["supported"] = False
        result["diagnostic"] = f"projects path is not a directory: {projects_dir}"
        return _finish_skill_scan(result, "Claude")

    seen_calls = set()
    def on_walk_error(exc):
        _mark_store_error(result, "Claude", exc)

    for root, _, files in os.walk(projects_dir, onerror=on_walk_error):
        for fname in files:
            if not fname.endswith(".jsonl"):
                continue
            try:
                with open(os.path.join(root, fname), encoding="utf-8", errors="ignore") as handle:
                    for line in handle:
                        try:
                            record = json.loads(line)
                        except json.JSONDecodeError:
                            result["malformed"]["json"] += 1
                            continue
                        if not isinstance(record, dict):
                            result["malformed"]["record"] += 1
                            continue
                        result["records_scanned"] += 1
                        event_time = timestamp_seconds(record.get("timestamp"))
                        if "timestamp" in record and event_time is None:
                            result["malformed"]["timestamp"] += 1
                            continue
                        if cutoff and (event_time is None or event_time < cutoff):
                            if event_time is None:
                                result["malformed"]["timestamp"] += 1
                            continue
                        if record.get("type") != "assistant":
                            continue
                        message = record.get("message") or {}
                        content = message.get("content") if isinstance(message, dict) else None
                        if not isinstance(content, list):
                            continue
                        for block in content:
                            if not isinstance(block, dict) or block.get("type") != "tool_use":
                                continue
                            candidate = {
                                "type": "assistant",
                                "payload": {
                                    "type": "tool_use",
                                    "item": block,
                                },
                            }
                            parsed = _record_skill_call(candidate, known_skills)
                            if parsed is None:
                                continue
                            key = _call_identity(
                                block,
                                origin=os.path.realpath(os.path.join(root, fname)),
                                timestamp=record.get("timestamp"),
                            )
                            if key in seen_calls:
                                continue
                            seen_calls.add(key)
                            skill, label = parsed
                            destination = _classify_skill_destination(
                                human=(False if record.get("isSidechain") is True else
                                       True if record.get("isSidechain") is False else None)
                            )
                            result[destination][skill] += 1
                            result["record_types"][f"assistant.{label.split('.', 1)[-1]}"] += 1
            except OSError as exc:
                _mark_store_error(result, "Claude", exc)
                continue
    if result["malformed"]:
        details = ", ".join(
            f"{kind}={count}" for kind, count in sorted(result["malformed"].items())
        )
        _add_diagnostic(result, f"malformed Claude records: {details}")
    return _finish_skill_scan(result, "Claude")


def scan_codex_skill_invocations(
    known_skills: set[str], cutoff: float, db_path: Path | str | None = None
) -> dict[str, object]:
    """Count Codex records that explicitly identify a Skill tool call.

    Codex user messages containing ``/foo`` are not evidence here. Current
    Codex rollouts generally have no Skill tool record, in which case this
    returns an empty supported result and the report states that limitation.
    """
    result = _skill_scan_result()
    cutoff = _begin_skill_scan(cutoff, result)
    if cutoff is None:
        return result
    db_path = Path(db_path or os.path.expanduser("~/.codex/state_5.sqlite"))
    if not db_path.exists():
        result["supported"] = False
        result["diagnostic"] = f"database not found: {db_path}"
        return _finish_skill_scan(result, "Codex")
    seen_calls = set()
    conn = None
    try:
        conn = sqlite3.connect(str(db_path))
        columns = {row[1] for row in conn.execute("PRAGMA table_info(threads)")}
        if "rollout_path" not in columns:
            result["supported"] = False
            result["diagnostic"] = "missing required table: threads"
            conn.close()
            return _finish_skill_scan(result, "Codex")
        source_column = "thread_source" if "thread_source" in columns else "source"
        if source_column not in columns:
            result["supported"] = False
            result["diagnostic"] = "missing required thread provenance column"
            conn.close()
            return _finish_skill_scan(result, "Codex")
        # Thread updated_at is a mutable summary and can lag event timestamps.
        # Apply the lookback to each durable rollout event instead.
        where = "rollout_path IS NOT NULL AND rollout_path != ''"
        rows = conn.execute(
            f"SELECT rollout_path, {source_column} FROM threads WHERE {where}"
        ).fetchall()
        for rollout_path, source in rows:
            if not isinstance(rollout_path, str):
                result["malformed"]["record"] += 1
                continue
            path = Path(rollout_path)
            if not path.is_file():
                _mark_store_error(result, "Codex", f"rollout not readable: {path}")
                continue
            source_text = str(source or "").lower()
            human = True if source_text == "user" else False if source_text in {"subagent", "automation"} else None
            try:
                with path.open("r", encoding="utf-8", errors="ignore") as handle:
                    for line in handle:
                        try:
                            record = json.loads(line)
                        except json.JSONDecodeError:
                            result["malformed"]["json"] += 1
                            continue
                        if not isinstance(record, dict):
                            result["malformed"]["record"] += 1
                            continue
                        result["records_scanned"] += 1
                        event_time = timestamp_seconds(record.get("timestamp"))
                        if "timestamp" in record and event_time is None:
                            result["malformed"]["timestamp"] += 1
                            continue
                        if cutoff and (event_time is None or event_time < cutoff):
                            if event_time is None:
                                result["malformed"]["timestamp"] += 1
                            continue
                        for skill, label, call in _record_skill_calls(record, known_skills):
                            key = _call_identity(
                                call,
                                origin=os.path.realpath(path),
                                timestamp=record.get("timestamp"),
                                fallback_id=(record.get("call_id") or record.get("tool_call_id")),
                            )
                            if key in seen_calls:
                                continue
                            seen_calls.add(key)
                            destination = _classify_skill_destination(human=human)
                            result[destination][skill] += 1
                            result["record_types"][label] += 1
            except OSError as exc:
                _mark_store_error(result, "Codex", exc)
                continue
    except sqlite3.Error as exc:
        result["supported"] = False
        if "no such table" in str(exc).lower():
            result["diagnostic"] = f"unsupported Codex history schema: {exc}"
            result["status"] = "unsupported"
        else:
            _mark_store_error(result, "Codex", exc)
        return _finish_skill_scan(result, "Codex")
    finally:
        if conn is not None:
            conn.close()
    if result["malformed"]:
        details = ", ".join(
            f"{kind}={count}" for kind, count in sorted(result["malformed"].items())
        )
        _add_diagnostic(result, f"malformed Codex records: {details}")
    return _finish_skill_scan(result, "Codex")


def _decode_json_layers(value) -> tuple[object, bool]:
    """Decode nested JSON strings, returning whether any layer was malformed."""
    malformed = False
    while isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, json.JSONDecodeError):
            malformed = True
            break
    return value, malformed


def _hermes_skill_calls(tool_calls, tool_name) -> tuple[list[tuple[str, object]], bool]:
    calls = []
    tool_calls, malformed_json = _decode_json_layers(tool_calls)

    def function_for(call):
        function = call.get("function") if isinstance(call.get("function"), dict) else call
        if function is call:
            return function
        enclosing_id = {
            key: call[key]
            for key in ("call_id", "tool_call_id", "id")
            if key in call and key not in function
        }
        return {**enclosing_id, **function}

    def arguments_for(function):
        if "arguments" in function:
            value = function["arguments"]
        elif "input" in function:
            value = function["input"]
        else:
            value = function
        call_id = function.get("call_id") or function.get("tool_call_id") or function.get("id")
        for _ in range(20):
            value, nested_malformed = _decode_json_layers(value)
            if nested_malformed:
                return value, True
            if not isinstance(value, dict):
                break
            nested = None
            if "skill" not in value:
                if "arguments" in value:
                    nested = value["arguments"]
                elif "input" in value:
                    nested = value["input"]
            if nested is None:
                break
            value = nested
        if call_id and isinstance(value, dict) and not any(
            value.get(key) for key in ("call_id", "tool_call_id", "id")
        ):
            value = {**value, "call_id": call_id}
        return value, False

    if tool_name and str(tool_name).lower() == "skill":
        # Hermes stores the tool identity separately from its arguments in
        # some versions. Attribute that row to tool_name when an argument
        # payload is present, and avoid counting the same call twice below.
        if isinstance(tool_calls, list):
            for call in tool_calls:
                if isinstance(call, dict):
                    function = function_for(call)
                    value, malformed = arguments_for(function)
                    malformed_json |= malformed
                    calls.append(("tool_name", value))
        elif tool_calls:
            if isinstance(tool_calls, dict):
                value, malformed = arguments_for(tool_calls)
                malformed_json |= malformed
                calls.append(("tool_name", value))
            else:
                calls.append(("tool_name", tool_calls))
        return calls, malformed_json
    if isinstance(tool_calls, dict):
        tool_calls = [tool_calls]
    if not isinstance(tool_calls, list):
        return calls, malformed_json
    for call in tool_calls:
        if not isinstance(call, dict):
            continue
        function = function_for(call)
        name = function.get("name") or function.get("tool_name")
        if str(name).lower() == "skill":
            value, malformed = arguments_for(function)
            malformed_json |= malformed
            calls.append(("tool_calls", value))
    return calls, malformed_json


def scan_hermes_skill_invocations(
    known_skills: set[str], cutoff: float, db_path: Path | str | None = None
) -> dict[str, object]:
    """Count Hermes ``tool_name``/``tool_calls`` Skill records only."""
    result = _skill_scan_result()
    cutoff = _begin_skill_scan(cutoff, result)
    if cutoff is None:
        return result
    db_path = Path(db_path or os.path.expanduser("~/.hermes/state.db"))
    if not db_path.exists():
        result["supported"] = False
        result["diagnostic"] = f"database not found: {db_path}"
        return _finish_skill_scan(result, "Hermes")
    seen_calls = set()
    conn = None
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        rows = conn.execute(
            "SELECT m.session_id, m.tool_name, m.tool_calls, m.timestamp, "
            "s.source, s.user_id, s.parent_session_id "
            "FROM messages m LEFT JOIN sessions s ON m.session_id = s.id"
        )
        for session_id, tool_name, tool_calls, timestamp, source, user_id, parent_id in rows:
            result["records_scanned"] += 1
            timestamp_value = timestamp_seconds(timestamp)
            if timestamp is not None and timestamp_value is None:
                result["malformed"]["timestamp"] += 1
                continue
            if cutoff and (timestamp_value is None or timestamp_value < cutoff):
                if timestamp_value is None:
                    result["malformed"]["timestamp"] += 1
                continue
            source_text = str(source or "").lower()
            uid_text = str(user_id or "").lower()
            automated = bool(parent_id) or any(
                marker in source_text or marker in uid_text
                for marker in ("bot", "daemon", "subagent", "cron", "workflow", "automation")
            )
            human = False if automated else True if source_text in {"slack", "cli", "telegram", "api_server"} else None
            calls, malformed_json = _hermes_skill_calls(tool_calls, tool_name)
            if malformed_json:
                result["malformed"]["json"] += 1
            for kind, value in calls:
                if kind == "tool_name":
                    skill = _skill_from_value(value)
                    if skill is None:
                        continue
                    label = "messages.tool_name.Skill"
                else:
                    skill = _skill_from_value(value)
                    if skill is None or skill not in known_skills:
                        continue
                    label = "messages.tool_calls.Skill"
                if skill not in known_skills:
                    continue
                key = _call_identity(
                    value,
                    origin=str(session_id),
                    timestamp=timestamp,
                )
                if key in seen_calls:
                    continue
                seen_calls.add(key)
                destination = _classify_skill_destination(human=human)
                result[destination][skill] += 1
                result["record_types"][label] += 1
    except (sqlite3.Error, OSError) as exc:
        result["supported"] = False
        if _is_schema_incompatibility(exc):
            result["status"] = "unsupported"
            result["diagnostic"] = f"unsupported Hermes history schema: {exc}"
        else:
            _mark_store_error(result, "Hermes", exc)
        return _finish_skill_scan(result, "Hermes")
    finally:
        if conn is not None:
            conn.close()
    if result["malformed"]:
        details = ", ".join(
            f"{kind}={count}" for kind, count in sorted(result["malformed"].items())
        )
        _add_diagnostic(result, f"malformed Hermes records: {details}")
    return _finish_skill_scan(result, "Hermes")


def scan_skill_usage(
    known_skills: set[str], cutoff: float, *, claude_projects_dir: str | None = None,
    codex_db_path: Path | str | None = None, hermes_db_path: Path | str | None = None,
) -> dict[str, object]:
    """Aggregate explicit skill-tool measurements from the three stores."""
    raw_stores = {
        "claude": scan_claude_skill_invocations(known_skills, cutoff, claude_projects_dir),
        "codex": scan_codex_skill_invocations(known_skills, cutoff, codex_db_path),
        "hermes": scan_hermes_skill_invocations(known_skills, cutoff, hermes_db_path),
    }
    human = Counter()
    agent = Counter()
    unknown = Counter()
    stores = {}
    for name, raw_store in raw_stores.items():
        stores[name] = {
            **raw_store,
            "human": dict(sorted(raw_store["human"].items())),
            "agent": dict(sorted(raw_store["agent"].items())),
            "unknown": dict(sorted(raw_store["unknown"].items())),
            "record_types": dict(sorted(raw_store["record_types"].items())),
            "malformed": dict(sorted(raw_store["malformed"].items())),
        }
        store = raw_store
        human.update(store["human"])
        agent.update(store["agent"])
        unknown.update(store["unknown"])
    return {
        "human": dict(sorted(human.items())),
        "agent": dict(sorted(agent.items())),
        "unknown": dict(sorted(unknown.items())),
        "total": dict(sorted((human + agent + unknown).items())),
        "known_skills": sorted(known_skills),
        "stores": stores,
        "limitations": [
            "Only explicit Skill tool-call records count; slash text, prompt prose, and SKILL.md reads do not.",
            "Claude provenance uses the record-level isSidechain flag; missing flags remain unknown.",
            "Codex and Hermes report zero when no explicit Skill tool-call record exists; schema errors and malformed Hermes data are surfaced per store.",
        ],
    }


def _skill_destinations(*, human_only: bool = False, agent_only: bool = False) -> tuple[str, ...]:
    """Return the report buckets selected by the mutually exclusive CLI flags."""
    if human_only and agent_only:
        raise ValueError("--human-only and --agent-only are mutually exclusive")
    if human_only:
        return ("human",)
    if agent_only:
        return ("agent",)
    return ("human", "agent", "unknown")


def _filter_skill_payload(payload: dict[str, object], destinations: tuple[str, ...]) -> dict[str, object]:
    """Filter skill-mode JSON consistently while preserving per-store diagnostics."""
    selected = set(destinations)
    for name in ("human", "agent", "unknown"):
        if name not in selected:
            payload[name] = {}
    totals = Counter()
    for name in destinations:
        totals.update(payload[name])
    payload["total"] = dict(sorted(totals.items()))
    payload["selected_destinations"] = list(destinations)
    for store in payload["stores"].values():
        for name in ("human", "agent", "unknown"):
            if name not in selected:
                store[name] = {}
    return payload


def load_known_skills(search_roots: list[Path] | None = None) -> set[str]:
    skills = set()
    if search_roots is None:
        search_roots = [
            Path.home() / ".claude",
            Path.home() / ".codex",
            Path(__file__).resolve().parents[3],
        ]
    seen_paths = set()
    for root in search_roots:
        if not root.exists():
            continue
        for path in root.rglob("SKILL.md"):
            canonical_path = path.resolve()
            if canonical_path in seen_paths:
                continue
            seen_paths.add(canonical_path)
            if any(part in {"skills", "skills_archive"} for part in path.relative_to(root).parts):
                name = path.parent.name
                if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", name):
                    skills.add(name)
    return skills


def load_known_commands(search_roots: list[Path] | None = None) -> set[str]:
    cmds = set()
    if search_roots is None:
        search_roots = [
            Path.home() / ".claude",
            Path(__file__).resolve().parents[3],
        ]
    for root in search_roots:
        if not root.exists():
            continue
        for path in root.rglob("*.md"):
            parts = path.relative_to(root).parts
            if path.name == "SKILL.md" and any(
                part in {"skills", "skills_archive"} for part in parts
            ):
                name = path.parent.name
            elif any(
                part in {"commands", "commands_archive"} for part in parts
            ):
                if path.name == "README.md":
                    continue
                name = path.stem
            else:
                continue
            if not name.startswith("_") and name.upper() != name:
                cmds.add(name)
    return cmds


def timestamp_seconds(value) -> float | None:
    if isinstance(value, (int, float)):
        timestamp = float(value) / 1000 if value > 10_000_000_000 else float(value)
        return timestamp if math.isfinite(timestamp) else None
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def scan_hermes(known_cmds: set[str], cutoff: float) -> tuple[Counter, Counter]:
    human_counts = Counter()
    agent_counts = Counter()
    db_path = os.path.expanduser("~/.hermes/state.db")
    if not os.path.exists(db_path):
        return human_counts, agent_counts

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
    SELECT m.content, s.user_id, s.source, m.role, m.timestamp
    FROM messages m
    JOIN sessions s ON m.session_id = s.id
    WHERE m.timestamp >= ?
    """, (cutoff,))

    for content, user_id, source, role, ts in cur.fetchall():
        if not content or not isinstance(content, str):
            continue
        is_human = False
        if role == 'user':
            if source in ['slack', 'cli', 'telegram', 'api_server']:
                uid_str = str(user_id or '').lower()
                if not any(k in uid_str for k in ['bot', 'daemon', 'subagent', 'cron', 'workflow']):
                    if not any(m in content for m in AUTOMATION_MARKERS):
                        is_human = True

        for m in re.findall(r'(?:^|\s)/([a-zA-Z0-9_\-]+)', content):
            cmd = ALIAS_MAP.get(m, m)
            if cmd in known_cmds:
                if is_human:
                    human_counts[cmd] += 1
                else:
                    agent_counts[cmd] += 1
    conn.close()
    return human_counts, agent_counts


IMPERATIVE_VERBS = re.compile(
    r'\b(run|runs|running|rerun|reruns|rerunning|invoke|invokes|invoking|invocation|'
    r'use|uses|using|call|calls|calling|execute|executes|executing|execution|'
    r'launch|launches|launching|trigger|triggers|triggering|spawn|spawns|spawning|'
    r'start|starts|starting|try|trying|perform|performs|performing|apply|applies|applying|'
    r'dispatch|dispatches|dispatching|delegate|delegating|please|pls)\b',
    re.IGNORECASE,
)


def resolve_cmd(token: str, known_cmds: set[str]) -> str | None:
    cmd = ALIAS_MAP.get(token, token)
    if cmd in known_cmds:
        return cmd
    cmd_hyphen = cmd.replace("_", "-")
    if cmd_hyphen in known_cmds:
        return cmd_hyphen
    return None


def is_listing_or_report(text: str, known_cmds: set[str]) -> bool:
    # Check 1: Markdown table row with a slash command in a cell
    if re.search(r'\|[^|\n]*/[a-zA-Z0-9_\-]+[^|\n]*\|', text):
        return True
    # Check 2: 3 or more distinct known command tokens in the message
    raw_tokens = re.findall(r'(?:^|\s)/([a-zA-Z0-9_\-]+)', text)
    distinct = set()
    for m in raw_tokens:
        resolved = resolve_cmd(m, known_cmds)
        if resolved:
            distinct.add(resolved)
    if len(distinct) >= 3:
        return True
    return False


def is_imperative_invocation(text: str, slash_pos: int) -> bool:
    # 1. First non-whitespace token of message
    if not text[:slash_pos].strip():
        return True
    # 2. First non-whitespace token of line
    line_start = text.rfind('\n', 0, slash_pos)
    line_prefix = text[0:slash_pos] if line_start == -1 else text[line_start + 1:slash_pos]
    if line_prefix.strip() == "":
        return True
    # 3. Preceding text in current sentence/clause contains an imperative verb
    sent_start = max(line_prefix.rfind('. '), line_prefix.rfind('! '), line_prefix.rfind('? '), line_prefix.rfind('; '))
    clause_prefix = line_prefix[sent_start + 2:] if sent_start != -1 else line_prefix
    lookback = clause_prefix[-60:]
    if IMPERATIVE_VERBS.search(lookback):
        return True
    return False


def scan_claude(known_cmds: set[str], cutoff: float, projects_dir: str | None = None) -> tuple[Counter, Counter]:
    human_counts = Counter()
    agent_counts = Counter()
    if projects_dir is None:
        projects_dir = os.path.expanduser("~/.claude/projects")
    if not os.path.exists(projects_dir):
        return human_counts, agent_counts

    for root, _, files in os.walk(projects_dir):
        for fname in files:
            if not fname.endswith(".jsonl"):
                continue
            fpath = os.path.join(root, fname)
            try:
                if os.path.getmtime(fpath) < cutoff:
                    continue
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                if not lines:
                    continue

                session_is_subagent = False
                for line in lines[:5]:
                    try:
                        obj = json.loads(line)
                        if obj.get("isSidechain") or obj.get("agentType") or obj.get("parentUuid"):
                            session_is_subagent = True
                            break
                    except Exception:
                        pass

                for line in lines:
                    try:
                        obj = json.loads(line)
                        if cutoff:
                            event_time = timestamp_seconds(obj.get("timestamp"))
                            if event_time is None or event_time < cutoff:
                                continue
                        t = obj.get("type")
                        role = obj.get("role")
                        content = ""
                        if t == "user":
                            content = obj.get("message", {}).get("content", "")
                        elif role == "user":
                            content = obj.get("content", "")
                        elif t == "assistant" or role == "assistant":
                            content = obj.get("message", {}).get("content", "") or obj.get("content", "")

                        text = ""
                        if isinstance(content, str):
                            text = content
                        elif isinstance(content, list):
                            text = " ".join([p.get("text", "") for p in content if isinstance(p, dict)])

                        if not text or any(m in text for m in AUTOMATION_MARKERS):
                            continue

                        is_human = False
                        if not session_is_subagent and (t == "user" or role == "user"):
                            ps = obj.get("promptSource")
                            if ps in ['typed', None] and not text.startswith("You are a subagent"):
                                is_human = True

                        tag_hits = re.findall(r"<command-name>/([a-zA-Z0-9_\-]+)</command-name>", text)
                        if tag_hits:
                            for m in tag_hits:
                                cmd = resolve_cmd(m, known_cmds)
                                if cmd:
                                    if is_human:
                                        human_counts[cmd] += 1
                                    else:
                                        agent_counts[cmd] += 1
                        else:
                            if not is_listing_or_report(text, known_cmds):
                                for match in re.finditer(r'(?:^|\s)/([a-zA-Z0-9_\-]+)', text):
                                    cmd = resolve_cmd(match.group(1), known_cmds)
                                    if cmd:
                                        if is_human:
                                            human_counts[cmd] += 1
                                        else:
                                            slash_pos = match.start(1) - 1
                                            if is_imperative_invocation(text, slash_pos):
                                                agent_counts[cmd] += 1
                    except Exception:
                        pass
            except Exception:
                pass
    return human_counts, agent_counts



def scan_codex(
    known_cmds: set[str], cutoff: float, db_path: Path | str | None = None
) -> tuple[Counter, Counter, Counter, Counter]:
    human_counts = Counter()
    agent_counts = Counter()
    unknown_counts = Counter()
    source_counts = Counter()
    db_path = Path(db_path or os.path.expanduser("~/.codex/state_5.sqlite"))
    if not db_path.exists():
        return human_counts, agent_counts, unknown_counts, source_counts

    try:
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        columns = {row[1] for row in cur.execute("PRAGMA table_info(threads)")}
        required_columns = {"rollout_path", "thread_source"}
        if not required_columns.issubset(columns):
            raise RuntimeError(
                "Codex threads table lacks rollout_path or thread_source"
            )
        where = "rollout_path IS NOT NULL AND rollout_path != ''"
        parameters: tuple[float, ...] = ()
        if cutoff and "updated_at_ms" in columns:
            where += " AND updated_at_ms >= ?"
            parameters = (cutoff * 1000,)
        cur.execute(
            "SELECT rollout_path, thread_source FROM threads WHERE " + where,
            parameters,
        )
        for rollout_path, thread_source in cur.fetchall():
            path = Path(rollout_path)
            if not path.is_file():
                continue
            source = thread_source or "unknown"
            source_counts[source] += 1
            if source == "user":
                destination = human_counts
            elif source in {"subagent", "automation"}:
                destination = agent_counts
            else:
                destination = unknown_counts
            try:
                with path.open("r", encoding="utf-8", errors="ignore") as handle:
                    for line in handle:
                        try:
                            record = json.loads(line)
                            if record.get("type") != "event_msg":
                                continue
                            payload = record.get("payload") or {}
                            item = payload.get("item") or {}
                            if (
                                payload.get("type") != "item_completed"
                                or item.get("type") != "UserMessage"
                            ):
                                continue
                            event_time = timestamp_seconds(record.get("timestamp"))
                            if cutoff and (event_time is None or event_time < cutoff):
                                continue
                            content = item.get("content") or []
                            text = " ".join(
                                part.get("text", "")
                                for part in content
                                if isinstance(part, dict)
                            )
                            if not text or is_listing_or_report(text, known_cmds):
                                continue
                            for match in re.finditer(
                                r'(?:^|\s)/([a-zA-Z0-9_\-]+)', text
                            ):
                                cmd = resolve_cmd(match.group(1), known_cmds)
                                if not cmd:
                                    continue
                                if destination is human_counts:
                                    destination[cmd] += 1
                                elif destination is agent_counts:
                                    slash_pos = match.start(1) - 1
                                    if is_imperative_invocation(text, slash_pos):
                                        destination[cmd] += 1
                                else:
                                    destination[cmd] += 1
                        except (json.JSONDecodeError, OSError, TypeError):
                            continue
            except OSError:
                continue
        conn.close()
    except Exception as exc:
        raise RuntimeError(f"Failed to scan Codex history database: {db_path}") from exc
    return human_counts, agent_counts, unknown_counts, source_counts


def main():
    parser = argparse.ArgumentParser(description="Unified Command Usage & Invocation Research Scanner")
    parser.add_argument("--days", type=int, default=0, help="Lookback days (0 = all time)")
    parser.add_argument("--top", type=int, default=20, help="Top N commands to display")
    destination_group = parser.add_mutually_exclusive_group()
    destination_group.add_argument(
        "--human-only", action="store_true", help="Show only human-typed rankings"
    )
    destination_group.add_argument(
        "--agent-only", action="store_true", help="Show only agentic rankings"
    )
    parser.add_argument(
        "--skills",
        action="store_true",
        help="Measure explicit Skill tool calls across Claude, Codex, and Hermes",
    )
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    args = parser.parse_args()

    cutoff = (time.time() - args.days * 86400) if args.days > 0 else 0
    if args.skills:
        payload = scan_skill_usage(load_known_skills(), cutoff)
        payload["window"] = {"days": args.days, "cutoff_epoch": cutoff}
        destinations = _skill_destinations(
            human_only=args.human_only, agent_only=args.agent_only
        )
        _filter_skill_payload(payload, destinations)
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(f"=== EXPLICIT SKILL USAGE AUDIT ({'Last ' + str(args.days) + ' Days' if args.days else 'All Time'}) ===")
            for destination in destinations:
                print(f"--- {destination.title()} ---")
                for skill, count in sorted(payload[destination].items(), key=lambda item: (-item[1], item[0]))[:args.top]:
                    print(f"/{skill:<32} {count:>6d}")
            print("--- Store support ---")
            for store, store_payload in payload["stores"].items():
                print(f"{store:<8} supported={store_payload['supported']} records={store_payload['records_scanned']}")
                if store_payload["diagnostic"]:
                    print(f"         diagnostic={store_payload['diagnostic']}")
            print("--- Limitations ---")
            for limitation in payload["limitations"]:
                print(f"- {limitation}")
        return

    known_cmds = load_known_commands()

    h_hermes, a_hermes = scan_hermes(known_cmds, cutoff)
    h_claude, a_claude = scan_claude(known_cmds, cutoff)
    h_codex, a_codex, u_codex, codex_source_counts = scan_codex(
        known_cmds, cutoff
    )

    total_human = h_hermes + h_claude + h_codex
    total_agent = a_hermes + a_claude + a_codex
    total_unknown = u_codex
    total_all = total_human + total_agent + total_unknown

    if args.json:
        result = {
            "window": {"days": args.days, "cutoff_epoch": cutoff},
            "known_commands": sorted(known_cmds),
            "codex_thread_sources": dict(sorted(codex_source_counts.items())),
            "human": {name: total_human[name] for name in sorted(known_cmds)},
            "agent": {name: total_agent[name] for name in sorted(known_cmds)},
            "unknown": {name: total_unknown[name] for name in sorted(known_cmds)},
            "total": {name: total_all[name] for name in sorted(known_cmds)},
        }
        print(json.dumps(result, indent=2))
        return

    days_str = f"Last {args.days} Days" if args.days > 0 else "All Time"
    print(f"=== COMMAND USAGE AUDIT ({days_str}) ===\n")

    if not args.agent_only:
        print(f"--- Top {args.top} Human-Typed Commands ---")
        for r, (cmd, count) in enumerate(total_human.most_common(args.top), 1):
            tot = total_all[cmd]
            pct = (count / tot * 100) if tot > 0 else 0
            print(f"{r:2d}. /{cmd:<20} {count:>6d} human ({pct:>5.1f}% of {tot:>6d} total)")
        print()

    if not args.human_only:
        print(f"--- Top {args.top} Agentic / Subagent Commands ---")
        for r, (cmd, count) in enumerate(total_agent.most_common(args.top), 1):
            tot = total_all[cmd]
            pct = (count / tot * 100) if tot > 0 else 0
            print(f"{r:2d}. /{cmd:<20} {count:>6d} agent ({pct:>5.1f}% of {tot:>6d} total)")
        print()

        if total_unknown:
            print("--- Codex Commands With Unknown Thread Provenance ---")
            for cmd, count in total_unknown.most_common(args.top):
                print(f"   /{cmd:<20} {count:>6d} unknown")
            print()


if __name__ == "__main__":
    main()
