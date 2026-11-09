"""Per-PR steering aggregation stays evidence-bound and coverage-aware."""

import json
import re
import tempfile
import unittest

from scripts.prw_metrics import DashboardRenderer, Publisher, aggregate_native_human_steering


class NativeHumanSteeringTests(unittest.TestCase):
    def setUp(self):
        self.prs = [
            {
                "repo": "example/repo", "number": 5, "headRefName": "topic",
                "headRefOid": "sha-pr5", "state": "CLOSED",
                "createdAt": "2026-10-01T00:00:00Z", "closedAt": "2026-10-10T00:00:00Z",
                "url": "https://github.com/example/repo/pull/5",
            },
            {
                "repo": "example/repo", "number": 6, "headRefName": "topic",
                "headRefOid": "sha-pr6", "state": "OPEN",
                "createdAt": "2026-10-11T00:00:00Z", "closedAt": None,
                "url": "https://github.com/example/repo/pull/6",
            },
            {
                "repo": "example/repo", "number": 7, "headRefName": "topic",
                "headRefOid": "sha-pr7", "state": "OPEN",
                "createdAt": "2026-10-11T00:30:00Z", "closedAt": None,
                "url": "https://github.com/example/repo/pull/7",
            },
        ]
        self.stats = {
            "status": "PARTIAL", "runtime_coverage": "Claude/Codex roots only",
            "human_candidates": 6, "human_verified": 5, "human_unannotated": 5,
        }
        self.events = [
            {
                "event_id": "direct-1", "provider": "anthropic", "timestamp": "2026-10-05T10:00:00Z",
                "origin_status": "verified_human", "pr_binding": {"pr": "example/repo#5"},
                "episode_id": "episode-a", "episode_role": "followup", "quality_label": "bad",
                "source_fingerprint": "sha256:direct",
            },
            {
                "event_id": "branch-1", "provider": "codex", "timestamp": "2026-10-06T10:00:00Z",
                "origin_status": "verified_human", "repository": "example/repo", "git_branch": "topic",
                "episode_id": "episode-a", "episode_role": "followup", "quality_label": "bad",
                "source_fingerprint": "sha256:branch",
            },
            {
                "event_id": "initial-1", "provider": "codex", "timestamp": "2026-10-07T10:00:00Z",
                "origin_status": "verified_human", "repository": "example/repo", "git_branch": "topic",
                "episode_id": "initial-episode", "episode_role": "initial",
                "message_kind": "initial_task", "source_fingerprint": "sha256:initial",
            },
            {
                "event_id": "candidate-1", "provider": "codex", "timestamp": "2026-10-08T10:00:00Z",
                "origin_status": "unverified_candidate", "repository": "example/repo", "git_branch": "topic",
                "source_fingerprint": "sha256:candidate",
            },
            {
                "event_id": "ambiguous-1", "provider": "codex", "timestamp": "2026-10-11T01:00:00Z",
                "origin_status": "verified_human", "repository": "example/repo", "git_branch": "topic",
                "source_fingerprint": "sha256:ambiguous",
            },
            {
                "event_id": "unbound-1", "provider": "anthropic", "timestamp": "2026-10-12T10:00:00Z",
                "origin_status": "verified_human", "source_fingerprint": "sha256:unbound",
            },
        ]

    def test_direct_and_branch_associations_remain_separate_and_episode_labels_are_explicit(self):
        result = aggregate_native_human_steering(
            self.events, self.prs,
            window_start="2026-10-01T00:00:00Z", window_end="2026-10-20T00:00:00Z",
            source_stats=self.stats,
        )
        rows = {row["pr"]: row for row in result["per_pr"]}
        pr5 = rows["example/repo#5"]
        self.assertEqual(pr5["raw_verified_messages"], 3)
        self.assertEqual(pr5["direct_verified_messages"], 1)
        self.assertEqual(pr5["branch_associated_verified_messages"], 2)
        self.assertEqual(pr5["branch_associated_candidates"], 1)
        self.assertEqual(pr5["initial_requests"], 1)
        self.assertEqual(pr5["followup_episodes"], 1)
        self.assertEqual(pr5["episodes_by_quality"]["bad"], 1)
        self.assertEqual(pr5["episodes_by_quality"]["good"], 0)
        self.assertIn("best_effort_repo_branch_event_time", pr5["association_basis"])
        self.assertIn("reviewed_direct_pr_binding", pr5["association_basis"])
        self.assertEqual(rows["example/repo#6"]["raw_verified_messages"], 0)
        self.assertEqual(rows["example/repo#7"]["raw_verified_messages"], 0)
        self.assertEqual(rows["example/repo#6"]["coverage_status"], "UNKNOWN")

    def test_unassigned_and_ambiguous_records_remain_visible_in_coverage(self):
        result = aggregate_native_human_steering(
            self.events, self.prs,
            window_start="2026-10-01T00:00:00Z", window_end="2026-10-20T00:00:00Z",
            source_stats=self.stats,
        )
        coverage = result["coverage"]
        self.assertEqual(coverage["verified_messages"], 5)
        self.assertEqual(coverage["assigned_verified_messages"], 3)
        self.assertEqual(coverage["unassigned_verified_messages"], 2)
        self.assertEqual(coverage["ambiguous_branch_messages"], 1)
        self.assertEqual(coverage["unassigned_candidates"], 0)
        self.assertEqual(coverage["source_status"], "PARTIAL")
        self.assertIn("Claude/Codex roots only", coverage["runtime_coverage"])

    def test_missing_repository_uses_only_globally_unique_branch_and_marks_low_confidence(self):
        prs = [
            {
                "repo": "example/skills", "number": 1, "headRefName": "unique-feature",
                "headRefOid": "sha-1", "createdAt": "2026-10-01T00:00:00Z",
                "closedAt": None, "url": "https://github.com/example/skills/pull/1",
            },
            {
                "repo": "example/frontend", "number": 2, "headRefName": "main",
                "headRefOid": "sha-2", "createdAt": "2026-10-01T00:00:00Z",
                "closedAt": None, "url": "https://github.com/example/frontend/pull/2",
            },
            {
                "repo": "example/worldai", "number": 3, "headRefName": "main",
                "headRefOid": "sha-3", "createdAt": "2026-10-01T00:00:00Z",
                "closedAt": None, "url": "https://github.com/example/worldai/pull/3",
            },
        ]
        events = [
            {
                "event_id": "unique-branch", "provider": "codex",
                "timestamp": "2026-10-05T00:00:00Z", "origin_status": "verified_human",
                "git_branch": "unique-feature", "branch_source": "recorded_git_branch",
            },
            {
                "event_id": "ambiguous-main", "provider": "codex",
                "timestamp": "2026-10-05T00:00:00Z", "origin_status": "verified_human",
                "git_branch": "main", "branch_source": "recorded_git_branch",
            },
        ]
        result = aggregate_native_human_steering(
            events, prs,
            window_start="2026-10-01T00:00:00Z", window_end="2026-10-20T00:00:00Z",
            source_stats=self.stats,
        )
        rows = {row["pr"]: row for row in result["per_pr"]}
        unique = rows["example/skills#1"]
        self.assertEqual(unique["raw_verified_messages"], 1)
        self.assertEqual(unique["branch_only_associated_verified_messages"], 1)
        self.assertEqual(unique["branch_associated_verified_messages"], 0)
        self.assertEqual(unique["association_confidence"], "BRANCH_ONLY_LOW")
        self.assertIn("best_effort_branch_only_event_time", unique["association_basis"])
        self.assertIn("source:recorded_git_branch", unique["association_basis"])
        self.assertEqual(result["coverage"]["branch_only_messages"], 1)
        self.assertEqual(result["coverage"]["ambiguous_branch_messages"], 1)
        self.assertEqual(result["coverage"]["unassigned_verified_messages"], 1)

    def test_rendered_tables_have_matching_gfm_columns_and_empty_handoffs_are_not_collected(self):
        steering = aggregate_native_human_steering(
            self.events[:3], self.prs,
            window_start="2026-10-01T00:00:00Z", window_end="2026-10-20T00:00:00Z",
            source_stats=self.stats,
        )
        renderer = DashboardRenderer()
        empty = renderer.render({"human_summary": steering, "handoffs": [
            {"name": "review_return -> next_action", "observed_n": 0, "total_n": 0,
             "median_sec": None, "status": "UNKNOWN"},
        ]})
        self.assertIn("NOT COLLECTED", empty)
        self.assertNotIn("| Handoff Transition |", empty)
        self.assertIn("| PR | Human messages | Association | Reviewed follow-up episodes |", empty)

        measured = renderer.render({"human_summary": steering, "handoffs": [
            {"name": "review_return -> next_action", "observed_n": 1, "total_n": 2,
             "median_sec": 60, "status": "PARTIAL"},
        ]})
        self.assertIn("| Handoff Transition |", measured)
        self.assertIn("review_return -> next_action", measured)

        lines = measured.splitlines()
        for index, line in enumerate(lines[:-1]):
            if not line.startswith("|") or not lines[index + 1].startswith("|"):
                continue
            header = [cell.strip() for cell in line.strip("|").split("|")]
            delimiter = [cell.strip() for cell in lines[index + 1].strip("|").split("|")]
            if not delimiter or not all(re.fullmatch(r":?-{3,}:?", cell) for cell in delimiter):
                continue
            self.assertEqual(len(header), len(delimiter), line)
            row_index = index + 2
            while row_index < len(lines) and lines[row_index].startswith("|"):
                row = [cell.strip() for cell in lines[row_index].strip("|").split("|")]
                self.assertEqual(len(header), len(row), lines[row_index])
                row_index += 1

    def test_per_pr_rows_survive_existing_summary_snapshot_projection(self):
        result = aggregate_native_human_steering(
            self.events[:3], self.prs,
            window_start="2026-10-01T00:00:00Z", window_end="2026-10-20T00:00:00Z",
            source_stats=self.stats,
        )
        with tempfile.TemporaryDirectory() as directory:
            bundle = Publisher(repo_path=directory).write_telemetry_bundle({
                "human_summary": result,
                "w2_bounds": ["2026-10-01", "2026-10-20"],
            })
        snapshot = next(value for key, value in bundle.items()
                        if key.endswith("/summary_snapshot.json"))
        retained = json.loads(snapshot)["human_summary"]
        self.assertEqual(retained["per_pr"][0]["pr"], "example/repo#5")
        self.assertEqual(retained["per_pr"][0]["raw_verified_messages"], 3)
        self.assertEqual(retained["per_pr"][0]["episodes_by_quality"]["bad"], 1)

    def test_event_time_disambiguates_reused_branch_with_low_context_confidence(self):
        prs = [
            {
                "repo": "example/repo", "number": 1, "headRefName": "feature/reused",
                "headRefOid": "sha-old", "state": "CLOSED",
                "createdAt": "2026-10-01T00:00:00Z", "closedAt": "2026-10-04T00:00:00Z",
                "url": "https://github.com/example/repo/pull/1",
            },
            {
                "repo": "example/repo", "number": 2, "headRefName": "feature/reused",
                "headRefOid": "sha-new", "state": "OPEN",
                "createdAt": "2026-10-05T00:00:00Z", "closedAt": None,
                "url": "https://github.com/example/repo/pull/2",
            },
        ]
        event = {
            "event_id": "reused-branch", "provider": "claude",
            "timestamp": "2026-10-05T10:00:00Z", "origin_status": "verified_human",
            "repository": "example/repo", "git_branch": "feature/reused",
            "branch_source": "claude_session_metadata_low_confidence",
            "branch_basis": "first_64_session_records_not_event_time",
        }
        result = aggregate_native_human_steering(
            [event], prs,
            window_start="2026-10-01T00:00:00Z", window_end="2026-10-20T00:00:00Z",
            source_stats=self.stats,
        )
        rows = {row["pr"]: row for row in result["per_pr"]}
        self.assertEqual(rows["example/repo#1"]["coverage_status"], "UNKNOWN")
        self.assertEqual(rows["example/repo#2"]["branch_associated_verified_messages"], 1)
        self.assertEqual(rows["example/repo#2"]["association_confidence"], "LOW_BEST_EFFORT")
        self.assertIn("best_effort_repo_branch_event_time",
                      rows["example/repo#2"]["association_basis"])
    def test_unique_repo_branch_snapshot_can_associate_without_time_overlap_at_low_confidence(self):
        prs = [{
            "repo": "example/repo", "number": 8, "headRefName": "older-branch",
            "headRefOid": "sha-pr8", "state": "CLOSED",
            "createdAt": "2026-10-01T00:00:00Z", "closedAt": "2026-10-04T00:00:00Z",
            "url": "https://github.com/example/repo/pull/8",
        }]
        event = {
            "event_id": "late-followup", "provider": "codex",
            "timestamp": "2026-10-05T00:00:00Z", "origin_status": "verified_human",
            "repository": "example/repo", "git_branch": "older-branch",
            "branch_source": "claude_session_metadata_low_confidence",
            "branch_basis": "first_64_session_records_not_event_time",
        }
        result = aggregate_native_human_steering(
            [event], prs,
            window_start="2026-10-01T00:00:00Z", window_end="2026-10-20T00:00:00Z",
            source_stats=self.stats,
        )
        row = result["per_pr"][0]
        self.assertEqual(row["branch_associated_verified_messages"], 1)
        self.assertEqual(row["association_confidence"], "BRANCH_SNAPSHOT_LOW")
        self.assertIn("unique_repo_branch_snapshot", row["association_basis"])
        self.assertIn("context:first_64_session_records_not_event_time", row["association_basis"])

    def test_reviewed_unassigned_context_suppresses_branch_fallback_and_counts_nudge(self):
        event = {
            "event_id": "multi-pr", "provider": "claude", "timestamp": "2026-10-05T10:00:00Z",
            "origin_status": "verified_human", "actor_kind": "human",
            "repository": "example/repo", "git_branch": "topic",
            "original_associated_pr": "example/repo#5",
            "context_pr_decision": "unassigned_multi_pr",
            "context_associated_pr": None, "effective_associated_pr": None,
            "association_method": "context_semantic_unassigned",
            "effective_association_confidence": "UNASSIGNED_CONTEXT",
            "episode_id": "multi-episode", "episode_role": "followup",
            "quality_label": "bad", "message_kind": "continuation/followthrough_nudge",
            "human_nudge_eligible": True,
        }
        result = aggregate_native_human_steering(
            [event], self.prs,
            window_start="2026-10-01T00:00:00Z", window_end="2026-10-20T00:00:00Z",
            source_stats=self.stats,
        )
        pr5 = next(row for row in result["per_pr"] if row["pr"] == "example/repo#5")
        self.assertEqual(pr5["raw_verified_messages"], 0)
        self.assertEqual(result["coverage"]["unassigned_verified_messages"], 1)
        self.assertEqual(result["coverage"]["multi_pr_unassigned_messages"], 1)
        self.assertEqual(result["coverage"]["human_nudge_messages"], 1)

    def test_context_override_uses_effective_pr_and_separates_nudge_categories(self):
        event = {
            "event_id": "context-override", "provider": "claude", "timestamp": "2026-10-05T10:00:00Z",
            "origin_status": "verified_human", "actor_kind": "human",
            "repository": "example/repo", "git_branch": "topic",
            "original_associated_pr": "example/repo#5",
            "context_pr_decision": "override",
            "context_associated_pr": "example/repo#6", "effective_associated_pr": "example/repo#6",
            "association_method": "context_override",
            "effective_association_confidence": "LOW_BEST_EFFORT_CONTEXT",
            "episode_id": "followup-6", "episode_role": "followup",
            "quality_label": "mixed", "message_kind": "continuation/followthrough_nudge",
            "human_nudge_eligible": True,
        }
        result = aggregate_native_human_steering(
            [event], self.prs,
            window_start="2026-10-01T00:00:00Z", window_end="2026-10-20T00:00:00Z",
            source_stats=self.stats,
        )
        rows = {row["pr"]: row for row in result["per_pr"]}
        self.assertEqual(rows["example/repo#5"]["raw_verified_messages"], 0)
        pr6 = rows["example/repo#6"]
        self.assertEqual(pr6["context_associated_verified_messages"], 1)
        self.assertEqual(pr6["association_confidence"], "LOW_BEST_EFFORT_CONTEXT")
        self.assertEqual(pr6["human_nudge_messages"], 1)
        self.assertEqual(pr6["human_nudge_episodes"], 1)
        self.assertEqual(pr6["message_kind_counts"]["continuation/followthrough_nudge"], 1)
        self.assertEqual(pr6["episodes_by_quality"]["mixed"], 1)

    def test_initial_episode_role_does_not_infer_initial_task_from_nudge_kind(self):
        event = {
            "event_id": "first-captured-nudge", "provider": "claude",
            "timestamp": "2026-10-06T10:00:00Z", "origin_status": "verified_human",
            "actor_kind": "human", "pr_binding": {"pr": "example/repo#5"},
            "episode_id": "episode-first-captured", "episode_role": "initial",
            "message_kind": "continuation/followthrough_nudge",
            "human_nudge_eligible": True, "quality_label": "unknown",
        }
        result = aggregate_native_human_steering(
            [event], self.prs,
            window_start="2026-10-01T00:00:00Z", window_end="2026-10-20T00:00:00Z",
            source_stats=self.stats,
        )
        pr5 = next(row for row in result["per_pr"] if row["pr"] == "example/repo#5")
        self.assertEqual(pr5["initial_requests"], 0)
        self.assertEqual(pr5["message_kind_counts"]["continuation/followthrough_nudge"], 1)
        self.assertEqual(pr5["human_nudge_messages"], 1)
        self.assertEqual(pr5["human_nudge_episodes"], 1)

    def test_automated_actor_override_excludes_native_human_role_and_nudge(self):
        event = {
            "event_id": "bot-watch", "provider": "claude", "timestamp": "2026-10-05T10:00:00Z",
            "origin_status": "verified_human", "actor_kind": "automated_watch",
            "pr_binding": {"pr": "example/repo#5"},
            "episode_id": "bot-episode", "episode_role": "followup",
            "quality_label": "bad", "message_kind": "continuation/followthrough_nudge",
            "human_nudge_eligible": False,
        }
        result = aggregate_native_human_steering(
            [event], self.prs,
            window_start="2026-10-01T00:00:00Z", window_end="2026-10-20T00:00:00Z",
            source_stats=self.stats,
        )
        pr5 = next(row for row in result["per_pr"] if row["pr"] == "example/repo#5")
        self.assertEqual(result["coverage"]["automated_excluded_messages"], 1)
        self.assertEqual(result["coverage"]["verified_messages"], 0)
        self.assertEqual(pr5["raw_verified_messages"], 0)
        self.assertEqual(pr5["human_nudge_messages"], 0)

    def test_candidate_metadata_never_inflates_verified_message_counts(self):
        candidates = [dict(
            self.events[3], event_id="unverified-1", origin_status="unverified_candidate",
            pr_binding={"pr": "example/repo#5"},
        )]
        result = aggregate_native_human_steering(
            candidates, self.prs,
            window_start="2026-10-01T00:00:00Z", window_end="2026-10-20T00:00:00Z",
            source_stats=self.stats,
        )
        pr5 = next(row for row in result["per_pr"] if row["pr"] == "example/repo#5")
        self.assertEqual(pr5["raw_verified_messages"], 0)
        self.assertEqual(pr5["direct_verified_messages"], 0)
        self.assertEqual(pr5["direct_candidates"], 1)
        self.assertEqual(pr5["coverage_status"], "CANDIDATE_ONLY")
