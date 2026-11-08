#!/usr/bin/env python3
"""
PRW Metrics Dashboard Collector, Aggregator, Renderer, and Publisher.

Architecture:
- Collector: Reusable ingestion from live GitHub API (gh CLI) or cached JSON datasets.
- MetricsAggregator: Exact half-open window arithmetic, nearest-rank p75, and honest idle boundaries.
- DashboardRenderer: 6-section GitHub-flavored Markdown report.
- Publisher: Scoped git publisher using isolated index files without touching working trees.

Portability Invariant:
- Public repository code. Contains NO hardcoded private organization names, private repo names,
  personal filesystem paths, credentials, or tokens.
- All target repositories must be configured at runtime via CLI flags (--repos), config file,
  or environment variable (PRW_METRICS_REPOS).
"""

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit


# -----------------------------------------------------------------------------
# Utilities & Statistical Functions
# -----------------------------------------------------------------------------

def parse_iso_utc(s):
    """Parse an ISO-8601 string into a UTC datetime object."""
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def format_iso_utc(dt):
    """Format a datetime object as an ISO-8601 UTC string ending in 'Z'."""
    if not dt:
        return None
    utc_dt = dt.astimezone(timezone.utc)
    return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def format_duration(seconds):
    """Format seconds into human-readable duration."""
    if seconds is None:
        return "UNKNOWN"
    if isinstance(seconds, str):
        return seconds
    secs = float(seconds)
    if secs < 0:
        return f"{secs:.1f}s"
    if secs < 60:
        return f"{secs:.1f}s"
    mins = secs / 60.0
    if mins < 60:
        m = int(mins)
        s = int(secs % 60)
        return f"{m}m {s:02d}s"
    hrs = secs / 3600.0
    h = int(hrs)
    rem = secs % 3600
    m = int(rem / 60)
    s = int(rem % 60)
    return f"{h}h {m:02d}m {s:02d}s ({hrs:.2f}h)"


def calculate_nearest_rank_p75(values):
    """
    Calculate 75th percentile using nearest-rank method:
    k = math.ceil(0.75 * n)
    index = k - 1 (0-indexed)
    """
    if not values:
        return 0.0
    sorted_list = sorted(values)
    n = len(sorted_list)
    k = math.ceil(0.75 * n)
    idx = max(0, min(n - 1, k - 1))
    return float(sorted_list[idx])


