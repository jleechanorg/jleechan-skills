import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from datetime import datetime, timezone

from scripts import native_usage_collector as collector
from scripts import human_nudge_adjudication as adjudication
from scripts.prw_metrics import aggregate_native_human_steering


NOW = datetime(2026, 11, 13, 12, tzinfo=timezone.utc)


def _sdk_rows():
    return [
        {"v": 1, "type": "assistant", "id": "a1", "ts": "2026-11-13T11:56:00Z", "agent": "codex", "content": "I will implement it."},
        {"v": 1, "type": "user", "id": "human-1", "ts": "2026-11-13T11:57:00Z", "agent": "codex", "content": "Please continue the existing fix."},
        {"v": 1, "type": "user", "id": "unknown-1", "ts": "2026-11-13T11:58:00Z", "agent": "codex", "content": "What is the status?"},
        {"v": 1, "type": "user", "id": "watch-1", "ts": "2026-11-13T11:59:00Z", "agent": "codex", "content": "Automated reminder."},
    ]


def _history(tmp_path):
    source = tmp_path / "native.jsonl"
    source.write_text(json.dumps({"type": "session_meta", "payload": {"id": "session-1"}}) + "\n")
    return source



class EntireHistoryIngestionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.tmp_path = Path(temporary.name)

    def patch(self, target, name, value):
        patcher = mock.patch.object(target, name, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_entire_rows_apply_exact_annotations_and_existing_nudge_counter(self):
        source = _history(self.tmp_path)
        self.patch(collector, "run_entire_parser", lambda argv, agent, data: _sdk_rows())
        baseline = collector.collect_native_history(
            [str(source)], cutoff=NOW, days=1, entire_parser=["entire-parser"], entire_agent="codex",
        )
        emitted_ids = {
            record["native_event_id"]: record["event_id"]
            for record in baseline["human_records"]
        }
        annotations = self.tmp_path / "review.jsonl"
        annotations.write_text("\n".join(json.dumps(row) for row in (
            {"event_id": emitted_ids["human-1"], "actor_kind": "human", "human_origin": "verified_human", "message_kind": "continuation/followthrough_nudge", "human_nudge_eligible": True},
            {"event_id": emitted_ids["watch-1"], "actor_kind": "automated_watch", "message_kind": "continuation/followthrough_nudge", "human_nudge_eligible": True},
        )) + "\n")
        result = collector.collect_native_history(
            [str(source)], cutoff=NOW, days=1, annotation_path=str(annotations),
            entire_parser=["entire-parser"], entire_agent="codex",
        )
        assert {row.get("native_event_id") for row in result["human_records"]} == {"human-1", "unknown-1", "watch-1"}
        summary = aggregate_native_human_steering(
            result["human_records"], [], window_start=NOW.replace(hour=0), window_end=NOW,
        )
        assert summary["coverage"]["human_nudge_messages"] == 1
        assert next(row for row in result["human_records"] if row.get("native_event_id") == "unknown-1")["actor_kind"] == "unknown"
        assert result["stats"]["automated_excluded_messages"] == 1

    def test_entire_verified_native_record_without_review_is_unannotated(self):
        source = self.tmp_path / "verified.jsonl"
        source.write_text(json.dumps({
            "type": "user", "sessionId": "verified-session", "uuid": "verified-event",
            "timestamp": "2026-11-13T11:59:00Z", "origin": {"kind": "human"},
            "message": {"role": "user", "content": "continue"},
        }) + "\n")
        self.patch(collector, "run_entire_parser", lambda *_args: [{
            "v": 1, "type": "user", "id": "verified-event",
            "ts": "2026-11-13T11:59:00Z", "content": "continue",
        }])

        result = collector.collect_native_history(
            [str(source)], cutoff=NOW, days=1,
            entire_parser="entire-parser", entire_agent="claude-code",
        )

        self.assertEqual(result["human_records"][0]["native_origin_status"], "verified_human")
        self.assertEqual(result["stats"]["human_unannotated"], 1)

    def test_reviewed_entire_unknown_record_is_not_unannotated(self):
        source = self.tmp_path / "unknown.jsonl"
        source.write_text(json.dumps({
            "type": "user", "sessionId": "unknown-session", "uuid": "unknown-event",
            "timestamp": "2026-11-13T11:59:00Z",
            "message": {"role": "user", "content": "status?"},
        }) + "\n")
        self.patch(collector, "run_entire_parser", lambda *_args: [{
            "v": 1, "type": "user", "id": "unknown-event",
            "ts": "2026-11-13T11:59:00Z", "content": "status?",
        }])
        baseline = collector.collect_native_history(
            [str(source)], cutoff=NOW, days=1,
            entire_parser="entire-parser", entire_agent="claude-code",
        )
        annotation_path = self.tmp_path / "unknown-review.jsonl"
        annotation_path.write_text(json.dumps({
            "event_id": baseline["human_records"][0]["event_id"],
            "actor_kind": "unknown",
        }) + "\n")

        result = collector.collect_native_history(
            [str(source)], cutoff=NOW, days=1, annotation_path=str(annotation_path),
            entire_parser="entire-parser", entire_agent="claude-code",
        )

        self.assertEqual(result["human_records"][0]["actor_kind"], "unknown")
        self.assertEqual(result["stats"]["human_unannotated"], 0)


    def test_successful_conversion_does_not_claim_native_source_completeness(self):
        source = _history(self.tmp_path)
        baseline = collector.collect_native_history([str(source)], cutoff=NOW, days=1)
        self.assertEqual(baseline["stats"]["status"], "COMPLETE")
        self.patch(collector, "run_entire_parser", lambda *_args: _sdk_rows())
        result = collector.collect_native_history(
            [str(source)], cutoff=NOW, days=1,
            entire_parser="entire-parser", entire_agent="codex",
        )
        self.assertEqual(result["stats"]["status"], "PARTIAL")
        self.assertEqual(result["stats"]["entire_source_coverage"], "UNVERIFIED")
        self.assertEqual(result["stats"]["entire_parser_sources"], 1)
        self.assertEqual(result["stats"]["entire_candidate_records"], 3)

    def test_normal_export_omits_text_and_requested_packet_is_private(self):
        source = _history(self.tmp_path)
        self.patch(collector, "run_entire_parser", lambda argv, agent, data: _sdk_rows())
        result = collector.collect_native_history(
            [str(source)], cutoff=NOW, days=1, entire_parser="entire-parser", entire_agent="codex",
        )
        export = self.tmp_path / "history.jsonl"
        packet = self.tmp_path / "private" / "packet.json"
        collector.write_normalized_history(export, result["export_records"])
        exported = export.read_text()
        assert "Please continue the existing fix." not in exported
        assert "content" not in exported
        collector.write_nudge_packets(packet, result["nudge_packet_events"])
        decoded = json.loads(packet.read_text())
        assert decoded["schema_version"] == "human-nudge-input.v1"
        human = next(event for event in decoded["events"] if event["native_event_id"] == "human-1")
        assert human["text"] == "Please continue the existing fix."
        assert {item["role"] for item in human["context"]} == {"assistant", "user"}
        assert os.stat(packet).st_mode & 0o777 == 0o600


    def test_entire_packet_keeps_full_text_blocks_and_null_content(self):
        source = _history(self.tmp_path)
        long_text = "x" * 6000
        rows = [
            {"v": 1, "type": "user", "id": "long", "ts": "2026-11-13T11:59:00Z",
             "agent": "codex", "content": [{"text": long_text}, {"text": "end"}]},
            {"v": 1, "type": "user", "id": "null", "ts": "2026-11-13T11:59:30Z",
             "agent": "codex", "content": None},
        ]
        self.patch(collector, "run_entire_parser", lambda argv, agent, data: rows)
        result = collector.collect_native_history(
            [str(source)], cutoff=NOW, days=1, entire_parser="entire-parser", entire_agent="codex",
        )
        packet = result["nudge_packet_events"]
        long_record = next(event for event in packet if event.get("native_event_id") == "long")
        assert long_record["text"] == long_text + "end"
        assert long_record["text_blocks"] == [long_text, "end"]
        null_record = next(event for event in packet if event.get("native_event_id") == "null")
        assert null_record["text"] == ""
        assert null_record["text_available"] is False
        assert null_record["actor_kind"] == "unknown"


    def test_missing_native_id_gets_stable_tool_id_for_packet_annotation(self):
        source = _history(self.tmp_path)
        row = {"v": 1, "type": "user", "ts": "2026-11-13T11:59:00Z",
               "agent": "claude-code", "content": "legacy user record"}
        self.patch(collector, "run_entire_parser", lambda *_args: [row])
        initial = collector.collect_native_history(
            [str(source)], cutoff=NOW, days=1, entire_parser="entire-parser", entire_agent="claude-code",
        )
        record = initial["human_records"][0]
        packet_record = initial["nudge_packet_events"][0]
        assert record["event_id_source"] == "entire_adapter"
        assert record["native_source_status"] == "missing_event_id"
        assert "native_event_id" not in record
        assert packet_record["event_id"] == record["event_id"]
        annotations = self.tmp_path / "legacy-review.jsonl"
        annotations.write_text(json.dumps({
            "event_id": packet_record["event_id"], "actor_kind": "human",
            "human_origin": "verified_human",
        }) + "\n")
        replay = collector.collect_native_history(
            [str(source)], cutoff=NOW, days=1, annotation_path=str(annotations),
            entire_parser="entire-parser", entire_agent="claude-code",
        )
        assert replay["human_records"][0]["actor_kind"] == "human"


    def test_entire_ids_are_stable_across_appends_and_scoped_to_source_session(self):
        first = self.tmp_path / "first.jsonl"
        second = self.tmp_path / "second.jsonl"
        first.write_text(json.dumps({"type": "session_meta", "payload": {"id": "session-a"}}) + "\n")
        second.write_text(json.dumps({"type": "session_meta", "payload": {"id": "session-b"}}) + "\n")
        sdk_row = {"v": 1, "type": "user", "id": "duplicate", "ts": "2026-11-13T11:59:00Z", "content": "stable"}

        def parse(_argv, _agent, source_bytes):
            if b"appended" in source_bytes:
                return [sdk_row, {"v": 1, "type": "assistant", "content": "appended"}]
            return [sdk_row]

        self.patch(collector, "run_entire_parser", parse)
        def collect(paths):
            return collector.collect_native_history(
                [str(path) for path in paths], cutoff=NOW, days=1,
                entire_parser="entire-parser", entire_agent="codex",
            )

        before = collect([first])
        before_id = before["human_records"][0]["event_id"]
        first.write_text(first.read_text() + json.dumps({"type": "assistant", "content": "appended"}) + "\n")
        after = collect([first])
        assert after["human_records"][0]["event_id"] == before_id
        both = collect([first, second])
        ids = {record["event_id"] for record in both["human_records"]}
        assert len(ids) == 2
        assert all(record["native_event_id"] == "duplicate" for record in both["human_records"])
        assert all(record["source_agent"] is None for record in both["human_records"])


    def test_copied_native_session_keeps_same_canonical_event_id(self):
        source_a, source_b = self.tmp_path / "copy-a.jsonl", self.tmp_path / "copy-b.jsonl"
        native = json.dumps({
            "type": "user", "sessionId": "shared-session", "uuid": "same-event",
            "timestamp": "2026-11-13T11:59:00Z",
            "message": {"role": "user", "content": "same"},
        }) + "\n"
        source_a.write_text(native)
        source_b.write_text(native)
        sdk_row = {"v": 1, "type": "user", "id": "same-event", "ts": "2026-11-13T11:59:00Z", "content": "same"}
        self.patch(collector, "run_entire_parser", lambda *_args: [sdk_row])
        result = collector.collect_native_history(
            [str(source_a), str(source_b)], cutoff=NOW, days=1,
            entire_parser="entire-parser", entire_agent="claude-code",
        )
        records = result["human_records"]
        assert len(records) == 2
        assert records[0]["session_id"] == records[1]["session_id"] == "shared-session"
        assert records[0]["event_id"] == records[1]["event_id"]
        assert len(result["export_records"]) == 2

        packet_path = self.tmp_path / "private" / "packet.json"
        collector.write_nudge_packets(packet_path, result["nudge_packet_events"])
        packet = adjudication._load_packet(packet_path)
        assert len(packet["events"]) == 1
        assert packet["events"][0] == result["nudge_packet_events"][0]

        conflicting_packet_path = self.tmp_path / "private" / "conflicting-packet.json"
        conflicting_records = [
            dict(result["nudge_packet_events"][0]),
            {**result["nudge_packet_events"][1], "text": "different"},
        ]
        collector.write_nudge_packets(conflicting_packet_path, conflicting_records)
        assert len(json.loads(conflicting_packet_path.read_text())["events"]) == 2
        with self.assertRaisesRegex(ValueError, "input event IDs must be unique"):
            adjudication._load_packet(conflicting_packet_path)


    def test_entire_preserves_only_uniquely_matched_native_human_evidence(self):
        source = self.tmp_path / "claude.jsonl"
        source.write_text("\n".join(json.dumps(row) for row in (
            {"type": "session_meta", "payload": {"id": "claude-session"}},
            {"type": "user", "uuid": "native-human", "timestamp": "2026-11-13T11:58:00Z",
             "origin": {"kind": "human"},
             "message": {"role": "user", "content": [{"type": "text", "text": "known"}]}},
            {"type": "user", "uuid": "native-unknown", "timestamp": "2026-11-13T11:59:00Z",
             "message": {"role": "user", "content": "unknown"}},
        )) + "\n")
        self.patch(collector, "run_entire_parser", lambda *_args: [
            {"v": 1, "type": "user", "id": "native-human", "ts": "2026-11-13T11:58:00Z",
             "agent": "claude-code", "content": "known"},
            {"v": 1, "type": "user", "id": "native-unknown", "ts": "2026-11-13T11:59:00Z",
             "agent": "claude-code", "content": "unknown"},
        ])
        result = collector.collect_native_history(
            [str(source)], cutoff=NOW, days=1, entire_parser="entire-parser", entire_agent="claude-code",
        )
        records = {row["native_event_id"]: row for row in result["human_records"]}
        assert records["native-human"]["native_origin_status"] == "verified_human"
        assert records["native-human"]["origin_status"] == "verified_human"
        assert records["native-human"]["actor_kind"] == "human"
        assert records["native-unknown"]["native_origin_status"] == "unknown"
        assert records["native-unknown"]["origin_status"] == "unverified_candidate"


    def test_entire_route_preserves_native_session_repository_and_branch(self):
        source = self.tmp_path / "codex.jsonl"
        source.write_text(json.dumps({
            "type": "session_meta", "payload": {
                "id": "git-session", "git_branch": "codex/human-nudges",
                "repository_url": "https://github.com/example/repo.git",
            },
        }) + "\n")
        self.patch(collector, "run_entire_parser", lambda *_args: [{
            "v": 1, "type": "user", "id": "event-1", "ts": "2026-11-13T11:59:00Z",
            "content": "continue",
        }])
        result = collector.collect_native_history(
            [str(source)], cutoff=NOW, days=1, entire_parser="entire-parser", entire_agent="codex",
        )
        record = result["human_records"][0]
        assert record["repository"] == "example/repo"
        assert record["git_branch"] == "codex/human-nudges"
        assert record["branch_source"] == "recorded_repository_url"


    def test_entire_route_preserves_uniquely_matched_event_git_context(self):
        source = self.tmp_path / "claude.jsonl"
        source.write_text(json.dumps({
            "type": "user", "uuid": "native-git-event", "timestamp": "2026-11-13T11:59:00Z",
            "gitBranch": "codex/event-branch", "repository_url": "https://github.com/example/repo.git",
            "message": {"role": "user", "content": "continue"},
        }) + "\n")
        self.patch(collector, "run_entire_parser", lambda *_args: [{
            "v": 1, "type": "user", "id": "native-git-event", "ts": "2026-11-13T11:59:00Z",
            "agent": "claude-code", "content": "continue",
        }])
        result = collector.collect_native_history(
            [str(source)], cutoff=NOW, days=1, entire_parser="entire-parser", entire_agent="claude-code",
        )
        record = result["human_records"][0]
        assert record["repository"] == "example/repo"
        assert record["git_branch"] == "codex/event-branch"


    def test_entire_source_failure_is_visible_not_an_empty_success(self):
        source = _history(self.tmp_path)

        def fail(*_args):
            raise RuntimeError("parser unavailable")

        self.patch(collector, "run_entire_parser", fail)
        result = collector.collect_native_history(
            [str(source)], cutoff=NOW, days=1, entire_parser="entire-parser", entire_agent="codex",
        )
        assert result["stats"]["entire_parser_errors"] == 1
        assert result["stats"]["status"] == "PARTIAL"
        assert result["human_records"] == []


    def test_parser_transport_uses_stdin_explicit_agent_and_canonical_rows(self):
        seen = {}

        class Completed:
            returncode = 0
            stdout = b'{"v":1,"type":"user","content":"safe fixture"}\n'
            stderr = b""

        def run(argv, **kwargs):
            seen["argv"] = argv
            seen.update(kwargs)
            return Completed()

        self.patch(collector.subprocess, "run", run)
        records = collector.run_entire_parser(["entire-parser", "--fixture"], "claude-code", b"fixture")
        assert seen["argv"] == ["entire-parser", "--fixture", "--agent", "claude-code"]
        assert seen["input"] == b"fixture"
        assert records[0]["content"] == "safe fixture"


    def test_metrics_cli_entire_ingress_exports_without_text(self):
        source = _history(self.tmp_path)
        parser = self.tmp_path / "entire-parser"
        parser.write_text(
            "#!/usr/bin/env python3\n"
            "import json, sys\n"
            "assert sys.argv[1:] == ['--agent', 'claude-code']\n"
            "sys.stdin.buffer.read()\n"
            "print(json.dumps({'v': 1, 'type': 'user', 'id': 'cli-user', "
            "'ts': '2026-11-13T11:59:00Z', 'agent': 'claude-code', "
            "'content': 'private fixture text'}))\n"
        )
        parser.chmod(0o700)
        export, packet = self.tmp_path / "history.jsonl", self.tmp_path / "packet.json"
        command = [
            sys.executable, "scripts/prw_metrics.py", "--offline", "--history-root", str(source),
            "--entire-parser", str(parser), "--entire-agent", "claude-code",
            "--history-export", str(export), "--nudge-packets", str(packet),
            "--cutoff", "2026-11-13T12:00:00Z", "--days", "1",
        ]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        assert completed.returncode == 0, completed.stderr
        assert "private fixture text" not in export.read_text()
        assert json.loads(packet.read_text())["events"][0]["text"] == "private fixture text"


    def test_codex_item_completed_user_record_is_collected(self):
        source = self.tmp_path / "codex.jsonl"
        source.write_text(json.dumps({
            "type": "event_msg", "timestamp": "2026-11-13T11:59:00Z",
            "payload": {"type": "item_completed", "item": {
                "id": "completed-user", "type": "message", "role": "user",
                "content": "synthetic Codex user text",
            }},
        }) + "\n")
        data = collector.collect_native_history([str(source)], cutoff=NOW, days=1)
        assert data["human_records"][0]["event_id"] == "completed-user"
        assert data["human_records"][0]["actor_kind"] == "unknown"

