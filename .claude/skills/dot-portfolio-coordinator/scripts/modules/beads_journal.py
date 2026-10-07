"""Beads control journal module for dot-portfolio-coordinator.

Implements:
- Sole writer lock on designated host (via fcntl.flock)
- Observed full-record digest computation
- Read-only domain store invariant (only coordinator-control records writable)
- Optimistic concurrency control via `--if-unchanged <updated_at>`
- Atomic note appending via `--append-notes`
- Post-write reread of updated_at and record digest
- Idempotent action recording (retries reuse action ID without duplicating journal entries)
"""
import fcntl
import hashlib
import json
import os
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple


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
    """Manages roadmap Beads control records with sole-writer lock and CAS protocol."""

    def __init__(self, registry: Any, roadmap_store_dir: str, lock_path: Optional[str] = None):
        self.registry = registry
        self.roadmap_store_dir = roadmap_store_dir
        self.lock_path = lock_path or os.path.join(roadmap_store_dir, ".coordinator-writer.lock")
        self._lock_file = None
        self._lock_held = False

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
        cmd = ["br", "show", record_id, "--json", "--no-auto-flush"]
        try:
            out = subprocess.check_output(cmd, cwd=self.roadmap_store_dir, stderr=subprocess.PIPE, text=True)
            record = json.loads(out)
            if isinstance(record, list):
                if not record:
                    raise JournalError(f"Record {record_id} not found")
                record = record[0]
        except subprocess.CalledProcessError as e:
            raise JournalError(f"Failed to read record {record_id}: {e.stderr}")
        except Exception as e:
            raise JournalError(f"Error reading record {record_id}: {e}")

        updated_at = record.get("updated_at", "")
        digest = self._compute_record_digest(record)
        return record, updated_at, digest

    def append_journal_entry(
        self,
        record_id: str,
        action_id: str,
        entry_payload: str,
        expected_digest: Optional[str] = None,
        retry_on_conflict: bool = True
    ) -> Dict[str, Any]:
        """Appends an immutable journal note to a roadmap control record with CAS and idempotence."""
        if not self._lock_held:
            raise JournalError("Sole-writer lock must be held before modifying control records")

        # Read current state
        record, updated_at, current_digest = self.read_control_record(record_id)

        # Invariant: Only records with 'coordinator-control' label are writable
        labels = record.get("labels", [])
        if "coordinator-control" not in labels:
            raise DomainStoreReadOnlyError(
                f"Record {record_id} does not have 'coordinator-control' label. "
                "Domain task stores and non-control records are strictly read-only."
            )

        # Idempotence: Check if action_id already recorded in notes
        action_tag = f"[action_id:{action_id}]"
        notes = record.get("notes") or ""
        if action_tag in notes:
            return {
                "status": "already_applied",
                "action_id": action_id,
                "record_id": record_id,
                "updated_at": updated_at
            }

        # CAS Digest validation
        if expected_digest and expected_digest != current_digest:
            raise JournalConflictError(
                f"Digest mismatch on record {record_id}: expected {expected_digest}, observed {current_digest}"
            )

        # Prepare formatted append line
        now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        note_entry = f"{action_tag} [{now_iso}] {entry_payload.strip()}"

        cmd = [
            "br", "update", record_id,
            "--if-unchanged", updated_at,
            "--append-notes", note_entry,
            "--no-auto-flush",
            "--json"
        ]

        proc = subprocess.run(
            cmd,
            cwd=self.roadmap_store_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if proc.returncode == 6:
            # Timestamp CAS conflict
            if retry_on_conflict:
                # Re-read and retry once
                record_retry, updated_at_retry, _ = self.read_control_record(record_id)
                if action_tag in (record_retry.get("notes") or ""):
                    return {
                        "status": "already_applied",
                        "action_id": action_id,
                        "record_id": record_id,
                        "updated_at": updated_at_retry
                    }
                cmd_retry = [
                    "br", "update", record_id,
                    "--if-unchanged", updated_at_retry,
                    "--append-notes", note_entry,
                    "--no-auto-flush",
                    "--json"
                ]
                proc_retry = subprocess.run(
                    cmd_retry,
                    cwd=self.roadmap_store_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                if proc_retry.returncode != 0:
                    raise JournalConflictError(
                        f"Conflict retry failed on record {record_id}: {proc_retry.stderr}"
                    )
            else:
                raise JournalConflictError(f"CAS conflict on record {record_id} (exit 6): {proc.stderr}")
        elif proc.returncode != 0:
            raise JournalError(f"Failed to update record {record_id}: {proc.stderr}")

        # Post-write reread to verify mutation and obtain fresh updated_at
        fresh_record, new_updated_at, new_digest = self.read_control_record(record_id)
        if action_tag not in (fresh_record.get("notes") or ""):
            raise JournalError(f"Post-write reread failed: {action_tag} not found in notes")

        return {
            "status": "applied",
            "action_id": action_id,
            "record_id": record_id,
            "new_updated_at": new_updated_at,
            "new_digest": new_digest
        }
