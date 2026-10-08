"""Scope attribution and evidence strength regression cases."""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.audit_command_skill_usage import audit, digest
from tests.test_command_skill_usage_audit import build_audit_fixture


class ScopedSkillUsageTest(unittest.TestCase):
    def test_alias_selection_preserves_name_evidence_without_inventing_scope(self):
        for scoped in (False, True):
            with self.subTest(scoped=scoped), TemporaryDirectory() as directory:
                root = Path(directory)
                path = root / "SKILL.md"
                path.write_text("# Skill")
                skill = {"skill": "accept-adapt-reject", "path": str(path)}
                if scoped:
                    skill["skill_id"] = "home:accept-adapt-reject/SKILL.md"
                manifest = build_audit_fixture(
                    root,
                    skills=[skill],
                    events=[
                        {
                            "kind": "skill_selection",
                            "event_id": "alias",
                            "timestamp": "2026-08-10T12:00:00Z",
                            "selected_name": "aar",
                        }
                    ],
                )
                audit(manifest, root / "out")
                payload = json.loads((root / "out/skill-usage-30d.json").read_text())
                row = payload["skills"][0]
                self.assertEqual(row["explicit_skill_selections"], 0 if scoped else 1)
                self.assertEqual(row["name_only_selection_events"], 1 if scoped else 0)
                self.assertEqual(payload["events"][0]["selected_name"], "aar")

    def test_same_name_read_is_not_credited_to_both_scopes(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            skills = []
            for scope in ("home", "repo"):
                path = root / scope / "SKILL.md"
                path.parent.mkdir()
                path.write_text("# Same name, different scope\n")
                skills.append(
                    {
                        "skill": "gcp-deployments",
                        "skill_id": scope + ":gcp/SKILL.md",
                        "scope": scope,
                        "path": str(path),
                        "content_sha256": digest(path.read_bytes()),
                    }
                )
            events = [
                {
                    "kind": "skill_read",
                    "event_id": "read-1",
                    "runtime": "codex",
                    "timestamp": "2026-08-10T12:00:00Z",
                    "selected_path": skills[1]["path"],
                },
                {
                    "kind": "skill_selection",
                    "event_id": "select-1",
                    "runtime": "claude",
                    "timestamp": "2026-08-10T12:00:01Z",
                    "selected_name": "gcp-deployments",
                },
            ]
            manifest = build_audit_fixture(root, events=events, skills=skills)
            audit(manifest, root / "out")
            rows = json.loads((root / "out/skill-usage-30d.json").read_text())["skills"]
            rows = {row["scope"]: row for row in rows}
            self.assertEqual(rows["repo"]["file_read_attempts"], 1)
            self.assertEqual(rows["home"]["file_read_attempts"], 0)
            self.assertEqual(rows["repo"]["explicit_skill_selections"], 0)
            self.assertEqual(rows["home"]["name_only_selection_events"], 1)
            self.assertFalse(rows["repo"]["positive_evidence"])
            self.assertFalse(rows["home"]["archive_eligible_from_usage_alone"])

    def test_live_content_drift_fails_closed(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "SKILL.md"
            path.write_text("original")
            manifest = build_audit_fixture(
                root,
                events=[],
                skills=[
                    {
                        "skill": "gcp",
                        "path": str(path),
                        "content_sha256": digest(path.read_bytes()),
                    }
                ],
            )
            path.write_text("changed after capture")
            with self.assertRaisesRegex(ValueError, "inventory content drift"):
                audit(manifest, root / "out")

    def test_absence_is_unknown_and_excluded_sessions_do_not_count(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = build_audit_fixture(
                root,
                events=[
                    {
                        "kind": "skill_selection",
                        "event_id": "self",
                        "session_id": "audit-session",
                        "timestamp": "2026-08-10T12:00:00Z",
                        "selected_name": "4layer",
                    }
                ],
                manifest_overrides={"excluded_session_ids": ["audit-session"]},
            )
            audit(manifest, root / "out")
            rows = json.loads((root / "out/skill-usage-30d.json").read_text())["skills"]
            row = next(row for row in rows if row["skill"] == "4layer")
            self.assertEqual(row["explicit_skill_selections"], 0)
            self.assertEqual(row["usage_status"], "no_observed_use_coverage_unknown")

    def test_ambiguous_symlink_target_is_not_double_counted(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "canonical.md"
            target.write_text("# Shared source")
            skills = []
            for scope in ("claude", "codex"):
                path = root / scope / "SKILL.md"
                path.parent.mkdir()
                path.symlink_to(target)
                skills.append(
                    {
                        "skill": "same",
                        "skill_id": scope + ":same",
                        "scope": scope,
                        "path": str(path),
                        "resolved_target": str(target.resolve()),
                        "content_sha256": digest(target.read_bytes()),
                    }
                )
            events = [
                {
                    "kind": "skill_read",
                    "event_id": "r",
                    "timestamp": "2026-08-10T12:00:00Z",
                    "selected_path": str(target),
                    "runtime": "codex",
                }
            ]
            manifest = build_audit_fixture(root, events=events, skills=skills)
            audit(manifest, root / "out")
            payload = json.loads((root / "out/skill-usage-30d.json").read_text())
            self.assertEqual(payload["total_file_read_attempts"], 1)
            self.assertEqual(payload["scope_attributed_read_attempts"], 0)
            self.assertIsNone(payload["events"][0]["attributed_skill_id"])

    def test_scanner_dependency_hash_is_verified(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = build_audit_fixture(
                root,
                events=[],
                manifest_overrides={
                    "scanner_source_sha256": {
                        "scripts/scoped_skill_usage.py": "not-the-source-hash"
                    }
                },
            )
            with self.assertRaisesRegex(ValueError, "scanner source hash"):
                audit(manifest, root / "out")

    def test_capture_source_hash_is_verified(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = build_audit_fixture(
                root,
                events=[],
                manifest_overrides={
                    "capture_source_sha256": {
                        "scripts/skill_read_telemetry.py": "not-the-source-hash"
                    }
                },
            )
            with self.assertRaisesRegex(ValueError, "capture source hash"):
                audit(manifest, root / "out")

    def test_capture_source_hash_path_must_stay_in_source_root(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = build_audit_fixture(
                root,
                events=[],
                manifest_overrides={
                    "capture_source_sha256": {
                        "../../outside.py": "not-the-source-hash"
                    }
                },
            )
            with self.assertRaisesRegex(ValueError, "capture source hash path"):
                audit(manifest, root / "out")

    def test_capture_source_hash_is_ignored_only_with_explicit_flag(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = build_audit_fixture(
                root,
                events=[],
                manifest_overrides={
                    "capture_source_sha256": {
                        "scripts/skill_read_telemetry.py": "not-the-source-hash"
                    }
                },
            )
            audit(manifest, root / "out", ignore_scanner_hash=True)
            payload = json.loads((root / "out/skill-usage-30d.json").read_text())
            self.assertEqual(payload["provenance_status"], "unverified_explicit_override")
            self.assertFalse(payload["provenance_verified"])

    def test_legacy_missing_source_hashes_are_marked_unverified(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = build_audit_fixture(root, events=[])
            audit(manifest, root / "out")
            payload = json.loads((root / "out/skill-usage-30d.json").read_text())
            self.assertEqual(
                payload["provenance_status"],
                "unverified_legacy_missing_source_hashes",
            )
            self.assertFalse(payload["provenance_verified"])

    def test_standard_manifest_requires_complete_source_hash_maps(self):
        for overrides in (
            {"schema": "claude_usage_audit_manifest.v3"},
            {
                "schema": "claude_usage_audit_manifest.v3",
                "scanner_source_sha256": {
                    "scripts/audit_command_skill_usage.py": digest(
                        (Path(__file__).parents[1] / "scripts/audit_command_skill_usage.py").read_bytes()
                    )
                },
            },
        ):
            with self.subTest(overrides=overrides), TemporaryDirectory() as directory:
                root = Path(directory)
                manifest = build_audit_fixture(
                    root, events=[], manifest_overrides=overrides
                )
                with self.assertRaisesRegex(ValueError, "complete source hash"):
                    audit(manifest, root / "out")


if __name__ == "__main__":
    unittest.main()
