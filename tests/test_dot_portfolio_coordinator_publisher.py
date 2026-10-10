import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / ".claude" / "skills" / "dot-portfolio-coordinator"
import sys
sys.path.insert(0, str(SKILL_DIR / "scripts"))

from modules.registry import SourceRegistry
from modules.publisher import RoadmapPublisher, PublisherError, PublicationHoldError


class TestDotPortfolioCoordinatorPublisher(unittest.TestCase):
    def setUp(self):
        self.sources_json_path = SKILL_DIR / "references" / "sources.json"
        self.registry = SourceRegistry.from_file(str(self.sources_json_path))
        self.publisher = RoadmapPublisher(self.registry)

        self.sample_snapshot = {
            "snapshot_id": "snap-001",
            "sources": {
                "roadmap-main": {
                    "source_id": "roadmap-main",
                    "version": "v1",
                    "items": [
                        {
                            "id": "bd-1",
                            "title": "Roadmap Goal A",
                            "status": "in_progress",
                            "priority": 1,
                            "owner": "alice",
                            "blocker": "none",
                            "next_action": "Finish spec",
                            "notes": "Secret internal design notes",
                            "principal_id": "admin-99"
                        }
                    ]
                }
            }
        }

    def test_render_work_md_audience_filtered(self):
        work_md = self.publisher.render_work_md(self.sample_snapshot)
        self.assertIn("# Portfolio Dashboard", work_md)
        self.assertIn("Roadmap Goal A", work_md)
        self.assertIn("alice", work_md)
        # Audience policy: notes and principal_id are internal, must NOT appear in public WORK.md
        self.assertNotIn("Secret internal design notes", work_md)
        self.assertNotIn("admin-99", work_md)

    def test_public_id_obeys_destination_policy(self):
        for destinations in (["internal"], ["model"], None, ["public"]):
            with self.subTest(destinations=destinations):
                policy = self.registry.sources["roadmap-main"]["audience_policy"]
                if destinations is None:
                    policy.pop("id", None)
                else:
                    policy["id"] = destinations
                rendered = self.publisher.render_work_md(self.sample_snapshot)
                if destinations == ["public"]:
                    self.assertIn("| bd-1 |", rendered)
                else:
                    self.assertNotIn("bd-1", rendered)
                    self.assertIn("| - |", rendered)

    def test_render_coverage_json(self):
        metrics = {
            "registered_count": 3,
            "attempted_count": 3,
            "fresh_count": 2,
            "stale_count": 1,
            "unavailable_count": 0
        }
        gaps = ["example-org/unregistered-secret-repo"]
        coverage = self.publisher.render_coverage_json(metrics, gaps)
        self.assertEqual(coverage["registered_sources"], 3)
        self.assertEqual(coverage["fresh_sources"], 2)
        self.assertEqual(coverage["coverage_gaps"], ["example-org/unregistered-secret-repo"])
        self.assertIn("generated_at", coverage)

    def test_publish_no_op_detection(self):
        mock_git = MagicMock()
        mock_git.read_file.side_effect = lambda f: "# Portfolio Dashboard\n\nContent unchanged" if f.endswith("WORK.md") else '{"coverage": 1}'
        mock_git.current_branch.return_value = "coordinator/portfolio-snapshot"

        res = self.publisher.publish_snapshot(
            repo_dir="/fake/repo",
            work_md_content="# Portfolio Dashboard\n\nContent unchanged",
            coverage_json_data={"coverage": 1},
            git_runner=mock_git
        )
        self.assertEqual(res["status"], "no_op")
        self.assertFalse(mock_git.commit.called)
        self.assertFalse(mock_git.push.called)

    def test_publish_closed_unmerged_hold(self):
        mock_git = MagicMock()
        mock_git.get_pr_state.return_value = {"state": "closed", "merged": False}

        with self.assertRaises(PublicationHoldError) as ctx:
            self.publisher.publish_snapshot(
                repo_dir="/fake/repo",
                work_md_content="New Content",
                coverage_json_data={"fresh": 1},
                git_runner=mock_git
            )
        self.assertIn("hold", str(ctx.exception).lower())

    def test_publish_creates_branch_and_verifies_readback(self):
        mock_git = MagicMock()
        mock_git.get_pr_state.return_value = {"state": "open", "merged": False, "pr_url": "https://github.com/org/repo/pull/10"}
        mock_git.read_file.return_value = "old"
        mock_git.commit.return_value = "sha-pushed-123"
        # Remote readback matches newly pushed content
        mock_git.read_remote_file.side_effect = lambda sha, f: "New Content" if f.endswith("WORK.md") else '{"fresh": 1}'

        res = self.publisher.publish_snapshot(
            repo_dir="/fake/repo",
            work_md_content="New Content",
            coverage_json_data={"fresh": 1},
            git_runner=mock_git
        )
        self.assertEqual(res["status"], "published")
        self.assertEqual(res["pushed_sha"], "sha-pushed-123")
        self.assertTrue(mock_git.push.called)
        # Verify no force push and not on main
        push_args = mock_git.push.call_args[0]
        self.assertNotIn("--force", push_args)
        self.assertNotIn("main", push_args)


if __name__ == "__main__":
    unittest.main()
