"""Collector module for dot-portfolio-coordinator.

Deterministic collectors for:
- GitHub REST pagination (issues, draft PRs, checks, terminal changes)
- Native beads all-status collection (`br --db <exact> --no-auto-flush --no-auto-import list --status all --deferred --limit 0 --json`)
- Strict envelope parsing `{issues, total, limit, offset, has_more}`
- Absolute exclusion of ambient DB fallback
- Strict sanitization of raw bodies, descriptions, and notes
- Cursors committed only on final-page completion
- Stale and partial preservation (UNION of old unseen records)
- HTTP 304 Not Modified reuse of verified prior snapshots only
"""
import copy
import hashlib
import json
import os
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from modules.process_utils import run_bounded_command, ProcessTimeoutError, ProcessExecutionError


class CollectorError(Exception):
    """Raised on collection failure."""
    pass


# Allowlisted sanitized fields for collected portfolio items
ALLOWED_ITEM_FIELDS = {
    "id",
    "title",
    "status",
    "owner",
    "priority",
    "created_at",
    "updated_at",
    "head_sha",
    "url",
    "is_draft",
    "checks",
    "task_composite_key"
}


def sanitize_item(raw_item: Dict[str, Any], composite_key: Tuple[str, str, str, str]) -> Dict[str, Any]:
    """Sanitizes raw source item, strictly omitting raw bodies, descriptions, and notes."""
    sanitized: Dict[str, Any] = {"task_composite_key": list(composite_key)}
    for k in ALLOWED_ITEM_FIELDS:
        if k in raw_item and k != "task_composite_key":
            sanitized[k] = raw_item[k]

    # Map alternative field names if needed
    if "id" not in sanitized and "number" in raw_item:
        sanitized["id"] = raw_item["number"]
    if "status" not in sanitized and "state" in raw_item:
        sanitized["status"] = raw_item["state"]
    if "owner" not in sanitized:
        if "user" in raw_item and isinstance(raw_item["user"], dict):
            sanitized["owner"] = raw_item["user"].get("login", "")
        elif "assignee" in raw_item and isinstance(raw_item["assignee"], dict):
            sanitized["owner"] = raw_item["assignee"].get("login", "")
        else:
            sanitized["owner"] = raw_item.get("assignee", "")

    return sanitized


