#!/usr/bin/env python3
"""
Unit and integration tests for scripts/prw_metrics.py.
Following strict RED -> GREEN TDD.

Portability Invariant:
- Uses only synthetic repository names (e.g. example-org/repo-alpha, example-org/repo-beta).
- Contains NO hardcoded private organization names, private repo names, personal user paths, or tokens.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

# Direct execution sets sys.path[0] to tests/, so make the repository package importable.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# We will import from scripts.prw_metrics
# Before implementation, this will fail or functions will be missing (RED).
try:
    from scripts.prw_metrics import (
        Collector,
        DashboardRenderer,
        MetricsAggregator,
        Publisher,
        calculate_median,
        calculate_nearest_rank_percentile,
        calculate_nearest_rank_p75,
        compute_disjoint_interval_union,
        filter_events_half_open,
        format_iso_utc,
        normalize_markdown_for_comparison,
        parse_iso_utc,
        parse_operational_title,
        publish_dashboard,
        redact_sensitive_excerpt,
        render_dashboard,
        split_search_window_on_cap,
        extract_github_repo_slug,
        sanitize_telemetry_file,
        _project_summary,
        RETAINED_PR_FIELDS,
        RETAINED_TIMELINE_FIELDS,
        RETAINED_HANDOFF_FIELDS,
    )
except ImportError:
    Collector = None
    DashboardRenderer = None
    MetricsAggregator = None
    Publisher = None
    sanitize_telemetry_file = None
    _project_summary = None
    parse_operational_title = None
    split_search_window_on_cap = None


class TestPortabilityAndHygiene(unittest.TestCase):
    """Verify that source code and test files adhere to public repository portability rules."""

    def test_no_forbidden_strings_in_scripts_or_tests(self):
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        forbidden = [
            "world" + "architect",
            "worldai_" + "frontend",
            "jleechan" + "org",
            "/Users/" + "jleechan",
            "/home/" + "jleechan",
            "ghp" + "_",
            "github_pat" + "_",
        ]

        targets = [
            os.path.join(root_dir, "scripts", "prw_metrics.py"),
            os.path.join(root_dir, "scripts", "run_prw_metrics.sh"),
            os.path.join(root_dir, "scripts", "install-prw-metrics-launchd.sh"),
            os.path.join(root_dir, "docs", "specs", "prw-metrics-dashboard-spec.md"),
            os.path.join(root_dir, "docs", "user-stories", "prw-metrics-dashboard.md"),
        ]

        for target in targets:
            if os.path.exists(target):
                with open(target, "r", encoding="utf-8") as f:
                    content = f.read().lower()
                    for forb in forbidden:
                        self.assertNotIn(
                            forb.lower(),
                            content,
                            f"Found forbidden string in {target}",
                        )


class TestStatisticalFunctions(unittest.TestCase):
    """Test nearest-rank p75 and median implementations."""

    def test_nearest_rank_p75_definition(self):
        """p75 must use math.ceil(0.75 * n) - 1 on 0-indexed sorted array."""
        self.assertEqual(calculate_nearest_rank_p75([]), 0.0)
        self.assertEqual(calculate_nearest_rank_p75([10.0]), 10.0)

        # n = 2: ceil(0.75*2) = 2 -> index 1
        self.assertEqual(calculate_nearest_rank_p75([5.0, 15.0]), 15.0)

        # n = 4: ceil(0.75*4) = 3 -> index 2
        self.assertEqual(calculate_nearest_rank_p75([1.0, 2.0, 3.0, 4.0]), 3.0)

        # n = 10: ceil(0.75*10) = 8 -> index 7 (8th element)
        data = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        self.assertEqual(calculate_nearest_rank_p75(data), 8.0)

    def test_median_calculation(self):
        self.assertEqual(calculate_median([]), 0.0)
        self.assertEqual(calculate_median([42.0]), 42.0)
        self.assertEqual(calculate_median([1.0, 3.0, 2.0]), 2.0)
        self.assertEqual(calculate_median([1.0, 2.0, 3.0, 4.0]), 2.5)

    def test_nearest_rank_percentiles_cover_boundaries_and_ties(self):
        self.assertIsNone(calculate_nearest_rank_percentile([], 50))
        self.assertEqual(
            [calculate_nearest_rank_percentile([7.0], p) for p in (50, 90, 99)],
            [7.0, 7.0, 7.0],
        )
        self.assertEqual(
            [calculate_nearest_rank_percentile([1.0, 9.0], p) for p in (50, 90, 99)],
            [1.0, 9.0, 9.0],
        )
        ten = list(range(1, 11))
        self.assertEqual(
            [calculate_nearest_rank_percentile(ten, p) for p in (50, 90, 99)],
            [5.0, 9.0, 10.0],
        )
        tied = [4.0, 2.0, 2.0, 1.0, 2.0]
        self.assertEqual(
            [calculate_nearest_rank_percentile(tied, p) for p in (50, 90, 99)],
            [2.0, 4.0, 4.0],
        )

    def test_disjoint_interval_union(self):
        """Disjoint union of overlapping or parallel intervals without double counting."""
        intervals = [
            (datetime(2026, 11, 1, 10, 0, tzinfo=timezone.utc), datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)),
            (datetime(2026, 11, 1, 11, 0, tzinfo=timezone.utc), datetime(2026, 11, 1, 13, 0, tzinfo=timezone.utc)),
            (datetime(2026, 11, 1, 14, 0, tzinfo=timezone.utc), datetime(2026, 11, 1, 15, 0, tzinfo=timezone.utc)),
        ]
        # [10..13] is 3h, [14..15] is 1h -> total 4h = 14400s
        total_sec = compute_disjoint_interval_union(intervals)
        self.assertEqual(total_sec, 14400.0)


class TestHalfOpenBoundariesAndFiltering(unittest.TestCase):
    """Test half-open window filtering [start, end)."""

    def setUp(self):
        self.w1_start = datetime(2026, 10, 24, 0, 0, tzinfo=timezone.utc)
        self.w1_end = datetime(2026, 10, 31, 0, 0, tzinfo=timezone.utc)

    def test_exact_half_open_boundaries(self):
        """Events at start are included; events at end are excluded."""
        event_at_start = {"event_time": "2026-10-24T00:00:00Z", "id": 1}
        event_mid = {"event_time": "2026-10-28T12:00:00Z", "id": 2}
        event_at_end = {"event_time": "2026-10-31T00:00:00Z", "id": 3}
        event_after = {"event_time": "2026-10-31T00:00:01Z", "id": 4}

        items = [event_at_start, event_mid, event_at_end, event_after]
        filtered = filter_events_half_open(items, "event_time", self.w1_start, self.w1_end)
        ids = [item["id"] for item in filtered]

        self.assertIn(1, ids, "Boundary start must be included [start, end)")
        self.assertIn(2, ids, "Midpoint must be included")
        self.assertNotIn(3, ids, "Boundary end must be excluded [start, end)")
        self.assertNotIn(4, ids, "Post-end event must be excluded")

    def test_merges_not_filtered_by_created_at(self):
        """A PR created before the window but merged inside the window MUST be counted as a merge."""
        pr = {
            "number": 101,
            "repo": "example-org/repo-alpha",
            "createdAt": "2026-10-01T00:00:00Z",  # Well before window
            "mergedAt": "2026-10-28T12:00:00Z",   # Inside window
            "state": "MERGED",
        }
        filtered_merges = filter_events_half_open([pr], "mergedAt", self.w1_start, self.w1_end)
        self.assertEqual(len(filtered_merges), 1)

    def test_backlog_merge_definition(self):
        """Backlog merge is defined as mergedAt - createdAt > 7 days (168 hours), NOT age at cutoff."""
        pr_fresh = {
            "createdAt": "2026-10-25T00:00:00Z",
            "mergedAt": "2026-10-28T00:00:00Z",  # 3 days
        }
        pr_backlog = {
            "createdAt": "2026-10-10T00:00:00Z",
            "mergedAt": "2026-10-28T00:00:00Z",  # 18 days > 7 days
        }
        aggregator = MetricsAggregator()
        self.assertFalse(aggregator.is_backlog_merge(pr_fresh))
        self.assertTrue(aggregator.is_backlog_merge(pr_backlog))

    def test_closed_unmerged_vs_current_state(self):
        """Closed-unmerged transition in window must be distinct from current closed state."""
        pr_closed_in_window = {
            "number": 201,
            "state": "CLOSED",
            "closedAt": "2026-10-29T10:00:00Z",
            "mergedAt": None,
        }
        pr_closed_prior_to_window = {
            "number": 202,
            "state": "CLOSED",
            "closedAt": "2026-10-15T10:00:00Z",
            "mergedAt": None,
        }
        # Both are currently in closed state, but only pr_closed_in_window had a transition in W1
        filtered = filter_events_half_open([pr_closed_in_window, pr_closed_prior_to_window], "closedAt", self.w1_start, self.w1_end)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["number"], 201)


class TestDeduplicationAndPagination(unittest.TestCase):
    """Test deduplication and paginated collection."""

    def test_deduplicate_prs_by_repo_and_number(self):
        collector = Collector(repos=["example-org/repo-alpha"])
        pr_batch = [
            {"repo": "example-org/repo-alpha", "number": 1, "id": "PR_1", "title": "First"},
            {"repo": "example-org/repo-alpha", "number": 1, "id": "PR_1", "title": "First duplicate"},
            {"repo": "example-org/repo-alpha", "number": 2, "id": "PR_2", "title": "Second"},
        ]
        deduped = collector.deduplicate_prs(pr_batch)
        self.assertEqual(len(deduped), 2)
        self.assertEqual([p["number"] for p in deduped], [1, 2])

    def test_deduplicate_timeline_events_by_event_id(self):
        collector = Collector(repos=["example-org/repo-alpha"])
        events = [
            {"id": "EVT_100", "event": "labeled", "createdAt": "2026-10-25T10:00:00Z"},
            {"id": "EVT_100", "event": "labeled", "createdAt": "2026-10-25T10:00:00Z"},
            {"id": "EVT_101", "event": "merged", "createdAt": "2026-10-25T12:00:00Z"},
        ]
        deduped = collector.deduplicate_events(events)
        self.assertEqual(len(deduped), 2)

    def test_missing_fields_tolerated(self):
        """Records with missing or null attributes do not crash parsing."""
        collector = Collector(repos=["example-org/repo-alpha"])
        bad_pr = {"repo": "example-org/repo-alpha", "number": 999}
        # Should not raise exception
        parsed = collector.normalize_pr_record(bad_pr)
        self.assertIsNone(parsed.get("createdAt"))
        self.assertIsNone(parsed.get("mergedAt"))
        self.assertEqual(parsed.get("additions"), 0)
        self.assertEqual(parsed.get("deletions"), 0)


class TestHonestIdleAndWaitingSemantics(unittest.TestCase):
    """Test the strict rules governing idle time and waiting metrics."""

    def setUp(self):
        self.aggregator = MetricsAggregator()

    def test_queued_time_cannot_become_review_execution_start(self):
        """queued_at to completed_at is attempt elapsed time; review_execution requires actual_review_started_at."""
        attempt = {
            "attempt_id": "att-1",
            "queued_at": "2026-11-01T10:00:00Z",
            "actual_review_started_at": None,  # Missing actual start
            "completed_at": "2026-11-01T10:05:00Z",
        }
        res = self.aggregator.compute_review_attempt_metrics(attempt)
        self.assertEqual(res["attempt_elapsed_sec"], 300.0)
        self.assertIsNone(res["review_execution_sec"], "Execution duration must be UNKNOWN without actual start")
        self.assertEqual(res["review_execution_status"], "UNKNOWN")

    def test_separate_attempts_cannot_form_one_delay(self):
        """Different attempts must have separate durations and inter-attempt gaps, not single pickup delay."""
        attempt1 = {
            "attempt_number": 1,
            "started_at": "2026-11-01T10:00:00Z",
            "completed_at": "2026-11-01T10:04:00Z",
        }
        attempt2 = {
            "attempt_number": 2,
            "started_at": "2026-11-01T10:20:00Z",
            "completed_at": "2026-11-01T10:25:00Z",
        }
        attempts = [attempt1, attempt2]
        res = self.aggregator.compute_multi_attempt_metrics(attempts)
        self.assertEqual(len(res["attempts"]), 2)
        # Gap between attempt 1 completion and attempt 2 start is 16m = 960s
        self.assertEqual(res["attempts"][1]["inter_attempt_gap_sec"], 960.0)
        # Attempt 1 has no prior attempt gap
        self.assertIsNone(res["attempts"][0]["inter_attempt_gap_sec"])

    def test_post_merge_review_cannot_establish_pre_merge_authority_ready(self):
        """Review completing after merge cannot prove authority readiness pre-merge."""
        pr = {
            "mergedAt": "2026-11-01T12:00:00Z",
            "review_completed_at": "2026-11-01T12:05:00Z",  # Completed AFTER merge
        }
        ready_status = self.aggregator.derive_authority_ready(pr)
        self.assertEqual(ready_status, "UNKNOWN")

    def test_missing_owner_hold_evidence_yields_unknown_idle(self):
        """Eligible unattended duration cannot be assumed 0s without continuous telemetry."""
        pr = {
            "number": 501,
            "state": "OPEN",
            "telemetry_coverage": 0.0,
            "has_continuous_observation": False,
        }
        idle_metric = self.aggregator.compute_eligible_unattended_duration(pr)
        self.assertIsNone(idle_metric["duration_sec"])
        self.assertEqual(idle_metric["status"], "UNKNOWN")
        self.assertNotEqual(idle_metric["duration_sec"], 0)

    def test_clock_conflict_yields_conflict(self):
        """Events where end < start must yield CONFLICT rather than negative or wrapped duration."""
        res = self.aggregator.compute_interval_duration("2026-11-01T12:00:00Z", "2026-11-01T11:00:00Z")
        self.assertEqual(res["status"], "CONFLICT")
        self.assertIsNone(res["duration_sec"])

    def test_closure_sprint_separated_from_task_to_merge(self):
        """Closure sprint duration must never overwrite or substitute for task_to_merge."""
        pr = {
            "initial_task_accepted_at": None,  # Not recorded
            "closure_sprint_accepted_at": "2026-11-07T07:41:00Z",
            "mergedAt": "2026-11-07T08:43:00Z",
        }
        res = self.aggregator.compute_lifecycle_durations(pr)
        self.assertEqual(res["task_to_merge_status"], "UNKNOWN")
        self.assertIsNotNone(res["closure_sprint_to_merge_sec"])
        self.assertEqual(res["closure_sprint_to_merge_sec"], 3720.0)


class TestDashboardRenderer(unittest.TestCase):
    """Test Markdown dashboard rendering across all states."""

    def setUp(self):
        self.renderer = DashboardRenderer()

    def test_render_all_six_sections_present(self):
        """Dashboard must contain the 6 required sections in exact order."""
        summary_data = {
            "status": "FRESH",
            "generated_at": "2026-11-07T12:00:00Z",
            "data_through": "2026-11-07T12:00:00Z",
            "w1_bounds": ("2026-10-24T00:00:00Z", "2026-10-31T00:00:00Z"),
            "w2_bounds": ("2026-10-31T00:00:00Z", "2026-11-07T12:00:00Z"),
            "sources": {"example-org/repo-alpha": {"status": "COMPLETE", "cutoff": "2026-11-07T12:00:00Z"}},
            "repo_comparison": [
                {
                    "repo": "example-org/repo-alpha",
                    "created": 10,
                    "merged_w1": 8,
                    "merged_w2": 12,
                    "closed_unmerged_w2": 1,
                    "current_closed_unmerged": 15,
                    "still_open": 3,
                    "all_median_hours": 4.5,
                    "all_p75_hours": 12.0,
                    "comp_median_hours": 3.8,
                    "comp_p75_hours": 8.5,
                    "backlog_n": 1,
                    "backlog_median_hours": 200.0,
                }
            ],
            "stage_dwell": [
                {"stage": "stage:1-coding", "median_h": 2.1, "p75_h": 5.0, "n": 10, "total_n": 12, "conflicts": 0}
            ],
            "handoffs": [
                {"name": "evidence_ready -> review_requested", "n": 5, "total_n": 10, "status": "PARTIAL"}
            ],
            "open_prs_known_idle": [],
            "open_prs_unknown_idle": [
                {
                    "url": "https://github.com/example-org/repo-alpha/pull/1",
                    "sha": "abcdef1",
                    "stage": "stage:2-evidence",
                    "next_action": "Run test",
                    "owner": "worker-1",
                    "hold_status": "none",
                    "potential_handoff_waiting": "2h",
                    "quiet_time": "3h",
                }
            ],
        }

        md = self.renderer.render(summary_data)

        # Check for 6 major sections
        self.assertIn("# PRW Metrics Dashboard", md)
        self.assertIn("## 1. Header & Coverage", md)
        self.assertIn("## 2. Repository Comparison", md)
        self.assertIn("## 3. Stage Dwell", md)
        self.assertIn("## 4. Handoff Waiting Breakdown", md)
        self.assertIn("## 5. Open PR Attention Table", md)
        self.assertIn("## 6. Definitions & Limitations", md)

        # Check section 5 subsections
        self.assertIn("### 5A. Open PRs with Observed Eligible Unattended Duration", md)
        self.assertRegex(md, r"(?m)^### 5B\. .+$")

    def test_render_states(self):
        """Dashboard must gracefully handle EMPTY, STALE, and PARTIAL_FAILURE."""
        for state in ["EMPTY", "STALE", "PARTIAL_FAILURE"]:
            data = {
                "status": state,
                "generated_at": "2026-11-07T12:00:00Z",
                "data_through": "2026-11-07T10:00:00Z",
                "sources": {"example-org/repo-alpha": {"status": state, "cutoff": "2026-11-07T10:00:00Z"}},
                "repo_comparison": [],
                "stage_dwell": [],
                "handoffs": [],
                "open_prs_known_idle": [],
                "open_prs_unknown_idle": [],
            }
            md = self.renderer.render(data)
            self.assertIn(f"**Status**: **{state}**", md)


class TestPublisher(unittest.TestCase):
    """Test safe scoped git publication using isolated index files."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.remote_dir = os.path.join(self.temp_dir, "remote.git")
        self.local_dir = os.path.join(self.temp_dir, "local")

        # Initialize bare remote repo with default branch main
        subprocess.run(["git", "init", "--bare", self.remote_dir], check=True, capture_output=True)
        subprocess.run(["git", "-C", self.remote_dir, "symbolic-ref", "HEAD", "refs/heads/main"], check=True, capture_output=True)

        # Clone to local and ensure branch is main across git versions
        subprocess.run(["git", "clone", self.remote_dir, self.local_dir], check=True, capture_output=True)
        subprocess.run(["git", "-C", self.local_dir, "checkout", "-B", "main"], check=True, capture_output=True)

        # Configure user
        env = os.environ.copy()
        env["HERMES_SKIP_EXAMPLE_COM_GUARD"] = "1"
        subprocess.run(["git", "-C", self.local_dir, "config", "user.name", "Test User"], check=True)
        subprocess.run(["git", "-C", self.local_dir, "config", "user.email", "metrics-bot@test.local"], check=True)

        # Initial commit
        readme_path = os.path.join(self.local_dir, "README.md")
        with open(readme_path, "w") as f:
            f.write("# Root README\n")
        subprocess.run(["git", "-C", self.local_dir, "add", "README.md"], check=True)
        subprocess.run(["git", "-C", self.local_dir, "commit", "-m", "Initial commit"], check=True, env=env)
        subprocess.run(["git", "-C", self.local_dir, "push", "origin", "main"], check=True)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_failed_collection_retains_prior_and_does_not_commit(self):
        """If collection status is FAILED, publisher must not commit or push."""
        res = publish_dashboard(
            markdown_text="# Content",
            status="FAILED",
            repo_path=self.local_dir,
            target_relpath="dashboards/prw/README.md",
            verify_private_fn=lambda _: True,
        )
        self.assertEqual(res["action"], "RETAINED_PRIOR")
        self.assertFalse(res["committed"])

    def test_no_change_when_normalized_content_matches(self):
        """When content is identical except for volatile Generated at line, no commit is made."""
        content1 = "# PRW Metrics Dashboard\nGenerated at: 2026-11-07T12:00:00Z\nCutoff: 2026-11-07T08:00:00Z\nData: 42\n"
        content2 = "# PRW Metrics Dashboard\nGenerated at: 2026-11-07T16:00:00Z\nCutoff: 2026-11-07T08:00:00Z\nData: 42\n"

        # First publish
        res1 = publish_dashboard(
            markdown_text=content1,
            status="FRESH",
            repo_path=self.local_dir,
            target_relpath="dashboards/prw/README.md",
            verify_private_fn=lambda _: True,
        )
        self.assertTrue(res1["committed"])

        # Second publish with identical data, only newer generation time
        res2 = publish_dashboard(
            markdown_text=content2,
            status="FRESH",
            repo_path=self.local_dir,
            target_relpath="dashboards/prw/README.md",
            verify_private_fn=lambda _: True,
        )
        self.assertEqual(res2["action"], "NO_CHANGE")
        self.assertFalse(res2["committed"])

    def test_scoped_isolated_index_does_not_touch_dirty_working_tree(self):
        """Publisher must use isolated index and leave dirty files in working tree untouched."""
        dirty_file = os.path.join(self.local_dir, "dirty_worktree_file.txt")
        with open(dirty_file, "w") as f:
            f.write("uncommitted local edits\n")

        content = "# New Dashboard\nCutoff: 2026-11-07T12:00:00Z\n"
        res = publish_dashboard(
            markdown_text=content,
            status="FRESH",
            repo_path=self.local_dir,
            target_relpath="dashboards/prw/README.md",
            verify_private_fn=lambda _: True,
        )
        self.assertTrue(res["committed"])

        # Dirty file must still exist and be untracked/dirty
        self.assertTrue(os.path.exists(dirty_file))
        with open(dirty_file, "r") as f:
            self.assertEqual(f.read(), "uncommitted local edits\n")

        status_out = subprocess.run(
            ["git", "-C", self.local_dir, "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        self.assertIn("?? dirty_worktree_file.txt", status_out)


class TestCollectorPaginationAndSearchCap(unittest.TestCase):
    """Test pagination, search cap splitting, and per-source failure fallback in Collector."""

    def test_search_window_splitting_on_cap(self):
        """When count >= cap, split window at midpoint into two half-open sub-windows."""
        start = datetime(2026, 11, 1, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 11, 8, 0, 0, tzinfo=timezone.utc)

        # Under cap: no split
        w_under = split_search_window_on_cap(start, end, count=500, cap=1000)
        self.assertEqual(len(w_under), 1)
        self.assertEqual(w_under[0], (start, end))

        # At or over cap: split at midpoint
        w_over = split_search_window_on_cap(start, end, count=1200, cap=1000)
        self.assertEqual(len(w_over), 2)
        mid = start + (end - start) / 2
        self.assertEqual(w_over[0], (start, mid))
        self.assertEqual(w_over[1], (mid, end))

    def test_collect_repo_prs_paginated_multi_page(self):
        """Test multi-page collection with pagination stopping condition and attribute normalization."""
        def mock_fetch(repo, page, per_page):
            if page == 1:
                return [
                    {
                        "number": i,
                        "title": f"PR {i}",
                        "created_at": "2026-11-05T10:00:00Z",
                        "draft": False,
                        "state": "open",
                        "head": {"sha": f"sha{i}"},
                        "html_url": f"https://github.com/{repo}/pull/{i}",
                    }
                    for i in range(1, 101)
                ]
            elif page == 2:
                return [
                    {
                        "number": i,
                        "title": f"PR {i}",
                        "created_at": "2026-11-04T10:00:00Z",
                        "draft": True,
                        "state": "closed",
                        "merged_at": "2026-11-05T12:00:00Z",
                        "head": {"sha": f"sha{i}"},
                        "html_url": f"https://github.com/{repo}/pull/{i}",
                    }
                    for i in range(101, 126)
                ]
            return []

        collector = Collector(repos=["example-org/repo-alpha"])
        prs = collector.collect_repo_prs_paginated("example-org/repo-alpha", fetch_page_fn=mock_fetch, per_page=100)
        self.assertEqual(len(prs), 125)

        pr1 = prs[0]
        self.assertEqual(pr1["number"], 1)
        self.assertEqual(pr1["state"], "OPEN")
        self.assertEqual(pr1["createdAt"], "2026-11-05T10:00:00Z")
        self.assertFalse(pr1["isDraft"])
        self.assertEqual(pr1["headRefOid"], "sha1")

        pr101 = prs[100]
        self.assertEqual(pr101["number"], 101)
        self.assertEqual(pr101["state"], "MERGED")
        self.assertEqual(pr101["mergedAt"], "2026-11-05T12:00:00Z")
        self.assertTrue(pr101["isDraft"])

    def test_per_source_failure_fallback_partial_and_failed(self):
        """Partial source failure preserves prior data (PARTIAL_FAILURE); total failure returns FAILED."""
        temp_state = tempfile.mkdtemp()
        try:
            prior_beta_prs = [
                {
                    "number": 10,
                    "repo": "example-org/repo-beta",
                    "title": "Beta PR 10",
                    "state": "OPEN",
                    "createdAt": "2026-11-05T10:00:00Z",
                    "headRefOid": "beta10",
                }
            ]
            with open(os.path.join(temp_state, "enriched_prs.json"), "w") as f:
                json.dump(prior_beta_prs, f)

            # Scenario 1: Partial failure (alpha succeeds, beta fails)
            def fetch_mock(repo, page, per_page):
                if repo == "example-org/repo-alpha":
                    return [{"number": 1, "repo": repo, "state": "open", "head": {"sha": "a1"}}]
                raise RuntimeError("API rate limit exceeded for repo-beta")

            collector = Collector(repos=["example-org/repo-alpha", "example-org/repo-beta"])
            res = collector.collect_all(state_dir=temp_state, fetch_page_fn=fetch_mock, fetch_timeline_fn=lambda r, n: [])

            self.assertEqual(res["status"], "PARTIAL_FAILURE")
            self.assertEqual(res["sources"]["example-org/repo-alpha"]["status"], "COMPLETE")
            self.assertEqual(res["sources"]["example-org/repo-beta"]["status"], "PARTIAL_FAILURE")
            pr_numbers = [p["number"] for p in res["prs"]]
            self.assertIn(1, pr_numbers)
            self.assertIn(10, pr_numbers)

            # Scenario 2: Total failure with no cached data
            empty_temp = tempfile.mkdtemp()
            try:
                def failing_fetch(repo, page, per_page):
                    raise RuntimeError("Network down")

                collector_fail = Collector(repos=["example-org/repo-alpha", "example-org/repo-beta"])
                fail_res = collector_fail.collect_all(state_dir=empty_temp, fetch_page_fn=failing_fetch)
                self.assertEqual(fail_res["status"], "FAILED")
                self.assertEqual(len(fail_res["prs"]), 0)
            finally:
                shutil.rmtree(empty_temp)
        finally:
            shutil.rmtree(temp_state)


class TestStageDwellAndHandoffAggregation(unittest.TestCase):
    """Test stage dwell and handoff breakdown calculations in MetricsAggregator."""

    def test_stage_dwell_computation_and_conflicts_from_timeline(self):
        """Timeline events produce median dwell, p75 dwell, and detect clock conflicts."""
        cutoff = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)
        agg = MetricsAggregator(cutoff_dt=cutoff)

        timeline = [
            # PR 1: stage:1-coding entered at 10:00, exited at 12:00 (2 hours)
            {"repo": "example-org/repo-alpha", "pr_number": 1, "stage": "stage:1-coding", "start_at": "2026-11-05T10:00:00Z", "end_at": "2026-11-05T12:00:00Z"},
            # PR 2: stage:1-coding entered at 10:00, exited at 14:00 (4 hours)
            {"repo": "example-org/repo-alpha", "pr_number": 2, "stage": "stage:1-coding", "start_at": "2026-11-05T10:00:00Z", "end_at": "2026-11-05T14:00:00Z"},
            # PR 3: clock conflict (end < start)
            {"repo": "example-org/repo-alpha", "pr_number": 3, "stage": "stage:1-coding", "start_at": "2026-11-05T15:00:00Z", "end_at": "2026-11-05T14:00:00Z"},
        ]
        prs = [
            {"repo": "example-org/repo-alpha", "number": 1, "mergedAt": "2026-11-06T10:00:00Z"},
            {"repo": "example-org/repo-alpha", "number": 2, "mergedAt": "2026-11-06T10:00:00Z"},
            {"repo": "example-org/repo-alpha", "number": 3, "mergedAt": "2026-11-06T10:00:00Z"},
        ]

        dwell = agg.compute_stage_dwell(prs, timeline_events=timeline)
        coding_dwell = next(d for d in dwell if d["stage"] == "stage:1-coding")
        self.assertEqual(coding_dwell["median_h"], 3.0)
        self.assertEqual(coding_dwell["p75_h"], 4.0)
        self.assertEqual(coding_dwell["p50_h"], 2.0)
        self.assertEqual(coding_dwell["p90_h"], 4.0)
        self.assertEqual(coding_dwell["p99_h"], 4.0)
        self.assertEqual(coding_dwell["conflicts"], 1)
        self.assertEqual(coding_dwell["n"], 2)

    def test_handoff_breakdown_metrics(self):
        """Test calculation of observed counts, medians, and honest rules across handoffs."""
        cutoff = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)
        agg = MetricsAggregator(cutoff_dt=cutoff)

        prs = [
            {
                "repo": "example-org/repo-alpha",
                "number": 1,
                "mergedAt": "2026-11-05T16:00:00Z",
                "evidence_ready_at": "2026-11-05T10:00:00Z",
                "review_requested_at": "2026-11-05T10:30:00Z",
                "actual_review_started_at": "2026-11-05T11:00:00Z",
                "queued_at": "2026-11-05T10:31:00Z",
                "review_returned_at": "2026-11-05T11:45:00Z",
                "next_action_started_at": "2026-11-05T12:00:00Z",
                "review_completed_at": "2026-11-05T11:45:00Z",
                "authority_ready_at": "2026-11-05T12:00:00Z",
                "final_ready": True,
                "merge_authority": True,
                "initial_task_accepted_at": "2026-11-05T08:00:00Z",
                "closure_sprint_accepted_at": "2026-11-05T15:00:00Z",
            },
            {
                # PR with post-merge review: cannot establish authority readiness pre-merge
                "repo": "example-org/repo-alpha",
                "number": 2,
                "mergedAt": "2026-11-05T12:00:00Z",
                "review_completed_at": "2026-11-05T13:00:00Z",
                "authority_ready_at": "2026-11-05T13:00:00Z",
                "review_requested_at": "2026-11-05T10:00:00Z",
                "queued_at": "2026-11-05T10:01:00Z",
            }
        ]

        handoffs = agg.compute_handoff_breakdown(prs, total_cohort_n=2)
        ev_to_req = next(h for h in handoffs if h["name"] == "evidence_ready -> review_requested")
        self.assertEqual(ev_to_req["observed_n"], 1)
        self.assertEqual(ev_to_req["median_sec"], 1800.0)
        self.assertEqual(ev_to_req["sample_n"], 1)
        self.assertEqual([ev_to_req[f"p{p}_sec"] for p in (50, 90, 99)], [1800.0] * 3)

        req_to_act = next(h for h in handoffs if h["name"] == "review_requested -> actual_review_started")
        self.assertEqual(req_to_act["observed_n"], 1)
        self.assertEqual(req_to_act["median_sec"], 1800.0)

        auth_to_merge = next(h for h in handoffs if h["name"] == "authority_ready -> merged")
        self.assertEqual(auth_to_merge["observed_n"], 1)
        self.assertEqual(auth_to_merge["median_sec"], 14400.0)

        task_to_merge = next(h for h in handoffs if h["name"] == "task_accepted -> merged")
        self.assertEqual(task_to_merge["observed_n"], 1)
        self.assertEqual(task_to_merge["median_sec"], 28800.0)

        sprint_to_merge = next(h for h in handoffs if h["name"] == "closure_sprint_accepted -> merged")
        self.assertEqual(sprint_to_merge["observed_n"], 1)
        self.assertEqual(sprint_to_merge["median_sec"], 3600.0)


    def test_canonical_transition_events_pair_by_exact_pr_candidate_and_attempt(self):
        cutoff = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)
        collector = Collector(cutoff_dt=cutoff)
        prs = [
            {
                "repo": "example-org/repo-alpha", "number": 20,
                "headRefOid": "c" * 40, "state": "OPEN",
                "createdAt": "2026-11-01T00:00:00Z",
            }
        ]
        event_rows = [
            ("evidence_ready", "2026-11-05T10:00:00Z", "a" * 40, 1),
            ("review_requested", "2026-11-05T10:10:00Z", "a" * 40, 1),
            ("actual_review_started", "2026-11-05T10:20:00Z", "a" * 40, 1),
            ("review_return", "2026-11-05T11:00:00Z", "a" * 40, 1),
            ("next_action_started", "2026-11-05T11:05:00Z", "a" * 40, 1),
            # Similar transitions on different candidates may not cross-pair.
            ("review_requested", "2026-11-05T12:00:00Z", "b" * 40, 2),
            ("actual_review_started", "2026-11-05T12:10:00Z", "a" * 40, 2),
        ]
        with tempfile.TemporaryDirectory() as receipts_dir:
            path = os.path.join(receipts_dir, "transition-events.jsonl")
            with open(path, "w", encoding="utf-8") as stream:
                for index, (event_type, occurred_at, candidate_sha, attempt) in enumerate(event_rows):
                    stream.write(json.dumps({
                        "event_id": f"event-{index}",
                        "event_type": event_type,
                        "occurred_at": occurred_at,
                        # Deliberately far from occurred_at: audit clock is not the event clock.
                        "observed_at": "2026-11-09T12:00:00Z",
                        "pr_id": "example-org/repo-alpha#20",
                        "candidate_sha": candidate_sha,
                        "attempt_number": attempt,
                    }) + "\n")
                stream.write("{malformed receipt line}\n")

            receipts = collector.collect_receipts_from_dir(receipts_dir)
            self.assertEqual(len(receipts), len(event_rows))
            self.assertTrue(all("source_receipt" not in receipt for receipt in receipts))
            self.assertEqual(receipts[0]["occurred_at"], "2026-11-05T10:00:00Z")
            self.assertEqual(receipts[0]["observed_at"], "2026-11-09T12:00:00Z")
            self.assertEqual(collector.receipt_scan_stats["status"], "PARTIAL")

            with tempfile.TemporaryDirectory() as publisher_dir:
                telemetry = Publisher(repo_path=publisher_dir).write_telemetry_bundle(
                    {"w2_bounds": ["2026-11-02", "2026-11-09"]},
                    handoff_records=receipts,
                )
            retained_events = next(
                value for key, value in telemetry.items() if key.endswith("retained_handoffs.jsonl")
            )
            self.assertNotIn(receipts_dir, retained_events)
            self.assertIn("observed_at", retained_events)
            self.assertIn("occurred_at", retained_events)

            handoffs = MetricsAggregator(cutoff_dt=cutoff).compute_handoff_breakdown(
                prs, handoff_records=receipts, receipt_stats=collector.receipt_scan_stats,
            )

        evidence = next(
            row for row in handoffs
            if row["name"] == "evidence_ready -> review_requested"
        )
        review = next(row for row in handoffs if row["name"] == "review_requested -> actual_review_started")
        returned = next(row for row in handoffs if row["name"] == "review_return -> next_substantive_action")
        self.assertEqual(evidence["median_sec"], 600.0)
        self.assertEqual(review["median_sec"], 600.0)
        self.assertEqual(returned["median_sec"], 300.0)
        self.assertEqual(evidence["receipt_events_seen"], len(event_rows))
        self.assertEqual(evidence["receipt_events_unmatched"], 2)
        self.assertEqual(evidence["receipt_pairs"], 3)
        self.assertEqual(evidence["receipt_parse_errors"], 1)
        self.assertEqual(evidence["receipt_status"], "PARTIAL")

    def test_invalid_utf8_optional_json_receipt_is_counted_without_aborting(self):
        collector = Collector(cutoff_dt=datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc))
        with tempfile.TemporaryDirectory() as receipts_dir:
            Path(receipts_dir, "run.stats.json").write_bytes(b"\xff")
            receipts = collector.collect_receipts_from_dir(receipts_dir)

        self.assertEqual(receipts, [])
        self.assertEqual(collector.receipt_scan_stats["status"], "PARTIAL")
        self.assertEqual(collector.receipt_scan_stats["receipt_parse_errors"], 1)

    def test_transition_receipts_preserve_fractional_seconds_and_reject_reversed_order(self):
        aggregator = MetricsAggregator()
        prs = [{"repo": "example-org/repo-alpha", "number": 20}]
        records = [
            {
                "record_type": "transition_event", "event_id": "fractional-start",
                "event_type": "evidence_ready", "occurred_at": "2026-11-05T10:00:00.900Z",
                "pr_id": "example-org/repo-alpha#20", "candidate_sha": "a" * 40,
                "attempt_number": 1,
            },
            {
                "record_type": "transition_event", "event_id": "fractional-end",
                "event_type": "review_requested", "occurred_at": "2026-11-05T10:00:01.100Z",
                "pr_id": "example-org/repo-alpha#20", "candidate_sha": "a" * 40,
                "attempt_number": 1,
            },
            {
                "record_type": "transition_event", "event_id": "reversed-start",
                "event_type": "evidence_ready", "occurred_at": "2026-11-05T10:00:02.900Z",
                "pr_id": "example-org/repo-alpha#20", "candidate_sha": "b" * 40,
                "attempt_number": 2,
            },
            {
                "record_type": "transition_event", "event_id": "reversed-end",
                "event_type": "review_requested", "occurred_at": "2026-11-05T10:00:02.100Z",
                "pr_id": "example-org/repo-alpha#20", "candidate_sha": "b" * 40,
                "attempt_number": 2,
            },
        ]

        _, pairing = aggregator.adapt_transition_event_receipts(records, prs)
        handoffs = aggregator.compute_handoff_breakdown(prs, handoff_records=records)
        evidence = next(row for row in handoffs if row["name"] == "evidence_ready -> review_requested")
        self.assertEqual(pairing["receipt_pairs"], 1)
        self.assertEqual(pairing["receipt_events_unmatched"], 2)
        self.assertEqual(evidence["observed_n"], 1)
        self.assertEqual(evidence["median_sec"], 0.2)

    def test_missing_transition_feed_is_unknown_and_does_not_fail_collection(self):
        collector = Collector(cutoff_dt=datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc))
        with tempfile.TemporaryDirectory() as parent:
            missing = os.path.join(parent, "no-receipt-feed")
            result = collector.collect_all(
                offline=True, receipts_dir=missing,
            )
        self.assertEqual(result["status"], "EMPTY")
        self.assertEqual(result["handoff_receipt_stats"]["status"], "UNAVAILABLE")
        self.assertEqual(result["handoff_receipt_stats"]["receipt_read_errors"], 1)


