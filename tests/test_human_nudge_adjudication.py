import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import human_nudge_adjudication as adjudication

from scripts.native_usage_collector import _apply_replay_annotation
from scripts.prw_metrics import aggregate_native_human_steering


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "human_nudge_adjudication.py"


class HumanNudgeAdjudicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.packet = self.root / "input.json"
        self.output = self.root / "annotations.jsonl"
        self.secret = "PRIVATE_NUDGE_TEXT_should_not_be_logged"
        self.packet.write_text(json.dumps({
            "schema_version": "human-nudge-input.v1",
            "events": [{
                "event_id": "event-1", "provider": "codex", "session_id": "s-1",
                "timestamp": "2026-11-12T12:00:00Z", "origin_status": "unknown",
                "native_origin_status": "unverified_candidate", "actor_kind": "unknown",
                "text": self.secret,
                "context": [{"role": "user", "text": "prior task", "event_id": "e0"}],
            }],
        }), encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def run_judge(self, response):
        for annotation in response.get("annotations", []):
            annotation.setdefault("association_scope", "unknown")
            annotation.setdefault("associated_prs", [])
            annotation.setdefault("association_evidence", [])
        fake = self.root / "fake_judge.py"
        fake.write_text(
            "import json,sys\n"
            "request=json.load(sys.stdin)\n"
            "assert request['packet']['events'][0]['text'] == "
            + repr(self.secret) + "\n"
            "assert request['packet']['events'][0]['context'][0]['text'] "
            "== 'prior task'\n"
            "assert request['response_schema']['properties']['annotations']\n"
            "print(json.dumps(" + repr(response) + "))\n",
            encoding="utf-8",
        )
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--input", str(self.packet),
             "--judge-command", f"{sys.executable} {fake}", "--output",
             str(self.output)],
            text=True, capture_output=True, check=False, timeout=10,
        )

    def test_one_call_transports_private_context_and_writes_replay_annotations(self):
        response = {"annotations": [{
            "event_id": "event-1", "actor_kind": "human",
            "message_kind": "continuation/followthrough_nudge",
            "human_nudge_eligible": True,
        }]}
        result = self.run_judge(response)
        self.assertEqual(result.returncode, 0, result.stderr)
        annotation = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual(annotation["event_id"], "event-1")
        self.assertEqual(annotation["actor_kind"], "human")
        self.assertTrue(annotation["human_nudge_eligible"])
        record = {"event_id": "event-1", "actor_kind": "unknown"}
        _apply_replay_annotation(record, annotation)
        self.assertEqual(record["actor_kind"], "human")
        self.assertEqual(record["message_kind"], "continuation/followthrough_nudge")
        self.assertTrue(record["human_nudge_eligible"])
        self.assertNotIn(self.secret, annotation.__repr__())
        self.assertNotIn(self.secret, result.stderr + result.stdout)
        self.assertEqual(os.stat(self.output).st_mode & 0o777, 0o600)

    def test_existing_output_is_private_before_writing(self):
        self.output.write_text("previous annotation", encoding="utf-8")
        self.output.chmod(0o644)
        fdopen = os.fdopen

        def private_fdopen(fd, *args, **kwargs):
            self.assertEqual(os.fstat(fd).st_mode & 0o777, 0o600)
            return fdopen(fd, *args, **kwargs)

        with mock.patch.object(adjudication, "_judge", return_value=[]), \
                mock.patch.object(adjudication.os, "fdopen", side_effect=private_fdopen):
            self.assertEqual(adjudication.main([
                "--input", str(self.packet), "--judge-command", "unused",
                "--output", str(self.output),
            ]), 0)

    def test_unknown_and_native_origin_are_preserved_without_role_promotion(self):
        response = {"annotations": [{
            "event_id": "event-1", "actor_kind": "unknown",
            "message_kind": None, "human_nudge_eligible": None,
        }]}
        self.assertEqual(self.run_judge(response).returncode, 0)
        annotation = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual(annotation["actor_kind"], "unknown")
        self.assertNotIn("human_origin", annotation)
        self.assertNotIn("text", annotation)
        self.assertNotIn("native_origin_status", annotation)

    def test_foreign_or_duplicate_ids_fail_without_source_leak(self):
        valid = {
            "actor_kind": "unknown", "message_kind": None,
            "human_nudge_eligible": None,
        }
        for response in (
            {"annotations": [{**valid, "event_id": self.secret}]},
            {"annotations": [
                {**valid, "event_id": "event-1"},
                {**valid, "event_id": "event-1"},
            ]},
        ):
            with self.subTest(response=response):
                result = self.run_judge(response)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn(self.secret, result.stderr + result.stdout)

    def test_non_json_response_fails_without_repair_or_raw_output(self):
        fake = self.root / "fake_bad_judge.py"
        fake.write_text(
            "import sys; sys.stdin.read(); print('not-json "
            + self.secret + "')\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--input", str(self.packet),
             "--judge-command",
             f"{sys.executable} {fake}", "--output", str(self.output)],
            text=True, capture_output=True, check=False, timeout=10,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn(self.secret, result.stderr + result.stdout)

    def test_unsupported_judgment_labels_fail_protocol_validation(self):
        invalid_labels = (
            ("actor_kind", "probable_human"),
            ("human_origin", "verified_human"),
            ("message_kind", "kind-of-nudge"),
        )
        for field, value in invalid_labels:
            with self.subTest(field=field):
                annotation = {
                    "event_id": "event-1", "actor_kind": "unknown",
                    "message_kind": None, "human_nudge_eligible": None,
                }
                annotation[field] = value
                result = self.run_judge({"annotations": [annotation]})
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn(self.secret, result.stderr + result.stdout)

    def test_response_schema_uses_strict_all_required_object_shape(self):
        schema = json.loads(
            (REPO / "scripts/prompts/human_nudge_adjudication.schema.json")
            .read_text(encoding="utf-8")
        )
        annotation = schema["properties"]["annotations"]["items"]
        expected_fields = {
            "event_id", "actor_kind", "message_kind", "human_nudge_eligible",
            "association_scope", "associated_prs", "association_evidence",
        }
        self.assertIs(schema["additionalProperties"], False)
        self.assertEqual(set(schema["required"]), {"annotations"})
        self.assertIs(annotation["additionalProperties"], False)
        self.assertEqual(set(annotation["required"]), expected_fields)
        self.assertEqual(set(annotation["properties"]), expected_fields)
        self.assertEqual(
            annotation["properties"]["actor_kind"]["enum"],
            ["human", "automated_watch", "unknown"],
        )
        self.assertEqual(
            annotation["properties"]["message_kind"]["enum"],
            [
                "initial_task", "new_requirement/domain_judgment",
                "status_request", "continuation/followthrough_nudge",
                "teammate_message", "cold_reviewer_dispatch",
                "compaction", "merge_approval", None,
            ],
        )

    def test_reviewed_binding_and_episode_metadata_survive_judging(self):
        packet = json.loads(self.packet.read_text(encoding="utf-8"))
        event = packet["events"][0]
        event.update({
            "episode_id": "episode-reviewed", "episode_role": "continuation",
            "pr_binding": {
                "pr": "example/game#42", "method": "reviewed_context", "weight": 1,
            },
            "association_method": "reviewed_context",
            "unrelated_source_metadata": "must-not-be-copied",
        })
        self.packet.write_text(json.dumps(packet), encoding="utf-8")
        response = {"annotations": [{
            "event_id": "event-1", "actor_kind": "human",
            "message_kind": "continuation/followthrough_nudge",
            "human_nudge_eligible": True,
        }]}
        result = self.run_judge(response)
        self.assertEqual(result.returncode, 0, result.stderr)
        annotation = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual(annotation["episode_id"], "episode-reviewed")
        self.assertEqual(annotation["pr_binding"], event["pr_binding"])
        self.assertEqual(annotation["association_method"], "reviewed_context")
        self.assertEqual(annotation["actor_kind"], "human")
        self.assertNotIn("text", annotation)
        self.assertNotIn("context", annotation)
        self.assertNotIn("unrelated_source_metadata", annotation)
        self.assertNotIn(self.secret, json.dumps(annotation))

    def test_automated_actor_cannot_become_human_nudge_after_annotation(self):
        response = {"annotations": [{
            "event_id": "event-1", "actor_kind": "automated_watch",
            "message_kind": "continuation/followthrough_nudge",
            "human_nudge_eligible": True,
        }]}
        result = self.run_judge(response)
        self.assertEqual(result.returncode, 0, result.stderr)
        annotation = json.loads(self.output.read_text(encoding="utf-8"))
        record = {
            "event_id": "event-1", "provider": "codex",
            "timestamp": "2026-11-12T12:00:00Z", "actor_kind": "unknown",
            "native_origin_status": "unverified_candidate",
        }
        _apply_replay_annotation(record, annotation)
        summary = aggregate_native_human_steering(
            [record], [], window_start="2026-11-12T00:00:00Z",
            window_end="2026-11-13T00:00:00Z",
        )
        self.assertEqual(record["actor_kind"], "automated_watch")
        self.assertEqual(record["native_origin_status"], "unverified_candidate")
        self.assertEqual(summary["coverage"]["human_nudge_messages"], 0)
        self.assertEqual(summary["coverage"]["automated_excluded_messages"], 1)

    def test_non_nudge_message_kinds_are_accepted_and_excluded_from_nudges(self):
        for kind in (
            "teammate_message",
            "cold_reviewer_dispatch",
            "compaction",
            "merge_approval",
        ):
            with self.subTest(message_kind=kind):
                response = {"annotations": [{
                    "event_id": "event-1", "actor_kind": "human",
                    "message_kind": kind,
                    "human_nudge_eligible": False,
                }]}
                result = self.run_judge(response)
                self.assertEqual(result.returncode, 0, result.stderr)
                annotation = json.loads(self.output.read_text(encoding="utf-8"))
                record = {
                    "event_id": "event-1", "provider": "codex",
                    "timestamp": "2026-11-12T12:00:00Z", "actor_kind": "unknown",
                    "native_origin_status": "unverified_candidate",
                }
                _apply_replay_annotation(record, annotation)
                summary = aggregate_native_human_steering(
                    [record], [], window_start="2026-11-12T00:00:00Z",
                    window_end="2026-11-13T00:00:00Z",
                )
                self.assertEqual(summary["coverage"]["human_nudge_messages"], 0)
                self.assertEqual(summary["coverage"]["message_kind_counts"].get(kind), 1)


