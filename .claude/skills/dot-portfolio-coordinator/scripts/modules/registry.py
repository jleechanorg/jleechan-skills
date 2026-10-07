"""Registry module for dot-portfolio-coordinator.

Enforces:
- Strict schema validation
- Duplicate namespace and source ID rejection
- Host binding resolution
- Audience policy filtering (model, public, internal)
- Org repository gap detection
"""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


class RegistryValidationError(Exception):
    """Raised when registry validation fails."""
    pass


class SourceRegistry:
    """Manages source definitions, composite keys, audience policies, and coverage gaps."""

    def __init__(self, raw_data: Dict[str, Any]):
        self.raw_data = raw_data
        self.sources: Dict[str, Dict[str, Any]] = {}
        self.namespaces: Dict[str, str] = {}  # namespace -> source_id
        self.budget_policy = raw_data.get("budget_policy", {})
        self.endpoint_policy = raw_data.get("endpoint_policy", {})
        self.caller_allowlist = raw_data.get("caller_allowlist", [])
        self._validate_and_index()

    def _validate_and_index(self) -> None:
        if not self.raw_data:
            raise RegistryValidationError("Empty registry data")

        sources_list = self.raw_data.get("sources", [])
        if not isinstance(sources_list, list):
            raise RegistryValidationError("'sources' must be a list")

        for src in sources_list:
            src_id = src.get("id")
            if not src_id:
                raise RegistryValidationError("Source missing 'id'")
            if src_id in self.sources:
                raise RegistryValidationError(f"Duplicate source ID: {src_id}")

            namespace = src.get("namespace")
            if not namespace:
                raise RegistryValidationError(f"Source {src_id} missing 'namespace'")
            if namespace in self.namespaces:
                raise RegistryValidationError(
                    f"Duplicate namespace: '{namespace}' claimed by {self.namespaces[namespace]} and {src_id}"
                )

            # Validate required fields
            for req in ["type", "github_host", "repository", "canonical_tracker", "authority", "audience_policy"]:
                if req not in src:
                    raise RegistryValidationError(f"Source {src_id} missing required field '{req}'")

            self.sources[src_id] = src
            self.namespaces[namespace] = src_id

        # Validate budget policy
        if not self.budget_policy:
            raise RegistryValidationError("Missing budget_policy")
        for req_budget in ["per_cycle_tokens", "per_cycle_cost_usd", "daily_tokens", "daily_cost_usd", "allowed_models"]:
            if req_budget not in self.budget_policy:
                raise RegistryValidationError(f"budget_policy missing required field '{req_budget}'")

    @classmethod
    def from_file(cls, path: str) -> "SourceRegistry":
        p = Path(path)
        if not p.is_file():
            raise FileNotFoundError(f"Registry file not found: {path}")
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(data)

    def get_source(self, source_id: str) -> Optional[Dict[str, Any]]:
        return self.sources.get(source_id)

    def get_source_by_namespace(self, namespace: str) -> Optional[Dict[str, Any]]:
        src_id = self.namespaces.get(namespace)
        if src_id:
            return self.sources.get(src_id)
        return None

    def make_task_composite_key(
        self, github_host: str, repository: str, namespace: str, bead_id: str
    ) -> Tuple[str, str, str, str]:
        """Constructs an immutable task composite key tuple."""
        return (github_host.strip().lower(), repository.strip().lower(), namespace.strip(), bead_id.strip())

    def filter_by_audience(
        self, source_id: str, item_data: Dict[str, Any], destination: str
    ) -> Dict[str, Any]:
        """Filters fields of an item based on the source's audience policy for the destination.

        Destinations: 'model', 'public', 'internal'.
        If a field is not explicitly mapped or does not include the destination, it is omitted.
        """
        src = self.get_source(source_id)
        if not src:
            return {}

        policy = src.get("audience_policy", {})
        filtered: Dict[str, Any] = {}

        for k, v in item_data.items():
            allowed_dests = policy.get(k, [])
            if destination in allowed_dests:
                filtered[k] = v

        return filtered

    def detect_org_gaps(
        self, org: str, discovered_repos: List[str]
    ) -> List[str]:
        """Compares discovered repos against registered repos and returns gaps.

        Never silently expands registration.
        """
        registered_repos: Set[str] = set()
        for src in self.sources.values():
            registered_repos.add(src["repository"].strip().lower())

        gaps: List[str] = []
        for repo in discovered_repos:
            repo_clean = repo.strip().lower()
            if repo_clean.startswith(f"{org.strip().lower()}/") and repo_clean not in registered_repos:
                gaps.append(repo)

        return sorted(gaps)