class TestOpenPRAttentionPartitioningAndSorting(unittest.TestCase):
    """Test 5A vs 5B partitioning and sorting of open PRs."""

    def test_open_pr_attention_5a_vs_5b_partitioning_and_sort(self):
        cutoff = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)
        agg = MetricsAggregator(cutoff_dt=cutoff)

        prs = [
            # PR 1: continuous telemetry, 3600s idle -> placed in 5A
            {
                "repo": "example-org/repo-alpha",
                "number": 1,
                "state": "OPEN",
                "has_continuous_observation": True,
                "telemetry_coverage": 1.0,
                "eligible_intervals": [
                    (datetime(2026, 11, 7, 10, 0, tzinfo=timezone.utc), datetime(2026, 11, 7, 11, 0, tzinfo=timezone.utc))
                ],
                "url": "https://github.com/example-org/repo-alpha/pull/1",
                "headRefOid": "1111111",
            },
            # PR 2: continuous telemetry, 10800s idle -> placed in 5A
            {
                "repo": "example-org/repo-alpha",
                "number": 2,
                "state": "OPEN",
                "has_continuous_observation": True,
                "telemetry_coverage": 1.0,
                "eligible_intervals": [
                    (datetime(2026, 11, 7, 6, 0, tzinfo=timezone.utc), datetime(2026, 11, 7, 9, 0, tzinfo=timezone.utc))
                ],
                "url": "https://github.com/example-org/repo-alpha/pull/2",
                "headRefOid": "2222222",
            },
            # PR 3: 0% telemetry -> placed in 5B
            {
                "repo": "example-org/repo-alpha",
                "number": 3,
                "state": "OPEN",
                "has_continuous_observation": False,
                "telemetry_coverage": 0.0,
                "url": "https://github.com/example-org/repo-alpha/pull/3",
                "headRefOid": "3333333",
            },
        ]

        summary = agg.aggregate_full_dataset(prs=prs)
        known = summary["open_prs_known_idle"]
        unknown = summary["open_prs_unknown_idle"]

        self.assertEqual(len(known), 2)
        self.assertEqual(len(unknown), 1)

        # Known idle must be sorted descending: PR 2 (10800s) before PR 1 (3600s)
        self.assertEqual(known[0]["sha"], "2222222")
        self.assertEqual(known[0]["eligible_unattended_duration_sec"], 10800.0)
        self.assertEqual(known[1]["sha"], "1111111")
        self.assertEqual(known[1]["eligible_unattended_duration_sec"], 3600.0)

        # PR 3 must be in unknown
        self.assertEqual(unknown[0]["sha"], "3333333")


class TestCLIEnvironmentDefaults(unittest.TestCase):
    """Test CLI argument parsing and environment variable defaults."""

    def test_main_cli_environment_defaults(self):
        temp_dir = tempfile.mkdtemp()
        try:
            with open(os.path.join(temp_dir, "enriched_prs.json"), "w") as f:
                json.dump([], f)
            with open(os.path.join(temp_dir, "raw_timeline.json"), "w") as f:
                json.dump([], f)

            env = os.environ.copy()
            env["PRW_METRICS_REPOS"] = "example-org/repo-alpha"
            env["PRW_METRICS_INPUT_DIR"] = temp_dir
            env["PRW_METRICS_OFFLINE"] = "1"

            root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            script_path = os.path.join(root_dir, "scripts", "prw_metrics.py")
            proc = subprocess.run(
                ["python3", script_path],
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0)
            self.assertIn("# PRW Metrics Dashboard", proc.stdout)
            self.assertIn("## 1. Header & Coverage", proc.stdout)
        finally:
            shutil.rmtree(temp_dir)


