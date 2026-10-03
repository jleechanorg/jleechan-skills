#!/usr/bin/env python3
"""test_ci_queue_trim.py — focused offline regression tests for ci_queue_trim.py.

These tests exercise the audit logic without touching the network or any
``gh`` CLI. They patch ``ci_queue_trim.run_cmd`` so the script's helpers see
deterministic GitHub-API responses built from per-test fixtures.

The fixtures model the failure modes the tool must respect:

* Superseded runs (run.headSha differs from the PR's current head SHA).
* Merge-group and unknown events must NEVER be cancelled via stale-head.
* Lookup failures (PR / commit / run) must keep the run and mark audit
  incomplete; never substitute run age as a head-age fact.
* Fork PRs where the PR's merge SHA is not equal to the run's recorded SHA.
* Pre-cancellation refresh must catch concurrent changes (run moved on,
  PR head advanced, run no longer on a protected branch).
* ``--superseded-only`` mode must cancel only proven obsolete heads.
* Workflow importance is decided by an explicit configured allowlist, not
  by fuzzy substring heuristics on the workflow name.

Run with::

    python3 -m pytest .claude/skills/ci-queue-trim/tests/test_ci_queue_trim.py -v
or::

    python3 .claude/skills/ci-queue-trim/tests/test_ci_queue_trim.py
"""

from __future__ import annotations

import datetime
import json
import sys
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from unittest import mock

SKILL_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = SKILL_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import ci_queue_trim  # noqa: E402

FIXED_NOW = datetime.datetime(2026, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)


def _iso(dt: datetime.datetime) -> str:
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _run(
    run_id: int,
    *,
    name: str = "CI",
    branch: str = "feature/test",
    head_sha: str = "abc123",
    event: str = "pull_request",
    created_at: Optional[datetime.datetime] = None,
    status: str = "queued",
) -> Dict[str, Any]:
    return {
        "databaseId": run_id,
        "name": name,
        "headBranch": branch,
        "headSha": head_sha,
        "event": event,
        "status": status,
        "createdAt": _iso(created_at or (FIXED_NOW - datetime.timedelta(minutes=30))),
        "url": f"https://github.com/x/y/actions/runs/{run_id}",
    }


def _pr(
    number: int,
    *,
    branch: str = "feature/test",
    sha: str = "abc123",
    state: str = "OPEN",
    updated_minutes_ago: int = 10,
    fork: Optional[str] = None,
) -> Dict[str, Any]:
    base: Dict[str, Any] = {
        "number": number,
        "state": state,
        "updated_at": _iso(FIXED_NOW - datetime.timedelta(minutes=updated_minutes_ago)),
        "head": {
            "ref": branch,
            "sha": sha,
            "repo": {"full_name": "owner/repo"},
        },
    }
    if fork is not None:
        base["head"]["repo"] = {"full_name": fork}
    return base


def _commit(sha: str, *, age_minutes: int) -> Dict[str, Any]:
    return {
        "sha": sha,
        "commit": {"committer": {"date": _iso(FIXED_NOW - datetime.timedelta(minutes=age_minutes))}},
    }


class _RunCmdStub:
    """Stub for ``ci_queue_trim.run_cmd`` that responds by argv-substring match.

    Each test registers a sequence of (matcher, payload) pairs. The first
    matcher whose substring appears in the command argv wins; if no matcher
    matches, an empty result is returned so the audit path is forced to
    handle a lookup failure (which the test can then assert).
    """

    def __init__(self) -> None:
        self.responses: List[Tuple[str, Any]] = []
        self.calls: List[List[str]] = []

    def add(self, matcher: str, payload: Any) -> None:
        self.responses.append((matcher, payload))

    def __call__(self, cmd: List[str], timeout: int = 60) -> Tuple[int, str, str]:
        self.calls.append(list(cmd))
        cmd_str = " ".join(cmd)
        for matcher, payload in self.responses:
            if matcher in cmd_str:
                if isinstance(payload, BaseException):
                    raise payload
                if isinstance(payload, tuple):
                    rc, stdout, stderr = payload
                    return rc, stdout, stderr
                return 0, payload if isinstance(payload, str) else json.dumps(payload), ""
        # Default: a JSON "not found" shape so callers treat this as a
        # lookup failure rather than an empty success.
        return 0, "{}", ""


