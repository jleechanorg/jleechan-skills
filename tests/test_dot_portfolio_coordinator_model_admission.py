import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / ".claude" / "skills" / "dot-portfolio-coordinator"
import sys
sys.path.insert(0, str(SKILL_DIR / "scripts"))

from modules.registry import SourceRegistry
from modules.model_admission import ModelAdmissionChecker
from modules.proposal_validator import ProposalValidator, ProposalValidationError


class TestDotPortfolioCoordinatorModelAdmission(unittest.TestCase):
    def setUp(self):
        self.sources_json_path = SKILL_DIR / "references" / "sources.json"
        self.registry = SourceRegistry.from_file(str(self.sources_json_path))
        self.admission = ModelAdmissionChecker(self.registry)
        self.validator = ProposalValidator(self.registry)

        self.sample_snapshot = {
            "snapshot_id": "snap-20261007-001",
            "sources": {
                "roadmap-main": {
                    "source_id": "roadmap-main",
                    "version": "sha-road-1",
                    "items": [
                        {
                            "id": "bd-ctrl-1",
                            "title": "Roadmap Control Record",
                            "status": "open",
                            "task_composite_key": ["github.com", "example-org/roadmap", "roadmap", "bd-ctrl-1"],
                            "notes": "control notes",
                            "principal_id": "admin-1"
                        }
                    ]
                },
                "core-skills": {
                    "source_id": "core-skills",
                    "version": "sha-skill-1",
                    "items": [
                        {
                            "id": "bd-s1",
                            "title": "Skills Task 1",
                            "status": "open",
                            "task_composite_key": ["github.com", "example-org/skills", "skills", "bd-s1"],
                            "notes": "some notes",
                            "principal_id": "usr-42"
                        }
                    ]
                }
            }
        }

    def test_admission_blocked_when_unisolated_or_arbitrary_egress(self):
        # Case 1: unisolated host mounts
        env_with_host_mounts = {
            "sandbox_enforced": True,
            "host_mounts": ["/Users/jleechan", "/etc"],
            "network_egress_allowlist_enforced": True,
            "allowed_endpoints": ["https://generativelanguage.googleapis.com/v1beta/models"],
            "tool_inventory": ["read_only_snapshot"],
            "write_credentials_excluded": True
        }
        res = self.admission.admit_model_transport(env_with_host_mounts)
        self.assertFalse(res["admitted"])
        self.assertEqual(res["reason"], "capability_blocked")

        # Case 2: arbitrary network egress (no endpoint allowlist enforcement)
        env_with_open_network = {
            "sandbox_enforced": True,
            "host_mounts": [],
            "network_egress_allowlist_enforced": False,
            "allowed_endpoints": ["*"],
            "tool_inventory": ["read_only_snapshot"],
            "write_credentials_excluded": True
        }
        res = self.admission.admit_model_transport(env_with_open_network)
        self.assertFalse(res["admitted"])
        self.assertEqual(res["reason"], "capability_blocked")

        # Case 3: write credentials present
        env_with_creds = {
            "sandbox_enforced": True,
            "host_mounts": [],
            "network_egress_allowlist_enforced": True,
            "allowed_endpoints": ["https://generativelanguage.googleapis.com/v1beta/models"],
            "tool_inventory": ["read_only_snapshot"],
            "write_credentials_excluded": False
        }
        res = self.admission.admit_model_transport(env_with_creds)
        self.assertFalse(res["admitted"])
        self.assertEqual(res["reason"], "capability_blocked")

    def test_admission_always_capability_blocked_absent_genuine_isolation_adapter(self):
        # Caller JSON booleans MUST NOT establish actual isolation
        env_isolated = {
            "sandbox_enforced": True,
            "host_mounts": [],
            "network_egress_allowlist_enforced": True,
            "allowed_endpoints": ["https://generativelanguage.googleapis.com/v1beta/models"],
            "tool_inventory": ["read_only_snapshot"],
            "write_credentials_excluded": True
        }
        res = self.admission.admit_model_transport(env_isolated)
        self.assertFalse(res["admitted"])
        self.assertEqual(res["reason"], "capability_blocked")
        self.assertIn("isolation adapter", res["details"].lower())

    def test_minimized_snapshot_filters_prohibited_fields(self):
        minimized = self.admission.prepare_minimized_snapshot(self.sample_snapshot)
        road_items = minimized["sources"]["roadmap-main"]["items"]
        self.assertEqual(len(road_items), 1)
        self.assertIn("title", road_items[0])
        self.assertIn("notes", road_items[0])
        # principal_id only has ['internal'] in sources.json, so it must be stripped from 'model'
        self.assertNotIn("principal_id", road_items[0])

    def test_minimized_snapshot_preserves_safe_coverage_freshness_and_error_code(
        self,
    ):
        snapshot = {
            "snapshot_id": "snap-partial",
            "collected_at": 900,
            "coverage": {
                "registered_count": 3,
                "fresh_count": 1,
                "stale_count": 1,
                "unavailable_count": 1,
                "private_notes": "must not pass through",
            },
            "private_error": "raw failure details",
            "sources": {
                "core-skills": {
                    "source_id": "core-skills",
                    "status": "partial",
                    "version": "sha-skill-2",
                    "cursor": {"last_completed_page": 2, "completed": False},
                    "checkpoint_committed": False,
                    "collected_at": 700,
                    "validated_at": 750,
                    "attempted_at": 800,
                    "error_code": "incomplete_envelope",
                    "error": "private raw exception",
                    "items": self.sample_snapshot["sources"]["core-skills"][
                        "items"
                    ],
                }
            },
        }

        minimized = self.admission.prepare_minimized_snapshot(snapshot)

        self.assertEqual(minimized["collected_at"], 900)
        self.assertEqual(
            minimized["coverage"],
            {
                "registered_count": 3,
                "fresh_count": 1,
                "stale_count": 1,
                "unavailable_count": 1,
            },
        )
        source = minimized["sources"]["core-skills"]
        self.assertEqual(source["status"], "partial")
        self.assertEqual(
            source["cursor"], {"last_completed_page": 2, "completed": False}
        )
        self.assertFalse(source["checkpoint_committed"])
        self.assertEqual(source["collected_at"], 700)
        self.assertEqual(source["validated_at"], 750)
        self.assertEqual(source["attempted_at"], 800)
        self.assertEqual(source["error_code"], "incomplete_envelope")
        self.assertNotIn("private_error", minimized)
        self.assertNotIn("private_notes", minimized["coverage"])
        self.assertNotIn("error", source)
        self.assertNotIn("principal_id", source["items"][0])

        snapshot["sources"]["core-skills"]["error_code"] = "private raw exception"
        unsafe_code_snapshot = self.admission.prepare_minimized_snapshot(snapshot)
        self.assertNotIn(
            "error_code", unsafe_code_snapshot["sources"]["core-skills"]
        )

    def test_proposal_validation_valid_and_deterministic_action_id(self):
        proposal = {
            "schema_version": 1,
            "snapshot_id": "snap-20261007-001",
            "items": [
                {
                    "task_key": {
                        "github_host": "github.com",
                        "repository": "example-org/roadmap",
                        "source_namespace": "roadmap",
                        "bead_id": "bd-ctrl-1"
                    },
                    "source_version": "sha-road-1",
                    "citations": ["example-org/roadmap#bd-ctrl-1@sha-road-1"],
                    "owner": "admin",
                    "priority": 0,
                    "status": "open",
                    "blocker": "none",
                    "next_action": "track work",
                    "uncertainty": "none"
                },
                {
                    "task_key": {
                        "github_host": "github.com",
                        "repository": "example-org/skills",
                        "source_namespace": "skills",
                        "bead_id": "bd-s1"
                    },
                    "source_version": "sha-skill-1",
                    "citations": ["example-org/skills#bd-s1@sha-skill-1"],
                    "owner": "alice",
                    "priority": 1,
                    "status": "open",
                    "blocker": "none",
                    "next_action": "review test results",
                    "uncertainty": "none"
                }
            ],
            "mutations": [
                {
                    "target_control_record_id": "bd-ctrl-1",
                    "action_type": "tracking_observation",
                    "append_note": "[2026-10-07T12:00:00Z] Observed bd-s1 open."
                }
            ]
        }
        res1 = self.validator.validate_proposal(proposal, self.sample_snapshot)
        self.assertTrue(res1["valid"])
        self.assertTrue(res1["action_id"].startswith("act_"))

        # Re-running validation yields identical action_id (idempotence)
        res2 = self.validator.validate_proposal(proposal, self.sample_snapshot)
        self.assertEqual(res1["action_id"], res2["action_id"])

    def test_prose_containing_curl_or_rm_not_rejected_by_keyword_classifier(self):
        # Semantic keyword classifier was removed: arbitrary prose in append_note is allowed
        proposal = {
            "schema_version": 1,
            "snapshot_id": "snap-20261007-001",
            "items": [
                {
                    "task_key": {
                        "github_host": "github.com",
                        "repository": "example-org/roadmap",
                        "source_namespace": "roadmap",
                        "bead_id": "bd-ctrl-1"
                    },
                    "source_version": "sha-road-1",
                    "citations": ["example-org/roadmap#bd-ctrl-1@sha-road-1"],
                    "owner": "admin",
                    "priority": 0,
                    "status": "open",
                    "next_action": "none"
                },
                {
                    "task_key": {
                        "github_host": "github.com",
                        "repository": "example-org/skills",
                        "source_namespace": "skills",
                        "bead_id": "bd-s1"
                    },
                    "source_version": "sha-skill-1",
                    "citations": ["example-org/skills#bd-s1@sha-skill-1"],
                    "owner": "alice",
                    "priority": 1,
                    "status": "open",
                    "next_action": "review curl documentation"
                }
            ],
            "mutations": [
                {
                    "target_control_record_id": "bd-ctrl-1",
                    "action_type": "tracking_observation",
                    "append_note": "Investigating curl timeout on endpoint; do not rm files."
                }
            ]
        }
        res = self.validator.validate_proposal(proposal, self.sample_snapshot)
        self.assertTrue(res["valid"])

    def test_proposal_validation_rejects_unknown_structural_executable_fields(self):
        # Reject unknown executable fields structurally
        proposal = {
            "schema_version": 1,
            "snapshot_id": "snap-20261007-001",
            "items": [],
            "mutations": [
                {
                    "target_control_record_id": "bd-ctrl-1",
                    "action_type": "tracking_observation",
                    "append_note": "Valid note",
                    "execute_command": "rm -rf /"  # unknown executable field
                }
            ]
        }
        with self.assertRaises(ProposalValidationError) as ctx:
            self.validator.validate_proposal(proposal, self.sample_snapshot)
        self.assertIn("unknown", str(ctx.exception).lower())

    def test_proposal_validation_enforces_full_item_coverage(self):
        # Proposal omits bd-s1 from items coverage
        proposal = {
            "schema_version": 1,
            "snapshot_id": "snap-20261007-001",
            "items": [
                {
                    "task_key": {
                        "github_host": "github.com",
                        "repository": "example-org/roadmap",
                        "source_namespace": "roadmap",
                        "bead_id": "bd-ctrl-1"
                    },
                    "source_version": "sha-road-1",
                    "citations": ["example-org/roadmap#bd-ctrl-1@sha-road-1"],
                    "owner": "admin",
                    "priority": 0,
                    "status": "open",
                    "next_action": "track work"
                }
            ],
            "mutations": []
        }
        with self.assertRaises(ProposalValidationError) as ctx:
            self.validator.validate_proposal(proposal, self.sample_snapshot)
        self.assertIn("coverage", str(ctx.exception).lower())

    def test_proposal_validation_rejects_invented_task_key(self):
        proposal = {
            "schema_version": 1,
            "snapshot_id": "snap-20261007-001",
            "items": [
                {
                    "task_key": {
                        "github_host": "github.com",
                        "repository": "example-org/skills",
                        "source_namespace": "skills",
                        "bead_id": "bd-invented-999"
                    },
                    "source_version": "sha-skill-1",
                    "citations": ["example-org/skills#bd-invented-999"],
                    "owner": "alice",
                    "priority": 1,
                    "status": "open",
                    "blocker": "none",
                    "next_action": "do something"
                }
            ],
            "mutations": []
        }
        with self.assertRaises(ProposalValidationError) as ctx:
            self.validator.validate_proposal(proposal, self.sample_snapshot)
        self.assertIn("not found in snapshot", str(ctx.exception))

    def test_proposal_validation_rejects_domain_store_mutation(self):
        # Attempting to mutate a task in core-skills (domain store is read-only!)
        proposal = {
            "schema_version": 1,
            "snapshot_id": "snap-20261007-001",
            "items": [],
            "mutations": [
                {
                    "target_control_record_id": "bd-s1",  # bd-s1 is in core-skills, not roadmap-main
                    "action_type": "tracking_observation",
                    "append_note": "illegal mutation"
                }
            ]
        }
        with self.assertRaises(ProposalValidationError) as ctx:
            self.validator.validate_proposal(proposal, self.sample_snapshot)
        self.assertIn("domain store", str(ctx.exception).lower())


if __name__ == "__main__":
    unittest.main()
