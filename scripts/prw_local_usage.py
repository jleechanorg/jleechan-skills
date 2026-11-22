#!/usr/bin/env python3
"""Summarize local coding-agent session logs into a small, privacy-preserving usage feed.

Stdlib only; runs on macOS and Linux. Reads facts only (token counts, timestamps, branch,
repo "owner/name"). It never copies prompt/response text, file contents, working
directories or remote URLs into the feed, and it never classifies or judges anything.

Feed (schema "prw-local-usage.v1"): {schema, machine, generated_at, window{start,end},
idle_gap_sec, sessions[{tool, session_id, repo, branch, first_at, last_at, active_sec,
models{<model>: {input, output, cache_read, cache_write}}}]}. Keys are sorted and sessions
are ordered by (tool, session_id). Only events with start <= timestamp < end count; sessions
with no counted event are omitted.

active_sec: the sum of gaps between consecutive counted event timestamps of a session where
the gap is <= idle_gap_sec (default 300); larger gaps contribute 0.

Tools: claude (message.usage grouped by message.id, largest output kept) and codex
(cumulative token_count totals; usage is last total before end minus last total before
start). Adding a tool is one scan function (roots, start, end) -> {session_id: record}
plus one TOOLS registry entry.

Publishing reuses prw_metrics.publish to write dashboards/prw/usage/<machine-slug>.json.
"""
import argparse
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prw_metrics import publish  # noqa: E402

SCHEMA = "prw-local-usage.v1"
ZERO = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}


def parse_ts(value):
    """ISO-8601 -> aware UTC datetime, or None."""
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def fmt_ts(dt):
    return dt.astimezone(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _int(v):
    return v if isinstance(v, int) and not isinstance(v, bool) and v > 0 else 0


def normalize_remote(url):
    """Remote URL (https, ssh, scp-style) -> "owner/name", else None."""
    url = (url or "").strip()
    path = url.split("://", 1)[1].split("/", 1)[1] if "://" in url and "/" in url.split("://", 1)[1] else url.rsplit(":", 1)[-1]
    parts = [p for p in re.sub(r"\.git/?$", "", path.strip("/")).split("/") if p]
    return "/".join(parts[-2:]) if len(parts) >= 2 else None


def resolve_repo(cwd):
    if not cwd or not os.path.isdir(cwd):
        return None
    try:
        out = subprocess.run(["git", "-C", cwd, "remote", "get-url", "origin"], capture_output=True,
                             text=True, timeout=2, check=True).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    return normalize_remote(out)


def _jsonl_files(roots, start):
    cutoff = start.timestamp()
    for root in roots:
        for dirpath, _, names in os.walk(root):
            for name in sorted(names):
                path = os.path.join(dirpath, name)
                try:
                    if name.endswith(".jsonl") and os.path.getmtime(path) >= cutoff:
                        yield path
                except OSError:
                    continue


def _rows(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    yield row
    except OSError:
        return


def _session(table, sid):
    return table.setdefault(sid, {"events": [], "cwd": None, "branch": None, "repo_hint": None, "models": {}})


def scan_claude(roots, start, end):
    table, best = {}, {}
    for path in _jsonl_files(roots, start):
        for row in _rows(path):
            ts = parse_ts(row.get("timestamp"))
            if ts is None or not start <= ts < end:
                continue
            sid = str(row.get("sessionId") or Path(path).stem)
            rec = _session(table, sid)
            rec["events"].append(ts)
            rec["cwd"] = rec["cwd"] or row.get("cwd")
            rec["branch"] = rec["branch"] or row.get("gitBranch")
            msg = row.get("message")
            usage = msg.get("usage") if isinstance(msg, dict) else None
            if not isinstance(usage, dict):
                continue
            use = {"input": _int(usage.get("input_tokens")), "output": _int(usage.get("output_tokens")),
                   "cache_read": _int(usage.get("cache_read_input_tokens")),
                   "cache_write": _int(usage.get("cache_creation_input_tokens"))}
            key = (sid, msg.get("id") or "%s:%s" % (path, ts))
            if key not in best or use["output"] > best[key][1]["output"]:
                best[key] = (str(msg.get("model") or "unknown"), use)
    for (sid, _), (model, use) in best.items():
        slot = table[sid]["models"].setdefault(model, dict(ZERO))
        for k, v in use.items():
            slot[k] += v
    return table


def _codex_totals(info):
    tot = (info or {}).get("total_token_usage") if isinstance(info, dict) else None
    if not isinstance(tot, dict):
        return None
    return {"input": _int(tot.get("input_tokens")), "cache_read": _int(tot.get("cached_input_tokens")),
            "cache_write": _int(tot.get("cache_write_input_tokens")), "output": _int(tot.get("output_tokens"))}


def scan_codex(roots, start, end):
    table = {}
    for path in _jsonl_files(roots, start):
        sid, cwd, branch, hint, model = Path(path).stem, None, None, None, "unknown"
        base = final = final_model = None
        events = []
        for row in _rows(path):
            payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
            if row.get("type") == "session_meta":
                sid = str(payload.get("id") or sid)
                cwd = payload.get("cwd")
                git = payload.get("git") if isinstance(payload.get("git"), dict) else {}
                branch, hint = git.get("branch"), git.get("repository_url")
            elif row.get("type") == "turn_context" and payload.get("model"):
                model = str(payload["model"])
            ts = parse_ts(row.get("timestamp"))
            if ts is None:
                continue
            if start <= ts < end:
                events.append(ts)
            if row.get("type") == "event_msg" and payload.get("type") == "token_count":
                totals = _codex_totals(payload.get("info"))
                if totals is None:
                    continue
                if ts < start:
                    base = totals
                if ts < end:
                    final, final_model = totals, model
        if not events:
            continue
        rec = _session(table, sid)
        rec["events"] += events
        rec["cwd"], rec["branch"], rec["repo_hint"] = rec["cwd"] or cwd, rec["branch"] or branch, rec["repo_hint"] or hint
        if final:
            base = base or ZERO
            d = {k: max(final[k] - base[k], 0) for k in ZERO}
            d["input"] = max(d["input"] - d["cache_read"], 0)
            slot = rec["models"].setdefault(final_model, dict(ZERO))
            for k, v in d.items():
                slot[k] += v
    return table


def _env_roots(var, sub):
    value = os.environ.get(var)
    return [os.path.join(value, sub)] if value else []


TOOLS = {
    "claude": (lambda: _env_roots("CLAUDE_CONFIG_DIR", "projects") + [os.path.expanduser("~/.claude/projects")], scan_claude),
    "codex": (lambda: _env_roots("CODEX_HOME", "sessions") + [os.path.expanduser("~/.codex/sessions")], scan_codex),
}


def _active_sec(events, idle):
    events = sorted(events)
    return int(sum(g for g in ((b - a).total_seconds() for a, b in zip(events, events[1:])) if g <= idle))


def collect(start, end, claude_roots, codex_roots, idle_gap_sec, machine, now=None, resolver=resolve_repo):
    start, end = parse_ts(start), parse_ts(end)
    roots = {"claude": claude_roots, "codex": codex_roots}
    cache, sessions = {}, []
    for tool, (_, scan) in TOOLS.items():
        existing = [r for r in roots.get(tool) or [] if os.path.isdir(r)]
        for sid, rec in scan(existing, start, end).items():
            if not rec["events"]:
                continue
            cwd = rec["cwd"]
            if cwd not in cache:
                cache[cwd] = resolver(cwd)
            branch = rec["branch"] if rec["branch"] not in (None, "", "HEAD") else None
            sessions.append({
                "tool": tool, "session_id": sid, "repo": cache[cwd] or normalize_remote(rec["repo_hint"]),
                "branch": branch, "first_at": fmt_ts(min(rec["events"])), "last_at": fmt_ts(max(rec["events"])),
                "active_sec": _active_sec(rec["events"], idle_gap_sec),
                "models": {m: rec["models"][m] for m in sorted(rec["models"])}})
    sessions.sort(key=lambda s: (s["tool"], s["session_id"]))
    return {"schema": SCHEMA, "machine": machine, "generated_at": now or fmt_ts(datetime.now(timezone.utc)),
            "window": {"start": fmt_ts(start), "end": fmt_ts(end)}, "idle_gap_sec": idle_gap_sec, "sessions": sessions}


def machine_slug(machine):
    return re.sub(r"[^a-z0-9]+", "-", machine.lower()).strip("-") or "unknown"


def _has_credentials(remote):
    if re.match(r"^[a-z]+://[^/]*@", remote or "") and not remote.startswith("ssh://"):
        return True
    return bool(re.match(r"^[^@/:]+:[^@/]+@", remote or "")) and "://" not in remote


def _write_atomic(path, text):
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".usage-")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, path)