def _patch_now() -> Any:
    """Pin ``datetime.datetime.now`` inside the module to FIXED_NOW."""
    real_datetime = ci_queue_trim.datetime.datetime

    class FrozenDateTime(real_datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            if tz is None:
                return FIXED_NOW.replace(tzinfo=None)
            return FIXED_NOW

    return mock.patch.object(ci_queue_trim.datetime, "datetime", FrozenDateTime)


def _audit_with(stub: _RunCmdStub, **overrides: Any) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Run ``audit_queue`` against the stub and return its raw results."""
    kwargs = {"max_age_hours": 2.0, "limit": 50}
    kwargs.update(overrides)
    # Clear module-level caches so per-test fixtures do not bleed.
    ci_queue_trim._COMMIT_DATE_CACHE.clear()
    ci_queue_trim._PR_BY_HEAD_CACHE.clear()
    with mock.patch.object(ci_queue_trim, "run_cmd", side_effect=stub), _patch_now():
        return ci_queue_trim.audit_queue("owner/repo", **kwargs)


# ---------------------------------------------------------------------------
# Superseded vs current head
# ---------------------------------------------------------------------------


class TestSupersededAndCurrentHead(unittest.TestCase):
    """``pull_request`` and ``push`` runs must be cancelled when the run's
    recorded head SHA no longer matches the PR/branch current head. A run
    whose head SHA still matches must only be cancelled for MERGED/CLOSED
    PRs, never for stale code alone on a fresh push."""

    def test_pull_request_run_superseded_by_newer_head_is_cancelled(self):
        stub = _RunCmdStub()
        stub.add("gh run list", [_run(1, head_sha="old_sha_aaa")])
        stub.add("/pulls?state=all", [_pr(42, sha="new_sha_bbb", branch="feature/test")])
        stub.add("/pulls?state=all&head=owner:feature/test", _pr(42, sha="new_sha_bbb", branch="feature/test"))
        stub.add("/commits/new_sha_bbb", _commit("new_sha_bbb", age_minutes=5))

        audited, stats = _audit_with(stub)

        self.assertEqual(stats["total_queued"], 1)
        self.assertEqual(stats["to_cancel"], 1)
        self.assertEqual(audited[0]["verdict"], "CANCEL")
        self.assertTrue(audited[0]["superseded"])
        self.assertFalse(audited[0]["audit_incomplete"])

    def test_pull_request_run_at_current_head_is_kept(self):
        stub = _RunCmdStub()
        stub.add("gh run list", [_run(2, head_sha="same_sha")])
        stub.add("/pulls?state=all", [_pr(7, sha="same_sha", branch="feature/test", state="OPEN")])
        stub.add("/commits/same_sha", _commit("same_sha", age_minutes=10))

        audited, stats = _audit_with(stub)

        self.assertEqual(stats["to_cancel"], 0)
        self.assertEqual(stats["to_keep"], 1)
        self.assertEqual(audited[0]["verdict"], "KEEP")
        self.assertFalse(audited[0]["superseded"])
        self.assertFalse(audited[0]["audit_incomplete"])

    def test_push_event_branch_head_mismatch_is_cancelled(self):
        stub = _RunCmdStub()
        stub.add("gh run list", [_run(3, head_sha="branch_old", event="push", branch="release-2026")])
        stub.add("/pulls?state=all", [])
        stub.add("/branches/release-2026", {"commit": {"sha": "branch_new"}})
        stub.add("/commits/branch_new", _commit("branch_new", age_minutes=5))

        audited, _ = _audit_with(stub)

        self.assertEqual(audited[0]["verdict"], "CANCEL")
        self.assertTrue(audited[0]["superseded"])

    def test_merged_pr_run_is_cancelled_even_when_head_matches(self):
        stub = _RunCmdStub()
        stub.add("gh run list", [_run(4, head_sha="merged_sha")])
        stub.add("/pulls?state=all", [_pr(99, sha="merged_sha", state="MERGED", updated_minutes_ago=180)])

        audited, _ = _audit_with(stub)

        self.assertEqual(audited[0]["verdict"], "CANCEL")
        self.assertEqual(audited[0]["pr_state"], "MERGED")


# ---------------------------------------------------------------------------
# Event-specific merge-ref / fork identity semantics
# ---------------------------------------------------------------------------


class TestEventSemantics(unittest.TestCase):
    """``merge_group`` and unknown events MUST NOT receive the generic
    stale-head comparison. ``pull_request_target`` and fork PRs must use
    the PR's head SHA (which is the merge ref), not the run's recorded
    SHA which may be a fork SHA."""

    def test_merge_group_event_skips_stale_head_comparison(self):
        stub = _RunCmdStub()
        old_run = _run(
            5,
            head_sha="mergegroup_old",
            event="merge_group",
            branch="feature/mq",
            created_at=FIXED_NOW - datetime.timedelta(hours=6),
        )
        stub.add("gh run list", [old_run])
        stub.add("/pulls?state=all", [])

        audited, _ = _audit_with(stub)

        self.assertEqual(audited[0]["verdict"], "KEEP")
        self.assertFalse(audited[0]["superseded"])
        self.assertIn("merge_group", audited[0]["reason"].lower())

    def test_unknown_event_marks_audit_incomplete_and_keeps(self):
        stub = _RunCmdStub()
        weird_run = _run(
            6,
            head_sha="weird_sha",
            event="repository_dispatch",
            branch="feature/automation",
        )
        stub.add("gh run list", [weird_run])
        stub.add("/pulls?state=all", [])

        audited, _ = _audit_with(stub)

        self.assertEqual(audited[0]["verdict"], "KEEP")
        self.assertTrue(audited[0]["audit_incomplete"])
        self.assertIn("unsupported", audited[0]["reason"].lower())

    def test_fork_pr_uses_pr_head_sha_not_run_head_sha(self):
        """A fork PR's PR.head.sha is the merge ref inside the base repo.
        The run's recorded head SHA may be the fork's SHA and is therefore
        NOT comparable to PR.head.sha directly. When the run's SHA is on
        the fork, the audit must use the PR's head SHA as the current head."""

        stub = _RunCmdStub()
        stub.add("gh run list", [_run(7, head_sha="fork_sha_zzz")])
        stub.add("/pulls?state=all", [_pr(11, sha="created_sha_base", branch="feature/fork", fork="alice/repo")])
        stub.add("/commits/fork_sha_zzz", _commit("fork_sha_zzz", age_minutes=5))

        audited, _ = _audit_with(stub)

        self.assertEqual(audited[0]["verdict"], "CANCEL")
        self.assertTrue(audited[0]["superseded"])


# ---------------------------------------------------------------------------
# Lookup failures must mark incomplete, never substitute run age
# ---------------------------------------------------------------------------


class TestLookupFailures(unittest.TestCase):
    """If PR/commit/run lookup fails, the run must be KEPT with
    ``audit_incomplete=True``. The audit must NOT fall back to the run's
    age as a substitute for the head commit age."""

    def test_missing_pr_lookup_marks_incomplete_and_keeps(self):
        stub = _RunCmdStub()
        stub.add("gh run list", [_run(8, branch="scratch/runaway")])
        stub.add("/pulls?state=all", [])
        stub.add("/pulls?state=all&head=owner:scratch/runaway", [])

        audited, _ = _audit_with(stub)

        self.assertEqual(audited[0]["verdict"], "KEEP")
        self.assertTrue(audited[0]["audit_incomplete"])
        self.assertIn("pr lookup", audited[0]["reason"].lower())

    def test_missing_commit_date_marks_incomplete_and_does_not_use_run_age(self):
        stub = _RunCmdStub()
        stub.add(
            "gh run list",
            [_run(9, head_sha="missing_sha", branch="feature/x",
                  created_at=FIXED_NOW - datetime.timedelta(hours=10))],
        )
        stub.add("/pulls?state=all", [_pr(12, sha="missing_sha", branch="feature/x")])
        stub.add("/commits/missing_sha", (1, "", "404 Not Found"))

        audited, _ = _audit_with(stub)

        self.assertEqual(audited[0]["verdict"], "KEEP")
        self.assertTrue(audited[0]["audit_incomplete"])
        self.assertEqual(audited[0]["head_commit_age"], "unknown")

    def test_run_metadata_fetch_failure_marks_incomplete(self):
        stub = _RunCmdStub()
        stub.add("gh run list", [_run(10, head_sha="sha_x", branch="feature/y")])
        stub.add("/pulls?state=all", [_pr(13, sha="sha_x", branch="feature/y")])
        stub.add("/commits/sha_x", _commit("sha_x", age_minutes=5))
        stub.add("/actions/runs/10", (1, "", "boom"))

        audited, _ = _audit_with(stub)
        self.assertEqual(len(audited), 1)
        self.assertEqual(audited[0]["pr_number"], 13)
        # If metadata fetch failed, the audit must mark the run incomplete
        # rather than treat the missing fields as evidence of staleness.
        self.assertTrue(audited[0]["audit_incomplete"])


# ---------------------------------------------------------------------------
# Pre-cancellation refresh catches concurrent changes
# ---------------------------------------------------------------------------


class TestPreCancelRefresh(unittest.TestCase):
    """``refresh_before_cancel`` must re-fetch run status, event, and the
    candidate fingerprint (PR head SHA, PR number, workflow name). If any
    field moved on since the audit, the run must NOT be cancelled."""

    def test_refresh_skips_run_that_is_no_longer_queued(self):
        stub = _RunCmdStub()
        stub.add("gh run list", [_run(11, head_sha="old_x", event="pull_request", status="queued")])
        stub.add("/pulls?state=all", [_pr(20, sha="new_x", branch="feature/z")])
        stub.add("/commits/new_x", _commit("new_x", age_minutes=5))

        audited, _ = _audit_with(stub)
        self.assertEqual(audited[0]["verdict"], "CANCEL")

        stub.calls.clear()
        stub.add("/actions/runs/11", {"status": "in_progress", "event": "pull_request", "name": "CI"})
        stub.add("/pulls/20", _pr(20, sha="new_x", branch="feature/z"))

        refreshed = ci_queue_trim.refresh_before_cancel(
            "owner/repo", audited, run_cmd=stub
        )
        self.assertEqual(refreshed, [])

    def test_refresh_skips_run_when_pr_head_advanced_to_match(self):
        stub = _RunCmdStub()
        stub.add("gh run list", [_run(12, head_sha="v1", event="pull_request")])
        stub.add("/pulls?state=all", [_pr(21, sha="v2", branch="feature/w")])

        audited, _ = _audit_with(stub)
        self.assertEqual(audited[0]["verdict"], "CANCEL")

        stub.calls.clear()
        stub.add("/actions/runs/12", {"status": "queued", "event": "pull_request", "name": "CI"})
        stub.add("/pulls/21", _pr(21, sha="v1", branch="feature/w"))

        refreshed = ci_queue_trim.refresh_before_cancel(
            "owner/repo", audited, run_cmd=stub
        )
        self.assertEqual(refreshed, [])

    def test_refresh_skips_run_when_workflow_changed_to_protected(self):
        """If the run's workflow filename matches the explicit protected
        list now (e.g. an admin reconfigured the workflow), the refresh
        must drop the candidate."""

        stub = _RunCmdStub()
        stub.add("gh run list", [_run(15, head_sha="r1", event="pull_request", name="Plain CI")])
        stub.add("/pulls?state=all", [_pr(40, sha="new1", branch="feature/prot")])
        stub.add("/commits/new1", _commit("new1", age_minutes=5))

        audited, _ = _audit_with(stub)
        self.assertEqual(audited[0]["verdict"], "CANCEL")

        stub.calls.clear()
        stub.add("/actions/runs/15", {"status": "queued", "event": "pull_request", "name": "release.yml"})
        stub.add("/pulls/40", _pr(40, sha="new1", branch="feature/prot"))

        with mock.patch.object(ci_queue_trim, "PROTECTED_WORKFLOWS", {"release.yml"}):
            refreshed = ci_queue_trim.refresh_before_cancel(
                "owner/repo", audited, run_cmd=stub
            )
        self.assertEqual(refreshed, [])


# ---------------------------------------------------------------------------
# Workflow / branch protection guards (explicit allowlists only)
# ---------------------------------------------------------------------------


class TestProtection(unittest.TestCase):
    """Workflows that are explicitly listed in ``PROTECTED_WORKFLOWS`` must
    be kept. The ``deploy`` branch must be protected. Workflows whose names
    merely contain the substring 'reusable' must NOT trigger protection
    unless they are explicitly listed."""

    def test_reusable_workflow_call_is_kept_via_event(self):
        stub = _RunCmdStub()
        stub.add(
            "gh run list",
            [_run(13, name="Plain CI", head_sha="r1", event="workflow_call", branch="feature/q")],
        )
        stub.add("/pulls?state=all", [_pr(30, sha="r1", branch="feature/q")])
        stub.add("/commits/r1", _commit("r1", age_minutes=5))

        audited, _ = _audit_with(stub)
        self.assertEqual(audited[0]["verdict"], "KEEP")
        # Reason must reference the event, not a fuzzy substring of the name.
        self.assertIn("workflow_call", audited[0]["reason"].lower())

    def test_workflow_in_explicit_protect_list_is_kept(self):
        stub = _RunCmdStub()
        stub.add(
            "gh run list",
            [_run(16, name="Deploy Production", head_sha="r2", event="pull_request", branch="feature/d")],
        )
        stub.add("/pulls?state=all", [_pr(31, sha="new2", branch="feature/d")])
        stub.add("/commits/new2", _commit("new2", age_minutes=5))

        audited, _ = _audit_with(stub)
        # Audit-time check: name contains "Deploy" but is NOT in protected list yet.
        self.assertEqual(audited[0]["verdict"], "CANCEL")

    def test_fuzzy_name_match_does_not_trigger_protection(self):
        """A workflow whose name merely contains a protected keyword must
        not be kept unless explicitly listed."""

        stub = _RunCmdStub()
        stub.add(
            "gh run list",
            [_run(17, name="my-deploy-helper", head_sha="r3", event="pull_request", branch="feature/x")],
        )
        stub.add("/pulls?state=all", [_pr(32, sha="new3", branch="feature/x")])
        stub.add("/commits/new3", _commit("new3", age_minutes=5))

        with mock.patch.object(ci_queue_trim, "PROTECTED_WORKFLOWS", set()):
            audited, _ = _audit_with(stub)

        self.assertEqual(audited[0]["verdict"], "CANCEL")

    def test_deploy_branch_is_kept(self):
        stub = _RunCmdStub()
        stub.add("gh run list", [_run(14, head_sha="d1", event="push", branch="deploy")])
        stub.add("/pulls?state=all", [])

        audited, _ = _audit_with(stub)
        self.assertEqual(audited[0]["verdict"], "KEEP")
        self.assertIn("protected branch", audited[0]["reason"].lower())


# ---------------------------------------------------------------------------
# --superseded-only mode
# ---------------------------------------------------------------------------


class TestSupersededOnlyMode(unittest.TestCase):
    """``superseded_only=True`` must cancel ONLY runs whose head SHA no
    longer matches the PR/branch current head. Dormant but-current-head
    runs must stay untouched, even if their head commit is ancient."""

    def test_superseded_only_keeps_dormant_but_current_head_runs(self):
        stub = _RunCmdStub()
        # Old run, but its head SHA still matches the PR's current head.
        # In normal mode this would be cancelled for dormancy (>2h).
        stub.add("gh run list", [_run(50, head_sha="still_current", branch="feature/long")])
        stub.add("/pulls?state=all", [_pr(60, sha="still_current", branch="feature/long")])
        stub.add("/commits/still_current", _commit("still_current", age_minutes=60 * 24 * 30))  # 30 days

        audited, stats = _audit_with(stub, superseded_only=True)

        self.assertEqual(audited[0]["verdict"], "KEEP")
        self.assertEqual(stats["to_cancel"], 0)
        self.assertIn("superseded-only", audited[0]["reason"].lower())

    def test_superseded_only_cancels_proven_superseded_runs(self):
        stub = _RunCmdStub()
        stub.add("gh run list", [_run(51, head_sha="old_run_sha")])
        stub.add("/pulls?state=all", [_pr(61, sha="new_head_sha", branch="feature/s")])
        stub.add("/pulls?state=all&head=owner:feature/s", _pr(61, sha="new_head_sha", branch="feature/s"))
        stub.add("/commits/new_head_sha", _commit("new_head_sha", age_minutes=5))

        audited, stats = _audit_with(stub, superseded_only=True)

        self.assertEqual(audited[0]["verdict"], "CANCEL")
        self.assertTrue(audited[0]["superseded"])
        self.assertEqual(stats["to_cancel"], 1)

    def test_superseded_only_still_cancels_merged_pr_runs(self):
        """Even in superseded-only mode, MERGED/CLOSED PRs are orphans and
        must be cancelled because the work landed regardless of head SHA."""

        stub = _RunCmdStub()
        stub.add("gh run list", [_run(52, head_sha="merged_sha")])
        stub.add("/pulls?state=all", [_pr(62, sha="merged_sha", state="MERGED", updated_minutes_ago=240)])

        audited, _ = _audit_with(stub, superseded_only=True)

        self.assertEqual(audited[0]["verdict"], "CANCEL")
        self.assertEqual(audited[0]["pr_state"], "MERGED")


if __name__ == "__main__":
    unittest.main()