#!/usr/bin/env python3
"""Capture a privacy-safe normalized multi-runtime telemetry corpus (Claude Code + Codex + Hermes)."""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import json
import os
import re
import sqlite3
from collections import Counter
from pathlib import Path

try:
    from scripts.scoped_skill_usage import event_excluded
    from scripts.skill_read_telemetry import extract_skill_read_events
except ModuleNotFoundError:
    from scoped_skill_usage import event_excluded
    from skill_read_telemetry import extract_skill_read_events

TAG = re.compile(r"<command-name>/([a-zA-Z0-9_-]+)</command-name>")
LEADING = re.compile(r"^\s*/([a-zA-Z0-9_-]+(?::[a-zA-Z0-9_-]+)?)(?:\s|$)")
SLASH_TOKEN_RE = re.compile(
    r"(?<![\w/])/((?:extended-library:)?[A-Za-z][A-Za-z0-9_-]*)(?![\w/])"
)
FILE_EXT_RE = re.compile(
    r"\.(sh|md|py|json|jsonl|ya?ml|dot|txt|log|toml|ts|js|html|png|mp4)\b"
)
FRONTMATTER_NAME_RE = re.compile(r"^\s*name\s*:\s*(.+?)\s*$", re.MULTILINE)

NON_COMMAND_TOKENS = {
    "tmp", "dev", "null", "api", "src", "lib", "bin", "etc", "var", "usr", "opt",
    "home", "root", "proc", "sys", "boot", "projects", "backend", "frontend",
    "tests", "test", "docs", "scripts", "config", "utils", "services", "agents",
    "models", "tools", "hooks", "commands", "github", "v1", "v2", "venv", "json",
    "rate-limit-options", "STATE", "workflows", "code", "no", "install", "reviewer",
    "pipeline", "Users", "Applications", "Library", "System", "Volumes",
}


def digest(data: bytes | str) -> str:
    return hashlib.sha256(data.encode() if isinstance(data, str) else data).hexdigest()


def parse_time(raw: object) -> dt.datetime | None:
    try:
        if isinstance(raw, (int, float)):
            ts = raw / 1000.0 if raw > 1e11 else float(raw)
            return dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc)
        if isinstance(raw, str):
            stamp = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return stamp if stamp.utcoffset() is not None else None
    except (ValueError, OverflowError, OSError):
        return None
    return None


def message_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    return "\n".join(
        part.get("text", "")
        for part in content
        if isinstance(part, dict) and isinstance(part.get("text"), str)
    )


def frozen_content(content: bytes | None) -> dict[str, str | bool]:
    """Embed the exact bytes the row attests so the audit never re-reads disk.

    Capture and audit run minutes apart against live inventory roots, so a
    concurrent write would otherwise invalidate an in-flight run.  Base64 keeps
    the payload byte-exact and independently checkable against
    ``content_sha256``.

    Every row is frozen, including a legitimately empty document; leaving empty
    rows unfrozen would send them back to the live filesystem and reopen the
    race this exists to close.  ``None`` means capture could not read the file,
    which is recorded as ``content_captured: False`` rather than flattened into
    an empty document, so the audit never mistakes an unread file for an empty
    one or substitutes live bytes for it.
    """
    if content is None:
        return {"content_encoding": "base64", "content_b64": "", "content_captured": False}
    return {
        "content_encoding": "base64",
        "content_b64": base64.b64encode(content).decode("ascii"),
        "content_captured": True,
    }


def command_inventory(
    commands_root: Path, excluded_docs: dict[str, str] | None = None
) -> list[dict]:
    if excluded_docs is None:
        excluded_docs = {"README": "directory documentation"}
    rows = []
    paths = sorted(commands_root.glob("*.md"))
    extended_dir = commands_root / "extended-library"
    if extended_dir.is_dir():
        paths.extend(sorted(extended_dir.glob("*.md")))

    for item in paths:
        target = item.resolve(strict=False)
        exists = target.exists()
        try:
            content = item.read_bytes() if exists else None
        except OSError:
            content = None
        name = item.stem
        is_extended = item.parent.name == "extended-library"
        full_name = f"extended-library:{name}" if is_extended else name
        is_callable = name not in excluded_docs and full_name not in excluded_docs
        exclusion_reason = (
            excluded_docs.get(name, "")
            if name in excluded_docs
            else excluded_docs.get(full_name, "")
        )
        rows.append(
            {
                "command": full_name,
                "base_name": name,
                "path": str(item),
                "is_extended_library": is_extended,
                "callable": is_callable,
                "exclusion_reason": exclusion_reason,
                "is_symlink": item.is_symlink(),
                "resolved_target": str(target),
                "resolved_target_exists": exists,
                "content_sha256": digest(content) if content else "",
                **frozen_content(content),
            }
        )
    return rows


