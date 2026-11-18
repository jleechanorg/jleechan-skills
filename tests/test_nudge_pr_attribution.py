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


def test_cli_replay_exports_multi_pr_nudge_counts_to_snapshot(tmp_path):
    import subprocess
    import pytest
    pytest.importorskip("duckdb")
    source, annotations, cache = (tmp_path / name for name in ("source.jsonl", "annotations.jsonl", "prs.json"))
    source.write_text(json.dumps({"record_type": "human", "event_id": "e", "provider": "openai", "timestamp": "2026-10-10T00:00:00Z", "actor_kind": "unknown", "origin_status": "unverified_candidate"}) + "\n")
    annotations.write_text(json.dumps({"event_id": "e", "actor_kind": "human", "message_kind": "continuation/followthrough_nudge", "human_nudge_eligible": True, "association_scope": "multi", "associated_prs": ["example/repo#1", "example/repo#2"], "association_evidence": ["conversation"]}) + "\n")
    cache.write_text(json.dumps({"prs": [{"repo": "example/repo", "number": n, "state": "OPEN", "createdAt": "2026-10-01T00:00:00Z"} for n in (1, 2)]}))
    snapshot = tmp_path / "snapshot.json"
    cmd = [sys.executable, "scripts/prw_metrics.py", "--offline", "--history-replay", str(source), "--history-annotations", str(annotations), "--cutoff", "2026-10-20T00:00:00Z", "--days", "30", "--pr-lookup-cache", str(cache), "--output", str(tmp_path / "report.md"), "--dashboard-json", str(snapshot)]
    result = subprocess.run(cmd, text=True, capture_output=True, timeout=60)
    assert result.returncode == 0, result.stderr
    data = json.loads(snapshot.read_text())
    assert data["human_coverage"]["human_nudge_messages"] == 1
    assert [row["human"]["nudge_messages"] for row in data["prs"]] == [1, 1]


def test_saved_review_without_receipt_survives_collector_and_rejudgment(tmp_path, monkeypatch):
    from datetime import datetime, timezone
    from scripts import native_usage_collector as collector

    source = tmp_path / "source.jsonl"
    source.write_text(json.dumps({"type": "session_meta", "payload": {"id": "s"}}) + "\n")
    rows = [{"v": 1, "type": "user", "id": name, "ts": f"2026-11-13T11:5{i}:00Z", "content": "continue"}
            for i, name in enumerate(("watch", "retracted", "unknown"))]
    monkeypatch.setattr(collector, "run_entire_parser", lambda *_: rows)
    kwargs = dict(cutoff=datetime(2026, 11, 13, 12, tzinfo=timezone.utc), days=1,
                  entire_parser="parser", entire_agent="codex")
    first = collector.collect_native_history([source], **kwargs)
    ids = {e["native_event_id"]: e["event_id"] for e in first["human_records"]}
    reviews = tmp_path / "reviews.jsonl"
    reviews.write_text("\n".join(json.dumps(x) for x in (
        {"event_id": ids["watch"], "actor_kind": "automated_watch", "message_kind": None, "human_nudge_eligible": False},
        {"event_id": ids["retracted"], "actor_kind": "human", "message_kind": None, "human_nudge_eligible": None},
        {"event_id": ids["unknown"], "actor_kind": "unknown"},
    )) + "\n")
    packet = collector.collect_native_history([source], annotation_path=reviews, **kwargs)["nudge_packet_events"]
    fake = tmp_path / "judge.py"
    value = {"actor_kind": "human", "message_kind": "continuation/followthrough_nudge", "human_nudge_eligible": True,
             "association_scope": "multi", "associated_prs": ["example/repo#1", "example/repo#2"], "association_evidence": ["conversation"]}
    response = {"annotations": {event["event_id"]: value for event in packet}}
    fake.write_text("import sys; sys.stdin.read(); print(" + repr(json.dumps(response)) + ")")
    result = {e["event_id"]: e for e in judge._judge({"events": packet}, f"{sys.executable} {fake}", 10)}
    assert result[ids["watch"]]["actor_kind"] == "automated_watch"
    assert result[ids["watch"]]["human_nudge_eligible"] is False
    assert result[ids["retracted"]]["message_kind"] is None
    assert result[ids["retracted"]]["human_nudge_eligible"] is None
    assert result[ids["unknown"]]["actor_kind"] == "human"
    assert result[ids["unknown"]]["associated_prs"] == ["example/repo#1", "example/repo#2"]


