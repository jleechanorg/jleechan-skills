"""Sender protocol module for dot-portfolio-coordinator.

Implements:
- Registration and read-only resolution of immutable notification authorization bindings
- Reconciliation validation and state transition verification
"""
import copy
import hashlib
import json
import os
import time
from typing import Any, Dict, List, Optional


class SenderProtocolError(Exception):
    """Raised on sender protocol errors."""
    pass


class NotificationBindingManager:
    """Validates/reloads bindings; overlapping writers still require external serialization."""

    def __init__(self, registry: Any, storage_file: Optional[str] = None):
        self.registry = registry
        self.storage_file = storage_file
        self.bindings: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if not self.storage_file:
            return
        try:
            with open(self.storage_file, "r", encoding="utf-8") as f:
                bindings = json.load(f)
            if not isinstance(bindings, dict):
                raise ValueError("invalid binding store")
            for ref, binding in bindings.items():
                fields = ("control_record_id", "action_id", "attempt_id", "account", "event_id",
                          "kind", "message_sha256", "grant_version", "control_entry_digest", "registered_at")
                if not isinstance(binding, dict) or any(
                        not isinstance(binding.get(field), str) or not binding[field] for field in fields):
                    raise ValueError("invalid binding")
                expected_ref = "/".join(binding[field] for field in fields[:3])
                if ref != expected_ref or not isinstance(binding.get("task_key"), dict):
                    raise ValueError("invalid binding identity")
                if any(not isinstance(k, str) or not isinstance(v, str)
                       for k, v in binding["task_key"].items()):
                    raise ValueError("invalid task key")
                for field in ("message_sha256", "control_entry_digest"):
                    digest = binding[field]
                    if len(digest) != 64 or any(c not in "0123456789abcdefABCDEF" for c in digest):
                        raise ValueError("invalid binding digest")
        except FileNotFoundError as exc:
            if self.bindings:
                raise SenderProtocolError("Persisted notification bindings disappeared") from exc
            return
        except (OSError, ValueError, TypeError) as exc:
            raise SenderProtocolError("Invalid or unreadable persisted notification bindings") from exc
        self.bindings = bindings

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
        self._load()
        ref_key = f"{control_record_id}/{action_id}/{attempt_id}"
        binding = {
            "control_record_id": control_record_id,
            "action_id": action_id,
            "attempt_id": attempt_id,
            "account": account,
            "event_id": event_id,
            "kind": kind,
            "message_sha256": message_sha256,
            "task_key": copy.deepcopy(task_key),
            "grant_version": grant_version,
            "control_entry_digest": control_entry_digest
        }
        existing = self.bindings.get(ref_key)
        if existing is not None:
            immutable = {key: value for key, value in existing.items() if key != "registered_at"}
            if immutable != binding:
                raise SenderProtocolError("Notification binding is immutable")
            return copy.deepcopy(existing)
        binding["registered_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.bindings[ref_key] = binding
        self._save()
        return copy.deepcopy(binding)

    def resolve_notification(self, auth_ref: str) -> Optional[Dict[str, Any]]:
        """Resolves notification binding by authorization reference."""
        self._load()
        return copy.deepcopy(self.bindings.get(auth_ref))