def parse_frontmatter_name(path: Path) -> str:
    """Return the declared skill name, falling back to the file/directory stem."""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as stream:
            prefix = "".join(stream.readline() for _ in range(80))
    except OSError:
        return path.parent.name if path.name == "SKILL.md" else path.stem
    match = FRONTMATTER_NAME_RE.search(prefix) if prefix.startswith("---") else None
    return match.group(1).strip(" `\"'") if match else (
        path.parent.name if path.name == "SKILL.md" else path.stem
    )


def _inventory_paths(root: Path) -> list[Path]:
    """Walk an inventory root while following symlinks but preventing cycles.

    A skill consists of any recursive ``SKILL.md`` plus a loose Markdown file
    directly beneath the root.  Reference Markdown below a skill is not itself
    a skill entry.
    """
    root = Path(os.path.abspath(str(root.expanduser())))
    if not root.is_dir():
        return []
    found: list[Path] = []
    stack: list[tuple[Path, frozenset[tuple[int, int]]]] = [(root, frozenset())]
    while stack:
        current, ancestors = stack.pop()
        try:
            stat = current.stat()
            identity = (stat.st_dev, stat.st_ino)
            if identity in ancestors:
                continue
            ancestors = ancestors | {identity}
            entries = sorted(current.iterdir(), key=lambda item: item.name, reverse=True)
        except OSError:
            continue
        for item in entries:
            if item.name in {".git", "node_modules", "skills_archive", "archive", "archives"}:
                continue
            if item.is_dir():
                stack.append((item, ancestors))
                continue
            if not item.is_file() or item.suffix.lower() != ".md":
                continue
            if item.name == "SKILL.md" or current == root:
                found.append(item)
    return sorted(found, key=lambda item: str(item))


def skill_inventory(
    skills_root: Path | None = None,
    inventory_roots: list[dict] | None = None,
) -> list[dict]:
    """Build a recursive, scope-aware skill inventory.

    ``inventory_roots`` is the new manifest form.  A single ``skills_root`` is
    retained for callers of the old API and receives the ``repo`` scope.
    """
    roots = inventory_roots or ([{"scope": "repo", "path": str(skills_root)}] if skills_root else [])
    rows: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for root_spec in roots:
        if not isinstance(root_spec, dict):
            continue
        scope = str(root_spec.get("scope") or "repo")
        root = Path(str(root_spec.get("path", ""))).expanduser()
        root_abs = Path(os.path.abspath(str(root)))
        for item in _inventory_paths(root_abs):
            try:
                relative = item.relative_to(root_abs).as_posix()
            except ValueError:
                continue
            target = item.resolve(strict=False)
            key = (scope, relative)
            if key in seen:
                continue
            seen.add(key)
            try:
                content = item.read_bytes()
            except OSError:
                content = None
            name = parse_frontmatter_name(item)
            rows.append(
                {
                    "skill_id": f"{scope}:{relative}",
                    "skill": name,
                    "name": name,
                    "scope": scope,
                    "relative_path": relative,
                    "path": str(item),
                    "is_symlink": item.is_symlink(),
                    "resolved_target": str(target),
                    "resolved_target_exists": target.exists(),
                    "hash": digest(content) if content else "",
                    "content_sha256": digest(content) if content else "",
                    **frozen_content(content),
                }
            )
    return sorted(rows, key=lambda row: row["skill_id"])


def write_json(path: Path, payload: dict) -> str:
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return digest(path.read_bytes())