def test_previous_judge_output_survives_next_ingestion(tmp_path, monkeypatch):
    from datetime import datetime, timezone
    from scripts import native_usage_collector as collector
    source = tmp_path / "source.jsonl"
    source.write_text(json.dumps({"type": "session_meta", "payload": {"id": "s"}}) + "\n")
    monkeypatch.setattr(collector, "run_entire_parser", lambda *_: [
        {"v": 1, "type": "user", "id": "e", "ts": "2026-11-13T11:59:00Z", "content": "continue"}])
    kwargs = dict(cutoff=datetime(2026, 11, 13, 12, tzinfo=timezone.utc), days=1,
                  entire_parser="parser", entire_agent="codex")
    packet = collector.collect_native_history([source], **kwargs)["nudge_packet_events"]
    event_id = packet[0]["event_id"]
    fake = tmp_path / "judge.py"
    def answer(actor, kind, eligible):
        value = {"actor_kind": actor, "message_kind": kind, "human_nudge_eligible": eligible,
                 "association_scope": "unknown", "associated_prs": [], "association_evidence": []}
        fake.write_text("import sys; sys.stdin.read(); print(" + repr(json.dumps({"annotations": {event_id: value}})) + ")")
        return judge._judge({"events": packet}, f"{sys.executable} {fake}", 10)[0]
    saved = answer("automated_watch", None, False)
    assert "review_id" not in saved
    sidecar = tmp_path / "saved.jsonl"
    sidecar.write_text(json.dumps(saved) + "\n")
    packet = collector.collect_native_history([source], annotation_path=sidecar, **kwargs)["nudge_packet_events"]
    assert answer("human", "continuation/followthrough_nudge", True)["actor_kind"] == "automated_watch"
    assert answer("human", "continuation/followthrough_nudge", True)["human_nudge_eligible"] is False


def test_saved_association_and_null_retraction_survive_readjudication(tmp_path, monkeypatch):
    from datetime import datetime, timezone
    from scripts import native_usage_collector as collector
    source = tmp_path / "source.jsonl"
    source.write_text(json.dumps({"type": "session_meta", "payload": {"id": "s"}}) + "\n")
    monkeypatch.setattr(collector, "run_entire_parser", lambda *_: [
        {"v": 1, "type": "user", "id": name, "ts": f"2026-11-13T11:5{i}:00Z", "content": "continue"}
        for i, name in enumerate(("saved", "retracted", "fresh"))])
    kwargs = dict(cutoff=datetime(2026, 11, 13, 12, tzinfo=timezone.utc), days=1,
                  entire_parser="parser", entire_agent="codex")
    initial = collector.collect_native_history([source], **kwargs)["human_records"]
    ids = {e["native_event_id"]: e["event_id"] for e in initial}
    sidecar = tmp_path / "saved.jsonl"
    sidecar.write_text("\n".join(json.dumps(x) for x in (
        {"event_id": ids["saved"], "association_scope": "single", "associated_prs": ["example/repo#1"], "association_evidence": ["conversation"]},
        {"event_id": ids["retracted"], "association_scope": None},
    )) + "\n")
    packet = collector.collect_native_history([source], annotation_path=sidecar, **kwargs)["nudge_packet_events"]
    value = {"actor_kind": "human", "message_kind": "continuation/followthrough_nudge", "human_nudge_eligible": True,
             "association_scope": "multi", "associated_prs": ["example/repo#2", "example/repo#3"], "association_evidence": ["conversation"]}
    fake = tmp_path / "judge.py"
    fake.write_text("import sys; sys.stdin.read(); print(" + repr(json.dumps({"annotations": {e["event_id"]: value for e in packet}})) + ")")
    result = {e["event_id"]: e for e in judge._judge({"events": packet}, f"{sys.executable} {fake}", 10)}
    assert result[ids["saved"]]["associated_prs"] == ["example/repo#1"]
    assert result[ids["retracted"]]["association_scope"] == "unknown"
    assert result[ids["retracted"]]["associated_prs"] == []
    assert result[ids["fresh"]]["associated_prs"] == ["example/repo#2", "example/repo#3"]


