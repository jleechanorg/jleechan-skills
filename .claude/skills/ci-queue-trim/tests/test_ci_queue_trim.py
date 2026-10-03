#!/usr/bin/env python3
"""test_ci_queue_trim.py — focused offline regression tests for ci_queue_trim.py.

These tests exercise the audit + classifier without touching the network or
any ``gh`` CLI. They patch ``ci_queue_trim.run_cmd`` so the script's helpers
see per-test responses built from faithful GH REST shapes:

* ``run.workflow_path`` may be ``release.yml`` or ``release.yml@main`` — the
  comparator strips the ``@ref`` suffix.
* ``run.pull_requests`` is the only source of truth for which PR owns a run;
  a branch-name collision between fork A and fork B must NOT bind them.
* ``PR.head.sha`` is the head branch tip SHA, NOT the merge ref.

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

# Stable numeric repo identity (matches the live
# ``actions/runs/{id}.pull_requests[].head.repo`` shape, which has
# ``{id, name, url}`` but NOT ``full_name``). Identity verification
# in the audit + cancel path matches by this numeric ``id``.
REPO_ID = 1002634306
ALICE_REPO_ID = 1002634310
BOB_REPO_ID = 1002634312


def _iso(dt: datetime.datetime) -> str:
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Faithful GitHub REST fixtures
# ---------------------------------------------------------------------------


def queued_run(
    run_id: int,
    *,
    name: str = "CI",
    branch: str = "feature/test",
    head_sha: str = "abc123",
    event: str = "pull_request",
    workflow_path: str = ".github/workflows/ci.yml",
    pr_numbers: Optional[List[int]] = None,
    status: str = "queued",
    created_minutes_ago: int = 30,
    repository: Optional[Dict[str, Any]] = None,
    pr_head_repo: Optional[Dict[str, Any]] = None,
    pr_head_sha: Optional[str] = None,
) -> Dict[str, Any]:
    """The shape `gh api /repos/.../actions/runs/{id}` actually returns.

    ``pull_requests`` is the only authoritative pointer from run → PR; the
    audit MUST NOT derive that binding from head_branch alone. The run
    record also carries ``repository.{id, full_name, name}`` and the
    PR association's ``head.repo`` is ``{id, name, url}`` — WITHOUT
    ``full_name`` (per the live API). Identity verification matches by
    the stable numeric ``repo.id``.
    """
    if repository is None:
        repository = {"id": REPO_ID, "full_name": "owner/repo", "name": "repo"}
    if pr_head_repo is None:
        pr_head_repo = {"id": REPO_ID, "name": "repo"}
    return {
        "databaseId": run_id,
        "id": run_id,
        "name": name,
        "head_branch": branch,
        "head_sha": head_sha,
        "event": event,
        "path": workflow_path,
        "workflow_path": workflow_path,
        "status": status,
        "repository": repository,
        "pull_requests": [
            {
                "number": n,
                "head": {
                    "sha": pr_head_sha or head_sha,
                    "ref": "feature/x",
                    "repo": pr_head_repo,
                },
                "base": {
                    "ref": "main",
                    "repo": {
                        "id": REPO_ID,
                        "name": "repo",
                        "full_name": "owner/repo",
                    },
                },
            }
            for n in (pr_numbers or [])
        ],
        "createdAt": _iso(FIXED_NOW - datetime.timedelta(minutes=created_minutes_ago)),
        "url": f"https://github.com/owner/repo/actions/runs/{run_id}",
    }


def pr_record(
    number: int,
    *,
    head_sha: str = "abc123",
    base_sha: str = "base000",
    merge_commit_sha: Optional[str] = None,
    state: str = "open",
    head_repo: str = "owner/repo",
    base_repo: str = "owner/repo",
    head_repo_id: Optional[int] = None,
    base_repo_id: Optional[int] = None,
    head_ref: str = "feature/test",
    merged: bool = False,
    head_commit_minutes_ago: int = 10,
) -> Dict[str, Any]:
    """Faithful PR shape (``pulls/{n}``).

    ``head.sha`` is the head branch tip; ``merge_commit_sha`` is a separate
    field and is NOT what supersede comparison should use. ``head.repo``
    and ``base.repo`` carry the stable numeric ``id``; ``head.repo`` also
    carries ``full_name`` (the run's ``pull_requests[].head.repo`` does
    NOT — identity match is by ``id``).
    """
    if head_repo_id is None:
        head_repo_id = REPO_ID if head_repo == "owner/repo" else (
            ALICE_REPO_ID if head_repo == "alice/repo" else REPO_ID
        )
    if base_repo_id is None:
        base_repo_id = REPO_ID if base_repo == "owner/repo" else (
            ALICE_REPO_ID if base_repo == "alice/repo" else REPO_ID
        )
    return {
        "number": number,
        "state": state,
        "merged": merged,
        "merge_commit_sha": merge_commit_sha,
        "head": {
            "sha": head_sha,
            "ref": head_ref,
            "repo": {
                "id": head_repo_id,
                "full_name": head_repo,
                "name": head_repo.split("/")[-1],
            },
        },
        "base": {
            "sha": base_sha,
            "ref": "main",
            "repo": {
                "id": base_repo_id,
                "full_name": base_repo,
                "name": base_repo.split("/")[-1],
            },
        },
        "updated_at": _iso(FIXED_NOW - datetime.timedelta(minutes=5)),
        "head_commit_date": _iso(FIXED_NOW - datetime.timedelta(minutes=head_commit_minutes_ago)),
    }


# ---------------------------------------------------------------------------
# Command stub
# ---------------------------------------------------------------------------


class _RunCmdStub:
    """Stub for ``ci_queue_trim.run_cmd`` that responds by argv-substring match."""

    def __init__(self) -> None:
        self.responses: List[Tuple[str, Any]] = []
        self.calls: List[List[str]] = []
        # Per-run cmd response when `gh run cancel <id>` is invoked.
        self.cancel_calls: List[int] = []
        self.cancel_responses: Dict[int, Tuple[int, str, str]] = {}

    def add(self, matcher: str, payload: Any) -> None:
        self.responses.append((matcher, payload))

    def allow_cancel(self, run_id: int, rc: int = 0) -> None:
        self.cancel_responses[run_id] = (rc, "", "" if rc == 0 else "boom")

    def __call__(self, cmd: List[str], timeout: int = 60) -> Tuple[int, str, str]:
        self.calls.append(list(cmd))
        cmd_str = " ".join(cmd)
        # Intercept `gh run cancel`
        if "run cancel" in cmd_str:
            # parse run id
            for tok in cmd:
                if tok.isdigit():
                    self.cancel_calls.append(int(tok))
                    return self.cancel_responses.get(int(tok), (0, "", ""))
            return (1, "", "no run id parsed")
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
    real_datetime = ci_queue_trim.datetime.datetime

    class FrozenDateTime(real_datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            if tz is None:
                return FIXED_NOW.replace(tzinfo=None)
            return FIXED_NOW

    return mock.patch.object(ci_queue_trim.datetime, "datetime", FrozenDateTime)


def _reset_caches() -> None:
    # No module-level caches in the refactored design.
    return


def _setup_queue(
    stub: _RunCmdStub,
    run_records: List[Dict[str, Any]],
    pr_by_number: Optional[Dict[int, Dict[str, Any]]] = None,
    *,
    queue_fetch_rc: int = 0,
) -> None:
    """Wire up stub responses for an audit run.

    `run_records` are returned by per-run ``actions/runs/{id}`` calls.
    `pr_by_number` is fetched by ``pulls/{n}`` keyed by run PR number.
    The default ``gh run list`` response uses the first run's record so
    the audit has a starting queue. ``queue_fetch_rc`` is non-zero to
    simulate a failed queue fetch.

    Push events DO NOT have a branch HEAD stub pre-registered here; tests
    that need a particular branch HEAD must register one explicitly so
    they retain control over the supersede-vs-not verdict.
    """
    pr_by_number = pr_by_number or {}
    if queue_fetch_rc != 0:
        stub.add("gh run list", (queue_fetch_rc, "", "boom"))
        return
    list_view = [
        {
            "databaseId": r["databaseId"],
            "name": r["name"],
            "headBranch": r["head_branch"],
            "headSha": r["head_sha"],
            "event": r["event"],
            "status": r["status"],
            "createdAt": r["createdAt"],
            "url": r["url"],
        }
        for r in run_records
    ]
    stub.add("gh run list", list_view)
    for r in run_records:
        run_id = r["databaseId"]
        stub.add(f"/actions/runs/{run_id}", r)
        for pr_ref in r.get("pull_requests", []):
            pr_num = pr_ref["number"]
            if pr_num in pr_by_number:
                stub.add(f"/pulls/{pr_num}", pr_by_number[pr_num])
            else:
                stub.add(f"/pulls/{pr_num}", (1, "", "404 missing"))


def _audit_with(stub: _RunCmdStub, **overrides: Any) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    kwargs = {
        "max_age_hours": 2.0, "limit": 50,
        # Default allowlist for tests that expect CANCEL verdicts on the
        # standard ci.yml workflow. Tests that exercise workflow
        # protection / different paths override this.
        "allowed_workflows": {".github/workflows/ci.yml"},
    }
    kwargs.update(overrides)
    _reset_caches()
    with mock.patch.object(ci_queue_trim, "run_cmd", side_effect=stub), _patch_now():
        return ci_queue_trim.audit_queue("owner/repo", **kwargs)


# ---------------------------------------------------------------------------
# Pure classifier — supersede / current head semantics
# ---------------------------------------------------------------------------


class TestClassifierSemantics(unittest.TestCase):
    """Exercise ``classify_run`` directly with PR-independent fixtures so the
    pure logic is tested without any HTTP shape coupling."""

    BASE_OPTS = {
        "protected_branches": ci_queue_trim.PROTECTED_BRANCHES,
        "protected_workflows": set(),
        "allowed_workflows": {".github/workflows/ci.yml"},
        "max_age_hours": 2.0,
        "superseded_only": False,
    }

    def _classify(self, run: Dict[str, Any], pr: Optional[Dict[str, Any]],
                  branch_head_sha: Optional[str], metadata_complete: bool = True):
        return ci_queue_trim.classify_run(
            run=run,
            pr=pr,
            branch_head_sha=branch_head_sha,
            metadata_complete=metadata_complete,
            options=self.BASE_OPTS,
            now=FIXED_NOW,
        )

    def test_pull_request_supersede_uses_pr_head_sha_tip_not_merge_ref(self):
        """The merge_commit_sha must NOT be used for supersede comparison;
        PR.head.sha (the head branch tip) is the correct ref."""
        run = queued_run(1, head_sha="old_run_sha", pr_numbers=[42])
        pr = pr_record(
            42,
            head_sha="new_tip",
            merge_commit_sha="merge_commit_xyz",  # separate field; not used
        )
        cls = self._classify(run, pr, None)
        self.assertEqual(cls.verdict, "CANCEL")
        self.assertTrue(cls.superseded)
        self.assertFalse(cls.audit_incomplete)

    def test_pull_request_current_head_kept_when_run_sha_matches_tip(self):
        run = queued_run(2, head_sha="tip_a", pr_numbers=[42])
        pr = pr_record(42, head_sha="tip_a", head_commit_minutes_ago=10)
        cls = self._classify(run, pr, None)
        self.assertEqual(cls.verdict, "KEEP")
        self.assertFalse(cls.superseded)

    def test_pull_request_target_keeps_unless_proven(self):
        """pull_request_target runs use the BASE branch SHA; supersede is
        NOT proven by PR.head.sha differing. Only MERGED/CLOSED cancels."""
        run = queued_run(3, head_sha="base_at_v1", event="pull_request_target",
                         branch="feature/qt", pr_numbers=[42])
        pr_open = pr_record(42, head_sha="tip_v2")  # tip advanced
        cls = self._classify(run, pr_open, None)
        # Open PR + base-side semantics → KEEP unless proven.
        self.assertEqual(cls.verdict, "KEEP")
        self.assertFalse(cls.superseded)

        pr_merged = pr_record(42, head_sha="tip_v2", state="closed", merged=True)
        cls = self._classify(run, pr_merged, None)
        self.assertEqual(cls.verdict, "CANCEL")
        self.assertEqual(cls.pr_state, "MERGED")

    def test_push_event_branch_head_mismatch_cancels(self):
        run = queued_run(4, head_sha="branch_old", event="push", branch="feature/x",
                         pr_numbers=[])
        cls = self._classify(run, None, branch_head_sha="branch_new")
        self.assertEqual(cls.verdict, "CANCEL")
        self.assertTrue(cls.superseded)

    def test_merge_group_event_skips_stale_head_comparison(self):
        run = queued_run(5, head_sha="x", event="merge_group", branch="feature/mq",
                         pr_numbers=[], created_minutes_ago=6 * 60)
        cls = self._classify(run, None, "anything")
        self.assertEqual(cls.verdict, "KEEP")
        self.assertIn("merge_group", cls.reason.lower())

    def test_unknown_event_keeps_with_audit_incomplete(self):
        run = queued_run(6, head_sha="x", event="repository_dispatch", pr_numbers=[])
        cls = self._classify(run, None, None)
        self.assertEqual(cls.verdict, "KEEP")
        self.assertTrue(cls.audit_incomplete)
        self.assertIn("unsupported", cls.reason.lower())


# ---------------------------------------------------------------------------
# PR association — fork A branch must not bind fork B's PR
# ---------------------------------------------------------------------------


class TestPRAssociation(unittest.TestCase):
    """The run-detail ``pull_requests`` array is the only authoritative PR
    pointer. Two forks sharing a branch name MUST NOT cross-bind."""

    def test_two_forks_same_branch_identity_does_not_cross_bind(self):
        """Both forks push a branch named ``feature/x``. The audit must
        only follow the PR that the run detail explicitly associates."""
        stub = _RunCmdStub()
        fork_a_run = queued_run(
            100,
            branch="feature/x",
            head_sha="sha_alice_tip",
            pr_numbers=[1001],  # alice's PR, only
            pr_head_repo={"id": ALICE_REPO_ID, "name": "repo"},
        )
        pr_alice = pr_record(
            1001,
            head_sha="sha_alice_tip",
            head_repo="alice/repo",
            head_ref="feature/x",
        )
        # Note: fork B's PR (2002, branch=feature/x) is in the queue but
        # NOT in fork A's run detail pull_requests array. The audit must
        # not classify fork A's run against fork B's PR.
        pr_bob = pr_record(
            2002,
            head_sha="sha_bob_tip",
            head_repo="bob/repo",
            head_ref="feature/x",
            merged=True,  # closed
        )
        _setup_queue(stub, [fork_a_run], {1001: pr_alice, 2002: pr_bob})

        audited, _ = _audit_with(stub)
        self.assertEqual(len(audited), 1)
        self.assertEqual(audited[0]["pr_number"], 1001)
        self.assertEqual(audited[0]["verdict"], "KEEP")
        self.assertFalse(audited[0]["superseded"])

    def test_fork_pr_with_unknown_association_is_kept_unknown(self):
        """If the run detail's pull_requests array is empty (or the lookup
        fails for the listed PR), the audit must KEEP UNKNOWN — never guess
        via the branch name."""
        stub = _RunCmdStub()
        run_no_pr = queued_run(101, branch="feature/x", head_sha="sha_x",
                               pr_numbers=[])
        _setup_queue(stub, [run_no_pr])

        audited, _ = _audit_with(stub)
        self.assertEqual(len(audited), 1)
        self.assertIsNone(audited[0]["pr_number"])
        self.assertEqual(audited[0]["verdict"], "KEEP")
        self.assertTrue(audited[0]["audit_incomplete"])

    def test_push_event_does_not_bind_arbitrary_pr_via_branch(self):
        """Push events are NOT pull requests. The audit must not classify a
        push run against a PR that happens to share the branch name."""
        stub = _RunCmdStub()
        push_run = queued_run(
            102, event="push", branch="feature/x", head_sha="branch_old",
            pr_numbers=[],
        )
        # A PR happens to exist with the same branch name.
        same_branch_pr = pr_record(
            7, head_sha="branch_new", head_ref="feature/x"
        )
        _setup_queue(stub, [push_run], {7: same_branch_pr})
        # Override the branch-head response so push event sees a different head.
        stub.add("/branches/feature/x", {"commit": {"name": "refs/heads/feature/x", "sha": "branch_new"}})

        audited, _ = _audit_with(stub)
        self.assertEqual(len(audited), 1)
        self.assertEqual(audited[0]["event"], "push")
        # Push run is cancelled via branch-head mismatch, NOT via the PR.
        self.assertEqual(audited[0]["verdict"], "CANCEL")
        self.assertTrue(audited[0]["superseded"])
        # The PR was not used to classify.
        self.assertIsNone(audited[0]["pr_number"])


# ---------------------------------------------------------------------------
# API failure handling — incomplete audit must KEEP, not inherit stale defaults
# ---------------------------------------------------------------------------


class TestAPIFailureHandling(unittest.TestCase):
    """fetch_run_details or get_queued_runs failure must force KEEP for any
    run that depended on the missing data. A failed queue fetch must not be
    silently turned into a healthy empty success."""

    def test_run_detail_fetch_failure_marks_incomplete_and_keeps(self):
        stub = _RunCmdStub()
        stub.add("gh run list", [{"databaseId": 1, "headBranch": "feature/x",
                                  "headSha": "sha1", "event": "pull_request",
                                  "status": "queued", "name": "CI",
                                  "createdAt": _iso(FIXED_NOW)}])
        # Per-run detail fails (e.g. transient API error).
        stub.add("/actions/runs/1", (1, "", "boom"))

        audited, _ = _audit_with(stub)
        self.assertEqual(len(audited), 1)
        self.assertTrue(audited[0]["audit_incomplete"])
        self.assertEqual(audited[0]["verdict"], "KEEP")

    def test_queue_fetch_failure_does_not_become_healthy_empty(self):
        """A failed queue fetch must propagate as a failure marker, NOT
        succeed with an empty queue and no error."""
        stub = _RunCmdStub()
        stub.add("gh run list", (124, "", "timeout"))
        # The call to `audit_queue` itself should signal failure.
        from ci_queue_trim import audit_queue
        with mock.patch.object(ci_queue_trim, "run_cmd", side_effect=stub), _patch_now():
            audited, stats = audit_queue("owner/repo")
        self.assertEqual(audited, [])
        # Stats must carry the failure so the caller knows audit failed.
        self.assertTrue(stats.get("queue_fetch_failed"))
        self.assertEqual(stats["to_cancel"], 0)


# ---------------------------------------------------------------------------
# Pre-cancellation refresh — per-item, re-fetch + re-classify
# ---------------------------------------------------------------------------


class TestPerItemRefresh(unittest.TestCase):
    """Before EACH individual cancellation, the run AND its exact PR are
    re-fetched and the candidate re-classified with fresh state."""

    def _two_candidates(self) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        runs = [
            queued_run(200, head_sha="old_a", pr_numbers=[10]),
            queued_run(201, head_sha="old_b", pr_numbers=[11]),
        ]
        prs = {
            10: pr_record(10, head_sha="new_a"),
            11: pr_record(11, head_sha="new_b"),
        }
        return runs, prs

    def test_state_advance_between_first_and_second_cancel_drops_later(self):
        """After the first cancel, the second run's PR head advances so
        its supersede resolves. The second cancel must be dropped."""
        stub = _RunCmdStub()
        runs, prs = self._two_candidates()
        _setup_queue(stub, runs, prs)
        stub.allow_cancel(200)
        stub.allow_cancel(201)

        # Audit-time classification: both runs are CANCEL candidates.
        audited, _ = _audit_with(stub)
        cancel_candidates = [r for r in audited if r["verdict"] == "CANCEL"]
        self.assertEqual({r["run_id"] for r in cancel_candidates}, {200, 201})

        from ci_queue_trim import cancel_with_per_item_refresh

        # Between cancels: the first /pulls/11 fetch during cancel
        # returns a head that matches run 201, so the classifier
        # re-classifies it as KEEP and the run is dropped.
        fetch_counts = {"11": 0}
        stub_obj = stub

        def dynamic_fetch(cmd: List[str], timeout: int = 60):
            cmd_str = " ".join(cmd)
            if "/pulls/11" in cmd_str:
                fetch_counts["11"] += 1
                if fetch_counts["11"] >= 1:
                    return 0, json.dumps(pr_record(11, head_sha="old_b")), ""
            return stub_obj.__class__.__call__(stub_obj, cmd, timeout)

        with mock.patch.object(ci_queue_trim, "run_cmd", side_effect=dynamic_fetch), _patch_now():
            cancel_with_per_item_refresh(
                "owner/repo", cancel_candidates,
                allowed_workflows={".github/workflows/ci.yml"},
            )

        # Only run 200 should be cancelled; run 201 was dropped on re-fetch.
        self.assertEqual(stub.cancel_calls, [200])

    def test_real_eligible_cancellation_executes_gh_cancel_with_exact_id(self):
        """Verify ``gh run cancel <id>`` receives exactly the eligible ID
        and nothing else, with no extras."""
        stub = _RunCmdStub()
        runs, prs = self._two_candidates()
        _setup_queue(stub, runs, prs)
        stub.allow_cancel(200)
        stub.allow_cancel(201)

        from ci_queue_trim import cancel_with_per_item_refresh

        # Audit-time classification must agree the runs are CANCEL.
        audited, _ = _audit_with(stub)
        cancel_candidates = [r for r in audited if r["verdict"] == "CANCEL"]
        self.assertEqual({r["run_id"] for r in cancel_candidates}, {200, 201})

        with mock.patch.object(ci_queue_trim, "run_cmd", side_effect=stub), _patch_now():
            cancel_with_per_item_refresh(
                "owner/repo", cancel_candidates,
                allowed_workflows={".github/workflows/ci.yml"},
            )

        # Both candidates survive the per-item refresh and get cancelled.
        self.assertEqual(sorted(stub.cancel_calls), [200, 201])
        # Each cancel call must name exactly one numeric run id.
        for cmd in stub.calls:
            if "run cancel" in " ".join(cmd):
                self.assertEqual(sum(1 for t in cmd if t.isdigit()), 1)


# ---------------------------------------------------------------------------
# Workflow protection — @ref suffix, default safe allowlist
# ---------------------------------------------------------------------------


class TestWorkflowProtection(unittest.TestCase):
    """Workflow importance is decided by an explicit ``--allow-workflow``
    allowlist. Default empty allowlist keeps ALL workflows (no workflow
    may be cancelled unless the operator explicitly opts it in). The
    ``@<ref>`` suffix on a workflow path is stripped before matching,
    including refs that contain slashes (e.g. ``@refs/heads/feature/x``)."""

    def test_release_yml_at_refs_heads_feature_x_kept_by_default(self):
        """Without --allow-workflow, even a release workflow is kept by
        default. The full path including @refs/heads/feature/x must be
        stripped before matching."""
        stub = _RunCmdStub()
        run = queued_run(
            300, name="Release", event="pull_request",
            head_sha="old", pr_numbers=[42],
            workflow_path=".github/workflows/release.yml@refs/heads/feature/x",
        )
        pr = pr_record(42, head_sha="new_tip")
        _setup_queue(stub, [run], {42: pr})

        audited, _ = _audit_with(stub)
        self.assertEqual(audited[0]["verdict"], "KEEP")
        self.assertIn("release.yml", audited[0]["reason"])
        # The reason reflects the safe default (no allow-workflow match).
        self.assertIn("not in", audited[0]["reason"].lower())

    def test_deploy_yml_at_v2_kept_by_default(self):
        stub = _RunCmdStub()
        run = queued_run(
            301, name="Deploy", event="push",
            branch="feature/x", head_sha="branch_old", pr_numbers=[],
            workflow_path=".github/workflows/deploy.yml@v2",
        )
        _setup_queue(stub, [run])
        stub.add(
            "/branches/feature/x",
            {"commit": {"name": "refs/heads/feature/x", "sha": "branch_new"}},
        )

        audited, _ = _audit_with(stub)
        # Default empty allowlist → KEEP "not in --allow-workflow list".
        self.assertEqual(audited[0]["verdict"], "KEEP")
        self.assertIn("not in", audited[0]["reason"].lower())

    def test_allow_workflow_cli_flag_enables_cancellation(self):
        """``--allow-workflow`` is a positive cancellation allowlist. It
        does NOT extend any default protection; without an explicit
        opt-in, no workflows may be cancelled."""
        stub = _RunCmdStub()
        run = queued_run(
            302, name="My Build", event="pull_request",
            head_sha="old", pr_numbers=[42],
            workflow_path=".github/workflows/custom/build.yml",
        )
        pr = pr_record(42, head_sha="new_tip")
        _setup_queue(stub, [run], {42: pr})

        # Default: empty allowlist → KEEP
        audited, _ = _audit_with(stub)
        self.assertEqual(audited[0]["verdict"], "KEEP")

        # Opt-in: allow .github/workflows/custom/build.yml → CANCEL
        audited, _ = _audit_with(
            stub, allowed_workflows={".github/workflows/custom/build.yml"}
        )
        self.assertEqual(audited[0]["verdict"], "CANCEL")

    def test_protect_workflow_cli_flag_protects_even_when_allowed(self):
        """``--protect-workflow`` adds an explicit protection. A workflow
        that's both allowed and protected stays KEEP (protection wins)."""
        stub = _RunCmdStub()
        run = queued_run(
            303, name="CI", event="pull_request",
            head_sha="old", pr_numbers=[42],
            workflow_path=".github/workflows/ci.yml@refs/heads/feature/x",
        )
        pr = pr_record(42, head_sha="new_tip")
        _setup_queue(stub, [run], {42: pr})

        audited, _ = _audit_with(
            stub,
            allowed_workflows={".github/workflows/ci.yml"},
            protected_workflows={".github/workflows/ci.yml"},
        )
        self.assertEqual(audited[0]["verdict"], "KEEP")
        self.assertIn("protected", audited[0]["reason"].lower())

    def test_protected_branch_main_preserved(self):
        stub = _RunCmdStub()
        run = queued_run(
            304, name="CI", event="pull_request",
            branch="main", head_sha="sha_x", pr_numbers=[42],
        )
        _setup_queue(stub, [run])

        audited, _ = _audit_with(stub)
        self.assertEqual(audited[0]["verdict"], "KEEP")
        self.assertIn("protected branch", audited[0]["reason"].lower())