def normalize_path(raw: object, cwd: object = None) -> str | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    value = raw.strip()
    if value.startswith("~"):
        path = Path(value).expanduser()
    elif os.path.isabs(value):
        path = Path(value)
    elif isinstance(cwd, str) and os.path.isabs(cwd):
        path = Path(cwd) / value
    else:
        return None
    return os.path.abspath(str(path))


def extract_claude_telemetry(
    hist_root: Path,
    start: dt.datetime,
    end: dt.datetime,
    coverage: Counter,
    inventory: list[dict] | None = None,
) -> list[dict]:
    events = []
    for history_file in sorted(hist_root.glob("**/*.jsonl")):
        coverage["files_discovered"] += 1
        path_id = digest(str(history_file.relative_to(hist_root)))
        try:
            stream = history_file.open("rb")
        except OSError:
            coverage["files_unreadable"] += 1
            continue
        coverage["files_opened"] += 1
        with stream:
            for line_number, raw_line in enumerate(stream, 1):
                coverage["lines_scanned"] += 1
                try:
                    line = raw_line.decode("utf-8", errors="strict")
                except UnicodeDecodeError:
                    coverage["lines_invalid_utf8"] += 1
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    coverage["lines_malformed_json"] += 1
                    continue
                if not isinstance(record, dict):
                    coverage["records_invalid_shape"] += 1
                    continue
                stamp = parse_time(record.get("timestamp"))
                if stamp is None:
                    coverage["records_missing_or_invalid_timestamp"] += 1
                    continue
                if not (start <= stamp < end):
                    coverage["records_outside_window"] += 1
                    continue
                coverage["records_in_window"] += 1
                message = record.get("message")
                content = message.get("content", "") if isinstance(message, dict) else ""
                session_id = record.get("sessionId") or record.get("session_id")
                cwd = record.get("cwd") if isinstance(record.get("cwd"), str) else None
                if record.get("type") == "assistant" and isinstance(content, list):
                    events.extend(
                        extract_skill_read_events(
                            content,
                            runtime="claude",
                            timestamp=stamp,
                            source_path_id=path_id,
                            session_id=str(session_id) if session_id else None,
                            cwd=cwd,
                            record_position=f"claude:{line_number}",
                            inventory=inventory,
                            coverage=coverage,
                        )
                    )
                    for part_index, part in enumerate(content):
                        if (
                            isinstance(part, dict)
                            and part.get("type") == "tool_use"
                            and part.get("name") == "Skill"
                        ):
                            name = (part.get("input") or {}).get("skill")
                            if isinstance(name, str) and name:
                                events.append(
                                    {
                                        "kind": "skill_selection",
                                        "runtime": "claude",
                                        "event_id": digest(f"claude:{path_id}:{line_number}:{part_index}:{stamp.isoformat()}:{name}"),
                                        "timestamp": stamp.isoformat(),
                                        "source_path_id": path_id,
                                        "selected_name": name,
                                        "cwd": cwd,
                                        "session_id": str(session_id) if session_id else None,
                                    }
                                )
                if (
                    record.get("type") != "user"
                    or record.get("isMeta")
                    or record.get("sourceToolUseID")
                ):
                    continue
                body = message_text(content)
                tags = sorted(set(TAG.findall(body)))
                leading = LEADING.match(body)
                embedded_tokens = [
                    tok for tok in set(SLASH_TOKEN_RE.findall(body))
                    if tok not in NON_COMMAND_TOKENS and not FILE_EXT_RE.search(tok)
                ]
                if tags or leading or embedded_tokens:
                    events.append(
                        {
                            "kind": "command_candidate",
                            "runtime": "claude",
                            "event_id": digest(
                                f"claude:{path_id}:{line_number}:{stamp.isoformat()}"
                            ),
                            "timestamp": stamp.isoformat(),
                            "entrypoint": record.get("entrypoint"),
                            "prompt_source": record.get("promptSource"),
                            "origin_kind": (record.get("origin") or {}).get("kind"),
                            "distinct_command_tags": tags,
                            "leading_slash": leading.group(1) if leading else None,
                            "embedded_slash_tokens": sorted(embedded_tokens),
                            "source_path_id": path_id,
                            "cwd": cwd,
                            "session_id": str(session_id) if session_id else None,
                        }
                    )
    return events