def test_malformed_saved_association_does_not_block_new_memberships(tmp_path, monkeypatch):
    from datetime import datetime, timezone
    from scripts import native_usage_collector as collector
    source = tmp_path / "source.jsonl"
    source.write_text(json.dumps({"type": "session_meta", "payload": {"id": "s"}}) + "\n")
    monkeypatch.setattr(collector, "run_entire_parser", lambda *_: [
        {"v": 1, "type": "user", "id": str(i), "ts": f"2026-11-13T11:5{i}:00Z", "content": "continue"}
        for i in range(4)])
    kwargs = dict(cutoff=datetime(2026, 11, 13, 12, tzinfo=timezone.utc), days=1,
                  entire_parser="parser", entire_agent="codex")
    initial = collector.collect_native_history([source], **kwargs)["human_records"]
    ids = [e["event_id"] for e in initial]
    invalid = [
        {"association_scope": [], "associated_prs": [], "association_evidence": []},
        {"association_scope": {}, "associated_prs": [], "association_evidence": []},
        {"association_scope": "single", "associated_prs": ["not-a-pr"], "association_evidence": ["conversation"]},
        {"association_scope": "multi", "associated_prs": ["example/repo#1", "example/repo#1"], "association_evidence": ["conversation"]},
    ]
    sidecar = tmp_path / "saved.jsonl"
    sidecar.write_text("\n".join(json.dumps({"event_id": event_id, **item}) for event_id, item in zip(ids, invalid)) + "\n")
    packet = collector.collect_native_history([source], annotation_path=sidecar, **kwargs)["nudge_packet_events"]
    value = {"actor_kind": "unknown", "message_kind": None, "human_nudge_eligible": None,
             "association_scope": "multi", "associated_prs": ["example/repo#2", "example/repo#3"], "association_evidence": ["conversation"]}
    fake = tmp_path / "judge.py"
    fake.write_text("import sys; sys.stdin.read(); print(" + repr(json.dumps({"annotations": {e["event_id"]: value for e in packet}})) + ")")
    result = judge._judge({"events": packet}, f"{sys.executable} {fake}", 10)
    assert all(e["associated_prs"] == ["example/repo#2", "example/repo#3"] for e in result)


def test_scope_null_retracts_existing_binding_and_context():
    for previous in ({"pr_binding": {"pr": "example/repo#1"}},
                     {"context_pr_decision": "override", "effective_associated_pr": "example/repo#1"}):
        record = {"event_id": "e", "timestamp": "2026-10-10T00:00:00Z", "actor_kind": "human",
                  "message_kind": "continuation/followthrough_nudge", "human_nudge_eligible": True,
                  "repository": "example/repo", "git_branch": "topic", **previous}
        _apply_replay_annotation(record, {"association_scope": None})
        prs = [{"repo": "example/repo", "number": 1, "headRefName": "topic", "createdAt": "2026-10-01T00:00:00Z"}]
        summary = aggregate_native_human_steering([record], prs, window_start="2026-10-01T00:00:00Z", window_end="2026-10-20T00:00:00Z")
        assert summary["coverage"]["assigned_verified_messages"] == 0
        assert summary["per_pr"][0]["human_nudge_messages"] == 0


def test_null_prior_human_origin_does_not_keep_verified_human(tmp_path):
    packet = {"events": [{"event_id": "e", "text": "continue", "context": [], "prior_review": {"human_origin": None}}]}
    value = {"actor_kind": "unknown", "message_kind": "continuation/followthrough_nudge", "human_nudge_eligible": True,
             "association_scope": "unknown", "associated_prs": [], "association_evidence": []}
    fake = tmp_path / "judge.py"
    fake.write_text("import sys; sys.stdin.read(); print(" + repr(json.dumps({"annotations": {"e": value}})) + ")")
    annotation = judge._judge(packet, f"{sys.executable} {fake}", 10)[0]
    record = {"event_id": "e", "timestamp": "2026-10-10T00:00:00Z", "origin_status": "verified_human", "actor_kind": "human"}
    _apply_replay_annotation(record, annotation)
    summary = aggregate_native_human_steering([record], [], window_start="2026-10-01T00:00:00Z", window_end="2026-10-20T00:00:00Z")
    assert summary["coverage"]["human_nudge_messages"] == 0
    assert record["origin_status"] == "unverified_candidate"


