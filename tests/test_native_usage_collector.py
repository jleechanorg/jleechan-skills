"""Deterministic metadata-only acquisition from explicit native history roots."""

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scripts.native_usage_collector import collect_native_history, write_normalized_history
from scripts.prw_metrics import aggregate_usage, load_usage_events


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
            {"type": "session_meta", "payload": {"id": "thread-codex"}},
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
                "receipt_refs": ["receipt-42"], "rationale": "reviewed exact request binding",
            },
        }) + "\n", encoding="utf-8")
        data = collect_native_history(
            [self.codex], cutoff=self.cutoff, days=14, annotation_path=sidecar,
        )
        self.assertEqual(data["stats"]["pr_bound_usage_records"], 1)
        self.assertEqual(data["usage_records"][0]["attributions"][0]["pr"], "example/repo#42")
        self.assertEqual(data["usage_records"][0]["attributions"][0]["receipt_refs"], ["receipt-42"])

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
