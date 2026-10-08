"""Beads control journal module for dot-portfolio-coordinator.

Implements:
- Sole writer lock on designated host (via fcntl.flock in private /tmp)
- Registry store authority enforcement (mutations permitted only on authoritative_control store)
- Mandatory observed full-record digest and timestamp CAS
- Zero blind-retries on CAS exit 6 (stops immediately on conflict)
- Conflicting action payload replay rejection (binds payload hash to action_id)
- Post-write reread of full record, notes, and new digest
- Explicit DB binding and --no-auto-import on all br invocations
"""
import fcntl
import hashlib
import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from modules.process_utils import run_bounded_command, ProcessExecutionError


class JournalError(Exception):
    """Base journal error."""
    pass


class JournalConflictError(JournalError):
    """Raised on CAS timestamp or digest conflict."""
    pass


class DomainStoreReadOnlyError(JournalError):
    """Raised when attempting to mutate a read-only domain store."""
    pass


class BeadsControlJournal:
    """Manages roadmap Beads control records with sole-writer lock and strict CAS protocol."""

    def __init__(self, registry: Any, roadmap_store_dir: str, lock_path: Optional[str] = None):
        self.registry = registry
        self.roadmap_store_dir = roadmap_store_dir
        self.lock_path = lock_path or "/tmp/ai.gemini.dot-portfolio-coordinator-writer.lock"
        self._lock_file = None
        self._lock_held = False
        self._db_path = self._resolve_db_path()

    def _resolve_db_path(self) -> str:
        """Require an exact registered authoritative roadmap database; never fall back."""
        candidate = os.path.realpath(os.path.join(self.roadmap_store_dir, ".beads", "beads.db"))
        matches = [
            source for source in self.registry.sources.values()
            if isinstance(source.get("host_binding"), str)
            and os.path.isabs(source["host_binding"])
            and os.path.realpath(source["host_binding"]) == candidate
        ]
        if (not os.path.isfile(candidate) or len(matches) != 1
                or matches[0].get("type") != "roadmap_beads"
                or matches[0].get("canonical_tracker") != "beads"
                or matches[0].get("authority") != "authoritative_control"):
            raise DomainStoreReadOnlyError(
                "Journal requires one exact authoritative_control roadmap DB binding; store is read-only"
            )
        return candidate

    def _verify_db_binding(self) -> None:
        db_path = self._resolve_db_path()
        if db_path != self._db_path:
            raise JournalError("Journal database binding changed")
        cmd = ["br", "where", "--json", "--db", db_path, "--no-auto-flush", "--no-auto-import"]
        try:
            rc, stdout, _ = run_bounded_command(cmd, cwd=self.roadmap_store_dir, timeout_secs=15)
            resolved = json.loads(stdout) if rc == 0 else None
            resolved_db = resolved.get("database_path") if isinstance(resolved, dict) else None
            if not isinstance(resolved_db, str) or os.path.realpath(resolved_db) != db_path:
                raise JournalError("br resolved a different journal database")
        except (ValueError, ProcessExecutionError) as exc:
            raise JournalError("Unable to verify journal database binding") from exc

    def acquire_writer_lock(self, blocking: bool = False) -> None:
        """Acquires exclusive sole-writer lock on the lockfile."""
        if self._lock_held:
            return
        os.makedirs(os.path.dirname(os.path.abspath(self.lock_path)), exist_ok=True)
        self._lock_file = open(self.lock_path, "a+")
        flags = fcntl.LOCK_EX
        if not blocking:
            flags |= fcntl.LOCK_NB
        try:
            fcntl.flock(self._lock_file.fileno(), flags)
            self._lock_held = True
        except (IOError, OSError) as e:
            if self._lock_file:
                self._lock_file.close()
                self._lock_file = None
            raise JournalError(f"Failed to acquire sole writer lock on {self.lock_path}: {e}")

    def release_writer_lock(self) -> None:
        """Releases the sole-writer lock."""
        if not self._lock_held or not self._lock_file:
            return
        try:
            fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_UN)
            self._lock_file.close()
        finally:
            self._lock_file = None
            self._lock_held = False

    def _compute_record_digest(self, record: Dict[str, Any]) -> str:
        """Computes deterministic digest of the full record content."""
        canonical_str = json.dumps(record, sort_keys=True, default=str)
        return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()

    def read_control_record(self, record_id: str) -> Tuple[Dict[str, Any], str, str]:
        """Reads a record from the roadmap store.

        Returns (record_dict, updated_at, full_record_digest).
        """
        self._verify_db_binding()
        cmd = ["br", "show", record_id, "--json", "--no-auto-flush", "--no-auto-import"]
        cmd.extend(["--db", self._db_path])
        try:
            rc, stdout, stderr = run_bounded_command(cmd, cwd=self.roadmap_store_dir, timeout_secs=15)
            if rc != 0:
                raise JournalError(f"Failed to read record {record_id}: {stderr}")
            record = json.loads(stdout)
            if isinstance(record, list):
                if not record:
                    raise JournalError(f"Record {record_id} not found")
                record = record[0]
        except Exception as e:
            raise JournalError(f"Error reading record {record_id}: {e}")

        updated_at = record.get("updated_at", "")
        digest = self._compute_record_digest(record)
        return record, updated_at, digest

    @staticmethod
    def _entry_matches(notes: str, action_tag: str, payload_tag: str) -> bool:
        # Tags must belong to one leading journal header, never unrelated notes.
        entries = [line.split(" ", 2) for line in notes.splitlines()
                   if line.startswith(action_tag + " ")]
        return bool(entries) and all(len(parts) == 3 and parts[1] == payload_tag
                                     for parts in entries)

    def append_journal_entry(
        self,
        record_id: str,
        action_id: str,
        entry_payload: str,
        expected_digest: Optional[str] = None
    ) -> Dict[str, Any]:
        """Appends an immutable journal note to a roadmap control record with CAS and payload binding."""
        if not self._lock_held:
            raise JournalError("Sole-writer lock must be held before modifying control records")

        if not expected_digest or not str(expected_digest).strip():
            raise JournalError("expected_digest is mandatory for CAS control journal updates")

        # Read current state
        record, updated_at, current_digest = self.read_control_record(record_id)

        # Invariant: Only records with 'coordinator-control' label are writable
        labels = record.get("labels", [])
        if "coordinator-control" not in labels:
            raise DomainStoreReadOnlyError(
                f"Record {record_id} does not have 'coordinator-control' label. "
                "Domain task stores and non-control records are strictly read-only."
            )

        # Compute payload hash
        payload_sha = hashlib.sha256(entry_payload.strip().encode("utf-8")).hexdigest()
        action_tag = f"[action_id:{action_id}]"
        payload_tag = f"[payload_sha256:{payload_sha}]"

        notes = record.get("notes") or ""
        if action_tag in notes:
            # Check for conflicting payload replay
            if self._entry_matches(notes, action_tag, payload_tag):
                return {
                    "status": "already_applied",
                    "action_id": action_id,
                    "record_id": record_id,
                    "updated_at": updated_at
                }
            raise JournalConflictError(
                f"Conflicting replay detected for action_id '{action_id}' on record {record_id}: "
                "action_id already exists with different payload digest."
            )

        # CAS Digest validation
        if expected_digest != current_digest:
            raise JournalConflictError(
                f"CAS conflict: digest mismatch on record {record_id}: expected {expected_digest}, observed {current_digest}"
            )

        # Prepare formatted append line
        now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        # Encode payload line breaks so text cannot introduce another entry header.
        note_entry = f"{action_tag} {payload_tag} [{now_iso}] {json.dumps(entry_payload.strip())}"

        cmd = [
            "br", "update", record_id,
            "--if-unchanged", updated_at,
            "--append-notes", note_entry,
            "--no-auto-flush",
            "--no-auto-import",
            "--json"
        ]
        cmd.extend(["--db", self._db_path])

        self._verify_db_binding()
        rc, stdout, stderr = run_bounded_command(cmd, cwd=self.roadmap_store_dir, timeout_secs=15)

        if rc == 6:
            # Stop immediately on CAS timestamp conflict: NO blind retry
            raise JournalConflictError(
                f"CAS conflict: timestamp changed on record {record_id} (br update exit 6): {stderr}"
            )
        elif rc != 0:
            raise JournalError(f"Failed to update record {record_id}: {stderr}")

        # Post-write reread to verify mutation and obtain fresh updated_at and digest
        fresh_record, new_updated_at, new_digest = self.read_control_record(record_id)
        fresh_notes = fresh_record.get("notes") or ""
        if not self._entry_matches(fresh_notes, action_tag, payload_tag):
            raise JournalError(
                f"Post-write reread verification failed: {action_tag} or {payload_tag} missing in record notes"
            )

        return {
            "status": "applied",
            "action_id": action_id,
            "record_id": record_id,
            "new_updated_at": new_updated_at,
            "new_digest": new_digest
        }
