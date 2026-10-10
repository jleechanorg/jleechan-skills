"""Registry module for dot-portfolio-coordinator.

Enforces:
- Strict schema validation (rejects unknown root and source fields)
- Strict types, enums, and finite numeric limits (rejects NaN, boolean, negative)
- Observe-only support without invented model/budget defaults
- Unknown canonical_tracker intake support
- Optional registered owner (with explicit unknown support)
- Structural repository and endpoint validation
- Duplicate namespace and source ID rejection
- Host binding resolution
- Audience policy filtering (model, public, internal)
- Org repository gap detection without automatic access expansion
"""
import json
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


class RegistryValidationError(Exception):
    """Raised when registry validation fails."""
    pass


ALLOWED_ROOT_KEYS = {
    "version",
    "sources",
    "budget_policy",
    "endpoint_policy",
    "caller_allowlist",
    "host_binding",
    "designated_host"
}

ALLOWED_SOURCE_KEYS = {
    "id",
    "namespace",
    "type",
    "github_host",
    "repository",
    "canonical_tracker",
    "authority",
    "host_binding",
    "freshness_budget_secs",
    "collection_mode",
    "audience_policy",
    "owner"
}

VALID_SOURCE_TYPES = {"github_repo", "beads_store", "roadmap_beads"}
VALID_CANONICAL_TRACKERS = {"beads", "github_issues", "unknown"}
VALID_AUTHORITIES = {"read_only", "authoritative_control"}
VALID_COLLECTION_MODES = {"full_census", "incremental"}
VALID_AUDIENCE_DESTS = {"model", "public", "internal"}

REPO_REGEX = re.compile(r"^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$")