class TestTimeSemanticsHumanInterventionsAndTitleParsing(unittest.TestCase):
    """Test Task 4 time semantics, human intervention aggregation, retention readback, and title parsing."""

    def test_overlapping_active_agents_union_vs_effort_sum(self):
        """Union of parallel agents gives active wall time; arithmetic sum gives agent effort."""
        agg = MetricsAggregator()
        pr = {
            "number": 1,
            "repo": "example-org/repo-alpha",
            "createdAt": "2026-11-05T09:00:00Z",
            "mergedAt": "2026-11-05T14:00:00Z",
            "initial_task_accepted_at": "2026-11-05T09:30:00Z",
        }
        # Two parallel agents: Agent 1 (10:00 - 12:00 = 2h), Agent 2 (11:00 - 13:00 = 2h)
        events = [
            {
                "pr_number": 1,
                "span_kind": "observed_active_execution",
                "agent_id": "agent-1",
                "start_at": "2026-11-05T10:00:00Z",
                "end_at": "2026-11-05T12:00:00Z",
            },
            {
                "pr_number": 1,
                "span_kind": "observed_active_execution",
                "agent_id": "agent-2",
                "start_at": "2026-11-05T11:00:00Z",
                "end_at": "2026-11-05T13:00:00Z",
            },
        ]
        metrics = agg.compute_time_semantics(pr, pilot_events=events)
        # Disjoint union: 10:00 to 13:00 = 3h = 10800s
        self.assertEqual(metrics["observed_active_wall_sec"], 10800.0)
        # Arithmetic effort sum: 2h + 2h = 4h = 14400s
        self.assertEqual(metrics["agent_effort_sec"], 14400.0)
        self.assertGreater(metrics["agent_effort_sec"], metrics["observed_active_wall_sec"])

    def test_operation_elapsed_not_counted_as_pure_active_and_residual_not_waste(self):
        """CLI/API span includes queue/setup time; residual elapsed is NOT classified as waste."""
        agg = MetricsAggregator()
        pr = {
            "number": 2,
            "repo": "example-org/repo-alpha",
            "createdAt": "2026-11-05T10:00:00Z",
            "mergedAt": "2026-11-05T12:00:00Z", # 2h = 7200s elapsed
        }
        events = [
            # Operation elapsed includes setup / queue: 10:00 -> 10:30 (1800s)
            {
                "pr_number": 2,
                "span_kind": "observed_operation_elapsed",
                "start_at": "2026-11-05T10:00:00Z",
                "end_at": "2026-11-05T10:30:00Z",
            },
            # Evidenced active execution: 10:05 -> 10:30 (1500s)
            {
                "pr_number": 2,
                "span_kind": "observed_active_execution",
                "start_at": "2026-11-05T10:05:00Z",
                "end_at": "2026-11-05T10:30:00Z",
            },
        ]
        metrics = agg.compute_time_semantics(pr, pilot_events=events)
        self.assertEqual(metrics["observed_operation_elapsed_sec"], 1800.0)
        self.assertEqual(metrics["observed_active_wall_sec"], 1500.0)
        # Residual: 7200 - 1500 = 5700s
        self.assertEqual(metrics["unattributed_or_waiting_residual_sec"], 5700.0)
        self.assertEqual(metrics["residual_classification"], "UNATTRIBUTED_OR_WAITING_NOT_WASTE")

    def test_absent_telemetry_and_cross_attempt_mismatch_remain_unknown(self):
        """Missing telemetry or mismatched attempts must remain UNKNOWN (None), never 0."""
        agg = MetricsAggregator()
        pr = {
            "number": 3,
            "repo": "example-org/repo-alpha",
            "createdAt": "2026-11-05T10:00:00Z",
            "mergedAt": "2026-11-05T12:00:00Z",
        }
        metrics = agg.compute_time_semantics(pr, pilot_events=[])
        self.assertIsNone(metrics["task_elapsed_sec"])
        self.assertIsNone(metrics["observed_active_wall_sec"])
        self.assertIsNone(metrics["agent_effort_sec"])
        self.assertIsNone(metrics["avoidable_unattended_sec"])

    def test_bot_origin_and_initial_assignment_excluded_from_episodes(self):
        """Bots/automated prompts are excluded; initial task assignment is counted in raw human messages only."""
        agg = MetricsAggregator()
        episodes = [
            # Human initial assignment: counted in raw_human_messages, but excluded from qualifying episodes
            {
                "episode_id": "ep-1",
                "is_bot": False,
                "actor_status": "human",
                "origin": "user",
                "raw_message_count": 2,
                "is_initial_assignment": True,
                "label": "good",
            },
            # Bot watchdog message: excluded completely
            {
                "episode_id": "ep-bot",
                "is_bot": True,
                "origin": "bot",
                "raw_message_count": 5,
                "is_initial_assignment": False,
                "label": "unknown",
            },
            # Human qualifying intervention
            {
                "episode_id": "ep-2",
                "is_bot": False,
                "actor_status": "human",
                "origin": "user",
                "raw_message_count": 1,
                "is_initial_assignment": False,
                "label": "bad",
            },
        ]
        summary = agg.compute_human_interventions(episodes)
        # raw_human_messages: 2 (from initial) + 1 (from ep-2) = 3
        self.assertEqual(summary["raw_human_messages"], 3)
        # qualifying_episodes: only ep-2
        self.assertEqual(summary["qualifying_episodes"], 1)
        self.assertEqual(summary["label_breakdown"]["bad"], 1)

    def test_mirrored_message_and_multi_pr_episode_deduplication(self):
        """Mirrored transcripts and multi-PR mentions deduplicate to one episode and message count."""
        agg = MetricsAggregator()
        episodes = [
            {
                "episode_id": "ep-mirror",
                "actor_status": "human",
                "message_ids": ["msg-100", "msg-101"],
                "is_bot": False,
                "origin": "user",
                "raw_message_count": 2,
                "is_initial_assignment": False,
                "label": "good",
                "pr_attribution": "example-org/repo-alpha#1",
            },
            # Duplicate mirrored record with same episode_id / message_ids referring to repo-alpha#2
            {
                "episode_id": "ep-mirror",
                "actor_status": "human",
                "message_ids": ["msg-100", "msg-101"],
                "is_bot": False,
                "origin": "user",
                "raw_message_count": 2,
                "is_initial_assignment": False,
                "label": "good",
                "pr_attribution": "example-org/repo-alpha#2",
            },
        ]
        summary = agg.compute_human_interventions(episodes)
        self.assertEqual(summary["qualifying_episodes"], 1)
        self.assertEqual(summary["raw_human_messages"], 2)

    def test_unassigned_task_level_episode_and_changed_spec_vs_agent_miss_calibration(self):
        """Unassigned episodes persist while unresolved annotator disagreement stays unknown."""
        agg = MetricsAggregator()
        episodes = [
            # Unassigned task-level episode with differing annotators
            {
                "episode_id": "ep-task-unassigned",
                "is_bot": False,
                "actor_status": "human",
                "origin": "user",
                "raw_message_count": 1,
                "is_initial_assignment": False,
                "pr_attribution": "unassigned",
                "annotator_a": {"label": "good", "rationale": "Changed spec"},
                "annotator_b": {"label": "bad", "rationale": "Agent miss"},
            }
        ]
        summary = agg.compute_human_interventions(episodes)
        self.assertEqual(summary["unassigned_count"], 1)
        self.assertEqual(summary["pr_attributed_count"], 0)
        self.assertEqual(summary["label_breakdown"]["unknown"], 1)
        self.assertEqual(summary["label_breakdown"]["mixed"], 0)
        self.assertEqual(summary["label_breakdown"]["good"], 0)
        self.assertEqual(summary["label_breakdown"]["bad"], 0)

    def test_post_merge_intervention_counted_not_hidden(self):
        """Corrections occurring after merge are tracked as post-merge, never hidden."""
        agg = MetricsAggregator()
        episodes = [
            {
                "episode_id": "ep-post-merge",
                "is_bot": False,
                "actor_status": "human",
                "origin": "user",
                "raw_message_count": 1,
                "is_initial_assignment": False,
                "is_post_merge": True,
                "label": "bad",
                "pr_attribution": "example-org/repo-alpha#1",
            }
        ]
        summary = agg.compute_human_interventions(episodes)
        self.assertEqual(summary["post_merge_count"], 1)
        self.assertEqual(summary["qualifying_episodes"], 1)

    def test_retained_telemetry_readback_reconstructs_when_scratch_missing(self):
        """Private retained telemetry store readback reconstructs pilot events when scratch is empty."""
        temp_repo = tempfile.mkdtemp()
        try:
            telem_dir = os.path.join(temp_repo, "dashboards", "prw", "telemetry")
            os.makedirs(telem_dir, exist_ok=True)

            with open(os.path.join(telem_dir, "pilot_events.jsonl"), "w") as f:
                f.write(json.dumps({"pr_number": 1, "span_kind": "observed_active_execution", "duration_sec": 1200}) + "\n")

            with open(os.path.join(telem_dir, "human_episodes.jsonl"), "w") as f:
                f.write(json.dumps({"episode_id": "ep-ret-1", "is_bot": False, "actor_status": "human", "origin": "user", "raw_message_count": 1, "is_initial_assignment": False, "label": "good"}) + "\n")

            with open(os.path.join(telem_dir, "calibration_audit.json"), "w") as f:
                json.dump({"audit_status": "CALIBRATED", "disagreement_rate": 0.05}, f)

            with open(os.path.join(telem_dir, "retention_manifest.json"), "w") as f:
                json.dump({"retention_days": 90, "version": "1.0"}, f)

            collector = Collector(repos=["example-org/repo-alpha"])
            retained = collector.load_retained_telemetry(roadmap_repo=temp_repo)
            self.assertEqual(len(retained["pilot_events"]), 1)
            self.assertEqual(len(retained["human_episodes"]), 1)
            self.assertEqual(retained["calibration_audit"]["audit_status"], "CALIBRATED")
            self.assertEqual(retained["retention_manifest"]["retention_days"], 90)
        finally:
            shutil.rmtree(temp_repo)

    def test_raw_timeline_dict_flattening_and_stage_dwell(self):
        """Dict mapping in raw_timeline.json is flattened, aliases normalized, and stage dwell computed."""
        temp_dir = tempfile.mkdtemp()
        try:
            raw_timeline_dict = {
                "example-org/repo-alpha#10": [
                    {"__typename": "LabeledEvent", "createdAt": "2026-11-05T10:00:00Z", "label": {"name": "stage:1-coding"}},
                    # Legacy stage alias stage:4-ci-undraft -> stage:4-code-review
                    {"__typename": "LabeledEvent", "createdAt": "2026-11-05T12:00:00Z", "label": {"name": "stage:4-ci-undraft"}},
                ]
            }
            with open(os.path.join(temp_dir, "raw_timeline.json"), "w") as f:
                json.dump(raw_timeline_dict, f)

            collector = Collector(repos=["example-org/repo-alpha"])
            data = collector.load_from_cached_scratch(temp_dir)
            events = data["timeline"]
            self.assertEqual(len(events), 2)
            self.assertEqual(events[0]["pr_number"], 10)
            self.assertEqual(events[0]["event"], "labeled")
            self.assertEqual(events[0]["label"], "stage:1-coding")
            self.assertEqual(events[1]["label"], "stage:4-code-review")

            agg = MetricsAggregator()
            prs = [{"repo": "example-org/repo-alpha", "number": 10, "mergedAt": "2026-11-05T14:00:00Z"}]
            dwell = agg.compute_stage_dwell(prs, timeline_events=events)
            coding_dwell = next(d for d in dwell if d["stage"] == "stage:1-coding")
            # 10:00 to 12:00 = 2 hours
            self.assertEqual(coding_dwell["median_h"], 2.0)
            self.assertEqual(coding_dwell["n"], 1)
        finally:
            shutil.rmtree(temp_dir)

    def test_parse_operational_title(self):
        """parse_operational_title distinguishes [status][detail] from legacy stage prefixes."""
        t1 = "[working][fixing review] Correct wiki destination [codex][gpt-6-luna]"
        res1 = parse_operational_title(t1)
        self.assertTrue(res1["is_operational"])
        self.assertEqual(res1["status"], "working")
        self.assertEqual(res1["detail"], "fixing review")
        self.assertIn("Correct wiki destination", res1["substantive_title"])

        t2 = "[waiting][CI] Correct wiki destination [codex][gpt-6-luna]"
        res2 = parse_operational_title(t2)
        self.assertTrue(res2["is_operational"])
        self.assertEqual(res2["status"], "waiting")
        self.assertEqual(res2["detail"], "CI")

        t3 = "[cd] Implement feature [stage:1-coding]"
        res3 = parse_operational_title(t3)
        self.assertFalse(res3["is_operational"])
        self.assertEqual(res3["legacy_stage"], "stage:1-coding")

    def test_render_sections_4b_and_5b(self):
        """DashboardRenderer renders sections 4b and 5b with explicit non-waste disclaimers."""
        renderer = DashboardRenderer()
        payload = {
            "status": "FRESH",
            "time_semantics_pilot": [
                {
                    "pr_url": "https://github.com/example-org/repo-alpha/pull/1",
                    "pr_elapsed_sec": 7200,
                    "task_elapsed_sec": 3600,
                    "closure_sprint_to_merge_sec": 600,
                    "observed_operation_elapsed_sec": 1800,
                    "observed_active_wall_sec": 1500,
                    "agent_effort_sec": 2400,
                    "explicit_waiting_sec": 900,
                    "avoidable_unattended_sec": None,
                }
            ],
            "human_interventions": {
                "raw_human_messages": 5,
                "qualifying_episodes": 2,
                "label_breakdown": {"good": 1, "bad": 1, "mixed": 0, "unknown": 0},
                "pr_attributed_count": 2,
                "unassigned_count": 0,
                "post_merge_count": 0,
                "channel_coverage": {"dot_history": "UNTESTED_ADAPTER_PENDING"},
                "retention_status": "OK",
            }
        }
        md = renderer.render(payload)
        self.assertIn("## 4b. Time Semantics & Effort Breakdown (Pilot Cohort)", md)
        self.assertIn("Residual elapsed minus observed active is NOT wasted time", md)
        self.assertIn("## 5b. Human Interventions, Episode Calibration & Retention", md)
        self.assertIn("UNTESTED_ADAPTER_PENDING", md)

    def test_persisted_eligible_intervals_roundtrip_state_dir(self):
        """Saving PRs with eligible_intervals as ISO string pairs roundtrips via state_dir without TypeError."""
        temp_dir = tempfile.mkdtemp()
        try:
            # Seed state_dir with a PR that has string-based eligible_intervals
            pr = {
                "number": 42,
                "repo": "example-org/repo-alpha",
                "state": "OPEN",
                "createdAt": "2026-11-05T10:00:00Z",
                "has_continuous_observation": True,
                "telemetry_coverage": 1.0,
                "eligible_intervals": [
                    ["2026-11-05T10:00:00Z", "2026-11-05T11:00:00Z"],
                    {"start_at": "2026-11-05T11:30:00Z", "end_at": "2026-11-05T12:00:00Z"},
                ],
            }
            collector = Collector(repos=["example-org/repo-alpha"])
            # Save into temp_dir via collect_all with a dummy fetch_page_fn returning this pr
            collector.collect_all(
                state_dir=temp_dir,
                fetch_page_fn=lambda r, p, pp: [pr] if p == 1 else [],
            )

            # Reload via offline mode
            collector2 = Collector(repos=["example-org/repo-alpha"])
            reloaded = collector2.collect_all(input_dir=temp_dir, offline=True)
            self.assertEqual(len(reloaded["prs"]), 1)

            # Aggregate dataset: compute_eligible_unattended_duration runs compute_disjoint_interval_union
            agg = MetricsAggregator()
            summary = agg.aggregate_full_dataset(reloaded["prs"], sources=reloaded["sources"])
            self.assertEqual(len(summary["open_prs_known_idle"]), 1)
            # 1 hour (3600) + 30 min (1800) = 5400s
            self.assertEqual(summary["open_prs_known_idle"][0]["eligible_unattended_duration_sec"], 5400.0)
        finally:
            shutil.rmtree(temp_dir)

    def test_publisher_rejects_public_repository(self):
        """Publisher rejects publication to public repositories with PUBLIC_REPO_REJECTED."""
        temp_dir = tempfile.mkdtemp()
        try:
            publisher = Publisher(repo_path=temp_dir)
            res = publisher.publish(
                markdown_text="# PRW Dashboard",
                verify_private_fn=lambda repo: False,
            )
            self.assertEqual(res["action"], "PUBLIC_REPO_REJECTED")
            self.assertFalse(res["committed"])
            self.assertIn("Destination repository is public", res["reason"])
        finally:
            shutil.rmtree(temp_dir)

    def test_stale_status_derived_from_old_source_cutoff(self):
        """Passing sources with old cutoffs (>4.5h) derives STALE status and renders in Markdown."""
        now = datetime.now(timezone.utc)
        old_cutoff = now - timedelta(hours=6)
        sources = {
            "example-org/repo-alpha": {
                "status": "COMPLETE",
                "count": 5,
                "cutoff": format_iso_utc(old_cutoff),
            }
        }
        prs = [
            {
                "number": 1,
                "repo": "example-org/repo-alpha",
                "state": "MERGED",
                "createdAt": format_iso_utc(old_cutoff - timedelta(hours=10)),
                "mergedAt": format_iso_utc(old_cutoff - timedelta(hours=2)),
            }
        ]
        agg = MetricsAggregator(cutoff_dt=now)
        # Note: we do NOT pass status="STALE" into aggregate_full_dataset
        summary = agg.aggregate_full_dataset(prs, sources=sources, now_dt=now, stale_threshold_hours=4.5)
        self.assertEqual(summary["status"], "STALE")

        renderer = DashboardRenderer()
        md = renderer.render(summary)
        self.assertIn("- **Status**: **STALE**", md)

    def test_raw_pilot_events_aggregation_and_parallel_overlap(self):
        """Passing raw pilot_events.jsonl records into aggregate_full_dataset groups by PR and computes disjoint active wall vs effort sum."""
        agg = MetricsAggregator(cutoff_dt=datetime(2026, 11, 7, tzinfo=timezone.utc))
        raw_events = [
            # PR 740 events
            {
                "event_id": "evt_pr740_accepted",
                "repo": "example-org/repo-alpha",
                "pr_number": 740,
                "event_type": "task_accepted",
                "occurred_at": "2026-11-05T10:00:00Z",
            },
            {
                "event_id": "evt_pr740_r1_codex_span",
                "repo": "example-org/repo-alpha",
                "pr_number": 740,
                "span_kind": "observed_active_execution",
                "occurred_at": "2026-11-05T10:30:00Z",
                "duration_sec": 898.054,
            },
            {
                "event_id": "evt_pr740_r1_hermes_span",
                "repo": "example-org/repo-alpha",
                "pr_number": 740,
                "span_kind": "observed_active_execution",
                "occurred_at": "2026-11-05T10:30:00Z",
                "duration_sec": 898.054,
            },
            {
                "event_id": "evt_pr740_merged",
                "repo": "example-org/repo-alpha",
                "pr_number": 740,
                "event_type": "merged",
                "occurred_at": "2026-11-05T12:00:00Z",
            },
            # PR 741 events
            {
                "event_id": "evt_pr741_accepted",
                "repo": "example-org/repo-alpha",
                "pr_number": 741,
                "event_type": "task_accepted",
                "occurred_at": "2026-11-05T11:00:00Z",
            },
            {
                "event_id": "evt_pr741_span",
                "repo": "example-org/repo-alpha",
                "pr_number": 741,
                "span_kind": "observed_active_execution",
                "occurred_at": "2026-11-05T11:15:00Z",
                "duration_sec": 300.0,
            },
            {
                "event_id": "evt_pr741_merged",
                "repo": "example-org/repo-alpha",
                "pr_number": 741,
                "event_type": "merged",
                "occurred_at": "2026-11-05T11:45:00Z",
            },
        ]
        summary = agg.aggregate_full_dataset(prs=[], time_semantics_pilot=raw_events, now_dt=agg.cutoff_dt)
        pilot_rows = summary["time_semantics_pilot"]
        self.assertEqual(len(pilot_rows), 2)

        # Check PR 740 row
        row740 = next(r for r in pilot_rows if "740" in r["pr_url"])
        self.assertEqual(row740["observed_active_wall_sec"], 898.054)
        self.assertEqual(row740["agent_effort_sec"], 1796.108)
        self.assertLess(row740["observed_active_wall_sec"], row740["agent_effort_sec"])
        # task_elapsed_sec: 10:00 to 12:00 = 7200s
        self.assertEqual(row740["task_elapsed_sec"], 7200.0)

        # Check PR 741 row
        row741 = next(r for r in pilot_rows if "741" in r["pr_url"])
        self.assertEqual(row741["observed_active_wall_sec"], 300.0)
        self.assertEqual(row741["agent_effort_sec"], 300.0)
        # task_elapsed_sec: 11:00 to 11:45 = 2700s
        self.assertEqual(row741["task_elapsed_sec"], 2700.0)


