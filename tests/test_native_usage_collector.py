"""Deterministic metadata-only acquisition from explicit native history roots."""

import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scripts.native_usage_collector import (
    collect_native_history, load_normalized_history, write_normalized_history,
)
from scripts.prw_metrics import (
    _sanitize_usage_event_record,
    _usage_event_record,
    aggregate_usage,
    load_usage_events,
)


class NativeUsageCollectorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.claude = self.base / "claude-root"
        self.codex = self.base / "codex-root"
        self.claude.mkdir()
        self.codex.mkdir()
        self.cutoff = datetime(2026, 11, 10, tzinfo=timezone.utc)

    def tearDown(self):
        self.temp.cleanup()

    def _write(self, root, name, rows):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        return path

    def _codex_usage(self, timestamp, response_id, input_tokens=100):
        return {
            "type": "token_usage_record", "timestamp": timestamp, "response_id": response_id,
            "payload": {
                "turn_id": "turn-a",
                "usage": {
                    "input_tokens": input_tokens, "cached_input_tokens": 40,
                    "cache_write_input_tokens": 10, "output_tokens": 30,
                    "reasoning_output_tokens": 8, "total_tokens": input_tokens + 30,
                },
            },
        }

    def test_codex_per_response_usage_and_user_metadata_are_normalized_without_text(self):
        secret = "PRIVATE_PROMPT_MUST_NOT_BE_EXPORTED; incidental PR #999 is not a binding"
        rows = [
            {"type": "session_meta", "payload": {
                "id": "thread-codex", "cwd": "/fixture/cwd", "git_branch": "topic",
            }},
            {"type": "turn_context", "timestamp": "2026-10-28T09:00:00Z",
             "payload": {"turn_id": "turn-a", "model": "fixture-codex-model"}},
            {"type": "response_item", "timestamp": "2026-10-28T09:00:01Z",
             "payload": {"id": "prompt-1", "turn_id": "turn-a", "role": "user",
                         "content": [{"type": "input_text", "text": secret}]}},
            self._codex_usage("2026-10-28T09:00:02Z", "response-1"),
            self._codex_usage("2026-10-28T09:00:02Z", "response-1"),
        ]
        self._write(self.codex, "2026/11/rollout.jsonl", rows)
        data = collect_native_history([self.codex], cutoff=self.cutoff, days=14)
        self.assertEqual(len(data["usage_records"]), 2)
        usage = data["usage_records"][0]
        self.assertEqual(usage["provider"], "openai")
        self.assertEqual(usage["request_id"], "response-1")
        self.assertEqual(usage["model"], "fixture-codex-model")
        self.assertEqual(usage["raw_usage"]["input_tokens"], 60)
        self.assertEqual(usage["raw_usage"]["cache_read_input_tokens"], 40)
        self.assertEqual(usage["raw_usage"]["output_tokens"], 30)
        self.assertEqual(usage["raw_usage"]["output_tokens_details"]["thinking_tokens"], 8)
        self.assertEqual(usage["raw_usage"]["cache_write_input_tokens"], 10)
        normalized = load_usage_events(data["usage_records"])
        aggregate = aggregate_usage(normalized, [])
        event = aggregate["query_events"][0]
        self.assertEqual(event["total_tokens"], 130)
        self.assertTrue(event["token_complete"])
        self.assertEqual(event["cache_write_input_tokens"], 10)
        exported = _sanitize_usage_event_record(_usage_event_record(normalized[0]))
        self.assertEqual(exported["raw_usage"]["cache_write_input_tokens"], 10)
        absent = dict(data["usage_records"][0])
        absent["raw_usage"] = dict(absent["raw_usage"])
        absent["raw_usage"].pop("cache_write_input_tokens")
        absent_export = _sanitize_usage_event_record(
            _usage_event_record(load_usage_events([absent])[0])
        )
        self.assertIsNone(absent_export["raw_usage"]["cache_write_input_tokens"])
        self.assertEqual(data["stats"]["duplicate_usage_records"], 1)
        self.assertEqual(data["stats"]["pr_bound_usage_records"], 0)
        self.assertEqual(data["usage_records"][0].get("attributions", []), [])
        self.assertEqual(data["stats"]["human_candidates"], 1)
        self.assertEqual(data["stats"]["human_verified"], 0)
        human = data["human_records"][0]
        self.assertEqual(human["origin_status"], "unverified_candidate")
        self.assertEqual(human["turn_id"], "turn-a")
        self.assertTrue(human["source_fingerprint"].startswith("sha256:"))
        encoded = json.dumps(data["export_records"], sort_keys=True)
        self.assertNotIn(secret, encoded)
        self.assertNotIn(str(self.codex), encoded)

    def test_conflicting_response_observation_remains_unknown_not_first_priced(self):
        self._write(self.codex, "rollout.jsonl", [
            {"type": "turn_context", "payload": {"turn_id": "turn-a", "model": "fixture-codex-model"}},
            self._codex_usage("2026-10-28T09:00:02Z", "response-1", 100),
            self._codex_usage("2026-10-28T09:00:03Z", "response-1", 120),
        ])
        data = collect_native_history([self.codex], cutoff=self.cutoff, days=14)
        events = load_usage_events(data["usage_records"])
        summary = aggregate_usage(events, [])
        self.assertEqual(summary["source_records"], 2)
        self.assertEqual(summary["event_count"], 1)
        self.assertEqual(summary["unknown_event_count"], 1)
        self.assertEqual(summary["known_cost_usd"], 0)
        self.assertIsNone(summary["query_events"][0]["total_tokens"])
        self.assertFalse(summary["query_events"][0]["token_complete"])

    def test_append_new_records_preserves_prior_candidate_id_and_exports_new_request_once(self):
        path = self._write(self.codex, "rollout.jsonl", [
            {"type": "session_meta", "payload": {"id": "stable-thread"}},
            {"type": "turn_context", "payload": {"turn_id": "turn-a", "model": "fixture-codex-model"}},
            {"type": "response_item", "timestamp": "2026-10-28T09:00:01Z",
             "payload": {"role": "user", "content": "candidate one"}},
            self._codex_usage("2026-10-28T09:00:02Z", "response-1"),
        ])
        first = collect_native_history([self.codex], cutoff=self.cutoff, days=14)
        first_event_id = first["human_records"][0]["event_id"]
        export_a = self.base / "first.jsonl"
        write_normalized_history(export_a, first["export_records"])

        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({
                "type": "response_item", "timestamp": "2026-10-28T09:01:01Z",
                "payload": {"role": "user", "content": "candidate two"},
            }) + "\n")
            stream.write(json.dumps(
                self._codex_usage("2026-10-28T09:01:02Z", "response-2")
            ) + "\n")
        second = collect_native_history([self.codex], cutoff=self.cutoff, days=14)
        export_b = self.base / "second.jsonl"
        write_normalized_history(export_b, second["export_records"])

        self.assertEqual(second["human_records"][0]["event_id"], first_event_id)
        self.assertEqual(second["stats"]["human_candidates"], 2)
        self.assertEqual(second["stats"]["usage_records_in_window"], 2)
        self.assertEqual(
            [event["request_id"] for event in second["usage_records"]].count("response-2"),
            1,
        )
        self.assertNotEqual(export_a.read_bytes(), export_b.read_bytes())

    def test_utc_window_edges_undated_and_naive_timestamps_are_counted(self):
        start = "2026-10-27T00:00:00Z"
        rows = [
            {"type": "turn_context", "payload": {"turn_id": "turn-a", "model": "fixture-codex-model"}},
            self._codex_usage(start, "at-start"),
            self._codex_usage("2026-10-26T23:59:59.999Z", "before-start"),
            self._codex_usage("2026-11-10T00:00:00Z", "at-cutoff"),
            self._codex_usage("2026-10-28T00:00:00", "naive"),
            {"type": "token_usage_record", "response_id": "undated",
             "payload": {"turn_id": "turn-a", "usage": {"input_tokens": 3}}},
        ]
        self._write(self.codex, "rollout.jsonl", rows)
        data = collect_native_history([self.codex], cutoff=self.cutoff, days=14)
        self.assertEqual([row["request_id"] for row in data["usage_records"]], ["at-start"])
        self.assertEqual(data["stats"]["outside_window_records"], 2)
        self.assertEqual(data["stats"]["undated_records"], 2)

    def test_claude_origin_and_reviewed_annotations_are_explicit_and_repeatable(self):
        rows = [
            {"type": "user", "timestamp": "2026-11-08T10:00:00Z", "promptId": "p-1",
             "userType": "human", "promptSource": "typed", "turnOrigin": "human",
             "sessionId": "claude-session",
             "message": {"role": "user", "content": [{"type": "text",
                         "text": "PRIVATE_CLAUDE_PROMPT_MUST_NOT_LEAK"}]}},
            {"type": "assistant", "timestamp": "2026-11-08T10:00:01Z", "requestId": "req-1",
             "sessionId": "claude-session",
             "message": {"id": "msg-1", "model": "claude-test",
                         "usage": {"input_tokens": 10, "output_tokens": 2}}},
        ]
        self._write(self.claude, "project/session.jsonl", rows)
        initial = collect_native_history([self.claude], cutoff=self.cutoff, days=14)
        human = initial["human_records"][0]
        self.assertEqual(human["origin_status"], "verified_human")
        self.assertEqual(human["prompt_source"], "typed")
        self.assertNotIn("episode_role", human)

        annotation_path = self.base / "reviewed.jsonl"
        annotation_path.write_text(json.dumps({
            "event_id": human["event_id"], "human_origin": "verified_human",
            "episode_role": "initial", "quality_label": "GOOD", "score": 2.5,
            "score_source": "reviewed_annotation", "review_id": "review-1",
        }) + "\n", encoding="utf-8")
        first = collect_native_history(
            [self.claude], cutoff=self.cutoff, days=14, annotation_path=annotation_path,
        )
        second = collect_native_history(
            [self.claude], cutoff=self.cutoff, days=14, annotation_path=annotation_path,
        )
        self.assertEqual(first["human_records"], second["human_records"])
        self.assertEqual(first["human_records"][0]["episode_role"], "initial")
        self.assertEqual(first["human_records"][0]["quality_label"], "GOOD")
        self.assertEqual(first["human_records"][0]["score"], 2.5)
        export_a = self.base / "a.jsonl"
        export_b = self.base / "b.jsonl"
        write_normalized_history(export_a, first["export_records"])
        write_normalized_history(export_b, second["export_records"])
        self.assertEqual(export_a.read_bytes(), export_b.read_bytes())
        text = export_a.read_text(encoding="utf-8")
        self.assertNotIn("PRIVATE_CLAUDE_PROMPT_MUST_NOT_LEAK", text)
        self.assertNotIn(str(self.claude), text)

    def test_claude_message_id_fallback_deduplicates_missing_request_ids(self):
        usage = {
            "input_tokens": 10,
            "output_tokens": 2,
        }
        rows = [
            {
                "type": "assistant", "timestamp": "2026-11-08T10:00:01Z",
                "message": {
                    "id": "message-fallback", "model": "claude-test",
                    "usage": usage,
                },
            },
            {
                "type": "assistant", "timestamp": "2026-11-08T10:00:01Z",
                "message": {
                    "id": "message-fallback", "model": "claude-test",
                    "usage": usage,
                },
            },
            {
                "type": "assistant", "timestamp": "2026-11-08T10:00:02Z",
                "requestId": "explicit-request",
                "message": {
                    "id": "other-message", "model": "claude-test",
                    "usage": usage,
                },
            },
        ]
        self._write(self.claude, "session.jsonl", rows)
        data = collect_native_history([self.claude], cutoff=self.cutoff, days=14)
        self.assertEqual(
            [row["request_id"] for row in data["usage_records"]],
            ["message-fallback", "message-fallback", "explicit-request"],
        )
        self.assertEqual(data["stats"]["duplicate_usage_records"], 1)

    def test_automated_origin_annotation_updates_source_coverage_counters(self):
        self._write(self.claude, "session.jsonl", [{
            "type": "user", "timestamp": "2026-11-08T10:00:00Z",
            "promptId": "automated-origin", "userType": "human",
            "message": {"role": "user", "content": "ignored"},
        }])
        sidecar = self.base / "automated-origin.jsonl"
        sidecar.write_text(json.dumps({
            "event_id": "automated-origin", "human_origin": "automated_watch",
        }) + "\n", encoding="utf-8")
        data = collect_native_history(
            [self.claude], cutoff=self.cutoff, days=14, annotation_path=sidecar,
        )
        self.assertEqual(data["stats"]["human_candidates"], 0)
        self.assertEqual(data["stats"]["human_verified"], 0)
        self.assertEqual(data["stats"]["automated_excluded_messages"], 1)
        self.assertEqual(data["human_records"][0]["actor_kind"], "automated_watch")
        self.assertEqual(
            data["human_records"][0]["origin_status"], "excluded_automated",
        )

    def test_reviewed_pr_binding_sidecar_is_exact_and_not_prompt_derived(self):
        self._write(self.codex, "rollout.jsonl", [
            {"type": "turn_context", "payload": {"turn_id": "turn-a", "model": "fixture-codex-model"}},
            {"type": "response_item", "timestamp": "2026-10-28T09:00:01Z",
             "payload": {"role": "user", "content": "incidental PR #999"}},
            self._codex_usage("2026-10-28T09:00:02Z", "response-1"),
        ])
        sidecar = self.base / "bindings.jsonl"
        sidecar.write_text(json.dumps({
            "provider": "openai", "request_id": "response-1",
            "pr_binding": {
                "pr": "example/repo#42", "weight": "1", "method": "direct",
                "receipt_refs": ["receipt-42"],
                "rationale": "PRIVATE_BINDING_RATIONALE_FIXTURE",
            },
        }) + "\n", encoding="utf-8")
        data = collect_native_history(
            [self.codex], cutoff=self.cutoff, days=14, annotation_path=sidecar,
        )
        self.assertEqual(data["stats"]["pr_bound_usage_records"], 1)
        self.assertEqual(data["usage_records"][0]["attributions"][0]["pr"], "example/repo#42")
        self.assertEqual(data["usage_records"][0]["attributions"][0]["receipt_refs"], ["receipt-42"])
        self.assertEqual(
            data["usage_records"][0]["attributions"][0]["rationale"],
            "PRIVATE_BINDING_RATIONALE_FIXTURE",
        )
        exported = next(
            row for row in data["export_records"] if row.get("record_type") == "usage"
        )
        self.assertEqual(exported["attributions"][0]["rationale"], "retained")
        self.assertNotIn("PRIVATE_BINDING_RATIONALE_FIXTURE", json.dumps(exported))

    def test_prw_cli_rejects_unvalidated_flat_repository_map(self):
        caller = self.base / "unvalidated-map-caller"
        caller.mkdir()
        repository_map = self.base / "flat_repository_map.json"
        repository_map.write_text(
            json.dumps({"/fixture/cwd": "example/repo"}), encoding="utf-8"
        )
        script = Path(__file__).resolve().parents[1] / "scripts" / "prw_metrics.py"
        proc = subprocess.run(
            [sys.executable, str(script), "--offline", "--history-root", str(self.codex),
             "--cutoff", "2026-11-10T00:00:00Z", "--days", "14",
             "--repository-map", str(repository_map)],
            cwd=caller, check=False, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("native_origin_validated", proc.stderr)

    def test_prw_cli_collects_explicit_history_from_external_working_directory(self):
        secret = "EXTERNAL_CWD_PROMPT_MUST_NOT_LEAK"
        self._write(self.codex, "nested/rollout.jsonl", [
            {"type": "session_meta", "payload": {"id": "thread-codex"}},
            {"type": "turn_context", "payload": {"turn_id": "turn-a", "model": "fixture-codex-model"}},
            {"type": "response_item", "timestamp": "2026-10-28T09:00:01Z",
             "payload": {"id": "prompt-cli", "role": "user", "content": secret}},
            {"type": "response_item", "timestamp": "2026-10-28T09:00:03Z",
             "payload": {"id": "prompt-branch", "role": "user", "content": "candidate"}},
            self._codex_usage("2026-10-28T09:00:02Z", "response-cli"),
        ])
        caller = self.base / "external-caller"
        caller.mkdir()
        report = self.base / "out" / "dashboard.md"
        exported = self.base / "out" / "history.jsonl"
        annotations = self.base / "reviewed.jsonl"
        annotations.write_text(json.dumps({
            "event_id": "prompt-cli", "human_origin": "verified_human",
            "pr_binding": {"pr": "example/repo#5", "weight": "1", "method": "direct"},
        }) + "\n", encoding="utf-8")
        lookup = self.base / "pr_lookup.json"
        lookup.write_text(json.dumps({
            "fetchedAtUtc": "2026-11-10T00:00:00Z",
            "cache": {"sha256": "sha256:lookup"},
            "prs": [{
                "repo": "example/repo", "number": 5, "headRefName": "topic",
                "headRefOid": "sha-pr5", "state": "OPEN",
                "createdAt": "2026-10-01T00:00:00Z", "closedAt": None,
                "url": "https://github.com/example/repo/pull/5",
            }],
        }), encoding="utf-8")
        repository_map = self.base / "repository_map.json"
        repository_map.write_text(json.dumps({
            "cwdToRepo": {
                "/fixture/cwd": {
                    "repo": "example/repo", "status": "native_origin_validated",
                },
            },
        }), encoding="utf-8")
        script = Path(__file__).resolve().parents[1] / "scripts" / "prw_metrics.py"
        proc = subprocess.run(
            [sys.executable, str(script), "--offline", "--history-root", str(self.codex),
             "--cutoff", "2026-11-10T00:00:00Z", "--days", "14",
             "--history-annotations", str(annotations),
             "--pr-lookup-cache", str(lookup),
             "--repository-map", str(repository_map),
             "--history-export", str(exported), "--output", str(report)],
            cwd=caller, check=True, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertTrue(report.exists())
        self.assertTrue(exported.exists())
        dashboard = report.read_text(encoding="utf-8")
        export = exported.read_text(encoding="utf-8")
        self.assertIn("Native source acquisition: COMPLETE", dashboard)
        self.assertIn("Observed Native Human Activity by PR", dashboard)
        self.assertIn("[#5](https://github.com/example/repo/pull/5)", dashboard)
        self.assertIn("reviewed direct PR binding", dashboard)
        self.assertIn("| PR | Human messages | Association | Reviewed follow-up episodes |", dashboard)
        self.assertIn("candidates: direct", dashboard)
        self.assertIn("PR branch snapshot", dashboard)
        self.assertNotIn("/fixture/cwd", dashboard)
        self.assertNotIn("/fixture/cwd", export)
        self.assertIn('"request_id": "response-cli"', export)
        self.assertEqual(len(load_usage_events(str(exported))), 1)
        self.assertNotIn(secret, export)
        self.assertNotIn(str(self.codex), export)

        replay = load_normalized_history(
            exported, cutoff=self.cutoff, days=14, annotation_path=annotations,
        )
        self.assertEqual(replay["stats"]["status"], "REPLAYED")
        exported_usage = next(
            row for row in map(json.loads, export.splitlines())
            if row["record_type"] == "usage"
        )
        self.assertEqual(
            replay["usage_records"][0]["source_fingerprint"],
            exported_usage["source_fingerprint"],
        )
        self.assertEqual(replay["human_records"][0]["pr_binding"]["pr"],
                         "example/repo#5")
        self.assertEqual(replay["human_records"][0]["origin_status"], "verified_human")

        replay_report = self.base / "out" / "replay-dashboard.md"
        replay_proc = subprocess.run(
            [sys.executable, str(script), "--offline",
             "--cutoff", "2026-11-10T00:00:00Z",
             "--days", "14", "--history-replay", str(exported),
             "--history-annotations", str(annotations),
             "--pr-lookup-cache", str(lookup),
             "--output", str(replay_report)],
            cwd=caller, check=False, capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(replay_proc.returncode, 0, replay_proc.stderr)
        replay_dashboard = replay_report.read_text(encoding="utf-8")
        self.assertIn("Native history replay: REPLAYED", replay_dashboard)
        self.assertIn("## PRW Query Metrics (DuckDB)", replay_dashboard)
        self.assertIn("### Per-PR direct token totals", replay_dashboard)
        self.assertIn("example/repo#5", replay_dashboard)
        self.assertIn("Observed Native Human Activity by PR", replay_dashboard)
        self.assertNotIn(str(self.codex), replay_dashboard)

    def test_all_roots_and_source_errors_are_reported_without_paths(self):
        self._write(self.claude, "session.jsonl", [
            {"type": "assistant", "timestamp": "2026-11-08T10:00:00Z", "requestId": "req-1",
             "message": {"id": "msg-1", "model": "claude-test",
                         "usage": {"input_tokens": 10, "output_tokens": 2}}},
        ])
        self._write(self.codex, "rollout.jsonl", [
            {"type": "turn_context", "payload": {"turn_id": "turn-a", "model": "fixture-codex-model"}},
            self._codex_usage("2026-11-08T10:00:02Z", "response-1"),
        ])
        data = collect_native_history(
            [self.claude, self.codex, self.base / "missing-root"], cutoff=self.cutoff, days=14,
        )
        stats = data["stats"]
        self.assertEqual(stats["roots_requested"], 3)
        self.assertEqual(stats["roots_available"], 2)
        self.assertEqual(stats["missing_roots"], 1)
        self.assertEqual(stats["status"], "PARTIAL")
        self.assertEqual(stats["usage_records_in_window"], 2)
        self.assertIn("other runtimes not collected", stats["runtime_coverage"])
        self.assertNotIn(str(self.claude), json.dumps(stats))

    def test_reviewed_actor_and_context_override_native_role_and_keep_reasoning_private(self):
        secret_rationale = "PRIVATE_REVIEW_REASON_MUST_NOT_BE_RETAINED"
        self._write(self.claude, "project/session.jsonl", [
            {"type": "user", "timestamp": "2026-11-08T10:00:00Z", "promptId": "event-bot",
             "userType": "human", "turnOrigin": "human", "sessionId": "session-1",
             "message": {"role": "user", "content": [{"type": "text", "text": "message"}]}},
        ])
        annotation_path = self.base / "corrected.jsonl"
        annotation_path.write_text(json.dumps({
            "event_id": "event-bot", "actor_kind": "automated_watch",
            "context_pr_decision": "unassigned_multi_pr",
            "context_associated_pr": None, "effective_associated_pr": None,
            "original_associated_pr": "example/repo#5",
            "association_method": "context_semantic_unassigned",
            "annotation_confidence": "explicit", "effective_association_confidence": "UNASSIGNED_CONTEXT",
            "original_association_basis": "best_effort_repo_branch_time",
            "original_association_confidence": "LOW_BEST_EFFORT",
            "human_nudge_eligible": False, "message_kind": "continuation/followthrough_nudge",
            "effective_association_confidence": "UNASSIGNED_CONTEXT",
            "original_association_confidence": "LOW_BEST_EFFORT",
            "episode_id": "episode-bot", "episode_role": "followup",
            "quality_label": "bad", "quality_rationale": secret_rationale,
            "context_rationale": secret_rationale,
        }) + "\n", encoding="utf-8")
        data = collect_native_history(
            [self.claude], cutoff=self.cutoff, days=14, annotation_path=annotation_path,
        )
        row = data["human_records"][0]
        self.assertEqual(row["origin_status"], "excluded_automated")
        self.assertEqual(row["actor_kind"], "automated_watch")
        self.assertEqual(row["context_pr_decision"], "unassigned_multi_pr")
        self.assertEqual(row["effective_associated_pr"], None)
        self.assertEqual(row["original_associated_pr"], "example/repo#5")
        self.assertEqual(row["human_nudge_eligible"], False)
        self.assertEqual(row["message_kind"], "continuation/followthrough_nudge")
        self.assertEqual(row["association_method"], "context_semantic_unassigned")
        self.assertEqual(row["effective_association_confidence"], "UNASSIGNED_CONTEXT")
        serialized = json.dumps(data["export_records"])
        self.assertNotIn(secret_rationale, serialized)
        self.assertNotIn("context_rationale", serialized)
        self.assertNotIn("quality_rationale", serialized)

    def test_annotations_bind_by_exact_event_id_and_leave_new_candidates_unreviewed(self):
        rows = [
            {"type": "response_item", "timestamp": "2026-11-08T10:00:01Z",
             "payload": {"id": "p-1", "role": "user", "content": "one"}},
            {"type": "response_item", "timestamp": "2026-11-08T10:00:02Z",
             "payload": {"id": "p-2", "role": "user", "content": "two"}},
        ]
        self._write(self.codex, "rollout.jsonl", rows)
        before = collect_native_history([self.codex], cutoff=self.cutoff, days=14)
        first_id = before["human_records"][0]["event_id"]
        annotation = {
            "event_id": first_id, "human_origin": "verified_human",
            "episode_role": "followup", "quality_label": "MIXED",
            "score": 1, "score_source": "reviewed_annotation",
        }
        sidecar = self.base / "annotations.jsonl"
        sidecar.write_text(json.dumps(annotation) + "\n", encoding="utf-8")
        after = collect_native_history(
            [self.codex], cutoff=self.cutoff, days=14, annotation_path=sidecar,
        )
        self.assertEqual(after["human_records"][0]["episode_role"], "followup")
        self.assertEqual(after["human_records"][0]["origin_status"], "verified_human")
        self.assertNotIn("episode_role", after["human_records"][1])
        self.assertEqual(after["stats"]["human_verified"], 1)
        self.assertEqual(after["stats"]["human_unannotated"], 1)


if __name__ == "__main__":
    unittest.main()

class ReplaySourceQualityTests(unittest.TestCase):
    def test_export_quality_is_allowlisted_and_missing_is_unknown(self):
        from datetime import datetime, timezone
        from scripts.native_usage_collector import load_normalized_history
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "partial.jsonl"
            path.write_text("", encoding="utf-8")
            sidecar = Path(str(path) + ".stats.json")
            sidecar.write_text(json.dumps({
                "status": "PARTIAL", "malformed_lines": 76, "read_errors": 2,
                "files_scanned": 23, "window_start": "2026-10-26T00:00:00Z",
                "window_end": "2026-11-09T00:00:00Z", "secret_path": "/secret/private",
            }), encoding="utf-8")
            cutoff = datetime(2026, 11, 9, tzinfo=timezone.utc)
            partial = load_normalized_history(path, cutoff=cutoff)["stats"]
            self.assertEqual(partial["status"], "REPLAYED")
            self.assertEqual(partial["malformed_lines"], 0)
            self.assertEqual(partial["source_exports"][0]["status"], "PARTIAL")
            self.assertEqual(partial["source_exports"][0]["malformed_lines"], 76)
            self.assertNotIn("secret", json.dumps(partial))
            missing = Path(temp) / "missing.jsonl"
            missing.write_text("", encoding="utf-8")
            self.assertEqual(load_normalized_history(missing, cutoff=cutoff)["stats"]["source_exports"][0]["status"], "UNKNOWN")

    def test_combined_replay_exposes_upstream_partial_and_unknown(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            partial, missing = root / "one.jsonl", root / "two.jsonl"
            row = {"record_type": "usage", "provider": "openai", "request_id": "request", "session_id": "session", "timestamp": "2026-11-02T00:00:00Z", "model": "model", "raw_usage": {"input_tokens": 1, "cache_read_input_tokens": 0, "output_tokens": 1}}
            partial.write_text(json.dumps(row) + "\n", encoding="utf-8")
            missing.write_text("", encoding="utf-8")
            Path(str(partial) + ".stats.json").write_text(json.dumps({
                "status": "PARTIAL", "malformed_lines": 76, "read_errors": 0,
                "window_start": "2026-10-26T00:00:00Z", "window_end": "2026-11-09T00:00:00Z",
                "secret_path": "/private/secret",
            }), encoding="utf-8")
            output = root / "report.md"
            cmd = [sys.executable, "scripts/prw_metrics.py", "--offline", "--history-replay", str(partial), "--history-replay", str(missing), "--cutoff", "2026-11-09T00:00:00Z", "--output", str(output)]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr)
            text = output.read_text(encoding="utf-8")
            self.assertIn("Upstream export quality: PARTIAL", text)
            self.assertIn("export 1: PARTIAL", text)
            self.assertIn("malformed=76", text)
            self.assertIn("export 2: UNKNOWN", text)
            self.assertIn("malformed_lines=0", text)
            self.assertNotIn("/private/secret", text)

    def test_empty_replay_still_reports_unknown_source_quality(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, output = root / "empty.jsonl", root / "report.md"
            source.write_text("", encoding="utf-8")
            cmd = [sys.executable, "scripts/prw_metrics.py", "--offline", "--history-replay", str(source), "--cutoff", "2026-11-09T00:00:00Z", "--output", str(output)]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Upstream export quality: UNKNOWN", output.read_text(encoding="utf-8"))

class ReplayAnnotationPrivacyTests(unittest.TestCase):
    def test_freeform_annotation_is_absent_from_dashboard_and_retained_summary(self):
        from scripts.prw_metrics import aggregate_native_human_steering, _project_summary
        marker = "my confidential strategy meeting on Tuesday"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, annotations = root / "events.jsonl", root / "annotations.jsonl"
            event = {"record_type": "human", "provider": "openai", "event_id": "event1", "session_id": "session", "timestamp": "2026-11-02T00:00:00Z", "origin_status": "verified_human"}
            annotation = {"event_id": "event1", "actor_kind": "human", "context_pr_decision": "override", "effective_associated_pr": "acme/game#1", "association_method": marker, "effective_association_confidence": marker}
            source.write_text(json.dumps(event) + "\n", encoding="utf-8")
            annotations.write_text(json.dumps(annotation) + "\n", encoding="utf-8")
            cutoff = datetime(2026, 11, 9, tzinfo=timezone.utc)
            replay = load_normalized_history(source, cutoff=cutoff, annotation_path=annotations)
            human = aggregate_native_human_steering(replay["human_records"], [], window_start="2026-10-26T00:00:00Z", window_end="2026-11-09T00:00:00Z")
            retained = _project_summary({"human_summary": human})
            self.assertNotIn(marker, json.dumps(retained))
            untrusted_record = dict(event, **annotation)
            direct_human = aggregate_native_human_steering([untrusted_record], [], window_start="2026-10-26T00:00:00Z", window_end="2026-11-09T00:00:00Z")
            self.assertNotIn(marker, json.dumps(_project_summary({"human_summary": direct_human})))
            token = "PRIVATE_SECRET_ABC123"
            token_record = dict(untrusted_record, association_method=token, effective_association_confidence=token)
            token_human = aggregate_native_human_steering([token_record], [], window_start="2026-10-26T00:00:00Z", window_end="2026-11-09T00:00:00Z")
            self.assertNotIn(token, json.dumps(_project_summary({"human_summary": token_human})))
            report = root / "report.md"
            cmd = [sys.executable, "scripts/prw_metrics.py", "--offline", "--history-replay", str(source), "--history-annotations", str(annotations), "--cutoff", "2026-11-09T00:00:00Z", "--output", str(report)]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn(marker, report.read_text(encoding="utf-8"))

    def test_reviewed_low_confidence_survives_retained_and_rendered_output(self):
        from scripts.prw_metrics import aggregate_native_human_steering, _project_summary
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, annotations, output = root / "events.jsonl", root / "annotations.jsonl", root / "report.md"
            rows = []
            labels = ["BRANCH_SNAPSHOT_LOW", "BRANCH_ONLY_LOW", "high", "medium", "low", "UNASSIGNED_CONTEXT", "PRIVATE_TOKEN_123"]
            for number, label in enumerate(labels, 1):
                rows.append({"record_type": "human", "provider": "openai", "event_id": f"e{number}", "session_id": "session", "timestamp": "2026-11-02T00:00:00Z", "origin_status": "verified_human"})
            source.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            annotations.write_text("".join(json.dumps({"event_id": f"e{number}", "actor_kind": "human", "context_pr_decision": "confirm_original", "effective_associated_pr": f"acme/game#{number}", "association_method": "context_associated", "effective_association_confidence": label}) + "\n" for number, label in enumerate(labels, 1)), encoding="utf-8")
            replay = load_normalized_history(source, cutoff=datetime(2026, 11, 9, tzinfo=timezone.utc), annotation_path=annotations)
            summary = aggregate_native_human_steering(replay["human_records"], [], window_start="2026-10-26T00:00:00Z", window_end="2026-11-09T00:00:00Z")
            retained = _project_summary({"human_summary": summary})
            self.assertIn("context_associated", retained["human_summary"]["per_pr"][0]["association_basis"])
            by_pr = {row["pr"]: row["association_confidence"] for row in retained["human_summary"]["per_pr"]}
            self.assertEqual([by_pr[f"acme/game#{number}"] for number in range(1, len(labels) + 1)], labels[:-1] + ["UNKNOWN"])
            cmd = [sys.executable, "scripts/prw_metrics.py", "--offline", "--history-replay", str(source), "--history-annotations", str(annotations), "--cutoff", "2026-11-09T00:00:00Z", "--output", str(output)]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr)
            text = output.read_text(encoding="utf-8")
            low_rows = [line for line in text.splitlines() if "acme/game#1" in line or "acme/game#2" in line or "acme/game#5" in line]
            self.assertEqual(sum("low confidence" in line for line in low_rows), 3)
            self.assertIn("reviewed context association", text)
            self.assertNotIn("PRIVATE_TOKEN_123", text)
