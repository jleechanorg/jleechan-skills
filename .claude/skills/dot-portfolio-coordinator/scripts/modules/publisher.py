"""Publisher module for dot-portfolio-coordinator.

Implements:
- Sanitized derived projection of WORK.md and COVERAGE.json only
- Exclusion of native .beads/issues.jsonl, raw control notes, and credentials
- Strict per-field audience filtering for public consumption
- Dedicated draft branch/PR publishing (normal fast-forward pushes only)
- Remote readback verification at pushed SHA
- No-op detection when content is identical
- Closed-unmerged PR publication hold
"""
import json
import time
from typing import Any, Dict, List, Optional, Tuple


class PublisherError(Exception):
    """Raised on publishing error."""
    pass


class PublicationHoldError(PublisherError):
    """Raised when publication is held (e.g. closed unmerged PR)."""
    pass


class RoadmapPublisher:
    """Renders sanitized WORK.md and COVERAGE.json and manages draft PR publication."""

    def __init__(self, registry: Any):
        self.registry = registry

    def render_work_md(self, snapshot: Dict[str, Any], proposal: Optional[Dict[str, Any]] = None) -> str:
        """Renders sanitized WORK.md markdown dashboard.

        Applies source audience policy for destination 'public'.
        """
        lines = [
            "# Portfolio Dashboard",
            "",
            f"Generated: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}",
            "",
            "## Work Items by Track",
            ""
        ]

        sources = snapshot.get("sources", {})
        for sid, sdata in sources.items():
            lines.append(f"### Source: `{sid}` (version `{sdata.get('version', 'unknown')}`)")
            items = sdata.get("items", [])
            if not items:
                lines.append("*No items recorded.*")
                lines.append("")
                continue

            lines.append("| ID | Title | Status | Priority | Owner | Blocker | Next Action |")
            lines.append("|---|---|---|---|---|---|---|")

            for it in items:
                # Audience policy filtering for 'public'
                pub = self.registry.filter_by_audience(sid, it, "public")
                item_id = it.get("id", "-")
                title = pub.get("title", "*(redacted)*")
                status = pub.get("status", "unknown")
                priority = str(pub.get("priority", "-"))
                owner = pub.get("owner", "unassigned")
                blocker = pub.get("blocker", "none")
                next_act = pub.get("next_action", "none")

                lines.append(f"| {item_id} | {title} | {status} | {priority} | {owner} | {blocker} | {next_act} |")

            lines.append("")

        return "\n".join(lines)

    def render_coverage_json(self, collection_metrics: Dict[str, Any], gaps: List[str]) -> Dict[str, Any]:
        """Renders sanitized COVERAGE.json metrics."""
        return {
            "schema_version": 1,
            "registered_sources": collection_metrics.get("registered_count", 0),
            "attempted_sources": collection_metrics.get("attempted_count", 0),
            "fresh_sources": collection_metrics.get("fresh_count", 0),
            "stale_sources": collection_metrics.get("stale_count", 0),
            "unavailable_sources": collection_metrics.get("unavailable_count", 0),
            "coverage_gaps": sorted(gaps),
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }

    def publish_snapshot(
        self,
        repo_dir: str,
        work_md_content: str,
        coverage_json_data: Dict[str, Any],
        git_runner: Any
    ) -> Dict[str, Any]:
        """Publishes WORK.md and COVERAGE.json via draft PR on owned branch.

        Strictly enforces:
        - Closed-unmerged hold
        - No-op detection
        - No force-push
        - No main branch push
        - Remote readback verification
        """
        if not git_runner:
            raise PublisherError("git_runner is required for publication")

        # 1. Check existing PR state
        pr_state = git_runner.get_pr_state()
        if pr_state:
            state = pr_state.get("state")
            merged = pr_state.get("merged", False)
            if state == "closed" and not merged:
                raise PublicationHoldError(
                    "Publication hold: previous snapshot PR was closed unmerged. "
                    "Owner direction required before publishing successor."
                )

        # 2. Check no-op
        work_md_path = "coordinator/WORK.md"
        coverage_json_path = "coordinator/COVERAGE.json"

        curr_work_md = git_runner.read_file(work_md_path)
        curr_cov_raw = git_runner.read_file(coverage_json_path)

        cov_str = json.dumps(coverage_json_data, sort_keys=True, indent=2)

        is_cov_match = False
        try:
            is_cov_match = (json.loads(curr_cov_raw) == coverage_json_data)
        except Exception:
            pass

        if curr_work_md == work_md_content and is_cov_match:
            return {"status": "no_op", "reason": "Content unchanged"}

        # 3. Stage allowlisted files only and commit
        branch_name = "coordinator/portfolio-snapshot"
        commit_msg = "chore(coordinator): update portfolio dashboard and coverage snapshot"
        pushed_sha = git_runner.commit(
            branch=branch_name,
            files={work_md_path: work_md_content, coverage_json_path: cov_str},
            message=commit_msg
        )

        # 4. Push to remote (normal fast-forward push only, never force push, never main)
        git_runner.push(branch_name, remote="origin")

        # 5. Remote readback verification
        rb_work_md = git_runner.read_remote_file(pushed_sha, work_md_path)
        rb_cov = git_runner.read_remote_file(pushed_sha, coverage_json_path)

        is_rb_cov_match = False
        try:
            is_rb_cov_match = (json.loads(rb_cov) == coverage_json_data)
        except Exception:
            pass

        if rb_work_md != work_md_content or not is_rb_cov_match:
            raise PublisherError(
                f"Remote readback verification failed at SHA {pushed_sha}. "
                "Remote file content does not match published snapshot."
            )

        pr_url = pr_state.get("pr_url") if pr_state else None
        return {
            "status": "published",
            "pushed_sha": pushed_sha,
            "pr_url": pr_url
        }
