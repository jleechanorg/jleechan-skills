"""Conservative structured skill-read extraction shared by telemetry runtimes."""

from __future__ import annotations

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
HEAD_TAIL_COUNT_RE = re.compile(r"^-?\d+$")
SED_PRINT_PROGRAM_RE = re.compile(r"^(?:\d+|\$)(?:,(?:\d+|\$))?p$")


class _RecordLocalReceipt:
    def __init__(self, path: tuple[str, ...]):
        self.path = path


def digest(data: bytes | str) -> str:
    return hashlib.sha256(data.encode() if isinstance(data, str) else data).hexdigest()


def normalize_path(raw: object, cwd: object = None) -> str | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    if not raw.strip():
        return None
    value = raw
    if value.startswith(("~", r"\~", "'~", '"~', "'\\~", '"\\~')):
        # The capture host is not evidence for a historical user's home.
        # Keep tilde-prefixed operands unresolved rather than expanding them.
        return None
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
    """Return literal read operands only when the whole shell command is static."""
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
        return _shell_read_paths(tokens[2]) if len(tokens) == 3 else []
    if _contains_unquoted_shell_dynamic(command):
        return []
    paths: list[str] = []
    segment: list[str] = []
    segments: list[list[str]] = []
    if tokens and tokens[-1] == ";":
        tokens = tokens[:-1]
    if not tokens:
        return []
    for token in tokens + [";"]:
        if token in {";", "&&", "||", "|"}:
            if not segment:
                return []
            segments.append(segment)
            segment = []
        else:
            segment.append(token)
    for segment in segments:
        if not segment or any("<" in token or ">" in token for token in segment):
            return []
        executable = Path(segment[0]).name
        if executable not in {"cat", "sed", "head", "tail"}:
            return []
        operands = _literal_reader_operands(executable, segment[1:])
        if operands is None:
            return []
        paths.extend(operands)
    return paths


def _literal_reader_operands(executable: str, arguments: list[str]) -> list[str] | None:
    """Parse the small option subset whose operands are provably file paths."""
    if executable == "cat":
        if "--" in arguments:
            marker = arguments.index("--")
            if any(token.startswith("-") and token != "-" for token in arguments[:marker]):
                return None
            arguments = arguments[marker + 1 :]
        elif any(token.startswith("-") and token != "-" for token in arguments):
            return None
        return [token for token in arguments if token != "-"]

    if executable in {"head", "tail"}:
        operands: list[str] = []
        cursor = 0
        while cursor < len(arguments):
            token = arguments[cursor]
            if token == "--":
                operands.extend(
                    path for path in arguments[cursor + 1 :] if path != "-"
                )
                break
            if token in {"-n", "--lines"}:
                if (
                    cursor + 1 >= len(arguments)
                    or not HEAD_TAIL_COUNT_RE.fullmatch(arguments[cursor + 1])
                ):
                    return None
                cursor += 2
                continue
            if token.startswith("-n") and HEAD_TAIL_COUNT_RE.fullmatch(token[2:]):
                cursor += 1
                continue
            if token.startswith("--lines=") and HEAD_TAIL_COUNT_RE.fullmatch(
                token.split("=", 1)[1]
            ):
                cursor += 1
                continue
            if re.fullmatch(r"-\d+", token):
                cursor += 1
                continue
            if token.startswith("-"):
                return None
            operands.append(token)
            cursor += 1
        return operands

    # Only a literal print program is accepted for sed.  This excludes -e,
    # scripts that execute commands, and all other option/program forms.
    cursor = 1 if arguments and arguments[0] == "-n" else 0
    if cursor >= len(arguments) or not SED_PRINT_PROGRAM_RE.fullmatch(arguments[cursor]):
        return None
    cursor += 1
    if any(token.startswith("-") and token != "-" for token in arguments[cursor:]):
        return None
    return [token for token in arguments[cursor:] if token != "-"]


def _contains_unquoted_shell_dynamic(command: str) -> bool:
    """Return whether unquoted shell expansion, substitution, or glob syntax exists."""
    quote: str | None = None
    escaped = False
    for character in command:
        if escaped:
            escaped = False
            continue
        if quote == "'":
            if character == "'":
                quote = None
            continue
        if character == "\\":
            escaped = True
            continue
        if quote == '"':
            if character == '"':
                quote = None
            elif character in "$`":
                return True
            continue
        if character in "'\"":
            quote = character
        elif character in "$`*?[]{}()":
            return True
    return False


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


