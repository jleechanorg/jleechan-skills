"""Tests for hardened command and skill usage audit scanner and reachability contracts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.audit_command_skill_usage import audit, digest

START_UTC = "2026-07-30T00:00:00Z"
END_UTC = "2026-08-29T00:00:00Z"


def build_audit_fixture(
    tmp_path: Path,
    *,
    events: list[dict],
    commands: list[dict] | None = None,
    skills: list[dict] | None = None,
    excluded_docs: dict[str, str] | None = None,
    manifest_overrides: dict | None = None,
    corrupt_inventory: bool = False,
    corrupt_corpus: bool = False,
) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    if commands is None:
        commands = [
            {"command": "f", "base_name": "f", "path": str(tmp_path / "f.md"), "callable": True, "exclusion_reason": ""},
            {"command": "af", "base_name": "af", "path": str(tmp_path / "af.md"), "callable": True, "exclusion_reason": ""},
            {"command": "browserclaw", "base_name": "browserclaw", "path": str(tmp_path / "browserclaw.md"), "callable": True, "exclusion_reason": ""},
            {"command": "repro", "base_name": "repro", "path": str(tmp_path / "repro.md"), "callable": True, "exclusion_reason": ""},
            {"command": "backend-first", "base_name": "backend-first", "path": str(tmp_path / "backend-first.md"), "callable": True, "exclusion_reason": ""},
            {"command": "extended-library:4layer", "base_name": "4layer", "path": str(tmp_path / "4layer.md"), "callable": True, "exclusion_reason": ""},
            {"command": "extended-library:aar", "base_name": "aar", "path": str(tmp_path / "aar.md"), "callable": True, "exclusion_reason": ""},
            {"command": "extended-library:callpath", "base_name": "callpath", "path": str(tmp_path / "callpath.md"), "callable": True, "exclusion_reason": ""},
            {"command": "README", "base_name": "README", "path": str(tmp_path / "README.md"), "callable": False, "exclusion_reason": "directory documentation"},
        ]
        # Create dummy command files with realistic pointers
        (tmp_path / "f.md").write_text("---\ndescription: /f\n---\n# /f\nRead `.claude/skills/dark-factory/SKILL.md`\n")
        (tmp_path / "af.md").write_text("---\ndescription: Alias for /f\n---\n# /af\nShortcut alias for `/f`.\n")
        (tmp_path / "browserclaw.md").write_text("# /browserclaw\nRead `skills/browserclaw/SKILL.md`\n")
        (tmp_path / "repro.md").write_text("---\ndescription: /repro\n---\n# /repro\nRead `.claude/skills/repro-evidence/SKILL.md`\n")
        (tmp_path / "backend-first.md").write_text("---\ndescription: /backend-first\n---\nRead `~/.claude/skills/backend-first/SKILL.md`\n")
        (tmp_path / "4layer.md").write_text("---\ndescription: /4layer\n---\nRead `~/.claude/skills/4layer/SKILL.md`\n- `.claude/skills/pr-blocker-min-repro/SKILL.md`\n- `.claude/skills/integration-verification/SKILL.md`\n")
        (tmp_path / "aar.md").write_text("---\ndescription: Alias for /accept-adapt-reject\n---\nShortcut alias for `/accept-adapt-reject`. Read `~/.hermes/skills/accept-adapt-reject/SKILL.md`\n")
        (tmp_path / "callpath.md").write_text("---\ndescription: /callpath\n---\nFull rules: `~/.claude/skills/callpath/SKILL.md`\n")
        (tmp_path / "README.md").write_text("# Documentation\nNot callable.\n")

    if skills is None:
        skills = [
            {"skill": "dark-factory", "path": str(tmp_path / "skills" / "dark-factory" / "SKILL.md")},
            {"skill": "auto-factory", "path": str(tmp_path / "skills" / "auto-factory" / "SKILL.md")},
            {"skill": "browserclaw", "path": str(tmp_path / "skills" / "browserclaw" / "SKILL.md")},
            {"skill": "repro-evidence", "path": str(tmp_path / "skills" / "repro-evidence" / "SKILL.md")},
            {"skill": "backend-first", "path": str(tmp_path / "skills" / "backend-first" / "SKILL.md")},
            {"skill": "4layer", "path": str(tmp_path / "skills" / "4layer" / "SKILL.md")},
            {"skill": "pr-blocker-min-repro", "path": str(tmp_path / "skills" / "pr-blocker-min-repro" / "SKILL.md")},
            {"skill": "integration-verification", "path": str(tmp_path / "skills" / "integration-verification" / "SKILL.md")},
            {"skill": "accept-adapt-reject", "path": str(tmp_path / "skills" / "accept-adapt-reject" / "SKILL.md")},
            {"skill": "callpath", "path": str(tmp_path / "skills" / "callpath" / "SKILL.md")},
            {"skill": "unreached-skill", "path": str(tmp_path / "skills" / "unreached-skill" / "SKILL.md")},
        ]
        for sk in skills:
            sk_path = Path(sk["path"])
            sk_path.parent.mkdir(parents=True, exist_ok=True)
            sk_path.write_text(f"---\nname: {sk['skill']}\ndescription: Test skill\n---\n# {sk['skill']}\n")

    if excluded_docs is None:
        excluded_docs = {"README": "directory documentation"}

    inv_data = {"snapshot_id": "snap-1", "commands": commands, "skills": skills}
    inv_bytes = (json.dumps(inv_data) + "\n").encode()
    inv_file = tmp_path / "inventory-snapshot.json"
    inv_file.write_bytes(inv_bytes)

    corpus_data = {
        "snapshot_id": "snap-1",
        "window_start_inclusive": START_UTC,
        "window_end_exclusive": END_UTC,
        "coverage": {"files_scanned": 1, "events_retained": len(events)},
        "events": events,
    }
    corpus_bytes = (json.dumps(corpus_data) + "\n").encode()
    corpus_file = tmp_path / "normalized-event-corpus.json"
    corpus_file.write_bytes(corpus_bytes)

    manifest = {
        "schema": "claude_usage_audit_manifest.v2",
        "snapshot_id": "snap-1",
        "window_start_inclusive": START_UTC,
        "window_end_exclusive": END_UTC,
        "boundary_convention": "start <= event timestamp < end",
        "inventory_snapshot": "inventory-snapshot.json",
        "inventory_snapshot_sha256": "bad" if corrupt_inventory else digest(inv_bytes),
        "normalized_event_corpus": "normalized-event-corpus.json",
        "normalized_event_corpus_sha256": "bad" if corrupt_corpus else digest(corpus_bytes),
        "excluded_command_documents": excluded_docs,
    }
    if manifest_overrides:
        manifest.update(manifest_overrides)

    man_file = tmp_path / "audit-manifest.json"
    man_file.write_text(json.dumps(manifest, indent=2) + "\n")
    return man_file


def test_reachability_and_closure_fixtures(tmp_path: Path) -> None:
    """Validate reachability discovery for /af, /4layer, browserclaw, aar, repro, backend-first, and callpath."""
    manifest = build_audit_fixture(tmp_path, events=[])
    out_dir = tmp_path / "out"
    audit(manifest, out_dir, repo_root=tmp_path, ignore_scanner_hash=True)

    skills_res = json.loads((out_dir / "skill-usage-30d.json").read_text())
    skills_map = {r["skill"]: r for r in skills_res["skills"]}

    # Verify command-to-skill reachability links
    assert "dark-factory" in skills_map
    assert "f" in skills_map["dark-factory"]["reachable_from_commands"]

    assert "4layer" in skills_map
    assert "extended-library:4layer" in skills_map["4layer"]["reachable_from_commands"]
    assert "extended-library:4layer" in skills_map["pr-blocker-min-repro"]["reachable_from_commands"]
    assert "extended-library:4layer" in skills_map["integration-verification"]["reachable_from_commands"]

    assert "browserclaw" in skills_map
    assert "browserclaw" in skills_map["browserclaw"]["reachable_from_commands"]

    assert "repro-evidence" in skills_map
    assert "repro" in skills_map["repro-evidence"]["reachable_from_commands"]

    assert "backend-first" in skills_map
    assert "backend-first" in skills_map["backend-first"]["reachable_from_commands"]

    assert "callpath" in skills_map
    assert "extended-library:callpath" in skills_map["callpath"]["reachable_from_commands"]

    assert "accept-adapt-reject" in skills_map
    assert "extended-library:aar" in skills_map["accept-adapt-reject"]["reachable_from_commands"]


def test_static_reachability_never_claims_execution(tmp_path: Path) -> None:
    """Static reachability must classify as reachability_only, NOT as positive execution evidence."""
    # No events in corpus
    manifest = build_audit_fixture(tmp_path, events=[])
    out_dir = tmp_path / "out"
    audit(manifest, out_dir, repo_root=tmp_path, ignore_scanner_hash=True)

    skills_res = json.loads((out_dir / "skill-usage-30d.json").read_text())
    skills_map = {r["skill"]: r for r in skills_res["skills"]}

    # 4layer is reachable via extended-library:4layer, but has 0 explicit selections
    layer_skill = skills_map["4layer"]
    assert layer_skill["explicit_skill_selections"] == 0
    assert layer_skill["reachability_only"] is True
    assert layer_skill["positive_evidence"] is False
    assert layer_skill["archive_eligible_from_usage_alone"] is False

    # unreached skill has 0 selections and 0 reachability
    unreached = skills_map["unreached-skill"]
    assert unreached["explicit_skill_selections"] == 0
    assert unreached["reachability_only"] is False
    assert unreached["no_evidence_in_source"] is True
    assert unreached["positive_evidence"] is False
    assert unreached["archive_eligible_from_usage_alone"] is False


def test_alias_resolution_and_provenance(tmp_path: Path) -> None:
    """Validate that invocations via aliases (/af, /aar) resolve to canonical targets with alias attribution."""
    events = [
        {
            "event_id": "e1",
            "timestamp": "2026-08-01T12:00:00Z",
            "kind": "command_candidate",
            "prompt_source": "typed",
            "origin_kind": "human",
            "leading_slash": "af",
        },
        {
            "event_id": "e2",
            "timestamp": "2026-08-02T12:00:00Z",
            "kind": "command_candidate",
            "prompt_source": "typed",
            "origin_kind": "human",
            "leading_slash": "aar",
        },
    ]
    manifest = build_audit_fixture(tmp_path, events=events)
    out_dir = tmp_path / "out"
    audit(manifest, out_dir, repo_root=tmp_path, ignore_scanner_hash=True)

    cmds_res = json.loads((out_dir / "strict-claude-command-usage-30d.json").read_text())
    cmds_map = {r["command"]: r for r in cmds_res["commands"]}

    # /af resolved to /af command and tracked
    assert cmds_map["af"]["total_observed_events"] == 1
    assert cmds_map["af"]["positive_evidence"] is True
    assert cmds_map["af"]["archive_eligible_from_usage_alone"] is False


def test_operator_confirmation_tier(tmp_path: Path) -> None:
    """Operator confirmations must set operator_confirmed_use and positive_evidence without inventing telemetry."""
    manifest = build_audit_fixture(
        tmp_path,
        events=[],
        manifest_overrides={
            "operator_confirmations": {
                "extended-library:4layer": "Used weekly during multi-tier repro investigations",
                "callpath": "Used in incident triage",
            }
        },
    )
    out_dir = tmp_path / "out"
    audit(manifest, out_dir, repo_root=tmp_path, ignore_scanner_hash=True)

    cmds_res = json.loads((out_dir / "strict-claude-command-usage-30d.json").read_text())
    cmds_map = {r["command"]: r for r in cmds_res["commands"]}
    assert cmds_map["extended-library:4layer"]["operator_confirmed_use"] is True
    assert cmds_map["extended-library:4layer"]["positive_evidence"] is True
    assert cmds_map["extended-library:4layer"]["canonical_direct_events"] == 0

    skills_res = json.loads((out_dir / "skill-usage-30d.json").read_text())
    skills_map = {r["skill"]: r for r in skills_res["skills"]}
    assert skills_map["callpath"]["operator_confirmed_use"] is True
    assert skills_map["callpath"]["positive_evidence"] is True


def test_half_open_window_and_fail_closed(tmp_path: Path) -> None:
    """Validate half-open start <= t < end boundaries and fail-closed corrupt hashes."""
    valid_events = [
        {"event_id": "e_start", "timestamp": START_UTC, "kind": "skill_selection", "selected_name": "4layer"},
    ]
    manifest = build_audit_fixture(tmp_path, events=valid_events)
    out_dir = tmp_path / "out"
    audit(manifest, out_dir, repo_root=tmp_path, ignore_scanner_hash=True)

    res = json.loads((out_dir / "skill-usage-30d.json").read_text())
    assert res["total_structured_skill_selections"] == 1

    # Event on exclusive boundary must raise ValueError
    invalid_events = [
        {"event_id": "e_end", "timestamp": END_UTC, "kind": "skill_selection", "selected_name": "4layer"},
    ]
    bad_manifest = build_audit_fixture(tmp_path / "sub_invalid", events=invalid_events)
    with pytest.raises(ValueError, match="outside bound window"):
        audit(bad_manifest, tmp_path / "out2", repo_root=tmp_path / "sub_invalid", ignore_scanner_hash=True)

    # Tampered inventory hash fails closed
    corrupt_inv = build_audit_fixture(tmp_path / "sub_corrupt", events=valid_events, corrupt_inventory=True)
    with pytest.raises(ValueError, match="frozen input hash mismatch"):
        audit(corrupt_inv, tmp_path / "out3", repo_root=tmp_path / "sub_corrupt", ignore_scanner_hash=True)


def test_deterministic_replay(tmp_path: Path) -> None:
    """Replaying audit on the same fixture produces identical file outputs."""
    events = [
        {"event_id": "e1", "timestamp": "2026-08-05T00:00:00Z", "kind": "skill_selection", "selected_name": "browserclaw"},
        {"event_id": "e2", "timestamp": "2026-08-06T00:00:00Z", "kind": "command_candidate", "prompt_source": "typed", "origin_kind": "human", "leading_slash": "repro"},
    ]
    manifest = build_audit_fixture(tmp_path, events=events)
    out1 = tmp_path / "run1"
    out2 = tmp_path / "run2"
    audit(manifest, out1, repo_root=tmp_path, ignore_scanner_hash=True)
    audit(manifest, out2, repo_root=tmp_path, ignore_scanner_hash=True)

    for fname in ["strict-claude-command-usage-30d.json", "skill-usage-30d.json", "active-commands-30d.csv", "active-skills-30d.csv", "all-observed-skill-names-30d.csv"]:
        assert (out1 / fname).read_bytes() == (out2 / fname).read_bytes()


def test_codex_and_multi_runtime_provenance(tmp_path: Path) -> None:
    """Validate that Codex and multi-runtime events are correctly attributed."""
    events = [
        {"event_id": "codex_1", "timestamp": "2026-08-10T12:00:00Z", "kind": "command_candidate", "runtime": "codex", "prompt_source": "typed", "origin_kind": "human", "leading_slash": "f"},
        {"event_id": "codex_2", "timestamp": "2026-08-11T12:00:00Z", "kind": "command_candidate", "runtime": "codex", "prompt_source": "typed", "origin_kind": "human", "embedded_slash_tokens": ["callpath"]},
    ]
    manifest = build_audit_fixture(tmp_path, events=events)
    out_dir = tmp_path / "out"
    audit(manifest, out_dir, repo_root=tmp_path, ignore_scanner_hash=True)

    cmds_res = json.loads((out_dir / "strict-claude-command-usage-30d.json").read_text())
    cmds_map = {r["command"]: r for r in cmds_res["commands"]}
    assert cmds_map["f"]["canonical_direct_events"] == 1
    assert cmds_map["f"]["positive_evidence"] is True
    assert cmds_map["extended-library:callpath"]["canonical_direct_events"] == 1
    assert cmds_map["extended-library:callpath"]["positive_evidence"] is True
