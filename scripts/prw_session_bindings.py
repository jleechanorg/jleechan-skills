"""Join agent sessions to PRs through the hook-written session binding ledger.

Ledger format: one JSON object per line (see the session-to-PR binding design).
`load` builds, per session, a timeline of the active PR; `binding_at` looks up
the active PR at an instant.  Never raises on ledger content.
"""

from __future__ import annotations

import json
import re
from bisect import bisect_right
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

_PR_RE = re.compile(r"^([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)#([0-9]+)$")


def _parse_ts(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        return None
    return dt.astimezone(timezone.utc)


def _clean_record(obj):
    """Return (ts, session, kind, pr, repo, branch, source, ts_text) or None when malformed."""
    if not isinstance(obj, dict) or obj.get("v") != 1:
        return None
    ts = _parse_ts(obj.get("ts"))
    session = obj.get("session_id")
    kind = obj.get("kind")
    if ts is None or not isinstance(session, str) or not session or not isinstance(kind, str):
        return None
    pr = obj.get("pr")
    if kind == "pr_binding":
        if not isinstance(pr, str) or not _PR_RE.match(pr):
            return None
    repo = obj.get("repo") if isinstance(obj.get("repo"), str) else None
    branch = obj.get("branch") if isinstance(obj.get("branch"), str) else None
    source = obj.get("source") if isinstance(obj.get("source"), str) else None
    return ts, session, kind, pr if kind == "pr_binding" else None, repo, branch, source, obj["ts"]


def load(paths: Iterable) -> tuple[dict, dict]:
    """Return (index, stats).  index maps session_id -> (timestamps, active PRs)."""
    stats = {
        "session_binding_records": 0,
        "session_binding_malformed": 0,
        "session_binding_missing_files": 0,
    }
    per_session: dict[str, list] = {}
    for path in paths or ():
        try:
            handle = open(Path(path), "r", encoding="utf-8", errors="replace")
        except OSError:
            stats["session_binding_missing_files"] += 1
            continue
        with handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except ValueError:
                    stats["session_binding_malformed"] += 1
                    continue
                rec = _clean_record(obj)
                if rec is None:
                    stats["session_binding_malformed"] += 1
                    continue
                stats["session_binding_records"] += 1
                per_session.setdefault(rec[1], []).append(rec)

    index = {}
    for session, recs in per_session.items():
        recs.sort(key=lambda r: r[0])  # stable: file order breaks ties
        times, states = [], []
        active = None  # (pr, repo, branch)
        for ts, _s, kind, pr, repo, branch, source, ts_text in recs:
            if kind == "pr_binding":
                active = (pr, pr.split("#", 1)[0], branch, ts_text, source)
            elif kind == "branch" and active is not None:
                _pr, bound_repo, bound_branch = active[:3]
                if repo is not None and repo != bound_repo:
                    active = None
                elif repo == bound_repo and branch is not None and bound_branch is not None \
                        and branch != bound_branch:
                    active = None
            else:
                continue
            times.append(ts)
            states.append((active[0], active[3], active[4]) if active else None)
        index[session] = (times, states)
    return index, stats


def binding_record_at(index: dict, session_id, at: datetime):
    """(pr, ledger ts text, source) of the pr_binding record active at `at`, or None."""
    if not session_id or not isinstance(session_id, str) or at is None:
        return None
    entry = index.get(session_id)
    if not entry or at.tzinfo is None:
        return None
    times, states = entry
    pos = bisect_right(times, at)
    return states[pos - 1] if pos else None


def binding_at(index: dict, session_id, at: datetime):
    """Active `owner/name#N` for the session at instant `at`, or None."""
    found = binding_record_at(index, session_id, at)
    return found[0] if found else None
