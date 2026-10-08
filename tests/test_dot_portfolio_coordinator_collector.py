import json
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / ".claude" / "skills" / "dot-portfolio-coordinator"
sys.path.insert(0, str(SKILL_DIR / "scripts"))

from modules.registry import SourceRegistry
from modules.collector import PortfolioCollector, CollectorError


class TestDotPortfolioCoordinatorCollector(unittest.TestCase):
    def setUp(self):
        self.sources_json_path = SKILL_DIR / "references" / "sources.json"
        self.registry = SourceRegistry.from_file(str(self.sources_json_path))
        # Snapshot tests model the private coordinator audience explicitly.
        for source in self.registry.sources.values():
            policy = source["audience_policy"]
            for field in ("title", "status", "owner", "priority", "head_sha", "checks", "is_draft"):
                policy[field] = sorted(set(policy.get(field, [])) | {"internal"})
        self.collector = PortfolioCollector(self.registry)

    def test_collection_audience_switch_refetches_and_preserves_destination_fields(self):
        policy = self.registry.sources["web-app"]["audience_policy"]
        policy.update({"title": ["model", "public"], "owner": ["internal"]})
        raw = {"id": 7, "title": "Authorized model fact", "owner": "private owner"}
        internal = self.collector.collect_source_snapshot(
            "web-app", fetch_fn=lambda *args, **kwargs: {"items": [raw], "etag": "internal-v1"})
        self.assertNotIn("title", internal["items"][0])
        self.assertEqual(internal["items"][0]["owner"], "private owner")
        seen_etags = []
        def fetch(source, page, etag=None):
            seen_etags.append(etag)
            return {"items": [raw], "etag": "model-v1"}
        model = PortfolioCollector(self.registry, audience="model")
        snapshot = model.collect_source_snapshot("web-app", prior_snapshot=internal, fetch_fn=fetch)
        self.assertEqual(seen_etags, [None])
        self.assertEqual(snapshot["items"][0]["title"], "Authorized model fact")
        self.assertNotIn("owner", snapshot["items"][0])
        wrong_304 = model.collect_source_snapshot(
            "web-app", prior_snapshot=internal,
            fetch_fn=lambda *args, **kwargs: {"status_code": 304})
        self.assertNotEqual(wrong_304["status"], "fresh")

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
            "collected_at": 123,
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
        self.assertEqual(res["collected_at"], 123)
        self.assertIn("validated_at", res)

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

    def test_native_beads_all_status_command_preserves_every_task(self):
        source = self.registry.get_source("core-skills")
        source["host_binding"] = "/tmp/portfolio-fixture/beads.db"
        tasks = [
            {"id": "fixture-" + status, "title": "Task " + status, "status": status}
            for status in ("open", "in_progress", "deferred", "closed")
        ]
        common = ["br", "--db", source["host_binding"],
                  "--no-auto-flush", "--no-auto-import"]
        calls = []

        def native_fixture(argv, **kwargs):
            calls.append((argv, kwargs))
            if "where" in argv:
                return 0, json.dumps({"database_path": source["host_binding"]}), ""
            # Compatibility fixture for br versions where --status is a literal
            # filter. An unconditional response would hide fresh-but-empty data.
            selected = tasks
            if "--status" in argv:
                status = argv[argv.index("--status") + 1]
                selected = [task for task in selected if task["status"] == status]
            elif "--all" not in argv:
                selected = [task for task in selected if task["status"] != "closed"]
            if "--deferred" not in argv:
                selected = [task for task in selected if task["status"] != "deferred"]
            limit = int(argv[argv.index("--limit") + 1]) if "--limit" in argv else 1
            if limit:
                selected = selected[:limit]
            return 0, json.dumps(selected), ""

        with patch("modules.collector.run_bounded_command", side_effect=native_fixture), \
                patch("modules.collector.time.monotonic", return_value=1000):
            result = self.collector.collect_source_snapshot("core-skills", deadline_mono=1023)

        self.assertEqual(result["status"], "fresh")
        self.assertTrue(result["checkpoint_committed"])
        self.assertTrue(result["cursor"]["completed"])
        self.assertEqual({task["id"]: task["status"] for task in result["items"]},
                         {task["id"]: task["status"] for task in tasks})
        for task in result["items"]:
            self.assertEqual(task["task_composite_key"], [
                source["github_host"], source["repository"], source["namespace"], task["id"],
            ])
        self.assertEqual(calls, [
            (common + ["where", "--json"], {"timeout_secs": 23}),
            (common + ["list", "--all", "--deferred", "--limit", "0", "--json"],
             {"timeout_secs": 23}),
        ])
        print("native fixture retained open/in_progress/deferred/closed; exact DB, flags, and timeout verified")

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

    def test_incomplete_beads_envelope_does_not_commit_and_preserves_sanitized_prior(self):
        source = self.registry.get_source("core-skills")
        source["audience_policy"] = {
            "title": [],
            "status": ["internal"],
            "owner": ["internal"],
            "principal_id": ["internal"],
            "notes": ["internal"],
        }
        prior_snapshot = {
            "source_id": "core-skills",
            "status": "fresh",
            "version": "prior",
            "collected_at": 42,
            "items": [
                {
                    "id": "bd-old",
                    "title": "Prior item",
                    "status": "open",
                    "owner": {"login": "alice", "token": "PRIVATE"},
                    "notes": "PRIVATE NOTES",
                    "principal_id": "PRIVATE PRINCIPAL",
                    "body": "PRIVATE BODY",
                }
            ],
        }
        response = {
            "issues": [
                {
                    "id": "bd-new",
                    "title": "Partial item",
                    "status": "open",
                    "owner": {"login": "bob", "token": "PRIVATE"},
                    "notes": "PRIVATE NOTES",
                    "principal_id": "PRIVATE PRINCIPAL",
                    "description": "PRIVATE DESCRIPTION",
                }
            ],
            "total": 2,
            "limit": 1,
            "offset": 0,
            "has_more": True,
        }

        result = self.collector.collect_source_snapshot(
            "core-skills",
            prior_snapshot=prior_snapshot,
            fetch_fn=lambda _source: response,
        )

        self.assertEqual(result["status"], "partial")
        self.assertFalse(result["checkpoint_committed"])
        self.assertEqual(result["error_code"], "incomplete_envelope")
        self.assertIsNone(result["version"])
        self.assertEqual(result["collected_at"], 42)
        self.assertIn("attempted_at", result)
        self.assertEqual({item["id"] for item in result["items"]}, {"bd-old", "bd-new"})
        self.assertNotIn("title", result["items"][0])
        self.assertNotIn("title", result["items"][1])
        serialized = json.dumps(result)
        for private_value in ("PRIVATE", "PRIVATE NOTES", "PRIVATE PRINCIPAL", "PRIVATE BODY", "PRIVATE DESCRIPTION", "token"):
            self.assertNotIn(private_value, serialized)
        self.assertEqual(result["items"][0]["owner"], "alice")

    def test_github_pagination_repeated_cursor_and_caller_deadline_are_bounded(self):
        calls = []

        def repeated_page(_source, page, etag=None):
            calls.append(page)
            return {"items": [{"id": page}], "has_next": True, "next_page": 1}

        result = self.collector.collect_source_snapshot(
            "web-app",
            fetch_fn=repeated_page,
            deadline_mono=time.monotonic() + 5,
        )
        self.assertEqual(result["status"], "partial")
        self.assertFalse(result["checkpoint_committed"])
        self.assertEqual(result["error_code"], "repeated_cursor")
        self.assertEqual(calls, [1])

        expired = self.collector.collect_source_snapshot(
            "web-app",
            fetch_fn=lambda *_args, **_kwargs: self.fail("fetch called after deadline"),
            deadline_mono=time.monotonic() - 1,
        )
        self.assertEqual(expired["error_code"], "deadline_exceeded")
        self.assertFalse(expired["checkpoint_committed"])

    def test_github_fetch_honors_configured_host_and_hydrates_pr_head_and_checks(self):
        source = self.registry.get_source("web-app")
        source["github_host"] = "github.example.test"
        calls = []
        responses = [
            json.dumps([{
                "id": 4,
                "number": 4,
                "title": "Pull request",
                "state": "open",
                "pull_request": {"url": "https://github.example.test/api/v3/repos/example-org/web-app/pulls/4"},
            }]),
            json.dumps({"head": {"sha": "abc123"}}),
            json.dumps({
                "total_count": 1,
                "check_runs": [{"status": "completed", "conclusion": "success"}],
            }),
        ]

        def fake_command(argv, **_kwargs):
            calls.append(argv)
            return 0, responses.pop(0), ""

        with patch("modules.collector.run_bounded_command", side_effect=fake_command):
            result = self.collector._default_gh_fetch(source)

        self.assertTrue(all(argv[0:3] == ["gh", "api", "--hostname"] for argv in calls))
        self.assertTrue(all(argv[3] == "github.example.test" for argv in calls))
        self.assertEqual(len(calls), 3)
        pr = result["items"][0]
        self.assertEqual(pr["head_sha"], "abc123")
        self.assertEqual(pr["checks"], "success")

    def test_github_command_error_does_not_persist_stderr(self):
        with patch(
            "modules.collector.run_bounded_command",
            return_value=(1, "", "SECRET GitHub stderr"),
        ):
            result = self.collector.collect_source_snapshot("web-app")

        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["error_code"], "github_fetch_failed")
        self.assertNotIn("SECRET", json.dumps(result))

    def test_github_page_limit_is_finite(self):
        calls = []

        def pages(_source, page, etag=None):
            calls.append(page)
            return {"items": [{"id": page}], "has_next": True, "next_page": page + 1}

        with patch("modules.collector.MAX_GITHUB_PAGES", 2):
            result = self.collector.collect_source_snapshot(
                "web-app", fetch_fn=pages, deadline_mono=time.monotonic() + 5
            )

        self.assertEqual(calls, [1, 2])
        self.assertEqual(result["error_code"], "page_limit")
        self.assertEqual(result["status"], "partial")
        self.assertFalse(result["checkpoint_committed"])

    def test_beads_resolves_and_reads_only_the_exact_configured_store(self):
        source = self.registry.get_source("core-skills")
        source["host_binding"] = "/tmp/portfolio-test/beads.db"
        calls = []

        def fake_command(argv, **_kwargs):
            calls.append(argv)
            if "where" in argv:
                return 0, json.dumps({"database_path": source["host_binding"]}), ""
            return 0, json.dumps([{"id": "bd-exact", "title": "Exact store"}]), ""

        with patch("modules.collector.run_bounded_command", side_effect=fake_command):
            result = self.collector.collect_source_snapshot("core-skills")

        self.assertEqual(result["status"], "fresh")
        self.assertEqual(len(calls), 2)
        self.assertIn("where", calls[0])
        self.assertIn("list", calls[1])
        self.assertIn("--no-auto-flush", calls[0])
        self.assertIn("--no-auto-import", calls[0])
        self.assertIn("--no-auto-flush", calls[1])
        self.assertIn("--no-auto-import", calls[1])
        self.assertIn(source["host_binding"], calls[1])

    def test_beads_command_error_does_not_persist_stderr(self):
        source = self.registry.get_source("core-skills")
        source["host_binding"] = "/tmp/portfolio-test/beads.db"
        with patch(
            "modules.collector.run_bounded_command",
            return_value=(1, "", "SECRET stderr content"),
        ):
            result = self.collector.collect_source_snapshot("core-skills")

        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["error_code"], "beads_where_failed")
        self.assertNotIn("SECRET", json.dumps(result))

    def test_beads_where_mismatch_stops_before_list(self):
        source = self.registry.get_source("core-skills")
        source["host_binding"] = "/tmp/portfolio-test/beads.db"
        calls = []

        def fake_command(argv, **_kwargs):
            calls.append(argv)
            return 0, json.dumps({"database_path": "/tmp/other/beads.db"}), ""

        with patch("modules.collector.run_bounded_command", side_effect=fake_command):
            result = self.collector.collect_source_snapshot("core-skills")

        self.assertEqual(result["error_code"], "beads_store_mismatch")
        self.assertFalse(result["checkpoint_committed"])
        self.assertEqual(len(calls), 1)
        self.assertIn("where", calls[0])

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
