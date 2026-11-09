"""Recover native usage and prompt metadata from explicit history roots."""
import argparse
import hashlib
import io
import json
import math
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

if __package__:
    from .prw_metrics import _parse_utc_instant, _safe_pr_id, _usage_count, _usage_label, format_iso_utc
else:
    from prw_metrics import _parse_utc_instant, _safe_pr_id, _usage_count, _usage_label, format_iso_utc


def _apply_replay_annotation(record, annotation):
    actor_kind = annotation.get("actor_kind")
    human_origin = annotation.get("human_origin")
    if actor_kind in ("human", "automated_watch"):
        record["actor_kind"] = actor_kind
        record["origin_status"] = (
            "excluded_automated"
            if actor_kind == "automated_watch"
            else "verified_human"
        )
    elif human_origin in ("automated_watch", "automated_watch_excluded"):
        record["actor_kind"] = "automated_watch"
        record["origin_status"] = "excluded_automated"
    elif human_origin == "verified_human":
        record["origin_status"] = "verified_human"
    for key in (
        "episode_id", "episode_role", "quality_label", "score_source", "review_id",
        "context_pr_decision", "association_method", "annotation_confidence",
        "effective_association_confidence", "original_association_basis",
        "original_association_confidence",
    ):
        value = annotation.get(key)
        if isinstance(value, str) and value:
            record[key] = value
    for key in (
        "context_associated_pr", "effective_associated_pr", "original_associated_pr",
    ):
        if key in annotation:
            value = annotation[key]
            if value is None or _safe_pr_id(value):
                record[key] = value
    if annotation.get("message_kind") in {
        "initial_task", "new_requirement/domain_judgment", "status_request",
        "continuation/followthrough_nudge",
    }:
        record["message_kind"] = annotation["message_kind"]
    if isinstance(annotation.get("human_nudge_eligible"), bool):
        record["human_nudge_eligible"] = annotation["human_nudge_eligible"]
    score = annotation.get("score")
    if (
        isinstance(score, (int, float))
        and not isinstance(score, bool)
        and math.isfinite(score)
    ):
        record["score"] = score
    binding = annotation.get("pr_binding")
    if isinstance(binding, dict) and _safe_pr_id(binding.get("pr")):
        record["pr_binding"] = {
            key: binding[key] for key in ("pr", "method", "weight")
            if key in binding and isinstance(binding[key], (str, int, float))
        }


def _load_replay_annotations(path):
    annotations = {}
    if path:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
        for line_number, line in enumerate(lines, 1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except ValueError as exc:
                raise ValueError(
                    f"annotation line {line_number} is invalid JSON"
                ) from exc
            if not isinstance(item, dict):
                raise ValueError(f"annotation line {line_number} must be an object")
            event_id = item.get("event_id")
            if isinstance(event_id, str) and event_id:
                annotations[event_id] = item
    return annotations


def load_normalized_history(path, cutoff, days=14, annotation_path=None):
    """Replay a typed normalized export without reopening native history sources."""
    if isinstance(cutoff, datetime) and cutoff.tzinfo:
        cutoff = cutoff.astimezone(timezone.utc)
    else:
        cutoff = _parse_utc_instant(cutoff)
    if cutoff is None or days <= 0:
        raise ValueError(
            "normalized history replay requires a UTC cutoff and positive days"
        )
    start = cutoff - timedelta(days=days)
    usage, humans, exported = [], [], []
    stats = dict(
        roots_requested=0, roots_available=0, missing_roots=0, files_scanned=0,
        duplicate_files=0, malformed_lines=0, read_errors=0,
        outside_window_records=0, undated_records=0, usage_records_in_window=0,
        duplicate_usage_records=0, human_candidates=0, human_verified=0,
        human_unannotated=0, automated_excluded_messages=0,
        pr_bound_usage_records=0, tool_result_records_excluded=0,
        context_records_excluded=0, status="REPLAYED",
        runtime_coverage=(
            "Claude and Codex normalized export; source roots were not reopened"
        ),
        window_start=format_iso_utc(start), window_end=format_iso_utc(cutoff),
    )
    annotations = _load_replay_annotations(annotation_path)
    seen_usage = set()
    with Path(path).open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except (ValueError, UnicodeError) as exc:
                raise ValueError(
                    f"normalized history line {line_number} is invalid JSON"
                ) from exc
            if (
                not isinstance(record, dict)
                or record.get("record_type") not in ("usage", "human")
            ):
                raise ValueError(
                    f"normalized history line {line_number} has an "
                    "unsupported record type"
                )
            if record["record_type"] == "human":
                annotation = annotations.get(record.get("event_id"))
                if annotation is None:
                    aliases = record.get("event_id_aliases")
                    aliases = aliases if isinstance(aliases, list) else []
                    annotation = next(
                        (
                            annotations[alias]
                            for alias in aliases
                            if alias in annotations
                        ),
                        None,
                    )
                if annotation is not None:
                    record = dict(record)
                    _apply_replay_annotation(record, annotation)
            at = _parse_utc_instant(record.get("timestamp"))
            if at is None:
                stats["undated_records"] += 1
                continue
            if not start <= at < cutoff:
                stats["outside_window_records"] += 1
                continue
            exported.append(record)
            if record["record_type"] == "usage":
                identity = (record.get("provider"), record.get("request_id"))
                if identity[1] and identity in seen_usage:
                    stats["duplicate_usage_records"] += 1
                elif identity[1]:
                    seen_usage.add(identity)
                usage.append(record)
                stats["usage_records_in_window"] += 1
                stats["pr_bound_usage_records"] += bool(record.get("attributions"))
            else:
                humans.append(record)
                automated = (
                    record.get("actor_kind") == "automated_watch"
                    or record.get("origin_status") == "excluded_automated"
                )
                stats["automated_excluded_messages"] += automated
                if not automated:
                    stats["human_candidates"] += 1
                    verified = (
                        record.get("actor_kind") == "human"
                        or record.get("origin_status") == "verified_human"
                    )
                    stats["human_verified"] += verified
                    stats["human_unannotated"] += (
                        record.get("origin_status") == "unverified_candidate"
                    )
    return {
        "usage_records": usage,
        "human_records": humans,
        "export_records": exported,
        "stats": stats,
    }


def write_normalized_history(path, records):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in records), encoding="utf-8")


