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
        return float(value) / 1000 if value > 10_000_000_000 else float(value)
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
) -> tuple[Counter, Counter]:
    human_counts = Counter()
    agent_counts = Counter()
    db_path = Path(db_path or os.path.expanduser("~/.codex/state_5.sqlite"))
    if not db_path.exists():
        return human_counts, agent_counts

    try:
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        columns = {row[1] for row in cur.execute("PRAGMA table_info(threads)")}
        if "rollout_path" not in columns:
            raise RuntimeError("Codex threads table has no rollout_path column")
        where = "rollout_path IS NOT NULL AND rollout_path != ''"
        parameters: tuple[float, ...] = ()
        if cutoff and "updated_at_ms" in columns:
            where += " AND updated_at_ms >= ?"
            parameters = (cutoff * 1000,)
        cur.execute(
            "SELECT rollout_path, has_user_event FROM threads WHERE " + where,
            parameters,
        )
        for rollout_path, has_user_event in cur.fetchall():
            path = Path(rollout_path)
            if not path.is_file():
                continue
            is_human = bool(has_user_event)
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
                                if is_human:
                                    human_counts[cmd] += 1
                                else:
                                    slash_pos = match.start(1) - 1
                                    if is_imperative_invocation(text, slash_pos):
                                        agent_counts[cmd] += 1
                        except (json.JSONDecodeError, OSError, TypeError):
                            continue
            except OSError:
                continue
        conn.close()
    except Exception:
        pass
    return human_counts, agent_counts


def main():
    parser = argparse.ArgumentParser(description="Unified Command Usage & Invocation Research Scanner")
    parser.add_argument("--days", type=int, default=0, help="Lookback days (0 = all time)")
    parser.add_argument("--top", type=int, default=20, help="Top N commands to display")
    parser.add_argument("--human-only", action="store_true", help="Show only human-typed rankings")
    parser.add_argument("--agent-only", action="store_true", help="Show only agentic rankings")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    args = parser.parse_args()

    cutoff = (time.time() - args.days * 86400) if args.days > 0 else 0
    known_cmds = load_known_commands()

    h_hermes, a_hermes = scan_hermes(known_cmds, cutoff)
    h_claude, a_claude = scan_claude(known_cmds, cutoff)
    h_codex, a_codex = scan_codex(known_cmds, cutoff)

    total_human = h_hermes + h_claude + h_codex
    total_agent = a_hermes + a_claude + a_codex
    total_all = total_human + total_agent

    if args.json:
        result = {
            "window": {"days": args.days, "cutoff_epoch": cutoff},
            "known_commands": sorted(known_cmds),
            "human": {name: total_human[name] for name in sorted(known_cmds)},
            "agent": {name: total_agent[name] for name in sorted(known_cmds)},
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


if __name__ == "__main__":
    main()