class TestRound2HermesAndCodexReviewFixes(unittest.TestCase):
    """Unit tests for Hermes & Codex Round-2 review findings and parent addenda."""

    def test_extract_github_repo_slug_does_not_strip_trailing_characters(self):
        """Codex P0-1: never strip trailing g/i/t from repo names like testing."""
        self.assertEqual(extract_github_repo_slug("git@github.com:example-org/testing.git"), "example-org/testing")
        self.assertEqual(extract_github_repo_slug("https://github.com/example-org/testing"), "example-org/testing")
        self.assertEqual(extract_github_repo_slug("https://github.com/example-org/target.git"), "example-org/target")
        self.assertEqual(extract_github_repo_slug("https://github.com/example-org/repo-alpha.git"), "example-org/repo-alpha")
        self.assertIsNone(extract_github_repo_slug("/local/filesystem/path"))
        self.assertIsNone(extract_github_repo_slug(""))

    def test_publisher_fails_closed_on_mismatched_fetch_and_push_urls(self):
        """Codex P0-1: mismatched origin.url vs origin.pushurl must fail closed and block publish."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_dir = os.path.join(temp_dir, "repo")
            os.makedirs(repo_dir)
            subprocess.run(["git", "-C", repo_dir, "init"], check=True, capture_output=True)
            subprocess.run(
                ["git", "-C", repo_dir, "remote", "add", "origin", "https://github.com/example-org/private-repo.git"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", repo_dir, "remote", "set-url", "--push", "origin", "https://github.com/example-org/public-repo.git"],
                check=True,
                capture_output=True,
            )
            pub = Publisher(repo_path=repo_dir)
            self.assertFalse(pub._verify_destination_is_private())
            res = pub.publish("# Dashboard Content")
            self.assertEqual(res["action"], "BLOCKED")
            self.assertFalse(res["committed"])

    def test_verify_destination_is_private_fails_closed_on_local_remote(self):
        """Codex P0-1: local filesystem remotes fail closed without verify_private_fn."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_dir = os.path.join(temp_dir, "repo")
            os.makedirs(repo_dir)
            subprocess.run(["git", "-C", repo_dir, "init"], check=True, capture_output=True)
            subprocess.run(
                ["git", "-C", repo_dir, "remote", "add", "origin", "/local/bare/repo.git"],
                check=True,
                capture_output=True,
            )
            pub = Publisher(repo_path=repo_dir)
            self.assertFalse(pub._verify_destination_is_private())
            res = pub.publish("# Dashboard Content")
            self.assertEqual(res["action"], "BLOCKED")

    def test_normalize_pr_record_populates_operational_status_detail_legacy_stage(self):
        """Codex P0-3 & P2-2: operational title and legacy stages populated without losing body."""
        collector = Collector()
        # 1. Operational status
        p1 = {
            "number": 101,
            "title": "[working][lane4] implement live metrics [gemini][flash]",
            "body": "PR description body here",
        }
        n1 = collector.normalize_pr_record(p1, default_repo="example-org/repo-alpha")
        self.assertEqual(n1["operational_status"], "working")
        self.assertEqual(n1["operational_detail"], "lane4")
        self.assertIsNone(n1["legacy_stage"])
        self.assertEqual(n1["body"], "PR description body here")

        # 2. Leading legacy prefix [ci]
        p2 = {"number": 102, "title": "[ci] undraft PR"}
        n2 = collector.normalize_pr_record(p2)
        self.assertEqual(n2["legacy_stage"], "stage:4-ci-undraft")

        # 3. Leading legacy prefix [rv]
        p3 = {"number": 103, "title": "[rv] review changes"}
        n3 = collector.normalize_pr_record(p3)
        self.assertEqual(n3["legacy_stage"], "stage:3-review")

        # 4. Trailing bracket [final approval]
        p4 = {"number": 104, "title": "feat: release new feature [final approval]"}
        n4 = collector.normalize_pr_record(p4)
        self.assertEqual(n4["legacy_stage"], "stage:5-final-approval")

    def test_collect_pr_timeline_live_paginated_and_normalized(self):
        """Codex P0-3: collect_pr_timeline_live normalizes labeled/unlabeled/closed/merged events."""
        collector = Collector()
        mock_timeline = [
            {
                "id": "tl_1",
                "event": "labeled",
                "label": {"name": "stage:2-evidence"},
                "createdAt": "2026-11-05T10:00:00Z",
                "actor": {"login": "test-dev"},
            },
            {
                "id": "tl_2",
                "event": "unlabeled",
                "label": "stage:2-evidence",
                "createdAt": "2026-11-05T10:30:00Z",
                "actor": "test-reviewer",
            },
            {
                "id": "tl_3",
                "event": "merged",
                "createdAt": "2026-11-05T11:00:00Z",
            },
        ]
        evs = collector.collect_pr_timeline_live(
            repo="example-org/repo-alpha",
            pr_number=55,
            fetch_timeline_fn=lambda r, n: mock_timeline,
        )
        self.assertEqual(len(evs), 3)
        self.assertEqual(evs[0]["repo"], "example-org/repo-alpha")
        self.assertEqual(evs[0]["pr_number"], 55)
        self.assertEqual(evs[0]["label"], "stage:2-evidence")
        self.assertEqual(evs[0]["actor"], "test-dev")
        self.assertEqual(evs[2]["event"], "merged")

    def test_attention_tables_default_to_unknown_when_unrecorded_and_render_title_status(self):
        """Codex P0-3: unrecorded fields default to UNKNOWN and title_status renders in 5A/5B."""
        agg = MetricsAggregator(cutoff_dt=datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc))
        open_pr = {
            "number": 10,
            "repo": "example-org/repo-alpha",
            "url": "https://github.com/example-org/repo-alpha/pull/10",
            "headRefOid": "abcd1234ef",
            "state": "OPEN",
            "title": "[waiting][review] await second review",
            "operational_status": "waiting",
            "operational_detail": "review",
            "createdAt": "2026-11-06T10:00:00Z",
            "updatedAt": "2026-11-06T10:00:00Z",
            "labels": [],
        }
        summary = agg.aggregate_full_dataset(prs=[open_pr])
        open_unknown = summary["open_prs_unknown_idle"]
        self.assertEqual(len(open_unknown), 1)
        row = open_unknown[0]
        self.assertEqual(row["title_status"], "[waiting][review]")
        self.assertEqual(row["earliest_unmet_obligation"], "UNKNOWN")

        renderer = DashboardRenderer()
        md = renderer.render(summary)
        self.assertIn("Title Status", md)
        self.assertIn("[waiting][review]", md)

    def test_compute_handoff_breakdown_strict_validation(self):
        """Codex P0-5: validate handoff_records against cohort PRs, deduplicate, reject negative/NaN."""
        agg = MetricsAggregator()
        cohort_prs = [
            {
                "number": 20,
                "repo": "example-org/repo-alpha",
                "headRefOid": "sha20",
                "mergedAt": "2026-11-06T12:00:00Z",
                "labels": ["stage:5-final-approval"],
            }
        ]
        records = [
            # 1. Negative duration -> must be rejected
            {"name": "task_accepted -> merged", "number": 20, "repo": "example-org/repo-alpha", "candidate_sha": "sha20", "duration_sec": -3600.0},
            # 2. NaN duration -> must be rejected
            {"name": "task_accepted -> merged", "number": 20, "repo": "example-org/repo-alpha", "candidate_sha": "sha20", "duration_sec": float("nan")},
            # 3. Foreign non-cohort PR -> must be rejected
            {"name": "task_accepted -> merged", "number": 999, "repo": "example-org/repo-alpha", "candidate_sha": "sha999", "duration_sec": 1000.0},
            # 4. Valid record
            {"name": "task_accepted -> merged", "number": 20, "repo": "example-org/repo-alpha", "candidate_sha": "sha20", "duration_sec": 3600.0, "attempt_number": 1, "source_receipt": "r1"},
            # 5. Duplicate of record 4 -> deduplicated
            {"name": "task_accepted -> merged", "number": 20, "repo": "example-org/repo-alpha", "candidate_sha": "sha20", "duration_sec": 3600.0, "attempt_number": 1, "source_receipt": "r1"},
        ]
        data = agg.compute_handoff_breakdown(cohort_prs, handoff_records=records)
        t_row = next(r for r in data if r["name"] == "task_accepted -> merged")
        self.assertEqual(t_row["observed_n"], 1)
        self.assertEqual(t_row["median_sec"], 3600.0)

    def test_deduplicate_events_and_stage_dwell_prevent_foreign_repo_collision(self):
        """Codex P1-1: stage dwell and event deduplication must not collide across different repos with same PR number."""
        collector = Collector()
        agg = MetricsAggregator()
        ev1 = {"repo": "example-org/repo-alpha", "pr_number": 7, "event": "labeled", "label": "stage:1-coding", "createdAt": "2026-11-05T10:00:00Z"}
        ev2 = {"repo": "example-org/repo-beta", "pr_number": 7, "event": "labeled", "label": "stage:1-coding", "createdAt": "2026-11-05T10:00:00Z"}
        deduped = collector.deduplicate_events([ev1, ev2])
        self.assertEqual(len(deduped), 2)

        # Stage dwell: PR 7 in repo-alpha should not consume timeline events for PR 7 in repo-beta
        pr_alpha = {
            "number": 7,
            "repo": "example-org/repo-alpha",
            "mergedAt": "2026-11-05T12:00:00Z",
            "labels": [],
        }
        dwell = agg.compute_stage_dwell([pr_alpha], timeline_events=[ev2])
        coding_row = next(r for r in dwell if r["stage"] == "stage:1-coding")
        self.assertEqual(coding_row["n"], 0)

    def test_duration_only_events_give_effort_only_wall_time_unknown(self):
        """Codex P1-2: duration-only events without start/end endpoints give effort sum only, wall time UNKNOWN."""
        agg = MetricsAggregator()
        pr = {
            "number": 30,
            "repo": "example-org/repo-alpha",
            "createdAt": "2026-11-05T09:00:00Z",
            "mergedAt": "2026-11-05T12:00:00Z",
        }
        events = [
            {"pr_number": 30, "span_kind": "observed_active_execution", "duration_sec": 3600.0},
            {"pr_number": 30, "span_kind": "observed_active_execution", "duration_sec": 3600.0},
        ]
        metrics = agg.compute_time_semantics(pr, pilot_events=events)
        self.assertEqual(metrics["agent_effort_sec"], 7200.0)
        self.assertIsNone(metrics["observed_active_wall_sec"])

    def test_missing_manifest_or_invalid_cutoff_stamps_stale(self):
        """Codex P1-3: cached scratch lacking valid collection manifest stamps STALE, not COMPLETE/FRESH."""
        with tempfile.TemporaryDirectory() as temp_dir:
            prs = [{"number": 1, "repo": "example-org/repo-alpha", "state": "MERGED"}]
            with open(os.path.join(temp_dir, "enriched_prs.json"), "w") as f:
                json.dump(prs, f)
            collector = Collector()
            loaded = collector.load_from_cached_scratch(temp_dir)
            self.assertEqual(loaded["sources"]["collection_manifest"]["status"], "STALE")
            self.assertIsNone(loaded["sources"]["collection_manifest"]["cutoff"])

            agg = MetricsAggregator()
            summary = agg.aggregate_full_dataset(prs=loaded["prs"], sources=loaded["sources"])
            self.assertEqual(summary["status"], "STALE")

    def test_redact_sensitive_excerpt_scrubs_secrets_and_bounds_length(self):
        """Parent addendum: redact_sensitive_excerpt scrubs PATs, API keys, Bearer tokens, and OTPs."""
        raw = ("gh" + "p_1234567890abcdef ") + ("github_" + "pat_11AAAAAAA ") + "sk-proj-12345 Bearer mysecrettoken123 verification code: 849201"
        scrubbed = redact_sensitive_excerpt(raw, max_chars=200)
        self.assertNotIn("gh" + "p_", scrubbed)
        self.assertNotIn("github_pat_11AAAAAAA", scrubbed)
        self.assertNotIn("sk-proj-12345", scrubbed)
        self.assertNotIn("mysecrettoken123", scrubbed)
        self.assertNotIn("849201", scrubbed)
        self.assertIn("[REDACTED]", scrubbed)

        long_text = "A" * 500
        bounded = redact_sensitive_excerpt(long_text, max_chars=50)
        self.assertLessEqual(len(bounded), 55)

    def test_redact_labeled_password_values_including_quoted_spaces(self):
        excerpts = (
            "password is EXAMPLE_VALUE",
            "password: EXAMPLE_VALUE",
            "password=EXAMPLE_VALUE",
            'password is "EXAMPLE VALUE"',
            "password: 'EXAMPLE VALUE'",
        )
        for excerpt in excerpts:
            with self.subTest(excerpt=excerpt):
                scrubbed = redact_sensitive_excerpt(excerpt)
                self.assertNotIn("EXAMPLE", scrubbed)
                self.assertIn("[REDACTED]", scrubbed)

    def test_human_interventions_initial_requests_vs_followup_and_dot_page_tail(self):
        """Parent addendum & Codex P1-4: separate initial requests, follow-ups, and dot_page_tail."""
        agg = MetricsAggregator()
        episodes = [
            # 1. Initial task request (counted in raw_human_messages, not qualifying_episodes)
            {
                "episode_id": "ep_1",
                "origin": "user_prompt",
                "is_initial_assignment": True,
                "raw_message_count": 1,
            },
            # 2. Qualifying human follow-up intervention
            {
                "episode_id": "ep_2",
                "origin": "human",
                "is_initial_assignment": False,
                "label": "good",
                "raw_message_count": 2,
            },
            # 3. Unverified origin (excluded)
            {
                "episode_id": "ep_3",
                "origin": "unknown",
                "raw_message_count": 1,
            },
            # 4. Dot page-tail lacking message_ids / timestamps
            {
                "episode_id": "ep_4",
                "origin": "dot_page_tail",
                "raw_message_count": 1,
            },
        ]
        res = agg.compute_human_interventions(episodes)
        self.assertEqual(res["raw_human_messages"], 3)  # 1 initial + 2 follow-up
        self.assertEqual(res["initial_task_requests"], 1)
        self.assertEqual(res["qualifying_episodes"], 1)
        self.assertEqual(res["unverified_origin_excluded"], 1)
        self.assertEqual(res["dot_page_tail_partial_count"], 1)
        self.assertEqual(res["channel_coverage"]["dot_history"], "PARTIAL_PAGE_TAIL_NO_MESSAGE_IDS_OR_TIMESTAMPS")
        self.assertEqual(res["retention_status"], "UNVERIFIED")

    def test_main_cli_publish_without_roadmap_repo_exits_nonzero(self):
        """Hermes P0-3: CLI with --publish without --roadmap-repo exits 1."""
        cmd = [
            "python3",
            "scripts/prw_metrics.py",
            "--publish",
        ]
        env = os.environ.copy()
        env.pop("PRW_METRICS_ROADMAP_REPO", None)
        env.pop("PRW_METRICS_PUBLISH", None)
        proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("--roadmap-repo", proc.stderr)


class TestPublicationPrivacyAndRetainedTelemetry(unittest.TestCase):
    """PR #742 round-3 B1/B2/B5/B7: push-destination gate, URL parsing, retained layout, publication schema."""

    CREDENTIAL = "Bearer " + "synthetic-credential-" + "0123456789"

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.temp_dir, ignore_errors=True)

    def _git(self, repo, *args):
        return subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True, text=True)

    def _repo_with_origin(self, url, pushurls=()):
        repo = os.path.join(self.temp_dir, "gate-repo")
        shutil.rmtree(repo, ignore_errors=True)
        os.makedirs(repo)
        subprocess.run(["git", "init", "-q", repo], check=True, capture_output=True)
        self._git(repo, "remote", "add", "origin", url)
        for i, pushurl in enumerate(pushurls):
            self._git(repo, "remote", "set-url", "--add" if i else "--push", *(["--push"] if i else []), "origin", pushurl)
        return repo

    def _gate(self, repo, private_slugs=("example-org/private-repo",)):
        """Run the real gate with real git; only the `gh repo view` privacy response is stubbed."""
        real_run = subprocess.run
        gh_calls = []

        def fake_run(cmd, *args, **kwargs):
            if cmd and cmd[0] == "gh":
                gh_calls.append(cmd[3])
                is_private = cmd[3] in private_slugs
                body = {"isPrivate": is_private, "visibility": "PRIVATE" if is_private else "PUBLIC"}
                return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(body), stderr="")
            return real_run(cmd, *args, **kwargs)

        with mock.patch("scripts.prw_metrics.subprocess.run", side_effect=fake_run):
            return Publisher(repo_path=repo)._verify_destination_is_private(), gh_calls

    # B1
    def test_b1_second_public_pushurl_blocks_gate(self):
        repo = self._repo_with_origin(
            "https://github.com/example-org/private-repo.git",
            pushurls=(
                "https://github.com/example-org/private-repo.git",
                "https://github.com/example-org/public-repo.git",
            ),
        )
        listed = self._git(repo, "remote", "get-url", "--push", "--all", "origin").stdout.split()
        self.assertEqual(len(listed), 2)
        ok, _ = self._gate(repo)
        self.assertFalse(ok)

    def test_b1_single_private_destination_still_passes(self):
        repo = self._repo_with_origin("https://github.com/example-org/private-repo.git")
        ok, gh_calls = self._gate(repo)
        self.assertTrue(ok)
        self.assertEqual(gh_calls, ["example-org/private-repo"])

    # B2
    def test_b2_adversarial_urls_do_not_parse_as_github_slug(self):
        for url in (
            "file:///var/tmp/github.com/example-org/private-repo.git",
            "https://example.invalid/github.com/example-org/private-repo.git",
            "https://github.com.example.invalid/example-org/private-repo.git",
            "https://example.invalid:443/x/github.com:example-org/private-repo.git",
            "ssh://git@example.invalid/github.com/example-org/private-repo.git",
            "https://github.com/example-org",
            "https://github.com/example-org/private-repo/extra",
            "https://github.com/../private-repo",
            "http://github.com/example-org/private-repo.git",
        ):
            self.assertIsNone(extract_github_repo_slug(url), url)
        self.assertEqual(
            extract_github_repo_slug("ssh://git@github.com/example-org/private-repo.git"),
            "example-org/private-repo",
        )

    def test_b2_gate_rejects_file_and_foreign_remotes_without_asking_gh(self):
        for url in (
            "file:///var/tmp/github.com/example-org/private-repo.git",
            "https://example.invalid/github.com/example-org/private-repo.git",
        ):
            repo = self._repo_with_origin(url)
            ok, gh_calls = self._gate(repo)
            self.assertFalse(ok, url)
            self.assertEqual(gh_calls, [], url)

    # B5
    def _write_bundle(self, roadmap, slug, events, episodes):
        files = Publisher(repo_path=roadmap).write_telemetry_bundle(
            {"w2_bounds": ["2026-11-01T00:00:00Z", "2026-11-08T00:00:00Z"]},
            pilot_events=events,
            human_episodes=episodes,
            window_slug=slug,
        )
        for relpath, content in files.items():
            path = os.path.join(roadmap, relpath)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
        return files

    def test_b5_publisher_output_round_trips_through_collector(self):
        roadmap = os.path.join(self.temp_dir, "roadmap")
        ev1 = {"event_type": "task_accepted", "repo": "example-org/repo-alpha", "pr_number": 1, "occurred_at": "2026-11-01T01:00:00Z"}
        ev2 = {"event_type": "merged", "repo": "example-org/repo-alpha", "pr_number": 2, "occurred_at": "2026-11-02T01:00:00Z"}
        ep = {"episode_id": "ep-1", "origin": "user", "is_bot": False, "raw_message_count": 1, "label": "good"}
        self._write_bundle(roadmap, "20261101", [ev1], [ep])
        self._write_bundle(roadmap, "20261102", [ev1, ev2], [ep])

        collected = Collector(repos=[], cutoff_dt=parse_iso_utc("2026-11-08T00:00:00Z")).collect_all(
            roadmap_repo=roadmap, offline=True
        )
        self.assertCountEqual(collected["pilot_events"], [ev1, ev2])
        self.assertEqual(len(collected["human_episodes"]), 1)
        self.assertEqual(collected["human_episodes"][0]["episode_id"], "ep-1")
        self.assertIn("version", collected["retention_manifest"])

    def test_b5_root_manifest_does_not_mask_later_telemetry_sources(self):
        roadmap = os.path.join(self.temp_dir, "roadmap")
        input_dir = os.path.join(self.temp_dir, "input")
        ev_pub = {"event_type": "merged", "repo": "example-org/repo-alpha", "pr_number": 1, "occurred_at": "2026-11-02T01:00:00Z"}
        ev_local = {"event_type": "merged", "repo": "example-org/repo-alpha", "pr_number": 2, "occurred_at": "2026-11-03T01:00:00Z"}
        self._write_bundle(roadmap, "20261101", [ev_pub], None)
        os.makedirs(os.path.join(input_dir, "telemetry"))
        with open(os.path.join(input_dir, "telemetry", "pilot_events.jsonl"), "w") as f:
            f.write(json.dumps(ev_local) + "\n")

        collected = Collector(repos=[], cutoff_dt=parse_iso_utc("2026-11-08T00:00:00Z")).collect_all(
            roadmap_repo=roadmap, input_dir=input_dir, offline=True
        )
        self.assertCountEqual(collected["pilot_events"], [ev_pub, ev_local])

    def test_b5_window_slug_cannot_escape_telemetry_dir(self):
        with self.assertRaises(ValueError):
            Publisher(repo_path=self.temp_dir).write_telemetry_bundle({"a": 1}, window_slug="../../escape")

    # B7
    def test_b7_arbitrary_secret_bearing_fields_never_reach_bundle(self):
        cred = self.CREDENTIAL
        events = [{
            "event_type": "task_accepted", "repo": "example-org/repo-alpha", "pr_number": 1,
            "occurred_at": "2026-11-01T01:00:00Z", "message": cred, "pilot_text": cred, "nested": {"x": cred},
        }]
        episodes = [{
            "episode_id": "ep-1", "origin": "user", "is_bot": False, "raw_message_count": 1, "label": "good",
            "full_message": cred, "raw_transcript": cred, "excerpt": cred,
            "annotator_a": {"label": "good", "rationale": cred}, "annotator_b": {"label": "good", "rationale": cred},
        }]
        files = Publisher(repo_path=self.temp_dir).write_telemetry_bundle(
            {"headline": cred, "rows": [cred]}, pilot_events=events, human_episodes=episodes, window_slug="20261101"
        )
        for relpath, content in files.items():
            self.assertNotIn("synthetic-credential", content, relpath)
        persisted = json.loads(files["dashboards/prw/telemetry/20261101/human_episodes.jsonl"].splitlines()[0])
        self.assertEqual(persisted["annotator_a"], {"label": "good"})
        self.assertNotIn("full_message", persisted)
        self.assertNotIn("excerpt", persisted)

    def test_b7_credential_in_allowlisted_field_is_redacted(self):
        files = Publisher(repo_path=self.temp_dir).write_telemetry_bundle(
            None, pilot_events=[{"event_type": self.CREDENTIAL, "pr_number": 1}], window_slug="20261101"
        )
        content = files["dashboards/prw/telemetry/20261101/pilot_events.jsonl"]
        self.assertNotIn("synthetic-credential", content)
        self.assertIn("[REDACTED]", content)

    def test_b7_supplied_telemetry_files_are_resanitized_or_rejected(self):
        clean = Publisher(repo_path=self.temp_dir)
        raw_line = json.dumps({"episode_id": "e", "full_message": self.CREDENTIAL}) + "\n"
        sanitized = sanitize_telemetry_file("dashboards/prw/telemetry/20261101/human_episodes.jsonl", raw_line)
        self.assertNotIn("synthetic-credential", sanitized)
        self.assertNotIn("full_message", sanitized)
        for bad in (
            "dashboards/prw/telemetry/20261101/raw_transcript.txt",
            "dashboards/prw/README.md",
            "dashboards/prw/telemetry/../../../etc/x.json",
        ):
            with self.assertRaises(ValueError, msg=bad):
                sanitize_telemetry_file(bad, "{}")
        self.assertIsNotNone(clean)

    def test_b7_cli_publication_channel_commits_only_sanitized_telemetry(self):
        remote = os.path.join(self.temp_dir, "remote.git")
        local = os.path.join(self.temp_dir, "local")
        subprocess.run(["git", "init", "-q", "--bare", remote], check=True, capture_output=True)
        self._git(remote, "symbolic-ref", "HEAD", "refs/heads/main")
        subprocess.run(["git", "clone", "-q", remote, local], check=True, capture_output=True)
        self._git(local, "checkout", "-B", "main")
        self._git(local, "config", "user.name", "Test User")
        self._git(local, "config", "user.email", "metrics-bot@test.local")
        with open(os.path.join(local, "README.md"), "w") as f:
            f.write("# Root\n")
        self._git(local, "add", "README.md")
        self._git(local, "commit", "-qm", "init")
        self._git(local, "push", "-q", "origin", "main")

        res = publish_dashboard(
            markdown_text="# Dashboard\n",
            repo_path=local,
            verify_private_fn=lambda _: True,
            publish_telemetry=True,
            summary_data={"w2_bounds": ["2026-11-01T00:00:00Z", "x"], "note": self.CREDENTIAL},
            pilot_events=[{"event_type": "merged", "pr_number": 1, "full_message": self.CREDENTIAL}],
            human_episodes=[{"episode_id": "e", "origin": "user", "raw_transcript": self.CREDENTIAL}],
            telemetry_files={"dashboards/prw/telemetry/20261101/pilot_events.jsonl": json.dumps({"full_message": self.CREDENTIAL}) + "\n"},
        )
        self.assertTrue(res["committed"], res)
        tree = self._git(remote, "ls-tree", "-r", "--name-only", "main").stdout.split()
        self.assertTrue(any(p.startswith("dashboards/prw/telemetry/20261101/") for p in tree))
        for path in tree:
            blob = self._git(remote, "show", f"main:{path}").stdout
            self.assertNotIn("synthetic-credential", blob, path)

        blocked = publish_dashboard(
            markdown_text="# Dashboard 2\n",
            repo_path=local,
            verify_private_fn=lambda _: True,
            telemetry_files={"dashboards/prw/telemetry/20261101/raw.txt": self.CREDENTIAL},
        )
        self.assertEqual(blocked["action"], "BLOCKED")
        self.assertFalse(blocked["committed"])


