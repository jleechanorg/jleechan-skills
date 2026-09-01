#!/usr/bin/env python3
"""Capture a privacy-safe normalized telemetry corpus for command and skill audits."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

TAG = re.compile(r"<command-name>/([a-zA-Z0-9_-]+)</command-name>")
LEADING = re.compile(r"^\s*/([a-zA-Z0-9_-]+(?::[a-zA-Z0-9_-]+)?)(?:\s|$)")
SLASH_TOKEN_RE = re.compile(r"(?<![\w/])/((?:extended-library:)?[a-zA-Z0-9_-]+)(?![\w/])")
FILE_EXT_RE = re.compile(r"\.(sh|md|py|json|jsonl|ya?ml|dot|txt|log|toml|ts|js|html|png|mp4)\b")

NON_COMMAND_TOKENS = {
    "tmp", "dev", "null", "api", "src", "lib", "bin", "etc", "var", "usr", "opt",
    "home", "root", "proc", "sys", "boot", "projects", "backend", "frontend",
    "tests", "test", "docs", "scripts", "config", "utils", "services", "agents",
    "models", "tools", "hooks", "commands", "github", "v1", "v2", "venv", "json",
}


def digest(data: bytes | str) -> str:
    return hashlib.sha256(data.encode() if isinstance(data, str) else data).hexdigest()


def parse_time(raw: object) -> dt.datetime | None:
    if not isinstance(raw, str):
        return None
    try:
        return dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
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
                "content_sha256": digest(item.read_bytes()) if exists else "",
            }
        )
    return rows


def skill_inventory(skills_root: Path) -> list[dict]:
    rows = []
    for skill_file in sorted(skills_root.glob("*/SKILL.md")):
        rows.append(
            {
                "skill": skill_file.parent.name,
                "path": str(skill_file),
                "is_symlink": skill_file.parent.is_symlink() or skill_file.is_symlink(),
                "resolved_target": str(skill_file.resolve(strict=False)),
                "content_sha256": digest(skill_file.read_bytes()),
            }
        )
    return rows


def write_json(path: Path, payload: dict) -> str:
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return digest(path.read_bytes())


def capture(
    manifest_path: Path,
    history_root: Path | None = None,
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
    hist_root = history_root or Path(manifest["claude_history_root"])

    excluded = manifest.get(
        "excluded_command_documents", {"README": "directory documentation"}
    )
    inventory_data = {
        "schema": "claude_usage_inventory_snapshot.v2",
        "snapshot_id": manifest["snapshot_id"],
        "commands": command_inventory(cmd_root, excluded),
        "skills": skill_inventory(sk_root),
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
        }
    )
    events = []
    for history_file in sorted(hist_root.glob("**/*.jsonl")):
        coverage["files_discovered"] += 1
        path_id = digest(str(history_file.relative_to(hist_root)))
        try:
            data = history_file.read_bytes()
        except OSError:
            coverage["files_unreadable"] += 1
            continue
        coverage["files_opened"] += 1
        for line_number, raw_line in enumerate(data.splitlines(), 1):
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
            stamp = parse_time(record.get("timestamp"))
            if stamp is None:
                coverage["records_missing_or_invalid_timestamp"] += 1
                continue
            if not (start <= stamp < end):
                coverage["records_outside_window"] += 1
                continue
            coverage["records_in_window"] += 1
            content = (record.get("message") or {}).get("content", "")
            if record.get("type") == "assistant" and isinstance(content, list):
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
                                    "event_id": digest(
                                        f"{path_id}:{line_number}:{part_index}:{stamp.isoformat()}:{name}"
                                    ),
                                    "timestamp": stamp.isoformat(),
                                    "selected_name": name,
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
            # Also extract embedded non-path slash tokens
            embedded_tokens = [
                tok for tok in set(SLASH_TOKEN_RE.findall(body))
                if tok not in NON_COMMAND_TOKENS and not FILE_EXT_RE.search(tok)
            ]
            if tags or leading or embedded_tokens:
                events.append(
                    {
                        "kind": "command_candidate",
                        "event_id": digest(
                            f"{path_id}:{line_number}:{stamp.isoformat()}"
                        ),
                        "timestamp": stamp.isoformat(),
                        "entrypoint": record.get("entrypoint"),
                        "prompt_source": record.get("promptSource"),
                        "origin_kind": (record.get("origin") or {}).get("kind"),
                        "distinct_command_tags": tags,
                        "leading_slash": leading.group(1) if leading else None,
                        "embedded_slash_tokens": sorted(embedded_tokens),
                    }
                )

    corpus_data = {
        "schema": "claude_normalized_event_corpus.v2",
        "snapshot_id": manifest["snapshot_id"],
        "window_start_inclusive": manifest["window_start_inclusive"],
        "window_end_exclusive": manifest["window_end_exclusive"],
        "coverage": dict(coverage),
        "events": events,
    }
    corpus_sha = write_json(base / manifest["normalized_event_corpus"], corpus_data)
    manifest["inventory_snapshot_sha256"] = inventory_sha
    manifest["normalized_event_corpus_sha256"] = corpus_sha
    manifest["input_capture_completed_at"] = (
        dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z")
    )
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(
        f"captured inventory={inventory_sha} corpus={corpus_sha} events={len(events)}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Capture normalized telemetry corpus for command & skill usage audits."
    )
    parser.add_argument(
        "--manifest", type=Path, required=True, help="Path to audit manifest JSON"
    )
    parser.add_argument(
        "--history-root",
        type=Path,
        default=None,
        help="Optional history directory override",
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
    capture(
        args.manifest.resolve(),
        args.history_root.resolve() if args.history_root else None,
        args.commands_root.resolve() if args.commands_root else None,
        args.skills_root.resolve() if args.skills_root else None,
    )


if __name__ == "__main__":
    main()
