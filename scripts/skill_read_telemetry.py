"""Conservative structured skill-read extraction shared by telemetry runtimes."""

from __future__ import annotations

import ast
import datetime as dt
import hashlib
import json
import os
import re
import shlex
from collections import Counter
from pathlib import Path

READ_TOOL_NAMES = {"Read", "read", "read_file", "ReadFile"}
SHELL_TOOL_NAMES = {"Bash", "bash", "exec_command"}
LOOSE_SKILL_PATH_RE = re.compile(r"(?:^|/)\.claude/skills/[^/]+\.md$")


def digest(data: bytes | str) -> str:
    return hashlib.sha256(data.encode() if isinstance(data, str) else data).hexdigest()


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


def _skill_path_observation(
    raw_path: object, cwd: object, inventory: list[dict] | None = None
):
    normalized = normalize_path(raw_path, cwd)
    if not normalized:
        return None
    target = Path(normalized)
    resolved = str(target.resolve(strict=False))
    for row in inventory or []:
        if normalized == os.path.abspath(
            str(row.get("path", ""))
        ) or resolved == row.get("resolved_target"):
            return normalized, str(row.get("name") or row.get("skill") or "") or None
    parts = target.parts
    if target.name == "SKILL.md":
        skill_indexes = [i for i, part in enumerate(parts[:-1]) if part == "skills"]
        if skill_indexes and skill_indexes[-1] + 1 < len(parts) - 1:
            return normalized, parts[skill_indexes[-1] + 1]
    if LOOSE_SKILL_PATH_RE.search(normalized):
        return normalized, target.stem
    return None


def _arguments(value: object) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _shell_read_paths(command: object) -> list[str]:
    if not isinstance(command, str) or "\n" in command:
        return []
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|<>")
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return []
    if (
        len(tokens) >= 3
        and Path(tokens[0]).name in {"bash", "sh", "zsh", "dash"}
        and tokens[1] in {"-c", "-lc"}
    ):
        return _shell_read_paths(
            tokens[2] if len(tokens) == 3 else " ".join(tokens[2:])
        )
    paths: list[str] = []
    segment: list[str] = []
    segments: list[list[str]] = []
    for token in tokens + [";"]:
        if token in {";", "&&", "||", "|"}:
            if segment:
                segments.append(segment)
            segment = []
        else:
            segment.append(token)
    for segment in segments:
        if not segment or any("<" in token or ">" in token for token in segment):
            continue
        executable = Path(segment[0]).name
        if executable not in {"cat", "sed", "head", "tail"}:
            continue
        operands = [
            token for token in segment[1:] if token != "-" and not token.startswith("-")
        ]
        if executable == "sed" and operands:
            operands = operands[1:]
        paths.extend(operands)
    return paths


def _tool_read_paths(name: object, arguments: object) -> list[str]:
    args = _arguments(arguments)
    if name in READ_TOOL_NAMES:
        return [
            str(args[key])
            for key in ("file_path", "path", "file")
            if isinstance(args.get(key), str)
        ]
    if name in SHELL_TOOL_NAMES:
        return _shell_read_paths(
            args.get("cmd") or args.get("command") or args.get("script")
        )
    return []