def _timestamp_from_record(record: dict, fallback: object = None) -> dt.datetime | None:
    return parse_time(record.get("timestamp") or record.get("ts") or record.get("created_at_ms") or fallback)


def _codex_structured_events(
    record: object,
    *,
    stamp: dt.datetime,
    source_path_id: str,
    session_id: str | None,
    cwd: str | None,
    record_position: object,
    inventory: list[dict] | None,
    coverage: Counter,
) -> list[dict]:
    return extract_skill_read_events(
        record,
        runtime="codex",
        timestamp=stamp,
        source_path_id=source_path_id,
        session_id=session_id,
        cwd=cwd,
        record_position=record_position,
        inventory=inventory,
        coverage=coverage,
    )


def _extract_codex_jsonl(
    path: Path,
    start: dt.datetime,
    end: dt.datetime,
    coverage: Counter,
    inventory: list[dict] | None,
) -> list[dict]:
    events: list[dict] = []
    path_id = digest(str(path))
    try:
        stream = path.open("rb")
    except OSError:
        coverage["files_unreadable"] += 1
        return events
    coverage["files_opened"] += 1
    session_id: str | None = None
    cwd: str | None = None
    with stream:
        for line_number, raw_line in enumerate(stream, 1):
            coverage["lines_scanned"] += 1
            try:
                record = json.loads(raw_line.decode("utf-8", errors="strict"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                coverage["lines_malformed_json"] += 1
                continue
            if not isinstance(record, dict):
                continue
            record_type = record.get("type")
            payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
            if record_type == "session_meta":
                if isinstance(payload.get("id"), str):
                    session_id = payload["id"]
                if isinstance(payload.get("cwd"), str):
                    cwd = payload["cwd"]
            elif record_type == "turn_context" and isinstance(payload.get("cwd"), str):
                cwd = payload["cwd"]
            stamp = _timestamp_from_record(record)
            if stamp is None:
                coverage["records_missing_or_invalid_timestamp"] += 1
                continue
            if not (start <= stamp < end):
                coverage["records_outside_window"] += 1
                continue
            coverage["records_in_window"] += 1
            event_session_id = record.get("session_id") or record.get("thread_id") or session_id
            event_cwd = record.get("cwd") if isinstance(record.get("cwd"), str) else cwd
            events.extend(
                _codex_structured_events(
                    record,
                    stamp=stamp,
                    source_path_id=path_id,
                    session_id=str(event_session_id) if event_session_id else None,
                    cwd=event_cwd,
                    record_position=f"jsonl:{line_number}",
                    inventory=inventory,
                    coverage=coverage,
                )
            )
            # history.jsonl is a user-command source; rollout JSONL is structured only.
            if path.name != "history.jsonl":
                continue
            text = record.get("text", "")
            if not isinstance(text, str):
                continue
            leading = LEADING.match(text)
            embedded_tokens = [
                tok for tok in set(SLASH_TOKEN_RE.findall(text))
                if tok not in NON_COMMAND_TOKENS and not FILE_EXT_RE.search(tok)
            ]
            if leading or embedded_tokens:
                events.append(
                    {
                        "kind": "command_candidate",
                        "runtime": "codex",
                        "event_id": digest(f"codex:{path_id}:{line_number}:{stamp.isoformat()}"),
                        "timestamp": stamp.isoformat(),
                        "entrypoint": "cli",
                        "prompt_source": "typed",
                        "origin_kind": "human",
                        "distinct_command_tags": [],
                        "leading_slash": leading.group(1) if leading else None,
                        "embedded_slash_tokens": sorted(embedded_tokens),
                        "source_path_id": path_id,
                        "cwd": event_cwd,
                        "session_id": str(event_session_id) if event_session_id else None,
                    }
                )
    return events


def extract_codex_telemetry(
    codex_root: Path,
    start: dt.datetime,
    end: dt.datetime,
    coverage: Counter,
    inventory: list[dict] | None = None,
) -> list[dict]:
    events: list[dict] = []
    history_file = codex_root / "history.jsonl"
    if history_file.is_file():
        coverage["files_discovered"] += 1
        events.extend(_extract_codex_jsonl(history_file, start, end, coverage, inventory))

    # Read both projected items and bounded rollout locations.  Stable call IDs
    # make the final merge deterministic without conflating unrelated JSONL.
    db_file = codex_root / "thread_history_1.sqlite"
    sqlite_available = db_file.is_file()
    rollout_paths: list[Path] = []
    for directory in (codex_root / "sessions", codex_root / "archived_sessions"):
        if directory.is_dir():
            rollout_paths.extend(sorted(directory.rglob("*.jsonl")))
    for index, rollout in enumerate(rollout_paths, 1):
        print(f"capture runtime=codex rollout_files={index}", file=__import__("sys").stderr) if index % 500 == 0 else None
        coverage["files_discovered"] += 1
        events.extend(_extract_codex_jsonl(rollout, start, end, coverage, inventory))
    if not sqlite_available:
        return _dedupe_events(events)
    coverage["files_discovered"] += 1
    path_id = digest(str(db_file))
    try:
        conn = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True)
        coverage["files_opened"] += 1
        start_ms = int(start.timestamp() * 1000)
        end_ms = int(end.timestamp() * 1000)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT thread_id, item_id, created_at_ms, item_json, item_type FROM thread_items "
            "WHERE created_at_ms >= ? AND created_at_ms < "
            "? ORDER BY created_at_ms, thread_id, item_id",
            (start_ms, end_ms),
        )
        for row_number, (
            thread_id,
            item_id,
            created_at_ms,
            item_json,
            item_type,
        ) in enumerate(cursor, 1):
            coverage["lines_scanned"] += 1
            try:
                record = json.loads(item_json)
            except (TypeError, json.JSONDecodeError):
                coverage["lines_malformed_json"] += 1
                continue
            stamp = parse_time(created_at_ms)
            if stamp is None or not (start <= stamp < end):
                continue
            coverage["records_in_window"] += 1
            cwd = record.get("cwd") if isinstance(record, dict) and isinstance(record.get("cwd"), str) else None
            if item_type == "userMessage" or (isinstance(record, dict) and record.get("type") == "userMessage"):
                text = record.get("text") or record.get("content") or ""
                text = message_text(text) if isinstance(text, list) else text
                if isinstance(text, str):
                    leading = LEADING.match(text)
                    embedded_tokens = [tok for tok in set(SLASH_TOKEN_RE.findall(text)) if tok not in NON_COMMAND_TOKENS and not FILE_EXT_RE.search(tok)]
                    if leading or embedded_tokens:
                        events.append({"kind": "command_candidate", "runtime": "codex", "event_id": digest(f"codex_sqlite:{path_id}:{item_id}"), "timestamp": stamp.isoformat(), "entrypoint": "cli", "prompt_source": "typed", "origin_kind": "human", "distinct_command_tags": [], "leading_slash": leading.group(1) if leading else None, "embedded_slash_tokens": sorted(embedded_tokens), "source_path_id": path_id, "cwd": cwd, "session_id": str(thread_id) if thread_id else None})
            events.extend(
                _codex_structured_events(
                    record,
                    stamp=stamp,
                    source_path_id=path_id,
                    session_id=str(thread_id) if thread_id else None,
                    cwd=cwd,
                    record_position=f"sqlite:{row_number}:{thread_id}:{item_id}",
                    inventory=inventory,
                    coverage=coverage,
                )
            )
        conn.close()
    except (OSError, sqlite3.Error):
        coverage["files_unreadable"] += 1
        coverage["codex_sqlite_partial_unknown"] += 1
    return _dedupe_events(events)


