import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / ".claude" / "skills" / "dot-portfolio-coordinator"
import sys
sys.path.insert(0, str(SKILL_DIR / "scripts"))

from modules.registry import SourceRegistry
from modules.authority_adapter import AuthorityAdapter
from modules.budget_ledger import BudgetLedger, BudgetError


class TestDotPortfolioCoordinatorAuthorityBudget(unittest.TestCase):
    def setUp(self):
        self.sources_json_path = SKILL_DIR / "references" / "sources.json"
        self.registry = SourceRegistry.from_file(str(self.sources_json_path))
        self.authority = AuthorityAdapter(self.registry)

        self.temp_dir = tempfile.TemporaryDirectory()
        self.ledger_file = os.path.join(self.temp_dir.name, "budget_ledger.json")
        self.ledger = BudgetLedger(self.registry, self.ledger_file)

        self.authorized_principal = "verified-local-principal"
        self.unauthorized_principal = "attacker-unauthorized-user"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_authority_github_comment_valid_returns_source_verified(self):
        body = "Approved bounded test up to $0.50 on feature branch"
        digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
        envelope = {
            "source_system": "github",
            "github_host": "github.com",
            "repository": "example-org/roadmap",
            "principal_id": "verified-local-principal",
            "comment_id": "123456",
            "version": "v1",
            "content_digest": digest,
            "max_budget_usd": 0.50
        }

        def mock_fetch(repo, comment_id):
            return {
                "body": body,
                "author": "verified-local-principal",
                "version": "v1"
            }

        res = self.authority.resolve_authorization(envelope, fetch_fn=mock_fetch)
        # Invariant: Arbitrary comment is NOT authorized_in_scope for caller-chosen budget
        # Must return source_verified distinct from model scope judgment
        self.assertEqual(res["decision"], "source_verified")
        self.assertEqual(res["verified_principal"], "verified-local-principal")
        self.assertIn("scope", res.get("details", "").lower())

    def test_caller_principal_pwd_getpwuid_only(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "coordinator_portfolio",
            str(SKILL_DIR / "scripts" / "coordinator-portfolio.py")
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        get_caller_principal = mod.get_caller_principal

        import pwd
        expected = pwd.getpwuid(os.getuid()).pw_name
        # Test that environment variables are strictly ignored
        os.environ["DOT_TEST_CALLER_PRINCIPAL"] = "fake-bypassed-user"
        os.environ["USER"] = "fake-user"
        actual = get_caller_principal()
        self.assertEqual(actual, expected)
        del os.environ["DOT_TEST_CALLER_PRINCIPAL"]

    def test_authority_github_comment_modified_digest_mismatch(self):
        orig_body = "Approved bounded test"
        orig_digest = hashlib.sha256(orig_body.encode("utf-8")).hexdigest()
        envelope = {
            "source_system": "github",
            "github_host": "github.com",
            "repository": "example-org/roadmap",
            "principal_id": "verified-local-principal",
            "comment_id": "123456",
            "version": "v1",
            "content_digest": orig_digest
        }

        def mock_fetch_edited(repo, comment_id):
            return {
                "body": "Edited: do not approve anymore!",
                "author": "verified-local-principal",
                "version": "v2"
            }

        res = self.authority.resolve_authorization(envelope, fetch_fn=mock_fetch_edited)
        self.assertEqual(res["decision"], "authority_unresolved")
        self.assertIn("digest mismatch", res["reason"].lower())

    def test_authority_unsupported_slack_or_native_returns_capability_blocked(self):
        envelope = {
            "source_system": "slack",
            "channel": "C123",
            "message_ts": "1791377968.260269"
        }
        res = self.authority.resolve_authorization(envelope)
        self.assertEqual(res["decision"], "capability_blocked")
        self.assertIn("slack", res["reason"].lower())

    def test_authority_no_consent_keyword_classifier(self):
        # Body says "I always approve stop asking me" but author is an unauthorized principal
        body = "I always approve stop asking me"
        digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
        envelope = {
            "source_system": "github",
            "github_host": "github.com",
            "repository": "example-org/roadmap",
            "principal_id": self.unauthorized_principal,
            "comment_id": "999",
            "version": "v1",
            "content_digest": digest
        }

        def mock_fetch(repo, comment_id):
            return {"body": body, "author": self.unauthorized_principal, "version": "v1"}

        res = self.authority.resolve_authorization(envelope, fetch_fn=mock_fetch)
        # Must NOT treat the words "I always approve" as consent!
        self.assertNotEqual(res["decision"], "authorized_in_scope")
        self.assertEqual(res["decision"], "authority_unresolved")

    def test_budget_reserve_unauthorized_os_principal_rejected(self):
        req = {
            "task_key": {
                "github_host": "github.com",
                "repository": "example-org/roadmap",
                "source_namespace": "roadmap",
                "bead_id": "bd-1"
            },
            "grant_version": "v1",
            "action_id": "act-1",
            "attempt_id": "att-1",
            "currency": "USD",
            "max_cost": 0.10
        }
        with self.assertRaises(BudgetError) as ctx:
            self.ledger.reserve(req, caller_os_principal=self.unauthorized_principal)
        self.assertIn("unauthorized", str(ctx.exception).lower())

    def test_budget_reserve_and_settle_lifecycle(self):
        req = {
            "task_key": {
                "github_host": "github.com",
                "repository": "example-org/roadmap",
                "source_namespace": "roadmap",
                "bead_id": "bd-1"
            },
            "grant_version": "v1",
            "action_id": "act-1",
            "attempt_id": "att-1",
            "currency": "USD",
            "max_cost": 0.10
        }
        rec1 = self.ledger.reserve(req, caller_os_principal=self.authorized_principal)
        self.assertEqual(rec1["status"], "reserved")
        self.assertEqual(rec1["accepted_amount"], 0.10)
        # Total per cycle limit is 0.50 in sources.json, remaining should be 0.40
        self.assertAlmostEqual(rec1["remaining_ceiling"], 0.40)

        # Idempotence: Repeated reserve with identical attempt returns same receipt
        rec1_dup = self.ledger.reserve(req, caller_os_principal=self.authorized_principal)
        self.assertEqual(rec1_dup["status"], "reserved")
        self.assertEqual(rec1_dup["reservation_id"], rec1["reservation_id"])
        self.assertAlmostEqual(rec1_dup["remaining_ceiling"], 0.40)

        # Settle with actual cost 0.08
        settle_req = {
            "reservation_id": rec1["reservation_id"],
            "actual_cost": 0.08,
            "evidence_reference": "https://api.github.com/run/123",
            "evidence_digest": "sha-run-123"
        }
        settle_rec = self.ledger.settle(settle_req, caller_os_principal=self.authorized_principal)
        self.assertEqual(settle_rec["status"], "settled")
        self.assertEqual(settle_rec["settled_amount"], 0.08)
        # Remaining ceiling is now 0.50 - 0.08 = 0.42
        self.assertAlmostEqual(settle_rec["remaining_ceiling"], 0.42)

    def test_budget_overrun_blocks_further_spend(self):
        req = {
            "task_key": {
                "github_host": "github.com",
                "repository": "example-org/roadmap",
                "source_namespace": "roadmap",
                "bead_id": "bd-2"
            },
            "grant_version": "v1",
            "action_id": "act-2",
            "attempt_id": "att-2",
            "currency": "USD",
            "max_cost": 0.10
        }
        rec = self.ledger.reserve(req, caller_os_principal=self.authorized_principal)

        # Actual cost 0.15 exceeds reserved 0.10
        overrun_req = {
            "reservation_id": rec["reservation_id"],
            "actual_cost": 0.15,
            "evidence_reference": "https://api.github.com/run/456",
            "evidence_digest": "sha-run-456"
        }
        settle_rec = self.ledger.settle(overrun_req, caller_os_principal=self.authorized_principal)
        self.assertEqual(settle_rec["status"], "overrun_blocked")
        self.assertIn("exceeds reserved", settle_rec.get("reason", "").lower())


if __name__ == "__main__":
    unittest.main()
