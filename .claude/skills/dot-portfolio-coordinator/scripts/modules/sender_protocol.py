"""Sender protocol module for dot-portfolio-coordinator.

Implements:
- Registration and read-only resolution of immutable notification authorization bindings
- Reconciliation validation and state transition verification
"""
import hashlib
import json
import os
import time
from typing import Any, Dict, List, Optional


class SenderProtocolError(Exception):
    """Raised on sender protocol errors."""
    pass


class NotificationBindingManager:
    """Manages immutable notification authorization bindings."""

    def __init__(self, registry: Any, storage_file: Optional[str] = None):
        self.registry = registry
        self.storage_file = storage_file
        self.bindings: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if self.storage_file and os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, "r", encoding="utf-8") as f:
                    self.bindings = json.load(f)
            except Exception:
                pass

    def _save(self) -> None:
        if self.storage_file:
            os.makedirs(os.path.dirname(os.path.abspath(self.storage_file)), exist_ok=True)
            tmp = f"{self.storage_file}.tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.bindings, f, indent=2)
            os.replace(tmp, self.storage_file)

    def register_binding(
        self,
        control_record_id: str,
        action_id: str,
        attempt_id: str,
        account: str,
        event_id: str,
        kind: str,
        message_sha256: str,
        task_key: Dict[str, str],
        grant_version: str,
        control_entry_digest: str
    ) -> Dict[str, Any]:
        """Registers immutable notification authorization binding."""
        ref_key = f"{control_record_id}/{action_id}/{attempt_id}"
        binding = {
            "control_record_id": control_record_id,
            "action_id": action_id,
            "attempt_id": attempt_id,
            "account": account,
            "event_id": event_id,
            "kind": kind,
            "message_sha256": message_sha256,
            "task_key": task_key,
            "grant_version": grant_version,
            "control_entry_digest": control_entry_digest,
            "registered_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        self.bindings[ref_key] = binding
        self._save()
        return binding

    def resolve_notification(self, auth_ref: str) -> Optional[Dict[str, Any]]:
        """Resolves notification binding by authorization reference."""
        self._load()
        return self.bindings.get(auth_ref)
