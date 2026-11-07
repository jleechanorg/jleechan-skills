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
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from collections import defaultdict
from datetime import datetime, timedelta, timezone


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


def parse_operational_title(title):
    """
    Parse PR title into operational status/detail or legacy stage.
    Recognizes [status][detail] substantive title [cli][model].
    Legacy stages [sp]/[cd]/[ev]/[er]/[cr]/[fa] are recognized without
    confusing them with operational status.
    """
    if not title:
        return {"is_operational": False, "substantive_title": ""}

    # 1. Operational pattern: [status][detail] ...
    # status in ("working", "waiting", "blocked", "queued", "ready", "unknown")
    op_match = re.match(r"^\s*\[(working|waiting|blocked|queued|ready|unknown)\]\s*\[(.*?)\]\s*(.*)$", title, re.IGNORECASE)
    if op_match:
        status = op_match.group(1).lower()
        detail = op_match.group(2).strip()
        subst = op_match.group(3).strip()
        return {
            "is_operational": True,
            "status": status,
            "detail": detail,
            "substantive_title": subst,
        }

    # 2. Legacy stage patterns
    legacy_prefixes = {
        "sp": "stage:0-spec",
        "cd": "stage:1-coding",
        "ev": "stage:2-evidence",
        "er": "stage:3-evidence-review",
        "cr": "stage:4-code-review",
        "fa": "stage:5-final-approval",
    }
    leg_match = re.match(r"^\s*\[(sp|cd|ev|er|cr|fa)\]\s*(.*)$", title, re.IGNORECASE)
    if leg_match:
        prefix = leg_match.group(1).lower()
        rest = leg_match.group(2).strip()
        stage_match = re.search(r"\[(stage:\d+-[a-z-]+)\]\s*$", rest)
        stage_name = stage_match.group(1) if stage_match else legacy_prefixes.get(prefix)
        return {
            "is_operational": False,
            "legacy_stage": stage_name,
            "substantive_title": rest,
        }

    return {
        "is_operational": False,
        "substantive_title": title.strip(),
    }


# -----------------------------------------------------------------------------
# Task 1: Reusable Collection
# -----------------------------------------------------------------------------