_GITHUB_SLUG = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def _repository_slug(value):
    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip()
    if _GITHUB_SLUG.fullmatch(value):
        return value.lower()
    parsed = urlparse(value)
    if parsed.hostname not in ("github.com", "www.github.com"):
        return None
    slug = parsed.path.strip("/").removesuffix(".git")
    return slug.lower() if _GITHUB_SLUG.fullmatch(slug) else None


def _git_metadata(row, payload, repository_map):
    meta = payload.get("meta")
    meta = meta if isinstance(meta, dict) else {}
    branch = row.get("gitBranch") or row.get("git_branch") or payload.get("git_branch") or meta.get("git_branch")
    commit = row.get("commit_hash") or payload.get("commit_hash") or meta.get("commit_hash")
    repo_url = (row.get("repository_url") or payload.get("repository_url")
                or meta.get("repository_url") or row.get("repositoryURL"))
    repo = _repository_slug(repo_url)
    source = "recorded_repository_url" if repo else None
    basis = "recorded_repository_url" if repo else None
    if not repo:
        cwd = row.get("cwd") or payload.get("cwd") or meta.get("cwd")
        mapped = repository_map.get(cwd) if isinstance(cwd, str) else None
        repo = _repository_slug(mapped)
        if repo:
            source, basis = "cached_repository_map", "exact_recorded_cwd_lookup"
    branch = (branch.strip() or None) if isinstance(branch, str) else None
    commit = (commit.strip() or None) if isinstance(commit, str) else None
    if branch and source is None:
        source, basis = "recorded_git_branch", "exact_recorded_record"
    result = {"git_branch": branch, "repository": repo, "branch_source": source,
              "branch_basis": basis}
    if commit:
        result["commit_hash"] = commit
    return result


def _fill_snapshot_context(record, snapshot):
    repo, branch = snapshot.get("repository"), snapshot.get("git_branch")
    if (repo and branch and
        (not record.get("repository") or record["repository"] == repo) and
        (not record.get("git_branch") or record["git_branch"] == branch)):
        for key in ("repository", "git_branch"):
            if not record.get(key):
                record[key] = snapshot[key]
                record["branch_source"] = "state_db_snapshot"
                record["branch_basis"] = "state_db_thread_snapshot"


def enrich_replay_state(records, state_db):
    """Fill missing native Git context from read-only thread snapshots."""
    snapshots = {}
    with sqlite3.connect(Path(state_db).resolve().as_uri() + "?mode=ro", uri=True) as conn:
        for record in records:
            session = record.get("session_id")
            if record.get("provider") != "openai" or not session:
                continue
            if session not in snapshots:
                row = conn.execute(
                    "SELECT git_branch, git_origin_url FROM threads WHERE id = ?", (session,)
                ).fetchone()
                snapshots[session] = _git_metadata(
                    {"git_branch": row[0], "repository_url": row[1]}, {}, {}
                ) if row else {}
            _fill_snapshot_context(record, snapshots[session])