def _dedupe_events(events: list[dict]) -> list[dict]:
    unique: dict[str, dict] = {}
    for event in events:
        unique.setdefault(str(event.get("event_id")), event)
    return list(unique.values())


def extract_hermes_telemetry(
    hermes_root: Path, start: dt.datetime, end: dt.datetime, coverage: Counter
) -> list[dict]:
    events = []
    if not hermes_root.is_dir():
        return events
    for history_file in sorted(hermes_root.glob("**/*.jsonl")):
        coverage["files_discovered"] += 1
        path_id = digest(str(history_file.relative_to(hermes_root)))
        try:
            stream = history_file.open("rb")
            coverage["files_opened"] += 1
            with stream:
                for line_number, raw_line in enumerate(stream, 1):
                    coverage["lines_scanned"] += 1
                    try:
                        line = raw_line.decode("utf-8", errors="strict")
                        record = json.loads(line)
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        coverage["lines_malformed_json"] += 1
                        continue
                    if not isinstance(record, dict):
                        coverage["records_invalid_shape"] += 1
                        continue
                    stamp = parse_time(record.get("timestamp") or record.get("ts"))
                    if stamp is None or not (start <= stamp < end):
                        continue
                    coverage["records_in_window"] += 1
                    text = record.get("text") or message_text(record.get("message") or {})
                    leading = LEADING.match(text)
                    embedded_tokens = [
                        tok for tok in set(SLASH_TOKEN_RE.findall(text))
                        if tok not in NON_COMMAND_TOKENS and not FILE_EXT_RE.search(tok)
                    ]
                    if leading or embedded_tokens:
                        events.append(
                            {
                                "kind": "command_candidate",
                                "runtime": "hermes",
                                "event_id": digest(
                                    f"hermes:{path_id}:{line_number}:{stamp.isoformat()}"
                                ),
                                "timestamp": stamp.isoformat(),
                                "entrypoint": "cli",
                                "prompt_source": "typed",
                                "origin_kind": "human",
                                "distinct_command_tags": [],
                                "leading_slash": leading.group(1) if leading else None,
                                "embedded_slash_tokens": sorted(embedded_tokens),
                                "source_path_id": path_id,
                            }
                        )
        except OSError:
            coverage["files_unreadable"] += 1
    return events