class Collector:
    """Ingests PR and timeline events from live GitHub API or cached JSON scratch datasets."""

    split_search_window_on_cap = staticmethod(split_search_window_on_cap)

    def __init__(self, repos=None, cutoff_dt=None):
        self.repos = repos or []
        self.cutoff_dt = cutoff_dt or datetime.now(timezone.utc)
        self.source_manifest = {}

    def deduplicate_prs(self, prs):
        """Deduplicate PRs by (repo, number)."""
        seen = set()
        deduped = []
        for p in prs:
            repo = p.get("repo")
            num = p.get("number")
            key = (repo, num)
            if key not in seen:
                seen.add(key)
                deduped.append(p)
        return deduped

    def deduplicate_events(self, events):
        """Deduplicate timeline events by event ID where available or (pr_id, event, createdAt)."""
        seen = set()
        deduped = []
        for e in events:
            eid = e.get("id")
            if eid:
                key = ("id", eid)
            else:
                key = ("tuple", e.get("pr_id") or e.get("pr_number"), e.get("event"), e.get("createdAt"))
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

        return {
            "number": num,
            "repo": repo,
            "title": p.get("title") or "",
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
            "authority_ready_at": p.get("authority_ready_at"),
            "initial_task_accepted_at": p.get("initial_task_accepted_at"),
            "closure_sprint_accepted_at": p.get("closure_sprint_accepted_at"),
            "next_action": p.get("next_action"),
            "owner": p.get("owner"),
            "hold_status": p.get("hold_status"),
            "earliest_unmet_obligation": p.get("earliest_unmet_obligation"),
            "potential_handoff_waiting": p.get("potential_handoff_waiting"),
        }

    def collect_repo_prs_paginated(self, repo, fetch_page_fn=None, per_page=100):
        """
        Collect PRs for a repository across multiple pages.
        Maps both GitHub API snake_case and gh camelCase attributes.
        Preserves all open PRs even if >14d old, and includes reopened PRs.
        Stops when page returned has fewer than per_page items, or in live mode once
        updated_at falls before w1_start_dt (plus all open PRs).
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

            page_updated_dts = []
            for item in raw_items:
                norm = self.normalize_pr_record(item, default_repo=repo)
                all_prs.append(norm)
                if not fetch_page_fn:
                    upd_dt = parse_iso_utc(item.get("updated_at") or item.get("updatedAt") or norm.get("createdAt"))
                    if upd_dt:
                        page_updated_dts.append(upd_dt)

            if len(raw_items) < per_page:
                break
            if not fetch_page_fn and page_updated_dts and all(d < w1_start_dt for d in page_updated_dts):
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
                    elif "representative_prs" in raw_handoffs and isinstance(raw_handoffs["representative_prs"], dict):
                        for pr_id, pr_data in raw_handoffs["representative_prs"].items():
                            if isinstance(pr_data, dict):
                                m = pr_data.get("metrics", {})
                                if isinstance(m, dict):
                                    if isinstance(m.get("task_to_merge_sec"), (int, float)):
                                        handoffs.append({"name": "task_accepted -> merged", "duration_sec": m["task_to_merge_sec"]})
                                    if isinstance(m.get("closure_sprint_to_merge_sec"), (int, float)):
                                        handoffs.append({"name": "closure_sprint_accepted -> merged", "duration_sec": m["closure_sprint_to_merge_sec"]})
                source_status["handoffs"] = {"status": "COMPLETE", "path": handoff_path, "count": len(handoffs)}
            except Exception as e:
                source_status["handoffs"] = {"status": "FAILED", "error": str(e)}

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
            target_dir = os.path.join(roadmap_repo, "dashboards", "prw", "telemetry")

        pilot_events = []
        human_episodes = []
        calibration_audit = {}
        retention_manifest = {}

        if target_dir and os.path.isdir(target_dir):
            pe_path = os.path.join(target_dir, "pilot_events.jsonl")
            if os.path.exists(pe_path):
                with open(pe_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            pilot_events.append(json.loads(line))

            he_path = os.path.join(target_dir, "human_episodes.jsonl")
            if os.path.exists(he_path):
                with open(he_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            human_episodes.append(json.loads(line))

            ca_path = os.path.join(target_dir, "calibration_audit.json")
            if os.path.exists(ca_path):
                with open(ca_path, "r", encoding="utf-8") as f:
                    calibration_audit = json.load(f)

            rm_path = os.path.join(target_dir, "retention_manifest.json")
            if os.path.exists(rm_path):
                with open(rm_path, "r", encoding="utf-8") as f:
                    retention_manifest = json.load(f)

        return {
            "pilot_events": pilot_events,
            "human_episodes": human_episodes,
            "calibration_audit": calibration_audit,
            "retention_manifest": retention_manifest,
        }

    def collect_all(self, input_dir=None, state_dir=None, fetch_page_fn=None, offline=False):
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
        cached_timeline = []
        cached_handoffs = []
        prior_cutoffs = {}

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
                                if isinstance(v, dict) and v.get("cutoff"):
                                    prior_cutoffs[k] = v["cutoff"]
                    except Exception:
                        pass

        # 2. Determine repos to collect
        target_repos = list(self.repos)
        if not target_repos and cached_prs_by_repo:
            target_repos = list(cached_prs_by_repo.keys())

        if offline:
            for repo in target_repos:
                prs = cached_prs_by_repo.get(repo, [])
                if prs:
                    all_prs.extend(prs)
                    sources[repo] = {
                        "status": "COMPLETE",
                        "count": len(prs),
                        "cutoff": prior_cutoffs.get(repo, format_iso_utc(self.cutoff_dt)),
                    }
                else:
                    sources[repo] = {
                        "status": "EMPTY",
                        "count": 0,
                        "cutoff": format_iso_utc(self.cutoff_dt),
                    }
            all_timeline = cached_timeline
            handoff_records = cached_handoffs
        else:
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
                except Exception as e:
                    # Live collection failed for this repo
                    prior = cached_prs_by_repo.get(repo, [])
                    if prior:
                        all_prs.extend(prior)
                        sources[repo] = {
                            "status": "PARTIAL_FAILURE",
                            "error": str(e),
                            "count": len(prior),
                            "cutoff": prior_cutoffs.get(repo, format_iso_utc(self.cutoff_dt)),
                        }
                    else:
                        sources[repo] = {
                            "status": "FAILED",
                            "error": str(e),
                            "count": 0,
                            "cutoff": format_iso_utc(self.cutoff_dt),
                        }
            all_timeline = cached_timeline
            handoff_records = cached_handoffs

        all_prs = self.deduplicate_prs(all_prs)
        all_timeline = self.deduplicate_events(all_timeline)

        # 3. Overall status resolution
        failed_count = sum(1 for s in sources.values() if s.get("status") in ("FAILED", "PARTIAL_FAILURE"))
        complete_count = sum(1 for s in sources.values() if s.get("status") == "COMPLETE")

        if not all_prs and failed_count > 0:
            overall_status = "FAILED"
        elif any(s.get("status") == "PARTIAL_FAILURE" for s in sources.values()):
            overall_status = "PARTIAL_FAILURE"
        elif failed_count > 0 and complete_count > 0:
            overall_status = "PARTIAL_FAILURE"
        elif not all_prs:
            overall_status = "EMPTY"
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
        }


# -----------------------------------------------------------------------------
# Task 2: Aggregation and Honest Idle Boundaries
# -----------------------------------------------------------------------------

class MetricsAggregator:
    """Computes exact-window aggregations, stage dwell, and honest idle boundaries."""

    def __init__(self, cutoff_dt=None):
        self.cutoff_dt = cutoff_dt or datetime.now(timezone.utc)
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
        Requires explicit pr.get('authority_ready_at'); never substitutes review_completed_at.
        """
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

        pr_elapsed_sec = None
        if c_dt and m_dt and m_dt >= c_dt:
            pr_elapsed_sec = round((m_dt - c_dt).total_seconds(), 3)

        task_elapsed_sec = None
        if orig_t and m_dt and m_dt >= orig_t:
            task_elapsed_sec = round((m_dt - orig_t).total_seconds(), 3)

        closure_sprint_to_merge_sec = None
        if sprint_t and m_dt and m_dt >= sprint_t:
            closure_sprint_to_merge_sec = round((m_dt - sprint_t).total_seconds(), 3)

        # Match pilot_events for this PR
        matching_events = []
        if pilot_events:
            for ev in pilot_events:
                ev_pr = ev.get("pr_number") or ev.get("number")
                if ev_pr is not None and pr.get("number") is not None:
                    if ev_pr == pr.get("number"):
                        matching_events.append(ev)
                else:
                    matching_events.append(ev)

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
                dur = ev.get("duration_sec")
                s_dt = parse_iso_utc(s_iso)
                e_dt = parse_iso_utc(e_iso)

                if sk == "observed_active_execution":
                    if s_dt and e_dt and e_dt >= s_dt:
                        active_intervals.append((s_dt, e_dt))
                        active_durations.append((e_dt - s_dt).total_seconds())
                    elif dur is not None:
                        active_durations.append(float(dur))
                elif sk == "observed_operation_elapsed":
                    if s_dt and e_dt and e_dt >= s_dt:
                        operation_intervals.append((s_dt, e_dt))
                    elif dur is not None:
                        operation_intervals.append({"duration": float(dur)})
                elif sk == "explicit_waiting":
                    if s_dt and e_dt and e_dt >= s_dt:
                        waiting_intervals.append((s_dt, e_dt))

            if active_intervals:
                observed_active_wall_sec = compute_disjoint_interval_union(active_intervals)
                agent_effort_sec = round(sum(active_durations), 3)
            elif active_durations:
                observed_active_wall_sec = round(sum(active_durations), 3)
                agent_effort_sec = round(sum(active_durations), 3)
            else:
                observed_active_wall_sec = None
                agent_effort_sec = None

            if operation_intervals:
                if any(isinstance(x, dict) and "duration" in x for x in operation_intervals):
                    observed_operation_elapsed_sec = round(sum(x["duration"] for x in operation_intervals if "duration" in x), 3)
                else:
                    observed_operation_elapsed_sec = compute_disjoint_interval_union(operation_intervals)
            else:
                observed_operation_elapsed_sec = None

            if waiting_intervals:
                explicit_waiting_sec = compute_disjoint_interval_union(waiting_intervals)
            else:
                explicit_waiting_sec = None
        else:
            observed_active_wall_sec = None
            agent_effort_sec = None
            observed_operation_elapsed_sec = None
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
            "observed_active_wall_sec": observed_active_wall_sec,
            "agent_effort_sec": agent_effort_sec,
            "unattributed_or_waiting_residual_sec": unattributed_or_waiting_residual_sec,
            "residual_classification": residual_classification,
            "explicit_waiting_sec": explicit_waiting_sec,
            "avoidable_unattended_sec": None,
        }

    def compute_human_interventions(self, episodes, cohort_prs_count=None):
        """
        Aggregate human intervention episodes with bot exclusion, initial assignment separation,
        transcript deduplication, dual-annotator calibration, and post-merge tracking.
        """
        raw_human_messages = 0
        qualifying_episodes = 0
        label_breakdown = {"good": 0, "bad": 0, "mixed": 0, "unknown": 0}
        pr_attributed_count = 0
        unassigned_count = 0
        post_merge_count = 0

        seen_episode_ids = set()
        seen_message_ids = set()

        for ep in episodes or []:
            # Exclude bot messages
            if ep.get("is_bot") or ep.get("origin") == "bot":
                continue

            # Deduplication
            ep_id = ep.get("episode_id")
            msg_ids = ep.get("message_ids") or []
            if ep_id and ep_id in seen_episode_ids:
                continue
            if msg_ids and all(m in seen_message_ids for m in msg_ids):
                continue

            if ep_id:
                seen_episode_ids.add(ep_id)
            for m in msg_ids:
                seen_message_ids.add(m)

            raw_msgs = ep.get("raw_message_count", 1)
            raw_human_messages += raw_msgs

            # Initial task assignment is counted in raw human messages only, not qualifying episodes
            if ep.get("is_initial_assignment"):
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

        return {
            "raw_human_messages": raw_human_messages,
            "qualifying_episodes": qualifying_episodes,
            "label_breakdown": label_breakdown,
            "pr_attributed_count": pr_attributed_count,
            "unassigned_count": unassigned_count,
            "post_merge_count": post_merge_count,
            "channel_coverage": {"dot_history": "UNTESTED_ADAPTER_PENDING"},
            "retention_status": "OK",
        }

    def summarize_window_cohort(self, merged_prs):
        """Summarize creation-to-merge times for a cohort merged within window."""
        if not merged_prs:
            return {
                "n": 0, "all_median_hours": 0.0, "all_p75_hours": 0.0,
                "comparable_n": 0, "comp_median_hours": 0.0, "comp_p75_hours": 0.0,
                "backlog_n": 0, "backlog_median_hours": 0.0, "backlog_p75_hours": 0.0,
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
            "all_median_hours": round(calculate_median(durations_all), 2),
            "all_p75_hours": round(calculate_nearest_rank_p75(durations_all), 2),
            "comparable_n": len(durations_comp),
            "comp_median_hours": round(calculate_median(durations_comp), 2),
            "comp_p75_hours": round(calculate_nearest_rank_p75(durations_comp), 2),
            "backlog_n": len(durations_backlog),
            "backlog_median_hours": round(calculate_median(durations_backlog), 2),
            "backlog_p75_hours": round(calculate_nearest_rank_p75(durations_backlog), 2),
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
                cohort_pr_keys.add((None, num))
                pr_by_key[(repo, num)] = p
                pr_by_key[(None, num)] = p

        # 1. From PR stage_transitions if attached to PR objects
        for p in prs:
            pr_key = (p.get("repo"), p.get("number"))
            transitions = p.get("stage_transitions") or []
            for tr in transitions:
                stg = tr.get("stage") or tr.get("label")
                if stg in stage_durations:
                    s_iso = tr.get("start_at") or tr.get("entered_at") or tr.get("start")
                    e_iso = tr.get("end_at") or tr.get("exited_at") or tr.get("end")
                    s_dt = parse_iso_utc(s_iso)
                    e_dt = parse_iso_utc(e_iso)
                    if s_dt and e_dt:
                        if e_dt < s_dt:
                            stage_conflicts[stg] += 1
                        else:
                            hrs = (e_dt - s_dt).total_seconds() / 3600.0
                            stage_durations[stg].append(hrs)
                            stage_covered_prs[stg].add(pr_key)

        # 2. From timeline_events
        if timeline_events:
            events_by_pr = {}
            for ev in timeline_events:
                ev_pr_num = ev.get("pr_number") or ev.get("pr_id") or ev.get("number")
                ev_repo = ev.get("repo")
                pr_key = (ev_repo, ev_pr_num)
                # Filter to cohort PRs only
                if cohort_pr_keys and pr_key not in cohort_pr_keys and (None, ev_pr_num) not in cohort_pr_keys:
                    continue
                events_by_pr.setdefault(pr_key, []).append(ev)

            for pr_key, ev_list in events_by_pr.items():
                pr_obj = pr_by_key.get(pr_key) or pr_by_key.get((None, pr_key[1])) or {}
                for ev in ev_list:
                    stg = ev.get("stage") or ev.get("label")
                    if stg in stage_durations and (ev.get("start_at") or ev.get("entered_at")) and (ev.get("end_at") or ev.get("exited_at")):
                        s_dt = parse_iso_utc(ev.get("start_at") or ev.get("entered_at"))
                        e_dt = parse_iso_utc(ev.get("end_at") or ev.get("exited_at"))
                        if s_dt and e_dt:
                            if e_dt < s_dt:
                                stage_conflicts[stg] += 1
                            else:
                                hrs = (e_dt - s_dt).total_seconds() / 3600.0
                                stage_durations[stg].append(hrs)
                                stage_covered_prs[stg].add(pr_key)

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
                                if dt < s_dt:
                                    stage_conflicts[prev_lbl] += 1
                                else:
                                    hrs = (dt - s_dt).total_seconds() / 3600.0
                                    stage_durations[prev_lbl].append(hrs)
                                    stage_covered_prs[prev_lbl].add(pr_key)
                                del open_stages[prev_lbl]
                        open_stages[lbl] = dt
                    elif ev_type == "unlabeled":
                        if lbl in open_stages:
                            s_dt = open_stages.pop(lbl)
                            if dt < s_dt:
                                stage_conflicts[lbl] += 1
                            else:
                                hrs = (dt - s_dt).total_seconds() / 3600.0
                                stage_durations[lbl].append(hrs)
                                stage_covered_prs[lbl].add(pr_key)

                # Close remaining open stages at terminal merge or close
                term_dt = parse_iso_utc(pr_obj.get("mergedAt")) or parse_iso_utc(pr_obj.get("closedAt"))
                if term_dt:
                    for prev_lbl, s_dt in list(open_stages.items()):
                        if term_dt < s_dt:
                            stage_conflicts[prev_lbl] += 1
                        else:
                            hrs = (term_dt - s_dt).total_seconds() / 3600.0
                            stage_durations[prev_lbl].append(hrs)
                            stage_covered_prs[prev_lbl].add(pr_key)
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

    def compute_handoff_breakdown(self, prs, handoff_records=None, total_cohort_n=0):
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
        trans_durations = {t: [] for t in transitions}

        # 1. From PR fields
        for p in prs:
            # 1. evidence_ready -> review_requested
            if p.get("evidence_ready_at") and p.get("review_requested_at"):
                res = self.compute_interval_duration(p["evidence_ready_at"], p["review_requested_at"])
                if res["status"] == "OK":
                    trans_durations["evidence_ready -> review_requested"].append(res["duration_sec"])

            # 2. review_requested -> actual_review_started (requires actual_review_started_at)
            if p.get("review_requested_at") and p.get("actual_review_started_at"):
                res = self.compute_interval_duration(p["review_requested_at"], p["actual_review_started_at"])
                if res["status"] == "OK":
                    trans_durations["review_requested -> actual_review_started"].append(res["duration_sec"])

            # 3. review_return -> next_substantive_action
            r_ret = p.get("review_returned_at") or p.get("review_completed_at")
            next_act = p.get("next_action_started_at") or p.get("next_substantive_action_at")
            if r_ret and next_act:
                res = self.compute_interval_duration(r_ret, next_act)
                if res["status"] == "OK":
                    trans_durations["review_return -> next_substantive_action"].append(res["duration_sec"])

            # 4. authority_ready -> merged
            if self.derive_authority_ready(p) == "READY":
                auth_at = p.get("authority_ready_at")
                if auth_at and p.get("mergedAt"):
                    res = self.compute_interval_duration(auth_at, p["mergedAt"])
                    if res["status"] == "OK":
                        trans_durations["authority_ready -> merged"].append(res["duration_sec"])

            # 5. task_accepted -> merged (never closure_sprint_accepted_at)
            if p.get("initial_task_accepted_at") and p.get("mergedAt"):
                res = self.compute_interval_duration(p["initial_task_accepted_at"], p["mergedAt"])
                if res["status"] == "OK":
                    trans_durations["task_accepted -> merged"].append(res["duration_sec"])

            # 6. closure_sprint_accepted -> merged
            if p.get("closure_sprint_accepted_at") and p.get("mergedAt"):
                res = self.compute_interval_duration(p["closure_sprint_accepted_at"], p["mergedAt"])
                if res["status"] == "OK":
                    trans_durations["closure_sprint_accepted -> merged"].append(res["duration_sec"])

        # 2. From handoff_records
        if handoff_records:
            records_to_process = []
            if isinstance(handoff_records, list):
                records_to_process = handoff_records
            elif isinstance(handoff_records, dict):
                if "records" in handoff_records and isinstance(handoff_records["records"], list):
                    records_to_process = handoff_records["records"]
                elif "handoffs" in handoff_records and isinstance(handoff_records["handoffs"], list):
                    records_to_process = handoff_records["handoffs"]
                elif "representative_prs" in handoff_records and isinstance(handoff_records["representative_prs"], dict):
                    for pr_id, pr_data in handoff_records["representative_prs"].items():
                        if isinstance(pr_data, dict):
                            m = pr_data.get("metrics", {})
                            if isinstance(m, dict):
                                if isinstance(m.get("task_to_merge_sec"), (int, float)):
                                    records_to_process.append({"name": "task_accepted -> merged", "duration_sec": m["task_to_merge_sec"]})
                                if isinstance(m.get("closure_sprint_to_merge_sec"), (int, float)):
                                    records_to_process.append({"name": "closure_sprint_accepted -> merged", "duration_sec": m["closure_sprint_to_merge_sec"]})

            for rec in records_to_process:
                if not isinstance(rec, dict):
                    continue
                t_name = rec.get("name") or rec.get("transition")
                d_sec = rec.get("duration_sec")
                if t_name in trans_durations and d_sec is not None:
                    try:
                        trans_durations[t_name].append(float(d_sec))
                    except (ValueError, TypeError):
                        pass

        tot = total_cohort_n or len(prs)

        handoffs_data = []
        for t in transitions:
            durs = sorted(trans_durations[t])
            obs_n = len(durs)
            if obs_n > 0:
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
        if sources:
            for s in sources.values():
                if isinstance(s, dict) and s.get("cutoff"):
                    c_dt = parse_iso_utc(s["cutoff"])
                    if c_dt:
                        source_cutoffs.append(c_dt)

        if source_cutoffs:
            data_through_dt = min(source_cutoffs)
        else:
            data_through_dt = self.cutoff_dt

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
        stage_dwell_data = self.compute_stage_dwell(all_merged_w2 or prs, timeline_events=timeline_events)

        # Handoff breakdown
        handoffs = self.compute_handoff_breakdown(
            all_merged_w2 or prs,
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
                "stage:unknown",
            )
            sha = p.get("headRefOid") or "UNKNOWN"
            if idle.get("status") == "OK" and idle.get("duration_sec") is not None:
                open_prs_known.append({
                    "url": p.get("url"),
                    "sha": sha,
                    "stage": stg_lbl,
                    "next_action": p.get("next_action") or "Inspection",
                    "owner": p.get("owner") or "unassigned",
                    "hold_status": p.get("hold_status") or "none",
                    "eligible_unattended_duration_sec": idle["duration_sec"],
                })
            else:
                u_dt = parse_iso_utc(p.get("updatedAt")) or parse_iso_utc(p.get("createdAt"))
                quiet_hrs = round((cutoff - u_dt).total_seconds() / 3600.0, 1) if u_dt else "UNKNOWN"
                open_prs_unknown.append({
                    "url": p.get("url"),
                    "sha": sha,
                    "stage": stg_lbl,
                    "earliest_unmet_obligation": p.get("earliest_unmet_obligation") or "Review / Evidence",
                    "next_action": p.get("next_action") or "Inspection",
                    "owner": p.get("owner") or "unassigned",
                    "hold_status": p.get("hold_status") or "none",
                    "potential_handoff_waiting": p.get("potential_handoff_waiting") or "UNKNOWN",
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
        elif (now_dt - data_through_dt) > timedelta(hours=stale_threshold_hours):
            status = "STALE"
        elif source_cutoffs and any((now_dt - c) > timedelta(hours=stale_threshold_hours) for c in source_cutoffs):
            status = "STALE"

        # Pilot time semantics
        if time_semantics_pilot is None:
            time_semantics_pilot = []
            target_cohort = all_merged_w2 or prs
            for p in target_cohort:
                ts = self.compute_time_semantics(p)
                if ts.get("task_elapsed_sec") is not None or ts.get("observed_active_wall_sec") is not None:
                    time_semantics_pilot.append(ts)

        # Human interventions
        human_summary = None
        if human_episodes is not None:
            human_summary = self.compute_human_interventions(human_episodes, cohort_prs_count=len(all_merged_w2 or prs))

        return {
            "status": status,
            "generated_at": format_iso_utc(datetime.now(timezone.utc)),
            "data_through": format_iso_utc(data_through_dt),
            "w1_bounds": (format_iso_utc(w1_s), format_iso_utc(w2_s)),
            "w2_bounds": (format_iso_utc(w2_s), format_iso_utc(cutoff)),
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
                s_det = src_info.get("path") or src_info.get("cutoff") or src_info.get("error") or ""
                md.append(f"| `{src_name}` | **{s_stat}** | `{s_det}` |")
        else:
            md.append("*No per-source manifest available.*")
        md.append("")

        # Section 2: Repository Comparison
        md.append("## 2. Repository Comparison")
        md.append("")
        has_w1 = any("created_w1" in row for row in data.get("repo_comparison", []))
        if has_w1:
            md.append("| Repository | Created (W1 -> W2) | Merged (W1 -> W2) | Closed-Unmerged (W1 -> W2) | Closed Total | Open | Creation-to-Merge Median (W1 -> W2) | Nearest-Rank p75 (W1 -> W2) | <=7d Sensitivity Median (W1 -> W2) | Backlog Merges (>7d) (W1 -> W2) |")
        else:
            md.append("| Repository | Created (W2) | Merged (W1 -> W2) | Closed-Unmerged (W2) | Closed Total | Open | Creation-to-Merge Median (W2) | Nearest-Rank p75 | <=7d Sensitivity Median | Backlog Merges (>7d) |")
        md.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for row in data.get("repo_comparison", []):
            if "created_w1" in row:
                created_str = f"{row['created_w1']} -> {row['created']}"
                closed_str = f"{row['closed_unmerged_w1']} -> {row['closed_unmerged_w2']}"
                all_med_str = f"{row.get('w1_all_median_hours', 0.0)}h -> {row['all_median_hours']}h"
                all_p75_str = f"{row.get('w1_all_p75_hours', 0.0)}h -> {row['all_p75_hours']}h"
                comp_med_str = f"{row.get('w1_comp_median_hours', 0.0)}h -> {row['comp_median_hours']}h"
                backlog_str = f"{row.get('w1_backlog_n', 0)} ({row.get('w1_backlog_median_hours', 0.0)}h) -> {row['backlog_n']} ({row['backlog_median_hours']}h)"
            else:
                created_str = str(row['created'])
                closed_str = str(row['closed_unmerged_w2'])
                all_med_str = f"{row['all_median_hours']}h"
                all_p75_str = f"{row['all_p75_hours']}h"
                comp_med_str = f"{row['comp_median_hours']}h"
                backlog_str = f"{row['backlog_n']} ({row['backlog_median_hours']}h)"

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
            md.append("| PR | Head SHA | Stage | Actionable Next Step | Owner | Hold Status | Eligible Unattended Duration |")
            md.append("|---|---|---|---|---|---|---|")
            for pr in data.get("open_prs_known_idle"):
                md.append(f"| [{pr['url']}]({pr['url']}) | `{pr['sha'][:7]}` | `{pr['stage']}` | {pr['next_action']} | `{pr['owner']}` | {pr['hold_status']} | **{format_duration(pr['eligible_unattended_duration_sec'])}** |")
        else:
            md.append("*No open PRs currently exhibit proven eligible unattended duration.*")
        md.append("")
        md.append("### 5B. Open PRs with Unknown Eligibility (Telemetry Coverage 0%)")
        md.append("")
        md.append("> ℹ️ **Notice**: These PRs lack fine-grained active-worker/hold-state telemetry. They are reported transparently for operator attention and are NOT ranked as idle.")
        md.append("")
        if data.get("open_prs_unknown_idle"):
            md.append("| PR | Head SHA | Stage | Earliest Unmet Obligation | Next Action | Owner | Hold Status | Potential Handoff Waiting | GitHub Quiet Time (Proxy Only) |")
            md.append("|---|---|---|---|---|---|---|---:|---:|")
            for pr in data.get("open_prs_unknown_idle"):
                md.append(
                    f"| [{pr['url']}]({pr['url']}) | `{pr['sha'][:7]}` | `{pr['stage']}` | "
                    f"{pr.get('earliest_unmet_obligation', 'UNKNOWN')} | {pr.get('next_action', 'UNKNOWN')} | "
                    f"`{pr.get('owner', 'unassigned')}` | {pr.get('hold_status', 'none')} | "
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
            qual_eps = hi.get("qualifying_episodes", 0)
            lbls = hi.get("label_breakdown", {})
            pr_attr = hi.get("pr_attributed_count", 0)
            unass = hi.get("unassigned_count", 0)
            post_m = hi.get("post_merge_count", 0)
            cov = hi.get("channel_coverage", {})
            ret_stat = hi.get("retention_status", "OK")

            md.append(f"- **Raw Human Messages**: {raw_msgs}")
            md.append(f"- **Qualifying Episodes**: {qual_eps}")
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

        return "\n".join(md)


def render_dashboard(data):
    """Convenience functional wrapper for DashboardRenderer."""
    renderer = DashboardRenderer()
    return renderer.render(data)


# -----------------------------------------------------------------------------
# Task 5: Safe Scoped Git Publisher
# -----------------------------------------------------------------------------

class Publisher:
    """Publishes dashboard Markdown to a designated Git repository using an isolated index file."""

    def __init__(self, repo_path, target_relpath="dashboards/prw/README.md"):
        self.repo_path = repo_path
        self.target_relpath = target_relpath

    def _verify_destination_is_private(self, verify_private_fn=None):
        """Verify destination repo is private; reject if public or verification fails."""
        if verify_private_fn is not None:
            return verify_private_fn(self.repo_path)

        if os.environ.get("PRW_METRICS_ALLOW_LOCAL_REMOTE") == "1":
            return True

        remote_url = ""
        try:
            res = subprocess.run(
                ["git", "-C", self.repo_path, "config", "--get", "remote.origin.url"],
                capture_output=True,
                text=True,
            )
            remote_url = res.stdout.strip()
        except Exception:
            pass

        if remote_url and (remote_url.startswith("/") or remote_url.startswith("file://") or os.path.isdir(remote_url)):
            return True

        if remote_url:
            try:
                match = re.search(r"github\.com[:/]([^/]+/[^/.]+)", remote_url)
                if match:
                    nwo = match.group(1).rstrip(".git")
                    gh_proc = subprocess.run(
                        ["gh", "repo", "view", nwo, "--json", "isPrivate", "-q", ".isPrivate"],
                        capture_output=True,
                        text=True,
                        timeout=15,
                    )
                    if gh_proc.returncode == 0:
                        return gh_proc.stdout.strip().lower() == "true"
            except Exception:
                pass

        return False

    def publish(self, markdown_text, status="FRESH", max_retries=3, verify_private_fn=None):
        if status == "FAILED":
            return {
                "action": "RETAINED_PRIOR",
                "committed": False,
                "reason": "Collection status is FAILED; retained prior dashboard content.",
            }

        if not self._verify_destination_is_private(verify_private_fn=verify_private_fn):
            return {
                "action": "PUBLIC_REPO_REJECTED",
                "committed": False,
                "reason": "Destination repository is public or not verified private.",
            }

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

        # Idempotency check: compare normalized content
        if current_content is not None:
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

                    # 5. Write tree
                    write_tree_proc = subprocess.run(
                        ["git", "-C", self.repo_path, "write-tree"],
                        check=True,
                        capture_output=True,
                        text=True,
                        env=env,
                    )
                    tree_sha = write_tree_proc.stdout.strip()

                    # 6. Commit tree with parent_sha
                    commit_msg = "docs(dashboard): refresh PRW metrics dashboard [skip ci]"
                    commit_proc = subprocess.run(
                        ["git", "-C", self.repo_path, "commit-tree", tree_sha, "-p", parent_sha, "-m", commit_msg],
                        check=True,
                        capture_output=True,
                        text=True,
                        env=env,
                    )
                    commit_sha = commit_proc.stdout.strip()

                    # 7. Push to remote main (fast-forward only, NEVER force)
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


def publish_dashboard(markdown_text, repo_path, target_relpath="dashboards/prw/README.md", status="FRESH", verify_private_fn=None):
    """Functional helper for Publisher."""
    publisher = Publisher(repo_path=repo_path, target_relpath=target_relpath)
    return publisher.publish(markdown_text=markdown_text, status=status, verify_private_fn=verify_private_fn)


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
    parser.add_argument("--target-relpath", default="dashboards/prw/README.md", help="Relative path inside roadmap repo")

    args = parser.parse_args()

    repos = []
    if args.repos:
        repos = [r.strip() for r in args.repos.split(",") if r.strip()]

    cutoff_dt = parse_iso_utc(args.cutoff) if args.cutoff else datetime.now(timezone.utc)

    collector = Collector(repos=repos, cutoff_dt=cutoff_dt)
    collected = collector.collect_all(
        input_dir=args.input_dir,
        state_dir=args.state_dir,
        offline=args.offline,
    )
    prs = collected["prs"]
    timeline = collected["timeline"]
    sources = collected["sources"]
    handoff_records = collected.get("handoff_records", [])

    aggregator = MetricsAggregator(cutoff_dt=cutoff_dt)
    summary_data = aggregator.aggregate_full_dataset(
        prs=prs,
        timeline_events=timeline,
        sources=sources,
        handoff_records=handoff_records,
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
        )
        print(f"Publication result: {pub_res}")
        if pub_res.get("action") in ("ERROR", "RETRY_EXHAUSTED", "AUTH_ERROR", "PUBLIC_REPO_REJECTED"):
            sys.exit(1)

    if summary_data["status"] == "FAILED":
        sys.exit(1)


if __name__ == "__main__":
    main()
