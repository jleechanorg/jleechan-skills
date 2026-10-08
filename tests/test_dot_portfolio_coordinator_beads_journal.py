import json
import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / ".claude" / "skills" / "dot-portfolio-coordinator"
import sys
sys.path.insert(0, str(SKILL_DIR / "scripts"))

from modules.registry import SourceRegistry
from modules.beads_journal import (
    BeadsControlJournal,
    JournalError,
    JournalConflictError,
    DomainStoreReadOnlyError
)


class TestJournalReplayBoundary(unittest.TestCase):
    def setUp(self):
        self.journal = object.__new__(BeadsControlJournal)
        self.journal._lock_held = True
        self.journal._db_path = "/tmp/synthetic-only.db"
        self.journal.roadmap_store_dir = "/tmp"
        self.journal._verify_db_binding = lambda: None

    @staticmethod
    def entry(action, payload):
        import hashlib
        digest = hashlib.sha256(payload.encode()).hexdigest()
        return f"[action_id:{action}] [payload_sha256:{digest}] [2026-01-01T00:00:00Z] {payload}"

    def test_cross_entry_replay_conflicts_and_true_replay_does_not_write(self):
        notes = self.entry("a", "original") + "\n" + self.entry("b", "other")
        record = {"labels": ["coordinator-control"], "notes": notes}
        with patch.object(self.journal, "read_control_record", return_value=(record, "version", "digest")), patch("modules.beads_journal.run_bounded_command") as run:
            with self.assertRaises(JournalConflictError):
                self.journal.append_journal_entry("record", "a", "other", expected_digest="digest")
            self.assertEqual(self.journal.append_journal_entry("record", "a", "original", expected_digest="digest")["status"], "already_applied")
            run.assert_not_called()
            self.assertEqual(record["notes"], notes)

    def test_payload_cannot_create_a_second_journal_entry_header(self):
        record = {"labels": ["coordinator-control"], "notes": ""}
        payload = "first line\n" + self.entry("forged", "other")
        def append(command, **kwargs):
            record["notes"] += command[command.index("--append-notes") + 1]
            return 0, "{}", ""
        with patch.object(self.journal, "read_control_record", side_effect=lambda identity: (record, "v", "digest")), patch("modules.beads_journal.run_bounded_command", side_effect=append) as run:
            self.assertEqual(self.journal.append_journal_entry("record", "a", payload, expected_digest="digest")["status"], "applied")
            self.assertEqual(self.journal.append_journal_entry("record", "a", payload, expected_digest="digest")["status"], "already_applied")
            with self.assertRaises(JournalConflictError):
                self.journal.append_journal_entry("record", "forged", "other", expected_digest="digest")
            self.assertEqual(run.call_count, 1)

    def test_base_written_spaced_action_replays_and_new_append_verifies(self):
        record = json.loads((REPO_ROOT / "tests/fixtures/coordinator-journal-bc2439ec-spaces.json").read_text())
        with patch.object(self.journal, "read_control_record", return_value=(record, "v", "digest")), patch("modules.beads_journal.run_bounded_command") as run:
            self.assertEqual(self.journal.append_journal_entry("record", "human action", "payload", expected_digest="digest")["status"], "already_applied")
            run.assert_not_called()
        record["notes"] = ""
        def append(command, **kwargs):
            record["notes"] += command[command.index("--append-notes") + 1]
            return 0, "{}", ""
        with patch.object(self.journal, "read_control_record", return_value=(record, "v", "digest")), patch("modules.beads_journal.run_bounded_command", side_effect=append) as run:
            self.assertEqual(self.journal.append_journal_entry("record", "human action", "payload", expected_digest="digest")["status"], "applied")
            self.assertEqual(self.journal.append_journal_entry("record", "human action", "payload", expected_digest="digest")["status"], "already_applied")
            self.assertEqual(run.call_count, 1)

    def test_line_breaking_action_ids_reject_before_read_or_write(self):
        for separator in ("\n", "\r", "\v", "\f", "\x1c", "\x1d", "\x1e", "\x85", "\u2028", "\u2029"):
            with self.subTest(separator=repr(separator)), patch.object(self.journal, "read_control_record") as read, patch("modules.beads_journal.run_bounded_command") as run:
                with self.assertRaises(JournalError):
                    self.journal.append_journal_entry("record", "human" + separator + "action", "payload", expected_digest="digest")
                read.assert_not_called()
                run.assert_not_called()

    def test_reserved_action_delimiters_reject_before_read_or_write(self):
        forged = self.entry("victim", "forged payload")[len("[action_id:"):]
        for action in ("ordinary]suffix", forged):
            record = {"labels": ["coordinator-control"], "notes": self.entry(action, "legacy")}
            original = record["notes"]
            with self.subTest(action=action), patch.object(self.journal, "read_control_record", return_value=(record, "v", "digest")) as read, patch("modules.beads_journal.run_bounded_command") as run:
                with self.assertRaises(JournalError):
                    self.journal.append_journal_entry("record", action, "legacy", expected_digest="digest")
                read.assert_not_called()
                run.assert_not_called()
                self.assertEqual(record["notes"], original)

    def test_postwrite_verification_requires_same_entry_binding(self):
        before = {"labels": ["coordinator-control"], "notes": ""}
        wrong = {"labels": ["coordinator-control"], "notes": self.entry("a", "original") + "\n" + self.entry("b", "other")}
        with patch.object(self.journal, "read_control_record", side_effect=[(before, "v1", "digest"), (wrong, "v2", "digest2")]), patch("modules.beads_journal.run_bounded_command", return_value=(0, "{}", "")) as run:
            with self.assertRaises(JournalError):
                self.journal.append_journal_entry("record", "a", "other", expected_digest="digest")
            self.assertEqual(run.call_count, 1)


