"""Collector module for dot-portfolio-coordinator.

Deterministic collectors for:
- GitHub REST/GraphQL pagination (issues, draft PRs, checks, terminal changes)
- Native beads all-status collection (`br list --status all --json --limit 0`)
- Cursors committed only on final-page completion
- Stale snapshot preservation on partial/failed collection
- HTTP 304 Not Modified reuse of prior snapshot
"""
import copy
import hashlib
import json
import subprocess
import time
from typing import Any, Callable, Dict, List, Optional, Tuple


class CollectorError(Exception):
    """Raised on collection failure."""
    pass


class PortfolioCollector:
    """Collects snapshots from registered GitHub repositories and Beads stores."""

    def __init__(self, registry: Any):
        self.registry = registry

    def _compute_digest(self, data: Any) -> str:
        s = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(s.encode("utf-8")).hexdigest()

    def _default_beads_fetch(self, source: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Runs native `br list --status all --json --limit 0` against the source's beads store."""
        db_path = source.get("host_binding")
        cmd = ["br", "list", "--status", "all", "--json", "--limit", "0", "--no-auto-flush"]
        if db_path:
            cmd.extend(["--db", db_path])
        try:
            out = subprocess.check_output(cmd, stderr=subprocess.PIPE, text=True, timeout=30)
            return json.loads(out)
        except Exception as e:
            raise CollectorError(f"Failed to fetch beads for {source.get('id')}: {e}")

    def collect_source_snapshot(
        self,
        source_id: str,
        prior_snapshot: Optional[Dict[str, Any]] = None,
        fetch_fn: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """Collects a snapshot for a single source.

        Handles pagination, cursors, 304 reuse, and stale preservation.
        """
        source = self.registry.get_source(source_id)
        if not source:
            raise CollectorError(f"Source {source_id} not registered")

        src_type = source.get("type")
        namespace = source.get("namespace")
        github_host = source.get("github_host", "github.com")
        repo = source.get("repository", "")

        # 1. Beads store collection
        if src_type in ("beads_store", "roadmap_beads"):
            try:
                fn = fetch_fn or self._default_beads_fetch
                raw_items = fn(source)
                items: List[Dict[str, Any]] = []
                for it in raw_items:
                    it_copy = dict(it)
                    bead_id = str(it_copy.get("id", ""))
                    it_copy["task_composite_key"] = self.registry.make_task_composite_key(
                        github_host, repo, namespace, bead_id
                    )
                    items.append(it_copy)

                digest = self._compute_digest(items)
                return {
                    "source_id": source_id,
                    "status": "fresh",
                    "version": digest,
                    "items": items,
                    "cursor": {"last_completed_page": 1, "completed": True},
                    "checkpoint_committed": True,
                    "collected_at": int(time.time()),
                    "error": None
                }
            except Exception as e:
                # If failure, preserve prior snapshot as stale
                if prior_snapshot:
                    stale = copy.deepcopy(prior_snapshot)
                    stale["status"] = "stale"
                    stale["error"] = str(e)
                    stale["checkpoint_committed"] = False
                    return stale
                return {
                    "source_id": source_id,
                    "status": "unavailable",
                    "version": None,
                    "items": [],
                    "cursor": None,
                    "checkpoint_committed": False,
                    "collected_at": int(time.time()),
                    "error": str(e)
                }

        # 2. GitHub repo collection (paginated)
        elif src_type == "github_repo":
            if not fetch_fn:
                # Default fetch would use gh CLI (to be mocked in tests or used in e2e)
                raise CollectorError("Default gh fetch requires fetch_fn or runner")

            prior_etag = prior_snapshot.get("etag") if prior_snapshot else None
            all_items: List[Dict[str, Any]] = []
            page = 1
            last_completed_page = 0
            has_next = True
            latest_etag = None

            try:
                while has_next:
                    resp = fetch_fn(source, page=page, etag=prior_etag)
                    if isinstance(resp, dict) and resp.get("status_code") == 304:
                        # 304 Not Modified: Reuse prior snapshot
                        if prior_snapshot:
                            fresh_304 = copy.deepcopy(prior_snapshot)
                            fresh_304["status"] = "fresh"
                            fresh_304["checkpoint_committed"] = True
                            fresh_304["collected_at"] = int(time.time())
                            return fresh_304
                        else:
                            raise CollectorError("304 received without prior snapshot")

                    page_items = resp.get("items", [])
                    for it in page_items:
                        it_copy = dict(it)
                        bead_id = str(it_copy.get("id", ""))
                        it_copy["task_composite_key"] = self.registry.make_task_composite_key(
                            github_host, repo, namespace, bead_id
                        )
                        all_items.append(it_copy)

                    latest_etag = resp.get("etag", latest_etag)
                    last_completed_page = page
                    has_next = resp.get("has_next", False)
                    if has_next:
                        page = resp.get("next_page", page + 1)

                # Completed all pages successfully
                digest = self._compute_digest(all_items)
                return {
                    "source_id": source_id,
                    "status": "fresh",
                    "version": digest,
                    "etag": latest_etag,
                    "items": all_items,
                    "cursor": {"last_completed_page": last_completed_page, "completed": True},
                    "checkpoint_committed": True,
                    "collected_at": int(time.time()),
                    "error": None
                }
            except Exception as e:
                # Partial failure: do not commit checkpoint, preserve prior or partial items
                if prior_snapshot:
                    stale = copy.deepcopy(prior_snapshot)
                    stale["status"] = "partial" if all_items else "stale"
                    stale["error"] = str(e)
                    stale["cursor"] = {"last_completed_page": last_completed_page, "completed": False}
                    stale["checkpoint_committed"] = False
                    if all_items:
                        stale["items"] = all_items  # retain partial progress
                    return stale
                return {
                    "source_id": source_id,
                    "status": "partial" if all_items else "unavailable",
                    "version": None,
                    "items": all_items,
                    "cursor": {"last_completed_page": last_completed_page, "completed": False},
                    "checkpoint_committed": False,
                    "collected_at": int(time.time()),
                    "error": str(e)
                }

        raise CollectorError(f"Unsupported source type: {src_type}")

    def collect_all(
        self,
        prior_snapshots: Optional[Dict[str, Any]] = None,
        fetch_fn: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """Collects snapshots for all registered sources and aggregates metrics."""
        prior = prior_snapshots or {}
        registered = list(self.registry.sources.values())
        snapshots: Dict[str, Any] = {}

        fresh_count = 0
        stale_count = 0
        unavailable_count = 0
        attempted_count = 0

        for src in registered:
            sid = src["id"]
            attempted_count += 1
            src_prior = prior.get(sid)
            snap = self.collect_source_snapshot(sid, prior_snapshot=src_prior, fetch_fn=fetch_fn)
            snapshots[sid] = snap

            status = snap.get("status")
            if status == "fresh":
                fresh_count += 1
            elif status in ("stale", "partial"):
                stale_count += 1
            elif status == "unavailable":
                unavailable_count += 1

        return {
            "registered_count": len(registered),
            "attempted_count": attempted_count,
            "fresh_count": fresh_count,
            "stale_count": stale_count,
            "unavailable_count": unavailable_count,
            "snapshots": snapshots,
            "collected_at": int(time.time())
        }