def _iter_structured_calls(value: object, path: tuple[str, ...] = ()):
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
                receipt = value.get("id")
                if not receipt:
                    # A no-ID record has no cross-source identity.  This
                    # receipt only joins commandActions to its own command.
                    receipt = _RecordLocalReceipt(path)
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
            yield from _iter_structured_calls(child, path + (str(key),))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _iter_structured_calls(child, path + (str(index),))


JS_TOKEN = re.compile(
    r"""//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`|[A-Za-z_$][\w$]*|[^\s]"""
)
JS_IDENTIFIER = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*$")


def _literal_string(token):
    if not token.startswith(("'", '"')):
        return None
    if token.startswith('"'):
        try:
            value = json.loads(token)
        except json.JSONDecodeError:
            return None
        return value if isinstance(value, str) else None
    if "\\" in token:
        return None
    return token[1:-1]


def _orchestration_calls(arguments):
    """Read only direct literal ``tools.exec_command`` statements.

    The accepted subset is an optional ``await`` followed by one direct call,
    with literal object fields, and optional semicolon-separated repetitions.
    Any other program syntax is opaque and produces no calls.
    """
    if not isinstance(arguments, str):
        return []
    tokens = [
        m.group()
        for m in JS_TOKEN.finditer(arguments)
        if not m.group().startswith(("//", "/*"))
    ]
    if not tokens:
        return []

    unset = object()

    def literal(token):
        value = _literal_string(token)
        if value is not None:
            return value
        return {"true": True, "false": False, "null": None}.get(token, unset)

    def literal_object(cursor):
        if cursor >= len(tokens) or tokens[cursor] != "{":
            return None
        cursor += 1
        fields = {}
        while cursor < len(tokens):
            if tokens[cursor] == "}":
                return fields, cursor + 1
            key_literal = _literal_string(tokens[cursor])
            key = key_literal if key_literal is not None else tokens[cursor]
            if (
                not isinstance(key, str)
                or (key_literal is None and not JS_IDENTIFIER.fullmatch(key))
                or cursor + 2 >= len(tokens)
            ):
                return None
            if tokens[cursor + 1] != ":" or key in fields:
                return None
            value = literal(tokens[cursor + 2])
            if value is unset:
                return None
            fields[key] = value
            cursor += 3
            if cursor >= len(tokens):
                return None
            if tokens[cursor] == "}":
                return fields, cursor + 1
            if tokens[cursor] != ",":
                return None
            cursor += 1
            if cursor < len(tokens) and tokens[cursor] == "}":
                return fields, cursor + 1
        return None

    calls = []
    cursor = 0
    while cursor < len(tokens):
        if tokens[cursor] == "await":
            cursor += 1
        if tokens[cursor : cursor + 4] != [
            "tools",
            ".",
            "exec_command",
            "(",
        ]:
            return []
        parsed = literal_object(cursor + 4)
        if parsed is None:
            return []
        fields, cursor = parsed
        if cursor >= len(tokens) or tokens[cursor] != ")":
            return []
        cursor += 1
        for key in ("cmd", "command", "cwd", "workdir"):
            if key in fields and not isinstance(fields[key], str):
                return []
        if not (fields.get("cmd") or fields.get("command")):
            return []
        calls.append(fields)
        if cursor == len(tokens):
            break
        if tokens[cursor] != ";":
            return []
        cursor += 1
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
    record_position: object = None,
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
            if isinstance(call_id, _RecordLocalReceipt):
                record_path = json.dumps(call_id.path, separators=(",", ":"))
                position = (
                    str(record_position)
                    if record_position is not None
                    else record_path
                )
                stable = (
                    f"{runtime}:{source_path_id}:{timestamp.isoformat()}:record:"
                    f"{position}:{record_path}:{selected_path}"
                )
            elif call_id:
                stable = f"{runtime}:{session_id}:call:{call_id}:{selected_path}"
            else:
                position = (
                    str(record_position)
                    if record_position is not None
                    else "record"
                )
                stable = (
                    f"{runtime}:{source_path_id}:{timestamp.isoformat()}:"
                    f"{position}:{index}:{selected_path}"
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