class SourceRegistry:
    """Manages source definitions, composite keys, audience policies, and coverage gaps."""

    def __init__(self, raw_data: Dict[str, Any]):
        self.raw_data = raw_data
        self.sources: Dict[str, Dict[str, Any]] = {}
        self.namespaces: Dict[str, str] = {}  # namespace -> source_id
        self.budget_policy: Dict[str, Any] = {}
        self.endpoint_policy: Dict[str, Any] = {}
        self.caller_allowlist: List[str] = []
        self.designated_host: Optional[str] = None
        self._validate_and_index()

    @property
    def is_observe_only(self) -> bool:
        """Returns True if budget policy is omitted, meaning model usage is not configured."""
        return not bool(self.budget_policy)

    def _validate_numeric(self, val: Any, name: str, is_int: bool = False, min_val: float = 0.0) -> None:
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            raise RegistryValidationError(f"Field '{name}' must be numeric (got {type(val).__name__})")
        if math.isnan(val) or math.isinf(val):
            raise RegistryValidationError(f"Field '{name}' must be finite (got {val})")
        if val < min_val:
            raise RegistryValidationError(f"Field '{name}' must be >= {min_val} (got {val})")
        if is_int and not isinstance(val, int):
            raise RegistryValidationError(f"Field '{name}' must be an integer (got {val})")

    def _validate_and_index(self) -> None:
        if not isinstance(self.raw_data, dict) or not self.raw_data:
            raise RegistryValidationError("Empty or invalid registry data (must be a JSON object)")

        # 1. Reject unknown root keys
        unknown_root = set(self.raw_data.keys()) - ALLOWED_ROOT_KEYS
        if unknown_root:
            raise RegistryValidationError(f"Unknown root field(s) in registry: {sorted(unknown_root)}")

        version = self.raw_data.get("version")
        if not isinstance(version, str) or not version.strip():
            raise RegistryValidationError("Registry missing valid 'version' string")

        self.designated_host = self.raw_data.get("designated_host")
        if self.designated_host is not None and not isinstance(self.designated_host, str):
            raise RegistryValidationError("'designated_host' must be a string")

        sources_list = self.raw_data.get("sources", [])
        if not isinstance(sources_list, list):
            raise RegistryValidationError("'sources' must be a list")

        # 2. Validate sources
        for src in sources_list:
            if not isinstance(src, dict):
                raise RegistryValidationError("Each source item must be a JSON object")

            unknown_src = set(src.keys()) - ALLOWED_SOURCE_KEYS
            if unknown_src:
                raise RegistryValidationError(f"Unknown source field(s) detected: {sorted(unknown_src)}")

            src_id = src.get("id")
            if not isinstance(src_id, str) or not src_id.strip():
                raise RegistryValidationError("Source missing valid 'id'")
            if src_id in self.sources:
                raise RegistryValidationError(f"Duplicate source ID: {src_id}")

            namespace = src.get("namespace")
            if not isinstance(namespace, str) or not namespace.strip():
                raise RegistryValidationError(f"Source {src_id} missing valid 'namespace'")
            if namespace in self.namespaces:
                raise RegistryValidationError(
                    f"Duplicate namespace: '{namespace}' claimed by {self.namespaces[namespace]} and {src_id}"
                )

            src_type = src.get("type")
            if src_type not in VALID_SOURCE_TYPES:
                raise RegistryValidationError(f"Source {src_id} has invalid type '{src_type}'")

            github_host = src.get("github_host")
            if not isinstance(github_host, str) or not github_host.strip():
                raise RegistryValidationError(f"Source {src_id} missing valid 'github_host'")

            repo = src.get("repository")
            if not isinstance(repo, str) or not REPO_REGEX.match(repo.strip()):
                raise RegistryValidationError(
                    f"Source {src_id} repository '{repo}' must follow 'owner/repo' format"
                )

            tracker = src.get("canonical_tracker")
            if tracker not in VALID_CANONICAL_TRACKERS:
                raise RegistryValidationError(
                    f"Source {src_id} invalid canonical_tracker '{tracker}'. Expected {VALID_CANONICAL_TRACKERS}"
                )

            auth = src.get("authority")
            if auth not in VALID_AUTHORITIES:
                raise RegistryValidationError(
                    f"Source {src_id} invalid authority '{auth}'. Expected {VALID_AUTHORITIES}"
                )

            if "owner" in src and not isinstance(src["owner"], str):
                raise RegistryValidationError(f"Source {src_id} 'owner' must be a string")

            if "host_binding" in src and not isinstance(src["host_binding"], str):
                raise RegistryValidationError(f"Source {src_id} 'host_binding' must be a string")

            if "freshness_budget_secs" in src:
                self._validate_numeric(
                    src["freshness_budget_secs"],
                    f"sources[{src_id}].freshness_budget_secs",
                    is_int=True,
                    min_val=0
                )

            if "collection_mode" in src and src["collection_mode"] not in VALID_COLLECTION_MODES:
                raise RegistryValidationError(f"Source {src_id} invalid collection_mode '{src['collection_mode']}'")

            policy = src.get("audience_policy")
            if not isinstance(policy, dict):
                raise RegistryValidationError(f"Source {src_id} missing valid 'audience_policy' dict")
            for field_name, dests in policy.items():
                if not isinstance(dests, list):
                    raise RegistryValidationError(f"Audience policy for '{field_name}' must be a list")
                for dest in dests:
                    if dest not in VALID_AUDIENCE_DESTS:
                        raise RegistryValidationError(
                            f"Audience policy destination '{dest}' invalid. Expected {VALID_AUDIENCE_DESTS}"
                        )

            self.sources[src_id] = src
            self.namespaces[namespace] = src_id

        # 3. Validate budget policy if present (observe-only allows omission)
        if "budget_policy" in self.raw_data:
            bp = self.raw_data["budget_policy"]
            if not isinstance(bp, dict):
                raise RegistryValidationError("'budget_policy' must be a dict")
            for req_b in ["per_cycle_tokens", "per_cycle_cost_usd", "daily_tokens", "daily_cost_usd", "allowed_models"]:
                if req_b not in bp:
                    raise RegistryValidationError(f"budget_policy missing required field '{req_b}'")
            self._validate_numeric(bp["per_cycle_tokens"], "budget_policy.per_cycle_tokens", is_int=True, min_val=1)
            self._validate_numeric(bp["per_cycle_cost_usd"], "budget_policy.per_cycle_cost_usd", min_val=0.0)
            self._validate_numeric(bp["daily_tokens"], "budget_policy.daily_tokens", is_int=True, min_val=1)
            self._validate_numeric(bp["daily_cost_usd"], "budget_policy.daily_cost_usd", min_val=0.0)
            if not isinstance(bp["allowed_models"], list) or not bp["allowed_models"]:
                raise RegistryValidationError("budget_policy.allowed_models must be a non-empty list of strings")
            self.budget_policy = bp

        # 4. Validate endpoint policy if present
        if "endpoint_policy" in self.raw_data:
            ep = self.raw_data["endpoint_policy"]
            if not isinstance(ep, dict):
                raise RegistryValidationError("'endpoint_policy' must be a dict")
            provider = ep.get("provider")
            if not isinstance(provider, str) or not provider.strip():
                raise RegistryValidationError("endpoint_policy missing valid 'provider'")
            endpoints = ep.get("allowed_endpoints", [])
            if not isinstance(endpoints, list):
                raise RegistryValidationError("endpoint_policy.allowed_endpoints must be a list")
            for u in endpoints:
                if not isinstance(u, str) or not u.startswith("https://") or "*" in u:
                    raise RegistryValidationError(f"Invalid endpoint URI '{u}'. Must start with https:// and no wildcards.")
            self.endpoint_policy = ep

        # 5. Validate caller allowlist if present
        if "caller_allowlist" in self.raw_data:
            ca = self.raw_data["caller_allowlist"]
            if not isinstance(ca, list):
                raise RegistryValidationError("'caller_allowlist' must be a list")
            self.caller_allowlist = ca

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
        Builds approved allowlist from scratch. Unknown or broader access excludes the field.
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
