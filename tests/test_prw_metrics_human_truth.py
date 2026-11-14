"""Behavioral contracts for truthful human intervention measurements."""

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.prw_metrics import (
    RETAINED_EPISODE_FIELDS,
    Collector,
    DashboardRenderer,
    MetricsAggregator,
    Publisher,
    sanitize_telemetry_file,
)


class TestHumanActorClassification(unittest.TestCase):
    def test_explicit_human_actor_is_independent_of_source_label(self):
        result = MetricsAggregator().compute_human_interventions([
            {
                "episode_id": "structured-dot",
                "actor_status": "human",
                "channel": "provider",
                "source_channel": "dot",
                "message_ids": ["m1", "m2"],
                "timestamp": "2026-11-07T10:00:00Z",
            },
        ])

        self.assertEqual(result["raw_human_messages"], 2)
        self.assertEqual(result["qualifying_episodes"], 1)
        self.assertEqual(result["channel_coverage"]["dot_history"], "TESTED_CONNECTOR_OK")

    def test_automated_unknown_and_source_only_rows_are_not_humans(self):
        result = MetricsAggregator().compute_human_interventions([
            {"episode_id": "bot", "actor_status": "automated", "origin": "human"},
            {"episode_id": "unknown", "actor_status": "unknown", "origin": "human"},
            {"episode_id": "generic-user", "origin": "user", "raw_message_count": 9},
            {"episode_id": "codex-transcript", "origin": "codex_rollout", "raw_message_count": 9},
            {"episode_id": "agy-transcript", "origin": "agy_transcript", "raw_message_count": 9},
        ])

        self.assertEqual(result["raw_human_messages"], 0)
        self.assertEqual(result["qualifying_episodes"], 0)

    def test_curated_legacy_human_origins_remain_declared_human(self):
        result = MetricsAggregator().compute_human_interventions([
            {"episode_id": "human", "origin": "human", "raw_message_count": 1},
            {"episode_id": "operator", "origin": "operator", "raw_message_count": 1},
            {"episode_id": "prompt", "origin": "user_prompt", "raw_message_count": 1},
        ])

        self.assertEqual(result["raw_human_messages"], 3)
        self.assertEqual(result["qualifying_episodes"], 3)

    def test_dot_rows_require_ids_and_a_parseable_timestamp(self):
        result = MetricsAggregator().compute_human_interventions([
            {
                "episode_id": "missing-id",
                "actor_status": "human",
                "channel": "dot",
                "message_ids": [],
                "timestamp": "2026-11-07T10:00:00Z",
            },
            {
                "episode_id": "bad-time",
                "actor_status": "human",
                "channel": "dot",
                "message_ids": ["m2"],
                "timestamp": "not-a-timestamp",
            },
        ])

        self.assertEqual(result["raw_human_messages"], 0)
        self.assertEqual(result["dot_page_tail_partial_count"], 2)
        self.assertEqual(
            result["channel_coverage"]["dot_history"],
            "PARTIAL_PAGE_TAIL_NO_MESSAGE_IDS_OR_TIMESTAMPS",
        )

    def test_null_or_string_message_ids_do_not_prove_dot_coverage(self):
        result = MetricsAggregator().compute_human_interventions([
            {
                "episode_id": "null-ids",
                "actor_status": "human",
                "channel": "dot",
                "message_ids": None,
                "timestamp": "2026-11-07T10:00:00Z",
            },
            {
                "episode_id": "string-ids",
                "actor_status": "human",
                "channel": "dot",
                "message_ids": "msg-17",
                "timestamp": "2026-11-07T10:01:00Z",
            },
        ])

        self.assertEqual(result["raw_human_messages"], 0)
        self.assertEqual(result["dot_page_tail_partial_count"], 2)
        self.assertEqual(result["raw_message_count_coverage"], "PARTIAL_MISSING_MESSAGE_IDS")
        self.assertEqual(
            result["channel_coverage"]["dot_history"],
            "PARTIAL_PAGE_TAIL_NO_MESSAGE_IDS_OR_TIMESTAMPS",
        )

    def test_undated_dot_source_channel_survives_window_scoping_as_partial(self):
        aggregator = MetricsAggregator()
        summary = aggregator.aggregate_full_dataset(
            prs=[],
            human_episodes=[{
                "episode_id": "undated-dot",
                "actor_status": "human",
                "source_channel": "dot",
                "message_ids": ["m1"],
            }],
            now_dt=aggregator.cutoff_dt,
        )

        self.assertEqual(
            summary["human_interventions"]["dot_page_tail_partial_count"], 1
        )

    def test_retention_keeps_actor_and_channel_evidence(self):
        self.assertTrue({"actor_status", "channel", "source_channel"} <= RETAINED_EPISODE_FIELDS)
        payload = sanitize_telemetry_file(
            "dashboards/prw/telemetry/window/human_episodes.jsonl",
            json.dumps({
                "episode_id": "e1",
                "actor_status": "human",
                "channel": "dot",
                "source_channel": "dot",
                "unapproved_extra": "drop",
            }),
        )

        self.assertEqual(json.loads(payload), {
            "episode_id": "e1",
            "actor_status": "human",
            "channel": "dot",
            "source_channel": "dot",
        })

    def test_actor_and_channel_survive_retained_bundle_readback(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            files = Publisher(repo_path=temp_dir).write_telemetry_bundle(
                None,
                human_episodes=[{
                    "episode_id": "e1",
                    "actor_status": "human",
                    "channel": "claude",
                    "source_namespace": "claude-session-1",
                    "message_ids": ["m1"],
                    "timestamp": "2026-11-07T10:00:00Z",
                }],
                window_slug="20261107",
            )
            for relpath, content in files.items():
                path = Path(temp_dir, relpath)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")

            retained = Collector(repos=[]).load_retained_telemetry(
                telemetry_dir=str(Path(temp_dir, "dashboards/prw/telemetry"))
            )

        episode = retained["human_episodes"][0]
        self.assertEqual(episode["actor_status"], "human")
        self.assertEqual(episode["channel"], "claude")
        self.assertEqual(episode["source_namespace"], "claude-session-1")


class TestHumanMessageIdentity(unittest.TestCase):
    def test_legacy_initial_duplicate_counts_once_and_later_followup_survives(self):
        result = MetricsAggregator().compute_human_interventions([
            {
                "episode_id": "same-task",
                "actor_status": "human",
                "raw_message_count": 3,
                "is_initial_assignment": True,
            },
            {
                "episode_id": "same-task",
                "actor_status": "human",
                "raw_message_count": 3,
                "is_initial_assignment": True,
            },
            {
                "episode_id": "same-task",
                "actor_status": "human",
                "message_ids": ["m1"],
                "label": "good",
            },
        ])

        self.assertEqual(result["raw_human_messages"], 4)
        self.assertEqual(result["initial_task_requests"], 3)
        self.assertEqual(result["qualifying_episodes"], 1)

    def test_message_ids_are_scoped_to_source_namespace(self):
        result = MetricsAggregator().compute_human_interventions([
            {
                "episode_id": "slack-e1",
                "actor_status": "human",
                "channel": "slack",
                "message_ids": [42],
            },
            {
                "episode_id": "dot-e1",
                "actor_status": "human",
                "channel": "dot",
                "message_ids": [42],
                "timestamp": "2026-11-07T10:00:00Z",
            },
        ])

        self.assertEqual(result["raw_human_messages"], 2)
        self.assertEqual(result["qualifying_episodes"], 2)

        shared_namespace = MetricsAggregator().compute_human_interventions([
            {
                "episode_id": "slack-shared",
                "actor_status": "human",
                "channel": "slack",
                "source_namespace": "shared-thread",
                "message_ids": ["m1"],
            },
            {
                "episode_id": "dot-shared",
                "actor_status": "human",
                "channel": "dot",
                "source_namespace": "shared-thread",
                "message_ids": ["m1"],
                "timestamp": "2026-11-07T10:00:00Z",
            },
        ])

        self.assertEqual(shared_namespace["raw_human_messages"], 1)
        self.assertEqual(shared_namespace["qualifying_episodes"], 1)

    def test_string_message_ids_are_invalid_and_missing_episode_identity_is_partial(self):
        result = MetricsAggregator().compute_human_interventions([
            {
                "actor_status": "human",
                "channel": "claude",
                "message_ids": "msg-17",
            },
            {
                "actor_status": "human",
                "channel": "claude",
                "message_ids": ["m1"],
            },
        ])

        self.assertEqual(result["raw_human_messages"], 1)
        self.assertEqual(result["qualifying_episodes"], 1)
        self.assertEqual(result["raw_message_count_coverage"], "PARTIAL_MISSING_MESSAGE_IDS")
        self.assertEqual(result["episode_identity_coverage"], "PARTIAL_MISSING_EPISODE_IDS")

    def test_split_initial_messages_count_before_episode_dedupe_and_followup_survives(self):
        result = MetricsAggregator().compute_human_interventions([
            {
                "episode_id": "same-task",
                "actor_status": "human",
                "message_ids": ["m1"],
                "is_initial_assignment": True,
            },
            {
                "episode_id": "same-task",
                "actor_status": "human",
                "message_ids": ["m2"],
                "is_initial_assignment": True,
            },
            {
                "episode_id": "same-task",
                "actor_status": "human",
                "message_ids": ["m3"],
                "label": "good",
            },
        ])

        self.assertEqual(result["raw_human_messages"], 3)
        self.assertEqual(result["initial_task_requests"], 2)
        self.assertEqual(result["qualifying_episodes"], 1)

    def test_full_message_mirrors_do_not_add_episodes_but_partial_overlap_does(self):
        result = MetricsAggregator().compute_human_interventions([
            {
                "episode_id": "e1",
                "actor_status": "human",
                "message_ids": ["m1", "m2"],
            },
            {
                "episode_id": "e2",
                "actor_status": "human",
                "message_ids": ["m1", "m2"],
            },
            {
                "actor_status": "human",
                "message_ids": ["m1", "m2"],
            },
            {
                "episode_id": "e3",
                "actor_status": "human",
                "message_ids": ["m2", "m3"],
            },
        ])

        self.assertEqual(result["raw_human_messages"], 3)
        self.assertEqual(result["qualifying_episodes"], 2)

    def test_partial_overlap_counts_unique_message_ids_and_episode_identity(self):
        result = MetricsAggregator().compute_human_interventions([
            {
                "episode_id": "e1",
                "actor_status": "human",
                "message_ids": ["m1", "m2"],
                "raw_message_count": 2,
            },
            {
                "episode_id": "e2",
                "actor_status": "human",
                "message_ids": ["m2", "m3"],
                "raw_message_count": 2,
            },
            {
                "episode_id": "e2",
                "actor_status": "human",
                "message_ids": ["m3", "m4"],
                "raw_message_count": 2,
            },
        ])

        self.assertEqual(result["raw_human_messages"], 4)
        self.assertEqual(result["qualifying_episodes"], 2)

    def test_legacy_counts_are_retained_but_marked_partial_without_ids(self):
        result = MetricsAggregator().compute_human_interventions([
            {"episode_id": "legacy", "origin": "human", "raw_message_count": 3},
        ])

        self.assertEqual(result["raw_human_messages"], 3)
        self.assertEqual(result["raw_message_count_coverage"], "PARTIAL_MISSING_MESSAGE_IDS")
        rendered = DashboardRenderer().render({"human_interventions": result})
        self.assertIn("PARTIAL_MISSING_MESSAGE_IDS", rendered)


class TestHumanLabelAdjudication(unittest.TestCase):
    def _label_breakdown(self, **episode_fields):
        episode = {
            "episode_id": "e1",
            "actor_status": "human",
            "message_ids": ["m1"],
        }
        episode.update(episode_fields)
        result = MetricsAggregator().compute_human_interventions([episode])
        return result["label_breakdown"]

    def test_explicit_adjudicated_label_wins_over_annotator_disagreement(self):
        labels = self._label_breakdown(
            label="good",
            annotator_a={"label": "good"},
            annotator_b={"label": "bad"},
        )

        self.assertEqual(labels["good"], 1)
        self.assertEqual(labels["mixed"], 0)

    def test_unresolved_annotator_disagreement_is_unknown(self):
        labels = self._label_breakdown(
            annotator_a={"label": "good"},
            annotator_b={"label": "bad"},
        )

        self.assertEqual(labels["unknown"], 1)
        self.assertEqual(labels["mixed"], 0)

    def test_agreed_mixed_label_is_preserved(self):
        labels = self._label_breakdown(
            annotator_a={"label": "mixed"},
            annotator_b={"label": "mixed"},
        )

        self.assertEqual(labels["mixed"], 1)


class TestEmptyDurationDistribution(unittest.TestCase):
    def test_empty_statistics_are_unknown_and_render_as_unknown(self):
        aggregator = MetricsAggregator()
        empty_stats = aggregator.summarize_window_cohort([])
        self.assertEqual(empty_stats["n"], 0)
        self.assertEqual(empty_stats["all_median_hours"], "UNKNOWN")
        self.assertEqual(empty_stats["all_p75_hours"], "UNKNOWN")
        self.assertEqual(empty_stats["all_p50_hours"], "UNKNOWN")
        self.assertEqual(empty_stats["all_p90_hours"], "UNKNOWN")
        self.assertEqual(empty_stats["all_p99_hours"], "UNKNOWN")
        summary = MetricsAggregator().aggregate_full_dataset(
            prs=[{
                "repo": "o/r",
                "number": 1,
                "state": "OPEN",
                "createdAt": "2026-11-07T00:00:00Z",
                "mergedAt": None,
            }],
            now_dt=aggregator.cutoff_dt,
        )

        row = summary["repo_comparison"][0]
        self.assertEqual(summary["w2_merged_cohort_n"], 0)
        self.assertEqual(row["all_median_hours"], "UNKNOWN")
        self.assertEqual(row["all_p75_hours"], "UNKNOWN")
        self.assertEqual(row["d14_all_n"], 0)
        self.assertEqual(row["d14_all_p50_hours"], "UNKNOWN")
        rendered = DashboardRenderer().render(summary)
        self.assertIn("UNKNOWN", rendered)
        self.assertNotRegex(rendered, r"(?<![0-9.])0\.0h\b")

    def test_actual_zero_duration_remains_numeric_zero(self):
        result = MetricsAggregator().summarize_window_cohort([
            {"createdAt": "2026-11-07T10:00:00Z", "mergedAt": "2026-11-07T10:00:00Z"},
        ])

        self.assertEqual(result["all_median_hours"], 0.0)
        self.assertEqual(result["all_p75_hours"], 0.0)

    def test_fourteen_day_creation_to_merge_percentiles_keep_backlog_separate(self):
        cutoff = datetime(2026, 11, 8, tzinfo=timezone.utc)
        aggregator = MetricsAggregator(cutoff_dt=cutoff)
        prs = []
        for number, merged_at, duration_hours in (
            (1, "2026-10-28T00:00:00Z", 1),
            (2, "2026-10-29T00:00:00Z", 2),
            (3, "2026-11-02T00:00:00Z", 10),
            (4, "2026-11-03T00:00:00Z", 200),
        ):
            merged = datetime.fromisoformat(merged_at.replace("Z", "+00:00"))
            created = (merged - timedelta(hours=duration_hours)).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
            prs.append({
                "repo": "example-org/repo-alpha", "number": number, "state": "MERGED",
                "mergedAt": merged_at, "createdAt": created,
            })

        summary = aggregator.aggregate_full_dataset(prs=prs, now_dt=cutoff)
        row = next(
            r for r in summary["repo_comparison"] if r["repo"] == "Combined (All Repos)"
        )
        self.assertEqual(row["d14_all_n"], 4)
        self.assertEqual(
            [row[f"d14_all_p{p}_hours"] for p in (50, 90, 99)],
            [2.0, 200.0, 200.0],
        )
        self.assertEqual(row["d14_comp_n"], 3)
        self.assertEqual(
            [row[f"d14_comp_p{p}_hours"] for p in (50, 90, 99)],
            [2.0, 10.0, 10.0],
        )
        self.assertEqual(row["d14_backlog_n"], 1)
        self.assertEqual(
            [row[f"d14_backlog_p{p}_hours"] for p in (50, 90, 99)],
            [200.0, 200.0, 200.0],
        )



class TestInvalidIdentityRetention(unittest.TestCase):
    def test_invalid_id_evidence_survives_sanitized_replay(self):
        for invalid in (None, {"private": "payload-must-not-survive"}):
            with self.subTest(invalid=invalid):
                row = {
                    "actor_status": "human", "origin": "dot_history",
                    "episode_id": "partial-dot", "message_ids": ["m1", invalid],
                    "timestamp": "2026-11-08T10:00:00Z",
                }
                before = MetricsAggregator().compute_human_interventions([row])
                encoded = sanitize_telemetry_file(
                    "dashboards/prw/telemetry/20261101/human_episodes.jsonl",
                    json.dumps(row) + "\n",
                )
                retained = json.loads(encoded.strip())
                after = MetricsAggregator().compute_human_interventions([retained])
                self.assertEqual(retained["message_ids"], ["m1", None])
                self.assertNotIn("payload-must-not-survive", encoded)
                self.assertEqual(after["raw_human_messages"], before["raw_human_messages"])
                self.assertEqual(after["qualifying_episodes"], before["qualifying_episodes"])
                self.assertEqual(after["channel_coverage"], before["channel_coverage"])

if __name__ == "__main__":
    unittest.main()