class TestRound4RedactionAndWorkerIdentity(unittest.TestCase):
    """PR #742 Codex P0-1 (rendered/committed redaction) and P0-3 (worker identity across retention)."""

    CREDENTIAL = "Bearer " + "synthetic-credential-" + "0123456789"
    CUTOFF = "2026-11-08T00:00:00Z"

    def test_p0_1_rendered_dashboard_redacts_title_detail_and_source_error(self):
        agg = MetricsAggregator(cutoff_dt=parse_iso_utc(self.CUTOFF))
        pr = {
            "repo": "example-org/repo-alpha", "number": 1, "state": "OPEN",
            "title": "[working][detail " + self.CREDENTIAL + "] subject",
            "createdAt": "2026-11-05T00:00:00Z", "labels": [],
        }
        data = agg.aggregate_full_dataset(
            prs=[pr], sources={"example-org/repo-alpha": {"status": "FAILED", "error": "boom " + self.CREDENTIAL}}
        )
        md = DashboardRenderer().render(data)
        self.assertNotIn("synthetic-credential", md)
        self.assertNotIn("boom", md)

    def test_p0_1_redactor_leaves_hyphenated_words_alone(self):
        text = "task-level risk-based disk-usage"
        self.assertEqual(redact_sensitive_excerpt(text), text)
        self.assertNotIn("abc123", redact_sensitive_excerpt("key sk-abc123 here"))

    def test_p0_1_publish_redacts_markdown_in_committed_blob(self):
        with tempfile.TemporaryDirectory() as tmp:
            remote, local = os.path.join(tmp, "remote.git"), os.path.join(tmp, "local")
            subprocess.run(["git", "init", "-q", "--bare", remote], check=True, capture_output=True)
            subprocess.run(["git", "-C", remote, "symbolic-ref", "HEAD", "refs/heads/main"], check=True)
            subprocess.run(["git", "clone", "-q", remote, local], check=True, capture_output=True)
            for args in (["checkout", "-B", "main"], ["config", "user.name", "T"], ["config", "user.email", "t@test.local"]):
                subprocess.run(["git", "-C", local, *args], check=True, capture_output=True)
            with open(os.path.join(local, "README.md"), "w") as f:
                f.write("# Root\n")
            for args in (["add", "README.md"], ["commit", "-qm", "init"], ["push", "-q", "origin", "main"]):
                subprocess.run(["git", "-C", local, *args], check=True, capture_output=True)

            res = publish_dashboard(
                markdown_text="# Dashboard\nerror " + self.CREDENTIAL + "\n",
                repo_path=local,
                verify_private_fn=lambda _: True,
            )
            self.assertTrue(res["committed"], res)
            blob = subprocess.run(
                ["git", "-C", remote, "show", "main:dashboards/prw/README.md"],
                check=True, capture_output=True, text=True,
            ).stdout
            self.assertNotIn("synthetic-credential", blob)

    def test_p0_3_distinct_workers_with_identical_spans_survive_round_trip(self):
        events = [
            {
                "event_id": "ev-%d" % i, "agent_id": "agent-%d" % i, "repo": "example-org/repo-alpha",
                "pr_number": 1, "span_kind": "observed_active_execution",
                "start_at": "2026-11-06T00:00:00Z", "end_at": "2026-11-06T01:00:00Z",
            }
            for i in (1, 2)
        ]
        # A genuine duplicate observation of worker 1 must still collapse.
        events.append(dict(events[0]))
        with tempfile.TemporaryDirectory() as roadmap:
            files = Publisher(repo_path=roadmap).write_telemetry_bundle(
                {"a": 1}, pilot_events=events, window_slug="20261106"
            )
            for relpath, content in files.items():
                path = os.path.join(roadmap, relpath)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
            collected = Collector(repos=[], cutoff_dt=parse_iso_utc(self.CUTOFF)).collect_all(
                roadmap_repo=roadmap, offline=True
            )
        self.assertEqual(len(collected["pilot_events"]), 2)
        agg = MetricsAggregator(cutoff_dt=parse_iso_utc(self.CUTOFF))
        ts = agg.compute_time_semantics(
            {"repo": "example-org/repo-alpha", "number": 1,
             "createdAt": "2026-11-05T00:00:00Z", "mergedAt": "2026-11-07T00:00:00Z"},
            pilot_events=collected["pilot_events"],
        )
        self.assertEqual(ts["agent_effort_sec"], 7200.0)

    def test_p0_3_worker_identity_fields_are_redacted_not_dropped(self):
        files = Publisher(repo_path=".").write_telemetry_bundle(
            None, pilot_events=[{"agent_id": TestRound4RedactionAndWorkerIdentity.CREDENTIAL, "pr_number": 1}],
            window_slug="20261106",
        )
        content = files["dashboards/prw/telemetry/20261106/pilot_events.jsonl"]
        self.assertNotIn("synthetic-credential", content)
        self.assertIn("agent_id", content)


class TestRetainedBundleRebuildsAudit(unittest.TestCase):
    """PR #742 Codex round-3 P0 4: the published bundle alone must rebuild repository/stage/handoff tables."""

    CUTOFF = "2026-11-08T00:00:00Z"
    REPO = "example-org/repo-alpha"
    CREDENTIAL = "Bearer " + "synthetic-credential-" + "0123456789"

    def _seed_scratch(self, scratch):
        prs = [
            {
                "number": 1, "repo": self.REPO, "state": "MERGED", "title": "[ready][done] Alpha change",
                "createdAt": "2026-11-02T00:00:00Z", "mergedAt": "2026-11-04T00:00:00Z",
                "updatedAt": "2026-11-04T00:00:00Z", "additions": 10, "deletions": 2, "changedFiles": 3,
                "headRefOid": "aaa1111", "labels": ["stage:5-final-approval"],
                "body": "raw private body " + self.CREDENTIAL,
                "evidence_ready_at": "2026-11-02T10:00:00Z",
                "review_requested_at": "2026-11-02T11:00:00Z",
                "actual_review_started_at": "2026-11-02T12:30:00Z",
                "initial_task_accepted_at": "2026-11-02T00:00:00Z",
                "stage_transitions": [
                    {"stage": "stage:1-coding", "entered_at": "2026-11-02T00:00:00Z", "exited_at": "2026-11-02T06:00:00Z", "note": self.CREDENTIAL},
                    {"stage": "stage:2-evidence", "entered_at": "2026-11-02T06:00:00Z", "exited_at": "2026-11-02T10:00:00Z"},
                ],
            },
            {
                "number": 2, "repo": self.REPO, "state": "OPEN", "title": "[working][fixing] Beta change",
                "createdAt": "2026-11-06T00:00:00Z", "updatedAt": "2026-11-07T00:00:00Z",
                "has_continuous_observation": True, "telemetry_coverage": 1.0,
                "eligible_intervals": [["2026-11-07T01:00:00Z", "2026-11-07T04:00:00Z"]],
                "labels": ["stage:1-coding"], "headRefOid": "bbb2222",
            },
        ]
        timeline = {
            self.REPO + "#1": [
                {"__typename": "LabeledEvent", "createdAt": "2026-11-02T00:00:00Z", "label": {"name": "stage:1-coding"}},
                {"__typename": "LabeledEvent", "createdAt": "2026-11-03T00:00:00Z", "label": {"name": "stage:3-review"}},
            ]
        }
        handoffs = [
            {"repo": self.REPO, "pr_number": 1, "attempt": 1, "candidate_sha": "aaa1111",
             "start_at": "2026-11-02T11:00:00Z", "end_at": "2026-11-02T12:30:00Z", "receipt_id": "r-1",
             "reviewer_notes": self.CREDENTIAL},
        ]
        os.makedirs(scratch)
        for name, payload in (
            ("enriched_prs.json", prs), ("raw_timeline.json", timeline),
            ("actionable_handoff_metrics.json", handoffs),
            ("source_manifest.json", {self.REPO: {"status": "COMPLETE", "count": 2, "cutoff": self.CUTOFF}}),
        ):
            with open(os.path.join(scratch, name), "w", encoding="utf-8") as f:
                json.dump(payload, f)

    def _summarize(self, collected):
        cutoff = parse_iso_utc(self.CUTOFF)
        summary = MetricsAggregator(cutoff_dt=cutoff).aggregate_full_dataset(
            prs=collected["prs"], timeline_events=collected["timeline"], sources=collected["sources"],
            handoff_records=collected["handoff_records"], now_dt=cutoff,
        )
        summary.pop("generated_at", None)
        return summary

    def test_published_bundle_alone_reproduces_aggregates(self):
        with tempfile.TemporaryDirectory() as tmp:
            scratch, roadmap = os.path.join(tmp, "scratch"), os.path.join(tmp, "roadmap")
            self._seed_scratch(scratch)
            collector = Collector(repos=[self.REPO], cutoff_dt=parse_iso_utc(self.CUTOFF))
            before = collector.collect_all(input_dir=scratch, offline=True)
            self.assertEqual(len(before["prs"]), 2)
            summary_before = self._summarize(before)

            files = Publisher(repo_path=roadmap).write_telemetry_bundle(
                summary_before, prs=before["prs"], timeline=before["timeline"],
                handoff_records=before["handoff_records"], sources=before["sources"],
                window_slug="20261101",
            )
            for relpath, content in files.items():
                self.assertNotIn("synthetic-credential", content, relpath)
                self.assertNotIn("raw private body", content, relpath)
                path = os.path.join(roadmap, relpath)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)

            shutil.rmtree(scratch)
            after = Collector(repos=[self.REPO], cutoff_dt=parse_iso_utc(self.CUTOFF)).collect_all(
                roadmap_repo=roadmap, offline=True
            )
            self.assertEqual(len(after["prs"]), 2)
            self.assertEqual(self._summarize(after), summary_before)

    def test_retained_collection_files_are_fixed_field(self):
        files = Publisher(repo_path=".").write_telemetry_bundle(
            None,
            prs=[{"number": 1, "repo": self.REPO, "body": self.CREDENTIAL, "extra": self.CREDENTIAL,
                  "stage_transitions": [{"stage": "s", "note": self.CREDENTIAL}]}],
            timeline=[{"id": "1", "event": "labeled", "raw": self.CREDENTIAL}],
            handoff_records=[{"receipt_id": "r", "notes": self.CREDENTIAL}],
            sources={self.REPO: {"status": "FAILED", "error": self.CREDENTIAL, "path": "/private/path"}},
            window_slug="20261101",
        )
        joined = "\n".join(files.values())
        self.assertNotIn("synthetic-credential", joined)
        self.assertNotIn("/private/path", joined)
        for key in ("body", "extra", "note", "raw", "notes", "error"):
            self.assertNotIn('"%s"' % key, joined)


