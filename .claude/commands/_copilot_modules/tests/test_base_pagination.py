#!/usr/bin/env python3
"""
Unit tests for base.py pagination handling.

Tests the fix for GitHub API pagination where run_gh_command() now properly
handles paginated responses by adding --jq '.[]' and parsing JSONL output.
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from base import CopilotCommandBase


class TestCopilotCommand(CopilotCommandBase):
    """Concrete test implementation of CopilotCommandBase"""

    def execute(self):
        """Implement abstract execute method for testing"""
        return {"success": True}


class TestBasePagination(unittest.TestCase):
    """Test pagination handling in CopilotCommandBase.run_gh_command()"""

    def setUp(self):
        """Set up test fixtures"""
        # Create a test instance with mocked initialization
        with patch.object(TestCopilotCommand, "__init__", lambda x, **kwargs: None):
            self.base = TestCopilotCommand()
        # Keep the fixture contract aligned with CopilotCommandBase.__init__.
        self.base.fetch_errors = []

    def test_non_paginated_command_returns_dict(self):
        """Test that non-paginated commands return dict as before"""
        mock_result = MagicMock()
        mock_result.stdout = json.dumps({"key": "value"})
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = self.base.run_gh_command(["gh", "api", "user"])

            # Should return dict for non-paginated
            self.assertIsInstance(result, dict)
            self.assertEqual(result, {"key": "value"})

            # Should NOT add --jq for non-paginated
            called_cmd = mock_run.call_args[0][0]
            self.assertNotIn("--jq", called_cmd)

    def test_paginated_command_adds_jq_flag(self):
        """Test that --paginate triggers automatic --jq '.[]' addition"""
        # Simulate JSONL output (one JSON per line)
        jsonl_output = '{"id": 1, "body": "Comment 1"}\n{"id": 2, "body": "Comment 2"}\n'

        mock_result = MagicMock()
        mock_result.stdout = jsonl_output
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            _ = self.base.run_gh_command([
                "gh", "api", "repos/owner/repo/issues/comments", "--paginate"
            ])

            # Verify --jq was added
            called_cmd = mock_run.call_args[0][0]
            self.assertIn("--paginate", called_cmd)
            self.assertIn("--jq", called_cmd)
            self.assertIn(".[]", called_cmd)

            # Verify --jq is placed after --paginate
            paginate_idx = called_cmd.index("--paginate")
            jq_idx = called_cmd.index("--jq")
            self.assertGreater(jq_idx, paginate_idx)

    def test_paginated_command_returns_list(self):
        """Test that paginated commands return list of items"""
        # Simulate JSONL output from paginated API call
        jsonl_output = '{"id": 1, "body": "Comment 1"}\n{"id": 2, "body": "Comment 2"}\n{"id": 3, "body": "Comment 3"}\n'

        mock_result = MagicMock()
        mock_result.stdout = jsonl_output
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            result = self.base.run_gh_command([
                "gh", "api", "repos/owner/repo/issues/comments", "--paginate"
            ])

            # Should return list for paginated
            self.assertIsInstance(result, list)
            self.assertEqual(len(result), 3)

            # Verify items are parsed correctly
            self.assertEqual(result[0]["id"], 1)
            self.assertEqual(result[1]["id"], 2)
            self.assertEqual(result[2]["id"], 3)

    def test_paginated_command_handles_empty_response(self):
        """Test that empty paginated response returns empty list"""
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            result = self.base.run_gh_command([
                "gh", "api", "repos/owner/repo/issues/comments", "--paginate"
            ])

            # Should return empty list for empty paginated response
            self.assertIsInstance(result, list)
            self.assertEqual(len(result), 0)

    def test_paginated_command_records_invalid_json_lines(self):
        """Test that invalid JSON lines are recorded for fail-closed producers"""
        # Mix valid and invalid JSON lines
        jsonl_output = (
            '{"id": 1, "body": "Valid 1"}\n'
            'INVALID JSON LINE\n'
            '{"id": 2, "body": "Valid 2"}\n'
            'Another invalid line\n'
            '{"id": 3, "body": "Valid 3"}\n'
        )

        mock_result = MagicMock()
        mock_result.stdout = jsonl_output
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            result = self.base.run_gh_command([
                "gh", "api", "repos/owner/repo/issues/comments", "--paginate"
            ])

            # Should only parse valid JSON lines
            self.assertIsInstance(result, list)
            self.assertEqual(len(result), 3)
            self.assertEqual(result[0]["id"], 1)
            self.assertEqual(result[2]["id"], 3)
            self.assertEqual(len(self.base.fetch_errors), 2)

    def test_paginated_with_existing_jq_not_duplicated(self):
        """Test that existing --jq flag is not duplicated"""
        mock_result = MagicMock()
        mock_result.stdout = '{"id": 1}\n{"id": 2}\n'
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            # Command already has --jq
            _ = self.base.run_gh_command([
                "gh", "api", "repos/owner/repo/issues/comments",
                "--paginate", "--jq", ".[]"
            ])

            # Verify --jq is not duplicated
            called_cmd = mock_run.call_args[0][0]
            jq_count = called_cmd.count("--jq")
            self.assertEqual(jq_count, 1, "Should not duplicate --jq flag")

    def test_subprocess_error_returns_empty_list_for_paginated(self):
        """Test that subprocess errors return empty list for paginated calls"""
        with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "gh")):
            result = self.base.run_gh_command([
                "gh", "api", "repos/owner/repo/issues/comments", "--paginate"
            ])

            # Should return empty list on error for paginated
            self.assertIsInstance(result, list)
            self.assertEqual(len(result), 0)

    def test_subprocess_error_returns_empty_dict_for_non_paginated(self):
        """Test that subprocess errors return empty dict for non-paginated calls"""
        with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "gh")):
            result = self.base.run_gh_command([
                "gh", "api", "user"
            ])

            # Should return empty dict on error for non-paginated
            self.assertIsInstance(result, dict)
            self.assertEqual(len(result), 0)

    def test_real_world_pr_comments_pagination(self):
        """Test pagination with real-world PR comments structure"""
        # Simulate 150 comments across 2 pages (GitHub default is 100 per page)
        page1_comments = [{"id": i, "body": f"Comment {i}"} for i in range(1, 101)]
        page2_comments = [{"id": i, "body": f"Comment {i}"} for i in range(101, 151)]

        # Simulate JSONL output that gh CLI produces with --paginate --jq '.[]'
        jsonl_output = "\n".join(
            json.dumps(c) for c in page1_comments + page2_comments
        ) + "\n"

        mock_result = MagicMock()
        mock_result.stdout = jsonl_output
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            result = self.base.run_gh_command([
                "gh", "api", "repos/owner/repo/pulls/123/comments", "--paginate"
            ])

            # Should get all 150 comments from both pages
            self.assertIsInstance(result, list)
            self.assertEqual(len(result), 150)
            self.assertEqual(result[0]["id"], 1)
            self.assertEqual(result[99]["id"], 100)
            self.assertEqual(result[100]["id"], 101)
            self.assertEqual(result[149]["id"], 150)

    def test_paginated_with_user_jq_returns_list(self):
        """Test that user-provided --jq with pagination works correctly even if it produces JSONL"""
        # Simulate JSONL output which happens if user passes --jq '.[]'
        jsonl_output = '{"id": 1}\n{"id": 2}\n'
        mock_result = MagicMock()
        mock_result.stdout = jsonl_output
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            # Command has user-provided --jq
            result = self.base.run_gh_command([
                "gh", "api", "comments",
                "--paginate", "--jq", ".[]"
            ])

            # Should successfully parse JSONL into list
            self.assertIsInstance(result, list)
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0]["id"], 1)
            self.assertEqual(result[1]["id"], 2)


if __name__ == "__main__":
    unittest.main()
