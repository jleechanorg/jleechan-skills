#!/usr/bin/env python3
"""Compact JSON snapshot for the PRW web dashboard.

Projects structured objects the metrics job already computes (the renderer
summary, the DuckDB query result and the cached PR list) into one small,
versioned payload for a static frontend. It never parses rendered Markdown,
never reads history, and never turns a missing measurement into zero: an
unobserved value is ``null`` and each PR carries the status that explains it.

No prompt text, PR bodies, reasoning or credentials are copied.
"""

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

try:
    from scripts.prw_metrics import MetricsAggregator, _project_summary, _scrub_secrets
except ModuleNotFoundError:
    from prw_metrics import MetricsAggregator, _project_summary, _scrub_secrets

SCHEMA_VERSION = 1

_TS = re.compile(
    r"^(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})(?:\.\d+)?(Z|[+-]\d{2}(?::?\d{2})?)?$"
)


def to_utc_iso(value):
    """Normalize an ISO or DuckDB-rendered timestamp to ``YYYY-MM-DDTHH:MM:SSZ``."""
    if not isinstance(value, str):
        return None
    match = _TS.match(value.strip())
    if not match:
        return None
    day, clock, zone = match.groups()
    if zone in (None, "Z"):
        zone = "+00:00"
    else:
        digits = zone[1:].replace(":", "")
        zone = f"{zone[0]}{digits[:2]}:{digits[2:] or '00'}"
    try:
        parsed = datetime.fromisoformat(f"{day}T{clock}{zone}")
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _number(value):
    """Return a finite number, or None. Booleans and sentinels are not numbers."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return value if value == value and value not in (float("inf"), float("-inf")) else None
    if isinstance(value, str):
        try:
            parsed = float(value)
        except ValueError:
            return None
        return _number(parsed)
    return None


def _count(value):
    number = _number(value)
    return int(number) if number is not None else None


def _pr_key(repository, number):
    return f"{repository}#{number}"


def _index_prs(prs):
    index = {}
    for record in prs or []:
        if not isinstance(record, dict):
            continue
        repository = record.get("repo") or record.get("repository")
        number = _count(record.get("number"))
        if isinstance(repository, str) and number is not None:
            index[_pr_key(repository, number)] = record
    return index


def _size(record):
    """Line/file counts, or None when the collector did not observe them.

    The PR list reports 0/0/0 when sizes were never fetched. A merged PR with no
    changed files is not a real observation, so an all-zero triple is unknown.
    """
    if not isinstance(record, dict):
        return None
    additions = _count(record.get("additions"))
    deletions = _count(record.get("deletions"))
    files = _count(record.get("changedFiles"))
    if additions is None or deletions is None or files is None:
        return None
    if additions == 0 and deletions == 0 and files == 0:
        return None
    return {"additions": additions, "deletions": deletions, "files": files}


# (key, label, start fields, end fields): the first present field is used, as in the collector.
HANDOFF_TRANSITIONS = (
    ("evidence_to_review_request", "Evidence ready to review requested", ("evidence_ready_at",), ("review_requested_at",)),
    ("review_request_to_start", "Review requested to review started", ("review_requested_at",), ("actual_review_started_at",)),
    ("review_return_to_next_action", "Review returned to next action started",
     ("review_returned_at", "review_completed_at"), ("next_action_started_at", "next_substantive_action_at")),
    ("authority_to_merge", "Merge authority ready to merged", ("authority_ready_at",), ("mergedAt",)),
)


def _first(record, fields):
    return next((record.get(field) for field in fields if record.get(field)), None)


def _handoffs(record):
    """Seconds between observed workflow transitions. A missing endpoint leaves the interval out."""
    if not isinstance(record, dict):
        return None
    intervals = {}
    for key, _label, start_fields, end_fields in HANDOFF_TRANSITIONS:
        # Merge-authority time counts only when the collector accepts the authority facts.
        if key == "authority_to_merge" and MetricsAggregator().derive_authority_ready(record) != "READY":
            continue
        start, end = to_utc_iso(_first(record, start_fields)), to_utc_iso(_first(record, end_fields))
        if not start or not end:
            continue
        seconds = (
            datetime.strptime(end, "%Y-%m-%dT%H:%M:%SZ") - datetime.strptime(start, "%Y-%m-%dT%H:%M:%SZ")
        ).total_seconds()
        if seconds >= 0:  # an end before its start is a recording conflict, not a duration
            intervals[key] = seconds
    return intervals or None


# Strongest first, matching the usage basis precedence in _pr_row (direct > session binding > branch).
_SCENARIO_METHODS = ("direct", "convention", "branch_associated")


def _scenarios_by_pr(rows):
    """Public-list scenario rows grouped per PR. These are not billing.

    The query emits one row per attribution method, and one request can be matched to the same PR
    both directly and by branch. Only the strongest method present is used, so a request counts once.
    """
    by_pr = {}
    for row in rows or []:
        if isinstance(row, dict) and isinstance(row.get("pr"), str):
            by_pr.setdefault(row["pr"], []).append(row)
    grouped = {}
    for pr, pr_rows in by_pr.items():
        methods = {row.get("attribution_method") for row in pr_rows}
        chosen = next((m for m in _SCENARIO_METHODS if m in methods), None)
        entry = {
            "known_subtotal_usd": None,
            "full_scenario_usd": None,
            "event_n": 0,
            "fully_priced_event_n": 0,
            "unknown_event_n": 0,
            "statuses": [],
            "models": [],
            "attribution_methods": [],
            "catalog_version": pr_rows[0].get("catalog_version"),
        }
        complete = True
        for row in pr_rows:
            if row.get("attribution_method") != chosen:
                continue
            known = _number(row.get("known_component_subtotal_usd"))
            if known is not None:
                entry["known_subtotal_usd"] = round((entry["known_subtotal_usd"] or 0) + known, 6)
            full = _number(row.get("scenario_cost_usd"))
            if full is None or row.get("scenario_status") != "COMPLETE":
                complete = False
            else:
                entry["full_scenario_usd"] = round((entry["full_scenario_usd"] or 0) + full, 6)
            for key in ("event_n", "fully_priced_event_n", "unknown_event_n"):
                entry[key] += _count(row.get(key)) or 0
            for key, source in (
                ("statuses", "scenario_status"),
                ("models", "model_id"),
                ("attribution_methods", "attribution_method"),
            ):
                value = row.get(source)
                if isinstance(value, str) and value not in entry[key]:
                    entry[key].append(value)
        # A full scenario total is only meaningful when every counted row was fully priced.
        if not complete:
            entry["full_scenario_usd"] = None
        for key in ("statuses", "models", "attribution_methods"):
            entry[key].sort()
        grouped[pr] = entry
    return grouped


def _pr_row(metric, record, scenario):
    repository = metric.get("repository")
    number = _count(metric.get("pr_number"))
    record = record or {}
    usage = None
    if metric.get("branch_usage_status") == "OBSERVED_SOURCE_BRANCH_ATTRIBUTION":
        usage = {
            "basis": "source_branch",
            "confidence": metric.get("branch_association_confidence"),
            "uncached_input": _count(metric.get("branch_uncached_input_tokens")),
            "cache_read": _count(metric.get("branch_cache_read_input_tokens")),
            "output": _count(metric.get("branch_output_tokens")),
            "total": _count(metric.get("branch_total_tokens")),
            "requests": _count(metric.get("branch_usage_observation_count")),
        }
    convention_total = _count(metric.get("convention_total_tokens"))
    if convention_total is not None:
        # Usage bound by a recorded session-to-PR binding (hook ledger): stronger than a branch match.
        usage = {
            "basis": "session_binding",
            "confidence": "session_bound",
            "uncached_input": None,
            "cache_read": None,
            "output": None,
            "total": convention_total,
            "requests": _count(metric.get("convention_usage_observation_count")),
        }
    direct_total = _count(metric.get("direct_total_tokens"))
    if direct_total is not None:
        usage = {
            "basis": "direct",
            "confidence": metric.get("direct_association_confidence"),
            "uncached_input": _count(metric.get("direct_uncached_input_tokens")),
            "cache_read": _count(metric.get("direct_cache_read_input_tokens")),
            "output": _count(metric.get("direct_output_tokens")),
            "total": direct_total,
            "requests": _count(metric.get("direct_usage_observation_count")),
        }
    human = None
    if metric.get("human_coverage_status") not in (None, "UNKNOWN"):
        human = {
            "coverage_status": metric.get("human_coverage_status"),
            "confidence": metric.get("human_association_confidence"),
            "verified_messages": _count(metric.get("raw_verified_human_message_count")),
            "initial": _count(metric.get("verified_initial_human_message_count")),
            "followup": _count(metric.get("verified_followup_human_message_count")),
            "branch_candidates": _count(metric.get("branch_associated_candidates")),
            "episodes": {
                label: _count(metric.get(f"{label}_episode_count"))
                for label in ("good", "bad", "mixed", "unknown")
            },
        }
    return {
        "id": _pr_key(repository, number),
        "repo": repository,
        "number": number,
        "title": record.get("title") if isinstance(record.get("title"), str) else None,
        "url": record.get("url")
        if isinstance(record.get("url"), str)
        else f"https://github.com/{repository}/pull/{number}",
        "state": metric.get("pr_state"),
        "draft": record.get("isDraft") if isinstance(record.get("isDraft"), bool) else None,
        "stage": record.get("legacy_stage") or None,
        "branch": metric.get("head_branch"),
        "created": to_utc_iso(metric.get("created_at_utc")),
        "merged": to_utc_iso(metric.get("merged_at_utc")),
        "closed": to_utc_iso(metric.get("closed_at_utc")),
        "elapsed_s": _number(metric.get("pr_elapsed_seconds")),
        "elapsed_basis": metric.get("pr_elapsed_basis"),
        "size": _size(record),
        "usage": usage,
        "usage_status": metric.get("usage_status"),
        "branch_usage_status": metric.get("branch_usage_status"),
        "cost": scenario,
        "cost_status": metric.get("cost_status"),
        "human": human,
        "human_coverage_status": metric.get("human_coverage_status"),
        "handoffs": _handoffs(record),
        "active_s": _number(metric.get("observed_active_wall_seconds")),
        "agent_effort_s": _number(metric.get("agent_effort_seconds")),
        "eligible_idle_s": _number(metric.get("eligible_idle_seconds")),
    }


def _cohort_row(row):
    return {
        "repo": row.get("repository"),
        "cohort": row.get("cohort_definition"),
        "family": row.get("metric_family"),
        "measure": row.get("measure"),
        "unit": row.get("unit"),
        "cohort_pr_n": _count(row.get("cohort_pr_n")),
        "observation_n": _count(row.get("observation_n")),
        "distinct_pr_n": _count(row.get("distinct_pr_n")),
        "mean": _number(row.get("average")),
        "p50": _number(row.get("p50")),
        "p90": _number(row.get("p90")),
        "p99": _number(row.get("p99")),
        "coverage": _number(row.get("valid_coverage")),
        "coverage_status": row.get("coverage_status"),
        "method": row.get("quantile_method"),
    }


def _gaps(rows, coverage):
    """Plain statements of what this snapshot does not measure."""
    total = len(rows)

    def have(predicate):
        return sum(1 for row in rows if predicate(row))

    gaps = []

    def add(key, label, observed, detail):
        gaps.append({"key": key, "label": label, "observed_n": observed, "total_n": total, "detail": detail})

    add("usage", "Token usage per PR", have(lambda r: r["usage"]),
        "Usage is tied to a PR only where a session's source branch matches exactly one PR "
        "(low confidence) or a request names the PR directly. Unbound usage is not spread across PRs.")
    add("cost", "Cost per PR", have(lambda r: r["cost"] and r["cost"]["full_scenario_usd"] is not None),
        "Public-list-price scenario only, never invoiced spend. Rows with unpriced token buckets "
        "show a known-component subtotal, which is a lower bound.")
    add("human", "Human steering per PR", have(lambda r: r["human"] and r["human"]["verified_messages"]),
        "Counts verified-human messages bound to one PR. Branch-only and ambiguous candidates are not counted.")
    add("active", "Observed active time", have(lambda r: r["active_s"] is not None),
        "Needs timed operation telemetry; elapsed minus active is a residual, not wasted time.")
    add("idle", "Eligible idle time", have(lambda r: r["eligible_idle_s"] is not None),
        "Needs an observed, authorized next action with no worker, hold or dependency.")
    add("handoffs", "Handoff timestamps", have(lambda r: r["handoffs"]),
        "Needs both ends of a workflow transition recorded. Handoff delay is elapsed time between steps; "
        "it is not by itself avoidable waiting.")
    add("episodes", "Steering episodes rated good, bad or mixed",
        have(lambda r: r["human"] and any((r["human"]["episodes"].get(k) or 0) for k in ("good", "bad", "mixed"))),
        "Episodes with a reviewed quality label. Unrated episodes stay unknown.")
    add("size", "PR size (lines and files)", have(lambda r: r["size"]),
        "Additions, deletions and changed files were not collected for these PRs.")
    if isinstance(coverage, dict):
        events = _count(coverage.get("canonical_event_n"))
        direct = _count(coverage.get("validated_direct_attribution_event_n"))
        if events:
            gaps.append({
                "key": "direct_attribution", "label": "Usage events naming a PR directly",
                "observed_n": direct or 0, "total_n": events,
                "detail": "Share of deduplicated usage events that carry a validated direct PR attribution.",
            })
    return gaps


def _finite(value):
    """Copy of a JSON-like value with NaN and infinities replaced by None (unobserved, not a number)."""
    if isinstance(value, float):
        return value if value == value and value not in (float("inf"), float("-inf")) else None
    if isinstance(value, dict):
        return {key: _finite(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_finite(item) for item in value]
    return value


def build_snapshot(summary_data, query_summary, prs, *, generated_at=None, code_version=None):
    """Build the dashboard payload. All three inputs are optional; absent means unknown."""
    # The retained-summary schema projection: only listed fields, at every depth.
    summary_data = _project_summary(summary_data)
    query_summary = query_summary if isinstance(query_summary, dict) else {}
    index = _index_prs(prs)
    scenarios = _scenarios_by_pr(query_summary.get("catalog_scenario_pr_metrics"))
    rows = []
    for metric in query_summary.get("pr_metrics") or []:
        if not isinstance(metric, dict) or _count(metric.get("pr_number")) is None:
            continue
        key = _pr_key(metric.get("repository"), _count(metric.get("pr_number")))
        rows.append(_pr_row(metric, index.get(key), scenarios.get(key)))
    rows.sort(key=lambda row: (row["repo"] or "", row["number"]))
    cohorts = [_cohort_row(row) for row in query_summary.get("metric_cohorts") or [] if isinstance(row, dict)]
    usage = summary_data.get("usage_summary") if isinstance(summary_data.get("usage_summary"), dict) else {}
    human = summary_data.get("human_summary") if isinstance(summary_data.get("human_summary"), dict) else {}
    methods = sorted({row["method"] for row in cohorts if row["method"]})
    return _scrub_secrets(_finite({
        "schema_version": SCHEMA_VERSION,
        "generated_at": to_utc_iso(generated_at or summary_data.get("generated_at")),
        # Freshness is the collector's verified value; the query cutoff only bounds the reporting window.
        "data_through": to_utc_iso(summary_data.get("data_through")),
        "window_start": to_utc_iso(query_summary.get("window_start_utc")),
        "window_end": to_utc_iso(query_summary.get("snapshot_at_utc")),
        "status": summary_data.get("status"),
        "code_version": code_version,
        "windows": {"w1": summary_data.get("w1_bounds"), "w2": summary_data.get("w2_bounds")},
        "quantile_method": methods[0] if len(methods) == 1 else methods or None,
        "sources": summary_data.get("sources"),
        "repositories": sorted({row["repo"] for row in rows if row["repo"]}),
        "query_coverage": query_summary.get("query_coverage"),
        "repo_comparison": summary_data.get("repo_comparison"),
        "stage_dwell": summary_data.get("stage_dwell"),
        "handoffs": summary_data.get("handoffs"),
        "cohorts": cohorts,
        "usage_totals": {
            key: usage.get(key)
            for key in (
                "event_count", "priced_event_count", "partially_priced_event_count",
                "unknown_event_count", "known_cost_usd", "tokens_by_bucket",
                "reasoning_tokens", "unallocated", "label", "scope",
            )
            if key in usage
        },
        "human_coverage": human.get("coverage"),
        "human_interventions": summary_data.get("human_interventions"),
        "handoff_transitions": [{"key": key, "label": label} for key, label, _s, _e in HANDOFF_TRANSITIONS],
        "gaps": _gaps(rows, query_summary.get("query_coverage")),
        "prs": rows,
    }))


def write_snapshot(path, snapshot):
    """Write atomically so a reader never sees a half-written file."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(
        json.dumps(snapshot, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", help="Renderer summary JSON")
    parser.add_argument("--query", required=True, help="prw_metrics_queries result JSON")
    parser.add_argument("--prs", help="Cached PR list JSON")
    parser.add_argument("--code-version", help="Source revision that produced the inputs")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    def load(path):
        return json.loads(Path(path).read_text(encoding="utf-8")) if path else None

    snapshot = build_snapshot(
        load(args.summary), load(args.query), load(args.prs), code_version=args.code_version
    )
    write_snapshot(args.output, snapshot)
    print(f"Wrote {len(snapshot['prs'])} PR rows to {args.output}")


if __name__ == "__main__":
    main()