class TestRetentionRoundTripInvariant(unittest.TestCase):
    """PR #742 r4: collect -> publish -> wipe scratch -> rebuild must reproduce the same audit."""

    CUTOFF = "2026-11-08T00:00:00Z"
    REPO_A = "example-org/repo-alpha"
    REPO_B = "example-org/repo-beta"

    def _pr(self, repo, number, state, updated, merged=None, head="aaa1111"):
        return {
            "number": number, "repo": repo, "state": state, "title": "[ready][done] Change %d" % number,
            "createdAt": "2026-11-02T00:00:00Z", "updatedAt": updated, "mergedAt": merged,
            "headRefOid": head, "labels": ["stage:3-review"],
        }

    def _receipt(self, receipts_dir):
        os.makedirs(receipts_dir)
        receipt = {
            "repo": self.REPO_A, "pr_number": 1, "candidate_sha": "aaa1111",
            "timestamps": {"accepted_at": "2026-11-02T00:00:00Z", "merged_at": "2026-11-04T20:00:00Z"},
            "rounds": [{
                "round": 1, "candidate_sha": "aaa1111",
                "review_requested_at": "2026-11-03T10:00:00Z",
                "actual_review_started_at": "2026-11-03T11:00:00Z",
            }],
        }
        with open(os.path.join(receipts_dir, "run.stats.json"), "w", encoding="utf-8") as f:
            json.dump(receipt, f)

    def _collect(self, pages, receipts_dir=None, state_dir=None, fail_repos=(), roadmap=None, offline=False):
        def fetch_page(repo, page, per_page):
            if repo in fail_repos:
                raise RuntimeError("synthetic API outage")
            return pages.get(repo, []) if page == 1 else []

        collector = Collector(repos=[self.REPO_A, self.REPO_B], cutoff_dt=parse_iso_utc(self.CUTOFF))
        return collector.collect_all(
            fetch_page_fn=fetch_page, fetch_timeline_fn=lambda r, n: [], receipts_dir=receipts_dir,
            state_dir=state_dir, roadmap_repo=roadmap, offline=offline,
        )

    def _summarize(self, collected):
        cutoff = parse_iso_utc(self.CUTOFF)
        summary = MetricsAggregator(cutoff_dt=cutoff).aggregate_full_dataset(
            prs=collected["prs"], timeline_events=collected["timeline"], sources=collected["sources"],
            handoff_records=collected["handoff_records"], now_dt=cutoff,
        )
        summary.pop("generated_at", None)
        return summary

    def _write(self, roadmap, files):
        for relpath, content in files.items():
            path = os.path.join(roadmap, relpath)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

    def _publish(self, roadmap, collected, slug):
        self._write(roadmap, Publisher(repo_path=roadmap).write_telemetry_bundle(
            self._summarize(collected), prs=collected["prs"], timeline=collected["timeline"],
            handoff_records=collected["handoff_records"], sources=collected["sources"], window_slug=slug,
        ))

    def test_canonical_receipt_nested_fields_survive_publish_and_reload(self):
        with tempfile.TemporaryDirectory() as tmp:
            receipts, roadmap = os.path.join(tmp, "receipts"), os.path.join(tmp, "roadmap")
            self._receipt(receipts)
            pages = {self.REPO_A: [self._pr(self.REPO_A, 1, "MERGED", "2026-11-04T20:00:00Z", "2026-11-04T20:00:00Z")]}
            before = self._collect(pages, receipts_dir=receipts)
            handoff_before = self._summarize(before)["handoffs"]
            self.assertTrue(any(r.get("observed_n") for r in handoff_before), handoff_before)
            self._publish(roadmap, before, "20261104")
            after = Collector(repos=[self.REPO_A], cutoff_dt=parse_iso_utc(self.CUTOFF)).collect_all(
                roadmap_repo=roadmap, offline=True
            )
            self.assertEqual(self._summarize(after)["handoffs"], handoff_before)

    def test_newer_merged_snapshot_beats_older_open_across_bundles_and_scratch_overrides(self):
        with tempfile.TemporaryDirectory() as tmp:
            roadmap, state = os.path.join(tmp, "roadmap"), os.path.join(tmp, "state")
            open_pages = {self.REPO_A: [self._pr(self.REPO_A, 1, "OPEN", "2026-11-03T00:00:00Z")]}
            merged_pages = {self.REPO_A: [self._pr(self.REPO_A, 1, "MERGED", "2026-11-05T00:00:00Z", "2026-11-05T00:00:00Z")]}
            # Bundle directory order must not decide precedence: try both assignments.
            for open_slug, merged_slug in (("20261101", "20261109"), ("20261109", "20261101")):
                shutil.rmtree(roadmap, ignore_errors=True)
                self._publish(roadmap, self._collect(open_pages), open_slug)
                self._publish(roadmap, self._collect(merged_pages), merged_slug)
                rebuilt = Collector(repos=[self.REPO_A], cutoff_dt=parse_iso_utc(self.CUTOFF)).collect_all(
                    roadmap_repo=roadmap, offline=True
                )
                states = [p["state"] for p in rebuilt["prs"] if p["number"] == 1]
                self.assertEqual(states, ["MERGED"], (open_slug, merged_slug))

            # A fresher scratch snapshot overrides retained; an equal-time one wins the tie.
            os.makedirs(state)
            scratch_pr = self._pr(self.REPO_A, 1, "CLOSED", "2026-11-06T00:00:00Z")
            with open(os.path.join(state, "enriched_prs.json"), "w", encoding="utf-8") as f:
                json.dump([scratch_pr], f)
            with_scratch = Collector(repos=[self.REPO_A], cutoff_dt=parse_iso_utc(self.CUTOFF)).collect_all(
                roadmap_repo=roadmap, state_dir=state, offline=True
            )
            self.assertEqual([p["state"] for p in with_scratch["prs"]], ["CLOSED"])

    def test_full_round_trip_reproduces_summary_and_source_statuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            receipts, roadmap, state = (os.path.join(tmp, n) for n in ("receipts", "roadmap", "state"))
            self._receipt(receipts)
            pages = {
                self.REPO_A: [self._pr(self.REPO_A, 1, "MERGED", "2026-11-04T20:00:00Z", "2026-11-04T20:00:00Z")],
                self.REPO_B: [self._pr(self.REPO_B, 7, "OPEN", "2026-11-07T00:00:00Z", head="bbb2222")],
            }
            self._collect(pages, state_dir=state)  # seed scratch so REPO_B has prior data
            before = self._collect(pages, receipts_dir=receipts, state_dir=state, fail_repos=(self.REPO_B,))
            self.assertEqual(before["sources"][self.REPO_B]["status"], "PARTIAL_FAILURE")
            self._publish(roadmap, before, "20261104")
            shutil.rmtree(state)
            shutil.rmtree(receipts)

            after = Collector(repos=[self.REPO_A, self.REPO_B], cutoff_dt=parse_iso_utc(self.CUTOFF)).collect_all(
                roadmap_repo=roadmap, offline=True
            )
            summary_before, summary_after = self._summarize(before), self._summarize(after)
            for key in set(summary_before) - {"sources"}:
                self.assertEqual(summary_after[key], summary_before[key], key)
            for repo in (self.REPO_A, self.REPO_B):
                self.assertEqual(
                    {k: summary_after["sources"][repo].get(k) for k in ("status", "cutoff")},
                    {k: summary_before["sources"][repo].get(k) for k in ("status", "cutoff")},
                    repo,
                )

    def test_every_publication_sink_is_free_of_error_strings_paths_and_credentials(self):
        cred = "Bearer " + "synthetic-credential-" + "0123456789"
        with tempfile.TemporaryDirectory() as tmp:
            remote, local = os.path.join(tmp, "remote.git"), os.path.join(tmp, "local")
            receipts, state = os.path.join(tmp, "private-receipts-dir"), os.path.join(tmp, "private-state-dir")
            subprocess.run(["git", "init", "-q", "--bare", remote], check=True, capture_output=True)
            subprocess.run(["git", "-C", remote, "symbolic-ref", "HEAD", "refs/heads/main"], check=True)
            subprocess.run(["git", "clone", "-q", remote, local], check=True, capture_output=True)
            for args in (["checkout", "-B", "main"], ["config", "user.name", "T"], ["config", "user.email", "t@test.local"]):
                subprocess.run(["git", "-C", local, *args], check=True, capture_output=True)
            with open(os.path.join(local, "README.md"), "w") as f:
                f.write("# Root\n")
            for args in (["add", "README.md"], ["commit", "-qm", "init"], ["push", "-q", "origin", "main"]):
                subprocess.run(["git", "-C", local, *args], check=True, capture_output=True)

            self._receipt(receipts)
            pages = {
                self.REPO_A: [self._pr(self.REPO_A, 1, "MERGED", "2026-11-04T20:00:00Z", "2026-11-04T20:00:00Z")],
                self.REPO_B: [self._pr(self.REPO_B, 7, "OPEN", "2026-11-07T00:00:00Z", head="bbb2222")],
            }
            pages[self.REPO_A][0]["body"] = "private body text " + cred
            self._collect(pages, state_dir=state)
            collected = self._collect(pages, receipts_dir=receipts, state_dir=state, fail_repos=(self.REPO_B,))
            collected["sources"][self.REPO_B]["error"] = "raw-error-sentinel " + cred
            collected["sources"]["prs"] = {"status": "COMPLETE", "path": "/private/local-path/prs.json"}
            summary = self._summarize(collected)
            res = publish_dashboard(
                markdown_text=DashboardRenderer().render(summary),
                repo_path=local,
                verify_private_fn=lambda _: True,
                publish_telemetry=True,
                summary_data=summary,
                prs=collected["prs"],
                timeline=collected["timeline"],
                handoff_records=collected["handoff_records"],
                sources=collected["sources"],
            )
            self.assertTrue(res["committed"], res)
            tree = subprocess.run(
                ["git", "-C", remote, "ls-tree", "-r", "--name-only", "main"],
                check=True, capture_output=True, text=True,
            ).stdout.split()
            self.assertTrue(any(p.endswith("summary_snapshot.json") for p in tree), tree)
            self.assertTrue(any(p.endswith("retained_handoffs.jsonl") for p in tree), tree)
            for path in tree:
                blob = subprocess.run(
                    ["git", "-C", remote, "show", "main:" + path], check=True, capture_output=True, text=True
                ).stdout
                for sentinel in (
                    "raw-error-sentinel", "synthetic API outage", "/private/local-path", "private-receipts-dir",
                    "private-state-dir", "private body text", "synthetic-credential",
                ):
                    self.assertNotIn(sentinel, blob, (path, sentinel))

    def test_attention_table_is_identical_after_publish_wipe_rebuild(self):
        body = "\n".join([
            "next_action: dispatch review seat 2",
            "owner: lane-b",
            "job_handle: job-4242",
            "wake_condition: CI green on candidate",
            "",
            "| obligation | status | receipt |",
            "|---|---|---|",
            "| Source Review Quorum | PENDING | https://example.org/receipts/742 |",
        ])
        pr = self._pr(self.REPO_A, 9, "OPEN", "2026-11-07T00:00:00Z", head="ccc3333")
        pr.update({"body": body, "has_continuous_observation": True, "telemetry_coverage": 1.0,
                   "eligible_intervals": [["2026-11-07T01:00:00Z", "2026-11-07T04:00:00Z"]],
                   "labels": ["stage:3-review"]})
        with tempfile.TemporaryDirectory() as tmp:
            roadmap = os.path.join(tmp, "roadmap")
            before = self._collect({self.REPO_A: [pr]})
            record = [p for p in before["prs"] if p["number"] == 9][0]
            self.assertEqual(record["job_handle"], "job-4242")
            self._publish(roadmap, before, "20261107")
            after = Collector(repos=[self.REPO_A], cutoff_dt=parse_iso_utc(self.CUTOFF)).collect_all(
                roadmap_repo=roadmap, offline=True
            )

            def attention(collected):
                md = DashboardRenderer().render(self._summarize(collected))
                return md[md.index("## 5. Open PR Attention Table"):]

            table = attention(before)
            self.assertIn("job-4242", table)
            self.assertIn("CI green on candidate", table)
            self.assertIn("https://example.org/receipts/742", table)
            self.assertEqual(attention(after), table)

    def _bare_remote_and_checkout(self, tmp):
        remote, local = os.path.join(tmp, "remote.git"), os.path.join(tmp, "local")
        subprocess.run(["git", "init", "-q", "--bare", remote], check=True, capture_output=True)
        subprocess.run(["git", "-C", remote, "symbolic-ref", "HEAD", "refs/heads/main"], check=True)
        subprocess.run(["git", "clone", "-q", remote, local], check=True, capture_output=True)
        for args in (["checkout", "-B", "main"], ["config", "user.name", "T"], ["config", "user.email", "t@test.local"]):
            subprocess.run(["git", "-C", local, *args], check=True, capture_output=True)
        with open(os.path.join(local, "README.md"), "w") as f:
            f.write("# Root\n")
        for args in (["add", "README.md"], ["commit", "-qm", "init"], ["push", "-q", "origin", "main"]):
            subprocess.run(["git", "-C", local, *args], check=True, capture_output=True)
        return remote, local

    def test_readback_consumes_published_commit_from_unchanged_checkout(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, local = self._bare_remote_and_checkout(tmp)
            receipts, state = os.path.join(tmp, "receipts"), os.path.join(tmp, "state")
            self._receipt(receipts)
            pages = {
                self.REPO_A: [self._pr(self.REPO_A, 1, "MERGED", "2026-11-04T20:00:00Z", "2026-11-04T20:00:00Z")],
                self.REPO_B: [self._pr(self.REPO_B, 7, "OPEN", "2026-11-07T00:00:00Z", head="bbb2222")],
            }
            self._collect(pages, state_dir=state)
            before = self._collect(pages, receipts_dir=receipts, state_dir=state)
            summary_before = self._summarize(before)
            with open(os.path.join(local, "dirty.txt"), "w") as f:
                f.write("unrelated local edit\n")
            res = publish_dashboard(
                markdown_text=DashboardRenderer().render(summary_before),
                repo_path=local,
                verify_private_fn=lambda _: True,
                publish_telemetry=True,
                summary_data=summary_before,
                prs=before["prs"], timeline=before["timeline"],
                handoff_records=before["handoff_records"], sources=before["sources"],
            )
            self.assertTrue(res["committed"], res)
            # The checkout never saw the published files.
            self.assertFalse(os.path.exists(os.path.join(local, "dashboards", "prw", "telemetry")))
            shutil.rmtree(state)
            shutil.rmtree(receipts)

            after = Collector(repos=[self.REPO_A, self.REPO_B], cutoff_dt=parse_iso_utc(self.CUTOFF)).collect_all(
                roadmap_repo=local, offline=True
            )
            summary_after = self._summarize(after)
            for key in set(summary_before) - {"sources"}:
                self.assertEqual(summary_after[key], summary_before[key], key)
            # Unrelated working-tree edits are untouched.
            with open(os.path.join(local, "dirty.txt")) as f:
                self.assertEqual(f.read(), "unrelated local edit\n")
            self.assertFalse(os.path.exists(os.path.join(local, "dashboards", "prw", "telemetry")))

    def test_absolute_paths_in_attention_fields_are_scrubbed_everywhere(self):
        body = "\n".join([
            "next_action: run /home/someone/private-dir/run.sh then ~/secret/notes",
            "owner: /Users/someone/agent",
            "job_handle: /var/tmp/job-4242/handle",
            "wake_condition: see https://example.org/receipts/742 for CI",
        ])
        pr = self._pr(self.REPO_A, 9, "OPEN", "2026-11-07T00:00:00Z", head="ccc3333")
        pr.update({"body": body, "has_continuous_observation": True, "telemetry_coverage": 1.0,
                   "eligible_intervals": [["2026-11-07T01:00:00Z", "2026-11-07T04:00:00Z"]]})
        with tempfile.TemporaryDirectory() as tmp:
            collected = self._collect({self.REPO_A: [pr]})
            summary = self._summarize(collected)
            files = Publisher(repo_path=tmp).write_telemetry_bundle(
                summary, prs=collected["prs"], window_slug="20261107"
            )
            sinks = list(files.values()) + [DashboardRenderer().render(summary)]
            for sink in sinks:
                for fragment in ("/home/someone", "private-dir", "~/secret", "/Users/someone", "/var/tmp/job-4242"):
                    self.assertNotIn(fragment, sink)
            self.assertIn("https://example.org/receipts/742", sinks[-1])
            self.assertIn("[PATH]", sinks[-1])

    def _telemetry_pr(self, head):
        pr = self._pr(self.REPO_A, 5, "OPEN", "2026-11-07T00:00:00Z", head=head)
        pr.update({
            "has_continuous_observation": True, "telemetry_coverage": 1.0,
            "eligible_intervals": [["2026-11-07T01:00:00Z", "2026-11-07T04:00:00Z"]],
            "evidence_ready_at": "2026-11-06T10:00:00Z",
        })
        return pr

    def _live_page(self, head):
        # The GitHub API carries identity/updatedAt/head but none of the recorded telemetry fields.
        return self._pr(self.REPO_A, 5, "OPEN", "2026-11-07T00:00:00Z", head=head)

    def test_live_refresh_same_candidate_preserves_recorded_telemetry(self):
        with tempfile.TemporaryDirectory() as tmp:
            state, roadmap = os.path.join(tmp, "state"), os.path.join(tmp, "roadmap")
            os.makedirs(state)
            with open(os.path.join(state, "enriched_prs.json"), "w", encoding="utf-8") as f:
                json.dump([self._telemetry_pr("ddd4444")], f)
            seeded = Collector(repos=[self.REPO_A], cutoff_dt=parse_iso_utc(self.CUTOFF)).collect_all(
                input_dir=state, offline=True
            )
            self._publish(roadmap, seeded, "20261107")

            for kwargs in ({"state_dir": state}, {"roadmap": roadmap}):
                refreshed = self._collect({self.REPO_A: [self._live_page("ddd4444")]}, **kwargs)
                pr = [p for p in refreshed["prs"] if p["number"] == 5][0]
                self.assertEqual(pr["telemetry_coverage"], 1.0, kwargs)
                self.assertEqual(pr["evidence_ready_at"], "2026-11-06T10:00:00Z", kwargs)
                self.assertTrue(pr["has_continuous_observation"], kwargs)
                self.assertEqual(self._summarize(refreshed)["open_prs_known_idle"][0]["eligible_unattended_duration_sec"], 10800.0)

    def test_live_refresh_changed_candidate_drops_telemetry_as_not_applicable(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = os.path.join(tmp, "state")
            os.makedirs(state)
            with open(os.path.join(state, "enriched_prs.json"), "w", encoding="utf-8") as f:
                json.dump([self._telemetry_pr("ddd4444")], f)
            refreshed = self._collect({self.REPO_A: [self._live_page("eee5555")]}, state_dir=state)
            pr = [p for p in refreshed["prs"] if p["number"] == 5][0]
            self.assertEqual(pr["headRefOid"], "eee5555")
            self.assertEqual(pr["telemetry_coverage"], 0.0)
            self.assertIsNone(pr["evidence_ready_at"])
            self.assertEqual(pr["eligible_intervals"], [])
            self.assertIn("candidate changed", pr["telemetry_applicability"])
            summary = self._summarize(refreshed)
            self.assertEqual(summary["open_prs_known_idle"], [])
            self.assertEqual(len(summary["open_prs_unknown_idle"]), 1)

    def test_unknown_nested_fields_reach_no_committed_blob_or_rendered_markdown(self):
        sentinel = "nested-transcript-sentinel"
        with tempfile.TemporaryDirectory() as tmp:
            remote, local = self._bare_remote_and_checkout(tmp)
            pages = {self.REPO_A: [self._telemetry_pr("fff6666")]}
            pages[self.REPO_A].append(self._pr(self.REPO_A, 1, "MERGED", "2026-11-04T20:00:00Z", "2026-11-04T20:00:00Z"))
            pages[self.REPO_A].append(self._pr(self.REPO_A, 3, "OPEN", "2026-11-07T00:00:00Z", head="ggg7777"))
            collected = self._collect(pages)
            cutoff = parse_iso_utc(self.CUTOFF)
            summary = MetricsAggregator(cutoff_dt=cutoff).aggregate_full_dataset(
                prs=collected["prs"], timeline_events=collected["timeline"], sources=collected["sources"],
                handoff_records=collected["handoff_records"], now_dt=cutoff,
                # Precomputed pilot rows pass through the aggregator unchanged.
                time_semantics_pilot=[{"pr_url": "https://example.org/pull/1", "pr_elapsed_sec": 5.0,
                                       "raw_transcript": sentinel}],
                human_episodes=[{"episode_id": "e", "origin": "user", "raw_message_count": 1, "label": "good"}],
            )
            injected = []

            def inject(container, label):
                container["raw_transcript"] = sentinel + "-" + label
                injected.append(label)

            for section in ("repo_comparison", "stage_dwell", "handoffs", "open_prs_known_idle",
                            "open_prs_unknown_idle", "time_semantics_pilot"):
                self.assertTrue(summary.get(section), section)
                for row in summary[section]:
                    inject(row, section)
            for name, src in summary["sources"].items():
                inject(src, "sources")
            hi = summary["human_interventions"]
            inject(hi, "human_interventions")
            inject(hi["label_breakdown"], "label_breakdown")
            inject(hi["channel_coverage"], "channel_coverage")
            summary["raw_transcript"] = sentinel + "-top"
            self.assertEqual(len(set(injected)), 10)

            res = publish_dashboard(
                markdown_text=DashboardRenderer().render(summary),
                repo_path=local,
                verify_private_fn=lambda _: True,
                publish_telemetry=True,
                summary_data=summary,
                prs=collected["prs"], timeline=collected["timeline"],
                handoff_records=collected["handoff_records"], sources=collected["sources"],
            )
            self.assertTrue(res["committed"], res)
            tree = subprocess.run(
                ["git", "-C", remote, "ls-tree", "-r", "--name-only", "main"],
                check=True, capture_output=True, text=True,
            ).stdout.split()
            snapshot = [p for p in tree if p.endswith("summary_snapshot.json")]
            self.assertEqual(len(snapshot), 1)
            for path in tree:
                blob = subprocess.run(
                    ["git", "-C", remote, "show", "main:" + path], check=True, capture_output=True, text=True
                ).stdout
                self.assertNotIn(sentinel, blob, path)
            kept = json.loads(subprocess.run(
                ["git", "-C", remote, "show", "main:" + snapshot[0]], check=True, capture_output=True, text=True
            ).stdout)
            self.assertTrue(kept["repo_comparison"] and kept["repo_comparison"][0]["repo"])
            self.assertEqual(kept["time_semantics_pilot"][0].get("pr_elapsed_sec"), 5.0)
            self.assertEqual(set(kept["human_interventions"]["label_breakdown"]), {"good", "bad", "mixed", "unknown"})

    def test_summary_schema_covers_every_key_the_aggregator_emits(self):
        collected = self._collect({self.REPO_A: [self._telemetry_pr("fff6666")]})
        summary = self._summarize(collected)
        projected = json.loads(json.dumps(_project_summary(summary)))
        self.assertEqual(set(projected), set(summary))
        for section in ("repo_comparison", "stage_dwell", "handoffs", "open_prs_known_idle", "open_prs_unknown_idle"):
            for original, kept in zip(summary[section], projected[section]):
                self.assertEqual(set(kept), set(original), section)

    def test_rendered_distributions_include_fourteen_day_and_percentile_values(self):
        summary = {
            "status": "FRESH",
            "repo_comparison": [{
                "repo": "example-org/repo-alpha",
                "created": 1, "created_w1": 1, "created_w2": 1,
                "merged_w1": 1, "merged_w2": 1, "closed_unmerged_w1": 0,
                "closed_unmerged_w2": 0, "current_closed_unmerged": 0, "still_open": 0,
                "w1_all_median_hours": 2, "all_median_hours": 3,
                "w1_all_p75_hours": 2, "all_p75_hours": 3,
                "w1_comp_median_hours": 2, "comp_median_hours": 3,
                "w1_comp_p75_hours": 2, "comp_p75_hours": 3,
                "w1_backlog_n": 0, "w1_backlog_median_hours": "UNKNOWN",
                "backlog_n": 0, "backlog_median_hours": "UNKNOWN",
                "d14_all_n": 2, "d14_all_p50_hours": 2, "d14_all_p90_hours": 3,
                "d14_all_p99_hours": 3, "d14_comp_n": 2, "d14_comp_p50_hours": 2,
                "d14_comp_p90_hours": 3, "d14_comp_p99_hours": 3,
                "d14_backlog_n": 0, "d14_backlog_p50_hours": "UNKNOWN",
                "d14_backlog_p90_hours": "UNKNOWN", "d14_backlog_p99_hours": "UNKNOWN",
            }],
            "stage_dwell": [{
                "stage": "stage:1-coding", "median_h": 2, "p75_h": 3,
                "p50_h": 2, "p90_h": 3, "p99_h": 3,
                "sample_n": 2, "n": 2, "total_n": 2, "conflicts": 0,
            }],
            "handoffs": [{
                "name": "task_accepted -> merged", "observed_n": 1, "sample_n": 1,
                "total_n": 2, "median_sec": 60, "p75_sec": 60, "p50_sec": 60,
                "p90_sec": 60, "p99_sec": 60, "status": "PARTIAL",
            }],
        }
        rendered = DashboardRenderer().render(summary)
        self.assertIn("14-day Creation-to-Merge Distribution", rendered)
        self.assertIn("n=2; p50=2h, p90=3h, p99=3h", rendered)
        self.assertIn(
            "| `stage:1-coding` | 2; 2 / 2 | 2h | 3h | 2h | 3h | 3h | 0 |",
            rendered,
        )
        self.assertIn("1m 00s", rendered)

    def test_manifest_and_calibration_files_are_fixed_field_in_every_path(self):
        sentinel = "private-message-sentinel"
        manifest = json.dumps({"version": "1.0", "retention_days": 90, "raw_transcript": sentinel,
                               "nested": {"raw_transcript": sentinel}})
        calibration = json.dumps({"audit_status": "CALIBRATED", "disagreement_rate": 0.05,
                                  "raw_transcript": sentinel, "annotations": [{"text": sentinel}]})
        with tempfile.TemporaryDirectory() as tmp:
            remote, local = self._bare_remote_and_checkout(tmp)
            base = "dashboards/prw/telemetry/20261107/"
            res = publish_dashboard(
                markdown_text="# Dashboard\n",
                repo_path=local,
                verify_private_fn=lambda _: True,
                telemetry_files={
                    "dashboards/prw/telemetry/retention_manifest.json": manifest,
                    base + "calibration_audit.json": calibration,
                },
            )
            self.assertTrue(res["committed"], res)
            tree = subprocess.run(
                ["git", "-C", remote, "ls-tree", "-r", "--name-only", "main"],
                check=True, capture_output=True, text=True,
            ).stdout.split()
            for path in tree:
                blob = subprocess.run(
                    ["git", "-C", remote, "show", "main:" + path], check=True, capture_output=True, text=True
                ).stdout
                self.assertNotIn(sentinel, blob, path)
            kept = json.loads(subprocess.run(
                ["git", "-C", remote, "show", "main:" + base + "calibration_audit.json"],
                check=True, capture_output=True, text=True,
            ).stdout)
            self.assertEqual(kept, {"audit_status": "CALIBRATED", "disagreement_rate": 0.05})

    def test_loader_projects_manifest_and_calibration_on_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "retention_manifest.json"), "w") as f:
                json.dump({"version": "1.0", "raw_transcript": "private-message-sentinel"}, f)
            with open(os.path.join(tmp, "calibration_audit.json"), "w") as f:
                json.dump({"audit_status": "OK", "raw_transcript": "private-message-sentinel"}, f)
            retained = Collector(repos=[]).load_retained_telemetry(telemetry_dir=tmp)
            self.assertEqual(retained["retention_manifest"], {"version": "1.0"})
            self.assertEqual(retained["calibration_audit"], {"audit_status": "OK"})

    def _two_attempt_scratch(self, scratch):
        pr = self._pr(self.REPO_A, 1, "MERGED", "2026-11-04T20:00:00Z", "2026-11-04T20:00:00Z", head="aaa1111")
        pr.update({
            "attempt": 2,
            "evidence_ready_at": "2026-11-02T10:00:00Z",
            "review_requested_at": "2026-11-02T11:00:00Z",
            "actual_review_started_at": "2026-11-02T12:30:00Z",
            "review_returned_at": "2026-11-02T14:00:00Z",
            "next_action_started_at": "2026-11-02T15:00:00Z",
            "initial_task_accepted_at": "2026-11-02T00:00:00Z",
            "closure_sprint_accepted_at": "2026-11-03T00:00:00Z",
            "has_continuous_observation": True, "telemetry_coverage": 1.0,
            "eligible_intervals": [["2026-11-03T01:00:00Z", "2026-11-03T02:00:00Z"]],
            "stage_transitions": [{"stage": "stage:1-coding", "entered_at": "2026-11-02T00:00:00Z",
                                   "exited_at": "2026-11-02T06:00:00Z"}],
        })
        first_attempt = {
            "repo": self.REPO_A, "pr_number": 1, "name": "review_requested -> actual_review_started",
            "candidate_sha": "aaa1111", "attempt_number": 1,
            "start_at": "2026-11-02T11:00:00Z", "end_at": "2026-11-02T12:00:00Z", "receipt_id": "r-1",
        }
        timeline = {self.REPO_A + "#1": [
            {"__typename": "LabeledEvent", "createdAt": "2026-11-02T00:00:00Z", "label": {"name": "stage:1-coding"}},
        ]}
        os.makedirs(scratch)
        for name, payload in (
            ("enriched_prs.json", [pr]), ("raw_timeline.json", timeline),
            ("actionable_handoff_metrics.json", [first_attempt]),
            ("source_manifest.json", {self.REPO_A: {"status": "COMPLETE", "count": 1, "cutoff": self.CUTOFF}}),
        ):
            with open(os.path.join(scratch, name), "w", encoding="utf-8") as f:
                json.dump(payload, f)

    def test_two_attempts_at_the_same_head_survive_publish_and_reload(self):
        with tempfile.TemporaryDirectory() as tmp:
            scratch, roadmap = os.path.join(tmp, "scratch"), os.path.join(tmp, "roadmap")
            self._two_attempt_scratch(scratch)
            collector = Collector(repos=[self.REPO_A], cutoff_dt=parse_iso_utc(self.CUTOFF))
            before = collector.collect_all(input_dir=scratch, offline=True)
            summary_before = self._summarize(before)
            review = [h for h in summary_before["handoffs"] if h["name"] == "review_requested -> actual_review_started"][0]
            self.assertEqual(review["sample_n"], 2)
            self._publish(roadmap, before, "20261104")
            shutil.rmtree(scratch)
            after = Collector(repos=[self.REPO_A], cutoff_dt=parse_iso_utc(self.CUTOFF)).collect_all(
                roadmap_repo=roadmap, offline=True
            )
            self.assertEqual(self._summarize(after)["handoffs"], summary_before["handoffs"])

    def test_every_record_key_the_aggregator_and_renderer_read_is_retained_or_documented(self):
        # Keys intentionally not retained although code may read them: PR bodies are never published
        # (their parsed fields are retained instead).
        never_retained = {"PR": {"body"}, "TIMELINE": set(), "HANDOFF": set()}
        seen = {"PR": set(), "TIMELINE": set(), "HANDOFF": set()}

        def recording(kind):
            class Recorder(dict):
                def get(self, key, default=None):
                    seen[kind].add(key)
                    return super().get(key, default)

                def __getitem__(self, key):
                    seen[kind].add(key)
                    return super().__getitem__(key)

                def __contains__(self, key):
                    seen[kind].add(key)
                    return super().__contains__(key)
            return Recorder

        with tempfile.TemporaryDirectory() as tmp:
            scratch, receipts = os.path.join(tmp, "scratch"), os.path.join(tmp, "receipts")
            self._two_attempt_scratch(scratch)
            self._receipt(receipts)
            collected = Collector(repos=[self.REPO_A], cutoff_dt=parse_iso_utc(self.CUTOFF)).collect_all(
                input_dir=scratch, receipts_dir=receipts,
                fetch_page_fn=lambda r, p, pp: [], fetch_timeline_fn=lambda r, n: [],
            )
            open_pr = self._telemetry_pr("hhh8888")
            open_pr["body"] = "next_action: x\nowner: y\njob_handle: j\nwake_condition: w"
            collected["prs"].append(Collector(repos=[]).normalize_pr_record(open_pr))
            prs = [recording("PR")(p) for p in collected["prs"]]
            timeline = [recording("TIMELINE")(e) for e in collected["timeline"]]
            handoffs = [recording("HANDOFF")(h) for h in collected["handoff_records"]]
            cutoff = parse_iso_utc(self.CUTOFF)
            summary = MetricsAggregator(cutoff_dt=cutoff).aggregate_full_dataset(
                prs=prs, timeline_events=timeline, sources=collected["sources"],
                handoff_records=handoffs, now_dt=cutoff,
            )
            DashboardRenderer().render(summary)

        self.assertTrue({"attempt", "headRefOid", "state"} <= seen["PR"], seen["PR"])
        self.assertTrue(seen["HANDOFF"] and seen["TIMELINE"])
        for kind, allowed in (
            ("PR", RETAINED_PR_FIELDS),
            ("TIMELINE", RETAINED_TIMELINE_FIELDS),
            ("HANDOFF", RETAINED_HANDOFF_FIELDS),
        ):
            missing = seen[kind] - set(allowed) - never_retained[kind]
            self.assertEqual(missing, set(), "%s keys read but not retained" % kind)


