#!/usr/bin/env python3
"""Sparse conversation history search across Claude, Codex, Hermes, agy CLI, and Cursor.

Extracts high-signal snippets within strict context budgets.
Gracefully handles absent databases, missing files, and malformed JSON.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Sequence


@dataclass
class HistoryEntry:
    source: str
    timestamp: str
    label: str
    snippet: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "timestamp": self.timestamp,
            "label": self.label,
            "snippet": self.snippet,
            "metadata": self.metadata,
        }


# Terminal color palette
ANSI = {
    "claude": "\033[34m",    # blue
    "codex":  "\033[36m",    # cyan
    "hermes": "\033[35m",    # magenta
    "agy":    "\033[33m",    # yellow
    "cursor": "\033[32m",    # green
    "head":   "\033[1;37m",  # bold white
    "match":  "\033[1;33m",  # bold yellow
    "dim":    "\033[2m",
    "reset":  "\033[0m",
}


def should_use_color(force_color: Optional[bool] = None) -> bool:
    if force_color is not None:
        return force_color
    if os.environ.get("NO_COLOR"):
        return False
    return sys.stdout.isatty()


def color(name: str, text: str, use_color: bool = True) -> str:
    if not use_color:
        return text
    c = ANSI.get(name, "")
    return f"{c}{text}{ANSI['reset']}" if c else text


def ansify(source: str, body: str, query: str = "", use_color: bool = True) -> str:
    """Wrap a result line: colored [Source] label + yellow-highlight matches in body only."""
    label = color(source, f"[{source.title()}]", use_color=use_color)
    line_body = body
    if query and use_color:
        pattern = re.compile(re.escape(query), re.IGNORECASE)
        line_body = pattern.sub(lambda m: color("match", m.group(0), use_color=True), line_body)
    return f"{label} {line_body}"


def head(text: str, use_color: bool = True) -> str:
    return color("head", text, use_color=use_color)


def _clean_snippet(text: str, max_chars: int = 200) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"\s+", " ", text).strip()
    return cleaned[:max_chars]


def _extract_claude_content(msg_obj: Any) -> str:
    if isinstance(msg_obj, str):
        return msg_obj
    if isinstance(msg_obj, list):
        parts = []
        for part in msg_obj:
            if isinstance(part, dict):
                if part.get("type") == "text" and part.get("text"):
                    parts.append(str(part["text"]))
                elif part.get("content"):
                    parts.append(str(part["content"]))
            elif isinstance(part, str):
                parts.append(part)
        return " ".join(parts)
    if isinstance(msg_obj, dict):
        if "content" in msg_obj:
            return _extract_claude_content(msg_obj["content"])
        if "text" in msg_obj:
            return str(msg_obj["text"])
    return ""


def search_claude(
    query: str = "",
    cwd: str = "",
    limit: int = 3,
    max_per_file: int = 3,
    max_chars: int = 200,
    projects_dir: Optional[Path | str] = None,
) -> list[HistoryEntry]:
    """Search Claude Code transcripts (~/.claude/projects/*/*.jsonl)."""
    results: list[HistoryEntry] = []
    base_dir = Path(projects_dir) if projects_dir is not None else Path.home() / ".claude" / "projects"
    if not base_dir.is_dir():
        return results

    cwd_path = cwd or os.getcwd()
    cwd_project_key = cwd_path.replace("/", "-")
    cwd_base = Path(cwd_path).name

    try:
        proj_entries = [e for e in os.scandir(base_dir) if e.is_dir() and not e.name.startswith('.')]
    except Exception:
        return results

    if not proj_entries:
        return results

    def safe_mtime(entry: os.DirEntry) -> float:
        try:
            return entry.stat().st_mtime
        except Exception:
            return 0.0

    cwd_matches: list[os.DirEntry] = []
    other_entries: list[os.DirEntry] = []

    for pe in proj_entries:
        if cwd_project_key in pe.name or (cwd_base and cwd_base in pe.name):
            cwd_matches.append(pe)
        else:
            other_entries.append(pe)

    sorted_projects = sorted(cwd_matches, key=safe_mtime, reverse=True) + sorted(
        other_entries, key=safe_mtime, reverse=True
    )

    query_lower = query.lower() if query else ""

    candidate_files: list[Path] = []
    for pe in sorted_projects[:10]:
        try:
            for fe in os.scandir(pe.path):
                if fe.is_file() and fe.name.endswith(".jsonl"):
                    candidate_files.append(Path(fe.path))
        except Exception:
            continue

    def file_mtime(p: Path) -> float:
        try:
            return p.stat().st_mtime
        except Exception:
            return 0.0

    candidate_files.sort(key=file_mtime, reverse=True)

    for file_path in candidate_files:
        if len(results) >= limit:
            break
        proj_name = file_path.parent.name
        file_hits = 0

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except Exception:
                        continue
                    if not isinstance(obj, dict):
                        continue

                    msg = obj.get("message", {})
                    role = obj.get("type") or (msg.get("role") if isinstance(msg, dict) else "")
                    is_user = role in ("user", "USER_INPUT", "human") or (
                        isinstance(msg, dict) and msg.get("role") == "user"
                    )

                    content = ""
                    if isinstance(msg, dict):
                        content = _extract_claude_content(msg.get("content"))
                    if not content and "content" in obj:
                        content = _extract_claude_content(obj.get("content"))

                    if not content:
                        continue

                    # If query is empty, restrict to user prompts only
                    if not query_lower and not is_user:
                        continue

                    if query_lower and query_lower not in content.lower():
                        continue

                    snippet = _clean_snippet(content, max_chars=max_chars)
                    if not snippet:
                        continue

                    ts = str(obj.get("timestamp") or "")[:16]
                    results.append(
                        HistoryEntry(
                            source="claude",
                            timestamp=ts,
                            label=proj_name,
                            snippet=snippet,
                            metadata={"file": file_path.name, "path": str(file_path), "is_user": is_user},
                        )
                    )
                    file_hits += 1
                    if file_hits >= max_per_file or len(results) >= limit:
                        break
        except Exception:
            continue

    return results[:limit]


def search_codex(
    query: str = "",
    cwd: str = "",
    limit: int = 5,
    max_chars: int = 200,
    db_path: Optional[Path | str] = None,
    sessions_dir: Optional[Path | str] = None,
) -> list[HistoryEntry]:
    """Search Codex threads (~/.codex/state_5.sqlite) and rollouts."""
    results: list[HistoryEntry] = []
    database = Path(db_path) if db_path is not None else Path.home() / ".codex" / "state_5.sqlite"

    cwd_path = cwd or os.getcwd()
    cwd_basename = Path(cwd_path).name

    if database.is_file():
        con = None
        try:
            con = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
            cur = con.cursor()
            like_param = f"%{query}%" if query else f"%{cwd_basename}%"

            date_expr = """
                CASE WHEN created_at > 100000000000
                     THEN datetime(created_at/1000, 'unixepoch', 'localtime')
                     ELSE datetime(created_at, 'unixepoch', 'localtime')
                END
            """

            if query:
                sql = f"""
                    SELECT title, substr(first_user_message, 1, 200), cwd, git_branch,
                           {date_expr} as created
                    FROM threads
                    WHERE (title LIKE ? OR first_user_message LIKE ?)
                      AND (archived = 0 OR archived IS NULL)
                    ORDER BY created_at DESC
                    LIMIT ?
                """
                params: tuple[Any, ...] = (like_param, like_param, limit)
            else:
                sql = f"""
                    SELECT title, substr(first_user_message, 1, 200), cwd, git_branch,
                           {date_expr} as created
                    FROM threads
                    WHERE (cwd LIKE ? OR cwd IS NULL)
                      AND (archived = 0 OR archived IS NULL)
                    ORDER BY created_at DESC
                    LIMIT ?
                """
                params = (like_param, limit)

            rows = cur.execute(sql, params).fetchall()
            if not rows and not query:
                # Fallback to recent threads across any workspace if cwd has no hits
                sql_recent = f"""
                    SELECT title, substr(first_user_message, 1, 200), cwd, git_branch,
                           {date_expr} as created
                    FROM threads
                    WHERE (archived = 0 OR archived IS NULL)
                    ORDER BY created_at DESC
                    LIMIT ?
                """
                rows = cur.execute(sql_recent, (limit,)).fetchall()

            for title, first_msg, row_cwd, branch, created in rows:
                proj = Path(row_cwd).name if row_cwd else "?"
                title_str = (title or "?")[:40]
                branch_str = branch or "main"
                snippet = _clean_snippet(first_msg or "", max_chars=max_chars)
                ts = str(created or "")[:10]
                label = f"{proj} | {branch_str} | {title_str}"
                results.append(
                    HistoryEntry(
                        source="codex",
                        timestamp=ts,
                        label=label,
                        snippet=snippet,
                        metadata={"cwd": row_cwd, "branch": branch, "title": title},
                    )
                )
        except Exception:
            pass
        finally:
            if con:
                try:
                    con.close()
                except Exception:
                    pass

    # Fallback to session rollout files if DB is missing or has no results
    if not results:
        sess_dir = Path(sessions_dir) if sessions_dir is not None else Path.home() / ".codex" / "sessions"
        if sess_dir.is_dir():
            try:
                rollout_files: list[Path] = []
                for root, _, files in os.walk(sess_dir):
                    for f in files:
                        if f.startswith("rollout-") and f.endswith(".jsonl"):
                            rollout_files.append(Path(root) / f)
                    if len(rollout_files) >= 20:
                        break

                def safe_mtime_p(p: Path) -> float:
                    try:
                        return p.stat().st_mtime
                    except Exception:
                        return 0.0

                rollout_files.sort(key=safe_mtime_p, reverse=True)

                for rf in rollout_files[:5]:
                    if len(results) >= limit:
                        break
                    try:
                        with open(rf, "r", encoding="utf-8", errors="ignore") as f:
                            for line in f:
                                line = line.strip()
                                if not line:
                                    continue
                                try:
                                    obj = json.loads(line)
                                except Exception:
                                    continue
                                if not isinstance(obj, dict):
                                    continue
                                text = ""
                                if obj.get("role") == "user":
                                    text = str(obj.get("content") or "")
                                elif "user_message" in obj:
                                    text = str(obj.get("user_message") or "")
                                elif "message" in obj and isinstance(obj["message"], dict):
                                    text = _extract_claude_content(obj["message"].get("content"))
                                if not text:
                                    continue
                                if query and query.lower() not in text.lower():
                                    continue
                                snippet = _clean_snippet(text, max_chars=max_chars)
                                ts = str(obj.get("timestamp") or "")[:10]
                                results.append(
                                    HistoryEntry(
                                        source="codex",
                                        timestamp=ts,
                                        label=rf.parent.name,
                                        snippet=snippet,
                                        metadata={"path": str(rf)},
                                    )
                                )
                                if len(results) >= limit:
                                    break
                    except Exception:
                        continue
            except Exception:
                pass

    return results[:limit]


def search_hermes(
    query: str = "",
    cwd: str = "",
    limit: int = 5,
    max_chars: int = 200,
    db_path: Optional[Path | str] = None,
) -> list[HistoryEntry]:
    """Search Hermes SQLite DB (~/.hermes/state.db) using FTS5 or LIKE fallback."""
    results: list[HistoryEntry] = []
    database = Path(db_path) if db_path is not None else Path.home() / ".hermes" / "state.db"
    if not database.is_file():
        return results

    con = None
    try:
        con = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
        cur = con.cursor()
        rows = []
        if query:
            try:
                sql_fts = """
                    SELECT s.title, s.source,
                           datetime(m.timestamp, 'unixepoch', 'localtime') as ts,
                           m.role, substr(m.content, 1, 200), m.tool_name
                    FROM messages m
                    JOIN sessions s ON m.session_id = s.id
                    WHERE m.id IN (SELECT rowid FROM messages_fts WHERE messages_fts MATCH ?)
                    ORDER BY m.timestamp DESC
                    LIMIT ?
                """
                rows = cur.execute(sql_fts, (query, limit)).fetchall()
            except sqlite3.OperationalError:
                rows = []

            if not rows:
                like_q = f"%{query}%"
                sql_like = """
                    SELECT s.title, s.source,
                           datetime(m.timestamp, 'unixepoch', 'localtime') as ts,
                           m.role, substr(m.content, 1, 200), m.tool_name
                    FROM messages m
                    JOIN sessions s ON m.session_id = s.id
                    WHERE (m.content LIKE ? OR m.tool_name LIKE ? OR m.tool_calls LIKE ?)
                    ORDER BY m.timestamp DESC
                    LIMIT ?
                """
                try:
                    rows = cur.execute(sql_like, (like_q, like_q, like_q, limit)).fetchall()
                except Exception:
                    rows = []
        else:
            # Query is empty: select newest messages without full table LIKE scan
            sql_recent = """
                SELECT s.title, s.source,
                       datetime(m.timestamp, 'unixepoch', 'localtime') as ts,
                       m.role, substr(m.content, 1, 200), m.tool_name
                FROM messages m
                JOIN sessions s ON m.session_id = s.id
                ORDER BY m.timestamp DESC
                LIMIT ?
            """
            try:
                rows = cur.execute(sql_recent, (limit,)).fetchall()
            except Exception:
                rows = []

        for row in rows:
            title, source_name, ts, role, content = row[0], row[1], row[2], row[3], row[4]
            tool_name = row[5] if len(row) > 5 else None
            snippet = _clean_snippet(content or "", max_chars=max_chars)
            role_desc = f"tool:{tool_name}" if role == "tool" and tool_name else (role or "user")
            label = f"{source_name or 'hermes'} | {(title or '?')[:40]} | {role_desc}"
            results.append(
                HistoryEntry(
                    source="hermes",
                    timestamp=str(ts or "")[:10],
                    label=label,
                    snippet=snippet,
                    metadata={"source": source_name, "title": title, "role": role, "tool_name": tool_name},
                )
            )
    except Exception:
        pass
    finally:
        if con:
            try:
                con.close()
            except Exception:
                pass

    return results[:limit]


def search_agy(
    query: str = "",
    cwd: str = "",
    limit: int = 5,
    max_chars: int = 200,
    db_path: Optional[Path | str] = None,
    brain_dir: Optional[Path | str] = None,
    history_file: Optional[Path | str] = None,
) -> list[HistoryEntry]:
    """Search agy CLI summaries DB and brain logs."""
    results: list[HistoryEntry] = []
    database = (
        Path(db_path)
        if db_path is not None
        else Path.home() / ".gemini" / "antigravity-cli" / "conversation_summaries.db"
    )

    cwd_path = cwd or os.getcwd()
    cwd_basename = Path(cwd_path).name

    if database.is_file():
        con = None
        try:
            con = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
            cur = con.cursor()
            rows = []
            if query:
                like_q = f"%{query}%"
                try:
                    sql = """
                        SELECT conversation_id, title, substr(preview, 1, 200),
                               step_count, last_modified_time, workspace_uris, agent_name
                        FROM conversation_summaries
                        WHERE (title LIKE ? OR preview LIKE ? OR workspace_uris LIKE ?)
                          AND (killed = 0 OR killed IS NULL)
                        ORDER BY last_modified_time DESC
                        LIMIT ?
                    """
                    rows = cur.execute(sql, (like_q, like_q, like_q, limit)).fetchall()
                except sqlite3.OperationalError:
                    sql_fallback = """
                        SELECT conversation_id, title, substr(preview, 1, 200),
                               step_count, last_modified_time, workspace_uris, agent_name
                        FROM conversation_summaries
                        WHERE (title LIKE ? OR preview LIKE ?)
                        ORDER BY last_modified_time DESC
                        LIMIT ?
                    """
                    rows = cur.execute(sql_fallback, (like_q, like_q, limit)).fetchall()
            else:
                try:
                    sql_cwd = """
                        SELECT conversation_id, title, substr(preview, 1, 200),
                               step_count, last_modified_time, workspace_uris, agent_name
                        FROM conversation_summaries
                        WHERE workspace_uris LIKE ?
                          AND (killed = 0 OR killed IS NULL)
                        ORDER BY last_modified_time DESC
                        LIMIT ?
                    """
                    rows = cur.execute(sql_cwd, (f"%{cwd_basename}%", limit)).fetchall()
                except sqlite3.OperationalError:
                    rows = []

                if not rows:
                    sql_recent = """
                        SELECT conversation_id, title, substr(preview, 1, 200),
                               step_count, last_modified_time, workspace_uris, agent_name
                        FROM conversation_summaries
                        WHERE (killed = 0 OR killed IS NULL)
                        ORDER BY last_modified_time DESC
                        LIMIT ?
                    """
                    rows = cur.execute(sql_recent, (limit,)).fetchall()

            for cid, title, preview, steps, mtime, ws, agent in rows:
                snippet = _clean_snippet(preview or "", max_chars=max_chars)
                title_str = (title or "?")[:40]
                agent_str = agent or "agy"
                steps_str = f"steps={steps}" if steps is not None else "steps=?"
                ts = str(mtime or "")[:10]
                label = f"{title_str} | {agent_str} | {steps_str}"
                results.append(
                    HistoryEntry(
                        source="agy",
                        timestamp=ts,
                        label=label,
                        snippet=snippet,
                        metadata={
                            "conversation_id": cid,
                            "workspace_uris": ws,
                            "agent": agent,
                            "steps": steps,
                        },
                    )
                )
        except Exception:
            pass
        finally:
            if con:
                try:
                    con.close()
                except Exception:
                    pass

    # Supplementary/fallback search in brain transcript logs only if DB returned 0 hits
    if not results:
        bdir = Path(brain_dir) if brain_dir is not None else Path.home() / ".gemini" / "antigravity-cli" / "brain"
        if bdir.is_dir():
            try:
                brain_entries = [e for e in os.scandir(bdir) if e.is_dir() and not e.name.startswith('.')]
                brain_entries.sort(key=lambda e: e.stat().st_mtime if e.is_dir() else 0, reverse=True)

                for be in brain_entries[:10]:
                    if len(results) >= limit:
                        break
                    candidate_logs = [
                        Path(be.path) / ".system_generated" / "logs" / "transcript.jsonl",
                        Path(be.path) / "logs" / "transcript.jsonl",
                        Path(be.path) / "transcript.jsonl",
                    ]
                    for tf in candidate_logs:
                        if not tf.is_file():
                            continue
                        try:
                            with open(tf, "r", encoding="utf-8", errors="ignore") as f:
                                for line in f:
                                    line = line.strip()
                                    if not line:
                                        continue
                                    try:
                                        obj = json.loads(line)
                                    except Exception:
                                        continue
                                    if not isinstance(obj, dict):
                                        continue
                                    content = str(obj.get("content") or "")
                                    if not content:
                                        continue
                                    if query and query.lower() not in content.lower():
                                        continue
                                    snippet = _clean_snippet(content, max_chars=max_chars)
                                    ts = str(obj.get("created_at") or "")[:10]
                                    label = f"brain | {be.name[:12]}"
                                    results.append(
                                        HistoryEntry(
                                            source="agy",
                                            timestamp=ts,
                                            label=label,
                                            snippet=snippet,
                                            metadata={"path": str(tf)},
                                        )
                                    )
                                    if len(results) >= limit:
                                        break
                        except Exception:
                            continue
            except Exception:
                pass

    # Optional history.jsonl if still no results
    if not results:
        hfile = Path(history_file) if history_file is not None else Path.home() / ".gemini" / "history.jsonl"
        if hfile.is_file():
            try:
                with open(hfile, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            obj = json.loads(line)
                        except Exception:
                            continue
                        if not isinstance(obj, dict):
                            continue
                        text = str(obj.get("prompt") or obj.get("content") or "")
                        if not text:
                            continue
                        if query and query.lower() not in text.lower():
                            continue
                        snippet = _clean_snippet(text, max_chars=max_chars)
                        ts = str(obj.get("timestamp") or "")[:10]
                        results.append(
                            HistoryEntry(
                                source="agy",
                                timestamp=ts,
                                label="history.jsonl",
                                snippet=snippet,
                                metadata={"path": str(hfile)},
                            )
                        )
                        if len(results) >= limit:
                            break
            except Exception:
                pass

    return results[:limit]


def search_cursor(
    query: str = "",
    cwd: str = "",
    limit: int = 3,
    max_chars: int = 200,
    prompt_history_path: Optional[Path | str] = None,
    chats_dir: Optional[Path | str] = None,
    projects_dir: Optional[Path | str] = None,
) -> list[HistoryEntry]:
    """Search Cursor prompt history (~/.cursor/prompt_history.json), chats, and agent transcripts."""
    results: list[HistoryEntry] = []
    hist_file = (
        Path(prompt_history_path)
        if prompt_history_path is not None
        else Path.home() / ".cursor" / "prompt_history.json"
    )

    query_lower = query.lower() if query else ""

    if hist_file.is_file():
        try:
            with open(hist_file, "r", encoding="utf-8", errors="ignore") as f:
                data = json.load(f)

            if isinstance(data, list):
                for entry in reversed(data):
                    text = ""
                    ts = ""
                    if isinstance(entry, dict):
                        text = (
                            entry.get("prompt")
                            or entry.get("text")
                            or entry.get("content")
                            or entry.get("message")
                            or ""
                        )
                        ts = str(entry.get("timestamp") or entry.get("ts") or "")[:16]
                    elif isinstance(entry, str):
                        text = entry

                    if not text:
                        continue

                    if query_lower and query_lower not in text.lower():
                        continue

                    snippet = _clean_snippet(text, max_chars=max_chars)
                    results.append(
                        HistoryEntry(
                            source="cursor",
                            timestamp=ts or "prompt",
                            label="prompt_history",
                            snippet=snippet,
                            metadata={"source": "prompt_history"},
                        )
                    )
                    if len(results) >= limit:
                        break
        except Exception:
            pass

    # Search Cursor agent transcripts if still under limit
    if len(results) < limit:
        pdir = Path(projects_dir) if projects_dir is not None else Path.home() / ".cursor" / "projects"
        if pdir.is_dir():
            try:
                candidate_files: list[Path] = []
                for root, dirs, files in os.walk(pdir):
                    if "agent-transcripts" in root:
                        for f in files:
                            if f.endswith(".jsonl"):
                                candidate_files.append(Path(root) / f)
                    if len(candidate_files) >= 10:
                        break

                def safe_mtime_p(p: Path) -> float:
                    try:
                        return p.stat().st_mtime
                    except Exception:
                        return 0.0

                candidate_files.sort(key=safe_mtime_p, reverse=True)

                for tf in candidate_files[:5]:
                    if len(results) >= limit:
                        break
                    try:
                        with open(tf, "r", encoding="utf-8", errors="ignore") as f:
                            for line in f:
                                line = line.strip()
                                if not line:
                                    continue
                                try:
                                    obj = json.loads(line)
                                except Exception:
                                    continue
                                if not isinstance(obj, dict):
                                    continue
                                msg = obj.get("message", {})
                                text = ""
                                if isinstance(msg, dict):
                                    text = _extract_claude_content(msg.get("content"))
                                if not text and "content" in obj:
                                    text = _extract_claude_content(obj.get("content"))
                                if not text and "prompt" in obj:
                                    text = str(obj["prompt"])

                                if not text:
                                    continue
                                if query_lower and query_lower not in text.lower():
                                    continue

                                snippet = _clean_snippet(text, max_chars=max_chars)
                                ts = str(obj.get("timestamp") or "")[:10]
                                label = f"agent | {tf.parent.parent.name[:30]}"
                                results.append(
                                    HistoryEntry(
                                        source="cursor",
                                        timestamp=ts or "agent",
                                        label=label,
                                        snippet=snippet,
                                        metadata={"path": str(tf)},
                                    )
                                )
                                if len(results) >= limit:
                                    break
                    except Exception:
                        continue
            except Exception:
                pass

    # Search Cursor chat files/meta if still under limit
    if len(results) < limit:
        cdir = Path(chats_dir) if chats_dir is not None else Path.home() / ".cursor" / "chats"
        if cdir.is_dir():
            try:
                chat_files: list[Path] = []
                for root, _, files in os.walk(cdir):
                    for f in files:
                        if f.endswith(".json") or f.endswith(".jsonl") or f == "meta.json":
                            chat_files.append(Path(root) / f)
                    if len(chat_files) >= 10:
                        break

                def safe_mtime_p(p: Path) -> float:
                    try:
                        return p.stat().st_mtime
                    except Exception:
                        return 0.0

                chat_files.sort(key=safe_mtime_p, reverse=True)

                for cf in chat_files[:5]:
                    if len(results) >= limit:
                        break
                    try:
                        with open(cf, "r", encoding="utf-8", errors="ignore") as f:
                            chunk = f.read(2048)
                        if query_lower and query_lower not in chunk.lower():
                            continue
                        snippet = _clean_snippet(chunk, max_chars=max_chars)
                        if not snippet:
                            continue
                        results.append(
                            HistoryEntry(
                                source="cursor",
                                timestamp="chat",
                                label=cf.name[:30],
                                snippet=snippet,
                                metadata={"path": str(cf)},
                            )
                        )
                    except Exception:
                        continue
            except Exception:
                pass

    return results[:limit]


ALL_SOURCES = ("claude", "codex", "hermes", "agy", "cursor")


def search_history(
    query: str = "",
    sources: Optional[Sequence[str]] = None,
    cwd: str = "",
    limit: int = 5,
    max_chars: int = 200,
    **kwargs: Any,
) -> dict[str, list[HistoryEntry]]:
    """Execute multi-source sparse history search across specified or all 5 sources."""
    selected_sources = [s.lower() for s in (sources or ALL_SOURCES)]
    results: dict[str, list[HistoryEntry]] = {}

    if "claude" in selected_sources:
        results["claude"] = search_claude(
            query=query,
            cwd=cwd,
            limit=limit,
            max_chars=max_chars,
            projects_dir=kwargs.get("claude_projects_dir"),
        )
    if "codex" in selected_sources:
        results["codex"] = search_codex(
            query=query,
            cwd=cwd,
            limit=limit,
            max_chars=max_chars,
            db_path=kwargs.get("codex_db_path"),
            sessions_dir=kwargs.get("codex_sessions_dir"),
        )
    if "hermes" in selected_sources:
        results["hermes"] = search_hermes(
            query=query,
            cwd=cwd,
            limit=limit,
            max_chars=max_chars,
            db_path=kwargs.get("hermes_db_path"),
        )
    if "agy" in selected_sources:
        results["agy"] = search_agy(
            query=query,
            cwd=cwd,
            limit=limit,
            max_chars=max_chars,
            db_path=kwargs.get("agy_db_path"),
            brain_dir=kwargs.get("agy_brain_dir"),
            history_file=kwargs.get("agy_history_file"),
        )
    if "cursor" in selected_sources:
        results["cursor"] = search_cursor(
            query=query,
            cwd=cwd,
            limit=limit,
            max_chars=max_chars,
            prompt_history_path=kwargs.get("cursor_prompt_history_path"),
            chats_dir=kwargs.get("cursor_chats_dir"),
            projects_dir=kwargs.get("cursor_projects_dir"),
        )

    return results


SOURCE_EMOJIS = {
    "claude": "📁 Claude Code",
    "codex": "🤖 Codex",
    "hermes": "⚡ Hermes",
    "agy": "🌐 agy CLI",
    "cursor": "🖥️  Cursor",
}


def format_results(
    results: dict[str, list[HistoryEntry]],
    query: str = "",
    use_color: bool = True,
) -> str:
    """Format multi-source results with ANSI colors and headers."""
    lines: list[str] = []
    total_hits = sum(len(hits) for hits in results.values())

    if query:
        lines.append(head(f"=== Sparse History Search: \"{query}\" ({total_hits} matches) ===", use_color=use_color))
    else:
        lines.append(head(f"=== Sparse History Overview ({total_hits} matches) ===", use_color=use_color))
    lines.append("")

    for source_key in ALL_SOURCES:
        if source_key not in results:
            continue
        entries = results[source_key]
        header_label = SOURCE_EMOJIS.get(source_key, source_key.title())
        lines.append(head(f"{header_label} ({len(entries)} matches)", use_color=use_color))

        if not entries:
            lines.append(f"  {color('dim', '(no matches)', use_color=use_color)}")
        else:
            for entry in entries:
                body = f"{entry.timestamp} | {entry.label} | {entry.snippet}"
                lines.append(f"  {ansify(source_key, body, query=query, use_color=use_color)}")
        lines.append("")

    return "\n".join(lines).rstrip()


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Sparse conversation history search across Claude, Codex, Hermes, agy, and Cursor."
    )
    parser.add_argument("query", nargs="?", default=os.environ.get("HIST_QUERY", ""), help="Search query string")
    parser.add_argument("-q", "--query-flag", dest="explicit_query", default="", help="Explicit query flag")
    parser.add_argument(
        "-s",
        "--source",
        choices=["all"] + list(ALL_SOURCES),
        default="all",
        help="Filter by specific source (default: all)",
    )
    parser.add_argument("-n", "--limit", type=int, default=5, help="Result limit per source (default: 5)")
    parser.add_argument("--max-chars", type=int, default=200, help="Max snippet length in chars (default: 200)")
    parser.add_argument("--cwd", default=os.getcwd(), help="Override working directory for project scoping")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI color codes")

    args = parser.parse_args(argv)

    search_query = args.explicit_query or args.query or ""
    use_color = should_use_color(force_color=False if args.no_color else None)

    sources = None if args.source == "all" else [args.source]
    results = search_history(
        query=search_query,
        sources=sources,
        cwd=args.cwd,
        limit=args.limit,
        max_chars=args.max_chars,
    )

    if args.json:
        json_out = {src: [e.to_dict() for e in entries] for src, entries in results.items()}
        print(json.dumps(json_out, indent=2))
    else:
        print(format_results(results, query=search_query, use_color=use_color))

    return 0


if __name__ == "__main__":
    sys.exit(main())
