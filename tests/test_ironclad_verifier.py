from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / ".claude" / "skills" / "ironclad" / "scripts" / "verify_pr_claims.py"


def load_helper():
    spec = importlib.util.spec_from_file_location("ironclad_verify_pr_claims", HELPER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {HELPER}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


verifier = load_helper()


def page(nodes: list[dict], has_next: bool, cursor: str | None) -> tuple[int, str, str]:
    return (
        0,
        json.dumps(
            {
                "data": {
                    "repository": {
                        "pullRequest": {
                            "reviewThreads": {
                                "nodes": nodes,
                                "pageInfo": {
                                    "hasNextPage": has_next,
                                    "endCursor": cursor,
                                },
                            }
                        }
                    }
                }
            }
        ),
        "",
    )


class ReviewThreadPaginationTests(unittest.TestCase):
    def test_counts_unresolved_thread_on_second_page(self) -> None:
        first = page([{"isResolved": True}] * 100, True, "cursor-1")
        second = page([{"isResolved": False}], False, None)
        calls = []

        def fake_gh(args, timeout=verifier.GH_TIMEOUT):
            calls.append(args)
            return [first, second][len(calls) - 1]

        with patch.object(verifier, "gh_call", side_effect=fake_gh):
            self.assertEqual(verifier.get_unresolved_review_threads(12, "owner/repo"), (1, 101))
        self.assertIn("-F", calls[1])
        self.assertIn("cursor=cursor-1", calls[1])

    def test_complete_all_resolved_pages_return_zero(self) -> None:
        response = page([{"isResolved": True}] * 100, False, None)
        with patch.object(verifier, "gh_call", return_value=response):
            self.assertEqual(verifier.get_unresolved_review_threads(12, "owner/repo"), (0, 100))

    def test_later_page_failure_is_unverifiable(self) -> None:
        first = page([{"isResolved": True}] * 100, True, "cursor-1")

        def fake_gh(args, timeout=verifier.GH_TIMEOUT):
            if "cursor=cursor-1" in args:
                return 1, "", "later page failed"
            return first

        with patch.object(verifier, "gh_call", side_effect=fake_gh):
            verdicts = verifier.verify_review_claims(12, "owner/repo", "Review threads: all resolved")
        self.assertEqual(verdicts[0].verdict, "UNVERIFIABLE")

    def test_repeated_cursor_is_unverifiable(self) -> None:
        first = page([{"isResolved": True}] * 100, True, "cursor-1")
        repeated = page([{"isResolved": True}], True, "cursor-1")

        def fake_gh(args, timeout=verifier.GH_TIMEOUT):
            if "cursor=cursor-1" in args:
                return repeated
            return first

        with patch.object(verifier, "gh_call", side_effect=fake_gh):
            verdicts = verifier.verify_review_claims(12, "owner/repo", "Review threads: all resolved")
        self.assertEqual(verdicts[0].verdict, "UNVERIFIABLE")

    def test_malformed_later_page_is_unverifiable(self) -> None:
        first = page([{"isResolved": True}] * 100, True, "cursor-1")
        malformed = (
            0,
            json.dumps(
                {
                    "data": {
                        "repository": {
                            "pullRequest": {
                                "reviewThreads": {
                                    "nodes": [{"isResolved": True}],
                                    "pageInfo": {"hasNextPage": True},
                                }
                            }
                        }
                    }
                }
            ),
            "",
        )

        def fake_gh(args, timeout=verifier.GH_TIMEOUT):
            if "cursor=cursor-1" in args:
                return malformed
            return first

        with patch.object(verifier, "gh_call", side_effect=fake_gh):
            verdicts = verifier.verify_review_claims(12, "owner/repo", "Review threads: all resolved")
        self.assertEqual(verdicts[0].verdict, "UNVERIFIABLE")


if __name__ == "__main__":
    unittest.main()
