import json
import sys
from pathlib import Path

from scripts import human_nudge_adjudication as judge
from scripts.native_usage_collector import _apply_replay_annotation
from scripts.prw_metrics import aggregate_native_human_steering


def test_unbound_judgments_flow_to_unique_global_and_per_pr_counts(tmp_path):
    prs = [{"repo": "example/repo", "number": n, "createdAt": "2026-10-01T00:00:00Z"} for n in (1, 2, 3)]
    events = [{"event_id": str(i), "provider": "codex", "timestamp": "2026-10-10T00:00:00Z", "text": text,
               "context": [{"role": "assistant", "text": "Working on PRs 1 and 2"}],
               "actor_kind": "unknown"}
              for i, text in enumerate(("Continue PR 1", "Continue both", "Continue everywhere", "Continue", "watch", "unrelated"))]
    outcomes = [("human", "single", ["example/repo#1"]), ("human", "multi", ["example/repo#1", "example/repo#2"]),
                ("human", "global", []), ("human", "unknown", []), ("automated_watch", "single", ["example/repo#1"]),
                ("human", "single", ["example/repo#3"])]
    annotations = [{"event_id": str(i), "actor_kind": actor, "message_kind": "continuation/followthrough_nudge",
                    "human_nudge_eligible": True, "association_scope": scope, "associated_prs": selected, "association_evidence": ["conversation"]}
                   for i, (actor, scope, selected) in enumerate(outcomes)]
    fake = tmp_path / "judge.py"
    fake.write_text("import json,sys\nr=json.load(sys.stdin)\nassert r['packet']['pr_candidates']\nprint(" + repr(json.dumps({"annotations": annotations})) + ")\n")
    packet = {"schema_version": "human-nudge-input.v1", "events": events, "pr_candidates": prs}
    reviewed = judge._judge(packet, f"{sys.executable} {fake}", 10)
    records = []
    for event, annotation in zip(events, reviewed):
        record = {key: event[key] for key in ("event_id", "provider", "timestamp")}
        _apply_replay_annotation(record, annotation)
        records.append(record)
    result = aggregate_native_human_steering(records, prs, window_start="2026-10-01T00:00:00Z", window_end="2026-10-20T00:00:00Z")
    rows = {row["pr"]: row for row in result["per_pr"]}
    assert result["coverage"]["human_nudge_messages"] == 5
    assert result["coverage"]["assigned_verified_messages"] == 3
    assert [rows[f"example/repo#{n}"]["human_nudge_messages"] for n in (1, 2, 3)] == [2, 1, 1]


def test_event_time_binding_is_context_not_an_automatic_association(tmp_path, monkeypatch):
    from datetime import datetime, timezone
    from scripts import native_usage_collector as collector

    source = tmp_path / "native.jsonl"
    source.write_text(json.dumps({"type": "session_meta", "payload": {"id": "session-1"}}) + "\n")
    ledger = tmp_path / "bindings.jsonl"
    ledger.write_text(json.dumps({"v": 1, "kind": "pr_binding", "session_id": "session-1",
                                  "ts": "2026-11-13T11:00:00Z", "pr": "example/repo#1"}) + "\n")
    rows = [{"v": 1, "type": "user", "id": "e", "ts": "2026-11-13T11:59:00Z", "content": "Continue"}]
    monkeypatch.setattr(collector, "run_entire_parser", lambda *_: rows)
    data = collector.collect_native_history([source], cutoff=datetime(2026, 11, 13, 12, tzinfo=timezone.utc), days=1,
                                            entire_parser="parser", entire_agent="codex", session_bindings=[ledger])
    event = data["nudge_packet_events"][0]
    assert event["session_binding_evidence"]["pr"] == "example/repo#1"
    assert data["human_records"][0]["session_binding_evidence"] == event["session_binding_evidence"]
    assert "pr_binding" not in data["human_records"][0]
    packet = tmp_path / "packet.json"
    candidates = [{"repo": "example/repo", "number": 1}]
    collector.write_nudge_packets(packet, data["nudge_packet_events"], candidates)
    assert json.loads(packet.read_text())["pr_candidates"] == candidates
    assert "Continue" not in json.dumps(data["export_records"])


def test_reviewed_retraction_blocks_reassignment():
    record = {"actor_kind": "human", "repository": "example/repo", "git_branch": "topic"}
    _apply_replay_annotation(record, {"context_pr_decision": None})
    assert record["association_scope"] == "unknown"
    record.update(event_id="e", timestamp="2026-10-10T00:00:00Z")
    prs = [{"repo": "example/repo", "number": 1, "headRefName": "topic", "createdAt": "2026-10-01T00:00:00Z"}]
    result = aggregate_native_human_steering([record], prs, window_start="2026-10-01T00:00:00Z", window_end="2026-10-20T00:00:00Z")
    assert result["coverage"]["unassigned_verified_messages"] == 1
    assert result["per_pr"][0]["raw_verified_messages"] == 0


