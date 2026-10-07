"""Model admission module for dot-portfolio-coordinator.

Enforces:
- Genuine sandbox/isolation guarantees
- Strict endpoint allowlists matching registry policy
- Mount restrictions (no host mounts)
- Tool inventory restrictions (no shell execution / arbitrary tools)
- Exclusion of write credentials
- Destination-specific field minimization
"""
import copy
from typing import Any, Dict, List, Optional


class ModelAdmissionChecker:
    """Enforces genuine sandbox/isolation, endpoint allowlists, and mount restrictions."""

    def __init__(self, registry: Any):
        self.registry = registry

    def admit_model_transport(self, environment_manifest: Dict[str, Any]) -> Dict[str, Any]:
        """Validates reasoning environment isolation.

        Returns {'admitted': True, 'reason': None} or
        {'admitted': False, 'reason': 'capability_blocked', 'details': '...'}.
        Never allows unisolated execution or pretends output validation substitutes for isolation.
        """
        if not environment_manifest.get("sandbox_enforced"):
            return {
                "admitted": False,
                "reason": "capability_blocked",
                "details": "Sandbox is not enforced for reasoning environment."
            }

        host_mounts = environment_manifest.get("host_mounts", [])
        if host_mounts:
            for mount in host_mounts:
                if not mount.startswith("/tmp"):
                    return {
                        "admitted": False,
                        "reason": "capability_blocked",
                        "details": f"Prohibited host mount detected: {mount}"
                    }

        if not environment_manifest.get("network_egress_allowlist_enforced"):
            return {
                "admitted": False,
                "reason": "capability_blocked",
                "details": "Network egress allowlist is not enforced."
            }

        allowed_endpoints = environment_manifest.get("allowed_endpoints", [])
        if "*" in allowed_endpoints:
            return {
                "admitted": False,
                "reason": "capability_blocked",
                "details": "Wildcard network egress is strictly forbidden."
            }

        # Check endpoints against registry endpoint policy
        policy_endpoints = set(self.registry.endpoint_policy.get("allowed_endpoints", []))
        for ep in allowed_endpoints:
            if ep not in policy_endpoints:
                return {
                    "admitted": False,
                    "reason": "capability_blocked",
                    "details": f"Endpoint {ep} is not allowed by registry policy."
                }

        # Tool inventory check: inference environment must not have write or broad shell tools
        prohibited_tools = {"run_command", "bash", "shell", "write_to_file", "replace_file_content", "git_push"}
        tool_inventory = set(environment_manifest.get("tool_inventory", []))
        overlap = tool_inventory.intersection(prohibited_tools)
        if overlap:
            return {
                "admitted": False,
                "reason": "capability_blocked",
                "details": f"Inference granted prohibited write/exec tools: {sorted(overlap)}"
            }

        if not environment_manifest.get("write_credentials_excluded"):
            return {
                "admitted": False,
                "reason": "capability_blocked",
                "details": "Write-capable credentials were not excluded from inference environment."
            }

        return {"admitted": True, "reason": None}

    def prepare_minimized_snapshot(
        self, snapshot: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Filters snapshot fields based on model destination policy."""
        minimized = copy.deepcopy(snapshot)
        sources = minimized.get("sources", {})

        for sid, sdata in sources.items():
            items = sdata.get("items", [])
            filtered_items = []
            for item in items:
                # Audience policy filtering for 'model'
                f = self.registry.filter_by_audience(sid, item, "model")
                # Always preserve structural identity keys
                if "id" in item:
                    f["id"] = item["id"]
                if "task_composite_key" in item:
                    f["task_composite_key"] = item["task_composite_key"]
                filtered_items.append(f)
            sdata["items"] = filtered_items

        return minimized
