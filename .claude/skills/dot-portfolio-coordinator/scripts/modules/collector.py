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
import hashlib
import json
import os
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from modules.process_utils import run_bounded_command, ProcessTimeoutError, ProcessExecutionError


class CollectorError(Exception):
    """Raised on collection failure."""

    def __init__(self, message: str, code: str = "collection_error") -> None:
        super().__init__(message)
        self.code = code if code in DIAGNOSTIC_CODES else "collection_error"


MAX_GITHUB_PAGES = 100
MAX_COLLECTION_SECS = 600
DIAGNOSTIC_CODES = {
    "beads_command_failed",
    "beads_fetch_failed",
    "beads_store_mismatch",
    "beads_where_failed",
    "collection_error",
    "deadline_exceeded",
    "execution_error",
    "github_fetch_failed",
    "incomplete_envelope",
    "invalid_304",
    "invalid_cursor",
    "invalid_envelope",
    "invalid_json",
    "missing_host_binding",
    "missing_pr_head",
    "missing_repository",
    "page_limit",
    "repeated_cursor",
    "timeout",
}
SAFE_STRING_FIELDS = {
    "title", "status", "created_at", "updated_at", "head_sha", "url", "checks"
}


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
    item_id = raw_item.get("id", raw_item.get("number"))
    if isinstance(item_id, (str, int)) and not isinstance(item_id, bool):
        sanitized["id"] = item_id

    for field in SAFE_STRING_FIELDS:
        value = raw_item.get(field)
        if field == "status" and value is None:
            value = raw_item.get("state")
        if isinstance(value, str):
            sanitized[field] = value

    priority = raw_item.get("priority")
    if isinstance(priority, int) and not isinstance(priority, bool):
        sanitized["priority"] = priority

    is_draft = raw_item.get("is_draft", raw_item.get("draft"))
    if isinstance(is_draft, bool):
        sanitized["is_draft"] = is_draft

    owner = raw_item.get("owner")
    if not isinstance(owner, str):
        if isinstance(owner, dict):
            owner = owner.get("login")
        if not isinstance(owner, str):
            owner = raw_item.get("user")
            if not isinstance(owner, dict):
                owner = raw_item.get("assignee")
            owner = owner.get("login") if isinstance(owner, dict) else None
    if isinstance(owner, str):
        sanitized["owner"] = owner

    return sanitized