def test_equivalent_multi_membership_order_does_not_dispute():
    base = {"event_id": "e", "provider": "codex", "timestamp": "2026-10-10T00:00:00Z", "actor_kind": "human",
            "message_kind": "continuation/followthrough_nudge", "human_nudge_eligible": True,
            "association_scope": "multi", "association_evidence": ["conversation"]}
    records = [dict(base, associated_prs=values) for values in (["example/repo#1", "example/repo#2"], ["example/repo#2", "example/repo#1"])]
    summary = aggregate_native_human_steering(records, [], window_start="2026-10-01T00:00:00Z", window_end="2026-10-20T00:00:00Z")
    assert summary["coverage"]["human_nudge_messages"] == 1
    assert [row["human_nudge_messages"] for row in summary["per_pr"]] == [1, 1]


def test_same_annotation_retractions_override_competing_associations():
    conflicts = [
        {"association_scope": None, "pr_binding": {"pr": "example/repo#1"}},
        {"pr_binding": None, "association_scope": "single", "associated_prs": ["example/repo#1"], "association_evidence": ["conversation"]},
        {"context_pr_decision": None, "association_scope": "single", "associated_prs": ["example/repo#1"], "association_evidence": ["conversation"]},
    ]
    for annotation in conflicts:
        record = {"event_id": "e", "timestamp": "2026-10-10T00:00:00Z", "actor_kind": "human",
                  "message_kind": "continuation/followthrough_nudge", "human_nudge_eligible": True,
                  "repository": "example/repo", "git_branch": "topic"}
        _apply_replay_annotation(record, annotation)
        prs = [{"repo": "example/repo", "number": 1, "headRefName": "topic", "createdAt": "2026-10-01T00:00:00Z"}]
        result = aggregate_native_human_steering([record], prs, window_start="2026-10-01T00:00:00Z", window_end="2026-10-20T00:00:00Z")
        assert result["coverage"]["assigned_verified_messages"] == 0
        assert result["per_pr"][0]["human_nudge_messages"] == 0


def test_equivalent_evidence_order_does_not_dispute():
    base = {"event_id": "e", "provider": "codex", "timestamp": "2026-10-10T00:00:00Z", "actor_kind": "human",
            "message_kind": "continuation/followthrough_nudge", "human_nudge_eligible": True,
            "association_scope": "multi", "associated_prs": ["example/repo#1", "example/repo#2"]}
    records = [dict(base, association_evidence=x) for x in (["conversation", "git_context"], ["git_context", "conversation"])]
    result = aggregate_native_human_steering(records, [], window_start="2026-10-01T00:00:00Z", window_end="2026-10-20T00:00:00Z")
    assert result["coverage"]["human_nudge_messages"] == 1
    assert [r["human_nudge_messages"] for r in result["per_pr"]] == [1, 1]


def test_legacy_four_field_array_adapter_remains_supported(tmp_path):
    fake = tmp_path / "judge.py"
    value = {"event_id": "e", "actor_kind": "human", "message_kind": "continuation/followthrough_nudge", "human_nudge_eligible": True}
    fake.write_text("import sys; sys.stdin.read(); print(" + repr(json.dumps({"annotations": [value]})) + ")")
    result = judge._judge({"events": [{"event_id": "e", "text": "continue", "context": []}]}, f"{sys.executable} {fake}", 10)
    assert result == [value]


def test_null_binding_preserves_explicit_legacy_decision_matrix():
    cases = [("override", "example/repo#2", 1, "reviewed_context_override_messages"),
             ("unassigned_multi_pr", None, 0, "multi_pr_unassigned_messages"),
             ("unassigned_global_scope", None, 0, "global_scope_unassigned_messages")]
    for decision, pr, assigned, counter in cases:
        record = {"event_id": "e", "timestamp": "2026-10-10T00:00:00Z", "actor_kind": "human", "pr_binding": {"pr": "example/repo#1"}}
        _apply_replay_annotation(record, {"pr_binding": None, "context_pr_decision": decision, "effective_associated_pr": pr})
        result = aggregate_native_human_steering([record], [], window_start="2026-10-01T00:00:00Z", window_end="2026-10-20T00:00:00Z")
        assert result["coverage"]["assigned_verified_messages"] == assigned
        assert result["coverage"][counter] == 1
        if pr:
            assert next(r for r in result["per_pr"] if r["pr"] == pr)["raw_verified_messages"] == 1


