"""Model admission module for dot-portfolio-coordinator.

Enforces:
- Model admission ALWAYS returns capability_blocked unless a genuine independently
  enforced isolation adapter actually exists. Caller JSON booleans never establish admission.
- Strict minimization from scratch based on reviewed audience policy.
- Zero re-injection of denied private identities, notes, or raw metadata.
"""
from typing import Any, Dict, List, Optional


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
        sources = snapshot.get("sources", {})

        for sid, sdata in sources.items():
            filtered_items = []
            for item in sdata.get("items", []):
                # Audience policy filtering for 'model' built from scratch
                f = self.registry.filter_by_audience(sid, item, "model")
                if f:
                    filtered_items.append(f)

            minimized["sources"][sid] = {
                "source_id": sid,
                "version": sdata.get("version"),
                "items": filtered_items
            }

        return minimized