def test_existing_actor_decisions_and_retractions_survive_readjudication(tmp_path, monkeypatch):
    from datetime import datetime, timezone
    from scripts import native_usage_collector as collector

    source = tmp_path / "source.jsonl"
    source.write_text(json.dumps({"type": "session_meta", "payload": {"id": "s"}}) + "\n")
    monkeypatch.setattr(collector, "run_entire_parser", lambda *_: [
        {"v": 1, "type": "user", "id": "e", "ts": "2026-11-13T11:59:00Z", "content": "continue"}])
    kwargs = dict(cutoff=datetime(2026, 11, 13, 12, tzinfo=timezone.utc), days=1,
                  entire_parser="parser", entire_agent="codex")
    first = collector.collect_native_history([source], **kwargs)
    event_id = first["human_records"][0]["event_id"]
    reviews = tmp_path / "reviews.jsonl"
    reviews.write_text(json.dumps({"event_id": event_id, "actor_kind": "human", "message_kind": None,
                                   "human_nudge_eligible": None, "review_id": "review-1"}) + "\n")
    event = collector.collect_native_history([source], annotation_path=reviews, **kwargs)["nudge_packet_events"][0]
    fake = tmp_path / "judge.py"
    result = {"annotations": [{"event_id": event_id, "actor_kind": "unknown", "message_kind": "initial_task",
                                "human_nudge_eligible": False, "association_scope": "unknown",
                                "associated_prs": [], "association_evidence": []}]}
    fake.write_text("import sys\nsys.stdin.read()\nprint(" + repr(json.dumps(result)) + ")\n")
    annotation = judge._judge({"schema_version": "human-nudge-input.v1", "events": [event]},
                              f"{sys.executable} {fake}", 10)[0]
    assert annotation["actor_kind"] == "human"
    assert annotation["message_kind"] is None
    assert annotation["human_nudge_eligible"] is None


def test_unreviewed_unknown_can_be_reclassified_and_linked(tmp_path):
    event = {"event_id": "e", "text": "continue PR 1", "context": [], "actor_kind": "unknown",
             "association_scope": "unknown", "associated_prs": [], "association_evidence": []}
    result = {"annotations": [{"event_id": "e", "actor_kind": "human",
              "message_kind": "continuation/followthrough_nudge", "human_nudge_eligible": True,
              "association_scope": "single", "associated_prs": ["example/repo#1"],
              "association_evidence": ["conversation"]}]}
    fake = tmp_path / "judge.py"
    fake.write_text("import sys\nsys.stdin.read()\nprint(" + repr(json.dumps(result)) + ")\n")
    output = judge._judge({"events": [event]}, f"{sys.executable} {fake}", 10)[0]
    assert output["actor_kind"] == "human"
    assert output["associated_prs"] == ["example/repo#1"]


def test_legacy_multi_disposition_accepts_new_multi_memberships(tmp_path):
    event = {"event_id": "e", "provider": "codex", "timestamp": "2026-10-10T00:00:00Z",
             "text": "continue both PRs", "context": [], "actor_kind": "human",
             "context_pr_decision": "unassigned_multi_pr", "context_associated_pr": None,
             "effective_associated_pr": None, "pr_binding": None,
             "association_retracted": True}
    result = {"annotations": [{"event_id": "e", "actor_kind": "human",
              "message_kind": "continuation/followthrough_nudge", "human_nudge_eligible": True,
              "association_scope": "multi", "associated_prs": ["example/repo#1", "example/repo#2"],
              "association_evidence": ["conversation"]}]}
    fake = tmp_path / "judge.py"
    fake.write_text("import sys\nsys.stdin.read()\nprint(" + repr(json.dumps(result)) + ")\n")
    annotation = judge._judge({"events": [event]}, f"{sys.executable} {fake}", 10)[0]
    assert annotation["associated_prs"] == ["example/repo#1", "example/repo#2"]
    record = {"event_id": "e", "provider": "codex", "timestamp": event["timestamp"]}
    _apply_replay_annotation(record, annotation)
    prs = [{"repo": "example/repo", "number": n, "createdAt": "2026-10-01T00:00:00Z"} for n in (1, 2, 3)]
    aggregate = aggregate_native_human_steering([record], prs, window_start="2026-10-01T00:00:00Z", window_end="2026-10-20T00:00:00Z")
    assert aggregate["coverage"]["human_nudge_messages"] == 1
    assert [r["human_nudge_messages"] for r in aggregate["per_pr"]] == [1, 1, 0]


def test_legacy_global_and_unknown_dispositions_do_not_restore_association(tmp_path):
    fake = tmp_path / "judge.py"
    result = {"annotations": [{"event_id": "e", "actor_kind": "human", "message_kind": "continuation/followthrough_nudge",
                                "human_nudge_eligible": True, "association_scope": "multi",
                                "associated_prs": ["example/repo#1", "example/repo#2"], "association_evidence": ["conversation"]}]}
    fake.write_text("import sys\nsys.stdin.read()\nprint(" + repr(json.dumps(result)) + ")\n")
    for decision in ("unassigned_global_scope", "unassigned_no_single_pr"):
        event = {"event_id": "e", "text": "continue", "context": [], "context_pr_decision": decision,
                 "original_associated_pr": "example/repo#1", "effective_associated_pr": None}
        annotation = judge._judge({"events": [event]}, f"{sys.executable} {fake}", 10)[0]
        assert "associated_prs" not in annotation
        record = {"event_id": "e", "timestamp": "2026-10-10T00:00:00Z"}
        _apply_replay_annotation(record, annotation)
        summary = aggregate_native_human_steering([record], [], window_start="2026-10-01T00:00:00Z", window_end="2026-10-20T00:00:00Z")
        assert summary["coverage"]["unassigned_verified_messages"] == 1
        assert all(row["raw_verified_messages"] == 0 for row in summary["per_pr"])
