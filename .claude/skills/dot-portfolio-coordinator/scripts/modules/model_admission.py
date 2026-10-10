"""Model admission module for dot-portfolio-coordinator.

Enforces:
- Model admission ALWAYS returns capability_blocked unless a genuine independently
  enforced isolation adapter actually exists. Caller JSON booleans never establish admission.
- Strict minimization from scratch based on reviewed audience policy.
- Zero re-injection of denied private identities, notes, or raw metadata.
"""
from typing import Any, Dict, List, Optional

from modules.collector import DIAGNOSTIC_CODES


COLLECTION_COVERAGE_FIELDS = (
    "registered_count",
    "fresh_count",
    "stale_count",
    "unavailable_count",
)
COLLECTION_STATUSES = {"fresh", "partial", "stale", "unavailable"}
SOURCE_TIMESTAMP_FIELDS = ("collected_at", "validated_at", "attempted_at")


class ModelAdmissionChecker:
    """Enforces genuine sandbox/isolation and audience-based snapshot minimization."""

    def __init__(self, registry: Any):
        self.registry = registry

    def admit_model_transport(self, environment_manifest: Dict[str, Any]) -> Dict[str, Any]:
        """Validates reasoning environment isolation.

        INVARIANT: Unverified caller JSON booleans never establish actual isolation.
        Absent a genuine independently verified isolation adapter, model execution
        is always capability_blocked.
        """
        # Always capability_blocked absent genuine isolation adapter
        return {
            "admitted": False,
            "reason": "capability_blocked",
            "details": (
                "No genuine independently enforced isolation adapter available. "
                "Caller JSON booleans cannot establish runtime isolation."
            )
        }

    def prepare_minimized_snapshot(
        self, snapshot: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Builds minimized snapshot from scratch using reviewed audience policy for destination 'model'.

        Never reinjects fields denied by audience policy.
        """
        minimized: Dict[str, Any] = {
            "snapshot_id": snapshot.get("snapshot_id"),
            "sources": {}
        }
        collected_at = snapshot.get("collected_at")
        if isinstance(collected_at, int) and not isinstance(collected_at, bool):
            minimized["collected_at"] = collected_at

        coverage = snapshot.get("coverage")
        if isinstance(coverage, dict):
            safe_coverage = {
                field: value
                for field in COLLECTION_COVERAGE_FIELDS
                if isinstance((value := coverage.get(field)), int)
                and not isinstance(value, bool)
                and value >= 0
            }
            if safe_coverage:
                minimized["coverage"] = safe_coverage

        sources = snapshot.get("sources", {})

        for sid, sdata in sources.items():
            filtered_items = []
            for item in sdata.get("items", []):
                # Audience policy filtering for 'model' built from scratch
                f = self.registry.filter_by_audience(sid, item, "model")
                if f:
                    filtered_items.append(f)

            minimized_source = {
                "source_id": sid,
                "items": filtered_items
            }
            version = sdata.get("version")
            if version is None or isinstance(version, str):
                minimized_source["version"] = version
            status = sdata.get("status")
            if isinstance(status, str) and status in COLLECTION_STATUSES:
                minimized_source["status"] = status
            for field in SOURCE_TIMESTAMP_FIELDS:
                value = sdata.get(field)
                if isinstance(value, int) and not isinstance(value, bool):
                    minimized_source[field] = value

            checkpoint_committed = sdata.get("checkpoint_committed")
            if isinstance(checkpoint_committed, bool):
                minimized_source["checkpoint_committed"] = checkpoint_committed

            cursor = sdata.get("cursor")
            if isinstance(cursor, dict):
                safe_cursor = {}
                last_completed_page = cursor.get("last_completed_page")
                if (
                    isinstance(last_completed_page, int)
                    and not isinstance(last_completed_page, bool)
                    and last_completed_page >= 0
                ):
                    safe_cursor["last_completed_page"] = last_completed_page
                completed = cursor.get("completed")
                if isinstance(completed, bool):
                    safe_cursor["completed"] = completed
                if safe_cursor:
                    minimized_source["cursor"] = safe_cursor

            if "error_code" in sdata:
                error_code = sdata["error_code"]
                if (
                    error_code is None
                    or (
                        isinstance(error_code, str)
                        and error_code in DIAGNOSTIC_CODES
                    )
                ):
                    minimized_source["error_code"] = error_code

            minimized["sources"][sid] = minimized_source

        return minimized