def collect_native_history(history_roots, *, cutoff, days=14, annotation_path=None,
                           repository_map=None, state_db=None):
    if cutoff.tzinfo is None or days <= 0:
        raise ValueError("An aware cutoff and positive window are required")
    repository_map = repository_map if isinstance(repository_map, dict) else {}
    state_conn = sqlite3.connect(Path(state_db).resolve().as_uri() + "?mode=ro", uri=True) if state_db else None
    start = cutoff - timedelta(days=days)
    annotations, bindings = {}, {}
    if annotation_path:
        for line in Path(annotation_path).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            if item.get("event_id"):
                annotations[item["event_id"]] = item
            if item.get("provider") and item.get("request_id") and isinstance(item.get("pr_binding"), dict):
                bindings[(item["provider"], item["request_id"])] = item["pr_binding"]
    stats = dict(roots_requested=len(history_roots), roots_available=0, missing_roots=0,
                 files_scanned=0, duplicate_files=0, malformed_lines=0, read_errors=0,
                 outside_window_records=0, undated_records=0, usage_records_in_window=0,
                 duplicate_usage_records=0, human_candidates=0, human_verified=0,
                 human_unannotated=0, automated_excluded_messages=0, pr_bound_usage_records=0,
                 tool_result_records_excluded=0, context_records_excluded=0)
    stats["runtime_coverage"] = "Claude and Codex configured roots; other runtimes not collected"
    usage, humans, exported, seen_files, seen_usage = [], [], [], set(), set()
    for root in history_roots:
        root = Path(root)
        if not root.exists():
            stats["missing_roots"] += 1
            continue
        stats["roots_available"] += 1
        files = [root] if root.is_file() else sorted(root.rglob("*.jsonl"))
        for path in files:
            identity = str(path.resolve())
            if identity in seen_files:
                stats["duplicate_files"] += 1
                continue
            seen_files.add(identity)
            models, session, session_git = {}, None, {}
            try:
                content = path.read_bytes()
                digest = hashlib.sha256(content)
                with io.BytesIO(content) as stream:
                    for line in stream:
                        try:
                            row = json.loads(line)
                        except (ValueError, UnicodeError):
                            continue
                        if not isinstance(row, dict):
                            continue
                        payload = row.get("payload", {})
                        if not isinstance(payload, dict):
                            continue
                        if row.get("type") == "session_meta":
                            session = _usage_label(payload.get("id"))
                            session_git = _git_metadata(row, payload, repository_map)
                        if row.get("type") == "turn_context" and payload.get("turn_id"):
                            models[payload["turn_id"]] = _usage_label(payload.get("model"))
                if state_conn and session:
                    snapshot = state_conn.execute(
                        "SELECT git_branch, git_origin_url FROM threads WHERE id = ?", (session,)
                    ).fetchone()
                    if snapshot:
                        snapshot_git = _git_metadata(
                            {"git_branch": snapshot[0], "repository_url": snapshot[1]}, {}, {}
                        )
                        _fill_snapshot_context(session_git, snapshot_git)
                fingerprint = "sha256:" + digest.hexdigest()
                stats["files_scanned"] += 1
                with io.StringIO(content.decode("utf-8")) as stream:
                    for ordinal, line in enumerate(stream):
                        try:
                            row = json.loads(line)
                        except (ValueError, UnicodeError):
                            stats["malformed_lines"] += 1
                            continue
                        if not isinstance(row, dict):
                            continue
                        kind, payload = row.get("type"), row.get("payload", {})
                        payload = payload if isinstance(payload, dict) else {}
                        message = row.get("message", {})
                        message = message if isinstance(message, dict) else {}
                        claude_usage = kind == "assistant" and isinstance(message.get("usage"), dict)
                        codex_usage = kind == "token_usage_record" and isinstance(payload.get("usage"), dict)
                        claude_user = kind == "user" and message.get("role") == "user"
                        codex_user = kind == "response_item" and payload.get("role") == "user"
                        if not any((claude_usage, codex_usage, claude_user, codex_user)):
                            continue
                        content = message.get("content")
                        if claude_user and isinstance(content, list) and any(
                            isinstance(block, dict) and block.get("type") == "tool_result" for block in content
                        ):
                            stats["tool_result_records_excluded"] += 1
                            continue
                        if claude_user and row.get("isMeta") is True:
                            stats["context_records_excluded"] += 1
                            continue
                        at = _parse_utc_instant(row.get("timestamp"))
                        if at is None:
                            stats["undated_records"] += 1
                            continue
                        if not start <= at < cutoff:
                            stats["outside_window_records"] += 1
                            continue
                        provider = "openai" if codex_usage or codex_user else "anthropic"
                        source_identity = "source:" + hashlib.sha256(identity.encode()).hexdigest()
                        namespace = session or _usage_label(row.get("sessionId")) or source_identity
                        turn = _usage_label(payload.get("turn_id"))
                        common = dict(timestamp=format_iso_utc(at), provider=provider,
                                      session_id=namespace, turn_id=turn, source_fingerprint=fingerprint)
                        if codex_usage or codex_user:
                            git_metadata = _git_metadata(row, payload, repository_map)
                            git_metadata = {key: value for key, value in git_metadata.items() if value is not None}
                            for key in ("git_branch", "repository", "commit_hash"):
                                if not git_metadata.get(key) and session_git.get(key):
                                    git_metadata[key] = session_git[key]
                                    git_metadata["branch_source"] = session_git.get("branch_source") or "session_meta"
                                    git_metadata["branch_basis"] = session_git.get("branch_basis") or "session_git_metadata"
                        else:
                            git_metadata = _git_metadata(row, {}, repository_map)
                            git_metadata = {key: value for key, value in git_metadata.items() if value is not None}
                        common.update(git_metadata)
                        if claude_usage or codex_usage:
                            raw = payload["usage"] if codex_usage else message["usage"]
                            request = (
                                (payload.get("response_id") or row.get("response_id"))
                                if codex_usage
                                else (row.get("requestId") or message.get("id"))
                            )
                            request = _usage_label(request)
                            model = models.get(turn) if codex_usage else _usage_label(message.get("model"))
                            normalized = {
                                "input_tokens": _usage_count(raw.get("input_tokens")),
                                "output_tokens": _usage_count(raw.get("output_tokens")),
                            }
                            if codex_usage:
                                cached = _usage_count(raw.get("cached_input_tokens"))
                                total = normalized["input_tokens"]
                                normalized["input_tokens"] = total - cached if total is not None and cached is not None and total >= cached else None
                                normalized["cache_read_input_tokens"] = cached
                                normalized["cache_write_input_tokens"] = _usage_count(raw.get("cache_write_input_tokens"))
                                thinking = raw.get("reasoning_output_tokens")
                            else:
                                normalized["cache_read_input_tokens"] = _usage_count(raw.get("cache_read_input_tokens"))
                                cache = raw.get("cache_creation", {})
                                cache = cache if isinstance(cache, dict) else {}
                                normalized["cache_creation"] = {key: _usage_count(cache.get(key)) for key in
                                    ("ephemeral_5m_input_tokens", "ephemeral_1h_input_tokens")}
                                normalized["cache_creation_input_tokens"] = _usage_count(raw.get("cache_creation_input_tokens"))
                                details = raw.get("output_tokens_details", {})
                                thinking = details.get("thinking_tokens") if isinstance(details, dict) else None
                            normalized["output_tokens_details"] = {"thinking_tokens": _usage_count(thinking)}
                            for key in ("service_tier", "inference_geo", "speed"):
                                normalized[key] = _usage_label(raw.get(key))
                            record = dict(common, request_id=request, model=model, raw_usage=normalized)
                            binding = bindings.get((provider, request))
                            if binding:
                                stats["pr_bound_usage_records"] += 1
                                record["attributions"] = [{key: binding[key] for key in
                                    ("pr", "weight", "method", "receipt_refs", "rationale", "basis", "convention_ref") if key in binding}]
                            key = (provider, request)
                            if request and key in seen_usage:
                                stats["duplicate_usage_records"] += 1
                            if request:
                                seen_usage.add(key)
                            usage.append(record)
                            export_record = dict(record, record_type="usage")
                            export_record["attributions"] = [
                                {
                                    **attr,
                                    "rationale": "retained" if attr.get("rationale") else "",
                                }
                                for attr in record.get("attributions", [])
                            ]
                            exported.append(export_record)
                            stats["usage_records_in_window"] += 1
                        else:
                            aliases = []
                            event_id = _usage_label(row.get("uuid") or row.get("promptId") or payload.get("id"))
                            for alias in (payload.get("id"), row.get("promptId"), row.get("uuid")):
                                alias = _usage_label(alias)
                                if alias and alias != event_id and alias not in aliases:
                                    aliases.append(alias)
                            event_id = event_id or namespace + ":" + str(ordinal)
                            origin = row.get("origin", {})
                            origin = origin if isinstance(origin, dict) else {}
                            verified = claude_user and (origin.get("kind") == "human" or row.get("turnOrigin") == "human" or row.get("userType") == "human")
                            record = dict(common, event_id=event_id,
                                          origin_status="verified_human" if verified else "unverified_candidate")
                            if aliases:
                                record["event_id_aliases"] = aliases
                            if claude_user:
                                record["prompt_source"] = _usage_label(row.get("promptSource"))
                            annotation = annotations.get(event_id)
                            if annotation is None:
                                annotation = next((annotations[alias] for alias in aliases if alias in annotations), None)
                            actor_kind = None
                            if annotation:
                                actor_kind = annotation.get("actor_kind")
                                human_origin = annotation.get("human_origin")
                                if actor_kind in ("human", "automated_watch"):
                                    record["actor_kind"] = actor_kind
                                    record["origin_status"] = (
                                        "excluded_automated" if actor_kind == "automated_watch"
                                        else "verified_human"
                                    )
                                elif human_origin in ("automated_watch", "automated_watch_excluded"):
                                    record["actor_kind"] = "automated_watch"
                                    record["origin_status"] = "excluded_automated"
                                elif human_origin == "verified_human":
                                    record["origin_status"] = "verified_human"
                                controlled_fields = (
                                    "episode_id", "episode_role", "quality_label", "score_source",
                                    "review_id", "context_pr_decision", "association_method",
                                    "annotation_confidence", "effective_association_confidence",
                                    "original_association_basis", "original_association_confidence",
                                )
                                for key in controlled_fields:
                                    value = _usage_label(annotation.get(key))
                                    if value is not None:
                                        record[key] = value
                                for key in ("context_associated_pr", "effective_associated_pr",
                                            "original_associated_pr"):
                                    if key not in annotation:
                                        continue
                                    value = annotation[key]
                                    if value is None:
                                        record[key] = None
                                    elif _safe_pr_id(value):
                                        record[key] = value
                                message_kinds = {
                                    "initial_task", "new_requirement/domain_judgment",
                                    "status_request", "continuation/followthrough_nudge",
                                }
                                if annotation.get("message_kind") in message_kinds:
                                    record["message_kind"] = annotation["message_kind"]
                                if isinstance(annotation.get("human_nudge_eligible"), bool):
                                    record["human_nudge_eligible"] = annotation["human_nudge_eligible"]
                                score = annotation.get("score")
                                if isinstance(score, (int, float)) and not isinstance(score, bool) and math.isfinite(score):
                                    record["score"] = score
                                binding = annotation.get("pr_binding")
                                if isinstance(binding, dict):
                                    pr_id = binding.get("pr")
                                    if _safe_pr_id(pr_id):
                                        record["pr_binding"] = {key: binding[key] for key in
                                            ("pr", "method", "weight") if key in binding and
                                            isinstance(binding[key], (str, int, float))}
                            automated = (
                                record.get("actor_kind") == "automated_watch"
                                or record.get("origin_status") == "excluded_automated"
                            )
                            if automated:
                                stats["automated_excluded_messages"] += 1
                            else:
                                stats["human_candidates"] += 1
                                stats["human_verified"] += record["origin_status"] == "verified_human"
                                stats["human_unannotated"] += annotation is None
                            humans.append(record)
                            exported.append(dict(record, record_type="human"))
            except (OSError, UnicodeError):
                stats["read_errors"] += 1
    errors = stats["missing_roots"] + stats["read_errors"] + stats["malformed_lines"]
    stats["status"] = "FAILED" if not stats["roots_available"] else "PARTIAL" if errors else "COMPLETE"
    stats["window_start"], stats["window_end"] = format_iso_utc(start), format_iso_utc(cutoff)
    if state_conn:
        state_conn.close()
    return dict(usage_records=usage, human_records=humans, export_records=exported, stats=stats)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history-root", action="append", required=True)
    parser.add_argument("--cutoff", required=True)
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--annotations")
    parser.add_argument("--state-db", help="Optional read-only Codex thread snapshot database")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    cutoff = _parse_utc_instant(args.cutoff)
    if cutoff is None:
        parser.error("--cutoff must include a UTC offset")
    data = collect_native_history(args.history_root, cutoff=cutoff, days=args.days, annotation_path=args.annotations, state_db=args.state_db)
    write_normalized_history(args.output, data["export_records"])
    Path(args.output + ".stats.json").write_text(json.dumps(data["stats"], sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(data["stats"], sort_keys=True))
    if data["stats"]["status"] == "FAILED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
