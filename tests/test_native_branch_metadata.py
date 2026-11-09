"""Branch and repository metadata extraction from native histories."""

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scripts.native_usage_collector import collect_native_history


class NativeBranchMetadataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "history"
        self.root.mkdir()
        self.cutoff = datetime(2026, 11, 10, tzinfo=timezone.utc)

    def tearDown(self):
        self.temp.cleanup()

    def collect(self, rows, repository_map=None):
        path = self.root / "history.jsonl"
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        return collect_native_history(
            [self.root], cutoff=self.cutoff, days=14, repository_map=repository_map
        )

    def test_codex_flat_session_metadata_reaches_human_and_usage(self):
        data = self.collect([
            {"type": "session_meta", "payload": {
                "id": "thread", "cwd": "/private/worktree",
                "git_branch": "feature/one", "commit_hash": "abc123",
                "repository_url": "https://github.com/Owner/Repo.git",
            }},
            {"type": "response_item", "timestamp": "2026-10-28T09:00:01Z",
             "payload": {"id": "prompt", "turn_id": "t", "role": "user", "content": "private"}},
            {"type": "token_usage_record", "timestamp": "2026-10-28T09:00:02Z",
             "response_id": "r", "payload": {"turn_id": "t", "usage": {
                 "input_tokens": 10, "cached_input_tokens": 1, "output_tokens": 2,
             }}},
        ])
        for record in (data["human_records"][0], data["usage_records"][0]):
            self.assertEqual(record["repository"], "owner/repo")
            self.assertEqual(record["git_branch"], "feature/one")
            self.assertEqual(record["commit_hash"], "abc123")
            self.assertEqual(record["branch_source"], "recorded_repository_url")
        exported = json.dumps(data["export_records"])
        self.assertNotIn("/private/worktree", exported)
        self.assertNotIn("private", exported)

    def test_codex_nested_meta_and_sibling_fields_and_uuid_precedence(self):
        data = self.collect([
            {"type": "session_meta", "payload": {"id": "thread", "meta": {
                "cwd": "/private/wt",
            }, "git_branch": "feature/two", "commit_hash": "def456",
                "repository_url": "https://github.com/acme/game"}},
            {"type": "response_item", "timestamp": "2026-10-28T09:00:01Z",
             "uuid": "uuid-human", "promptId": "legacy-prompt", "payload": {
                 "turn_id": "t", "role": "user", "content": "secret"}},
        ])
        human = data["human_records"][0]
        self.assertEqual(human["event_id"], "uuid-human")
        self.assertEqual(human["event_id_aliases"], ["legacy-prompt"])
        self.assertEqual(human["repository"], "acme/game")
        self.assertEqual(human["git_branch"], "feature/two")
        self.assertEqual(human["commit_hash"], "def456")
        self.assertEqual(human["branch_basis"], "recorded_repository_url")

    def test_claude_record_branch_switch_and_exact_cached_repo_mapping(self):
        data = self.collect([
            {"type": "user", "timestamp": "2026-10-28T09:00:01Z", "uuid": "u1",
             "gitBranch": "branch/a", "cwd": "/private/cwd",
             "message": {"role": "user", "content": "prompt"}},
            {"type": "user", "timestamp": "2026-10-28T09:00:02Z", "uuid": "u2",
             "gitBranch": "branch/b", "cwd": "/private/cwd",
             "message": {"role": "user", "content": "prompt"}},
        ], repository_map={"/private/cwd": "Acme/Game"})
        one, two = data["human_records"]
        self.assertEqual(one["git_branch"], "branch/a")
        self.assertEqual(two["git_branch"], "branch/b")
        self.assertEqual(one["repository"], "acme/game")
        self.assertEqual(one["branch_source"], "cached_repository_map")
        self.assertEqual(one["branch_basis"], "exact_recorded_cwd_lookup")
        self.assertNotIn("/private/cwd", json.dumps(data["export_records"]))

    def test_missing_or_unvalidated_repository_remains_unknown(self):
        data = self.collect([
            {"type": "user", "timestamp": "2026-10-28T09:00:01Z", "uuid": "u1",
             "gitBranch": "topic", "cwd": "/private/worktree",
             "repository_url": "https://example.com/owner/repo",
             "message": {"role": "user", "content": "prompt"}},
        ])
        human = data["human_records"][0]
        self.assertEqual(human["git_branch"], "topic")
        self.assertNotIn("repository", human)
        self.assertEqual(human["branch_source"], "recorded_git_branch")
        self.assertEqual(human["branch_basis"], "exact_recorded_record")
        self.assertNotIn("cwd", json.dumps(data["export_records"]))
