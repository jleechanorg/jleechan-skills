import json
import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / ".claude" / "skills" / "dot-portfolio-coordinator"
import sys
sys.path.insert(0, str(SKILL_DIR / "scripts"))

from modules.registry import SourceRegistry
from modules.collector import PortfolioCollector, CollectorError


class TestDotPortfolioCoordinatorCollector(unittest.TestCase):
    def setUp(self):
        self.sources_json_path = SKILL_DIR / "references" / "sources.json"
        self.registry = SourceRegistry.from_file(str(self.sources_json_path))
        self.collector = PortfolioCollector(self.registry)

    def test_github_paginated_collection_including_draft_prs_and_checks(self):
        pages = [
            {
                "items": [
                    {"id": 101, "title": "Issue 1", "state": "open", "type": "issue"},
                    {"id": 102, "title": "PR 1", "state": "open", "type": "pull_request", "is_draft": True, "head_sha": "abc1", "checks": "pending"}
                ],
                "has_next": True,
                "next_page": 2,
                "etag": "etag-p1"
            },
            {
                "items": [
                    {"id": 103, "title": "PR 2", "state": "open", "type": "pull_request", "is_draft": False, "head_sha": "abc2", "checks": "success"}
                ],
                "has_next": False,
                "next_page": None,
                "etag": "etag-p2"
            }
        ]

        def fake_fetch(source, page, etag=None):
            return pages[page - 1]

        res = self.collector.collect_source_snapshot("web-app", fetch_fn=fake_fetch)
        self.assertEqual(res["status"], "fresh")
        self.assertEqual(len(res["items"]), 3)
        self.assertTrue(res["checkpoint_committed"])
        self.assertEqual(res["cursor"]["last_completed_page"], 2)
        # Check draft PR preserved with checks and head_sha
        draft_pr = next(i for i in res["items"] if i.get("id") == 102)
        self.assertTrue(draft_pr.get("is_draft"))
        self.assertEqual(draft_pr.get("head_sha"), "abc1")
        self.assertEqual(draft_pr.get("checks"), "pending")

    def test_github_partial_page_failure_preserves_stale_and_resumes(self):
        prior_snapshot = {
            "source_id": "web-app",
            "version": "prior-v1",
            "items": [{"id": 99, "title": "Old PR", "state": "open"}],
            "cursor": {"last_completed_page": 1}
        }

        def failing_fetch(source, page, etag=None):
            if page == 1:
                return {
                    "items": [{"id": 101, "title": "Issue 1", "state": "open"}],
                    "has_next": True,
                    "next_page": 2,
                    "etag": "etag-p1"
                }
            raise CollectorError("Network timeout on page 2")

        res = self.collector.collect_source_snapshot(
            "web-app",
            prior_snapshot=prior_snapshot,
            fetch_fn=failing_fetch
        )
        # Partial collection should not commit checkpoint
        self.assertFalse(res["checkpoint_committed"])
        self.assertIn(res["status"], ["partial", "stale"])
        # Should preserve prior items or partial items, never empty
        self.assertGreater(len(res["items"]), 0)
        # Cursor should record last completed page (page 1)
        self.assertEqual(res["cursor"]["last_completed_page"], 1)

    def test_conditional_304_reuses_recorded_version(self):
        prior_snapshot = {
            "source_id": "web-app",
            "version": "v-304",
            "etag": "prior-etag",
            "items": [{"id": 101, "title": "Cached Issue", "state": "open"}]
        }

        def fetch_304(source, page, etag=None):
            if etag == "prior-etag":
                return {"status_code": 304}
            return {"items": [], "has_next": False}

        res = self.collector.collect_source_snapshot(
            "web-app",
            prior_snapshot=prior_snapshot,
            fetch_fn=fetch_304
        )
        self.assertEqual(res["status"], "fresh")
        self.assertTrue(res["checkpoint_committed"])
        self.assertEqual(len(res["items"]), 1)
        self.assertEqual(res["items"][0]["title"], "Cached Issue")

    def test_beads_all_status_collection(self):
        mock_beads_output = [
            {"id": "bd-1", "title": "Task 1", "status": "open", "priority": 1, "owner": "alice"},
            {"id": "bd-2", "title": "Task 2", "status": "in_progress", "priority": 2, "owner": "bob"},
            {"id": "bd-3", "title": "Task 3", "status": "deferred", "priority": 3, "owner": ""},
            {"id": "bd-4", "title": "Task 4", "status": "closed", "priority": 0, "owner": "alice"}
        ]

        def fake_beads_fetch(source):
            return mock_beads_output

        res = self.collector.collect_source_snapshot("core-skills", fetch_fn=fake_beads_fetch)
        self.assertEqual(res["status"], "fresh")
        self.assertEqual(len(res["items"]), 4)
        self.assertTrue(res["checkpoint_committed"])
        # Verify composite keys assigned
        for item in res["items"]:
            self.assertIn("task_composite_key", item)
            self.assertEqual(item["task_composite_key"][2], "skills")

    def test_aggregate_metrics_reporting(self):
        prior = {}
        def mock_fetch(source, page=1, etag=None):
            if source["id"] == "roadmap-main":
                return [{"id": "bd-r1", "title": "Goal 1", "status": "open", "priority": 0}]
            elif source["id"] == "core-skills":
                return [{"id": "bd-s1", "title": "Skill 1", "status": "open", "priority": 1}]
            elif source["id"] == "web-app":
                return {"items": [{"id": 1, "title": "Web 1", "state": "open"}], "has_next": False}
            raise CollectorError("Unknown source")

        res = self.collector.collect_all(prior_snapshots=prior, fetch_fn=mock_fetch)
        self.assertEqual(res["registered_count"], 3)
        self.assertEqual(res["attempted_count"], 3)
        self.assertEqual(res["fresh_count"], 3)
        self.assertEqual(res["stale_count"], 0)
        self.assertEqual(res["unavailable_count"], 0)


    def test_beads_parses_json_envelope_and_strips_notes_and_descriptions(self):
        mock_envelope = {
            "issues": [
                {
                    "id": "bd-10",
                    "title": "Clean Task",
                    "status": "open",
                    "notes": "SECRET_RAW_NOTES_MUST_NOT_PERSIST",
                    "description": "SECRET_DESCRIPTION_MUST_NOT_PERSIST",
                    "owner": "alice"
                }
            ],
            "total": 1,
            "limit": 0,
            "offset": 0,
            "has_more": False
        }

        def fake_envelope_fetch(source):
            return mock_envelope

        res = self.collector.collect_source_snapshot("core-skills", fetch_fn=fake_envelope_fetch)
        self.assertEqual(res["status"], "fresh")
        self.assertEqual(len(res["items"]), 1)
        item = res["items"][0]
        self.assertEqual(item["id"], "bd-10")
        self.assertEqual(item["title"], "Clean Task")
        self.assertNotIn("notes", item)
        self.assertNotIn("description", item)

    def test_beads_blocks_ambient_fallback_when_host_binding_missing(self):
        # A beads source without host_binding must NOT fall back to ambient br
        source_without_db = {
            "id": "orphan-beads",
            "namespace": "orphan",
            "type": "beads_store",
            "github_host": "github.com",
            "repository": "org/repo",
            "canonical_tracker": "beads",
            "authority": "read_only",
            "audience_policy": {"title": ["public"]}
        }
        with patch.object(self.registry, "get_source", return_value=source_without_db):
            with self.assertRaises(CollectorError) as ctx:
                self.collector._default_beads_fetch(source_without_db)
            self.assertIn("host_binding", str(ctx.exception).lower())

    def test_partial_github_preserves_union_of_old_unseen_records(self):
        prior_snapshot = {
            "source_id": "web-app",
            "version": "prior-v1",
            "items": [
                {"id": 101, "title": "Old Item 101", "task_composite_key": ["github.com", "example-org/web-app", "webapp", "101"]},
                {"id": 102, "title": "Old Item 102", "task_composite_key": ["github.com", "example-org/web-app", "webapp", "102"]}
            ],
            "cursor": {"last_completed_page": 2, "completed": True}
        }

        # Page 1 returns item 101 (updated) and item 103 (new), then page 2 fails
        def failing_page2(source, page, etag=None):
            if page == 1:
                return {
                    "items": [
                        {"id": 101, "title": "Updated Item 101"},
                        {"id": 103, "title": "New Item 103"}
                    ],
                    "has_next": True,
                    "next_page": 2
                }
            raise CollectorError("Network connection reset on page 2")

        res = self.collector.collect_source_snapshot(
            "web-app",
            prior_snapshot=prior_snapshot,
            fetch_fn=failing_page2
        )
        self.assertEqual(res["status"], "partial")
        self.assertFalse(res["checkpoint_committed"])
        # Should preserve UNION of old unseen (102), updated (101), and new (103)
        item_ids = {i["id"] for i in res["items"]}
        self.assertIn(101, item_ids)
        self.assertIn(102, item_ids)  # preserved from prior unseen!
        self.assertIn(103, item_ids)  # collected from partial page 1!
        self.assertEqual(len(item_ids), 3)

    def test_duplicate_items_deduped_across_pages(self):
        pages = [
            {
                "items": [
                    {"id": 201, "title": "Issue 201"}
                ],
                "has_next": True,
                "next_page": 2
            },
            {
                "items": [
                    {"id": 201, "title": "Issue 201 Duplicate"},
                    {"id": 202, "title": "Issue 202"}
                ],
                "has_next": False,
                "next_page": None
            }
        ]

        def fake_fetch(source, page, etag=None):
            return pages[page - 1]

        res = self.collector.collect_source_snapshot("web-app", fetch_fn=fake_fetch)
        self.assertEqual(res["status"], "fresh")
        item_ids = [i["id"] for i in res["items"]]
        self.assertEqual(len(item_ids), 2)
        self.assertEqual(item_ids, [201, 202])


if __name__ == "__main__":
    unittest.main()
