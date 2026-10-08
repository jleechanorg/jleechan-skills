import copy
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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

    def test_overrun_settlement_replay_is_terminal_and_preserves_storage(self):
        reservation = self.ledger.reserve({"action_id": "retry", "attempt_id": "1", "max_cost": .1}, self.authorized_principal)
        request = {"reservation_id": reservation["reservation_id"], "actual_cost": .15}
        first = self.ledger.settle(request, self.authorized_principal)
        before = Path(self.ledger_file).read_bytes()
        self.assertEqual(first["status"], "overrun_blocked")
        for ledger in (self.ledger, BudgetLedger(self.registry, self.ledger_file)):
            replay = ledger.settle(request, self.authorized_principal)
            self.assertEqual(replay["status"], "overrun_blocked")
            self.assertEqual((ledger.total_reserved, ledger.total_settled, ledger.ledger_version), (0, .15, 3))
            self.assertEqual(Path(self.ledger_file).read_bytes(), before)
            with self.assertRaises(BudgetError):
                ledger.settle(dict(request, actual_cost=.05), self.authorized_principal)
            self.assertEqual(Path(self.ledger_file).read_bytes(), before)

    def test_corrupt_budget_load_and_mutations_preserve_existing_bytes(self):
        self.ledger.reserve({"action_id": "stored", "attempt_id": "1", "max_cost": .1}, self.authorized_principal)
        path = Path(self.ledger_file)
        valid = json.loads(path.read_text())
        corrupt = ["{broken", "null", "[]", "{}"]
        for field, value in (("ledger_version", True), ("total_reserved", -1),
                             ("total_settled", float("nan")), ("reservations", []),
                             ("total_reserved", 0)):
            bad = copy.deepcopy(valid); bad[field] = value
            corrupt.append(json.dumps(bad))
        for field, value in (("status", "unknown"), ("reserved_amount", "0.1"),
                             ("settled_amount", -.1), ("reservation_id", "wrong")):
            bad = copy.deepcopy(valid); bad["reservations"]["res_stored_1"][field] = value
            corrupt.append(json.dumps(bad))
        for raw in corrupt:
            with self.subTest(raw=raw):
                path.write_text(raw)
                before = path.read_bytes()
                memory = copy.deepcopy(self.ledger.reservations)
                with self.assertRaises(BudgetError):
                    BudgetLedger(self.registry, self.ledger_file)
                for operation in (lambda: self.ledger.reserve({"action_id": "new", "attempt_id": "1", "max_cost": .1}, self.authorized_principal),
                                  lambda: self.ledger.settle({"reservation_id": "res_stored_1", "actual_cost": .05}, self.authorized_principal)):
                    with self.assertRaises(BudgetError):
                        operation()
                    self.assertEqual(path.read_bytes(), before)
                    self.assertEqual(self.ledger.reservations, memory)
        path.write_text(json.dumps(valid))
        reloaded = BudgetLedger(self.registry, self.ledger_file)
        self.assertEqual(reloaded.total_reserved, .1)
        self.assertEqual(reloaded.reservations, valid["reservations"])

    def test_valid_fractional_settlements_can_reload_without_negative_residue(self):
        self.registry.budget_policy["per_cycle_cost_usd"] = 1
        ledger = BudgetLedger(self.registry, self.ledger_file)
        ids = [ledger.reserve({"action_id": str(i), "attempt_id": "1", "max_cost": value}, self.authorized_principal)["reservation_id"] for i, value in enumerate((.1, .4, .2))]
        for identity in ids:
            ledger.settle({"reservation_id": identity, "actual_cost": 0}, self.authorized_principal)
        reloaded = BudgetLedger(self.registry, self.ledger_file)
        self.assertEqual(reloaded.total_reserved, 0)
        self.assertEqual(reloaded.total_settled, 0)

    def test_unreadable_budget_is_rejected_and_preserved(self):
        self.ledger.reserve({"action_id": "stored", "attempt_id": "1", "max_cost": .1}, self.authorized_principal)
        before = Path(self.ledger_file).read_bytes()
        with patch("builtins.open", side_effect=PermissionError("fixture denied")):
            with self.assertRaises(BudgetError):
                BudgetLedger(self.registry, self.ledger_file)
            with self.assertRaises(BudgetError):
                self.ledger.reserve({"action_id": "new", "attempt_id": "1", "max_cost": .1}, self.authorized_principal)
        self.assertEqual(Path(self.ledger_file).read_bytes(), before)
        self.assertEqual(self.ledger.total_reserved, .1)

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

    def _budget_snapshot(self):
        path = Path(self.ledger_file)
        stat = path.stat() if path.exists() else None
        return (
            self.ledger.total_reserved, self.ledger.total_settled,
            self.ledger.ledger_version, copy.deepcopy(self.ledger.reservations),
            path.read_bytes() if stat else None,
            (stat.st_ino, stat.st_mtime_ns) if stat else None,
            sorted(p.name for p in Path(self.temp_dir.name).iterdir()),
        )

    def test_budget_invalid_amounts_rejected_before_any_mutation(self):
        missing = object()
        invalid = [missing, None, True, False, -0.01, float("nan"),
                   float("inf"), float("-inf"), "0.1", "NaN", "bad", [], {},
                   10 ** 1000]
        for operation in ("reserve", "settle"):
            for value in invalid:
                for persisted in (False, True):
                    with self.subTest(operation=operation, value=repr(value),
                                      persisted=persisted):
                        path = Path(self.ledger_file)
                        path.unlink(missing_ok=True)
                        self.ledger = BudgetLedger(self.registry, self.ledger_file)
                        if persisted:
                            self.ledger.reserve({"action_id": "seed", "attempt_id": "1",
                                                 "max_cost": 0.1}, self.authorized_principal)
                        request = {"action_id": "new", "attempt_id": "1"} if operation == "reserve" else {
                            "reservation_id": "res_seed_1"}
                        field = "max_cost" if operation == "reserve" else "actual_cost"
                        if value is not missing:
                            request[field] = value
                        before = self._budget_snapshot()
                        with self.assertRaises(BudgetError):
                            getattr(self.ledger, operation)(request, self.authorized_principal)
                        self.assertEqual(self._budget_snapshot(), before)

    def test_budget_zero_and_bounded_replays_do_not_mutate(self):
        for amount in (0, 0.1):
            with self.subTest(amount=amount):
                request = {"action_id": str(amount), "attempt_id": "1", "max_cost": amount}
                receipt = self.ledger.reserve(request, self.authorized_principal)
                self.assertEqual(receipt["status"], "reserved")
                before = self._budget_snapshot()
                self.assertEqual(self.ledger.reserve(request, self.authorized_principal), receipt)
                self.assertEqual(self._budget_snapshot(), before)
                settlement = {"reservation_id": receipt["reservation_id"], "actual_cost": amount}
                settled = self.ledger.settle(settlement, self.authorized_principal)
                self.assertEqual(settled["status"], "settled")
                before = self._budget_snapshot()
                self.assertEqual(self.ledger.settle(settlement, self.authorized_principal), settled)
                self.assertEqual(self._budget_snapshot(), before)

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