if __name__ == "__main__":
    unittest.main()


def test_request_schema_requires_every_input_id_and_normalizes_keyed_response(tmp_path):
    events = [{"event_id": f"event-{i}", "text": "continue", "context": []} for i in range(10)]
    packet = {"schema_version": "human-nudge-input.v1", "events": events}
    fake = tmp_path / "judge.py"
    fake.write_text('''import json, sys
r = json.load(sys.stdin)
s = r["response_schema"]["properties"]["annotations"]
ids = [e["event_id"] for e in r["packet"]["events"]]
assert s["type"] == "object"
assert s["additionalProperties"] is False
assert set(s["required"]) == set(ids) == set(s["properties"])
for item in s["properties"].values():
    assert item["additionalProperties"] is False
    assert "event_id" not in item["properties"]
value = {"actor_kind":"unknown", "message_kind":None, "human_nudge_eligible":None,
         "association_scope":"unknown", "associated_prs":[], "association_evidence":[]}
print(json.dumps({"annotations": {key: value for key in reversed(ids)}}))
''')
    output = adjudication._judge(packet, f"{sys.executable} {fake}", 10)
    assert [a["event_id"] for a in output] == [e["event_id"] for e in events]


def test_keyed_response_missing_or_extra_id_is_rejected(tmp_path):
    import pytest

    packet = {"schema_version": "human-nudge-input.v1", "events": [
        {"event_id": "a", "text": "one", "context": []},
        {"event_id": "b", "text": "two", "context": []},
    ]}
    value = {"actor_kind": "unknown", "message_kind": None, "human_nudge_eligible": None,
             "association_scope": "unknown", "associated_prs": [], "association_evidence": []}
    fake = tmp_path / "judge.py"
    for annotations in ({"a": value}, {"a": value, "b": value, "extra": value}):
        fake.write_text("import sys; sys.stdin.read(); print(" + repr(json.dumps({"annotations": annotations})) + ")")
        with pytest.raises(ValueError, match="event IDs do not match"):
            adjudication._judge(packet, f"{sys.executable} {fake}", 10)
