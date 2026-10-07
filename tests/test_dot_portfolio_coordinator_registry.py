import json
import os
import unittest
from pathlib import Path

# Adjust path to import from scripts
REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / ".claude" / "skills" / "dot-portfolio-coordinator"
MODULES_DIR = SKILL_DIR / "scripts" / "modules"

import sys
sys.path.insert(0, str(SKILL_DIR / "scripts"))

from modules.registry import SourceRegistry, RegistryValidationError


class TestDotPortfolioCoordinatorRegistry(unittest.TestCase):
    def setUp(self):
        self.sources_json_path = SKILL_DIR / "references" / "sources.json"
        self.schema_json_path = SKILL_DIR / "references" / "portfolio-contract.schema.json"

    def test_schema_and_sources_file_exist_and_parse(self):
        self.assertTrue(self.sources_json_path.exists())
        self.assertTrue(self.schema_json_path.exists())
        with open(self.sources_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data.get("version"), "1.0.0")
        self.assertIn("sources", data)
        self.assertIn("budget_policy", data)
        self.assertIn("endpoint_policy", data)

    def test_load_valid_registry(self):
        reg = SourceRegistry.from_file(str(self.sources_json_path))
        self.assertIsNotNone(reg.get_source("roadmap-main"))
        src = reg.get_source("roadmap-main")
        self.assertEqual(src["namespace"], "roadmap")
        self.assertEqual(src["authority"], "authoritative_control")

    def test_reject_duplicate_namespaces(self):
        bad_data = {
            "version": "1.0.0",
            "sources": [
                {
                    "id": "s1",
                    "namespace": "dup-ns",
                    "type": "beads_store",
                    "github_host": "github.com",
                    "repository": "org/repo1",
                    "canonical_tracker": "beads",
                    "authority": "read_only",
                    "audience_policy": {"title": ["public"]}
                },
                {
                    "id": "s2",
                    "namespace": "dup-ns",
                    "type": "beads_store",
                    "github_host": "github.com",
                    "repository": "org/repo2",
                    "canonical_tracker": "beads",
                    "authority": "read_only",
                    "audience_policy": {"title": ["public"]}
                }
            ],
            "budget_policy": {
                "per_cycle_tokens": 1000,
                "per_cycle_cost_usd": 0.01,
                "daily_tokens": 10000,
                "daily_cost_usd": 0.10,
                "allowed_models": ["m1"]
            },
            "endpoint_policy": {"provider": "p", "allowed_endpoints": ["https://api.example.com"]},
            "caller_allowlist": ["caller1"]
        }
        with self.assertRaises(RegistryValidationError) as ctx:
            SourceRegistry(bad_data)
        self.assertIn("duplicate namespace", str(ctx.exception).lower())

    def test_composite_task_key_structure(self):
        reg = SourceRegistry.from_file(str(self.sources_json_path))
        key = reg.make_task_composite_key("github.com", "example-org/roadmap", "roadmap", "bd-123")
        self.assertEqual(key, ("github.com", "example-org/roadmap", "roadmap", "bd-123"))

    def test_audience_filtering_model_vs_public(self):
        reg = SourceRegistry.from_file(str(self.sources_json_path))
        item = {
            "title": "Secret Feature",
            "notes": "Internal debug notes",
            "principal_id": "usr_9999",
            "status": "in_progress"
        }
        # In sources.json:
        # title: ["model", "public"]
        # status: ["model", "public"]
        # notes: ["model", "internal"]
        # principal_id: ["internal"]

        # Filter for public: notes and principal_id must be excluded
        public_view = reg.filter_by_audience("roadmap-main", item, "public")
        self.assertIn("title", public_view)
        self.assertIn("status", public_view)
        self.assertNotIn("notes", public_view)
        self.assertNotIn("principal_id", public_view)

        # Filter for model: principal_id must be excluded, notes included
        model_view = reg.filter_by_audience("roadmap-main", item, "model")
        self.assertIn("title", model_view)
        self.assertIn("status", model_view)
        self.assertIn("notes", model_view)
        self.assertNotIn("principal_id", model_view)

    def test_org_gap_detection(self):
        reg = SourceRegistry.from_file(str(self.sources_json_path))
        discovered = [
            "example-org/roadmap",
            "example-org/skills",
            "example-org/web-app",
            "example-org/unregistered-secret-project",
            "example-org/legacy-repo"
        ]
        gaps = reg.detect_org_gaps("example-org", discovered)
        self.assertIn("example-org/unregistered-secret-project", gaps)
        self.assertIn("example-org/legacy-repo", gaps)
        self.assertNotIn("example-org/roadmap", gaps)
        self.assertEqual(len(gaps), 2)


if __name__ == "__main__":
    unittest.main()
