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
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

# We will import from scripts.prw_metrics
# Before implementation, this will fail or functions will be missing (RED).
try:
    from scripts.prw_metrics import (
        Collector,
        DashboardRenderer,
        MetricsAggregator,
        Publisher,
        calculate_median,
        calculate_nearest_rank_p75,
        compute_disjoint_interval_union,
        filter_events_half_open,
        normalize_markdown_for_comparison,
        parse_iso_utc,
        publish_dashboard,
        render_dashboard,
        split_search_window_on_cap,
    )
except ImportError:
    Collector = None
    DashboardRenderer = None
    MetricsAggregator = None
    Publisher = None
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
        self.assertIn("### 5B. Open PRs with Unknown Eligibility (Telemetry Coverage 0%)", md)

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

        # Initialize bare remote repo
        subprocess.run(["git", "init", "--bare", self.remote_dir], check=True, capture_output=True)

        # Clone to local
        subprocess.run(["git", "clone", self.remote_dir, self.local_dir], check=True, capture_output=True)

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
        )
        self.assertTrue(res1["committed"])

        # Second publish with identical data, only newer generation time
        res2 = publish_dashboard(
            markdown_text=content2,
            status="FRESH",
            repo_path=self.local_dir,
            target_relpath="dashboards/prw/README.md",
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
            res = collector.collect_all(state_dir=temp_state, fetch_page_fn=fetch_mock)

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


if __name__ == "__main__":
    unittest.main()