def test_legacy_multi_from_sidecar_through_collector_judge_and_replay(tmp_path, monkeypatch):
    from datetime import datetime, timezone
    from scripts import native_usage_collector as collector
    source = tmp_path / "source.jsonl"
    source.write_text(json.dumps({"type": "session_meta", "payload": {"id": "s"}}) + "\n")
    monkeypatch.setattr(collector, "run_entire_parser", lambda *_: [{"v": 1, "type": "user", "id": "e", "ts": "2026-11-13T11:59:00Z", "content": "continue both"}])
    kwargs = dict(cutoff=datetime(2026, 11, 13, 12, tzinfo=timezone.utc), days=1, entire_parser="parser", entire_agent="codex")
    event_id = collector.collect_native_history([source], **kwargs)["human_records"][0]["event_id"]
    sidecar = tmp_path / "saved.jsonl"
    sidecar.write_text(json.dumps({"event_id": event_id, "actor_kind": "human", "message_kind": "continuation/followthrough_nudge", "human_nudge_eligible": True, "context_pr_decision": "unassigned_multi_pr", "pr_binding": None}) + "\n")
    packet = collector.collect_native_history([source], annotation_path=sidecar, **kwargs)["nudge_packet_events"]
    value = {"actor_kind": "human", "message_kind": "continuation/followthrough_nudge", "human_nudge_eligible": True, "association_scope": "multi", "associated_prs": ["example/repo#1", "example/repo#2"], "association_evidence": ["conversation"]}
    fake = tmp_path / "judge.py"
    fake.write_text("import sys; sys.stdin.read(); print(" + repr(json.dumps({"annotations": {event_id: value}})) + ")")
    judged = judge._judge({"events": packet}, f"{sys.executable} {fake}", 10)[0]
    record = {"event_id": event_id, "timestamp": "2026-11-13T11:59:00Z"}
    _apply_replay_annotation(record, judged)
    result = aggregate_native_human_steering([record], [], window_start="2026-11-13T00:00:00Z", window_end="2026-11-14T00:00:00Z")
    assert result["coverage"]["human_nudge_messages"] == 1
    assert [r["human_nudge_messages"] for r in result["per_pr"]] == [1, 1]


def test_saved_legacy_multi_memberships_survive_null_binding_end_to_end(tmp_path, monkeypatch):
    from datetime import datetime, timezone
    from scripts import native_usage_collector as collector
    source = tmp_path / "source.jsonl"
    source.write_text(json.dumps({"type": "session_meta", "payload": {"id": "s"}}) + "\n")
    monkeypatch.setattr(collector, "run_entire_parser", lambda *_: [{"v": 1, "type": "user", "id": "e", "ts": "2026-11-13T11:59:00Z", "content": "continue both"}])
    kwargs = dict(cutoff=datetime(2026, 11, 13, 12, tzinfo=timezone.utc), days=1, entire_parser="parser", entire_agent="codex")
    event_id = collector.collect_native_history([source], **kwargs)["human_records"][0]["event_id"]
    sidecar = tmp_path / "saved.jsonl"
    sidecar.write_text(json.dumps({"event_id": event_id, "actor_kind": "human", "message_kind": "continuation/followthrough_nudge", "human_nudge_eligible": True, "context_pr_decision": "unassigned_multi_pr", "pr_binding": None, "association_scope": "multi", "associated_prs": ["example/repo#1", "example/repo#2"], "association_evidence": ["conversation"]}) + "\n")
    packet = collector.collect_native_history([source], annotation_path=sidecar, **kwargs)["nudge_packet_events"]
    value = {"actor_kind": "human", "message_kind": "continuation/followthrough_nudge", "human_nudge_eligible": True, "association_scope": "single", "associated_prs": ["example/repo#3"], "association_evidence": ["conversation"]}
    fake = tmp_path / "judge.py"
    fake.write_text("import sys; sys.stdin.read(); print(" + repr(json.dumps({"annotations": {event_id: value}})) + ")")
    judged = judge._judge({"events": packet}, f"{sys.executable} {fake}", 10)[0]
    record = {"event_id": event_id, "timestamp": "2026-11-13T11:59:00Z"}
    _apply_replay_annotation(record, judged)
    result = aggregate_native_human_steering([record], [], window_start="2026-11-13T00:00:00Z", window_end="2026-11-14T00:00:00Z")
    assert result["coverage"]["human_nudge_messages"] == 1
    assert [(r["pr"], r["human_nudge_messages"]) for r in result["per_pr"]] == [("example/repo#1", 1), ("example/repo#2", 1)]