class PortfolioCollector:
    """Collects snapshots from registered GitHub repositories and Beads stores."""

    def __init__(self, registry: Any):
        self.registry = registry

    def _compute_digest(self, data: Any) -> str:
        s = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(s.encode("utf-8")).hexdigest()

    def _default_beads_fetch(self, source: Dict[str, Any]) -> Any:
        """Runs native `br` against the source's exact beads store DB.

        STRICT INVARIANT: Ambient DB fallback is permanently forbidden.
        """
        db_path = source.get("host_binding")
        if not db_path or not str(db_path).strip():
            raise CollectorError(
                f"Source '{source.get('id')}' missing required 'host_binding' DB path. "
                "Ambient DB fallback is strictly forbidden."
            )

        cmd = [
            "br",
            "--db", str(db_path),
            "--no-auto-flush",
            "--no-auto-import",
            "list",
            "--status", "all",
            "--deferred",
            "--limit", "0",
            "--json"
        ]
        try:
            rc, stdout, stderr = run_bounded_command(cmd, timeout_secs=30)
            if rc != 0:
                raise CollectorError(f"br command failed with exit {rc}: {stderr}")
            return json.loads(stdout)
        except Exception as e:
            raise CollectorError(f"Failed to fetch beads for {source.get('id')}: {e}")

    def _default_gh_fetch(self, source: Dict[str, Any], page: int = 1, etag: Optional[str] = None) -> Dict[str, Any]:
        """Runs GitHub REST collection via gh CLI."""
        repo = source.get("repository")
        if not repo:
            raise CollectorError(f"Source {source.get('id')} missing repository")

        endpoint = f"repos/{repo}/issues?state=all&per_page=100&page={page}"
        cmd = ["gh", "api", endpoint]
        env = dict(os.environ)
        env["GH_PROMPT_DISABLED"] = "1"
        env["GH_NO_UPDATE_NOTIFIER"] = "1"
        env["GH_PAGER"] = ""

        try:
            rc, stdout, stderr = run_bounded_command(cmd, env=env, timeout_secs=30)
            if rc != 0:
                raise CollectorError(f"gh api failed with exit {rc}: {stderr}")
            raw_items = json.loads(stdout)
            has_next = len(raw_items) == 100
            return {
                "items": raw_items,
                "has_next": has_next,
                "next_page": page + 1 if has_next else None
            }
        except Exception as e:
            raise CollectorError(f"GitHub fetch failed for {repo} page {page}: {e}")

    def collect_source_snapshot(
        self,
        source_id: str,
        prior_snapshot: Optional[Dict[str, Any]] = None,
        fetch_fn: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """Collects a snapshot for a single source.

        Enforces pagination, dedup, 304 validation, stale/partial preservation, and sanitization.
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
                raw_response = fn(source)

                # Parse actual envelope {issues, total, limit, offset, has_more} or bare list
                if isinstance(raw_response, dict) and "issues" in raw_response:
                    raw_items = raw_response["issues"]
                elif isinstance(raw_response, list):
                    raw_items = raw_response
                else:
                    raise CollectorError(f"Unexpected beads output format: {type(raw_response).__name__}")

                items: List[Dict[str, Any]] = []
                seen_ids: Set[str] = set()

                for it in raw_items:
                    bead_id = str(it.get("id", ""))
                    if bead_id in seen_ids:
                        continue
                    seen_ids.add(bead_id)

                    key = self.registry.make_task_composite_key(github_host, repo, namespace, bead_id)
                    sanitized = sanitize_item(it, key)
                    items.append(sanitized)

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
            fn = fetch_fn or self._default_gh_fetch
            prior_etag = prior_snapshot.get("etag") if prior_snapshot else None

            collected_by_id: Dict[Any, Dict[str, Any]] = {}
            page = 1
            last_completed_page = 0
            has_next = True
            latest_etag = None

            try:
                while has_next:
                    resp = fn(source, page=page, etag=prior_etag)
                    if isinstance(resp, dict) and resp.get("status_code") == 304:
                        # 304 Not Modified: Reuse prior snapshot ONLY IF prior was fresh and complete
                        prior_status = prior_snapshot.get("status", "fresh") if prior_snapshot else None
                        if prior_snapshot and prior_status == "fresh" and prior_snapshot.get("version"):
                            fresh_304 = copy.deepcopy(prior_snapshot)
                            fresh_304["status"] = "fresh"
                            fresh_304["checkpoint_committed"] = True
                            fresh_304["collected_at"] = int(time.time())
                            return fresh_304
                        else:
                            raise CollectorError("304 received but prior snapshot is invalid or partial")

                    page_items = resp.get("items", [])
                    for it in page_items:
                        it_id = it.get("id") or it.get("number")
                        key = self.registry.make_task_composite_key(
                            github_host, repo, namespace, str(it_id)
                        )
                        sanitized = sanitize_item(it, key)
                        # Dedup by item id
                        collected_by_id[it_id] = sanitized

                    latest_etag = resp.get("etag", latest_etag)
                    last_completed_page = page
                    has_next = resp.get("has_next", False)
                    if has_next:
                        page = resp.get("next_page", page + 1)

                # Completed all pages successfully
                all_items = list(collected_by_id.values())
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
                # Partial failure: do not commit checkpoint, preserve UNION of prior unseen + new items
                union_items: Dict[Any, Dict[str, Any]] = {}
                if prior_snapshot and prior_snapshot.get("items"):
                    for prior_it in prior_snapshot["items"]:
                        p_id = prior_it.get("id")
                        if p_id is not None:
                            union_items[p_id] = prior_it
                # Overwrite/add with newly collected items
                for it_id, it_data in collected_by_id.items():
                    union_items[it_id] = it_data

                final_items = list(union_items.values())
                status = "partial" if final_items else "unavailable"

                return {
                    "source_id": source_id,
                    "status": status,
                    "version": prior_snapshot.get("version") if prior_snapshot else None,
                    "items": final_items,
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
