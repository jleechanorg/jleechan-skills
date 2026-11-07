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
        format_iso_utc,
        normalize_markdown_for_comparison,
        parse_iso_utc,
        parse_operational_title,
        publish_dashboard,
        redact_sensitive_excerpt,
        render_dashboard,
        split_search_window_on_cap,
        extract_github_repo_slug,
    )
except ImportError:
    Collector = None
    DashboardRenderer = None
    MetricsAggregator = None
    Publisher = None
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
        """Unassigned task-level episodes are preserved, and differing annotators resolve to mixed."""
        agg = MetricsAggregator()
        episodes = [
            # Unassigned task-level episode with differing annotators
            {
                "episode_id": "ep-task-unassigned",
                "is_bot": False,
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
        self.assertEqual(summary["label_breakdown"]["mixed"], 1)
        self.assertEqual(summary["label_breakdown"]["good"], 0)
        self.assertEqual(summary["label_breakdown"]["bad"], 0)

    def test_post_merge_intervention_counted_not_hidden(self):
        """Corrections occurring after merge are tracked as post-merge, never hidden."""
        agg = MetricsAggregator()
        episodes = [
            {
                "episode_id": "ep-post-merge",
                "is_bot": False,
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
                f.write(json.dumps({"episode_id": "ep-ret-1", "is_bot": False, "origin": "user", "raw_message_count": 1, "is_initial_assignment": False, "label": "good"}) + "\n")

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
        agg = MetricsAggregator()
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
        summary = agg.aggregate_full_dataset(prs=[], time_semantics_pilot=raw_events)
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
            {"name": "task_accepted -> merged", "number": 20, "repo": "example-org/repo-alpha", "candidate_sha": "sha20", "duration_sec": 3600.0, "attempt_number": 1},
            # 5. Duplicate of record 4 -> deduplicated
            {"name": "task_accepted -> merged", "number": 20, "repo": "example-org/repo-alpha", "candidate_sha": "sha20", "duration_sec": 3600.0, "attempt_number": 1},
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


if __name__ == "__main__":
    unittest.main()
