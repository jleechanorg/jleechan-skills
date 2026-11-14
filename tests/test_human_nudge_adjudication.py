import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.native_usage_collector import _apply_replay_annotation


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
            "human_origin": "verified_human",
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

    def test_unknown_and_native_origin_are_preserved_without_role_promotion(self):
        response = {"annotations": [{
            "event_id": "event-1", "actor_kind": "unknown", "human_origin": "unknown",
            "message_kind": None, "human_nudge_eligible": None,
        }]}
        self.assertEqual(self.run_judge(response).returncode, 0)
        annotation = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual(annotation["actor_kind"], "unknown")
        self.assertEqual(annotation["human_origin"], "unknown")
        self.assertNotIn("text", annotation)
        self.assertNotIn("native_origin_status", annotation)

    def test_foreign_or_duplicate_ids_fail_without_source_leak(self):
        for response in (
            {"annotations": [{"event_id": "foreign", "actor_kind": "unknown"}]},
            {"annotations": [{"event_id": "event-1"}, {"event_id": "event-1"}]},
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
            ("human_origin", "maybe_human"),
            ("message_kind", "kind-of-nudge"),
        )
        for field, value in invalid_labels:
            with self.subTest(field=field):
                annotation = {
                    "event_id": "event-1", "actor_kind": "unknown",
                    "human_origin": "unknown", "message_kind": None,
                    "human_nudge_eligible": None,
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
            "event_id", "actor_kind", "human_origin", "message_kind",
            "human_nudge_eligible",
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
                "status_request", "continuation/followthrough_nudge", None,
            ],
        )


if __name__ == "__main__":
    unittest.main()