# ---------------------------------------------------------------------------
# Backwards-compatibility smoke
# ---------------------------------------------------------------------------


class TestBackwardCompatibility(unittest.TestCase):
    """The audit output must still carry every field the original skill
    relied on, even if values are now more conservative."""

    def test_row_shape_includes_all_legacy_and_new_fields(self):
        stub = _RunCmdStub()
        run = queued_run(400, head_sha="old", pr_numbers=[42])
        pr = pr_record(42, head_sha="new_tip")
        _setup_queue(stub, [run], {42: pr})

        audited, _ = _audit_with(stub)
        row = audited[0]
        for key in (
            "run_id", "name", "branch", "pr_number", "pr_state",
            "head_commit_age", "pr_updated_age", "deceptive_delta",
            "verdict", "reason",
        ):
            self.assertIn(key, row)
        # New fields:
        for key in ("event", "superseded", "audit_incomplete"):
            self.assertIn(key, row)


# ---------------------------------------------------------------------------
# Round 4 fixes — strict identity, single classifier path, supersede-only,
# malformed/missing fields, fresh id-equality, repo-id shape.
# ---------------------------------------------------------------------------


class TestNewReviewCoverage(unittest.TestCase):
    """Regressions for the round-4 review fixes.

    * ``--allow-workflow`` is a positive allowlist (default empty keeps
      all workflows; arbitrary deploy paths stay KEEP absent allow).
    * ``--allow-workflow`` does NOT add protection (``--protect-workflow``
      does).
    * ``--superseded-only`` cancels only ``superseded=True``; terminal
      matching heads KEEP, including on ``pull_request_target``.
    * ``cancel_with_per_item_refresh`` validates the fresh response
      (``id == requested run_id``, required fields present, repo
      identity present), uses the SAME pure classifier for the final
      decision, and refuses to cancel on any incomplete state.
    * Dormancy-based cancellation is preserved separately from
      ``--superseded-only`` and propagates through the same classifier
      path at mutation time.
    * ``_strip_ref`` handles refs that contain slashes
      (``@refs/heads/feature/x``).
    * ``_collect_inputs`` requires exactly one PR association (0 or >1
      ⇒ UNKNOWN). Identity is matched by stable numeric ``repo.id``
      (the live ``actions/runs/{id}.pull_requests[].head.repo`` shape
      is ``{id, name, url}`` — NOT ``full_name``).
    """

    BASE_OPTS = {
        "protected_branches": ci_queue_trim.PROTECTED_BRANCHES,
        "protected_workflows": set(),
        "allowed_workflows": {".github/workflows/ci.yml"},
        "max_age_hours": 2.0,
        "superseded_only": False,
    }

    # ---- _strip_ref + realistic fixtures ----

    def test_strip_ref_handles_slash_in_ref(self):
        """_strip_ref must handle refs that contain slashes; the
        previous regex left such paths intact."""
        self.assertEqual(
            ci_queue_trim._strip_ref(".github/workflows/release.yml@refs/heads/feature/x"),
            ".github/workflows/release.yml",
        )
        self.assertEqual(
            ci_queue_trim._strip_ref(".github/workflows/release.yml@main"),
            ".github/workflows/release.yml",
        )
        self.assertEqual(
            ci_queue_trim._strip_ref(".github/workflows/release.yml"),
            ".github/workflows/release.yml",
        )
        self.assertEqual(ci_queue_trim._strip_ref(""), "")

    def test_live_shaped_pull_request_identity_red_and_green(self):
        """Live ``actions/runs/{id}.pull_requests[].head.repo`` is
        ``{id, name, url}`` (no ``full_name``); ``pulls/{n}.head.repo``
        is ``{id, full_name, name, ...}``. Identity MUST match by the
        stable numeric ``repo.id``. Mismatched id → UNKNOWN; matching
        id → proceeds to the classifier."""
        # RED: id mismatch → UNKNOWN
        stub = _RunCmdStub()
        run_red = queued_run(
            700, head_sha="old", pr_numbers=[42],
            pr_head_repo={"id": ALICE_REPO_ID, "name": "repo"},
        )
        pr_bob = pr_record(42, head_sha="new_tip", head_repo="bob/repo",
                           head_repo_id=BOB_REPO_ID)
        _setup_queue(stub, [run_red], {42: pr_bob})
        audited, _ = _audit_with(stub)
        self.assertEqual(audited[0]["verdict"], "KEEP")
        self.assertTrue(audited[0]["audit_incomplete"])

        # GREEN: matching id → proceeds to classifier (superseded → CANCEL)
        stub_g = _RunCmdStub()
        run_green = queued_run(
            701, head_sha="old", pr_numbers=[42],
            pr_head_repo={"id": ALICE_REPO_ID, "name": "repo"},
        )
        pr_alice = pr_record(42, head_sha="new_tip", head_repo="alice/repo",
                             head_repo_id=ALICE_REPO_ID)
        _setup_queue(stub_g, [run_green], {42: pr_alice})
        audited, _ = _audit_with(stub_g)
        self.assertEqual(audited[0]["verdict"], "CANCEL")
        self.assertTrue(audited[0]["superseded"])

    # ---- exactly-one PR requirement ----

    def test_exactly_one_pr_association_required_zero_or_many_yields_unknown(self):
        """0 or >1 PR associations both yield UNKNOWN. We do not pick
        a canonical PR when the run detail itself does not."""
        # Zero
        stub = _RunCmdStub()
        run_zero = queued_run(710, head_sha="old", pr_numbers=[])
        _setup_queue(stub, [run_zero])
        audited, _ = _audit_with(stub)
        self.assertEqual(audited[0]["verdict"], "KEEP")
        self.assertTrue(audited[0]["audit_incomplete"])

        # Many
        stub_m = _RunCmdStub()
        run_many = queued_run(711, head_sha="old", pr_numbers=[42, 99])
        _setup_queue(stub_m, [run_many])
        audited, _ = _audit_with(stub_m)
        self.assertEqual(audited[0]["verdict"], "KEEP")
        self.assertTrue(audited[0]["audit_incomplete"])

    # ---- allowlist semantics ----

    def test_arbitrary_deploy_path_kept_absent_allow(self):
        """Without ``--allow-workflow``, arbitrary deploy paths are kept
        by default — even with a fresh supersede the workflow filter
        blocks cancellation."""
        stub = _RunCmdStub()
        run = queued_run(
            720, event="pull_request", head_sha="old", pr_numbers=[42],
            workflow_path=".github/workflows/deploy.yml@refs/heads/feature/x",
        )
        pr = pr_record(42, head_sha="new_tip")
        _setup_queue(stub, [run], {42: pr})

        audited, _ = _audit_with(stub)
        self.assertEqual(audited[0]["verdict"], "KEEP")
        self.assertIn("not in", audited[0]["reason"].lower())

    def test_allowed_ci_path_cancels(self):
        """With ``--allow-workflow`` set to the run's path, the run is
        CANCEL-eligible and cancellation fires."""
        stub = _RunCmdStub()
        run = queued_run(
            721, event="pull_request", head_sha="old", pr_numbers=[42],
            workflow_path=".github/workflows/ci.yml",
        )
        pr = pr_record(42, head_sha="new_tip")
        _setup_queue(stub, [run], {42: pr})
        stub.allow_cancel(721)

        audited, _ = _audit_with(
            stub, allowed_workflows={".github/workflows/ci.yml"}
        )
        self.assertEqual(audited[0]["verdict"], "CANCEL")

        with mock.patch.object(ci_queue_trim, "run_cmd", side_effect=stub), _patch_now():
            cancelled = ci_queue_trim.cancel_with_per_item_refresh(
                "owner/repo", audited,
                allowed_workflows={".github/workflows/ci.yml"},
            )
        self.assertEqual(cancelled, [721])
        self.assertEqual(stub.cancel_calls, [721])

    def test_allow_does_not_protect(self):
        """``--allow-workflow PATH`` enables cancellation; it does NOT
        add ``PATH`` to the protected list. To protect, use
        ``--protect-workflow``."""
        stub = _RunCmdStub()
        run = queued_run(
            722, event="pull_request", head_sha="old", pr_numbers=[42],
            workflow_path=".github/workflows/custom/build.yml",
        )
        pr = pr_record(42, head_sha="new_tip")
        _setup_queue(stub, [run], {42: pr})

        # Default empty → KEEP
        audited, _ = _audit_with(stub)
        self.assertEqual(audited[0]["verdict"], "KEEP")

        # Opt-in allow → CANCEL
        audited, _ = _audit_with(
            stub, allowed_workflows={".github/workflows/custom/build.yml"}
        )
        self.assertEqual(audited[0]["verdict"], "CANCEL")

        # Same allow + protected → KEEP (protection wins over allow).
        audited, _ = _audit_with(
            stub,
            allowed_workflows={".github/workflows/custom/build.yml"},
            protected_workflows={".github/workflows/custom/build.yml"},
        )
        self.assertEqual(audited[0]["verdict"], "KEEP")
        self.assertIn("protected", audited[0]["reason"].lower())

    # ---- superseded-only terminal matching ----

    def test_terminal_current_sha_kept_superseded_only(self):
        """In ``--superseded-only`` mode, terminal matching heads KEEP.
        Only ``superseded=True`` cancels. This applies to
        ``pull_request_target`` (base-side runs are NEVER cancelled in
        superseded-only mode) and to ``pull_request`` MERGED/CLOSED
        whose head still matches the run."""
        # pull_request_target MERGED with matching head → KEEP
        run_t = queued_run(
            730, head_sha="base_v1", event="pull_request_target",
            branch="feature/qt", pr_numbers=[42],
        )
        pr_merged_qt = pr_record(42, head_sha="base_v1", state="closed", merged=True)
        cls = ci_queue_trim.classify_run(
            run=run_t, pr=pr_merged_qt, branch_head_sha=None,
            metadata_complete=True,
            options={**self.BASE_OPTS, "superseded_only": True},
            now=FIXED_NOW,
        )
        self.assertEqual(cls.verdict, "KEEP")

        # pull_request MERGED with matching head → KEEP in superseded-only
        run_p = queued_run(
            731, head_sha="tip_v1", event="pull_request",
            branch="feature/x", pr_numbers=[42],
        )
        pr_merged_p = pr_record(42, head_sha="tip_v1", state="closed", merged=True)
        cls = ci_queue_trim.classify_run(
            run=run_p, pr=pr_merged_p, branch_head_sha=None,
            metadata_complete=True,
            options={**self.BASE_OPTS, "superseded_only": True},
            now=FIXED_NOW,
        )
        self.assertEqual(cls.verdict, "KEEP")

        # But superseded=True still cancels in superseded-only mode.
        run_s = queued_run(
            732, head_sha="old_sha", event="pull_request",
            branch="feature/x", pr_numbers=[42],
        )
        pr_new = pr_record(42, head_sha="new_tip")
        cls = ci_queue_trim.classify_run(
            run=run_s, pr=pr_new, branch_head_sha=None,
            metadata_complete=True,
            options={**self.BASE_OPTS, "superseded_only": True},
            now=FIXED_NOW,
        )
        self.assertEqual(cls.verdict, "CANCEL")
        self.assertTrue(cls.superseded)

    # ---- fresh-response validation at mutation time ----

    def test_malformed_fresh_response_no_cancel(self):
        """If the fresh re-fetch returns a response missing required
        fields or with a mismatched ``id``, the run is NOT cancelled
        even if the audit verdict was CANCEL."""
        stub = _RunCmdStub()
        run = queued_run(740, head_sha="old", pr_numbers=[42])
        pr = pr_record(42, head_sha="new_tip")
        _setup_queue(stub, [run], {42: pr})

        audited, _ = _audit_with(stub)
        candidates = [r for r in audited if r["verdict"] == "CANCEL"]
        self.assertEqual(len(candidates), 1)

        call_count = {"740": 0}

        def dynamic_fetch(cmd, timeout=60):
            cmd_str = " ".join(cmd)
            if "/actions/runs/740" in cmd_str:
                call_count["740"] += 1
                if call_count["740"] >= 1:
                    # Malformed: missing 'id' and 'event'
                    return 0, json.dumps({
                        "name": "CI",
                        "head_branch": "feature/test",
                        "head_sha": "old",
                        "path": ".github/workflows/ci.yml",
                        "status": "queued",
                        "pull_requests": [
                            {"number": 42, "head": {"repo": {"id": REPO_ID, "name": "repo"}}}
                        ],
                        "repository": {"id": REPO_ID, "full_name": "owner/repo", "name": "repo"},
                    }), ""
            return stub(cmd, timeout)

        with mock.patch.object(ci_queue_trim, "run_cmd", side_effect=dynamic_fetch), _patch_now():
            cancelled = ci_queue_trim.cancel_with_per_item_refresh(
                "owner/repo", candidates,
                allowed_workflows={".github/workflows/ci.yml"},
            )
        self.assertEqual(cancelled, [])
        self.assertEqual(stub.cancel_calls, [])

    def test_missing_repo_identity_no_cancel(self):
        """If the fresh re-fetch returns data without repository identity
        (no ``id``, no ``full_name``), the run is NOT cancelled."""
        stub = _RunCmdStub()
        run = queued_run(750, head_sha="old", pr_numbers=[42])
        pr = pr_record(42, head_sha="new_tip")
        _setup_queue(stub, [run], {42: pr})

        audited, _ = _audit_with(stub)
        candidates = [r for r in audited if r["verdict"] == "CANCEL"]
        self.assertEqual(len(candidates), 1)

        call_count = {"750": 0}

        def dynamic_fetch(cmd, timeout=60):
            cmd_str = " ".join(cmd)
            if "/actions/runs/750" in cmd_str:
                call_count["750"] += 1
                if call_count["750"] >= 1:
                    return 0, json.dumps({
                        "id": 750, "name": "CI",
                        "head_branch": "feature/test", "head_sha": "old",
                        "event": "pull_request",
                        "path": ".github/workflows/ci.yml",
                        "status": "queued",
                        "pull_requests": [
                            {"number": 42, "head": {"repo": {"id": REPO_ID, "name": "repo"}}}
                        ],
                        # No "repository" field
                    }), ""
            return stub(cmd, timeout)

        with mock.patch.object(ci_queue_trim, "run_cmd", side_effect=dynamic_fetch), _patch_now():
            cancelled = ci_queue_trim.cancel_with_per_item_refresh(
                "owner/repo", candidates,
                allowed_workflows={".github/workflows/ci.yml"},
            )
        self.assertEqual(cancelled, [])
        self.assertEqual(stub.cancel_calls, [])

    def test_id_mismatch_in_fresh_response_no_cancel(self):
        """If the fresh re-fetch returns data with an ``id`` that does
        NOT match the requested ``run_id``, the run is NOT cancelled
        (the response is for a different run)."""
        stub = _RunCmdStub()
        run = queued_run(760, head_sha="old", pr_numbers=[42])
        pr = pr_record(42, head_sha="new_tip")
        _setup_queue(stub, [run], {42: pr})

        audited, _ = _audit_with(stub)
        candidates = [r for r in audited if r["verdict"] == "CANCEL"]
        self.assertEqual(len(candidates), 1)

        call_count = {"760": 0}

        def dynamic_fetch(cmd, timeout=60):
            cmd_str = " ".join(cmd)
            if "/actions/runs/760" in cmd_str:
                call_count["760"] += 1
                if call_count["760"] >= 1:
                    # Return data for a DIFFERENT run id.
                    return 0, json.dumps({
                        "id": 999999, "name": "CI",
                        "head_branch": "feature/test", "head_sha": "old",
                        "event": "pull_request",
                        "path": ".github/workflows/ci.yml",
                        "status": "queued",
                        "pull_requests": [
                            {"number": 42, "head": {"repo": {"id": REPO_ID, "name": "repo"}}}
                        ],
                        "repository": {"id": REPO_ID, "full_name": "owner/repo", "name": "repo"},
                    }), ""
            return stub(cmd, timeout)

        with mock.patch.object(ci_queue_trim, "run_cmd", side_effect=dynamic_fetch), _patch_now():
            cancelled = ci_queue_trim.cancel_with_per_item_refresh(
                "owner/repo", candidates,
                allowed_workflows={".github/workflows/ci.yml"},
            )
        self.assertEqual(cancelled, [])
        self.assertEqual(stub.cancel_calls, [])

    # ---- dormant mode preserved ----

    def test_dormant_current_head_cancels_at_mutation(self):
        """Dormancy-based CANCEL propagates through the same classifier
        + check path at mutation time (not silently dropped by separate
        decision logic)."""
        stub = _RunCmdStub()
        # Push event with an old head; branch head advanced → CANCEL.
        run = queued_run(
            770, event="push", branch="feature/dormant", head_sha="old_head",
            pr_numbers=[], workflow_path=".github/workflows/ci.yml",
        )
        _setup_queue(stub, [run])
        stub.add(
            "/branches/feature/dormant",
            {"commit": {"name": "refs/heads/feature/dormant", "sha": "new_head"}},
        )
        stub.allow_cancel(770)

        audited, _ = _audit_with(
            stub, allowed_workflows={".github/workflows/ci.yml"}
        )
        self.assertEqual(audited[0]["verdict"], "CANCEL")
        self.assertTrue(audited[0]["superseded"])

        with mock.patch.object(ci_queue_trim, "run_cmd", side_effect=stub), _patch_now():
            cancelled = ci_queue_trim.cancel_with_per_item_refresh(
                "owner/repo", audited,
                allowed_workflows={".github/workflows/ci.yml"},
            )
        self.assertEqual(cancelled, [770])
        self.assertEqual(stub.cancel_calls, [770])


if __name__ == "__main__":
    unittest.main()