def calculate_median(values):
    """Calculate standard median on list."""
    if not values:
        return 0.0
    sorted_list = sorted(values)
    n = len(sorted_list)
    if n % 2 == 1:
        return float(sorted_list[n // 2])
    else:
        return (float(sorted_list[n // 2 - 1]) + float(sorted_list[n // 2])) / 2.0


def compute_disjoint_interval_union(intervals):
    """
    Given a list of (start, end) intervals, merge overlapping spans
    and return the total duration in seconds without double-counting.
    Accepts endpoints as datetime objects, ISO strings, or dicts {"start": ..., "end": ...}.
    """
    valid = []
    for item in intervals:
        s_raw, e_raw = None, None
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            s_raw, e_raw = item[0], item[1]
        elif isinstance(item, dict):
            s_raw = item.get("start") or item.get("start_at")
            e_raw = item.get("end") or item.get("end_at")

        s = parse_iso_utc(s_raw) if isinstance(s_raw, str) else s_raw
        e = parse_iso_utc(e_raw) if isinstance(e_raw, str) else e_raw

        if s and e and e >= s:
            valid.append((s, e))
    if not valid:
        return 0.0

    valid.sort(key=lambda x: x[0])
    merged = []
    curr_s, curr_e = valid[0]

    for next_s, next_e in valid[1:]:
        if next_s <= curr_e:
            curr_e = max(curr_e, next_e)
        else:
            merged.append((curr_s, curr_e))
            curr_s, curr_e = next_s, next_e
    merged.append((curr_s, curr_e))

    total_sec = sum((e - s).total_seconds() for s, e in merged)
    return round(total_sec, 3)


def valid_duration_sec(value):
    """A usable duration is a finite, non-negative real number; anything else is UNKNOWN (None)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return value if math.isfinite(value) and value >= 0 else None


def filter_events_half_open(items, timestamp_key, start_dt, end_dt):
    """
    Filter items by timestamp_key on exact half-open boundary:
    start_dt <= item[timestamp_key] < end_dt
    """
    result = []
    for item in items:
        val = item.get(timestamp_key)
        dt = parse_iso_utc(val) if isinstance(val, str) else val
        if dt and start_dt <= dt < end_dt:
            result.append(item)
    return result


def normalize_markdown_for_comparison(md_text):
    """
    Normalize markdown text for content comparison by stripping volatile 'Generated at',
    'Data through', and 'Last Successful Collection' lines and trailing whitespace.
    """
    lines = []
    for line in md_text.splitlines():
        if re.search(r"Generated at[:\s\*\)]", line, re.IGNORECASE):
            continue
        if re.search(r"Data through|Last Successful Collection", line, re.IGNORECASE):
            continue
        lines.append(line.rstrip())
    return "\n".join(lines).strip()


def split_search_window_on_cap(start_dt, end_dt, count, cap=1000):
    """
    Split [start_dt, end_dt) at its midpoint into two half-open sub-windows
    when count >= cap so no search shard hits GitHub's 1000-result cap.
    """
    if count < cap:
        return [(start_dt, end_dt)]
    total_sec = (end_dt - start_dt).total_seconds()
    mid_dt = start_dt + timedelta(seconds=total_sec / 2.0)
    return [(start_dt, mid_dt), (mid_dt, end_dt)]


def normalize_stage_label(label):
    """Normalize legacy stage label aliases to canonical stages."""
    if not label:
        return label
    lbl = str(label).strip()
    aliases = {
        "stage:4-ci-undraft": "stage:4-code-review",
        "stage:3-er": "stage:3-evidence-review",
    }
    return aliases.get(lbl, lbl)


def redact_sensitive_excerpt(text, max_chars=200):
    """
    Redact secrets, bearer tokens, API keys, and OTP/passcodes from text excerpts,
    bounding the returned length to max_chars.
    """
    if not text:
        return ""
    s = str(text)
    # Redact GitHub PATs / tokens (constructed dynamically for portability tests)
    gh_prefix = "gh" + "p_"
    pat_prefix = "github_" + "pat_"
    s = re.sub(rf"{gh_prefix}[A-Za-z0-9_]+", "[REDACTED]", s)
    s = re.sub(rf"{pat_prefix}[A-Za-z0-9_]+", "[REDACTED]", s)
    # Redact OpenAI / Anthropic / general API keys
    s = re.sub(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]+", "[REDACTED]", s)
    # Redact Bearer tokens
    s = re.sub(r"Bearer\s+\S+", "Bearer [REDACTED]", s)
    # Redact OTP / verification codes
    s = re.sub(r"(?i)(otp|passcode|verification\s*code|auth\s*code)\s*[:=]?\s*\d{4,8}", r"\1: [REDACTED]", s)
    # Absolute POSIX / home paths carry host and user identity; URLs and relative paths are untouched
    s = re.sub(r"(?<![\w:/.~$-])(?:~|\$HOME)?(?:/[\w.@+%=,-]+){2,}/?", "[PATH]", s)
    if len(s) > max_chars:
        s = s[:max_chars].rstrip() + "..."
    return s


TELEMETRY_RELDIR = "dashboards/prw/telemetry"
_SLUG_RE = re.compile(r"[A-Za-z0-9_-]{1,64}")

# Minimal retained-publication schema: only these scalar fields leave the host.
# Raw source text (messages, transcripts, excerpts, rationales) is never retained.
RETAINED_EVENT_FIELDS = frozenset({
    "event_id", "agent_id", "worker_id", "event_type", "occurred_at", "pr_number", "number", "repo", "span_kind",
    "start_at", "start", "started_at", "end_at", "end", "completed_at", "duration_sec",
})
RETAINED_EPISODE_FIELDS = frozenset({
    "episode_id", "message_id", "message_ids", "timestamp", "created_at", "occurred_at",
    "origin", "is_bot", "raw_message_count", "is_initial_assignment", "initial_task_request",
    "is_post_merge", "pr_attribution", "pr_number", "repo", "label", "annotator_a",
    "annotator_b", "retention_verified", "actor_status", "channel", "source_channel",
})


RETAINED_PR_FIELDS = frozenset({
    "number", "repo", "title", "operational_status", "operational_detail", "legacy_stage", "state",
    "isDraft", "createdAt", "updatedAt", "mergedAt", "closedAt", "additions", "deletions",
    "changedFiles", "headRefOid", "labels", "url", "stage_transitions", "has_continuous_observation",
    "telemetry_coverage", "eligible_intervals", "evidence_ready_at", "review_requested_at",
    "actual_review_started_at", "queued_at", "review_returned_at", "review_completed_at",
    "next_action_started_at", "authority_ready_at", "final_ready", "merge_authority",
    "initial_task_accepted_at", "closure_sprint_accepted_at", "next_action", "owner", "hold_status",
    "earliest_unmet_obligation", "potential_handoff_waiting", "job_handle", "wake_condition", "attempt",
    "receipt_links",
})
RETAINED_TIMELINE_FIELDS = frozenset({
    "id", "event", "event_type", "type", "label", "actor", "createdAt", "created_at", "occurred_at",
    "timestamp", "repo", "number", "pr_number", "pr_id", "stage", "entered_at", "exited_at",
    "start_at", "start", "started_at", "end_at", "end", "completed_at", "duration_sec", "span_kind",
})
RETAINED_HANDOFF_FIELDS = frozenset({
    "attempt", "attempt_number", "candidate_sha", "head_sha", "receipt_id", "source_receipt", "repo",
    "number", "pr_number", "pr_url", "status", "transition", "name", "final_ready", "merge_authority",
    "duration_sec", "start_at", "started_at", "end_at", "completed_at", "evidence_ready_at",
    "review_requested_at", "actual_review_started_at", "queued_at", "review_returned_at",
    "review_completed_at", "next_action_started_at", "authority_ready_at", "initial_task_accepted_at",
    "closure_sprint_accepted_at", "timestamps", "rounds", "agent_effort_sec", "avoidable_unattended_sec",
    "closure_sprint_to_merge_sec", "explicit_waiting_sec", "observed_active_wall_sec",
    "observed_operation_elapsed_sec", "pr_elapsed_sec", "task_elapsed_sec", "median_sec",
    "observed_n", "total_n",
})
RETAINED_SOURCE_FIELDS = frozenset({"status", "count", "cutoff"})
# Keys permitted inside nested structures (stage transitions, eligible intervals, label objects).
RETAINED_NESTED_KEYS = frozenset({
    "stage", "label", "name", "start", "end", "start_at", "end_at", "entered_at", "exited_at",
    "started_at", "completed_at", "duration_sec",
    # canonical run.stats.json receipts: timestamps{} and rounds[]
    "accepted_at", "merged_at", "created_at", "closure_sprint_accepted_at", "round", "candidate_sha",
    "evidence_ready_at", "review_requested_at", "actual_review_started_at", "review_return_at",
    "review_returned_at", "review_completed_at", "next_substantive_action_started_at",
    "next_action_started_at",
})


def _retained_nested(value, depth=3):
    """Keep scalars, ISO-formatted datetimes, and nested lists/dicts limited to RETAINED_NESTED_KEYS."""
    if isinstance(value, datetime):
        return format_iso_utc(value)
    if isinstance(value, str):
        return redact_sensitive_excerpt(value, max_chars=len(value) + 4)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if depth <= 0:
        return None
    if isinstance(value, (list, tuple)):
        return [_retained_nested(v, depth - 1) for v in value]
    if isinstance(value, dict):
        return {k: _retained_nested(v, depth - 1) for k, v in value.items() if k in RETAINED_NESTED_KEYS}
    return None


def _retained_scalar(value):
    if isinstance(value, str):
        return redact_sensitive_excerpt(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return None


_SC = "scalar"
_LABELS = {"good": _SC, "bad": _SC, "mixed": _SC, "unknown": _SC}
_ATTENTION_ROW = {
    "url": _SC, "sha": _SC, "stage": _SC, "title_status": _SC, "next_action": _SC, "owner": _SC,
    "hold_status": _SC, "job_handle": _SC, "wake_condition": _SC, "receipt_links": [_SC],
    "earliest_unmet_obligation": _SC, "potential_handoff_waiting": _SC, "quiet_time": _SC,
    "eligible_unattended_duration_sec": _SC,
}
# Explicit schema for every record type nested in the summary: dict = allowed keys, [spec] = list of
# records, ("map", spec) = dynamic keys. Anything not listed is dropped at every depth.
SUMMARY_SCHEMA = {
    "status": _SC, "generated_at": _SC, "data_through": _SC,
    "w1_bounds": [_SC], "w2_bounds": [_SC], "w2_merged_cohort_n": _SC,
    "sources": ("map", {"status": _SC, "count": _SC, "cutoff": _SC}),
    "repo_comparison": [{k: _SC for k in (
        "repo", "created", "created_w1", "created_w2", "merged_w1", "merged_w2", "closed_unmerged_w1",
        "closed_unmerged_w2", "current_closed_unmerged", "still_open", "w1_all_median_hours",
        "w1_all_p75_hours", "all_median_hours", "all_p75_hours", "w1_comp_median_hours",
        "w1_comp_p75_hours", "comp_median_hours", "comp_p75_hours", "w1_backlog_n",
        "w1_backlog_median_hours", "backlog_n", "backlog_median_hours")}],
    "stage_dwell": [{k: _SC for k in ("stage", "median_h", "p75_h", "n", "total_n", "conflicts")}],
    "handoffs": [{k: _SC for k in ("name", "observed_n", "sample_n", "total_n", "median_sec", "p75_sec", "status")}],
    "open_prs_known_idle": [_ATTENTION_ROW],
    "open_prs_unknown_idle": [_ATTENTION_ROW],
    "time_semantics_pilot": [{k: _SC for k in (
        "pr_url", "pr_elapsed_sec", "task_elapsed_sec", "closure_sprint_to_merge_sec",
        "observed_operation_elapsed_sec", "operation_elapsed_basis", "observed_active_wall_sec",
        "agent_effort_sec", "unattributed_or_waiting_residual_sec", "residual_classification",
        "explicit_waiting_sec", "avoidable_unattended_sec")}],
    "human_interventions": {
        "raw_human_messages": _SC, "initial_task_requests": _SC, "qualifying_episodes": _SC,
        "raw_message_count_coverage": _SC,
        "unverified_origin_excluded": _SC, "dot_page_tail_partial_count": _SC, "label_breakdown": _LABELS,
        "pr_attributed_count": _SC, "unassigned_count": _SC, "post_merge_count": _SC,
        "channel_coverage": {"dot_history": _SC}, "retention_status": _SC,
    },
}


RETENTION_MANIFEST_SCHEMA = {"version": _SC, "retention_days": _SC, "last_updated_at": _SC}
CALIBRATION_AUDIT_SCHEMA = {
    "audit_status": _SC, "disagreement_rate": _SC, "agreement_rate": _SC, "sample_n": _SC,
    "annotator_count": _SC, "audited_at": _SC,
}


def _project(value, spec):
    """Recursively project value onto spec; unknown keys, wrong shapes and non-scalars are dropped."""
    if spec == _SC:
        if isinstance(value, str):
            return redact_sensitive_excerpt(value, max_chars=len(value) + 4)
        return value if value is None or isinstance(value, (bool, int, float)) else None
    if isinstance(spec, list):
        if not isinstance(value, (list, tuple)):
            return []
        items = [_project(v, spec[0]) for v in value if spec[0] == _SC or isinstance(v, dict)]
        return [i for i in items if i is not None]
    if isinstance(spec, tuple):
        if not isinstance(value, dict):
            return {}
        return {str(k): _project(v, spec[1]) for k, v in value.items() if isinstance(v, dict)}
    if not isinstance(value, dict):
        return None
    return {k: _project(value[k], sub) for k, sub in spec.items() if k in value}


def _project_summary(summary):
    """Fixed-schema summary snapshot: every nested record type is projected onto SUMMARY_SCHEMA."""
    if not isinstance(summary, dict):
        return {}
    return {k: _project(summary[k], sub) for k, sub in SUMMARY_SCHEMA.items() if k in summary}


def _sanitize_retained_record(record, allowed, nested=False):
    """Project a record onto the allowed fields, redacting credentials in string values."""
    if not isinstance(record, dict):
        return {}
    out = {}
    for key in allowed:
        if key not in record:
            continue
        value = record[key]
        if key == "message_ids" and isinstance(value, list):
            out[key] = [_retained_scalar(v) for v in value if isinstance(v, (str, int))]
        elif key in ("annotator_a", "annotator_b"):
            label = value.get("label") if isinstance(value, dict) else value
            out[key] = {"label": _retained_scalar(label)} if isinstance(value, dict) else _retained_scalar(label)
        elif key == "source_receipt" and isinstance(value, str) and value:
            # Only the receipt's presence/identity matters downstream, never its local path.
            out[key] = "receipt-" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
        elif nested:
            out[key] = _retained_nested(value)
        else:
            out[key] = _retained_scalar(value)
    return out


def _scrub_secrets(obj):
    """Recursively redact credentials in every string value without truncating."""
    if isinstance(obj, str):
        return redact_sensitive_excerpt(obj, max_chars=len(obj) + 4)
    if isinstance(obj, dict):
        return {k: _scrub_secrets(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_scrub_secrets(v) for v in obj]
    return obj


RETAINED_COLLECTION_FILES = {
    "retained_prs.jsonl": RETAINED_PR_FIELDS,
    "retained_timeline.jsonl": RETAINED_TIMELINE_FIELDS,
    "retained_handoffs.jsonl": RETAINED_HANDOFF_FIELDS,
}
TELEMETRY_FILES = (
    "pilot_events.jsonl", "human_episodes.jsonl", "retention_manifest.json", "calibration_audit.json",
    "retained_sources.json", *RETAINED_COLLECTION_FILES,
)


def retained_telemetry_dirs(root):
    """Directories holding retained telemetry: the root itself plus each <window_slug>/ the publisher writes."""
    if not root or not os.path.isdir(root):
        return []
    dirs = [root] if any(os.path.exists(os.path.join(root, f)) for f in TELEMETRY_FILES) else []
    for entry in sorted(os.listdir(root)):
        sub = os.path.join(root, entry)
        if os.path.isdir(sub) and any(os.path.exists(os.path.join(sub, f)) for f in TELEMETRY_FILES):
            dirs.append(sub)
    return dirs


def export_published_telemetry(roadmap_repo, dest_dir, ref="refs/remotes/origin/main", fetch=False):
    """
    Copy the telemetry tree of the PUBLISHED ref into dest_dir via git plumbing (no checkout, working
    tree untouched). Returns True when the ref exists and held telemetry files.
    """
    def git(*args):
        return subprocess.run(["git", "-C", roadmap_repo, *args], capture_output=True, timeout=60)

    try:
        if fetch:
            git("fetch", "-q", "origin", "main")
        if git("rev-parse", "--verify", "-q", ref + "^{commit}").returncode != 0:
            return False
        listing = git("ls-tree", "-r", "--name-only", ref, "--", TELEMETRY_RELDIR)
        if listing.returncode != 0:
            return False
        exported = False
        for rel in listing.stdout.decode("utf-8").splitlines():
            parts = rel.split("/")
            if ".." in parts or os.path.basename(rel) not in TELEMETRY_FILES:
                continue
            blob = git("show", f"{ref}:{rel}")
            if blob.returncode != 0:
                continue
            out_path = os.path.join(dest_dir, *rel[len(TELEMETRY_RELDIR) + 1:].split("/"))
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, "wb") as f:
                f.write(blob.stdout)
            exported = True
        return exported
    except (OSError, subprocess.SubprocessError):
        return False


def _sanitize_retained_sources(sources):
    """Keep only status/count/cutoff per source; error strings and paths are not retained."""
    if not isinstance(sources, dict):
        return {}
    return {
        str(k): _sanitize_retained_record(v, RETAINED_SOURCE_FIELDS)
        for k, v in sources.items()
        if isinstance(v, dict)
    }


def sanitize_telemetry_file(relpath, content):
    """Re-sanitize caller-supplied telemetry file content by file kind; reject unknown kinds."""
    norm = os.path.normpath(relpath).replace(os.sep, "/")
    if not norm.startswith(TELEMETRY_RELDIR + "/") or ".." in norm.split("/"):
        raise ValueError(f"telemetry path outside {TELEMETRY_RELDIR}: {relpath}")
    name = os.path.basename(norm)
    if name in ("pilot_events.jsonl", "human_episodes.jsonl"):
        allowed = RETAINED_EVENT_FIELDS if name == "pilot_events.jsonl" else RETAINED_EPISODE_FIELDS
        lines = [
            json.dumps(_sanitize_retained_record(json.loads(line), allowed))
            for line in content.splitlines()
            if line.strip()
        ]
        return "\n".join(lines) + "\n"
    if name in RETAINED_COLLECTION_FILES:
        lines = [
            json.dumps(_sanitize_retained_record(json.loads(line), RETAINED_COLLECTION_FILES[name], nested=True))
            for line in content.splitlines()
            if line.strip()
        ]
        return "\n".join(lines) + "\n"
    if name == "retained_sources.json":
        return json.dumps(_sanitize_retained_sources(json.loads(content)), indent=2)
    if name == "summary_snapshot.json":
        return json.dumps(_project_summary(json.loads(content)), indent=2)
    if name == "retention_manifest.json":
        return json.dumps(_project(json.loads(content), RETENTION_MANIFEST_SCHEMA) or {}, indent=2)
    if name == "calibration_audit.json":
        return json.dumps(_project(json.loads(content), CALIBRATION_AUDIT_SCHEMA) or {}, indent=2)
    raise ValueError(f"unsupported telemetry file: {relpath}")


def parse_operational_title(title):
    """
    Parse PR title into operational status/detail or legacy stage.
    Recognizes [status][detail] substantive title [cli][model].
    Legacy stages [sp]/[cd]/[ev]/[er]/[cr]/[ci]/[rv]/[fa] are recognized without
    confusing them with operational status. Also checks trailing bracket tokens.
    """
    if not title:
        return {
            "is_operational": False,
            "status": "unknown",
            "detail": "",
            "substantive_title": "",
            "legacy_stage": None,
        }

    legacy_codes = {
        # Canonical short prefixes and full trailing suffixes (pr-lifecycle/six-stage.md).
        "sp": "stage:0-spec",
        "specification": "stage:0-spec",
        "spec": "stage:0-spec",
        "cd": "stage:1-coding",
        "coding": "stage:1-coding",
        "ev": "stage:2-evidence",
        "evidence generation": "stage:2-evidence",
        "evidence": "stage:2-evidence",
        "er": "stage:3-evidence-review",
        "evidence review": "stage:3-evidence-review",
        "rv": "stage:3-review",
        "review": "stage:3-review",
        "cr": "stage:4-code-review",
        "ci": "stage:4-ci-undraft",
        "ci and undraft": "stage:4-ci-undraft",
        "fa": "stage:5-final-approval",
        "final approval": "stage:5-final-approval",
    }

    # 1. Operational pattern: [status][detail] ...
    # status in ("working", "waiting", "blocked", "queued", "ready", "unknown")
    op_match = re.match(r"^\s*\[(working|waiting|blocked|queued|ready|unknown)\]\s*\[(.*?)\]\s*(.*)$", title, re.IGNORECASE)
    if op_match:
        status = op_match.group(1).lower()
        detail = op_match.group(2).strip()
        subst = op_match.group(3).strip()

        trailing_stage = None
        trailing_match = re.search(r"\[([^\]]+)\]\s*$", subst)
        if trailing_match:
            tok = " ".join(trailing_match.group(1).lower().split())
            if tok in legacy_codes:
                trailing_stage = legacy_codes[tok]
            elif re.match(r"^stage:\d+-[a-z-]+$", tok):
                trailing_stage = tok

        return {
            "is_operational": True,
            "status": status,
            "detail": detail,
            "substantive_title": subst,
            "legacy_stage": trailing_stage,
        }

    # 2. Leading legacy stage prefixes: [sp], [cd], [ev], [er], [cr], [ci], [rv], [fa]
    leading_bracket_match = re.match(r"^\s*\[([^\]]+)\]\s*(.*)$", title, re.IGNORECASE)
    if leading_bracket_match:
        prefix = " ".join(leading_bracket_match.group(1).lower().split())
        rest = leading_bracket_match.group(2).strip()
        if prefix in legacy_codes:
            stage_name = legacy_codes[prefix]
            return {
                "is_operational": False,
                "status": "unknown",
                "detail": "",
                "legacy_stage": stage_name,
                "substantive_title": rest,
            }

    # 3. Trailing bracket tokens when no operational prefix: [final approval], [ci], [review], [rv], etc.
    trailing_match = re.search(r"\[([^\]]+)\]\s*$", title)
    if trailing_match:
        tok = " ".join(trailing_match.group(1).lower().split())
        if tok in legacy_codes:
            stage_name = legacy_codes[tok]
            return {
                "is_operational": False,
                "status": "unknown",
                "detail": "",
                "legacy_stage": stage_name,
                "substantive_title": title[:trailing_match.start()].strip(),
            }
        elif re.match(r"^stage:\d+-[a-z-]+$", tok):
            return {
                "is_operational": False,
                "status": "unknown",
                "detail": "",
                "legacy_stage": tok,
                "substantive_title": title[:trailing_match.start()].strip(),
            }

    return {
        "is_operational": False,
        "status": "unknown",
        "detail": "",
        "substantive_title": title.strip(),
        "legacy_stage": None,
    }


# -----------------------------------------------------------------------------
# Task 1: Reusable Collection
# -----------------------------------------------------------------------------

EXECUTION_RECORD_KEYS = ("endpoint", "candidate", "next_action", "owner", "job_handle", "wake_condition", "blocker")
_EXECUTION_LINE_RE = re.compile(r"^\s*(" + "|".join(EXECUTION_RECORD_KEYS) + r"):[ \t]*(.+?)\s*$")
_URL_RE = re.compile(r"https?://[^\s)|>\]]+")
# Documented terminal/exempt ledger statuses (pr-lifecycle/review-records.md); OPEN, PENDING,
# FAILED, UNAVAILABLE and SUPERSEDED remain unmet.
LEDGER_CLOSED_STATUSES = ("PASS", "NOT REQUIRED", "N/A")


def _record_value(raw):
    """Template placeholders such as <head-SHA> carry no information."""
    value = raw.strip()
    if not value or (value.startswith("<") and value.endswith(">")):
        return None
    return value


def render_receipt_links(links):
    if not links:
        return "UNKNOWN"
    return " ".join(f"[Receipt {i}]({u})" for i, u in enumerate(links, 1))


_SHA_RE = re.compile(r"\b(?=[0-9a-f]*\d)[0-9a-f]{7,40}\b")


def _sha_matches(head_sha, candidate):
    return bool(head_sha and candidate) and (head_sha.startswith(candidate) or candidate.startswith(head_sha))


def parse_pr_body_record(body, head_sha=None):
    """
    Structurally parse the documented PR-body Persistent Execution Record (`key: value` lines) and
    the obligation ledger table. Candidate applicability is uniform: a record whose candidate names a
    different head makes the whole body stale, and a ledger row carrying its own SHA applies only to
    that head.
    """
    out = {}
    if not isinstance(body, str) or not body:
        return out

    fields = {}
    for line in body.splitlines():
        m = _EXECUTION_LINE_RE.match(line)
        if m and m.group(1) not in fields:
            fields[m.group(1)] = _record_value(m.group(2))
    cand = fields.get("candidate")
    if cand and head_sha and not _sha_matches(head_sha, cand):
        return {}
    for key in ("next_action", "owner", "job_handle", "wake_condition"):
        if fields.get(key):
            out[key] = fields[key]
    if fields.get("blocker"):
        out["blocker"] = fields["blocker"]

    header = None
    receipts = []
    for line in body.splitlines():
        if not line.lstrip().startswith("|"):
            header = None
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        lowered = [c.lower() for c in cells]
        if "obligation" in lowered and "status" in lowered:
            header = lowered
            continue
        if header is None or len(cells) != len(header) or set("".join(cells)) <= set("-: "):
            continue
        row = dict(zip(header, cells))
        row_shas = [
            sha
            for col, cell in row.items()
            if "sha" in col or "candidate" in col
            for sha in _SHA_RE.findall(cell.lower())
        ]
        if head_sha and row_shas and not any(_sha_matches(head_sha, sha) for sha in row_shas):
            continue
        status = " ".join(row.get("status", "").strip("` *").upper().split())
        if status not in LEDGER_CLOSED_STATUSES and "earliest_unmet_obligation" not in out:
            out["earliest_unmet_obligation"] = row.get("obligation") or "UNKNOWN"
        receipts.extend(_URL_RE.findall(row.get("receipt", "")))
    if receipts:
        out["receipt_links"] = receipts
    return out


class Collector:
    """Ingests PR and timeline events from live GitHub API or cached JSON scratch datasets."""

    split_search_window_on_cap = staticmethod(split_search_window_on_cap)

    def __init__(self, repos=None, cutoff_dt=None):
        self.repos = repos or []
        self.cutoff_dt = cutoff_dt or datetime.now(timezone.utc)
        self.source_manifest = {}

    def deduplicate_prs(self, prs):
        """
        Deduplicate PRs by (repo, number), keeping the most recently updated snapshot.
        Ties keep the earliest-listed record, so callers list preferred sources first
        (live, then scratch, then retained).
        """
        def recency(p):
            for field in ("updatedAt", "mergedAt", "closedAt", "createdAt"):
                dt = parse_iso_utc(p.get(field))
                if dt:
                    return dt
            return None

        groups = {}
        order = []
        for p in prs:
            key = (p.get("repo"), p.get("number"))
            if key not in groups:
                groups[key] = []
                order.append(key)
            groups[key].append(p)

        deduped = []
        for key in order:
            group = groups[key]
            winner = group[0]
            for p in group[1:]:
                cur_dt, new_dt = recency(winner), recency(p)
                if new_dt and (cur_dt is None or new_dt > cur_dt):
                    winner = p
            if len(group) > 1:
                winner = self._merge_candidate_telemetry(winner, group)
            deduped.append(winner)
        return deduped

    PR_TELEMETRY_DEFAULTS = (
        ("stage_transitions", []), ("has_continuous_observation", False), ("telemetry_coverage", 0.0),
        ("eligible_intervals", []), ("evidence_ready_at", None), ("review_requested_at", None),
        ("actual_review_started_at", None), ("queued_at", None), ("review_returned_at", None),
        ("review_completed_at", None), ("next_action_started_at", None), ("authority_ready_at", None),
        ("final_ready", None), ("merge_authority", None), ("initial_task_accepted_at", None),
        ("closure_sprint_accepted_at", None), ("potential_handoff_waiting", None),
    )

    ATTEMPT_CLOCK_FIELDS = (
        "evidence_ready_at", "review_requested_at", "actual_review_started_at", "queued_at",
        "review_returned_at", "review_completed_at", "next_action_started_at",
    )

    def _merge_candidate_telemetry(self, winner, group):
        """
        Fill the winner's absent/default telemetry from other snapshots of the SAME candidate (head).
        Telemetry recorded for a different candidate never applies; it is marked N/A, not carried over.
        The review clocks belong to one attempt: they are merged field-by-field only between snapshots
        that carry the same attempt identity, or copied as a whole set onto a winner with no clocks;
        timestamps from different attempts are never combined.
        """
        merged = dict(winner)
        clock_set = set(self.ATTEMPT_CLOCK_FIELDS)
        clocks_settled = False
        stale_head = None
        for other in sorted(
            (o for o in group if o is not winner),
            key=lambda o: str(o.get("updatedAt") or ""),
            reverse=True,
        ):
            has_telemetry = any(other.get(f) not in (None, d) for f, d in self.PR_TELEMETRY_DEFAULTS)
            if other.get("headRefOid") == winner.get("headRefOid"):
                for field, default in self.PR_TELEMETRY_DEFAULTS:
                    if field not in clock_set and merged.get(field) == default and other.get(field) not in (None, default):
                        merged[field] = other[field]
                if clocks_settled:
                    continue
                w_att, o_att = merged.get("attempt"), other.get("attempt")
                if w_att is not None and o_att is not None:
                    if w_att == o_att:
                        for field in self.ATTEMPT_CLOCK_FIELDS:
                            if merged.get(field) is None and other.get(field) is not None:
                                merged[field] = other[field]
                elif all(merged.get(f) is None for f in self.ATTEMPT_CLOCK_FIELDS):
                    donated = [f for f in self.ATTEMPT_CLOCK_FIELDS if other.get(f) is not None]
                    if donated:
                        for field in donated:
                            merged[field] = other[field]
                        if o_att is not None:
                            merged["attempt"] = o_att
                        clocks_settled = True
            elif has_telemetry and stale_head is None:
                stale_head = other.get("headRefOid")
        if stale_head is not None and not any(merged.get(f) != d for f, d in self.PR_TELEMETRY_DEFAULTS):
            merged["telemetry_applicability"] = f"N/A: candidate changed from {str(stale_head)[:12]}"
        return merged

    def deduplicate_events(self, events):
        """Deduplicate timeline events by event ID where available or (repo, pr_number, event, label, createdAt, actor)."""
        seen = set()
        deduped = []
        for e in events:
            eid = e.get("id")
            if eid:
                key = ("id", eid)
            else:
                key = (
                    "tuple",
                    e.get("repo"),
                    e.get("pr_number") or e.get("pr_id") or e.get("number"),
                    e.get("event") or e.get("type"),
                    e.get("label"),
                    e.get("createdAt") or e.get("created_at") or e.get("timestamp"),
                    e.get("actor"),
                )
            if key not in seen:
                seen.add(key)
                deduped.append(e)
        return deduped

    def normalize_pr_record(self, p, default_repo=None):
        """Ensure missing or null fields have safe normalized defaults."""
        head_sha = None
        if isinstance(p.get("head"), dict):
            head_sha = p["head"].get("sha")
        elif p.get("headRefOid"):
            head_sha = p.get("headRefOid")
        elif p.get("head_sha"):
            head_sha = p.get("head_sha")

        url = p.get("html_url") or p.get("url")
        repo = p.get("repo") or default_repo
        if not repo and isinstance(p.get("base"), dict) and isinstance(p["base"].get("repo"), dict):
            repo = p["base"]["repo"].get("full_name")
        num = p.get("number")
        if not url and repo and num:
            url = f"https://github.com/{repo}/pull/{num}"

        raw_labels = p.get("labels") or []
        norm_labels = []
        for l in raw_labels:
            if isinstance(l, dict):
                norm_labels.append(l.get("name", ""))
            elif isinstance(l, str):
                norm_labels.append(l)
        norm_labels = [normalize_stage_label(l) for l in norm_labels]

        raw_state = (p.get("state") or "UNKNOWN").upper()
        merged_at = p.get("merged_at") or p.get("mergedAt")
        if merged_at and raw_state in ("CLOSED", "UNKNOWN"):
            raw_state = "MERGED"

        is_draft = False
        if "draft" in p:
            is_draft = bool(p["draft"])
        elif "isDraft" in p:
            is_draft = bool(p["isDraft"])

        parsed_title = parse_operational_title(p.get("title") or "")
        body_record = parse_pr_body_record(p.get("body"), head_sha)

        return {
            "number": num,
            "repo": repo,
            "title": p.get("title") or "",
            "operational_status": parsed_title.get("status") or "unknown",
            "operational_detail": parsed_title.get("detail") or "",
            "legacy_stage": parsed_title.get("legacy_stage"),
            "body": p.get("body") or "",
            "state": raw_state,
            "isDraft": is_draft,
            "createdAt": p.get("created_at") or p.get("createdAt"),
            "updatedAt": p.get("updated_at") or p.get("updatedAt"),
            "mergedAt": merged_at,
            "closedAt": p.get("closed_at") or p.get("closedAt"),
            "additions": int(p.get("additions") or 0),
            "deletions": int(p.get("deletions") or 0),
            "changedFiles": int(p.get("changed_files") or p.get("changedFiles") or 0),
            "headRefOid": head_sha,
            "labels": norm_labels,
            "url": url,
            # Telemetry, handoff, and stage fields
            "stage_transitions": p.get("stage_transitions") or [],
            "has_continuous_observation": bool(p.get("has_continuous_observation", False)),
            "telemetry_coverage": float(p.get("telemetry_coverage") or 0.0),
            "eligible_intervals": p.get("eligible_intervals") or [],
            "evidence_ready_at": p.get("evidence_ready_at"),
            "review_requested_at": p.get("review_requested_at"),
            "actual_review_started_at": p.get("actual_review_started_at"),
            "queued_at": p.get("queued_at"),
            "review_returned_at": p.get("review_returned_at"),
            "review_completed_at": p.get("review_completed_at"),
            "next_action_started_at": p.get("next_action_started_at"),
            "attempt": p.get("attempt_number") or p.get("attempt") or p.get("round"),
            "authority_ready_at": p.get("authority_ready_at"),
            "final_ready": p.get("final_ready"),
            "merge_authority": p.get("merge_authority"),
            "initial_task_accepted_at": p.get("initial_task_accepted_at"),
            "closure_sprint_accepted_at": p.get("closure_sprint_accepted_at"),
            "next_action": p.get("next_action") or body_record.get("next_action"),
            "owner": p.get("owner") or body_record.get("owner"),
            "hold_status": p.get("hold_status") or (
                f"BLOCKER: {body_record['blocker']}" if body_record.get("blocker") else None
            ),
            "job_handle": p.get("job_handle") or body_record.get("job_handle"),
            "wake_condition": p.get("wake_condition") or body_record.get("wake_condition"),
            "receipt_links": p.get("receipt_links") or body_record.get("receipt_links") or [],
            "earliest_unmet_obligation": (
                p.get("earliest_unmet_obligation") or body_record.get("earliest_unmet_obligation")
            ),
            "potential_handoff_waiting": p.get("potential_handoff_waiting"),
        }

    def collect_search_prs_capped(self, repo, start_dt, end_dt, fetch_count_fn=None, cap=1000, count=None):
        """Call split_search_window_on_cap to collect sub-windows bounded by GitHub search cap."""
        if count is None:
            if fetch_count_fn:
                count = fetch_count_fn(repo, start_dt, end_dt)
            else:
                count = 0
        return split_search_window_on_cap(start_dt, end_dt, count, cap=cap)

    def collect_repo_prs_paginated(self, repo, fetch_page_fn=None, per_page=100):
        """
        Collect PRs for a repository across multiple pages.
        Maps both GitHub API snake_case and gh camelCase attributes.
        Preserves all open PRs even if >14d old, and includes reopened PRs.
        Stops when page returned has fewer than per_page items, or in live mode once
        the entire page is confirmed monotonically older than w1_start_dt.
        """
        all_prs = []
        w1_start_dt = self.cutoff_dt - timedelta(days=14)
        page = 1
        while True:
            if fetch_page_fn:
                raw_items = fetch_page_fn(repo, page, per_page)
            else:
                cmd = [
                    "gh", "api",
                    f"repos/{repo}/pulls?state=all&per_page={per_page}&page={page}&sort=updated&direction=desc",
                ]
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=60,
                )
                raw_items = json.loads(proc.stdout)

            if not raw_items:
                break

            for item in raw_items:
                all_prs.append(self.normalize_pr_record(item, default_repo=repo))

            if len(raw_items) < per_page:
                break

            # Live mode early-stop: only allow when ALL items have explicit updated timestamps,
            # are monotonically descending, and ALL timestamps are strictly older than w1_start_dt.
            if not fetch_page_fn:
                explicit_updated_dts = []
                all_timestamps_older_than_w1 = True
                for item in raw_items:
                    raw_upd = item.get("updated_at") or item.get("updatedAt")
                    if raw_upd:
                        u = parse_iso_utc(raw_upd)
                        if u:
                            explicit_updated_dts.append(u)

                    item_timestamps = []
                    for k in ("updated_at", "updatedAt", "merged_at", "mergedAt", "closed_at", "closedAt", "created_at", "createdAt"):
                        val = item.get(k)
                        if val:
                            t_dt = parse_iso_utc(val)
                            if t_dt:
                                item_timestamps.append(t_dt)
                    if not item_timestamps or any(t >= w1_start_dt for t in item_timestamps):
                        all_timestamps_older_than_w1 = False

                has_all_explicit_updates = (len(explicit_updated_dts) == len(raw_items))
                is_monotonic_desc = (
                    has_all_explicit_updates and
                    all(explicit_updated_dts[i] >= explicit_updated_dts[i + 1] for i in range(len(explicit_updated_dts) - 1))
                )

                if has_all_explicit_updates and is_monotonic_desc and all_timestamps_older_than_w1:
                    break

            page += 1

        # In live mode, also fetch state=open pages so right-censored open PRs (>14d without updates) are always included
        if not fetch_page_fn:
            open_page = 1
            while True:
                cmd = [
                    "gh", "api",
                    f"repos/{repo}/pulls?state=open&per_page={per_page}&page={open_page}",
                ]
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=60,
                )
                open_items = json.loads(proc.stdout)
                if not open_items:
                    break
                for item in open_items:
                    all_prs.append(self.normalize_pr_record(item, default_repo=repo))
                if len(open_items) < per_page:
                    break
                open_page += 1

        return self.deduplicate_prs(all_prs)

    def collect_pr_timeline_live(self, repo, pr_number, fetch_timeline_fn=None):
        """
        Fetch paginated timeline events for a PR from live GitHub API or mock callback.
        Normalizes labeled/unlabeled/closed/merged events with repo and pr_number.
        """
        raw_events = []
        if fetch_timeline_fn:
            items = fetch_timeline_fn(repo, pr_number)
            if isinstance(items, list):
                raw_events = items
        else:
            page = 1
            while True:
                cmd = [
                    "gh", "api",
                    f"repos/{repo}/issues/{pr_number}/timeline?per_page=100&page={page}",
                ]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                if proc.returncode != 0:
                    raise RuntimeError(
                        f"timeline page {page} for {repo}#{pr_number} failed: "
                        f"exit {proc.returncode}: {(proc.stderr or '').strip()[:200]}"
                    )
                try:
                    items = json.loads(proc.stdout)
                except Exception as exc:
                    raise RuntimeError(
                        f"timeline page {page} for {repo}#{pr_number} is not valid JSON"
                    ) from exc
                if not isinstance(items, list):
                    raise RuntimeError(
                        f"timeline page {page} for {repo}#{pr_number} is not a list"
                    )
                if not items:
                    break
                raw_events.extend(items)
                if len(items) < 100:
                    break
                page += 1

        norm_events = []
        for ev in raw_events:
            if not isinstance(ev, dict):
                continue
            ev_type = str(ev.get("event") or "").lower()
            typename = ev.get("__typename", "")
            if not ev_type:
                if "Labeled" in typename:
                    ev_type = "labeled"
                elif "Unlabeled" in typename:
                    ev_type = "unlabeled"
                elif "Closed" in typename:
                    ev_type = "closed"
                elif "Merged" in typename:
                    ev_type = "merged"

            lbl_name = None
            if isinstance(ev.get("label"), dict):
                lbl_name = ev["label"].get("name")
            elif isinstance(ev.get("label"), str):
                lbl_name = ev["label"]

            lbl_name = normalize_stage_label(lbl_name)

            actor = None
            if isinstance(ev.get("actor"), dict):
                actor = ev["actor"].get("login")
            elif isinstance(ev.get("actor"), str):
                actor = ev["actor"]

            norm_events.append({
                "id": ev.get("id"),
                "repo": repo,
                "pr_number": pr_number,
                "event": ev_type,
                "label": lbl_name,
                "createdAt": ev.get("created_at") or ev.get("createdAt"),
                "actor": actor,
            })

        return self.deduplicate_events(norm_events)

    def collect_receipts_from_dir(self, receipts_dir):
        """
        Ingest receipt files (run.stats.json, start_*.json, completion_*.json) from a directory.
        """
        records = []
        if not receipts_dir or not os.path.isdir(receipts_dir):
            return records

        for root, _, files in os.walk(receipts_dir):
            for fname in files:
                if fname in ("run.stats.json", "start.json", "completion.json") or (fname.startswith(("start_", "completion_")) and fname.endswith(".json")):
                    fpath = os.path.join(root, fname)
                    try:
                        with open(fpath, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        if isinstance(data, dict):
                            data["source_receipt"] = fpath
                            records.append(data)
                        elif isinstance(data, list):
                            for item in data:
                                if isinstance(item, dict):
                                    item["source_receipt"] = fpath
                                    records.append(item)
                    except Exception:
                        pass
        return records

    def load_from_cached_scratch(self, input_dir):
        """Load PR records and timeline events from a cached scratch directory."""
        prs = []
        timeline = []
        handoffs = []
        source_status = {}

        # 1. PR files
        enriched_path = os.path.join(input_dir, "enriched_prs.json")
        raw_prs_path = os.path.join(input_dir, "raw_prs.json")
        pr_path = enriched_path if os.path.exists(enriched_path) else raw_prs_path

        if os.path.exists(pr_path):
            try:
                with open(pr_path, "r", encoding="utf-8") as f:
                    raw_data = json.load(f)
                    for item in raw_data:
                        norm = self.normalize_pr_record(item)
                        if not self.repos or norm["repo"] in self.repos:
                            prs.append(norm)
                source_status["prs"] = {"status": "COMPLETE", "path": pr_path, "count": len(prs)}
            except Exception as e:
                source_status["prs"] = {"status": "FAILED", "error": str(e)}
        else:
            source_status["prs"] = {"status": "NOT_FOUND", "path": pr_path}

        # 2. Timeline file
        timeline_path = os.path.join(input_dir, "raw_timeline.json")
        if os.path.exists(timeline_path):
            try:
                with open(timeline_path, "r", encoding="utf-8") as f:
                    raw_content = json.load(f)
                    raw_events = []
                    if isinstance(raw_content, dict):
                        for pr_key, ev_list in raw_content.items():
                            repo = None
                            num = None
                            if "#" in pr_key:
                                parts = pr_key.split("#", 1)
                                repo = parts[0] or None
                                try:
                                    num = int(parts[1])
                                except ValueError:
                                    num = parts[1]
                            for ev in ev_list:
                                typename = ev.get("__typename", "")
                                ev_type = "unknown"
                                if "Labeled" in typename:
                                    ev_type = "labeled"
                                elif "Unlabeled" in typename:
                                    ev_type = "unlabeled"
                                elif "Closed" in typename:
                                    ev_type = "closed"
                                elif "Merged" in typename:
                                    ev_type = "merged"
                                elif ev.get("event"):
                                    ev_type = str(ev.get("event")).lower()

                                lbl_name = None
                                if isinstance(ev.get("label"), dict):
                                    lbl_name = ev["label"].get("name")
                                elif isinstance(ev.get("label"), str):
                                    lbl_name = ev["label"]

                                lbl_name = normalize_stage_label(lbl_name)

                                raw_events.append({
                                    "repo": repo,
                                    "pr_number": num,
                                    "event": ev_type,
                                    "label": lbl_name,
                                    "createdAt": ev.get("createdAt"),
                                })
                    elif isinstance(raw_content, list):
                        for ev in raw_content:
                            lbl_name = None
                            if isinstance(ev.get("label"), dict):
                                lbl_name = ev["label"].get("name")
                            elif isinstance(ev.get("label"), str):
                                lbl_name = ev["label"]
                            lbl_name = normalize_stage_label(lbl_name)
                            norm_ev = dict(ev)
                            if lbl_name is not None:
                                norm_ev["label"] = lbl_name
                            raw_events.append(norm_ev)

                    timeline = self.deduplicate_events(raw_events)
                source_status["timeline"] = {"status": "COMPLETE", "path": timeline_path, "count": len(timeline)}
            except Exception as e:
                source_status["timeline"] = {"status": "FAILED", "error": str(e)}
        else:
            source_status["timeline"] = {"status": "NOT_FOUND", "path": timeline_path}

        # 3. Handoff metrics file
        handoffs = []
        handoff_path = os.path.join(input_dir, "actionable_handoff_metrics.json")
        if os.path.exists(handoff_path):
            try:
                with open(handoff_path, "r", encoding="utf-8") as f:
                    raw_handoffs = json.load(f)
                if isinstance(raw_handoffs, list):
                    handoffs = raw_handoffs
                elif isinstance(raw_handoffs, dict):
                    if "records" in raw_handoffs and isinstance(raw_handoffs["records"], list):
                        handoffs = raw_handoffs["records"]
                    elif "handoffs" in raw_handoffs and isinstance(raw_handoffs["handoffs"], list):
                        handoffs = raw_handoffs["handoffs"]
                source_status["handoffs"] = {"status": "COMPLETE", "path": handoff_path, "count": len(handoffs)}
            except Exception as e:
                source_status["handoffs"] = {"status": "FAILED", "error": str(e)}

        # 4. Manifest validation (Codex P1-3: missing manifest or invalid cutoff stamps STALE, not COMPLETE)
        manifest_path = os.path.join(input_dir, "collection_manifest.json")
        if not os.path.exists(manifest_path):
            manifest_path = os.path.join(input_dir, "source_manifest.json")

        valid_manifest = False
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    m = json.load(f)
                if isinstance(m, dict):
                    cutoff_str = m.get("cutoff")
                    if not cutoff_str and "sources" in m and isinstance(m["sources"], dict):
                        for s_val in m["sources"].values():
                            if isinstance(s_val, dict) and s_val.get("cutoff"):
                                cutoff_str = s_val["cutoff"]
                                break
                    if cutoff_str and parse_iso_utc(cutoff_str):
                        source_status["collection_manifest"] = {"status": "COMPLETE", "cutoff": cutoff_str}
                        valid_manifest = True
            except Exception:
                pass

        if not valid_manifest:
            source_status["collection_manifest"] = {"status": "STALE", "cutoff": None}

        prs = self.deduplicate_prs(prs)
        self.source_manifest = source_status
        return {
            "prs": prs,
            "timeline": timeline,
            "sources": source_status,
            "handoff_records": handoffs,
        }

    def load_retained_telemetry(self, telemetry_dir=None, roadmap_repo=None):
        """
        Load retained private telemetry store from roadmap repo or custom telemetry directory.
        Reconstructs pilot_events, human_episodes, calibration_audit, and retention_manifest.
        """
        target_dir = telemetry_dir
        if not target_dir and roadmap_repo:
            published = tempfile.mkdtemp(prefix="prw_published_")
            try:
                if export_published_telemetry(roadmap_repo, published):
                    return self.load_retained_telemetry(telemetry_dir=published)
            finally:
                shutil.rmtree(published, ignore_errors=True)
            target_dir = os.path.join(roadmap_repo, "dashboards", "prw", "telemetry")

        pilot_events = []
        human_episodes = []
        calibration_audit = {}
        retention_manifest = {}

        prs = []
        timeline = []
        handoff_records = []
        retained_sources = {}

        jsonl_sinks = (
            ("pilot_events.jsonl", pilot_events),
            ("human_episodes.jsonl", human_episodes),
            ("retained_prs.jsonl", prs),
            ("retained_timeline.jsonl", timeline),
            ("retained_handoffs.jsonl", handoff_records),
        )
        seen = {name: set() for name, _ in jsonl_sinks}
        for bundle_dir in retained_telemetry_dirs(target_dir):
            for name, sink in jsonl_sinks:
                path = os.path.join(bundle_dir, name)
                if not os.path.exists(path):
                    continue
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        record = json.loads(line)
                        key = json.dumps(record, sort_keys=True)
                        if key not in seen[name]:
                            seen[name].add(key)
                            sink.append(record)

            for name in ("calibration_audit.json", "retention_manifest.json", "retained_sources.json"):
                path = os.path.join(bundle_dir, name)
                if os.path.exists(path):
                    with open(path, "r", encoding="utf-8") as f:
                        loaded = json.load(f)
                    if name == "calibration_audit.json":
                        calibration_audit = _project(loaded, CALIBRATION_AUDIT_SCHEMA) or {}
                    elif name == "retained_sources.json":
                        retained_sources.update(_sanitize_retained_sources(loaded))
                    else:
                        retention_manifest = _project(loaded, RETENTION_MANIFEST_SCHEMA) or {}

        return {
            "pilot_events": pilot_events,
            "human_episodes": human_episodes,
            "calibration_audit": calibration_audit,
            "retention_manifest": retention_manifest,
            "prs": prs,
            "timeline": timeline,
            "handoff_records": handoff_records,
            "sources": retained_sources,
        }

    def collect_all(
        self,
        input_dir=None,
        state_dir=None,
        fetch_page_fn=None,
        fetch_timeline_fn=None,
        offline=False,
        telemetry_dir=None,
        roadmap_repo=None,
        receipts_dir=None,
    ):
        """
        Collect PRs, timeline, and handoffs from live GitHub API and/or cached scratch/state.
        Handles per-source failures gracefully:
        - If live collection fails for a repo, preserves prior cached data from input_dir/state_dir
          and flags sources[repo] as PARTIAL_FAILURE.
        - If all sources fail with no data, status is FAILED.
        """
        all_prs = []
        all_timeline = []
        handoff_records = []
        sources = {}

        cached_prs_by_repo = {}
        retained_prs_by_repo = {}
        cached_timeline = []
        cached_handoffs = []
        prior_cutoffs = {}
        prior_sources = {}

        def remember_prior_source(key, entry):
            """Record a saved source entry; its status and failure provenance survive reloads."""
            if not isinstance(entry, dict):
                return
            cutoff = entry.get("cutoff") if parse_iso_utc(entry.get("cutoff")) else None
            prior_sources[key] = {"status": entry.get("status"), "cutoff": cutoff}
            if cutoff and entry.get("status") not in ("STALE", "FAILED"):
                prior_cutoffs[key] = cutoff
            else:
                prior_cutoffs.pop(key, None)

        # Telemetry candidate discovery
        candidate_telem_dirs = []
        if telemetry_dir:
            candidate_telem_dirs.append(telemetry_dir)
        published_tmp = None
        if roadmap_repo:
            # Readback consumes the PUBLISHED ref; the working tree is only a fallback.
            published_tmp = tempfile.mkdtemp(prefix="prw_published_")
            if export_published_telemetry(roadmap_repo, published_tmp, fetch=not offline):
                candidate_telem_dirs.append(published_tmp)
            else:
                candidate_telem_dirs.append(os.path.join(roadmap_repo, "dashboards", "prw", "telemetry"))
        if input_dir:
            candidate_telem_dirs.append(os.path.join(input_dir, "telemetry"))
            candidate_telem_dirs.append(input_dir)
        if state_dir:
            candidate_telem_dirs.append(os.path.join(state_dir, "telemetry"))
            candidate_telem_dirs.append(state_dir)

        pilot_events = []
        human_episodes = []
        calibration_audit = {}
        retention_manifest = {}

        seen_telem_dirs = set()
        for t_dir in candidate_telem_dirs:
            real = os.path.realpath(t_dir) if t_dir else None
            if not real or real in seen_telem_dirs or not retained_telemetry_dirs(t_dir):
                continue
            seen_telem_dirs.add(real)
            retained = self.load_retained_telemetry(telemetry_dir=t_dir)
            for ev in retained.get("pilot_events", []):
                if ev not in pilot_events:
                    pilot_events.append(ev)
            for ep in retained.get("human_episodes", []):
                if ep not in human_episodes:
                    human_episodes.append(ep)
            calibration_audit = retained.get("calibration_audit") or calibration_audit
            retention_manifest = retained.get("retention_manifest") or retention_manifest
            # Retained collections seed the same caches scratch state does; scratch (loaded next) wins.
            for p in reversed(retained.get("prs", [])):
                r = p.get("repo")
                if r and (not self.repos or r in self.repos):
                    retained_prs_by_repo.setdefault(r, []).append(self.normalize_pr_record(p))
            cached_timeline.extend(retained.get("timeline", []))
            cached_handoffs.extend(retained.get("handoff_records", []))
            for k, v in retained.get("sources", {}).items():
                remember_prior_source(k, v)

        if published_tmp:
            shutil.rmtree(published_tmp, ignore_errors=True)

        # 1. Attempt loading from state_dir or input_dir
        for directory in (state_dir, input_dir):
            if directory and os.path.isdir(directory):
                cached = self.load_from_cached_scratch(directory)
                for p in cached.get("prs", []):
                    r = p.get("repo")
                    if r:
                        cached_prs_by_repo.setdefault(r, []).append(p)
                if cached.get("timeline"):
                    cached_timeline.extend(cached["timeline"])
                if cached.get("handoff_records"):
                    if isinstance(cached["handoff_records"], list):
                        cached_handoffs.extend(cached["handoff_records"])
                    elif isinstance(cached["handoff_records"], dict):
                        cached_handoffs.append(cached["handoff_records"])
                manifest_path = os.path.join(directory, "source_manifest.json")
                if os.path.exists(manifest_path):
                    try:
                        with open(manifest_path, "r", encoding="utf-8") as f:
                            m = json.load(f)
                            for k, v in m.items():
                                remember_prior_source(k, v)
                    except Exception:
                        pass

        # Retained snapshots rank after scratch: dedupe keeps the newest updatedAt, ties go to scratch.
        for r, retained_list in retained_prs_by_repo.items():
            cached_prs_by_repo.setdefault(r, []).extend(retained_list)

        # 2. Determine repos to collect
        target_repos = list(self.repos)
        if not target_repos and cached_prs_by_repo:
            target_repos = list(cached_prs_by_repo.keys())

        if offline:
            for repo in target_repos:
                # Offline data is only as fresh as its verified cached cutoff; never
                # substitute the current collection cutoff for an unknown one.
                # Only a successful live fetch can mint COMPLETE; a saved FAILED/PARTIAL_FAILURE/STALE
                # status is reloaded as-is.
                prs = cached_prs_by_repo.get(repo, [])
                prior_cutoff = prior_cutoffs.get(repo)
                prior_status = prior_sources.get(repo, {}).get("status")
                if prs:
                    all_prs.extend(prs)
                    if prior_status == "COMPLETE" and prior_cutoff:
                        status = "COMPLETE"
                    elif prior_status in ("PARTIAL_FAILURE", "FAILED"):
                        status = prior_status
                    else:
                        status = "STALE"
                    sources[repo] = {"status": status, "count": len(prs), "cutoff": prior_cutoff}
                elif prior_status in ("PARTIAL_FAILURE", "FAILED"):
                    sources[repo] = {"status": prior_status, "count": 0, "cutoff": prior_cutoff}
                else:
                    sources[repo] = {"status": "EMPTY", "count": 0, "cutoff": prior_cutoff}
            for key, entry in prior_sources.items():
                if key not in sources and entry.get("status") in ("PARTIAL_FAILURE", "FAILED", "STALE"):
                    sources[key] = {"status": entry["status"], "cutoff": entry["cutoff"]}
            all_timeline = cached_timeline
            handoff_records = cached_handoffs
        else:
            live_timeline = []
            w1_start = self.cutoff_dt - timedelta(days=14)
            for repo in target_repos:
                try:
                    repo_prs = self.collect_repo_prs_paginated(repo, fetch_page_fn=fetch_page_fn)
                    combined_repo_prs = self.deduplicate_prs(repo_prs + cached_prs_by_repo.get(repo, []))
                    all_prs.extend(combined_repo_prs)
                    sources[repo] = {
                        "status": "COMPLETE",
                        "count": len(combined_repo_prs),
                        "cutoff": format_iso_utc(self.cutoff_dt),
                    }
                    # Live timeline collection for in-window PRs
                    for p in combined_repo_prs:
                        m_dt = parse_iso_utc(p.get("mergedAt"))
                        c_dt = parse_iso_utc(p.get("createdAt"))
                        is_open = (p.get("state") == "OPEN")
                        in_window = (m_dt and m_dt >= w1_start) or is_open or (c_dt and c_dt >= w1_start)
                        if in_window and p.get("number"):
                            try:
                                tl = self.collect_pr_timeline_live(repo, p["number"], fetch_timeline_fn=fetch_timeline_fn)
                                live_timeline.extend(tl)
                            except Exception as tle:
                                sources[f"{repo}:timeline"] = {"status": "PARTIAL_FAILURE", "error": str(tle)}
                                sources[repo]["status"] = "PARTIAL_FAILURE"
                                sources[repo]["error"] = str(tle)
                                sources[repo]["cutoff"] = prior_cutoffs.get(repo)
                except Exception as e:
                    # Live collection failed for this repo
                    prior = cached_prs_by_repo.get(repo, [])
                    if prior:
                        all_prs.extend(prior)
                        sources[repo] = {
                            "status": "PARTIAL_FAILURE",
                            "error": str(e),
                            "count": len(prior),
                            "cutoff": prior_cutoffs.get(repo),
                        }
                    else:
                        sources[repo] = {
                            "status": "FAILED",
                            "error": str(e),
                            "count": 0,
                            "cutoff": None,
                        }
            all_timeline = self.deduplicate_events(live_timeline + cached_timeline)
            handoff_records = list(cached_handoffs)

            # Ingest receipts if receipts_dir or PRW_METRICS_RECEIPTS_DIR is provided
            r_dir = receipts_dir or os.environ.get("PRW_METRICS_RECEIPTS_DIR")
            if r_dir:
                receipt_records = self.collect_receipts_from_dir(r_dir)
                if receipt_records:
                    handoff_records.extend(receipt_records)

        all_prs = self.deduplicate_prs(all_prs)
        all_timeline = self.deduplicate_events(all_timeline)

        # 3. Overall status resolution
        failed_count = sum(1 for s in sources.values() if s.get("status") in ("FAILED", "PARTIAL_FAILURE"))
        complete_count = sum(1 for s in sources.values() if s.get("status") == "COMPLETE")

        if not all_prs and failed_count > 0:
            overall_status = "FAILED"
        elif any(s.get("status") == "PARTIAL_FAILURE" for s in sources.values()):
            overall_status = "PARTIAL_FAILURE"
        elif failed_count > 0:
            overall_status = "PARTIAL_FAILURE"
        elif not all_prs:
            overall_status = "EMPTY"
        elif any(s.get("status") == "STALE" for s in sources.values()):
            overall_status = "STALE"
        else:
            overall_status = "FRESH"

        # 4. Save snapshot to state_dir if provided and not completely failed
        if state_dir and overall_status != "FAILED":
            try:
                os.makedirs(state_dir, exist_ok=True)
                pid = os.getpid()
                for fname, payload in [
                    ("enriched_prs.json", all_prs),
                    ("raw_timeline.json", all_timeline),
                    ("source_manifest.json", sources),
                    ("actionable_handoff_metrics.json", handoff_records if handoff_records else None),
                ]:
                    if payload is not None:
                        fpath = os.path.join(state_dir, fname)
                        tmp_path = f"{fpath}.tmp.{pid}"
                        with open(tmp_path, "w", encoding="utf-8") as f:
                            json.dump(payload, f, indent=2)
                        os.replace(tmp_path, fpath)
            except Exception:
                pass

        self.source_manifest = sources
        return {
            "prs": all_prs,
            "timeline": all_timeline,
            "sources": sources,
            "handoff_records": handoff_records,
            "status": overall_status,
            "pilot_events": pilot_events,
            "human_episodes": human_episodes,
            "calibration_audit": calibration_audit,
            "retention_manifest": retention_manifest,
        }


# -----------------------------------------------------------------------------
# Task 2: Aggregation and Honest Idle Boundaries
# -----------------------------------------------------------------------------

class MetricsAggregator:
    VERIFIED_HUMAN_ORIGINS = frozenset({
        "human",
        "operator",
        "user_prompt",
    })

    """Computes exact-window aggregations, stage dwell, and honest idle boundaries."""

    def __init__(self, cutoff_dt=None, repos=None):
        self.cutoff_dt = cutoff_dt or datetime.now(timezone.utc)
        self.configured_repos = frozenset(repos or ())
        self.w2_start_dt = self.cutoff_dt - timedelta(days=7)
        self.w1_start_dt = self.cutoff_dt - timedelta(days=14)

    def is_backlog_merge(self, pr):
        """Backlog merge is defined as mergedAt - createdAt > 7 days (168h) at merge time."""
        c_dt = parse_iso_utc(pr.get("createdAt"))
        m_dt = parse_iso_utc(pr.get("mergedAt"))
        if not c_dt or not m_dt:
            return False
        return (m_dt - c_dt).total_seconds() > 7 * 86400

    def compute_interval_duration(self, start_iso, end_iso):
        """Compute duration between two ISO timestamps; flag CONFLICT if end < start."""
        s = parse_iso_utc(start_iso)
        e = parse_iso_utc(end_iso)
        if not s or not e:
            return {"duration_sec": None, "status": "UNKNOWN"}
        if e < s:
            return {"duration_sec": None, "status": "CONFLICT"}
        sec = round((e - s).total_seconds(), 3)
        return {"duration_sec": sec, "status": "OK"}

    def compute_review_attempt_metrics(self, attempt):
        """
        Validate queued_at vs actual_review_started_at:
        queued_at to completed_at is attempt_elapsed_sec.
        actual_review_started_at to completed_at is review_execution_sec (or UNKNOWN).
        """
        q_dt = parse_iso_utc(attempt.get("queued_at"))
        a_dt = parse_iso_utc(attempt.get("actual_review_started_at"))
        c_dt = parse_iso_utc(attempt.get("completed_at"))

        elapsed_sec = None
        if q_dt and c_dt:
            elapsed_sec = round((c_dt - q_dt).total_seconds(), 3)

        execution_sec = None
        exec_status = "UNKNOWN"
        if a_dt and c_dt:
            if c_dt >= a_dt:
                execution_sec = round((c_dt - a_dt).total_seconds(), 3)
                exec_status = "OK"
            else:
                exec_status = "CONFLICT"

        return {
            "attempt_elapsed_sec": elapsed_sec,
            "review_execution_sec": execution_sec,
            "review_execution_status": exec_status,
        }

    def compute_multi_attempt_metrics(self, attempts):
        """Compute per-attempt durations and inter-attempt gaps."""
        results = []
        for i, att in enumerate(attempts):
            s_dt = parse_iso_utc(att.get("started_at"))
            c_dt = parse_iso_utc(att.get("completed_at"))
            dur = None
            if s_dt and c_dt and c_dt >= s_dt:
                dur = round((c_dt - s_dt).total_seconds(), 3)

            gap = None
            if i > 0:
                prev_c = parse_iso_utc(attempts[i - 1].get("completed_at"))
                if prev_c and s_dt:
                    gap = round((s_dt - prev_c).total_seconds(), 3)

            results.append({
                "attempt_number": att.get("attempt_number", i + 1),
                "started_at": att.get("started_at"),
                "completed_at": att.get("completed_at"),
                "duration_sec": dur,
                "inter_attempt_gap_sec": gap,
            })

        return {"attempts": results}

    def derive_authority_ready(self, pr):
        """
        Reviews completing after merge cannot establish pre-merge authority readiness.
        Requires explicit final_ready and merge_authority facts plus authority_ready_at; a timestamp
        alone is not evidence, and review_completed_at is never substituted.
        """
        if pr.get("final_ready") is not True or pr.get("merge_authority") is not True:
            return "UNKNOWN"
        auth_iso = pr.get("authority_ready_at")
        if not auth_iso:
            return "UNKNOWN"
        a_dt = parse_iso_utc(auth_iso)
        if not a_dt:
            return "UNKNOWN"
        m_dt = parse_iso_utc(pr.get("mergedAt"))
        if m_dt and a_dt > m_dt:
            return "UNKNOWN"
        return "READY"

    def compute_eligible_unattended_duration(self, pr):
        """
        Eligible unattended duration cannot be inferred as 0s without continuous observation.
        Missing telemetry coverage yields UNKNOWN.
        """
        has_obs = pr.get("has_continuous_observation", False)
        if not has_obs or pr.get("telemetry_coverage", 0.0) <= 0.0:
            return {"duration_sec": None, "status": "UNKNOWN"}

        intervals = pr.get("eligible_intervals", [])
        total_sec = compute_disjoint_interval_union(intervals)
        return {"duration_sec": total_sec, "status": "OK"}

    def compute_lifecycle_durations(self, pr):
        """Separate closure sprint from task-to-merge."""
        m_dt = parse_iso_utc(pr.get("mergedAt"))
        orig_t = parse_iso_utc(pr.get("initial_task_accepted_at"))
        sprint_t = parse_iso_utc(pr.get("closure_sprint_accepted_at"))

        task_to_merge_sec = None
        task_status = "UNKNOWN"
        if orig_t and m_dt and m_dt >= orig_t:
            task_to_merge_sec = round((m_dt - orig_t).total_seconds(), 3)
            task_status = "OK"

        sprint_to_merge_sec = None
        if sprint_t and m_dt and m_dt >= sprint_t:
            sprint_to_merge_sec = round((m_dt - sprint_t).total_seconds(), 3)

        return {
            "task_to_merge_sec": task_to_merge_sec,
            "task_to_merge_status": task_status,
            "closure_sprint_to_merge_sec": sprint_to_merge_sec,
        }

    def compute_time_semantics(self, pr, pilot_events=None):
        """
        Compute active wall time (disjoint union) vs agent effort (arithmetic sum),
        observed operation elapsed, and residual classified as UNATTRIBUTED_OR_WAITING_NOT_WASTE.
        Missing telemetry or endpoints remain UNKNOWN (None).
        """
        c_dt = parse_iso_utc(pr.get("createdAt"))
        m_dt = parse_iso_utc(pr.get("mergedAt"))
        orig_t = parse_iso_utc(pr.get("initial_task_accepted_at"))
        sprint_t = parse_iso_utc(pr.get("closure_sprint_accepted_at"))

        # Match pilot_events by exact repo and pr_number; repo-less or number-less events stay unassigned
        matching_events = []
        pr_num = pr.get("number")
        pr_repo = pr.get("repo")
        if pilot_events and pr_num is not None:
            for ev in pilot_events:
                ev_pr = ev.get("pr_number") or ev.get("number")
                if ev_pr is None:
                    continue
                try:
                    if int(ev_pr) != int(pr_num):
                        continue
                except (ValueError, TypeError):
                    if str(ev_pr) != str(pr_num):
                        continue
                ev_repo = ev.get("repo")
                if ev_repo and pr_repo and ev_repo != pr_repo:
                    continue
                matching_events.append(ev)

        # Fall back to matching events if endpoints are missing on pr
        if matching_events:
            for ev in matching_events:
                ev_type = ev.get("event_type")
                occ_iso = ev.get("occurred_at")
                if occ_iso:
                    occ_dt = parse_iso_utc(occ_iso)
                    if occ_dt:
                        if ev_type == "task_accepted" and orig_t is None:
                            orig_t = occ_dt
                        elif ev_type == "closure_sprint_accepted" and sprint_t is None:
                            sprint_t = occ_dt
                        elif ev_type == "merged" and m_dt is None:
                            m_dt = occ_dt

        pr_elapsed_sec = None
        if c_dt and m_dt and m_dt >= c_dt:
            pr_elapsed_sec = round((m_dt - c_dt).total_seconds(), 3)

        task_elapsed_sec = None
        if orig_t and m_dt and m_dt >= orig_t:
            task_elapsed_sec = round((m_dt - orig_t).total_seconds(), 3)

        closure_sprint_to_merge_sec = None
        if sprint_t and m_dt and m_dt >= sprint_t:
            closure_sprint_to_merge_sec = round((m_dt - sprint_t).total_seconds(), 3)

        active_intervals = []
        agent_effort_sec = None
        operation_intervals = []
        waiting_intervals = []

        if matching_events:
            active_durations = []
            for ev in matching_events:
                sk = ev.get("span_kind")
                s_iso = ev.get("start_at") or ev.get("start") or ev.get("started_at")
                e_iso = ev.get("end_at") or ev.get("end") or ev.get("completed_at")
                dur = valid_duration_sec(ev.get("duration_sec"))
                s_dt = parse_iso_utc(s_iso)
                e_dt = parse_iso_utc(e_iso)

                if not (s_dt and e_dt) and ev.get("occurred_at") and dur is not None:
                    s_dt = parse_iso_utc(ev.get("occurred_at"))
                    if s_dt is not None:
                        e_dt = s_dt + timedelta(seconds=dur)

                if sk == "observed_active_execution":
                    if s_dt and e_dt and e_dt >= s_dt:
                        active_intervals.append((s_dt, e_dt))
                        active_durations.append((e_dt - s_dt).total_seconds())
                    elif dur is not None:
                        active_durations.append(dur)
                elif sk == "observed_operation_elapsed":
                    if s_dt and e_dt and e_dt >= s_dt:
                        operation_intervals.append((s_dt, e_dt))
                    elif dur is not None:
                        operation_intervals.append({"duration": dur})
                elif sk == "explicit_waiting":
                    if s_dt and e_dt and e_dt >= s_dt:
                        waiting_intervals.append((s_dt, e_dt))

            if active_intervals:
                observed_active_wall_sec = compute_disjoint_interval_union(active_intervals)
                agent_effort_sec = round(sum(active_durations), 3)
            elif active_durations:
                # Codex P1-2: duration-only events without start/end timestamps give effort sum only,
                # keeping active wall time unknown (None)
                observed_active_wall_sec = None
                agent_effort_sec = round(sum(active_durations), 3)
            else:
                observed_active_wall_sec = None
                agent_effort_sec = None

            # Timed operations contribute their interval union; duration-only operations cannot be
            # placed on the timeline, so their sum is added and the basis is labelled (overlap with
            # timed intervals cannot be excluded).
            timed_ops = [x for x in operation_intervals if isinstance(x, tuple)]
            untimed_secs = [x["duration"] for x in operation_intervals if isinstance(x, dict)]
            if timed_ops and untimed_secs:
                observed_operation_elapsed_sec = round(
                    compute_disjoint_interval_union(timed_ops) + sum(untimed_secs), 3
                )
                operation_elapsed_basis = "TIMED_UNION_PLUS_DURATION_ONLY_SUM"
            elif timed_ops:
                observed_operation_elapsed_sec = compute_disjoint_interval_union(timed_ops)
                operation_elapsed_basis = "TIMED_UNION"
            elif untimed_secs:
                observed_operation_elapsed_sec = round(sum(untimed_secs), 3)
                operation_elapsed_basis = "DURATION_ONLY_SUM"
            else:
                observed_operation_elapsed_sec = None
                operation_elapsed_basis = None

            if waiting_intervals:
                explicit_waiting_sec = compute_disjoint_interval_union(waiting_intervals)
            else:
                explicit_waiting_sec = None
        else:
            observed_active_wall_sec = None
            agent_effort_sec = None
            observed_operation_elapsed_sec = None
            operation_elapsed_basis = None
            explicit_waiting_sec = None

        unattributed_or_waiting_residual_sec = None
        residual_classification = None
        if pr_elapsed_sec is not None and observed_active_wall_sec is not None:
            unattributed_or_waiting_residual_sec = round(pr_elapsed_sec - observed_active_wall_sec, 3)
            residual_classification = "UNATTRIBUTED_OR_WAITING_NOT_WASTE"

        return {
            "pr_url": pr.get("url") or f"https://github.com/{pr.get('repo', 'unknown')}/pull/{pr.get('number', 0)}",
            "pr_elapsed_sec": pr_elapsed_sec,
            "task_elapsed_sec": task_elapsed_sec,
            "closure_sprint_to_merge_sec": closure_sprint_to_merge_sec,
            "observed_operation_elapsed_sec": observed_operation_elapsed_sec,
            "operation_elapsed_basis": operation_elapsed_basis,
            "observed_active_wall_sec": observed_active_wall_sec,
            "agent_effort_sec": agent_effort_sec,
            "unattributed_or_waiting_residual_sec": unattributed_or_waiting_residual_sec,
            "residual_classification": residual_classification,
            "explicit_waiting_sec": explicit_waiting_sec,
            "avoidable_unattended_sec": None,
        }

    @staticmethod
    def event_in_window(ev, start_dt, end_dt):
        """Dated pilot events must fall in [start_dt, end_dt); undated duration-only events stay with their PR."""
        for key in ("occurred_at", "start_at", "start", "started_at", "end_at", "end", "completed_at"):
            ts = parse_iso_utc(ev.get(key))
            if ts:
                return start_dt <= ts < end_dt
        return True

    @staticmethod
    def episode_in_scope(ep, start_dt, end_dt, repos):
        """
        Keep episodes inside [start_dt, end_dt) and the PR repo scope. Dot rows are kept even
        without a timestamp because their absence of ids/timestamps is itself the coverage signal.
        """
        if not isinstance(ep, dict):
            return False
        ep_repo = ep.get("repo")
        if ep_repo and repos and ep_repo not in repos:
            return False
        ts = next(
            (parse_iso_utc(ep.get(k)) for k in ("timestamp", "created_at", "occurred_at") if parse_iso_utc(ep.get(k))),
            None,
        )
        if ts is None:
            origin = str(ep.get("origin") or "").lower().strip()
            channel = str(ep.get("channel") or "").lower().strip()
            source_channel = str(ep.get("source_channel") or "").lower().strip()
            return origin.startswith("dot") or bool({channel, source_channel} & {"dot", "dot_history"})
        return start_dt <= ts < end_dt

    def compute_human_interventions(self, episodes, cohort_prs_count=None, retention_manifest=None):
        """
        Aggregate human intervention episodes with bot exclusion, initial assignment separation,
        transcript deduplication, dual-annotator calibration, origin verification, and post-merge tracking.
        """
        raw_human_messages = 0
        raw_message_ids = set()
        raw_message_count_partial = False
        accepted_human_rows = 0
        initial_task_requests = 0
        qualifying_episodes = 0
        unverified_origin_excluded = 0
        dot_page_tail_partial_count = 0
        label_breakdown = {"good": 0, "bad": 0, "mixed": 0, "unknown": 0}
        pr_attributed_count = 0
        unassigned_count = 0
        post_merge_count = 0

        seen_episode_ids = set()
        dot_has_structured = False

        for ep in episodes or []:
            if not isinstance(ep, dict):
                continue

            # Redact excerpt if present
            if "excerpt" in ep:
                ep["excerpt"] = redact_sensitive_excerpt(ep["excerpt"])

            origin = str(ep.get("origin") or "").lower().strip()
            actor_status = str(ep.get("actor_status") or "").lower().strip()
            channels = {
                str(ep.get(key) or "").lower().strip()
                for key in ("channel", "source_channel")
            }
            if ep.get("is_bot") or origin == "bot" or actor_status in {"bot", "automated"}:
                continue

            # A Dot row is useful only when the source supplies message identity and a parseable time.
            msg_ids = ep.get("message_ids") or []
            if ep.get("message_id"):
                msg_ids = list(msg_ids) + [ep["message_id"]]
            msg_ids = list(dict.fromkeys(str(value).strip() for value in msg_ids if str(value).strip()))
            has_timestamp = any(
                parse_iso_utc(ep.get(key)) is not None
                for key in ("timestamp", "created_at", "occurred_at")
            )
            is_dot = origin.startswith("dot") or bool(channels & {"dot", "dot_history"})

            if origin == "dot_page_tail" or (is_dot and (not msg_ids or not has_timestamp)):
                dot_page_tail_partial_count += 1
                raw_message_count_partial = True
                continue

            # Structured actor evidence is authoritative; curated legacy origins remain explicit declarations.
            is_human = actor_status == "human" or (
                not actor_status and origin in self.VERIFIED_HUMAN_ORIGINS
            )
            if not is_human:
                unverified_origin_excluded += 1
                continue
            accepted_human_rows += 1

            # Connector coverage comes only from a verified, structured Dot row.
            if is_dot:
                dot_has_structured = True

            # Episode identity deduplicates semantic episodes; message identity is counted independently.
            ep_id = ep.get("episode_id")
            duplicate_episode = bool(ep_id and ep_id in seen_episode_ids)
            if ep_id and not duplicate_episode:
                seen_episode_ids.add(ep_id)
            if msg_ids:
                new_message_ids = [message_id for message_id in msg_ids if message_id not in raw_message_ids]
                raw_message_ids.update(new_message_ids)
                raw_msgs = len(new_message_ids)
                raw_human_messages += raw_msgs
            else:
                raw_message_count_partial = True
                raw_msgs = 0 if duplicate_episode else ep.get("raw_message_count", 1)
                raw_human_messages += raw_msgs

            if duplicate_episode:
                continue

            is_initial = bool(ep.get("is_initial_assignment") or ep.get("initial_task_request"))
            if is_initial:
                initial_task_requests += raw_msgs
                continue

            qualifying_episodes += 1

            if ep.get("is_post_merge"):
                post_merge_count += 1

            pr_attr = ep.get("pr_attribution")
            if not pr_attr or pr_attr == "unassigned":
                unassigned_count += 1
            else:
                pr_attributed_count += 1

            # Semantic calibration
            ann_a = ep.get("annotator_a")
            ann_b = ep.get("annotator_b")
            if ann_a and ann_b:
                lbl_a = ann_a.get("label") if isinstance(ann_a, dict) else str(ann_a)
                lbl_b = ann_b.get("label") if isinstance(ann_b, dict) else str(ann_b)
                if lbl_a != lbl_b:
                    resolved_label = "mixed"
                else:
                    resolved_label = lbl_a or "unknown"
            else:
                resolved_label = ep.get("label") or "unknown"

            if resolved_label not in label_breakdown:
                resolved_label = "unknown"
            label_breakdown[resolved_label] += 1

        if dot_page_tail_partial_count > 0:
            dot_coverage = "PARTIAL_PAGE_TAIL_NO_MESSAGE_IDS_OR_TIMESTAMPS"
        elif dot_has_structured:
            dot_coverage = "TESTED_CONNECTOR_OK"
        else:
            dot_coverage = "UNTESTED_ADAPTER_PENDING"

        has_retention = bool(retention_manifest) or any(bool(ep.get("retention_verified")) for ep in (episodes or []))
        retention_status = "OK" if has_retention else "UNVERIFIED"

        if accepted_human_rows == 0:
            raw_message_count_coverage = "UNKNOWN_NO_HUMAN_EPISODES"
        elif raw_message_count_partial:
            raw_message_count_coverage = "PARTIAL_MISSING_MESSAGE_IDS"
        else:
            raw_message_count_coverage = "COMPLETE_SOURCE_IDS"

        return {
            "raw_human_messages": raw_human_messages,
            "raw_message_count_coverage": raw_message_count_coverage,
            "initial_task_requests": initial_task_requests,
            "qualifying_episodes": qualifying_episodes,
            "unverified_origin_excluded": unverified_origin_excluded,
            "dot_page_tail_partial_count": dot_page_tail_partial_count,
            "label_breakdown": label_breakdown,
            "pr_attributed_count": pr_attributed_count,
            "unassigned_count": unassigned_count,
            "post_merge_count": post_merge_count,
            "channel_coverage": {"dot_history": dot_coverage},
            "retention_status": retention_status,
        }

    def summarize_window_cohort(self, merged_prs):
        """Summarize creation-to-merge times for a cohort merged within window."""
        if not merged_prs:
            return {
                "n": 0, "all_median_hours": "UNKNOWN", "all_p75_hours": "UNKNOWN",
                "comparable_n": 0, "comp_median_hours": "UNKNOWN", "comp_p75_hours": "UNKNOWN",
                "backlog_n": 0, "backlog_median_hours": "UNKNOWN", "backlog_p75_hours": "UNKNOWN",
            }

        durations_all = []
        durations_comp = []
        durations_backlog = []

        for p in merged_prs:
            c = parse_iso_utc(p.get("createdAt"))
            m = parse_iso_utc(p.get("mergedAt"))
            if c and m and m >= c:
                hrs = (m - c).total_seconds() / 3600.0
                durations_all.append(hrs)
                if self.is_backlog_merge(p):
                    durations_backlog.append(hrs)
                else:
                    durations_comp.append(hrs)

        durations_all.sort()
        durations_comp.sort()
        durations_backlog.sort()

        return {
            "n": len(durations_all),
            "all_median_hours": round(calculate_median(durations_all), 2) if durations_all else "UNKNOWN",
            "all_p75_hours": round(calculate_nearest_rank_p75(durations_all), 2) if durations_all else "UNKNOWN",
            "comparable_n": len(durations_comp),
            "comp_median_hours": round(calculate_median(durations_comp), 2) if durations_comp else "UNKNOWN",
            "comp_p75_hours": round(calculate_nearest_rank_p75(durations_comp), 2) if durations_comp else "UNKNOWN",
            "backlog_n": len(durations_backlog),
            "backlog_median_hours": round(calculate_median(durations_backlog), 2) if durations_backlog else "UNKNOWN",
            "backlog_p75_hours": round(calculate_nearest_rank_p75(durations_backlog), 2) if durations_backlog else "UNKNOWN",
        }

    def compute_stage_dwell(self, prs, timeline_events=None, stages=None):
        """
        Compute real stage dwell intervals from timeline_events and PR stage_transitions.
        Filters timeline_events to only PRs in the passed prs cohort.
        Closes open stages on transition to a subsequent stage or upon terminal merge/close.
        If end_dt < start_dt: increments conflicts for that stage and excludes duration.
        If end_dt >= start_dt: accumulates duration in hours and computes median and nearest-rank p75.
        """
        if stages is None:
            stages = [
                "stage:0-spec",
                "stage:1-coding",
                "stage:2-evidence",
                "stage:3-evidence-review",
                "stage:4-code-review",
                "stage:5-final-approval",
            ]

        stage_durations = {s: [] for s in stages}
        stage_conflicts = {s: 0 for s in stages}
        stage_covered_prs = {s: set() for s in stages}

        cohort_pr_keys = set()
        pr_by_key = {}
        for p in prs:
            num = p.get("number")
            repo = p.get("repo")
            if num is not None:
                cohort_pr_keys.add((repo, num))
                pr_by_key[(repo, num)] = p
                if repo is None:
                    cohort_pr_keys.add((None, num))
                    pr_by_key[(None, num)] = p

        seen_observations = set()

        def record(stg, pr_key, s_dt, e_dt):
            """Add one interval; equivalent observations from different sources count once."""
            obs = (pr_key, stg, s_dt, e_dt)
            if obs in seen_observations:
                return
            seen_observations.add(obs)
            if e_dt < s_dt:
                stage_conflicts[stg] += 1
                return
            stage_durations[stg].append((e_dt - s_dt).total_seconds() / 3600.0)
            stage_covered_prs[stg].add(pr_key)

        # 1. From PR stage_transitions if attached to PR objects
        for p in prs:
            pr_key = (p.get("repo"), p.get("number"))
            for tr in p.get("stage_transitions") or []:
                stg = tr.get("stage") or tr.get("label")
                if stg in stage_durations:
                    s_dt = parse_iso_utc(tr.get("start_at") or tr.get("entered_at") or tr.get("start"))
                    e_dt = parse_iso_utc(tr.get("end_at") or tr.get("exited_at") or tr.get("end"))
                    if s_dt and e_dt:
                        record(stg, pr_key, s_dt, e_dt)

        # 2. From timeline_events
        if timeline_events:
            events_by_pr = {}
            for ev in timeline_events:
                ev_pr_num = ev.get("pr_number") or ev.get("pr_id") or ev.get("number")
                ev_repo = ev.get("repo")
                if ev_pr_num is None:
                    continue
                pr_key = (ev_repo, ev_pr_num)
                # Filter to cohort PRs only: require exact (repo, number) when repo is present
                if ev_repo is not None:
                    if pr_key not in cohort_pr_keys:
                        continue
                else:
                    if (None, ev_pr_num) not in cohort_pr_keys:
                        continue
                    pr_key = (None, ev_pr_num)
                events_by_pr.setdefault(pr_key, []).append(ev)

            for pr_key, ev_list in events_by_pr.items():
                pr_obj = pr_by_key.get(pr_key)
                if not pr_obj:
                    continue
                # Same identity as the PR's own stage_transitions so the sources reconcile.
                pr_key = (pr_obj.get("repo"), pr_obj.get("number"))
                for ev in ev_list:
                    stg = ev.get("stage") or ev.get("label")
                    if stg in stage_durations and (ev.get("start_at") or ev.get("entered_at")) and (ev.get("end_at") or ev.get("exited_at")):
                        s_dt = parse_iso_utc(ev.get("start_at") or ev.get("entered_at"))
                        e_dt = parse_iso_utc(ev.get("end_at") or ev.get("exited_at"))
                        if s_dt and e_dt:
                            record(stg, pr_key, s_dt, e_dt)

                # Chronological labeled/unlabeled events
                labeled_evs = sorted(
                    [e for e in ev_list if e.get("createdAt") and e.get("event") in ("labeled", "unlabeled")],
                    key=lambda x: parse_iso_utc(x.get("createdAt")) or datetime.min.replace(tzinfo=timezone.utc),
                )
                open_stages = {}
                for ev in labeled_evs:
                    ev_type = ev.get("event")
                    lbl = ev.get("label")
                    if isinstance(lbl, dict):
                        lbl = lbl.get("name")
                    if lbl not in stage_durations:
                        continue
                    dt = parse_iso_utc(ev.get("createdAt"))
                    if not dt:
                        continue

                    if ev_type == "labeled":
                        # Close any previously open stage upon transitioning to a new stage
                        for prev_lbl, s_dt in list(open_stages.items()):
                            if prev_lbl != lbl:
                                record(prev_lbl, pr_key, s_dt, dt)
                                del open_stages[prev_lbl]
                        open_stages.setdefault(lbl, dt)
                    elif ev_type == "unlabeled":
                        if lbl in open_stages:
                            record(lbl, pr_key, open_stages.pop(lbl), dt)

                # Close remaining open stages at terminal merge or close
                term_dt = parse_iso_utc(pr_obj.get("mergedAt")) or parse_iso_utc(pr_obj.get("closedAt"))
                if term_dt:
                    for prev_lbl, s_dt in list(open_stages.items()):
                        record(prev_lbl, pr_key, s_dt, term_dt)
                        del open_stages[prev_lbl]

        merged_in_cohort = [p for p in prs if p.get("mergedAt")]
        total_merged_count = len(merged_in_cohort) if merged_in_cohort else len(prs)

        stage_dwell_data = []
        for stg in stages:
            durs = sorted(stage_durations[stg])
            n = len(stage_covered_prs[stg])
            conflicts = stage_conflicts[stg]
            if durs:
                med_h = round(calculate_median(durs), 2)
                p75_h = round(calculate_nearest_rank_p75(durs), 2)
            else:
                med_h = "UNKNOWN"
                p75_h = "UNKNOWN"

            stage_dwell_data.append({
                "stage": stg,
                "median_h": med_h,
                "p75_h": p75_h,
                "n": n,
                "total_n": total_merged_count,
                "conflicts": conflicts,
            })

        return stage_dwell_data

    ROUND_TRANSITIONS = (
        ("evidence_ready -> review_requested", "evidence_ready_at", "review_requested_at"),
        ("review_requested -> actual_review_started", "review_requested_at", "actual_review_started_at"),
        ("review_return -> next_substantive_action", "review_return_at", "next_substantive_action_started_at"),
    )

    def adapt_run_stats_receipt(self, rec, prs):
        """
        Convert a canonical run.stats.json receipt (timestamps + rounds[]) into evidence-bound
        handoff records. The PR is identified by an explicit repo/pr_number on the receipt, else by
        the receipt's candidate_sha equalling exactly one PR head. Unidentified receipts yield nothing.
        """
        num = rec.get("pr_number") or rec.get("number")
        repo = rec.get("repo")
        pr = None
        if repo and num is not None:
            pr = next((p for p in prs if p.get("repo") == repo and p.get("number") == num), None)
        elif rec.get("candidate_sha"):
            heads = [p for p in prs if p.get("headRefOid") == rec["candidate_sha"] and p.get("repo")]
            pr = heads[0] if len(heads) == 1 else None
        if not pr:
            return []

        base = {
            "repo": pr["repo"],
            "number": pr["number"],
            "source_receipt": rec.get("source_receipt") or "",
        }
        out = []
        for rnd in rec.get("rounds") or []:
            if not isinstance(rnd, dict) or not rnd.get("candidate_sha") or rnd.get("round") is None:
                continue
            for name, start_key, end_key in self.ROUND_TRANSITIONS:
                if rnd.get(start_key) and rnd.get(end_key):
                    out.append(dict(
                        base, name=name, candidate_sha=rnd["candidate_sha"], attempt_number=rnd["round"],
                        start_at=rnd[start_key], end_at=rnd[end_key],
                    ))
        ts = rec["timestamps"]
        if rec.get("candidate_sha") and ts.get("accepted_at") and ts.get("merged_at"):
            out.append(dict(
                base, name="task_accepted -> merged", candidate_sha=rec["candidate_sha"], attempt_number=1,
                start_at=ts["accepted_at"], end_at=ts["merged_at"],
            ))
        return out

    def compute_handoff_breakdown(self, prs, handoff_records=None, total_cohort_n=None):
        """
        Compute observed counts, medians, and telemetry coverage across the 6 transitions:
        1. evidence_ready -> review_requested
        2. review_requested -> actual_review_started (strictly requiring actual_review_started_at)
        3. review_return -> next_substantive_action
        4. authority_ready -> merged (using derive_authority_ready)
        5. task_accepted -> merged (using initial_task_accepted_at, never closure_sprint_accepted_at)
        6. closure_sprint_accepted -> merged (using closure_sprint_accepted_at)
        """
        transitions = [
            "evidence_ready -> review_requested",
            "review_requested -> actual_review_started",
            "review_return -> next_substantive_action",
            "authority_ready -> merged",
            "task_accepted -> merged",
            "closure_sprint_accepted -> merged",
        ]
        # Observations keyed by full identity so a PR field and its receipt count once.
        trans_obs = {t: {} for t in transitions}

        def add_pr_field(p, t_name, start, end):
            if not (start and end):
                return
            res = self.compute_interval_duration(start, end)
            if res["status"] != "OK":
                return
            cohort = (p.get("repo"), p.get("number"))
            dur = res["duration_sec"]
            key = (cohort, t_name, p.get("headRefOid") or "", p.get("attempt") or 1)
            trans_obs[t_name].setdefault(key, (cohort, dur))

        for p in prs:
            add_pr_field(p, "evidence_ready -> review_requested", p.get("evidence_ready_at"), p.get("review_requested_at"))
            add_pr_field(p, "review_requested -> actual_review_started", p.get("review_requested_at"), p.get("actual_review_started_at"))
            add_pr_field(
                p, "review_return -> next_substantive_action",
                p.get("review_returned_at") or p.get("review_completed_at"),
                p.get("next_action_started_at") or p.get("next_substantive_action_at"),
            )
            if self.derive_authority_ready(p) == "READY":
                add_pr_field(p, "authority_ready -> merged", p.get("authority_ready_at"), p.get("mergedAt"))
            add_pr_field(p, "task_accepted -> merged", p.get("initial_task_accepted_at"), p.get("mergedAt"))
            add_pr_field(p, "closure_sprint_accepted -> merged", p.get("closure_sprint_accepted_at"), p.get("mergedAt"))

        if handoff_records:
            records_to_process = []
            if isinstance(handoff_records, list):
                records_to_process = handoff_records
            elif isinstance(handoff_records, dict):
                if "records" in handoff_records and isinstance(handoff_records["records"], list):
                    records_to_process = handoff_records["records"]
                elif "handoffs" in handoff_records and isinstance(handoff_records["handoffs"], list):
                    records_to_process = handoff_records["handoffs"]

            prs_by_key = {}
            for p in prs:
                if p.get("repo") and p.get("number") is not None:
                    prs_by_key[(p["repo"], p["number"])] = p

            expanded = []
            for rec in records_to_process:
                if isinstance(rec, dict) and isinstance(rec.get("timestamps"), dict):
                    expanded.extend(self.adapt_run_stats_receipt(rec, prs))
                else:
                    expanded.append(rec)

            for rec in expanded:
                if not isinstance(rec, dict):
                    continue
                t_name = rec.get("name") or rec.get("transition")
                if t_name not in trans_obs:
                    continue

                # Exact repo+number identity; repo-less or number-less records stay unmatched.
                rec_pr_num = rec.get("pr_number") or rec.get("number")
                rec_repo = rec.get("repo")
                matched_pr = prs_by_key.get((rec_repo, rec_pr_num)) if rec_repo and rec_pr_num is not None else None
                if not matched_pr:
                    continue

                # Evidence-bound identity: never invent a candidate or attempt.
                candidate_sha = rec.get("candidate_sha") or rec.get("head_sha")
                attempt_num = rec.get("attempt_number") or rec.get("attempt")
                if not candidate_sha or attempt_num is None:
                    continue
                source_receipt = rec.get("source_receipt") or rec.get("receipt_id") or ""

                cohort = (matched_pr.get("repo"), matched_pr.get("number"))
                dedup_key = (cohort, t_name, candidate_sha, attempt_num)
                if dedup_key in trans_obs[t_name]:
                    continue

                if t_name == "authority_ready -> merged":
                    is_ready = self.derive_authority_ready(matched_pr) == "READY"
                    has_explicit = (
                        rec.get("final_ready") is True
                        and rec.get("merge_authority") is True
                        and bool(rec.get("authority_ready_at"))
                    )
                    if not is_ready and not has_explicit:
                        continue

                computed_sec = None
                if rec.get("start_at") and rec.get("end_at"):
                    res = self.compute_interval_duration(rec["start_at"], rec["end_at"])
                    if res.get("status") == "OK" and res.get("duration_sec") is not None:
                        computed_sec = float(res["duration_sec"])
                elif "duration_sec" in rec:
                    raw_dur = rec.get("duration_sec")
                    if (
                        isinstance(raw_dur, (int, float))
                        and not isinstance(raw_dur, bool)
                        and math.isfinite(float(raw_dur))
                        and float(raw_dur) >= 0
                        and source_receipt
                    ):
                        computed_sec = float(raw_dur)

                if computed_sec is None or not math.isfinite(computed_sec) or computed_sec < 0:
                    continue
                trans_obs[t_name][dedup_key] = (cohort, computed_sec)

        tot = total_cohort_n if total_cohort_n is not None else len(prs)

        handoffs_data = []
        for t in transitions:
            durs = sorted(d for _, d in trans_obs[t].values())
            sample_n = len(durs)
            obs_n = len({c for c, _ in trans_obs[t].values()})
            if sample_n > 0:
                med_sec = round(calculate_median(durs), 1)
                p75_sec = round(calculate_nearest_rank_p75(durs), 1)
                status = "COMPLETE" if (tot > 0 and obs_n >= tot) else "PARTIAL"
            else:
                med_sec = "UNKNOWN"
                p75_sec = "UNKNOWN"
                status = "UNKNOWN"

            handoffs_data.append({
                "name": t,
                "observed_n": obs_n,
                "sample_n": sample_n,
                "total_n": tot,
                "median_sec": med_sec,
                "p75_sec": p75_sec,
                "status": status,
            })

        return handoffs_data

    def aggregate_full_dataset(
        self,
        prs,
        timeline_events=None,
        sources=None,
        handoff_records=None,
        time_semantics_pilot=None,
        human_episodes=None,
        now_dt=None,
        stale_threshold_hours=4.5,
    ):
        """Produce full structured dashboard summary."""
        w1_s, w2_s, cutoff = self.w1_start_dt, self.w2_start_dt, self.cutoff_dt
        now_dt = now_dt or datetime.now(timezone.utc)

        # Derive data_through_dt from sources cutoff
        source_cutoffs = []
        unknown_cutoff = False
        if sources:
            for s in sources.values():
                if isinstance(s, dict) and s.get("status") != "EMPTY":
                    c_dt = parse_iso_utc(s.get("cutoff"))
                    if c_dt:
                        source_cutoffs.append(c_dt)
                    else:
                        unknown_cutoff = True

        if unknown_cutoff:
            data_through_dt = None
        elif source_cutoffs:
            data_through_dt = min(source_cutoffs)
        else:
            data_through_dt = None

        # Group by repository
        repos = sorted(list(set(p.get("repo") for p in prs if p.get("repo"))))

        repo_rows = []
        all_created_w1 = filter_events_half_open(prs, "createdAt", w1_s, w2_s)
        all_created_w2 = filter_events_half_open(prs, "createdAt", w2_s, cutoff)
        all_merged_w1 = filter_events_half_open(prs, "mergedAt", w1_s, w2_s)
        all_merged_w2 = filter_events_half_open(prs, "mergedAt", w2_s, cutoff)
        all_closed_w1 = [p for p in filter_events_half_open(prs, "closedAt", w1_s, w2_s) if not p.get("mergedAt")]
        all_closed_w2 = [p for p in filter_events_half_open(prs, "closedAt", w2_s, cutoff) if not p.get("mergedAt")]
        all_current_closed = [p for p in prs if p.get("state") == "CLOSED" and not p.get("mergedAt")]
        all_still_open = [p for p in prs if p.get("state") == "OPEN"]

        for repo in repos:
            repo_prs = [p for p in prs if p.get("repo") == repo]
            created_w1 = filter_events_half_open(repo_prs, "createdAt", w1_s, w2_s)
            created_w2 = filter_events_half_open(repo_prs, "createdAt", w2_s, cutoff)
            merged_w1 = filter_events_half_open(repo_prs, "mergedAt", w1_s, w2_s)
            merged_w2 = filter_events_half_open(repo_prs, "mergedAt", w2_s, cutoff)
            closed_w1 = [
                p for p in filter_events_half_open(repo_prs, "closedAt", w1_s, w2_s)
                if not p.get("mergedAt")
            ]
            closed_w2 = [
                p for p in filter_events_half_open(repo_prs, "closedAt", w2_s, cutoff)
                if not p.get("mergedAt")
            ]
            current_closed = [p for p in repo_prs if p.get("state") == "CLOSED" and not p.get("mergedAt")]
            still_open = [p for p in repo_prs if p.get("state") == "OPEN"]

            stats_w1 = self.summarize_window_cohort(merged_w1)
            stats_w2 = self.summarize_window_cohort(merged_w2)

            repo_rows.append({
                "repo": repo,
                "created": len(created_w2),
                "created_w1": len(created_w1),
                "created_w2": len(created_w2),
                "merged_w1": len(merged_w1),
                "merged_w2": len(merged_w2),
                "closed_unmerged_w1": len(closed_w1),
                "closed_unmerged_w2": len(closed_w2),
                "current_closed_unmerged": len(current_closed),
                "still_open": len(still_open),
                "w1_all_median_hours": stats_w1["all_median_hours"],
                "w1_all_p75_hours": stats_w1["all_p75_hours"],
                "all_median_hours": stats_w2["all_median_hours"],
                "all_p75_hours": stats_w2["all_p75_hours"],
                "w1_comp_median_hours": stats_w1["comp_median_hours"],
                "w1_comp_p75_hours": stats_w1["comp_p75_hours"],
                "comp_median_hours": stats_w2["comp_median_hours"],
                "comp_p75_hours": stats_w2["comp_p75_hours"],
                "w1_backlog_n": stats_w1["backlog_n"],
                "w1_backlog_median_hours": stats_w1["backlog_median_hours"],
                "backlog_n": stats_w2["backlog_n"],
                "backlog_median_hours": stats_w2["backlog_median_hours"],
            })

        overall_stats_w1 = self.summarize_window_cohort(all_merged_w1)
        overall_stats_w2 = self.summarize_window_cohort(all_merged_w2)

        repo_rows.append({
            "repo": "Combined (All Repos)",
            "created": len(all_created_w2),
            "created_w1": len(all_created_w1),
            "created_w2": len(all_created_w2),
            "merged_w1": len(all_merged_w1),
            "merged_w2": len(all_merged_w2),
            "closed_unmerged_w1": len(all_closed_w1),
            "closed_unmerged_w2": len(all_closed_w2),
            "current_closed_unmerged": len(all_current_closed),
            "still_open": len(all_still_open),
            "w1_all_median_hours": overall_stats_w1["all_median_hours"],
            "w1_all_p75_hours": overall_stats_w1["all_p75_hours"],
            "all_median_hours": overall_stats_w2["all_median_hours"],
            "all_p75_hours": overall_stats_w2["all_p75_hours"],
            "w1_comp_median_hours": overall_stats_w1["comp_median_hours"],
            "w1_comp_p75_hours": overall_stats_w1["comp_p75_hours"],
            "comp_median_hours": overall_stats_w2["comp_median_hours"],
            "comp_p75_hours": overall_stats_w2["comp_p75_hours"],
            "w1_backlog_n": overall_stats_w1["backlog_n"],
            "w1_backlog_median_hours": overall_stats_w1["backlog_median_hours"],
            "backlog_n": overall_stats_w2["backlog_n"],
            "backlog_median_hours": overall_stats_w2["backlog_median_hours"],
        })

        # Stage dwell computation
        stage_dwell_data = self.compute_stage_dwell(all_merged_w2, timeline_events=timeline_events)

        # Handoff breakdown
        handoffs = self.compute_handoff_breakdown(
            all_merged_w2,
            handoff_records=handoff_records,
            total_cohort_n=len(all_merged_w2),
        )

        # Open PRs attention: partition into 5A (known idle) and 5B (unknown idle)
        open_prs_known = []
        open_prs_unknown = []
        for p in all_still_open:
            idle = self.compute_eligible_unattended_duration(p)
            stg_lbl = next(
                (l for l in p.get("labels", []) if isinstance(l, str) and l.startswith("stage:")),
                p.get("legacy_stage") or "stage:unknown",
            )
            sha = p.get("headRefOid") or "UNKNOWN"
            op_st = p.get("operational_status") or "unknown"
            op_det = p.get("operational_detail") or ""
            title_status = f"[{op_st}][{op_det}]" if op_st != "unknown" else "UNKNOWN"

            # Use "UNKNOWN" (not hardcoded assumptions) when unrecorded
            hold_status = p.get("hold_status") or (f"HOLD: {op_det}" if op_st in ("blocked", "waiting") else "UNKNOWN")
            next_action = p.get("next_action") or (f"Resume {op_det}" if op_st in ("waiting", "blocked") else "UNKNOWN")
            earliest_unmet = p.get("earliest_unmet_obligation") or "UNKNOWN"
            owner = p.get("owner") or "UNKNOWN"

            if idle.get("status") == "OK" and idle.get("duration_sec") is not None:
                open_prs_known.append({
                    "url": p.get("url"),
                    "sha": sha,
                    "stage": stg_lbl,
                    "title_status": title_status,
                    "earliest_unmet_obligation": earliest_unmet,
                    "next_action": next_action,
                    "owner": owner,
                    "hold_status": hold_status,
                    "job_handle": p.get("job_handle") or "UNKNOWN",
                    "wake_condition": p.get("wake_condition") or "UNKNOWN",
                    "receipt_links": p.get("receipt_links") or [],
                    "eligible_unattended_duration_sec": idle["duration_sec"],
                })
            else:
                u_dt = parse_iso_utc(p.get("updatedAt")) or parse_iso_utc(p.get("createdAt"))
                quiet_hrs = round((cutoff - u_dt).total_seconds() / 3600.0, 1) if u_dt else "UNKNOWN"
                open_prs_unknown.append({
                    "url": p.get("url"),
                    "sha": sha,
                    "stage": stg_lbl,
                    "title_status": title_status,
                    "earliest_unmet_obligation": earliest_unmet,
                    "next_action": next_action,
                    "owner": owner,
                    "hold_status": hold_status,
                    "potential_handoff_waiting": p.get("potential_handoff_waiting") or "UNKNOWN",
                    "job_handle": p.get("job_handle") or "UNKNOWN",
                    "wake_condition": p.get("wake_condition") or "UNKNOWN",
                    "receipt_links": p.get("receipt_links") or [],
                    "quiet_time": f"{quiet_hrs}h" if isinstance(quiet_hrs, (int, float)) else "UNKNOWN",
                })

        # Sort 5A descending by eligible unattended duration
        open_prs_known.sort(key=lambda x: x["eligible_unattended_duration_sec"], reverse=True)

        # Status resolution
        status = "FRESH"
        if not prs:
            status = "EMPTY"
        failed_count = sum(1 for s in (sources or {}).values() if s.get("status") in ("FAILED", "PARTIAL_FAILURE"))
        if failed_count > 0:
            status = "PARTIAL_FAILURE" if prs else "FAILED"
        elif sources and any(s.get("status") == "FAILED" for s in sources.values()):
            status = "PARTIAL_FAILURE" if prs else "FAILED"
        elif sources and any(s.get("status") == "STALE" or s.get("cutoff") is None for s in sources.values()):
            status = "STALE"
        elif data_through_dt is None or (now_dt - data_through_dt) > timedelta(hours=stale_threshold_hours):
            status = "STALE"
        elif source_cutoffs and any((now_dt - c) > timedelta(hours=stale_threshold_hours) for c in source_cutoffs):
            status = "STALE"

        # Reporting scope: the configured repo list when given, else the repos present in the PR set.
        scope_repos = set(self.configured_repos) or set(repos)

        # Pilot time semantics
        if time_semantics_pilot is None:
            time_semantics_pilot = []
            target_cohort = all_merged_w2
            for p in target_cohort:
                ts = self.compute_time_semantics(p)
                if ts.get("task_elapsed_sec") is not None or ts.get("observed_active_wall_sec") is not None:
                    time_semantics_pilot.append(ts)
        elif isinstance(time_semantics_pilot, list) and time_semantics_pilot:
            is_raw_events = any(
                isinstance(x, dict) and ("event_type" in x or "span_kind" in x or "event_id" in x) and "pr_url" not in x
                for x in time_semantics_pilot
            )
            if is_raw_events:
                grouped = {}
                for ev in time_semantics_pilot:
                    r = ev.get("repo")
                    n = ev.get("pr_number") or ev.get("number")
                    if not r or (scope_repos and r not in scope_repos) or not self.event_in_window(ev, w1_s, cutoff):
                        continue
                    grouped.setdefault((r, n), []).append(ev)

                pr_map = {}
                for p in prs:
                    pr_map[(p.get("repo"), p.get("number"))] = p

                processed_pilot = []
                for (r, n), ev_group in grouped.items():
                    pr_obj = pr_map.get((r, n)) if r and n is not None else None
                    if not pr_obj:
                        pr_url = f"https://github.com/{r}/pull/{n}" if r and n else f"https://github.com/unknown/pull/{n or 0}"
                        pr_obj = {"repo": r, "number": n, "url": pr_url}
                    ts = self.compute_time_semantics(pr_obj, pilot_events=ev_group)
                    processed_pilot.append(ts)
                time_semantics_pilot = processed_pilot

        # Human interventions
        human_summary = None
        if human_episodes is not None:
            scoped_episodes = [
                ep for ep in human_episodes if self.episode_in_scope(ep, w1_s, cutoff, scope_repos)
            ]
            human_summary = self.compute_human_interventions(scoped_episodes, cohort_prs_count=len(all_merged_w2))

        return {
            "status": status,
            "generated_at": format_iso_utc(datetime.now(timezone.utc)),
            "data_through": format_iso_utc(data_through_dt) if data_through_dt else "UNKNOWN",
            "w1_bounds": (format_iso_utc(w1_s), format_iso_utc(w2_s)),
            "w2_bounds": (format_iso_utc(w2_s), format_iso_utc(cutoff)),
            "w2_merged_cohort_n": len(all_merged_w2),
            "sources": sources or {},
            "repo_comparison": repo_rows,
            "stage_dwell": stage_dwell_data,
            "handoffs": handoffs,
            "open_prs_known_idle": open_prs_known,
            "open_prs_unknown_idle": open_prs_unknown,
            "time_semantics_pilot": time_semantics_pilot,
            "human_interventions": human_summary,
        }


# -----------------------------------------------------------------------------
# Task 3: Dashboard Rendering
# -----------------------------------------------------------------------------

class DashboardRenderer:
    """Renders structured summary data into GitHub-flavored Markdown."""

    def render(self, data):
        data = _project_summary(data)
        status = data.get("status", "UNKNOWN")
        gen_at = data.get("generated_at", "UNKNOWN")
        data_through = data.get("data_through", "UNKNOWN")
        w1_s, w1_e = data.get("w1_bounds", ("UNKNOWN", "UNKNOWN"))
        w2_s, w2_e = data.get("w2_bounds", ("UNKNOWN", "UNKNOWN"))
        sources = data.get("sources", {})

        md = []

        # Section 1: Header & Coverage
        md.append("# PRW Metrics Dashboard")
        md.append("")
        md.append("## 1. Header & Coverage")
        md.append("")
        md.append(f"- **Status**: **{status}**")
        md.append(f"- **Generated at (UTC)**: `{gen_at}`")
        md.append(f"- **Data through / Cutoff (UTC)**: `{data_through}`")
        md.append(f"- **Window Bounds**:")
        md.append(f"  - `W1 (Preceding 7d)`: `[{w1_s} to {w1_e})`")
        md.append(f"  - `W2 (Recent 7d)`: `[{w2_s} to {w2_e})`")
        md.append(f"- **Last Successful Collection**: `{data_through}`")
        md.append(f"- **Manual Refresh**: Trigger via `scripts/run_prw_metrics.sh` on host or local CLI.")
        md.append("")
        md.append("### Per-Source Collection Manifest")
        md.append("")
        if sources:
            md.append("| Source | Status | Details / Cutoff |")
            md.append("|---|---|---|")
            for src_name, src_info in sorted(sources.items()):
                s_stat = src_info.get("status", "UNKNOWN")
                s_det = src_info.get("cutoff") or ""
                md.append(f"| `{src_name}` | **{s_stat}** | `{s_det}` |")
        else:
            md.append("*No per-source manifest available.*")
        md.append("")

        # Section 2: Repository Comparison
        md.append("## 2. Repository Comparison")
        md.append("")
        has_w1 = any("created_w1" in row for row in data.get("repo_comparison", []))

        def hours(value):
            return f"{value}h" if isinstance(value, (int, float)) else str(value or "UNKNOWN")

        if has_w1:
            md.append("| Repository | Created (W1 -> W2) | Merged (W1 -> W2) | Closed-Unmerged (W1 -> W2) | Closed Total | Open | Creation-to-Merge Median (W1 -> W2) | Nearest-Rank p75 (W1 -> W2) | <=7d Sensitivity Median (W1 -> W2) | Backlog Merges (>7d) (W1 -> W2) |")
        else:
            md.append("| Repository | Created (W2) | Merged (W1 -> W2) | Closed-Unmerged (W2) | Closed Total | Open | Creation-to-Merge Median (W2) | Nearest-Rank p75 | <=7d Sensitivity Median | Backlog Merges (>7d) |")
        md.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for row in data.get("repo_comparison", []):
            if "created_w1" in row:
                created_str = f"{row['created_w1']} -> {row['created']}"
                closed_str = f"{row['closed_unmerged_w1']} -> {row['closed_unmerged_w2']}"
                all_med_str = f"{hours(row.get('w1_all_median_hours'))} -> {hours(row['all_median_hours'])}"
                all_p75_str = f"{hours(row.get('w1_all_p75_hours'))} -> {hours(row['all_p75_hours'])}"
                comp_med_str = f"{hours(row.get('w1_comp_median_hours'))} -> {hours(row['comp_median_hours'])}"
                backlog_str = f"{row.get('w1_backlog_n', 0)} ({hours(row.get('w1_backlog_median_hours'))}) -> {row['backlog_n']} ({hours(row['backlog_median_hours'])})"
            else:
                created_str = str(row['created'])
                closed_str = str(row['closed_unmerged_w2'])
                all_med_str = hours(row['all_median_hours'])
                all_p75_str = hours(row['all_p75_hours'])
                comp_med_str = hours(row['comp_median_hours'])
                backlog_str = f"{row['backlog_n']} ({hours(row['backlog_median_hours'])})"

            md.append(
                f"| {row['repo']} | {created_str} | {row['merged_w1']} -> {row['merged_w2']} | "
                f"{closed_str} | {row['current_closed_unmerged']} | {row['still_open']} | "
                f"{all_med_str} | {all_p75_str} | {comp_med_str} | "
                f"{backlog_str} |"
            )
        if not data.get("repo_comparison"):
            md.append("| *No repository data available* | - | - | - | - | - | - | - | - | - |")
        md.append("")

        # Section 3: Stage Dwell
        md.append("## 3. Stage Dwell")
        md.append("")
        md.append("> ℹ️ **Elapsed Stage Time vs Agent Idle**: Dwell time measures total elapsed calendar time within each stage. It is NOT agent idle time.")
        md.append("")
        if data.get("w2_merged_cohort_n") == 0:
            md.append("> No merges in window W2: stage dwell, handoff and pilot metrics have an empty cohort (UNKNOWN, n = 0); no historical or open PRs are substituted.")
            md.append("")
        md.append("| Lifecycle Stage | Covered Merged PRs (n / N) | Median Dwell | Nearest-Rank p75 | Clock Conflicts |")
        md.append("|---|---:|---:|---:|---:|")
        for row in data.get("stage_dwell", []):
            med = f"{row['median_h']}h" if isinstance(row['median_h'], (int, float)) else row['median_h']
            p75 = f"{row['p75_h']}h" if isinstance(row['p75_h'], (int, float)) else row['p75_h']
            md.append(f"| `{row['stage']}` | {row['n']} / {row['total_n']} | {med} | {p75} | {row['conflicts']} |")
        if not data.get("stage_dwell"):
            md.append("| *No stage dwell events observed* | 0 / 0 | UNKNOWN | UNKNOWN | 0 |")
        md.append("")

        # Section 4: Handoff Waiting Breakdown
        md.append("## 4. Handoff Waiting Breakdown")
        md.append("")
        md.append("| Handoff Transition | Observed Events (n / N) | Median Duration | Telemetry Coverage | Status |")
        md.append("|---|---:|---:|---:|---|")
        for h in data.get("handoffs", []):
            cov = "0%"
            n = h.get("observed_n", 0)
            tot = h.get("total_n", 0)
            if tot > 0:
                cov = f"{(n / tot) * 100:.1f}%"
            med_sec = h.get("median_sec", "UNKNOWN")
            med_str = format_duration(med_sec) if isinstance(med_sec, (int, float)) else str(med_sec)
            status_str = h.get("status", "UNKNOWN" if n == 0 else "PARTIAL")
            md.append(f"| `{h['name']}` | {n} / {tot} | {med_str} | {cov} | {status_str} |")
        if not data.get("handoffs"):
            md.append("| *No handoff transitions recorded* | 0 / 0 | UNKNOWN | 0% | UNKNOWN |")
        md.append("")

        # Section 4b: Time Semantics & Effort Breakdown (Pilot Cohort)
        md.append("## 4b. Time Semantics & Effort Breakdown (Pilot Cohort)")
        md.append("")
        md.append("> ℹ️ **Elapsed Time vs Active Effort**: Residual elapsed minus observed active is NOT wasted time. It contains known waits, human decisions, and unobserved periods. Agent effort (arithmetic sum of concurrent agents) may exceed elapsed wall time.")
        md.append("")
        ts_rows = data.get("time_semantics_pilot", [])
        if ts_rows:
            md.append("| PR | PR Elapsed | Task Elapsed | Closure Sprint | Observed Operation | Active Wall Time | Agent Effort | Explicit Waiting | Avoidable Delay |")
            md.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
            for r in ts_rows:
                pr_url = r.get("pr_url", "UNKNOWN")
                pr_link = f"[{pr_url}]({pr_url})" if pr_url.startswith("http") else f"`{pr_url}`"
                p_el = format_duration(r.get("pr_elapsed_sec")) if r.get("pr_elapsed_sec") is not None else "UNKNOWN"
                t_el = format_duration(r.get("task_elapsed_sec")) if r.get("task_elapsed_sec") is not None else "UNKNOWN"
                c_sp = format_duration(r.get("closure_sprint_to_merge_sec")) if r.get("closure_sprint_to_merge_sec") is not None else "UNKNOWN"
                o_op = format_duration(r.get("observed_operation_elapsed_sec")) if r.get("observed_operation_elapsed_sec") is not None else "UNKNOWN"
                if r.get("observed_operation_elapsed_sec") is not None:
                    o_op = f"{o_op} ({r.get('operation_elapsed_basis') or 'BASIS UNKNOWN'})"
                a_wl = format_duration(r.get("observed_active_wall_sec")) if r.get("observed_active_wall_sec") is not None else "UNKNOWN"
                a_ef = format_duration(r.get("agent_effort_sec")) if r.get("agent_effort_sec") is not None else "UNKNOWN"
                e_wt = format_duration(r.get("explicit_waiting_sec")) if r.get("explicit_waiting_sec") is not None else "UNKNOWN"
                a_un = format_duration(r.get("avoidable_unattended_sec")) if r.get("avoidable_unattended_sec") is not None else "UNKNOWN"
                md.append(f"| {pr_link} | {p_el} | {t_el} | {c_sp} | {o_op} | {a_wl} | {a_ef} | {e_wt} | {a_un} |")
        else:
            md.append("*No pilot cohort time semantics recorded.*")
        md.append("")

        # Section 5: Open PR Attention Table
        md.append("## 5. Open PR Attention Table")
        md.append("")
        md.append("### 5A. Open PRs with Observed Eligible Unattended Duration")
        md.append("")
        if data.get("open_prs_known_idle"):
            md.append("| PR | Head SHA | Stage | Title Status | Earliest Unmet Obligation | Actionable Next Step | Owner | Hold Status | Job Handle | Wake Condition | Receipts | Eligible Unattended Duration |")
            md.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
            for pr in data.get("open_prs_known_idle"):
                md.append(f"| [{pr['url']}]({pr['url']}) | `{pr['sha'][:7]}` | `{pr['stage']}` | {pr.get('title_status', 'UNKNOWN')} | {pr.get('earliest_unmet_obligation', 'UNKNOWN')} | {pr['next_action']} | `{pr['owner']}` | {pr['hold_status']} | {pr.get('job_handle', 'UNKNOWN')} | {pr.get('wake_condition', 'UNKNOWN')} | {render_receipt_links(pr.get('receipt_links'))} | **{format_duration(pr['eligible_unattended_duration_sec'])}** |")
        else:
            md.append("*No open PRs currently exhibit proven eligible unattended duration.*")
        md.append("")
        md.append("### 5B. Open PRs with Unknown Eligibility (Telemetry Coverage 0%)")
        md.append("")
        md.append("> ℹ️ **Notice**: These PRs lack fine-grained active-worker/hold-state telemetry. They are reported transparently for operator attention and are NOT ranked as idle.")
        md.append("")
        if data.get("open_prs_unknown_idle"):
            md.append("| PR | Head SHA | Stage | Title Status | Earliest Unmet Obligation | Next Action | Owner | Hold Status | Job Handle | Wake Condition | Receipts | Potential Handoff Waiting | GitHub Quiet Time (Proxy Only) |")
            md.append("|---|---|---|---|---|---|---|---|---|---|---|---:|---:|")
            for pr in data.get("open_prs_unknown_idle"):
                md.append(
                    f"| [{pr['url']}]({pr['url']}) | `{pr['sha'][:7]}` | `{pr['stage']}` | "
                    f"{pr.get('title_status', 'UNKNOWN')} | "
                    f"{pr.get('earliest_unmet_obligation', 'UNKNOWN')} | {pr.get('next_action', 'UNKNOWN')} | "
                    f"`{pr.get('owner', 'UNKNOWN')}` | {pr.get('hold_status', 'UNKNOWN')} | "
                    f"{pr.get('job_handle', 'UNKNOWN')} | {pr.get('wake_condition', 'UNKNOWN')} | "
                    f"{render_receipt_links(pr.get('receipt_links'))} | "
                    f"{pr.get('potential_handoff_waiting', 'UNKNOWN')} | {pr.get('quiet_time', 'UNKNOWN')} |"
                )
        else:
            md.append("*No open PRs pending.*")
        md.append("")

        # Section 5b: Human Interventions, Episode Calibration & Retention
        md.append("## 5b. Human Interventions, Episode Calibration & Retention")
        md.append("")
        md.append("> ℹ️ **Intervention Calibration**: Measures causes of human interventions (good/value-adding vs bad/avoidable vs mixed/calibrated), excluding automated prompts and bots. \"No observed intervention\" is not \"zero-touch\" unless all relevant channels are proven covered.")
        md.append("")
        hi = data.get("human_interventions")
        if hi:
            raw_msgs = hi.get("raw_human_messages", 0)
            raw_message_coverage = hi.get("raw_message_count_coverage", "UNKNOWN")
            initial_reqs = hi.get("initial_task_requests", 0)
            qual_eps = hi.get("qualifying_episodes", 0)
            unver_excl = hi.get("unverified_origin_excluded", 0)
            dot_tail = hi.get("dot_page_tail_partial_count", 0)
            lbls = hi.get("label_breakdown", {})
            pr_attr = hi.get("pr_attributed_count", 0)
            unass = hi.get("unassigned_count", 0)
            post_m = hi.get("post_merge_count", 0)
            cov = hi.get("channel_coverage", {})
            ret_stat = hi.get("retention_status", "OK")

            md.append(f"- **Raw Human Messages**: {raw_msgs} (`{raw_message_coverage}`)")
            if initial_reqs:
                md.append(f"- **Initial Task Requests**: {initial_reqs}")
            md.append(f"- **Qualifying Episodes**: {qual_eps}")
            if unver_excl:
                md.append(f"- **Unverified Origin Excluded Messages**: {unver_excl}")
            if dot_tail:
                md.append(f"- **Dot Page-Tail (No Timestamps) Excluded**: {dot_tail}")
            md.append(f"- **Episode Breakdown**:")
            md.append(f"  - **Good / Value-Adding**: {lbls.get('good', 0)}")
            md.append(f"  - **Bad / Avoidable**: {lbls.get('bad', 0)}")
            md.append(f"  - **Mixed / Calibration Disagreement**: {lbls.get('mixed', 0)}")
            md.append(f"  - **Unknown / Unclear**: {lbls.get('unknown', 0)}")
            md.append(f"- **Attribution**:")
            md.append(f"  - **PR-Attributed Episodes**: {pr_attr}")
            md.append(f"  - **Unassigned / Task-Level Episodes**: {unass}")
            md.append(f"  - **Post-Merge Episodes**: {post_m}")
            md.append(f"- **Channel Coverage**:")
            if cov:
                for ch, st in sorted(cov.items()):
                    md.append(f"  - `{ch}`: `{st}`")
            else:
                md.append("  - *No channel coverage metadata available.*")
            md.append(f"- **Retention Status**: `{ret_stat}`")
        else:
            md.append("*No human intervention telemetry available.*")
        md.append("")

        # Section 6: Definitions & Limitations
        md.append("## 6. Definitions & Limitations")
        md.append("")
        md.append("### Three Distinct Quantities")
        md.append("1. **Observed Eligible Unattended Duration**: Duration during which a specific next action was proven executable and authorized, no agent/job was active, and no external dependency or legitimate operator hold applied. Computed as the disjoint union of validated idle intervals (never double-counting parallel obligations). Requires complete telemetry; unobserved intervals read `UNKNOWN` (never `0`).")
        md.append("2. **Potential Handoff Waiting**: Elapsed calendar duration between two observed handoff timestamps (e.g. `review_returned` to `next_action_started`). May include legitimate operator reflection or dependency resolution; not interpreted as neglect.")
        md.append("3. **GitHub Quiet Time**: Elapsed time since the last recorded GitHub PR event (comment, commit, review). Serves as a coarse proxy only; does not prove background process inactivity.")
        md.append("")
        md.append("### Statistical Method")
        md.append("- **Nearest-Rank p75**: `k = math.ceil(0.75 * n) - 1` on 0-indexed sorted arrays.")
        md.append("- **Backlog Merges**: Merges where `mergedAt - createdAt > 7 days` (168 hours) at merge time, separated from fresh 7-day velocity.")
        md.append("- **Four-Hour Sampling Uncertainty**: Snapshots refresh on a 4-hour cycle. Exact event start/stop times possess an inherent 4-hour observation granularity.")
        md.append("- **Sanitization & Portability Guarantee**: No credentials, private tokens, raw model payloads, or personal filesystem paths are written to this dashboard.")
        md.append("")

        return _scrub_secrets("\n".join(md))


def render_dashboard(data):
    """Convenience functional wrapper for DashboardRenderer."""
    renderer = DashboardRenderer()
    return renderer.render(data)


# -----------------------------------------------------------------------------
# Task 5: Safe Scoped Git Publisher
# -----------------------------------------------------------------------------

def extract_github_repo_slug(url):
    """
    Extract owner/repo slug from GitHub URL without stripping valid name characters.
    e.g. 'git@github.com:acme/testing.git' -> 'acme/testing'
    """
    if not url or not isinstance(url, str):
        return None
    url = url.strip()
    scp_match = re.fullmatch(r"(?:[\w.-]+@)?github\.com:(.+)", url)
    if scp_match and "://" not in url:
        path = scp_match.group(1)
    else:
        try:
            parts = urlsplit(url)
            port = parts.port
        except ValueError:
            return None
        if parts.scheme not in ("https", "ssh") or port is not None:
            return None
        if (parts.hostname or "").lower() != "github.com":
            return None
        if parts.query or parts.fragment:
            return None
        path = parts.path.lstrip("/")
    path = path.rstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    components = path.split("/")
    if len(components) != 2:
        return None
    if not all(re.fullmatch(r"[A-Za-z0-9_.-]+", c) and c not in (".", "..") for c in components):
        return None
    return "/".join(components)


class Publisher:
    """Publishes dashboard Markdown to a designated Git repository using an isolated index file."""

    def __init__(self, repo_path, target_relpath="dashboards/prw/README.md"):
        self.repo_path = repo_path
        self.target_relpath = target_relpath

    def _get_remote_urls(self):
        """Return (fetch_urls, push_urls) for origin with insteadOf rewriting applied, every URL listed."""
        def _urls(*flags):
            try:
                r = subprocess.run(
                    ["git", "-C", self.repo_path, "remote", "get-url", *flags, "--all", "origin"],
                    capture_output=True,
                    text=True,
                )
            except Exception:
                return []
            if r.returncode != 0:
                return []
            return [line.strip() for line in r.stdout.splitlines() if line.strip()]

        return _urls(), _urls("--push")

    def _verify_destination_is_private(self, verify_private_fn=None):
        """
        Verify destination repo is private; fail closed on local, public, or unverified remotes.
        Requires exactly one effective fetch URL and one effective push URL (git pushes to every
        configured pushurl), both resolving to the same private GitHub repository slug.
        """
        if verify_private_fn is not None:
            return bool(verify_private_fn(self.repo_path))

        fetch_urls, push_urls = self._get_remote_urls()
        if len(fetch_urls) != 1 or len(push_urls) != 1:
            return False

        fetch_slug = extract_github_repo_slug(fetch_urls[0])
        push_slug = extract_github_repo_slug(push_urls[0])

        if not fetch_slug or not push_slug:
            return False

        if fetch_slug.lower() != push_slug.lower():
            return False

        try:
            gh_proc = subprocess.run(
                ["gh", "repo", "view", push_slug, "--json", "isPrivate,visibility"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if gh_proc.returncode == 0:
                data = json.loads(gh_proc.stdout)
                is_priv = data.get("isPrivate") is True
                vis = str(data.get("visibility", "")).upper()
                if is_priv and vis in ("PRIVATE", "INTERNAL"):
                    return True
        except Exception:
            pass

        return False

    def write_telemetry_bundle(
        self,
        summary_data,
        pilot_events=None,
        human_episodes=None,
        window_slug=None,
        prs=None,
        timeline=None,
        handoff_records=None,
        sources=None,
    ):
        """Generate relative file paths and contents for telemetry publishing under dashboards/prw/telemetry/."""
        if not window_slug:
            w2_start = summary_data.get("w2_bounds", ["", ""])[0] if isinstance(summary_data, dict) else ""
            if w2_start and len(w2_start) >= 10:
                window_slug = w2_start[:10].replace("-", "")
            else:
                window_slug = datetime.now(timezone.utc).strftime("%Y%m%d")

        if not _SLUG_RE.fullmatch(str(window_slug)):
            raise ValueError(f"invalid telemetry window slug: {window_slug!r}")
        window_dir = f"{TELEMETRY_RELDIR}/{window_slug}"

        files = {}
        if summary_data:
            files[f"{window_dir}/summary_snapshot.json"] = json.dumps(_project_summary(summary_data), indent=2)

        if pilot_events:
            lines = [json.dumps(_sanitize_retained_record(ev, RETAINED_EVENT_FIELDS)) for ev in pilot_events]
            files[f"{window_dir}/pilot_events.jsonl"] = "\n".join(lines) + "\n"

        if human_episodes:
            lines = [json.dumps(_sanitize_retained_record(ep, RETAINED_EPISODE_FIELDS)) for ep in human_episodes]
            files[f"{window_dir}/human_episodes.jsonl"] = "\n".join(lines) + "\n"

        for fname, records in (
            ("retained_prs.jsonl", prs),
            ("retained_timeline.jsonl", timeline),
            ("retained_handoffs.jsonl", handoff_records),
        ):
            if isinstance(records, dict):
                records = records.get("records") or records.get("handoffs") or []
            if records:
                allowed = RETAINED_COLLECTION_FILES[fname]
                lines = [json.dumps(_sanitize_retained_record(r, allowed, nested=True)) for r in records]
                files[f"{window_dir}/{fname}"] = "\n".join(lines) + "\n"
        if sources:
            files[f"{window_dir}/retained_sources.json"] = json.dumps(_sanitize_retained_sources(sources), indent=2)

        manifest_relpath = f"{TELEMETRY_RELDIR}/retention_manifest.json"
        files[manifest_relpath] = json.dumps(_project({
            "version": "1.0",
            "retention_days": 90,
            "last_updated_at": format_iso_utc(datetime.now(timezone.utc)),
        }, RETENTION_MANIFEST_SCHEMA), indent=2)

        return files

    def publish(
        self,
        markdown_text,
        status="FRESH",
        max_retries=3,
        verify_private_fn=None,
        publish_telemetry=False,
        summary_data=None,
        pilot_events=None,
        human_episodes=None,
        telemetry_files=None,
        prs=None,
        timeline=None,
        handoff_records=None,
        sources=None,
    ):
        if status == "FAILED":
            return {
                "action": "RETAINED_PRIOR",
                "committed": False,
                "reason": "Collection status is FAILED; retained prior dashboard content.",
            }

        markdown_text = _scrub_secrets(markdown_text)

        if not self._verify_destination_is_private(verify_private_fn=verify_private_fn):
            if verify_private_fn is not None:
                return {
                    "action": "PUBLIC_REPO_REJECTED",
                    "committed": False,
                    "reason": "Destination repository is public or unverified.",
                }
            return {
                "action": "BLOCKED",
                "committed": False,
                "reason": "Destination repository is not a verified private GitHub repository.",
            }

        telemetry_staged_files = {}
        if telemetry_files:
            try:
                for t_relpath, t_content in telemetry_files.items():
                    telemetry_staged_files[t_relpath] = sanitize_telemetry_file(t_relpath, t_content)
            except (ValueError, TypeError) as e:
                return {
                    "action": "BLOCKED",
                    "committed": False,
                    "reason": f"Unsanitizable telemetry file rejected: {e}",
                }
        if publish_telemetry and summary_data:
            tb = self.write_telemetry_bundle(
                summary_data,
                pilot_events=pilot_events,
                human_episodes=human_episodes,
                prs=prs,
                timeline=timeline,
                handoff_records=handoff_records,
                sources=sources,
            )
            telemetry_staged_files.update(tb)

        # Check existing content at origin/main:<target_relpath>
        current_content = None
        try:
            subprocess.run(["git", "-C", self.repo_path, "fetch", "origin", "main"], capture_output=True)
            head_proc = subprocess.run(
                ["git", "-C", self.repo_path, "rev-parse", "origin/main"],
                capture_output=True,
                text=True,
            )
            if head_proc.returncode == 0:
                parent_sha = head_proc.stdout.strip()
                show_proc = subprocess.run(
                    ["git", "-C", self.repo_path, "show", f"{parent_sha}:{self.target_relpath}"],
                    capture_output=True,
                    text=True,
                )
                if show_proc.returncode == 0:
                    current_content = show_proc.stdout
        except Exception:
            pass

        # Idempotency check: compare normalized content (only when no telemetry files are being updated)
        if current_content is not None and not telemetry_staged_files:
            norm_curr = normalize_markdown_for_comparison(current_content)
            norm_new = normalize_markdown_for_comparison(markdown_text)
            if norm_curr == norm_new:
                return {
                    "action": "NO_CHANGE",
                    "committed": False,
                    "reason": "Normalized dashboard content matches origin/main; avoided needless commit.",
                }

        # Scoped publication using an isolated GIT_INDEX_FILE
        # NEVER touches working tree files or unstaged changes.
        for attempt in range(max_retries):
            # Fetch origin main to ensure current head
            subprocess.run(["git", "-C", self.repo_path, "fetch", "origin", "main"], capture_output=True)

            with tempfile.NamedTemporaryFile(prefix="prw_index_") as idx_file:
                env = os.environ.copy()
                env["GIT_INDEX_FILE"] = idx_file.name
                env["GIT_AUTHOR_NAME"] = os.environ.get("GIT_AUTHOR_NAME") or "prw-metrics-collector"
                env["GIT_AUTHOR_EMAIL"] = os.environ.get("GIT_AUTHOR_EMAIL") or "prw-metrics@localhost"
                env["GIT_COMMITTER_NAME"] = os.environ.get("GIT_COMMITTER_NAME") or "prw-metrics-collector"
                env["GIT_COMMITTER_EMAIL"] = os.environ.get("GIT_COMMITTER_EMAIL") or "prw-metrics@localhost"

                try:
                    # 1. Pin exact parent commit SHA FIRST
                    head_proc = subprocess.run(
                        ["git", "-C", self.repo_path, "rev-parse", "origin/main"],
                        check=True,
                        capture_output=True,
                        text=True,
                        env=env,
                    )
                    parent_sha = head_proc.stdout.strip()

                    # 2. Read base tree from that exact pinned parent_sha into isolated index
                    subprocess.run(
                        ["git", "-C", self.repo_path, "read-tree", parent_sha],
                        check=True,
                        capture_output=True,
                        text=True,
                        env=env,
                    )

                    # 3. Hash new markdown blob
                    hash_proc = subprocess.run(
                        ["git", "-C", self.repo_path, "hash-object", "-w", "--stdin"],
                        input=markdown_text,
                        text=True,
                        check=True,
                        capture_output=True,
                        env=env,
                    )
                    blob_sha = hash_proc.stdout.strip()

                    # 4. Update index cacheinfo for target_relpath
                    subprocess.run(
                        [
                            "git",
                            "-C",
                            self.repo_path,
                            "update-index",
                            "--add",
                            "--cacheinfo",
                            "100644",
                            blob_sha,
                            self.target_relpath,
                        ],
                        check=True,
                        capture_output=True,
                        text=True,
                        env=env,
                    )

                    # 5. Stage any telemetry bundle files into the same atomic commit
                    for t_relpath, t_content in telemetry_staged_files.items():
                        t_hash_proc = subprocess.run(
                            ["git", "-C", self.repo_path, "hash-object", "-w", "--stdin"],
                            input=t_content,
                            text=True,
                            check=True,
                            capture_output=True,
                            env=env,
                        )
                        t_blob_sha = t_hash_proc.stdout.strip()
                        subprocess.run(
                            [
                                "git",
                                "-C",
                                self.repo_path,
                                "update-index",
                                "--add",
                                "--cacheinfo",
                                "100644",
                                t_blob_sha,
                                t_relpath,
                            ],
                            check=True,
                            capture_output=True,
                            text=True,
                            env=env,
                        )

                    # 6. Write tree
                    write_tree_proc = subprocess.run(
                        ["git", "-C", self.repo_path, "write-tree"],
                        check=True,
                        capture_output=True,
                        text=True,
                        env=env,
                    )
                    tree_sha = write_tree_proc.stdout.strip()

                    # 7. Commit tree with parent_sha
                    commit_msg = "docs(dashboard): refresh PRW metrics dashboard [skip ci]"
                    commit_proc = subprocess.run(
                        ["git", "-C", self.repo_path, "commit-tree", tree_sha, "-p", parent_sha, "-m", commit_msg],
                        check=True,
                        capture_output=True,
                        text=True,
                        env=env,
                    )
                    commit_sha = commit_proc.stdout.strip()

                    # 8. Push to remote main (fast-forward only, NEVER force)
                    push_proc = subprocess.run(
                        ["git", "-C", self.repo_path, "push", "origin", f"{commit_sha}:refs/heads/main"],
                        capture_output=True,
                        text=True,
                        env=env,
                    )

                    if push_proc.returncode == 0:
                        subprocess.run(
                            ["git", "-C", self.repo_path, "fetch", "origin", "main"],
                            capture_output=True,
                            text=True,
                            env=env,
                        )
                        return {
                            "action": "COMMITTED",
                            "committed": True,
                            "commit_sha": commit_sha,
                            "tree_sha": tree_sha,
                        }
                    else:
                        # Remote advanced concurrently; retry
                        continue

                except subprocess.CalledProcessError as e:
                    if attempt == max_retries - 1:
                        return {
                            "action": "ERROR",
                            "committed": False,
                            "error": str(e),
                        }

        return {
            "action": "RETRY_EXHAUSTED",
            "committed": False,
            "reason": f"Push failed after {max_retries} attempts due to concurrent remote advance.",
        }


def publish_dashboard(
    markdown_text,
    repo_path,
    target_relpath="dashboards/prw/README.md",
    status="FRESH",
    verify_private_fn=None,
    publish_telemetry=False,
    summary_data=None,
    pilot_events=None,
    human_episodes=None,
    telemetry_files=None,
    prs=None,
    timeline=None,
    handoff_records=None,
    sources=None,
):
    """Functional helper for Publisher."""
    publisher = Publisher(repo_path=repo_path, target_relpath=target_relpath)
    return publisher.publish(
        markdown_text=markdown_text,
        status=status,
        verify_private_fn=verify_private_fn,
        publish_telemetry=publish_telemetry,
        summary_data=summary_data,
        pilot_events=pilot_events,
        human_episodes=human_episodes,
        telemetry_files=telemetry_files,
        prs=prs,
        timeline=timeline,
        handoff_records=handoff_records,
        sources=sources,
    )


# -----------------------------------------------------------------------------
# Main CLI Entry Point
# -----------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="PRW Metrics Collector, Aggregator, and Dashboard Generator.")
    parser.add_argument("--repos", default=os.environ.get("PRW_METRICS_REPOS"), help="Comma-separated repository list (or via PRW_METRICS_REPOS env var)")
    parser.add_argument("--input-dir", default=os.environ.get("PRW_METRICS_INPUT_DIR"), help="Path to cached JSON scratch dataset directory")
    parser.add_argument("--state-dir", default=os.environ.get("PRW_METRICS_STATE_DIR"), help="Path to persistent state directory for saving/loading snapshots")
    parser.add_argument("--cutoff", help="Optional ISO-8601 UTC cutoff timestamp (default now)")
    parser.add_argument("--offline", action="store_true", default=os.environ.get("PRW_METRICS_OFFLINE", "").lower() in ("1", "true"), help="Offline mode: skip live GitHub API and use cached data")
    parser.add_argument("--output", help="Optional output path for rendered Markdown")
    parser.add_argument("--publish", action="store_true", default=os.environ.get("PRW_METRICS_PUBLISH", "").lower() in ("1", "true"), help="Publish dashboard to roadmap repo")
    parser.add_argument("--roadmap-repo", default=os.environ.get("PRW_METRICS_ROADMAP_REPO"), help="Path to local clone of roadmap repo")
    parser.add_argument("--telemetry-dir", default=os.environ.get("PRW_METRICS_TELEMETRY_DIR"), help="Path to telemetry directory containing pilot_events.jsonl, etc.")
    parser.add_argument("--receipts-dir", default=os.environ.get("PRW_METRICS_RECEIPTS_DIR"), help="Path to directory containing task receipts (run.stats.json, start_*.json, completion_*.json)")
    parser.add_argument("--target-relpath", default="dashboards/prw/README.md", help="Relative path inside roadmap repo")
    parser.add_argument("--stale-hours", type=float, default=float(os.environ.get("PRW_METRICS_STALE_HOURS", "4.5")), help="Threshold hours after which source cutoffs are marked STALE")

    args = parser.parse_args()

    if args.publish and not args.roadmap_repo:
        sys.stderr.write("ERROR: --publish requires --roadmap-repo (or PRW_METRICS_ROADMAP_REPO)\n")
        sys.exit(1)

    repos = []
    if args.repos:
        repos = [r.strip() for r in args.repos.split(",") if r.strip()]

    cutoff_dt = parse_iso_utc(args.cutoff) if args.cutoff else datetime.now(timezone.utc)

    collector = Collector(repos=repos, cutoff_dt=cutoff_dt)
    collected = collector.collect_all(
        input_dir=args.input_dir,
        state_dir=args.state_dir,
        offline=args.offline,
        telemetry_dir=args.telemetry_dir,
        roadmap_repo=args.roadmap_repo,
        receipts_dir=args.receipts_dir,
    )
    prs = collected["prs"]
    timeline = collected["timeline"]
    sources = collected["sources"]
    handoff_records = collected.get("handoff_records", [])
    pilot_events = collected.get("pilot_events") or None
    human_episodes = collected.get("human_episodes") or None

    aggregator = MetricsAggregator(cutoff_dt=cutoff_dt, repos=repos)
    summary_data = aggregator.aggregate_full_dataset(
        prs=prs,
        timeline_events=timeline,
        sources=sources,
        handoff_records=handoff_records,
        time_semantics_pilot=pilot_events,
        human_episodes=human_episodes,
        stale_threshold_hours=args.stale_hours,
    )

    if collected.get("status") in ("FAILED", "PARTIAL_FAILURE"):
        summary_data["status"] = collected["status"]

    renderer = DashboardRenderer()
    md_output = renderer.render(summary_data)

    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(md_output)
        print(f"Wrote dashboard to {args.output}")
    else:
        print(md_output)

    if args.publish and args.roadmap_repo:
        pub_res = publish_dashboard(
            markdown_text=md_output,
            repo_path=args.roadmap_repo,
            target_relpath=args.target_relpath,
            status=summary_data["status"],
            publish_telemetry=True,
            summary_data=summary_data,
            pilot_events=collected.get("pilot_events"),
            human_episodes=collected.get("human_episodes"),
            prs=prs,
            timeline=timeline,
            handoff_records=handoff_records,
            sources=sources,
        )
        print(f"Publication result: {pub_res}")
        if pub_res.get("action") in ("BLOCKED", "ERROR", "RETRY_EXHAUSTED", "PUBLIC_REPO_REJECTED", "AUTH_ERROR"):
            sys.stderr.write(f"ERROR: Publication failed: {pub_res.get('reason') or pub_res.get('error') or pub_res.get('action')}\n")
            sys.exit(1)

    if summary_data["status"] == "FAILED":
        sys.exit(2)


if __name__ == "__main__":
    main()