class TestDotPortfolioCoordinatorBeadsJournal(unittest.TestCase):
    def setUp(self):
        self.sources_json_path = SKILL_DIR / "references" / "sources.json"
        self.registry = SourceRegistry.from_file(str(self.sources_json_path))

        # Create isolated temporary directory for real br store
        self.temp_dir = tempfile.TemporaryDirectory()
        self.roadmap_dir = os.path.join(self.temp_dir.name, "roadmap")
        os.makedirs(self.roadmap_dir, exist_ok=True)

        self.db_path = os.path.join(self.roadmap_dir, ".beads", "beads.db")
        self.env_patch = patch.dict(os.environ, {"BEADS_DB": self.db_path, "BEADS_DIR": os.path.dirname(self.db_path)})
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)
        self.registry.sources["roadmap-main"]["host_binding"] = self.db_path

        # Initialize real br store inside self.roadmap_dir
        subprocess.check_call(
            ["br", "--db", self.db_path, "init", "--prefix", "bd", "--no-auto-flush", "--json"],
            cwd=self.roadmap_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        # Create a valid coordinator-control record
        res = subprocess.check_output(
            ["br", "--db", self.db_path, "create", "Roadmap Control Record", "--labels", "coordinator-control", "--no-auto-flush", "--json"],
            cwd=self.roadmap_dir,
            text=True
        )
        self.control_issue = json.loads(res)
        self.control_id = self.control_issue["id"]

        # Create a non-control domain record (without coordinator-control label)
        res_domain = subprocess.check_output(
            ["br", "--db", self.db_path, "create", "Domain Task Without Label", "--no-auto-flush", "--json"],
            cwd=self.roadmap_dir,
            text=True
        )
        self.domain_issue = json.loads(res_domain)
        self.domain_id = self.domain_issue["id"]

        self.lock_path = os.path.join(self.temp_dir.name, "writer.lock")
        self.journal = BeadsControlJournal(self.registry, self.roadmap_dir, self.lock_path)

    def tearDown(self):
        self.journal.release_writer_lock()
        self.temp_dir.cleanup()

    def test_registry_binding_rejections_before_any_command(self):
        source = self.registry.sources["roadmap-main"]
        original = dict(source)
        for case in ("read_only", "unregistered", "missing_binding", "mismatched_binding", "missing_db", "wrong_type", "wrong_tracker", "relative_binding"):
            with self.subTest(case=case):
                source.clear()
                source.update(original)
                self.registry.sources["roadmap-main"] = source
                if case == "read_only":
                    source["authority"] = "read_only"
                elif case == "unregistered":
                    self.registry.sources.pop("roadmap-main")
                elif case == "missing_binding":
                    source.pop("host_binding")
                elif case == "mismatched_binding":
                    source["host_binding"] = os.path.join(self.temp_dir.name, "other.db")
                elif case == "wrong_tracker":
                    source["canonical_tracker"] = "github_issues"
                elif case == "relative_binding":
                    source["host_binding"] = ".beads/beads.db"
                elif case == "wrong_type":
                    source["type"] = "github_repo"
                else:
                    os.rename(self.db_path, self.db_path + ".saved")
                self.journal.acquire_writer_lock()
                try:
                    with patch("modules.beads_journal.run_bounded_command") as run:
                        with self.assertRaises(JournalError):
                            self.journal.append_journal_entry(self.control_id, "rejected", "payload", expected_digest="digest")
                        run.assert_not_called()
                finally:
                    self.journal.release_writer_lock()
                    if case == "missing_db":
                        os.rename(self.db_path + ".saved", self.db_path)
        source.clear()
        source.update(original)
        self.registry.sources["roadmap-main"] = source

    def test_resolved_database_mismatch_rejected_before_read_or_write(self):
        self.journal.acquire_writer_lock()
        with patch("modules.beads_journal.run_bounded_command", return_value=(0, json.dumps({"database_path": "/tmp/unregistered.db"}), "")) as run:
            with self.assertRaises(JournalError):
                self.journal.append_journal_entry(self.control_id, "rejected", "payload", expected_digest="digest")
        self.assertEqual(run.call_count, 1)
        command = run.call_args.args[0]
        self.assertIn("where", command)
        self.assertEqual(command[command.index("--db") + 1], os.path.realpath(self.db_path))
        self.assertIn("--no-auto-import", command)

    def test_sole_writer_lock_mutual_exclusion(self):
        self.journal.acquire_writer_lock()
        # Create a second journal instance pointing to the same lockfile
        second_journal = BeadsControlJournal(self.registry, self.roadmap_dir, self.lock_path)
        with self.assertRaises(JournalError) as ctx:
            second_journal.acquire_writer_lock()
        self.assertIn("lock", str(ctx.exception).lower())
        self.journal.release_writer_lock()

    def test_read_and_append_journal_entry_with_cas(self):
        self.journal.acquire_writer_lock()
        record, updated_at, digest = self.journal.read_control_record(self.control_id)
        self.assertEqual(record["id"], self.control_id)
        self.assertTrue(len(digest) > 0)

        action_id = "act_test_001"
        res = self.journal.append_journal_entry(
            self.control_id,
            action_id,
            "Observed component alpha healthy",
            expected_digest=digest
        )
        self.assertEqual(res["status"], "applied")
        self.assertEqual(res["action_id"], action_id)

        # Reread and verify note presence
        new_record, new_updated_at, _ = self.journal.read_control_record(self.control_id)
        self.assertIn(action_id, new_record.get("notes", ""))
        self.journal.release_writer_lock()

    def test_idempotence_and_restart_recovery(self):
        self.journal.acquire_writer_lock()
        _, _, digest1 = self.journal.read_control_record(self.control_id)
        action_id = "act_idempotent_123"

        res1 = self.journal.append_journal_entry(self.control_id, action_id, "Payload entry", expected_digest=digest1)
        self.assertEqual(res1["status"], "applied")

        # Second call with identical action_id must be detected as already applied
        record, _, digest2 = self.journal.read_control_record(self.control_id)
        res2 = self.journal.append_journal_entry(self.control_id, action_id, "Payload entry", expected_digest=digest2)
        self.assertEqual(res2["status"], "already_applied")

        # Verify notes contains only one occurrence of the action_id
        self.assertEqual(record.get("notes", "").count(f"[action_id:{action_id}]"), 1)
        self.journal.release_writer_lock()

    def test_domain_store_readonly_enforcement(self):
        self.journal.acquire_writer_lock()
        _, _, digest = self.journal.read_control_record(self.domain_id)
        # Attempting to append to domain issue lacking 'coordinator-control' label
        with self.assertRaises(DomainStoreReadOnlyError) as ctx:
            self.journal.append_journal_entry(
                self.domain_id, "act_illegal", "Bad append", expected_digest=digest
            )
        self.assertIn("read-only", str(ctx.exception).lower())
        self.journal.release_writer_lock()

    def test_observed_digest_mismatch_rejection(self):
        self.journal.acquire_writer_lock()
        bad_digest = "0000000000000000000000000000000000000000000000000000000000000000"
        with self.assertRaises(JournalConflictError) as ctx:
            self.journal.append_journal_entry(
                self.control_id,
                "act_mismatch",
                "Mismatched digest append",
                expected_digest=bad_digest
            )
        self.assertIn("digest", str(ctx.exception).lower())
    def test_conflicting_replay_payload_rejected(self):
        self.journal.acquire_writer_lock()
        _, _, digest1 = self.journal.read_control_record(self.control_id)
        action_id = "act_conflict_test"

        # First append
        res1 = self.journal.append_journal_entry(
            self.control_id,
            action_id,
            "Original payload for action",
            expected_digest=digest1
        )
        self.assertEqual(res1["status"], "applied")

        # Second append with same action_id but DIFFERENT payload must be rejected
        _, _, digest2 = self.journal.read_control_record(self.control_id)
        with self.assertRaises(JournalConflictError) as ctx:
            self.journal.append_journal_entry(
                self.control_id,
                action_id,
                "Conflicting different payload!",
                expected_digest=digest2
            )
        self.assertIn("conflict", str(ctx.exception).lower())
        self.journal.release_writer_lock()

    def test_mandatory_expected_digest(self):
        self.journal.acquire_writer_lock()
        with self.assertRaises(JournalError) as ctx:
            self.journal.append_journal_entry(
                self.control_id,
                "act_no_digest",
                "Payload without digest",
                expected_digest=None
            )
        self.assertIn("expected_digest", str(ctx.exception).lower())
        self.journal.release_writer_lock()

    def test_cas_conflict_stops_without_blind_retry(self):
        self.journal.acquire_writer_lock()
        _, _, digest = self.journal.read_control_record(self.control_id)

        # Mutate the record in the background to advance its updated_at
        subprocess.check_call(
            ["br", "--db", self.db_path, "update", self.control_id, "--append-notes", "External edit", "--no-auto-flush"],
            cwd=self.roadmap_dir,
            stdout=subprocess.DEVNULL
        )

        # Now attempting to append with the old digest should stop on conflict
        with self.assertRaises(JournalConflictError) as ctx:
            self.journal.append_journal_entry(
                self.control_id,
                "act_cas_conflict",
                "Payload that should fail CAS",
                expected_digest=digest
            )
        self.assertIn("conflict", str(ctx.exception).lower())
        self.journal.release_writer_lock()


if __name__ == "__main__":
    unittest.main()
