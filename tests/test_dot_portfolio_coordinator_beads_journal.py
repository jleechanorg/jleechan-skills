import json
import os
import subprocess
import tempfile
import unittest
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


class TestDotPortfolioCoordinatorBeadsJournal(unittest.TestCase):
    def setUp(self):
        self.sources_json_path = SKILL_DIR / "references" / "sources.json"
        self.registry = SourceRegistry.from_file(str(self.sources_json_path))

        # Create isolated temporary directory for real br store
        self.temp_dir = tempfile.TemporaryDirectory()
        self.roadmap_dir = os.path.join(self.temp_dir.name, "roadmap")
        os.makedirs(self.roadmap_dir, exist_ok=True)

        # Initialize real br store inside self.roadmap_dir
        subprocess.check_call(
            ["br", "init", "--prefix", "bd", "--no-auto-flush", "--json"],
            cwd=self.roadmap_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        # Create a valid coordinator-control record
        res = subprocess.check_output(
            ["br", "create", "Roadmap Control Record", "--labels", "coordinator-control", "--no-auto-flush", "--json"],
            cwd=self.roadmap_dir,
            text=True
        )
        self.control_issue = json.loads(res)
        self.control_id = self.control_issue["id"]

        # Create a non-control domain record (without coordinator-control label)
        res_domain = subprocess.check_output(
            ["br", "create", "Domain Task Without Label", "--no-auto-flush", "--json"],
            cwd=self.roadmap_dir,
            text=True
        )
        self.domain_issue = json.loads(res_domain)
        self.domain_id = self.domain_issue["id"]

        self.lock_path = os.path.join(self.temp_dir.name, "writer.lock")
        self.journal = BeadsControlJournal(self.registry, self.roadmap_dir, self.lock_path)

    def tearDown(self):
        self.temp_dir.cleanup()

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
            ["br", "update", self.control_id, "--append-notes", "External edit", "--no-auto-flush"],
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