class PortfolioCollector:
    """Collects snapshots from registered GitHub repositories and Beads stores."""

    def __init__(self, registry: Any):
        self.registry = registry

    def _deadline(self, deadline_mono: Optional[float]) -> float:
        if deadline_mono is not None:
            return deadline_mono
        return time.monotonic() + MAX_COLLECTION_SECS

    def _timeout_secs(self, deadline_mono: float) -> int:
        remaining = deadline_mono - time.monotonic()
        if remaining < 1:
            raise CollectorError(
                "Collection deadline exceeded", code="deadline_exceeded"
            )
        return min(30, int(remaining))

    def _error_code(self, error: Exception, fallback: str = "collection_error") -> str:
        if isinstance(error, CollectorError):
            return error.code
        if isinstance(error, ProcessTimeoutError):
            return "timeout"
        if isinstance(error, ProcessExecutionError):
            return "execution_error"
        return fallback

    def _sanitize_source_item(
        self,
        source_id: str,
        raw_item: Dict[str, Any],
        composite_key: Tuple[str, str, str, str],
    ) -> Dict[str, Any]:
        safe = sanitize_item(raw_item, composite_key)
        audience_safe = self.registry.filter_by_audience(source_id, safe, "internal")
        for field in ("id", "task_composite_key"):
            if field in safe:
                audience_safe[field] = safe[field]
        return audience_safe

    def _sanitize_snapshot_items(
        self, source_id: str, source: Dict[str, Any], items: Any
    ) -> List[Dict[str, Any]]:
        if not isinstance(items, list):
            return []
        output: Dict[str, Dict[str, Any]] = {}
        host = source.get("github_host", "github.com")
        repo = source.get("repository", "")
        namespace = source.get("namespace", "")
        for item in items:
            if not isinstance(item, dict):
                continue
            item_id = item.get("id", item.get("number"))
            if not isinstance(item_id, (str, int)) or isinstance(item_id, bool):
                continue
            key = self.registry.make_task_composite_key(
                host, repo, namespace, str(item_id)
            )
            output[item_id] = self._sanitize_source_item(source_id, item, key)
        return list(output.values())

    def _failure_snapshot(
        self,
        source_id: str,
        source: Dict[str, Any],
        prior_snapshot: Optional[Dict[str, Any]],
        partial_items: List[Dict[str, Any]], error_code: str, cursor: Dict[str, Any]
    ) -> Dict[str, Any]:
        merged: Dict[Any, Dict[str, Any]] = {}
        if prior_snapshot:
            for item in self._sanitize_snapshot_items(
                source_id, source, prior_snapshot.get("items", [])
            ):
                merged[item["id"]] = item
        for item in partial_items:
            merged[item["id"]] = item
        items = list(merged.values())
        is_incomplete = error_code in {
            "incomplete_envelope", "repeated_cursor", "page_limit"
        }
        status = (
            "partial" if partial_items or is_incomplete
            else "stale" if items
            else "unavailable"
        )
        snapshot = {
            "source_id": source_id,
            "status": status,
            "version": None,
            "items": items,
            "cursor": cursor,
            "checkpoint_committed": False,
            "attempted_at": int(time.time()),
            "error_code": error_code,
        }
        collected_at = prior_snapshot.get("collected_at") if prior_snapshot else None
        if isinstance(collected_at, int) and not isinstance(collected_at, bool):
            snapshot["collected_at"] = collected_at
        return snapshot

    def _compute_digest(self, data: Any) -> str:
        s = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(s.encode("utf-8")).hexdigest()

    def _default_beads_fetch(
        self, source: Dict[str, Any], deadline_mono: Optional[float] = None
    ) -> Any:
        """Runs native `br` against the source's exact beads store DB.

        STRICT INVARIANT: Ambient DB fallback is permanently forbidden.
        """
        db_path = source.get("host_binding")
        if not db_path or not str(db_path).strip():
            raise CollectorError(
                f"Source '{source.get('id')}' missing required 'host_binding' DB path. "
                "Ambient DB fallback is strictly forbidden.",
                code="missing_host_binding",
            )

        deadline = self._deadline(deadline_mono)
        where_cmd = [
            "br",
            "--db", str(db_path),
            "--no-auto-flush",
            "--no-auto-import",
            "where",
            "--json",
        ]
        try:
            rc, stdout, _stderr = run_bounded_command(
                where_cmd, timeout_secs=self._timeout_secs(deadline)
            )
            if rc != 0:
                raise CollectorError("br where failed", code="beads_where_failed")
            resolved = json.loads(stdout)
            resolved_db = (
                resolved.get("database_path") if isinstance(resolved, dict) else None
            )
            paths_match = (
                isinstance(resolved_db, str)
                and os.path.realpath(resolved_db) == os.path.realpath(str(db_path))
            )
            if not paths_match:
                raise CollectorError(
                    "br resolved a different database", code="beads_store_mismatch"
                )

            cmd = [
                "br",
                "--db", resolved_db,
                "--no-auto-flush",
                "--no-auto-import",
                "list",
                "--status", "all",
                "--deferred",
                "--limit", "0",
                "--json"
            ]
            rc, stdout, _stderr = run_bounded_command(
                cmd, timeout_secs=self._timeout_secs(deadline)
            )
            if rc != 0:
                raise CollectorError("br list failed", code="beads_command_failed")
            return json.loads(stdout)
        except Exception as e:
            if isinstance(e, CollectorError):
                raise
            if isinstance(e, json.JSONDecodeError):
                raise CollectorError("Invalid br JSON response", code="invalid_json") from None
            raise CollectorError("Beads fetch failed", code=self._error_code(e, "beads_fetch_failed")) from None

    def _default_gh_fetch(
        self, source: Dict[str, Any], page: int = 1, etag: Optional[str] = None,
        deadline_mono: Optional[float] = None
    ) -> Dict[str, Any]:
        """Runs GitHub REST collection via gh CLI."""
        repo = source.get("repository")
        if not repo:
            raise CollectorError("Source missing repository", code="missing_repository")
        host = source.get("github_host", "github.com")
        deadline = self._deadline(deadline_mono)
        env = dict(os.environ)
        env["GH_PROMPT_DISABLED"] = "1"
        env["GH_NO_UPDATE_NOTIFIER"] = "1"
        env["GH_PAGER"] = ""

        def fetch_json(endpoint: str) -> Any:
            cmd = ["gh", "api", "--hostname", host, endpoint]
            rc, stdout, _stderr = run_bounded_command(
                cmd, env=env, timeout_secs=self._timeout_secs(deadline)
            )
            if rc != 0:
                raise CollectorError("GitHub API request failed", code="github_fetch_failed")
            try:
                return json.loads(stdout)
            except json.JSONDecodeError:
                raise CollectorError("Invalid GitHub JSON response", code="invalid_json") from None

        endpoint = f"repos/{repo}/issues?state=all&per_page=100&page={page}"
        raw_items = fetch_json(endpoint)
        if not isinstance(raw_items, list):
            raise CollectorError("Unexpected GitHub response shape", code="invalid_envelope")

        enriched = []
        for raw_item in raw_items:
            if not isinstance(raw_item, dict) or not isinstance(raw_item.get("pull_request"), dict):
                enriched.append(raw_item)
                continue
            number = raw_item.get("number")
            if not isinstance(number, int) or isinstance(number, bool):
                raise CollectorError("Pull request number is invalid", code="invalid_envelope")
            pr = fetch_json(f"repos/{repo}/pulls/{number}")
            if not isinstance(pr, dict):
                raise CollectorError("Pull request response is invalid", code="invalid_envelope")
            head = pr.get("head")
            sha = head.get("sha") if isinstance(head, dict) else None
            if not isinstance(sha, str) or not sha:
                raise CollectorError("Pull request head is missing", code="missing_pr_head")
            check_runs: List[Dict[str, Any]] = []
            total_checks: Optional[int] = None
            for check_page in range(1, MAX_GITHUB_PAGES + 1):
                checks = fetch_json(
                    f"repos/{repo}/commits/{sha}/check-runs?per_page=100&page={check_page}"
                )
                runs = checks.get("check_runs") if isinstance(checks, dict) else None
                total = checks.get("total_count") if isinstance(checks, dict) else None
                if not isinstance(runs, list):
                    raise CollectorError("Check response is invalid", code="invalid_envelope")
                if total is None or (
                    isinstance(total, bool) or not isinstance(total, int) or total < 0
                ):
                    raise CollectorError("Check count is invalid", code="invalid_envelope")
                total_checks = total if total_checks is None else total_checks
                check_runs.extend(run for run in runs if isinstance(run, dict))
                if total_checks is None or len(check_runs) >= total_checks:
                    break
            else:
                raise CollectorError("Check page limit exceeded", code="page_limit")
            if total_checks is not None and len(check_runs) < total_checks:
                raise CollectorError("Check result is incomplete", code="incomplete_envelope")
            conclusions = [run.get("conclusion") for run in check_runs]
            if not check_runs:
                check_state = "none"
            elif any(run.get("status") != "completed" for run in check_runs):
                check_state = "pending"
            elif all(value in ("success", "skipped", "neutral") for value in conclusions):
                check_state = "success"
            else:
                check_state = "failure"
            raw_item = dict(raw_item)
            raw_item["head_sha"] = sha
            raw_item["checks"] = check_state
            raw_item = dict(raw_item)
            raw_item["is_draft"] = pr.get("draft") is True
            enriched.append(raw_item)

        has_next = len(raw_items) == 100
        return {
            "items": enriched,
            "has_next": has_next,
            "next_page": page + 1 if has_next else None
        }

    def collect_source_snapshot(
        self,
        source_id: str,
        prior_snapshot: Optional[Dict[str, Any]] = None,
        fetch_fn: Optional[Callable] = None,
        deadline_mono: Optional[float] = None
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
        deadline = self._deadline(deadline_mono)

        # 1. Beads store collection
        if src_type in ("beads_store", "roadmap_beads"):
            partial_items: List[Dict[str, Any]] = []
            try:
                if time.monotonic() >= deadline:
                    raise CollectorError("Collection deadline exceeded", code="deadline_exceeded")
                if fetch_fn:
                    raw_response = fetch_fn(source)
                else:
                    raw_response = self._default_beads_fetch(source, deadline_mono=deadline)

                # Legacy injected list responses remain supported; native envelopes are validated.
                if isinstance(raw_response, dict) and "issues" in raw_response:
                    raw_items = raw_response["issues"]
                    if not isinstance(raw_items, list):
                        raise CollectorError("Invalid Beads issues field", code="invalid_envelope")
                    has_more = raw_response.get("has_more")
                    total = raw_response.get("total")
                    offset = raw_response.get("offset", 0)
                    if not isinstance(has_more, bool):
                        raise CollectorError("Invalid Beads completeness field", code="invalid_envelope")
                    if (isinstance(total, bool) or not isinstance(total, int)
                            or isinstance(offset, bool) or not isinstance(offset, int) or offset < 0):
                        raise CollectorError("Invalid Beads pagination metadata", code="invalid_envelope")
                    partial_items = self._sanitize_snapshot_items(source_id, source, raw_items)
                    if has_more or offset != 0 or offset + len(raw_items) != total:
                        raise CollectorError("Beads response is incomplete", code="incomplete_envelope")
                elif isinstance(raw_response, list):
                    raw_items = raw_response
                else:
                    raise CollectorError("Unexpected Beads output format", code="invalid_envelope")

                items: List[Dict[str, Any]] = []
                seen_ids: Set[str] = set()

                for it in raw_items:
                    if not isinstance(it, dict):
                        raise CollectorError("Invalid Beads issue item", code="invalid_envelope")
                    bead_id = str(it.get("id", ""))
                    if not bead_id:
                        raise CollectorError("Beads issue is missing an ID", code="invalid_envelope")
                    if bead_id in seen_ids:
                        continue
                    seen_ids.add(bead_id)

                    key = self.registry.make_task_composite_key(github_host, repo, namespace, bead_id)
                    sanitized = self._sanitize_source_item(source_id, it, key)
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
                    "error_code": None
                }
            except Exception as e:
                if isinstance(e, CollectorError):
                    code = e.code
                else:
                    code = self._error_code(e, "beads_fetch_failed")
                return self._failure_snapshot(
                    source_id, source, prior_snapshot, partial_items, code,
                    {"last_completed_page": 0, "completed": False},
                )

        # 2. GitHub repo collection (paginated)
        elif src_type == "github_repo":
            fn = fetch_fn or self._default_gh_fetch
            prior_etag = prior_snapshot.get("etag") if prior_snapshot else None

            collected_by_id: Dict[Any, Dict[str, Any]] = {}
            page = 1
            last_completed_page = 0
            has_next = True
            latest_etag = None
            visited_pages: Set[int] = set()

            try:
                while has_next:
                    if time.monotonic() >= deadline:
                        raise CollectorError("Collection deadline exceeded", code="deadline_exceeded")
                    if len(visited_pages) >= MAX_GITHUB_PAGES:
                        raise CollectorError("GitHub page limit exceeded", code="page_limit")
                    if isinstance(page, bool) or not isinstance(page, int) or page < 1:
                        raise CollectorError("Invalid GitHub page cursor", code="invalid_cursor")
                    if page in visited_pages:
                        raise CollectorError("Repeated GitHub page cursor", code="repeated_cursor")
                    visited_pages.add(page)
                    if fetch_fn:
                        resp = fn(source, page=page, etag=prior_etag)
                    else:
                        resp = fn(source, page=page, etag=prior_etag, deadline_mono=deadline)
                    if isinstance(resp, dict) and resp.get("status_code") == 304:
                        # 304 Not Modified: Reuse prior snapshot ONLY IF prior was fresh and complete
                        prior_status = prior_snapshot.get("status", "fresh") if prior_snapshot else None
                        if prior_snapshot and prior_status == "fresh" and prior_snapshot.get("version"):
                            safe_items = self._sanitize_snapshot_items(
                                source_id, source, prior_snapshot.get("items", [])
                            )
                            fresh_304 = {
                                "source_id": source_id,
                                "status": "fresh",
                                "version": self._compute_digest(safe_items),
                                "items": safe_items,
                                "cursor": {"last_completed_page": 1, "completed": True},
                                "checkpoint_committed": True,
                                "validated_at": int(time.time()),
                                "error_code": None,
                            }
                            collected_at = prior_snapshot.get("collected_at")
                            if isinstance(collected_at, int) and not isinstance(collected_at, bool):
                                fresh_304["collected_at"] = collected_at
                            etag = prior_snapshot.get("etag")
                            if isinstance(etag, str):
                                fresh_304["etag"] = etag
                            return fresh_304
                        else:
                            raise CollectorError("304 prior snapshot is invalid or partial", code="invalid_304")

                    if not isinstance(resp, dict) or not isinstance(resp.get("items"), list):
                        raise CollectorError("Invalid GitHub page response", code="invalid_envelope")
                    page_items = resp["items"]
                    for it in page_items:
                        if not isinstance(it, dict):
                            raise CollectorError("Invalid GitHub issue item", code="invalid_envelope")
                        it_id = it.get("id") or it.get("number")
                        if not isinstance(it_id, (int, str)) or isinstance(it_id, bool):
                            raise CollectorError("GitHub issue is missing an ID", code="invalid_envelope")
                        key = self.registry.make_task_composite_key(
                            github_host, repo, namespace, str(it_id)
                        )
                        sanitized = self._sanitize_source_item(source_id, it, key)
                        # Dedup by item id
                        collected_by_id[it_id] = sanitized

                    latest_etag = resp.get("etag", latest_etag)
                    last_completed_page = page
                    has_next = resp.get("has_next", False)
                    if not isinstance(has_next, bool):
                        raise CollectorError("Invalid GitHub pagination flag", code="invalid_envelope")
                    if has_next:
                        next_page = resp.get("next_page", page + 1)
                        if isinstance(next_page, bool) or not isinstance(next_page, int) or next_page < 1:
                            raise CollectorError("Invalid GitHub next-page cursor", code="invalid_cursor")
                        if next_page in visited_pages:
                            raise CollectorError("Repeated GitHub page cursor", code="repeated_cursor")
                        page = next_page

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
                    "error_code": None
                }
            except Exception as e:
                code = self._error_code(e)
                return self._failure_snapshot(
                    source_id, source, prior_snapshot, list(collected_by_id.values()), code,
                    {"last_completed_page": last_completed_page, "completed": False},
                )

        raise CollectorError(f"Unsupported source type: {src_type}")

    def collect_all(
        self,
        prior_snapshots: Optional[Dict[str, Any]] = None,
        fetch_fn: Optional[Callable] = None,
        deadline_mono: Optional[float] = None
    ) -> Dict[str, Any]:
        """Collects snapshots for all registered sources and aggregates metrics."""
        prior = prior_snapshots or {}
        deadline = self._deadline(deadline_mono)
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
            snap = self.collect_source_snapshot(
                sid, prior_snapshot=src_prior, fetch_fn=fetch_fn, deadline_mono=deadline
            )
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