def _iter_structured_calls(value: object):
    if isinstance(value, dict):
        record_type = value.get("type")
        name = value.get("name")
        if record_type in (
            "function_call",
            "custom_tool_call",
            "tool_use",
            "commandExecution",
        ):
            if record_type == "commandExecution":
                receipt = value.get("id") or "command-execution"
                yield (
                    "exec_command",
                    {"command": value.get("command", ""), "cwd": value.get("cwd")},
                    receipt,
                )
                actions = value.get("commandActions")
                for action in actions if isinstance(actions, list) else []:
                    if isinstance(action, dict) and action.get("type") in (
                        "read",
                        "Read",
                    ):
                        yield (
                            "Read",
                            {"path": action.get("path"), "cwd": value.get("cwd")},
                            receipt,
                        )
            elif isinstance(name, str):
                yield (
                    name,
                    value.get(
                        "arguments", value.get("input", value.get("parameters", {}))
                    ),
                    (value.get("call_id") or value.get("callId") or value.get("id")),
                )
        for key, child in value.items():
            if key in {"text", "content", "aggregatedOutput", "output", "summary"}:
                continue
            yield from _iter_structured_calls(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_structured_calls(child)


JS_TOKEN = re.compile(
    r"""//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`|[A-Za-z_$][\w$]*|[^\s]"""
)


def _literal_string(token):
    if not token.startswith(("'", '"')):
        return None
    try:
        value = ast.literal_eval(token)
        return value if isinstance(value, str) else None
    except (SyntaxError, ValueError):
        return None


def _orchestration_calls(arguments):
    """Read literal argument objects; strings, comments and expressions stay opaque."""
    if not isinstance(arguments, str):
        return []
    tokens = [
        m.group()
        for m in JS_TOKEN.finditer(arguments)
        if not m.group().startswith(("//", "/*"))
    ]
    calls = []
    for index in range(len(tokens) - 5):
        if tokens[index : index + 5] != ["tools", ".", "exec_command", "(", "{"]:
            continue
        fields, depth, invalid = {}, 1, False
        cursor = index + 5
        while cursor < len(tokens) and depth:
            token = tokens[cursor]
            key = _literal_string(token) or token
            if depth == 1 and key in {"cmd", "command", "cwd", "workdir"}:
                if (
                    cursor + 3 >= len(tokens)
                    or tokens[cursor + 1] != ":"
                    or tokens[cursor + 3] not in {",", "}"}
                ):
                    invalid = True
                else:
                    value = _literal_string(tokens[cursor + 2])
                    invalid |= value is None or key in fields
                    fields[key] = value
            if token in {"{", "[", "("}:
                depth += 1
            elif token in {"}", "]", ")"}:
                depth -= 1
            cursor += 1
        if not depth and not invalid and (fields.get("cmd") or fields.get("command")):
            calls.append(fields)
    return calls


def _expanded_calls(payload, coverage):
    for name, arguments, call_id in _iter_structured_calls(payload):
        if name not in {"functions.exec", "exec"}:
            yield name, arguments, call_id
            continue
        calls = _orchestration_calls(arguments)
        if not calls and coverage is not None:
            coverage["orchestration_calls_unparsed"] += 1
        for index, fields in enumerate(calls):
            yield (
                "exec_command",
                fields,
                f"{call_id}:nested:{index}" if call_id else None,
            )


def extract_skill_read_events(
    payload: object,
    *,
    runtime: str,
    timestamp: dt.datetime,
    source_path_id: str,
    session_id: str | None = None,
    cwd: str | None = None,
    inventory: list[dict] | None = None,
    coverage: Counter | None = None,
) -> list[dict]:
    events: list[dict] = []
    for index, (name, arguments, call_id) in enumerate(
        _expanded_calls(payload, coverage)
    ):
        if name == "functions.exec_command":
            name = "exec_command"
        call_arguments = _arguments(arguments)
        call_cwd = call_arguments.get("workdir") or call_arguments.get("cwd") or cwd
        if not isinstance(call_cwd, str):
            call_cwd = cwd
        paths = _tool_read_paths(name, arguments)
        supported = name in READ_TOOL_NAMES | SHELL_TOOL_NAMES | {
            "functions.exec",
            "exec",
            "functions.exec_command",
        }
        if not supported and coverage is not None:
            coverage["structured_calls_unsupported"] += 1
        if not supported:
            continue
        if coverage is not None:
            coverage["structured_read_calls_seen"] += 1
            if name in SHELL_TOOL_NAMES and not paths:
                coverage["shell_calls_without_literal_reads"] += 1
        for raw_path in paths:
            observed = _skill_path_observation(raw_path, call_cwd, inventory)
            if not observed:
                if coverage is not None:
                    coverage["skill_read_candidates_rejected"] += 1
                continue
            selected_path, selected_name = observed
            stable = (
                f"{runtime}:{session_id}:call:{call_id}:{selected_path}"
                if call_id
                else f"{runtime}:{source_path_id}:{timestamp.isoformat()}:{index}:{selected_path}"
            )
            event = {
                "kind": "skill_read",
                "runtime": runtime,
                "event_id": digest(stable),
                "timestamp": timestamp.isoformat(),
                "source_path_id": source_path_id,
                "selected_path": selected_path,
            }
            if selected_name:
                event["selected_name"] = selected_name
            if call_cwd:
                event["cwd"] = call_cwd
            if session_id:
                event["session_id"] = session_id
            events.append(event)
    return list({event["event_id"]: event for event in events}.values())