def _parser():
    p = argparse.ArgumentParser(description="Summarize local coding-agent session logs into a usage feed.")
    p.add_argument("--since", help="ISO-8601 UTC window start (default: 14 days before --until)")
    p.add_argument("--until", help="ISO-8601 UTC window end, exclusive (default: now)")
    p.add_argument("--claude-root", action="append", help="Claude projects dir (repeatable)")
    p.add_argument("--codex-root", action="append", help="Codex sessions dir (repeatable)")
    p.add_argument("--machine", default=None, help="machine label (default: hostname)")
    p.add_argument("--idle-gap-sec", type=int, default=300)
    p.add_argument("--output", help="write the feed JSON here atomically (default: print)")
    p.add_argument("--publish-remote", default="", help="git remote receiving dashboards/prw/usage/<machine-slug>.json")
    p.add_argument("--publish-branch", default="main")
    return p


def main(argv=None):
    args = _parser().parse_args(argv)
    if _has_credentials(args.publish_remote):
        print("publish remote must not embed credentials; use an SSH remote or a credential helper", file=sys.stderr)
        return 2
    end = parse_ts(args.until) if args.until else datetime.now(timezone.utc)
    start = parse_ts(args.since) if args.since else (end - timedelta(days=14) if end else None)
    if start is None or end is None:
        print("invalid --since/--until", file=sys.stderr)
        return 2
    machine = args.machine or socket.gethostname()
    feed = collect(fmt_ts(start), fmt_ts(end), args.claude_root or TOOLS["claude"][0](),
                   args.codex_root or TOOLS["codex"][0](), args.idle_gap_sec, machine)
    text = json.dumps(feed, sort_keys=True, separators=(",", ":")) + "\n"
    if args.output:
        _write_atomic(args.output, text)
    elif not args.publish_remote:
        sys.stdout.write(text)
    if args.publish_remote:
        slug = machine_slug(machine)
        fallback = os.path.join(tempfile.gettempdir(), "prw-local-usage-%s.json" % slug)
        return publish(text, args.publish_remote, args.publish_branch, fallback,
                       path="dashboards/prw/usage/%s.json" % slug, message="prw usage feed: %s" % slug)
    return 0


if __name__ == "__main__":
    sys.exit(main())