class TestDriverOwnershipProjection(unittest.TestCase):
    REPO = "example-org/repo-alpha"
    HEAD = "a" * 40

    def _event(self, event_id, event_type, at, sequence, state, preceding=None,
               obligation="review-follow-up", candidate=None, attempt=1, **extra):
        occurred = datetime(2026, 11, 11, 10, 15, tzinfo=timezone.utc) + timedelta(minutes=int(at))
        row = {
            "event_id": event_id,
            "event_type": event_type,
            "occurred_at": format_iso_utc(occurred),
            "observed_at": format_iso_utc(occurred + timedelta(seconds=1)),
            "pr_id": f"{self.REPO}#7",
            "candidate_sha": candidate or self.HEAD,
            "attempt_number": attempt,
            "schema_version": 1,
            "obligation_id": obligation,
            "source": "driver-session",
            "sequence": sequence,
            "preceding_event_id": preceding,
            "state": state,
            "owner_id": "driver-session",
        }
        if state == "actionable_unowned":
            row["result_receipt"] = f"actionable-{event_id}"
        if state == "executing":
            row["worker_id"] = "worker-1"
            row["result_receipt"] = f"work-start-{event_id}"
        if preceding:
            previous_minute = {
                "e1": "00", "e2": "02", "e3": "05", "e4": "12", "e5": "13", "e6": "15",
            }[preceding]
            row["continuity_from_event_id"] = preceding
            row["continuity_receipt"] = {
                "receipt_id": f"coverage-{preceding}-{event_id}",
                "covers_from": format_iso_utc(
                    datetime(2026, 11, 11, 10, 15, tzinfo=timezone.utc)
                    + timedelta(minutes=int(previous_minute))
                ),
                "covers_to": format_iso_utc(occurred),
                "pr_id": f"{self.REPO}#7",
                "candidate_sha": candidate or self.HEAD,
                "attempt_number": attempt,
                "obligation_id": obligation,
                "owner_id": "driver-session",
            }
        row.update(extra)
        return row

    def _fixture(self):
        return [
            self._event("e1", "action_observed", "00", 1, "actionable_unowned"),
            self._event("e2", "worker_acknowledged", "02", 2, "actionable_unowned", "e1"),
            self._event("e3", "worker_started", "05", 3, "executing", "e2"),
            self._event("e4", "worker_returned", "12", 4, "actionable_unowned", "e3"),
            self._event("e5", "wake_fired", "13", 5, "actionable_unowned", "e4"),
            self._event("e6", "next_action_started", "15", 6, "executing", "e5"),
            self._event("e7", "window_observed", "10080", 7, "executing", "e6"),
        ]

    def _collect(self, rows):
        with tempfile.TemporaryDirectory() as receipts_dir:
            path = Path(receipts_dir, "transition-events.jsonl")
            path.write_text("".join(json.dumps(row) + "\n" for row in rows))
            return Collector().collect_receipts_from_dir(receipts_dir)

    def test_real_collector_and_summary_project_eight_owned_observation_minutes(self):
        cutoff = datetime(2026, 11, 18, 10, 15, tzinfo=timezone.utc)
        receipts = self._collect(self._fixture())
        pr = {
            "repo": self.REPO, "number": 7, "state": "OPEN", "headRefOid": self.HEAD,
            "createdAt": "2026-11-10T00:00:00Z", "updatedAt": "2026-11-11T10:00:00Z",
            "url": "https://github.com/example-org/repo-alpha/pull/7", "labels": [],
        }
        summary = MetricsAggregator(cutoff_dt=cutoff).aggregate_full_dataset(
            [pr], handoff_records=receipts,
            handoff_receipt_stats={"status": "COMPLETE", "files_scanned": 1},
            sources={"github": {"status": "COMPLETE", "cutoff": format_iso_utc(cutoff)}},
            now_dt=cutoff,
        )
        ranked = summary["open_prs_known_idle"]
        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0]["eligible_unattended_duration_sec"], 480.0)
        self.assertEqual(ranked[0]["review_return_to_pickup_median_sec"], 180.0)
        self.assertEqual(ranked[0]["wake_to_pickup_median_sec"], 120.0)
        dashboard = DashboardRenderer().render(summary)
        self.assertIn("Review Return to Pickup", dashboard)
        self.assertIn("Wake to Pickup", dashboard)

    def test_fifteen_minute_collected_fixture_projects_five_plus_three_minutes(self):
        start = datetime(2026, 11, 11, 10, 15, tzinfo=timezone.utc)
        end = start + timedelta(minutes=15)
        records = self._collect(self._fixture()[:6])
        result = MetricsAggregator(cutoff_dt=end).compute_driver_ownership_metrics(
            {"repo": self.REPO, "number": 7, "headRefOid": self.HEAD}, records, start, end,
        )
        self.assertEqual(result, {
            "status": "COMPLETE", "unattended_sec_lower_bound": 480.0,
            "unknown_sec": 0.0, "coverage": 1.0,
        })
        paired, _ = MetricsAggregator().adapt_transition_event_receipts(
            records, [{"repo": self.REPO, "number": 7, "headRefOid": self.HEAD}],
        )
        durations = {
            event["name"]: MetricsAggregator().compute_interval_duration(
                event["start_at"], event["end_at"],
            )["duration_sec"]
            for event in paired
        }
        self.assertEqual(durations["review_return -> next_substantive_action"], 180.0)
        self.assertEqual(durations["wake_fired -> next_substantive_action"], 120.0)

    def test_versioned_receipts_have_live_and_retained_replay_parity(self):
        start = datetime(2026, 11, 11, 10, 15, tzinfo=timezone.utc)
        end = start + timedelta(minutes=15)
        pr = {"repo": self.REPO, "number": 7, "headRefOid": self.HEAD}
        rows = self._fixture()[:6]
        rows[1]["continuity_receipt"]["receipt_id"] = "../local/driver.log"
        invalid = {
            key: rows[3][key] for key in (
                "event_id", "occurred_at", "observed_at", "pr_id", "candidate_sha", "attempt_number",
            )
        }
        invalid.update(event_type="review_return", schema_version="invalid/schema")
        live = self._collect(rows + [invalid])
        path = "dashboards/prw/telemetry/20261111/retained_handoffs.jsonl"
        replay = [
            json.loads(line) for line in sanitize_telemetry_file(
                path, "\n".join(map(json.dumps, live)),
            ).splitlines()
        ]
        aggregator = MetricsAggregator()
        before = aggregator.compute_driver_ownership_metrics(pr, live[:-1], start, end)
        after = aggregator.compute_driver_ownership_metrics(pr, replay[:-1], start, end)
        self.assertEqual(before, after)
        self.assertNotEqual(before["status"], "COMPLETE")
        self.assertEqual(
            aggregator.adapt_transition_event_receipts(live, [pr], as_of=end),
            aggregator.adapt_transition_event_receipts(replay, [pr], as_of=end),
        )

    def test_legacy_receipt_does_not_interrupt_v1_continuity(self):
        start = datetime(2026, 11, 11, 10, 15, tzinfo=timezone.utc)
        end = start + timedelta(minutes=15)
        rows = self._fixture()[:6]
        legacy = {
            "event_id": "legacy-review-request",
            "event_type": "review_requested",
            "occurred_at": format_iso_utc(start + timedelta(minutes=1)),
            "observed_at": format_iso_utc(start + timedelta(minutes=1)),
            "pr_id": f"{self.REPO}#7",
            "candidate_sha": self.HEAD,
            "attempt_number": 1,
        }
        pr = {"repo": self.REPO, "number": 7, "headRefOid": self.HEAD}

        metrics = MetricsAggregator().compute_driver_ownership_metrics(
            pr, self._collect(rows + [legacy]), start, end,
        )
        self.assertEqual(metrics["status"], "COMPLETE")
        self.assertEqual(metrics["unattended_sec_lower_bound"], 480.0)

        unknown_version = dict(rows[1], schema_version=99)
        metrics = MetricsAggregator().compute_driver_ownership_metrics(
            pr, self._collect([rows[0], unknown_version, *rows[2:]]), start, end,
        )
        self.assertNotEqual(metrics["status"], "COMPLETE")
        self.assertEqual(metrics["unknown_sec"], 300.0)

    def test_pickup_clocks_are_right_censored_at_the_report_cutoff(self):
        start = datetime(2026, 11, 11, 10, 15, tzinfo=timezone.utc)
        pr = {
            "repo": self.REPO, "number": 7, "state": "OPEN", "headRefOid": self.HEAD,
            "createdAt": format_iso_utc(start), "updatedAt": format_iso_utc(start),
            "url": f"https://github.com/{self.REPO}/pull/7", "labels": [],
        }
        events = self._collect(self._fixture()[:6])
        for minute, review_open, wake_open, review_median, wake_median in (
            (11, [], [], "UNKNOWN", "UNKNOWN"),
            (12, [0.0], [], "UNKNOWN", "UNKNOWN"),
            (13, [60.0], [0.0], "UNKNOWN", "UNKNOWN"),
            (14, [120.0], [60.0], "UNKNOWN", "UNKNOWN"),
            (15, [], [], 180.0, 120.0),
        ):
            with self.subTest(cutoff_minute=minute):
                cutoff = start + timedelta(minutes=minute)
                summary = MetricsAggregator(cutoff_dt=cutoff).aggregate_full_dataset(
                    [pr], handoff_records=events, now_dt=cutoff,
                )
                projected = _project_summary(summary)
                row, = projected["open_prs_known_idle"] + projected["open_prs_unknown_idle"]
                self.assertEqual(row["review_return_to_pickup_open_elapsed_sec"], review_open)
                self.assertEqual(row["wake_to_pickup_open_elapsed_sec"], wake_open)
                self.assertEqual(row["review_return_to_pickup_median_sec"], review_median)
                self.assertEqual(row["wake_to_pickup_median_sec"], wake_median)

    def test_conflicting_duplicate_interrupts_ownership_at_every_occurrence(self):
        start = datetime(2026, 11, 11, 10, 15, tzinfo=timezone.utc)
        end = start + timedelta(minutes=15)
        rows = self._fixture()[:6]
        conflict = dict(rows[3], occurred_at=format_iso_utc(start + timedelta(minutes=14)))
        pr = {"repo": self.REPO, "number": 7, "headRefOid": self.HEAD}

        for events in (rows + [conflict], [conflict] + rows):
            metrics = MetricsAggregator().compute_driver_ownership_metrics(
                pr, self._collect(events), start, end,
            )
            self.assertEqual(metrics["status"], "PARTIAL")
            self.assertEqual(metrics["unattended_sec_lower_bound"], 300.0)
            self.assertEqual(metrics["unknown_sec"], 600.0)

    def test_untimed_duplicate_conflict_preserves_only_unaffected_ownership_spans(self):
        start = datetime(2026, 11, 11, 10, 15, tzinfo=timezone.utc)
        end = start + timedelta(minutes=15)
        pr = {
            "repo": self.REPO, "number": 7, "state": "OPEN",
            "headRefOid": self.HEAD, "createdAt": format_iso_utc(start),
        }
        records = self._fixture()[:6]
        endpoint = records[-1]
        untimed = dict(endpoint, result_receipt="conflicting")
        del untimed["occurred_at"]
        malformed = dict(untimed, occurred_at="not-a-timestamp")
        before_creation = dict(untimed, occurred_at="2026-11-11T10:14:00Z")
        legacy = {
            key: untimed[key] for key in (
                "event_id", "event_type", "observed_at", "pr_id", "candidate_sha", "attempt_number",
            )
        }
        for case, extra, expected, ownership in (
            ("missing time", untimed, 360.0, "PARTIAL"),
            ("invalid time", malformed, 360.0, "PARTIAL"),
            ("before creation", before_creation, 360.0, "PARTIAL"),
            ("unrelated ID", dict(untimed, event_id="unrelated-untimed"), 480.0, "COMPLETE"),
            ("other PR", dict(untimed, pr_id="other/repo#9"), 480.0, "COMPLETE"),
            ("clean mirror", dict(endpoint, observed_at="2026-11-11T10:31:00Z"), 480.0, "COMPLETE"),
            ("legacy", legacy, 480.0, "COMPLETE"),
        ):
            for order, raw in (("after", [*records, extra]), ("before", [extra, *records])):
                live = self._collect(raw)
                retained = sanitize_telemetry_file(
                    "dashboards/prw/telemetry/20261111/retained_handoffs.jsonl",
                    "\n".join(map(json.dumps, live)),
                )
                replay = [json.loads(line) for line in retained.splitlines()]
                for feed, events in (("live", live), ("replay", replay)):
                    with self.subTest(case=case, order=order, feed=feed):
                        summary = MetricsAggregator(cutoff_dt=end).aggregate_full_dataset(
                            [pr], handoff_records=events, now_dt=end,
                        )
                        section = (
                            "open_prs_known_idle" if ownership == "COMPLETE" else "open_prs_unknown_idle"
                        )
                        row, = summary[section]
                        self.assertEqual(row["ownership_status"], ownership)
                        self.assertEqual(row["ownership_unattended_sec_lower_bound"], expected)
                        self.assertEqual(row["ownership_unknown_sec"], 480.0 - expected)

    def test_malformed_pickup_blocks_open_clocks_only_for_matching_scope(self):
        cutoff = datetime(2026, 11, 11, 10, 35, tzinfo=timezone.utc)
        pr = {"repo": self.REPO, "number": 7, "headRefOid": self.HEAD}
        returned, wake, started = self._fixture()[3:6]
        malformed = dict(
            started, state="paused", wait_reason="explicit_pause",
            worker_id=None, result_receipt=None,
        )

        missing_obligation = dict(started)
        del missing_obligation["obligation_id"]
        for case, ends, expected in (
            ("invalid state", [malformed], []),
            ("missing obligation linked to wake", [missing_obligation], []),
            ("known other obligation", [dict(started, obligation_id="other")], ["RIGHT_CENSORED"] * 2),
            ("duplicate pickup ID", [started, dict(started, result_receipt="different")], []),
            ("other attempt", [dict(malformed, attempt_number=2)], ["RIGHT_CENSORED"] * 2),
            ("valid pickup", [started], ["COMPLETE"] * 2),
        ):
            with self.subTest(case=case):
                rows, _ = MetricsAggregator().adapt_transition_event_receipts(
                    self._collect([returned, wake, *ends]), [pr], as_of=cutoff,
                )
                self.assertEqual(
                    [row.get("status", "COMPLETE") for row in rows],
                    expected,
                )

    def test_missing_pickup_obligation_respects_contested_predecessor_scopes(self):
        cutoff = datetime(2026, 11, 11, 10, 35, tzinfo=timezone.utc)
        pr = {"repo": self.REPO, "number": 7, "headRefOid": self.HEAD}
        returned, wake, started = self._fixture()[3:6]
        del started["obligation_id"]
        alternate = self._event(
            "alternate-return", "worker_returned", 8, 8, "actionable_unowned",
            obligation="alternate",
        )
        unaffected = [
            self._event(
                "unrelated-return", "worker_returned", 9, 9, "actionable_unowned",
                obligation="unrelated",
            ),
            self._event(
                "other-attempt-return", "worker_returned", 10, 10, "actionable_unowned",
                obligation="alternate", attempt=2,
            ),
            self._event(
                "other-head-return", "worker_returned", 11, 11, "actionable_unowned",
                obligation="alternate", candidate="b" * 40,
            ),
        ]
        wake_without_obligation = dict(wake)
        del wake_without_obligation["obligation_id"]
        for case, wakes, expected_returns in (
            ("same obligation", [wake, dict(wake, result_receipt="conflicting")],
             [alternate, *unaffected]),
            ("different obligation", [wake, dict(wake, obligation_id="alternate")], unaffected),
            ("different attempt", [wake, dict(wake, obligation_id="alternate", attempt_number=2)],
             [alternate, *unaffected]),
            ("different head", [wake, dict(wake, obligation_id="alternate", candidate_sha="b" * 40)],
             [alternate, *unaffected]),
            ("later alternative", [wake, dict(wake, obligation_id="alternate",
                                              occurred_at="2026-11-11T10:31:00Z")],
             [alternate, *unaffected]),
            ("wake missing obligation", [wake_without_obligation], [alternate, *unaffected]),
            ("cyclic predecessor", [dict(wake_without_obligation, preceding_event_id=wake["event_id"])],
             [returned, alternate, *unaffected]),
        ):
            rows = [returned, alternate, *unaffected, *wakes, started]
            expected = {event["occurred_at"] for event in expected_returns}
            for order, raw in (("forward", rows), ("reversed", rows[::-1])):
                live = self._collect(raw)
                retained = sanitize_telemetry_file(
                    "dashboards/prw/telemetry/20261111/retained_handoffs.jsonl",
                    "\n".join(map(json.dumps, live)),
                )
                replay = [json.loads(line) for line in retained.splitlines()]
                for feed, events in (("live", live), ("replay", replay)):
                    with self.subTest(case=case, order=order, feed=feed):
                        clocks, _ = MetricsAggregator().adapt_transition_event_receipts(
                            events, [pr], as_of=cutoff,
                        )
                        self.assertEqual({clock["start_at"] for clock in clocks}, expected)
                        self.assertEqual(len(clocks), len(expected))
                        self.assertTrue(all(clock["status"] == "RIGHT_CENSORED" for clock in clocks))

    def test_unsupported_schema_or_unmatched_head_cannot_open_pickup_clock(self):
        cutoff = datetime(2026, 11, 11, 10, 29, tzinfo=timezone.utc)
        pr = {
            "repo": self.REPO, "number": 7, "state": "OPEN", "headRefOid": self.HEAD,
            "createdAt": "2026-11-11T10:15:00Z",
        }
        rows = self._fixture()[3:5]
        for record, observed in (
            (pr, [dict(row, schema_version=99) for row in rows]),
            (dict(pr, headRefOid="b" * 40), rows),
            (dict(pr, headRefOid=None), rows),
        ):
            with self.subTest(head=record["headRefOid"], version=observed[0]["schema_version"]):
                summary = MetricsAggregator(cutoff_dt=cutoff).aggregate_full_dataset(
                    [record], handoff_records=self._collect(observed), now_dt=cutoff,
                )
                row, = summary["open_prs_unknown_idle"]
                self.assertEqual(row["review_return_to_pickup_open_elapsed_sec"], [])
                self.assertEqual(row["wake_to_pickup_open_elapsed_sec"], [])

    def test_current_ownership_and_completed_pickup_require_matching_head(self):
        start = datetime(2026, 11, 11, 10, 15, tzinfo=timezone.utc)
        cutoff = start + timedelta(minutes=15)
        events = self._collect(self._fixture()[:6])
        for head, eligible, complete_samples in (
            (self.HEAD, 480.0, 1),
            ("b" * 40, None, 0),
            (None, None, 0),
        ):
            with self.subTest(head=head):
                pr = Collector().normalize_pr_record({
                    "repo": self.REPO, "number": 7, "state": "OPEN",
                    "headRefOid": head, "createdAt": format_iso_utc(start),
                })
                summary = MetricsAggregator(cutoff_dt=cutoff).aggregate_full_dataset(
                    [pr], handoff_records=events, now_dt=cutoff,
                )
                if eligible is None:
                    self.assertEqual(summary["open_prs_known_idle"], [])
                    row, = summary["open_prs_unknown_idle"]
                    self.assertEqual(row["ownership_coverage"], 0.0)
                else:
                    row, = summary["open_prs_known_idle"]
                    self.assertEqual(row["eligible_unattended_duration_sec"], eligible)
                self.assertEqual(row["review_return_to_pickup_sample_n"], complete_samples)
                self.assertEqual(row["wake_to_pickup_sample_n"], complete_samples)

    def test_incomplete_or_mismatched_evidence_is_not_ranked(self):
        cutoff = datetime(2026, 11, 18, 10, 15, tzinfo=timezone.utc)
        aggregator = MetricsAggregator(cutoff_dt=cutoff)
        pr = {"repo": self.REPO, "number": 7, "headRefOid": self.HEAD}
        base = self._collect(self._fixture())
        scenarios = [
            base[:-1],
            [base[0], base[1], dict(base[2], obligation_id="different-obligation"), *base[3:]],
            [base[0], base[1], dict(base[2], attempt_number=2), *base[3:]],
            [base[0], base[1], base[2], dict(base[3], candidate_sha="b" * 40), *base[4:]],
            [base[0], dict(base[1], occurred_at=base[0]["occurred_at"], state="executing"), *base[2:]],
            [base[0], base[1], dict(base[2], sequence=5), *base[3:]],
            [base[0], base[1], dict(base[2], schema_version=99), *base[3:]],
        ]
        for rows in scenarios:
            with self.subTest(rows=[row["event_id"] for row in rows]):
                result = aggregator.compute_driver_ownership_metrics(pr, rows, cutoff - timedelta(days=7), cutoff)
                self.assertNotEqual(result["status"], "COMPLETE")

    def test_identity_ownership_and_same_time_conflicts_leave_coverage_unknown(self):
        cutoff = datetime(2026, 11, 18, 10, 15, tzinfo=timezone.utc)
        start = cutoff - timedelta(days=7)
        aggregator = MetricsAggregator(cutoff_dt=cutoff)
        pr = {"repo": self.REPO, "number": 7, "headRefOid": self.HEAD}
        base = self._collect(self._fixture())

        missing_identity = json.loads(json.dumps(base))
        for event in missing_identity:
            event.pop("attempt_number", None)
            event.pop("obligation_id", None)
            if isinstance(event.get("continuity_receipt"), dict):
                event["continuity_receipt"].pop("attempt_number", None)
                event["continuity_receipt"].pop("obligation_id", None)
        missing_metrics = aggregator.compute_driver_ownership_metrics(pr, missing_identity, start, cutoff)
        self.assertNotEqual(missing_metrics["status"], "COMPLETE")
        self.assertEqual(missing_metrics["coverage"], 0.0)

        unrelated_owner = json.loads(json.dumps(base))
        unrelated_owner[1]["continuity_receipt"]["owner_id"] = "unrelated-driver"
        owner_metrics = aggregator.compute_driver_ownership_metrics(pr, unrelated_owner, start, cutoff)
        self.assertNotEqual(owner_metrics["status"], "COMPLETE")
        self.assertGreater(owner_metrics["unknown_sec"], 0.0)

        simultaneous = json.loads(json.dumps(base))
        simultaneous[1]["occurred_at"] = simultaneous[0]["occurred_at"]
        simultaneous[1].update(
            event_type="execution_observed", state="executing",
            worker_id="worker-1", result_receipt="simultaneous-work-started",
        )
        simultaneous[1]["preceding_event_id"] = "unlinked-event"
        simultaneous[1]["continuity_from_event_id"] = "unlinked-event"
        normalized = [
            MetricsAggregator.validate_ownership_observation(event, f"{self.REPO}#7")
            for event in simultaneous[:2]
        ]
        conflict_input = [
            (parse_iso_utc(event["occurred_at"]), event["sequence"], event["event_id"], event, record)
            for event, record in zip(simultaneous[:2], normalized)
        ]
        self.assertEqual(
            aggregator._simultaneous_ownership_conflicts(conflict_input),
            {(f"{self.REPO}#7", "e1"), (f"{self.REPO}#7", "e2")},
        )
        contradictory = aggregator.compute_driver_ownership_metrics(pr, simultaneous, start, cutoff)
        self.assertNotEqual(contradictory["status"], "COMPLETE")
        self.assertGreater(contradictory["unknown_sec"], 0.0)

    def test_head_change_and_malformed_wake_deadline_leave_unknown_spans(self):
        cutoff = datetime(2026, 11, 18, 10, 15, tzinfo=timezone.utc)
        start = cutoff - timedelta(days=7)
        aggregator = MetricsAggregator(cutoff_dt=cutoff)
        pr = {"repo": self.REPO, "number": 7, "headRefOid": self.HEAD}
        base = self._collect(self._fixture())

        changed_head = json.loads(json.dumps(base))
        changed_head[1]["candidate_sha"] = "b" * 40
        changed_head[1]["continuity_receipt"]["candidate_sha"] = "b" * 40
        changed_head[2]["sequence"] = 3
        changed_head[2]["preceding_event_id"] = changed_head[1]["event_id"]
        changed_head[2]["continuity_from_event_id"] = changed_head[1]["event_id"]
        changed_head[2]["continuity_receipt"]["covers_from"] = changed_head[1]["occurred_at"]
        changed_metrics = aggregator.compute_driver_ownership_metrics(pr, changed_head, start, cutoff)
        self.assertNotEqual(changed_metrics["status"], "COMPLETE")
        self.assertGreater(changed_metrics["unknown_sec"], 0.0)

        malformed_wait = json.loads(json.dumps(base))
        malformed_wait[0].update(
            state="verified_wait", result_receipt=None, wait_reason="review_pending",
            wake_trigger="review result", wake_due_at="not-a-time",
        )
        invalid_wait = aggregator.compute_driver_ownership_metrics(pr, malformed_wait, start, cutoff)
        self.assertNotEqual(invalid_wait["status"], "COMPLETE")
        self.assertGreater(invalid_wait["unknown_sec"], 0.0)

    def test_malformed_optional_state_and_sequence_do_not_crash_aggregate(self):
        cutoff = datetime(2026, 11, 18, 10, 15, tzinfo=timezone.utc)
        pr = {
            "repo": self.REPO, "number": 7, "state": "OPEN", "headRefOid": self.HEAD,
            "createdAt": "2026-11-10T00:00:00Z", "updatedAt": "2026-11-11T10:00:00Z",
            "url": "https://github.com/example-org/repo-alpha/pull/7", "labels": [],
        }
        malformed_cases = []
        bad_state = json.loads(json.dumps(self._fixture()))
        bad_state[1]["state"] = {"invalid": 1}
        malformed_cases.append(bad_state)
        bad_sequence = json.loads(json.dumps(self._fixture()))
        bad_sequence[1]["sequence"] = "bad"
        malformed_cases.append(bad_sequence)
        same_time_sequence = json.loads(json.dumps(self._fixture()[:2]))
        same_time_sequence[1]["occurred_at"] = same_time_sequence[0]["occurred_at"]
        same_time_sequence[1]["sequence"] = "2"
        malformed_cases.append(same_time_sequence)

        for events in malformed_cases:
            with self.subTest(event=events[1]):
                receipts = self._collect(events)
                summary = MetricsAggregator(cutoff_dt=cutoff).aggregate_full_dataset(
                    [pr], handoff_records=receipts,
                    handoff_receipt_stats={"status": "COMPLETE", "files_scanned": 1},
                    sources={"github": {"status": "COMPLETE", "cutoff": format_iso_utc(cutoff)}},
                    now_dt=cutoff,
                )
                self.assertEqual(summary["open_prs_known_idle"], [])
                self.assertGreater(summary["open_prs_unknown_idle"][0]["ownership_unknown_sec"], 0.0)

    def test_same_time_events_from_another_pr_do_not_suppress_pickup(self):
        events = self._collect(self._fixture()[:6])
        returned = next(event for event in events if event["event_id"] == "e4")
        unrelated = dict(
            returned, event_id="other-execution", event_type="execution_observed",
            pr_id="other/repo#9", obligation_id="other-obligation", owner_id="other-driver",
            state="executing", worker_id="other-worker", result_receipt="other-work-started",
            preceding_event_id=None, continuity_from_event_id=None, continuity_receipt=None,
        )
        pairs, stats = MetricsAggregator().adapt_transition_event_receipts(
            events + [unrelated],
            [
                {"repo": self.REPO, "number": 7, "headRefOid": self.HEAD},
                {"repo": "other/repo", "number": 9, "headRefOid": self.HEAD},
            ],
        )
        review_pickup = [row for row in pairs if row["name"] == "review_return -> next_substantive_action"]
        self.assertEqual(len(review_pickup), 1)
        self.assertEqual(review_pickup[0]["number"], 7)
        self.assertEqual(stats["receipt_event_conflicts"], 0)

        cutoff = datetime(2026, 11, 18, 10, 15, tzinfo=timezone.utc)
        prs = [
            {
                "repo": self.REPO, "number": 7, "state": "OPEN", "headRefOid": self.HEAD,
                "createdAt": "2026-11-10T00:00:00Z", "updatedAt": "2026-11-11T10:00:00Z",
                "url": f"https://github.com/{self.REPO}/pull/7", "labels": [],
            },
            {
                "repo": "other/repo", "number": 9, "state": "OPEN", "headRefOid": self.HEAD,
                "createdAt": "2026-11-10T00:00:00Z", "updatedAt": "2026-11-11T12:00:00Z",
                "url": "https://github.com/other/repo/pull/9", "labels": [],
            },
        ]
        summary = MetricsAggregator(cutoff_dt=cutoff).aggregate_full_dataset(
            prs, handoff_records=events + [unrelated],
            handoff_receipt_stats={"status": "COMPLETE", "files_scanned": 1},
            sources={"github": {"status": "COMPLETE", "cutoff": format_iso_utc(cutoff)}},
            now_dt=cutoff,
        )
        pr7 = next(row for row in summary["open_prs_unknown_idle"] if row["number"] == 7)
        self.assertEqual(pr7["review_return_to_pickup_sample_n"], 1)
        self.assertEqual(pr7["review_return_to_pickup_median_sec"], 180.0)

    def test_conflict_scope_stays_with_pr_when_another_pr_is_later(self):
        events = self._collect(self._fixture()[:6])
        returned = next(event for event in events if event["event_id"] == "e4")
        conflicting = dict(
            returned, event_id="unlinked-execution", event_type="execution_observed",
            state="executing", worker_id="worker-1", result_receipt="conflicting-state",
            preceding_event_id="unrelated-predecessor", continuity_from_event_id="unrelated-predecessor",
        )
        unrelated_later = self._event(
            "other-later", "action_observed", "30", 7, "actionable_unowned",
            obligation="other-obligation",
        )
        unrelated_later["pr_id"] = "other/repo#9"
        unrelated_later["owner_id"] = "other-driver"
        records = events + [conflicting, unrelated_later]
        prs = [
            {"repo": self.REPO, "number": 7, "headRefOid": self.HEAD},
            {"repo": "other/repo", "number": 9, "headRefOid": self.HEAD},
        ]
        pairs, stats = MetricsAggregator().adapt_transition_event_receipts(records, prs)
        self.assertEqual(stats["receipt_event_conflicts"], 2)
        self.assertFalse(any(
            row["name"] == "review_return -> next_substantive_action"
            and row["number"] == 7
            for row in pairs
        ))

    def test_job_continuity_must_match_both_interval_endpoints(self):
        start = datetime(2026, 11, 11, 10, 15, tzinfo=timezone.utc)
        end = start + timedelta(minutes=15)
        left = self._event("e1", "execution_observed", "00", 1, "executing")
        right = self._event("e2", "execution_observed", "15", 2, "executing", "e1")
        left.update(worker_id=None, job_id="old-job")
        right.update(worker_id=None, job_id="new-job")
        right["continuity_receipt"].pop("owner_id")
        right["continuity_receipt"]["job_id"] = "new-job"
        result = MetricsAggregator().compute_driver_ownership_metrics(
            {"repo": self.REPO, "number": 7, "headRefOid": self.HEAD},
            self._collect([left, right]), start, end,
        )
        self.assertEqual(result["status"], "PARTIAL")
        self.assertEqual(result["unknown_sec"], 900.0)

    def test_job_receipt_cannot_cover_different_endpoint_owners_or_rank_pr(self):
        start = datetime(2026, 11, 11, 10, 15, tzinfo=timezone.utc)
        end = start + timedelta(minutes=15)
        left = self._event("e1", "action_observed", "00", 1, "actionable_unowned")
        right = self._event("e2", "worker_started", "15", 2, "executing", "e1")
        left["owner_id"] = "driver-a"
        right.update(owner_id="driver-b", worker_id=None, job_id="job-1")
        right["continuity_receipt"].pop("owner_id")
        right["continuity_receipt"]["job_id"] = "job-1"
        records = self._collect([left, right])
        pr = {"repo": self.REPO, "number": 7, "headRefOid": self.HEAD}
        result = MetricsAggregator().compute_driver_ownership_metrics(pr, records, start, end)
        self.assertNotEqual(result["status"], "COMPLETE")
        self.assertEqual(result["unknown_sec"], 900.0)

        cutoff = datetime(2026, 11, 18, 10, 15, tzinfo=timezone.utc)
        summary_pr = dict(
            pr, state="OPEN", createdAt="2026-11-10T00:00:00Z",
            updatedAt="2026-11-11T10:00:00Z", url="https://github.com/example-org/repo-alpha/pull/7",
            labels=[],
        )
        summary = MetricsAggregator(cutoff_dt=cutoff).aggregate_full_dataset(
            [summary_pr], handoff_records=records,
            handoff_receipt_stats={"status": "COMPLETE", "files_scanned": 1},
            sources={"github": {"status": "COMPLETE", "cutoff": format_iso_utc(cutoff)}},
            now_dt=cutoff,
        )
        self.assertEqual(summary["open_prs_known_idle"], [])

    def test_each_supplied_continuity_identity_must_match_both_endpoints(self):
        start = datetime(2026, 11, 11, 10, 15, tzinfo=timezone.utc)
        end = start + timedelta(minutes=15)
        pr = {"repo": self.REPO, "number": 7, "headRefOid": self.HEAD}
        base = [
            self._event("e1", "execution_observed", "00", 1, "executing"),
            self._event("e2", "execution_observed", "15", 2, "executing", "e1"),
        ]

        owner_only = json.loads(json.dumps(base))
        owner_result = MetricsAggregator().compute_driver_ownership_metrics(
            pr, self._collect(owner_only), start, end,
        )
        self.assertEqual((owner_result["status"], owner_result["unknown_sec"]), ("COMPLETE", 0.0))

        both_match = json.loads(json.dumps(base))
        both_match[0]["job_id"] = both_match[1]["job_id"] = "job-1"
        both_match[1]["continuity_receipt"]["job_id"] = "job-1"
        both_match[1]["continuity_receipt"]["worker_id"] = "worker-1"
        both_result = MetricsAggregator().compute_driver_ownership_metrics(
            pr, self._collect(both_match), start, end,
        )
        self.assertEqual((both_result["status"], both_result["unknown_sec"]), ("COMPLETE", 0.0))

        conflicting_worker = json.loads(json.dumps(base))
        conflicting_worker[0]["worker_id"] = "worker-old"
        conflicting_worker[1]["worker_id"] = "worker-new"
        conflicting_worker[1]["continuity_receipt"]["worker_id"] = "worker-new"
        worker_result = MetricsAggregator().compute_driver_ownership_metrics(
            pr, self._collect(conflicting_worker), start, end,
        )
        self.assertEqual(worker_result["status"], "PARTIAL")
        self.assertEqual(worker_result["unknown_sec"], 900.0)

        owner_matches_job_conflicts = json.loads(json.dumps(both_match))
        owner_matches_job_conflicts[0]["job_id"] = "old-job"
        owner_matches_job_conflicts[1]["job_id"] = "new-job"
        owner_matches_job_conflicts[1]["continuity_receipt"]["job_id"] = "new-job"
        conflict_result = MetricsAggregator().compute_driver_ownership_metrics(
            pr, self._collect(owner_matches_job_conflicts), start, end,
        )
        self.assertEqual(conflict_result["status"], "PARTIAL")
        self.assertEqual(conflict_result["unknown_sec"], 900.0)

        job_only = json.loads(json.dumps(both_match))
        job_only[0]["owner_id"] = "driver-a"
        job_only[1]["owner_id"] = "driver-b"
        job_only[1]["continuity_receipt"].pop("owner_id")
        job_result = MetricsAggregator().compute_driver_ownership_metrics(
            pr, self._collect(job_only), start, end,
        )
        self.assertEqual((job_result["status"], job_result["unknown_sec"]), ("COMPLETE", 0.0))

    def test_legacy_multiple_returns_remain_ambiguous(self):
        def legacy_event(event_id, event_type, minute):
            return {
                "event_id": event_id, "event_type": event_type,
                "occurred_at": f"2026-11-05T10:{minute}:00Z",
                "observed_at": f"2026-11-05T10:{minute}:01Z",
                "pr_id": f"{self.REPO}#7", "candidate_sha": self.HEAD,
                "attempt_number": 2,
            }

        rows = self._collect([
            legacy_event("return-1", "review_return", "27"),
            legacy_event("return-2", "review_return", "29"),
            legacy_event("action-start", "next_action_started", "30"),
        ])
        pairs, _ = MetricsAggregator().adapt_transition_event_receipts(
            rows, [{"repo": self.REPO, "number": 7, "headRefOid": self.HEAD}],
        )
        self.assertFalse(any(row["name"] == "review_return -> next_substantive_action" for row in pairs))

    def test_pickup_rejects_causally_impossible_intermediate_clock(self):
        rows = json.loads(json.dumps(self._collect(self._fixture()[:6])))
        rows[4]["occurred_at"] = "2026-11-11T10:45:00Z"
        rows[4]["observed_at"] = "2026-11-11T10:45:01Z"
        pairs, _ = MetricsAggregator().adapt_transition_event_receipts(
            rows, [{"repo": self.REPO, "number": 7, "headRefOid": self.HEAD}],
        )
        self.assertFalse(any(row["name"] == "review_return -> next_substantive_action" for row in pairs))
        self.assertFalse(any(row["name"] == "wake_fired -> next_substantive_action" for row in pairs))

    def test_worker_acknowledgment_cannot_override_executing_state(self):
        start = datetime(2026, 11, 11, 10, 15, tzinfo=timezone.utc)
        end = start + timedelta(minutes=15)
        rows = json.loads(json.dumps(self._collect(self._fixture()[:6])))
        rows[2].update(
            event_type="worker_acknowledged", state="executing",
            worker_id="worker-1", result_receipt="ack-only",
        )
        result = MetricsAggregator().compute_driver_ownership_metrics(
            {"repo": self.REPO, "number": 7, "headRefOid": self.HEAD}, rows, start, end,
        )
        self.assertEqual(result["status"], "PARTIAL")
        self.assertGreaterEqual(result["unattended_sec_lower_bound"], 120.0)
        self.assertGreater(result["unknown_sec"], 0.0)

    def test_acknowledgment_alone_cannot_establish_execution(self):
        start = datetime(2026, 11, 11, 10, 15, tzinfo=timezone.utc)
        end = start + timedelta(minutes=15)
        rows = json.loads(json.dumps(self._collect(self._fixture()[:6])))
        rows[2].update(
            event_type="worker_acknowledged", state="executing",
            worker_id="worker-1", result_receipt="ack-only",
        )
        result = MetricsAggregator().compute_driver_ownership_metrics(
            {"repo": self.REPO, "number": 7, "headRefOid": self.HEAD}, rows, start, end,
        )
        self.assertEqual(result["status"], "PARTIAL")
        self.assertGreater(result["unknown_sec"], 0.0)

    def test_unhashable_event_type_values_do_not_crash_optional_feed(self):
        base = self._collect(self._fixture()[:6])
        cutoff = datetime(2026, 11, 18, 10, 15, tzinfo=timezone.utc)
        pr = {
            "repo": self.REPO, "number": 7, "state": "OPEN", "headRefOid": self.HEAD,
            "createdAt": "2026-11-10T00:00:00Z", "updatedAt": "2026-11-11T10:00:00Z",
            "url": f"https://github.com/{self.REPO}/pull/7", "labels": [],
        }
        for malformed_type in (["worker_returned"], {"name": "worker_returned"}):
            with self.subTest(event_type=malformed_type):
                event = dict(base[3], event_id=f"malformed-{len(base)}", event_type=malformed_type)
                summary = MetricsAggregator(cutoff_dt=cutoff).aggregate_full_dataset(
                    [pr], handoff_records=base + [event],
                    handoff_receipt_stats={"status": "COMPLETE", "files_scanned": 1},
                    sources={"github": {"status": "COMPLETE", "cutoff": format_iso_utc(cutoff)}},
                    now_dt=cutoff,
                )
                self.assertEqual(summary["open_prs_known_idle"], [])

    def test_duplicate_event_id_on_another_pr_does_not_suppress_pickup(self):
        records = self._collect(self._fixture()[:6])
        original_return = next(row for row in records if row["event_id"] == "e4")
        other_pr_copy = dict(
            original_return, pr_id="other/repo#9", owner_id="other-driver",
        )
        prs = [
            {"repo": self.REPO, "number": 7, "headRefOid": self.HEAD},
            {"repo": "other/repo", "number": 9, "headRefOid": self.HEAD},
        ]
        pairs, stats = MetricsAggregator().adapt_transition_event_receipts(
            records + [other_pr_copy], prs,
        )
        review_pickup = [row for row in pairs if row["name"] == "review_return -> next_substantive_action"]
        self.assertEqual(len(review_pickup), 1)
        self.assertEqual(review_pickup[0]["number"], 7)
        self.assertEqual(stats["receipt_event_conflicts"], 0)

    def test_wait_expiry_is_unknown_pause_is_zero_and_full_execution_measures_zero(self):
        cutoff = datetime(2026, 11, 18, 10, 15, tzinfo=timezone.utc)
        start = cutoff - timedelta(days=7)
        aggregator = MetricsAggregator(cutoff_dt=cutoff)
        pr = {"repo": self.REPO, "number": 7, "headRefOid": self.HEAD}
        rows = self._collect(self._fixture())
        paused = [dict(row) for row in rows]
        paused[0].update(state="paused", wait_reason="operator_pause")
        pause_metrics = aggregator.compute_driver_ownership_metrics(pr, paused, start, cutoff)
        self.assertEqual(pause_metrics["status"], "COMPLETE")
        self.assertEqual(pause_metrics["unattended_sec_lower_bound"], 360.0)
        waiting = json.loads(json.dumps(rows))
        waiting[0].update(
            state="verified_wait", wait_reason="review_running", job_id="job-1",
            wake_due_at=format_iso_utc(start + timedelta(minutes=2)),
        )
        waiting[1]["occurred_at"] = format_iso_utc(start + timedelta(minutes=4))
        waiting[1]["continuity_receipt"]["covers_to"] = waiting[1]["occurred_at"]
        expiry_metrics = aggregator.compute_driver_ownership_metrics(pr, waiting, start, cutoff)
        self.assertEqual(expiry_metrics["status"], "PARTIAL")
        self.assertGreaterEqual(expiry_metrics["unknown_sec"], 120.0)
        executing = [
            dict(row, event_type="execution_observed", state="executing", worker_id="worker-1")
            for row in rows
        ]
        zero_metrics = aggregator.compute_driver_ownership_metrics(pr, executing, start, cutoff)
        self.assertEqual(zero_metrics["status"], "COMPLETE")
        self.assertEqual(zero_metrics["unattended_sec_lower_bound"], 0.0)
        self.assertEqual(zero_metrics["unknown_sec"], 0.0)

    def test_pickup_accepts_worker_started_and_rejects_unproved_or_conflicting_start(self):
        aggregator = MetricsAggregator()
        pr = {"repo": self.REPO, "number": 7, "headRefOid": self.HEAD}
        events = self._collect(self._fixture())
        worker_start = json.loads(json.dumps(events))
        worker_start[5]["event_type"] = "worker_started"
        pairs, stats = aggregator.adapt_transition_event_receipts(worker_start, [pr])
        review_pickup = next(row for row in pairs if row["name"] == "review_return -> next_substantive_action")
        self.assertEqual(
            aggregator.compute_interval_duration(review_pickup["start_at"], review_pickup["end_at"])["duration_sec"],
            180.0,
        )
        self.assertGreater(stats["receipt_pairs"], 0)

        paused_start = json.loads(json.dumps(events))
        paused_start[5].update(
            state="paused", wait_reason="operator_pause", worker_id=None,
            result_receipt=None,
        )
        paused_pairs, _ = aggregator.adapt_transition_event_receipts(paused_start, [pr])
        self.assertFalse(any(row["name"] == "review_return -> next_substantive_action" for row in paused_pairs))

        conflicting_start = json.loads(json.dumps(events))
        conflicting_start.append(dict(events[5], result_receipt="different-proof"))
        conflicting_pairs, conflict_stats = aggregator.adapt_transition_event_receipts(conflicting_start, [pr])
        self.assertEqual(conflict_stats["receipt_event_conflicts"], 1)
        self.assertFalse(any(row["name"] == "review_return -> next_substantive_action" for row in conflicting_pairs))

    def test_duplicate_delivery_is_idempotent_and_missing_feed_is_unknown(self):
        cutoff = datetime(2026, 11, 18, 10, 15, tzinfo=timezone.utc)
        aggregator = MetricsAggregator(cutoff_dt=cutoff)
        pr = {"repo": self.REPO, "number": 7, "headRefOid": self.HEAD}
        rows = self._collect(self._fixture())
        mirrored = dict(rows[1], observed_at="2026-11-11T10:02:03Z")
        repeated = aggregator.compute_driver_ownership_metrics(pr, rows + [mirrored], cutoff - timedelta(days=7), cutoff)
        self.assertEqual(repeated["status"], "COMPLETE")
        self.assertEqual(repeated["unattended_sec_lower_bound"], 480.0)
        out_of_order = aggregator.compute_driver_ownership_metrics(
            pr, list(reversed(rows)), cutoff - timedelta(days=7), cutoff
        )
        self.assertEqual(out_of_order["status"], "COMPLETE")
        self.assertEqual(out_of_order["unattended_sec_lower_bound"], 480.0)
        missing = aggregator.compute_driver_ownership_metrics(pr, [], cutoff - timedelta(days=7), cutoff)
        self.assertEqual(missing["status"], "UNKNOWN")

    def test_published_receipt_replay_preserves_nested_attempt_identity(self):
        cutoff = datetime(2026, 11, 18, 10, 15, tzinfo=timezone.utc)
        start = cutoff - timedelta(days=7)
        aggregator = MetricsAggregator(cutoff_dt=cutoff)
        pr = {"repo": self.REPO, "number": 7, "headRefOid": self.HEAD}
        records = self._collect(self._fixture())
        expected = aggregator.compute_driver_ownership_metrics(pr, records, start, cutoff)
        with tempfile.TemporaryDirectory() as publisher_dir:
            bundle = Publisher(repo_path=publisher_dir).write_telemetry_bundle(
                {"w2_bounds": [format_iso_utc(start), format_iso_utc(cutoff)]},
                handoff_records=records,
            )
        retained_text = next(
            value for key, value in bundle.items() if key.endswith("retained_handoffs.jsonl")
        )
        replayed = [json.loads(line) for line in retained_text.splitlines() if line.strip()]
        self.assertEqual(
            replayed[1]["continuity_receipt"]["attempt_number"], 1
        )
        self.assertEqual(
            aggregator.compute_driver_ownership_metrics(pr, replayed, start, cutoff), expected
        )

    def test_partial_window_shows_verified_lower_bound_without_ranking(self):
        cutoff = datetime(2026, 11, 18, 10, 15, tzinfo=timezone.utc)
        receipts = self._collect(self._fixture()[:-1])
        pr = {
            "repo": self.REPO, "number": 7, "state": "OPEN", "headRefOid": self.HEAD,
            "createdAt": "2026-11-10T00:00:00Z", "updatedAt": "2026-11-11T10:00:00Z",
            "url": "https://github.com/example-org/repo-alpha/pull/7", "labels": [],
        }
        summary = MetricsAggregator(cutoff_dt=cutoff).aggregate_full_dataset(
            [pr], handoff_records=receipts,
            handoff_receipt_stats={"status": "COMPLETE", "files_scanned": 1},
            sources={"github": {"status": "COMPLETE", "cutoff": format_iso_utc(cutoff)}},
            now_dt=cutoff,
        )
        self.assertEqual(summary["open_prs_known_idle"], [])
        row = summary["open_prs_unknown_idle"][0]
        self.assertEqual(row["ownership_status"], "PARTIAL")
        self.assertEqual(row["ownership_unattended_sec_lower_bound"], 480.0)
        self.assertGreater(row["ownership_unknown_sec"], 0.0)
        self.assertIn("Verified Unattended Lower Bound", DashboardRenderer().render(summary))

    def test_open_pr_pickup_durations_are_limited_to_displayed_candidate(self):
        cutoff = datetime(2026, 11, 18, 10, 15, tzinfo=timezone.utc)
        rows = []
        for event in self._fixture():
            row = dict(event, candidate_sha="b" * 40)
            if isinstance(event.get("continuity_receipt"), dict):
                row["continuity_receipt"] = dict(event["continuity_receipt"], candidate_sha="b" * 40)
            rows.append(row)
        receipts = self._collect(rows)
        pr = {
            "repo": self.REPO, "number": 7, "state": "OPEN", "headRefOid": self.HEAD,
            "createdAt": "2026-11-10T00:00:00Z", "updatedAt": "2026-11-11T10:00:00Z",
            "url": "https://github.com/example-org/repo-alpha/pull/7", "labels": [],
        }
        summary = MetricsAggregator(cutoff_dt=cutoff).aggregate_full_dataset(
            [pr], handoff_records=receipts,
            handoff_receipt_stats={"status": "COMPLETE", "files_scanned": 1},
            sources={"github": {"status": "COMPLETE", "cutoff": format_iso_utc(cutoff)}},
            now_dt=cutoff,
        )
        row = summary["open_prs_unknown_idle"][0]
        self.assertEqual(row["ownership_status"], "UNKNOWN")
        self.assertEqual(row["review_return_to_pickup_median_sec"], "UNKNOWN")
        self.assertEqual(row["wake_to_pickup_median_sec"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