def capture(
    manifest_path: Path,
    history_root: Path | None = None,
    codex_root: Path | None = None,
    commands_root: Path | None = None,
    skills_root: Path | None = None,
) -> None:
    manifest = json.loads(manifest_path.read_text())
    start = parse_time(manifest["window_start_inclusive"])
    end = parse_time(manifest["window_end_exclusive"])
    if (
        start is None
        or end is None
        or start.utcoffset() != dt.timedelta(0)
        or end.utcoffset() != dt.timedelta(0)
    ):
        raise ValueError("manifest requires UTC-aware window endpoints")

    base = manifest_path.parent
    cmd_root = commands_root or Path(
        manifest.get("command_inventory_root", base / ".claude" / "commands")
    )
    sk_root = skills_root or Path(
        manifest.get("skill_inventory_root", base / ".claude" / "skills")
    )
    claude_hist_root = history_root or Path(manifest["claude_history_root"])
    codex_hist_root = codex_root or Path(
        manifest.get("codex_root", os.path.expanduser("~/.codex"))
    )
    hermes_hist_root = Path(
        manifest.get("hermes_root", os.path.expanduser("~/.hermes"))
    )

    excluded = manifest.get(
        "excluded_command_documents", {"README": "directory documentation"}
    )
    configured_roots = manifest.get("skill_inventory_roots")
    if not isinstance(configured_roots, list) or not configured_roots:
        configured_roots = [{"scope": "repo", "path": str(sk_root)}]
    inventory_rows = skill_inventory(inventory_roots=configured_roots)
    inventory_data = {
        "schema": "claude_usage_inventory_snapshot.v2",
        "snapshot_id": manifest["snapshot_id"],
        "commands": command_inventory(cmd_root, excluded),
        "skills": inventory_rows,
        "skill_inventory_roots": configured_roots,
    }
    inventory_sha = write_json(base / manifest["inventory_snapshot"], inventory_data)

    coverage = Counter(
        {
            "files_discovered": 0,
            "files_opened": 0,
            "files_unreadable": 0,
            "lines_scanned": 0,
            "lines_invalid_utf8": 0,
            "lines_malformed_json": 0,
            "records_missing_or_invalid_timestamp": 0,
            "records_outside_window": 0,
            "records_in_window": 0,
            "events_excluded_by_manifest": 0,
            "structured_read_calls_seen": 0,
            "orchestration_calls_unparsed": 0,
            "structured_calls_unsupported": 0,
            "shell_calls_without_literal_reads": 0,
            "skill_read_candidates_rejected": 0,
            "codex_sqlite_partial_unknown": 0,
            "inventory_roots_missing": 0,
        }
    )

    for root_spec in configured_roots:
        if not isinstance(root_spec, dict) or not Path(str(root_spec.get("path", ""))).expanduser().is_dir():
            coverage["inventory_roots_missing"] += 1

    events = []
    # 1. Ingest Claude Code telemetry
    print("capture runtime=claude start", file=__import__("sys").stderr); events.extend(extract_claude_telemetry(claude_hist_root, start, end, coverage, inventory_rows)); print("capture runtime=claude end", file=__import__("sys").stderr)

    # 2. Ingest Codex telemetry if available
    if codex_hist_root.is_dir():
        print("capture runtime=codex start", file=__import__("sys").stderr); events.extend(extract_codex_telemetry(codex_hist_root, start, end, coverage, inventory_rows)); print("capture runtime=codex end", file=__import__("sys").stderr)

    # 3. Ingest Hermes telemetry if available
    if hermes_hist_root.is_dir():
        print("capture runtime=hermes start", file=__import__("sys").stderr); events.extend(extract_hermes_telemetry(hermes_hist_root, start, end, coverage)); print("capture runtime=hermes end", file=__import__("sys").stderr)

    excluded_session_ids = {str(item) for item in manifest.get("excluded_session_ids", [])}
    excluded_cwds = {
        str(Path(str(item)).expanduser().resolve(strict=False))
        for item in manifest.get("excluded_cwds", [])
        if isinstance(item, str)
    }
    retained_events: list[dict] = []
    for event in events:
        if event_excluded(event, manifest):
            coverage["events_excluded_by_manifest"] += 1
            continue
        retained_events.append(event)
    source_manifest = {
        "excluded_session_ids": sorted(excluded_session_ids),
        "excluded_cwds": sorted(excluded_cwds),
        "skill_inventory_roots": configured_roots,
    }
    corpus_data = {
        "schema": "claude_normalized_event_corpus.v2",
        "snapshot_id": manifest["snapshot_id"],
        "window_start_inclusive": manifest["window_start_inclusive"],
        "window_end_exclusive": manifest["window_end_exclusive"],
        "coverage": dict(coverage),
        "events": retained_events,
        "exclusions": source_manifest,
    }
    corpus_sha = write_json(base / manifest["normalized_event_corpus"], corpus_data)
    manifest["inventory_snapshot_sha256"] = inventory_sha
    manifest["normalized_event_corpus_sha256"] = corpus_sha
    manifest["capture_exclusions"] = source_manifest
    script_paths = [Path(__file__), Path(__file__).with_name("scoped_skill_usage.py"),
                    Path(__file__).with_name("skill_read_telemetry.py")]
    manifest["capture_source_sha256"] = {
        f"scripts/{path.name}": digest(path.read_bytes())
        for path in script_paths
        if path.is_file()
    }
    manifest["input_capture_completed_at"] = (
        dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z")
    )
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(
        f"captured inventory={inventory_sha} corpus={corpus_sha} total_events={len(retained_events)}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Capture normalized telemetry corpus for command & skill usage audits."
    )
    parser.add_argument("manifest_positional", nargs="?", type=Path, help="Manifest path (legacy positional form)")
    parser.add_argument("--manifest", type=Path, default=None, help="Path to audit manifest JSON")
    parser.add_argument(
        "--history-root",
        type=Path,
        default=None,
        help="Optional Claude history directory override",
    )
    parser.add_argument(
        "--codex-root",
        type=Path,
        default=None,
        help="Optional Codex root directory override",
    )
    parser.add_argument(
        "--commands-root",
        type=Path,
        default=None,
        help="Optional commands directory override",
    )
    parser.add_argument(
        "--skills-root",
        type=Path,
        default=None,
        help="Optional skills directory override",
    )
    args = parser.parse_args()
    manifest = args.manifest or args.manifest_positional
    if manifest is None:
        parser.error("a manifest path is required via --manifest or the legacy positional form")
    capture(
        manifest.resolve(),
        args.history_root.resolve() if args.history_root else None,
        args.codex_root.resolve() if args.codex_root else None,
        args.commands_root.resolve() if args.commands_root else None,
        args.skills_root.resolve() if args.skills_root else None,
    )


if __name__ == "__main__":
    main()
