from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
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


class VerifierClaimTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.repo = Path(cls.temp.name)
        (cls.repo / "tests").mkdir()
        (cls.repo / "tests/test_demo.py").write_text(
            "def test_one():\n    pass\n\ndef helper():\n    pass\n\ndef test_two():\n    pass\n"
        )
        (cls.repo / "report.md").write_text("Fixture artifact\n")
        (cls.repo / "tests/test_failing.py").write_text(
            "def test_broken():\n    assert False\n"
        )
        env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
        for args in [
            ["init", "-q"],
            ["add", "tests/test_demo.py", "tests/test_failing.py", "report.md"],
            ["-c", "user.name=Test", "-c", "user.email=test@example.invalid",
             "-c", "commit.gpgsign=false", "commit", "-qm", "fixture"],
            ["remote", "add", "origin", "https://github.com/example/fixture.git"],
        ]:
            subprocess.run(
                ["git", "-c", "core.hooksPath=" + os.devnull, *args],
                cwd=cls.repo, env=env, capture_output=True, text=True,
                check=True, timeout=15,
            )
        cls.sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=cls.repo, text=True, timeout=15
        ).strip()

    def setUp(self) -> None:
        self.repo_patch = patch.object(verifier, "_repo_dir", self.repo)
        self.repo_patch.start()
        self.addCleanup(self.repo_patch.stop)

    def test_static_declarations_do_not_prove_collected_test_counts(self) -> None:
        self.assertEqual(verifier.static_test_count(self.sha, "tests/test_demo.py"), 2)
        for count in [1, 2, 3]:
            with self.subTest(count=count):
                result = verifier.verify_test_counts(
                    self.sha, f"tests/test_demo.py ({count} tests)"
                )
                self.assertEqual([v.verdict for v in result], ["UNVERIFIABLE"])
        result = verifier.verify_test_counts(self.sha, "tests/test_missing.py (2 tests)")
        self.assertEqual([v.verdict for v in result], ["UNVERIFIABLE"])

    def test_ci_rollup_does_not_count_skipped_neutral_or_pending_as_success(self) -> None:
        rollup = [{"conclusion": "SUCCESS"}, {"state": "SUCCESS"},
                  {"conclusion": "SKIPPED"}, {"conclusion": "NEUTRAL"},
                  {"conclusion": ""}, {"conclusion": "FAILURE"}]
        response = (0, json.dumps({"statusCheckRollup": rollup}), "")
        with patch.object(verifier, "gh_call", return_value=response):
            passed = verifier.verify_ci_claims(1, "CI: 2/6 checks")
            inflated = verifier.verify_ci_claims(1, "CI: 6/6 checks")
        self.assertEqual([v.verdict for v in passed], ["PASS"])
        self.assertEqual([v.verdict for v in inflated], ["FAIL"])

    def test_static_count_cannot_prove_a_runtime_passing_claim(self) -> None:
        failed = subprocess.run(
            [sys.executable, "-c",
             "import runpy; runpy.run_path('tests/test_failing.py')['test_broken']()"],
            cwd=self.repo, capture_output=True, text=True, timeout=15,
        )
        self.assertNotEqual(failed.returncode, 0)
        for claim in ["1 tests passing", "1 passed", "1/1 tests"]:
            with self.subTest(claim=claim):
                result = verifier.verify_test_counts(
                    self.sha, "tests/test_failing.py " + claim
                )
                self.assertEqual([v.verdict for v in result], ["UNVERIFIABLE"])

    def test_blob_sha_cannot_be_verified_as_a_commit(self) -> None:
        blob = subprocess.check_output(
            ["git", "rev-parse", self.sha + ":report.md"],
            cwd=self.repo, text=True, timeout=15,
        ).strip()
        result = verifier.verify_sha_claims("Tested at " + blob)
        self.assertEqual([v.verdict for v in result], ["FAIL"])

    def test_ci_errors_and_malformed_json_are_unverifiable(self) -> None:
        for response in [(1, "", "authentication required"), (0, "{broken", "")]:
            with self.subTest(response=response):
                with patch.object(verifier, "gh_call", return_value=response):
                    result = verifier.verify_ci_claims(1, "CI: 1/1 checks")
                self.assertEqual([v.verdict for v in result], ["UNVERIFIABLE"])

    def test_sha_and_path_claims_resolve_against_real_git_objects(self) -> None:
        result = verifier.verify_sha_claims("Tested at " + self.sha)
        self.assertEqual([v.verdict for v in result], ["PASS"])
        self.assertTrue(verifier.path_exists_at(self.sha, "report.md"))
        self.assertFalse(verifier.path_exists_at(self.sha, "missing.md"))
        with patch.object(verifier, "ensure_commit_local", return_value=False):
            result = verifier.verify_sha_claims("Tested at " + "f" * 40)
        self.assertEqual([v.verdict for v in result], ["FAIL"])

    def test_path_verdicts_reject_missing_and_nonreproducible_paths(self) -> None:
        with patch.object(verifier, "extract_path_claims", return_value=[
            ("report.md", "present"), ("missing.md", "missing"),
            ("/tmp/evidence.png", "external"),
        ]):
            result = verifier.verify_path_claims(self.sha, "")
        self.assertEqual([v.verdict for v in result], [
            "PASS", "FAIL", "FAIL (NON-REPRODUCIBLE)"
        ])

    def test_old_evidence_is_not_accepted_as_current_sha_proof(self) -> None:
        artifact = self.repo / "capture.png"
        artifact.write_bytes(b"fixture")
        os.utime(artifact, (1, 1))
        result = verifier.verify_sha_claims(f"Tested at {self.sha}: {artifact}")
        self.assertTrue(any(v.verdict == "FAIL" for v in result))
        self.assertEqual(verifier.summarize(result), 1)

    def test_repository_slug_is_derived_from_real_remote(self) -> None:
        self.assertEqual(verifier.derive_repo_slug_from_git(), "example/fixture")

    def test_missing_binary_and_timeout_return_failure_status(self) -> None:
        code, _, _ = verifier.run([str(self.repo / "missing-tool")])
        self.assertEqual(code, 127)
        code, _, error = verifier.run(
            [sys.executable, "-c", "import time; time.sleep(1)"], timeout=0.01
        )
        self.assertEqual((code, error), (124, "TIMEOUT"))


if __name__ == "__main__":
    unittest.main()
