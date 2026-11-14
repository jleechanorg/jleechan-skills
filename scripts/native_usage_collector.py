"""Recover native usage and prompt metadata from explicit history roots."""
import argparse
import hashlib
import io
import json
import math
import os
import re
import sqlite3
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

if __package__:
    from .prw_metrics import _parse_utc_instant, _safe_pr_id, _usage_count, _usage_label, format_iso_utc
    from .prw_session_bindings import binding_record_at as _session_binding_record_at, load as _load_session_bindings
else:
    from prw_session_bindings import binding_record_at as _session_binding_record_at, load as _load_session_bindings
    from prw_metrics import _parse_utc_instant, _safe_pr_id, _usage_count, _usage_label, format_iso_utc


def _apply_replay_annotation(record, annotation):
    actor_kind = annotation.get("actor_kind")
    human_origin = annotation.get("human_origin")
    if actor_kind == "unknown" or human_origin in ("unknown", "unverified_candidate"):
        record["actor_kind"] = "unknown"
        record["origin_status"] = "unverified_candidate"
    elif actor_kind in ("human", "automated_watch"):
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
    # Explicit null is a reviewed retraction; absent keys leave historical
    # metadata unchanged. Retractions apply before aggregation deduplicates IDs.
    for key in (
        "episode_id", "episode_role", "quality_label", "score_source", "review_id",
        "context_pr_decision", "association_method", "annotation_confidence",
        "effective_association_confidence", "original_association_basis",
        "original_association_confidence", "message_kind", "human_nudge_eligible",
        "score", "pr_binding",
    ):
        if key in annotation and annotation[key] is None:
            record.pop(key, None)
    for key in (
        "episode_id", "episode_role", "quality_label", "score_source", "review_id",
        "context_pr_decision", "association_method", "annotation_confidence",
        "effective_association_confidence", "original_association_basis",
        "original_association_confidence",
    ):
        value = _usage_label(annotation.get(key))
        if value is not None:
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


def _export_source_quality(path, start, cutoff):
    """Retain only source-quality fields from an export's companion receipt."""
    result = {"status": "UNKNOWN"}
    try:
        data = json.loads(Path(str(path) + ".stats.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        return result
    if not isinstance(data, dict):
        return result
    status = data.get("status")
    if status not in ("COMPLETE", "PARTIAL", "FAILED"):
        return result
    result["status"] = status
    for key in ("roots_requested", "roots_available", "missing_roots", "files_scanned",
                "duplicate_files", "malformed_lines", "read_errors"):
        value = data.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            result[key] = value
    for key in ("window_start", "window_end"):
        value = _parse_utc_instant(data.get(key))
        if value:
            result[key] = format_iso_utc(value)
    if status == "COMPLETE":
        source_start = _parse_utc_instant(result.get("window_start"))
        source_end = _parse_utc_instant(result.get("window_end"))
        if not source_start or not source_end:
            result["status"] = "UNKNOWN"
        elif (source_start > start or source_end < cutoff or result.get("missing_roots", 0)
              or result.get("malformed_lines", 0) or result.get("read_errors", 0)):
            result["status"] = "PARTIAL"
    return result


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
    stats["source_exports"] = [_export_source_quality(path, start, cutoff)]
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
                attributions = record.get("attributions") or []
                if any(isinstance(a, dict) and a.get("convention_ref") == "prw-session-binding.v1"
                       for a in attributions):
                    stats["session_bound_usage_records"] = stats.get("session_bound_usage_records", 0) + 1
                else:
                    stats["pr_bound_usage_records"] += bool(attributions)
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


def run_entire_parser(parser_argv, agent, source_bytes):
    """Normalize one native source with the caller-selected Entire facade."""
    if agent not in ("codex", "claude-code"):
        raise ValueError("Entire agent must be codex or claude-code")
    if isinstance(parser_argv, (str, Path)):
        parser_argv = [str(parser_argv)]
    if not isinstance(parser_argv, (list, tuple)) or not parser_argv:
        raise ValueError("Entire parser must be a non-empty argv")
    result = subprocess.run(
        [str(value) for value in parser_argv] + ["--agent", agent],
        input=source_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=600,
    )
    if result.returncode:
        raise RuntimeError(f"Entire parser failed with exit status {result.returncode}")
    rows = []
    for line_number, line in enumerate(result.stdout.splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except (ValueError, UnicodeError) as exc:
            raise ValueError(f"Entire parser output line {line_number} is invalid JSON") from exc
        if (not isinstance(row, dict) or row.get("v") != 1
                or row.get("type") not in ("user", "assistant")
                or "content" not in row):
            raise ValueError(f"Entire parser output line {line_number} has an invalid ETF v1 record")
        rows.append(row)
    return rows


def write_nudge_packets(path, records):
    """Write an explicitly requested, private model-input packet."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as descriptor:
        json.dump({"schema_version": "human-nudge-input.v1", "events": records},
                  descriptor, ensure_ascii=False, sort_keys=True)
        descriptor.write("\n")


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


def _history_text_blocks(value):
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [
            part if isinstance(part, str) else part.get("text", "")
            for part in value
            if isinstance(part, str) or (isinstance(part, dict) and isinstance(part.get("text"), str))
        ]
    return []


def _entire_records(rows, source_fingerprint, source_id, session_id, provider,
                    annotations, native_actor_evidence, session_git):
    effective_session_id = session_id or source_id
    sdk_id_counts = {}
    for row in rows:
        event_id = row.get("id")
        if isinstance(event_id, str) and event_id:
            sdk_id_counts[event_id] = sdk_id_counts.get(event_id, 0) + 1

    def matched_native_evidence(row, blocks):
        native_id = row.get("id")
        if native_id and sdk_id_counts.get(native_id) == 1:
            matches = [evidence for evidence in native_actor_evidence
                       if native_id in evidence["ids"]]
        else:
            matches = []
        if len(matches) != 1:
            timestamp = _parse_utc_instant(row.get("ts"))
            signature = (
                format_iso_utc(timestamp) if timestamp else None,
                hashlib.sha256("".join(blocks).encode("utf-8")).hexdigest(),
            )
            matches = [evidence for evidence in native_actor_evidence
                       if evidence["signature"] == signature]
            sdk_matches = 0
            for candidate in rows:
                if candidate.get("type") != "user":
                    continue
                candidate_time = _parse_utc_instant(candidate.get("ts"))
                candidate_sig = (
                    format_iso_utc(candidate_time) if candidate_time else None,
                    hashlib.sha256("".join(_history_text_blocks(candidate.get("content"))).encode("utf-8")).hexdigest(),
                )
                sdk_matches += candidate_sig == signature
            if sdk_matches != 1:
                return None
        return matches[0] if len(matches) == 1 else None

    candidates, occurrences = [], {}
    for index, row in enumerate(rows):
        if row.get("type") == "user":
            blocks = _history_text_blocks(row.get("content"))
            text = "".join(blocks)
            native_id = row.get("id") if isinstance(row.get("id"), str) and row.get("id") else None
            timestamp = _parse_utc_instant(row.get("ts"))
            identity = ("native:" + native_id) if native_id else (
                "fallback:" + (format_iso_utc(timestamp) if timestamp else "undated")
                + ":" + hashlib.sha256(text.encode("utf-8")).hexdigest()
            )
            occurrence = occurrences.get(identity, 0)
            occurrences[identity] = occurrence + 1
            namespace = hashlib.sha256(
                f"{provider}:{session_id or source_id}".encode("utf-8")
            ).hexdigest()
            event_id = "entire:" + namespace + ":" + hashlib.sha256(
                f"{identity}:{occurrence}".encode("utf-8")
            ).hexdigest()
            candidates.append((index, row, blocks, text, native_id, timestamp, event_id))
    result, packet = [], []
    for index, row, blocks, user_text, native_id, timestamp, event_id in candidates:
        normalized_timestamp = format_iso_utc(timestamp) if timestamp else None
        native_evidence = matched_native_evidence(row, blocks)
        native_human = native_evidence is not None and native_evidence["verified"]
        record = {
            "record_type": "human",
            "provider": provider,
            "session_id": effective_session_id,
            "source_fingerprint": source_fingerprint,
            "source_agent": row.get("agent") if isinstance(row.get("agent"), str) else None,
            "native_origin_status": "verified_human" if native_human else "unknown",
            "origin_status": "verified_human" if native_human else "unverified_candidate",
            "actor_kind": "human" if native_human else "unknown",
            "native_source_status": "stable_id" if native_id else "missing_event_id",
            "event_id": event_id,
            "event_id_source": "entire_adapter",
        }
        if native_id:
            record["native_event_id"] = native_id
        if native_evidence is not None:
            for key in ("repository", "git_branch", "commit_hash", "branch_source", "branch_basis"):
                value = native_evidence["git_metadata"].get(key)
                if value and not record.get(key):
                    record[key] = value
        for key in ("repository", "git_branch", "commit_hash", "branch_source", "branch_basis"):
            value = session_git.get(key)
            if value and not record.get(key):
                record[key] = value
        if normalized_timestamp:
            record["timestamp"] = normalized_timestamp
        else:
            record["native_timestamp_status"] = "missing_timestamp"
        annotation = annotations.get(event_id)
        if annotation is not None:
            _apply_replay_annotation(record, annotation)
        result.append(record)
        context = []
        for neighbor_index in range(max(0, index - 2), min(len(rows), index + 3)):
            if neighbor_index == index:
                continue
            neighbor = rows[neighbor_index]
            text_blocks = _history_text_blocks(neighbor.get("content"))
            if not text_blocks:
                continue
            context_record = {
                "role": neighbor.get("type"), "text": "".join(text_blocks),
                "text_blocks": text_blocks,
            }
            if isinstance(neighbor.get("id"), str):
                context_record["event_id"] = neighbor["id"]
            neighbor_timestamp = _parse_utc_instant(neighbor.get("ts"))
            if neighbor_timestamp:
                context_record["timestamp"] = format_iso_utc(neighbor_timestamp)
            context.append(context_record)
        packet.append({
            **record,
            "text": user_text,
            "text_blocks": blocks,
            "text_available": row.get("content") is not None,
            "context": context,
        })
    return result, packet


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
                           repository_map=None, state_db=None, session_bindings=None,
                           entire_parser=None, entire_agent=None):
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
    if entire_parser:
        stats.update(entire_parser_sources=0, entire_parser_errors=0,
                     entire_candidate_records=0, entire_source_coverage="UNVERIFIED",
                     entire_coverage_note=(
                         "SDK conversion may omit or merge native events; "
                         "source completeness is not reconciled"))
    stats["runtime_coverage"] = "Claude and Codex configured roots; other runtimes not collected"
    session_index = None
    if session_bindings:
        session_index, join_stats = _load_session_bindings(session_bindings)
        stats.update(join_stats, session_bound_usage_records=0)
    usage, humans, exported, packet_records, seen_files, seen_usage = [], [], [], [], set(), set()
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
            source_session_id = None
            native_actor_evidence = []
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
                        if source_session_id is None and isinstance(row.get("sessionId"), str):
                            source_session_id = _usage_label(row["sessionId"])
                        payload = row.get("payload", {})
                        if not isinstance(payload, dict):
                            continue
                        message = row.get("message", {})
                        message = message if isinstance(message, dict) else {}
                        native_item = payload.get("item", {})
                        native_item = native_item if isinstance(native_item, dict) else {}
                        native_claude_user = (
                            row.get("type") == "user" and message.get("role") == "user"
                        )
                        native_codex_user = (
                            (row.get("type") == "response_item" and payload.get("role") == "user")
                            or (row.get("type") == "event_msg" and payload.get("type") == "item_completed"
                                and native_item.get("role") == "user")
                        )
                        if native_claude_user or native_codex_user:
                            origin = row.get("origin", {})
                            origin = origin if isinstance(origin, dict) else {}
                            native_ids = {
                                value for value in (
                                    row.get("uuid"), row.get("promptId"), payload.get("id"),
                                    native_item.get("id"),
                                ) if isinstance(value, str) and value
                            }
                            native_at = _parse_utc_instant(row.get("timestamp"))
                            native_content = (
                                message.get("content") if native_claude_user
                                else native_item.get("content")
                            )
                            native_text = "".join(_history_text_blocks(native_content))
                            native_payload = {**payload, **native_item}
                            if "meta" in payload:
                                native_payload["meta"] = payload["meta"]
                            native_actor_evidence.append({
                                "ids": native_ids,
                                "signature": (
                                    format_iso_utc(native_at) if native_at else None,
                                    hashlib.sha256(native_text.encode("utf-8")).hexdigest(),
                                ),
                                "verified": (
                                    native_claude_user and (
                                        origin.get("kind") == "human"
                                        or row.get("turnOrigin") == "human"
                                        or row.get("userType") == "human"
                                    )
                                ),
                                "git_metadata": _git_metadata(row, native_payload, repository_map),
                            })
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
                entire_rows = None
                if entire_parser:
                    try:
                        entire_rows = run_entire_parser(entire_parser, entire_agent, content)
                        stats["entire_parser_sources"] += 1
                    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
                        stats["entire_parser_errors"] += 1
                        stats["read_errors"] += 1
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
                        codex_item = payload.get("item", {})
                        codex_item = codex_item if isinstance(codex_item, dict) else {}
                        codex_user = (
                            (kind == "response_item" and payload.get("role") == "user")
                            or (kind == "event_msg" and payload.get("type") == "item_completed"
                                and codex_item.get("role") == "user")
                        )
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
                            elif session_index is not None:
                                found = _session_binding_record_at(session_index, namespace, at)
                                if found:
                                    session_pr, ledger_ts, _source = found
                                    stats["session_bound_usage_records"] += 1
                                    record["attributions"] = [{"pr": session_pr, "weight": 1.0,
                                        "method": "convention", "convention_ref": "prw-session-binding.v1",
                                        "basis": "hook_session_binding",
                                        "receipt_refs": [f"prw-session-binding.v1:{namespace}:{session_pr}:{ledger_ts}"],
                                        "rationale": "session bound to this PR by the hook ledger"}]
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
                        elif not entire_parser:
                            aliases = []
                            event_id = _usage_label(
                                codex_item.get("id") if codex_user else None
                            ) or _usage_label(row.get("uuid") or row.get("promptId") or payload.get("id"))
                            for alias in (codex_item.get("id"), payload.get("id"), row.get("promptId"), row.get("uuid")):
                                alias = _usage_label(alias)
                                if alias and alias != event_id and alias not in aliases:
                                    aliases.append(alias)
                            event_id = event_id or namespace + ":" + str(ordinal)
                            origin = row.get("origin", {})
                            origin = origin if isinstance(origin, dict) else {}
                            verified = claude_user and (origin.get("kind") == "human" or row.get("turnOrigin") == "human" or row.get("userType") == "human")
                            record = dict(common, event_id=event_id,
                                          actor_kind="human" if verified else "unknown",
                                          origin_status="verified_human" if verified else "unverified_candidate")
                            if aliases:
                                record["event_id_aliases"] = aliases
                            if claude_user:
                                record["prompt_source"] = _usage_label(row.get("promptSource"))
                            annotation = annotations.get(event_id)
                            if annotation is None:
                                annotation = next((annotations[alias] for alias in aliases if alias in annotations), None)
                            if annotation is not None:
                                _apply_replay_annotation(record, annotation)
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
                if entire_rows is not None:
                    parsed, packet_rows = _entire_records(
                        entire_rows, fingerprint,
                        "source:" + hashlib.sha256(identity.encode()).hexdigest(),
                        session or source_session_id,
                        "openai" if entire_agent == "codex" else "anthropic", annotations,
                        native_actor_evidence, session_git,
                    )
                    for record, packet_record in zip(parsed, packet_rows):
                        at = _parse_utc_instant(record.get("timestamp"))
                        if at is None:
                            stats["undated_records"] += 1
                        elif not start <= at < cutoff:
                            stats["outside_window_records"] += 1
                        else:
                            humans.append(record)
                            exported.append(dict(record))
                            packet_records.append(packet_record)
                            automated = record.get("actor_kind") == "automated_watch" or record.get("origin_status") == "excluded_automated"
                            stats["automated_excluded_messages"] += bool(automated)
                            stats["human_candidates"] += not automated
                            stats["human_verified"] += record.get("origin_status") == "verified_human"
                            stats["human_unannotated"] += not automated and record.get("origin_status") != "verified_human"
                    stats["entire_candidate_records"] += len(parsed)
            except (OSError, UnicodeError):
                stats["read_errors"] += 1
    errors = stats["missing_roots"] + stats["read_errors"] + stats["malformed_lines"]
    if not stats["roots_available"]:
        stats["status"] = "FAILED"
    else:
        stats["status"] = "PARTIAL" if errors or entire_parser else "COMPLETE"
    stats["window_start"], stats["window_end"] = format_iso_utc(start), format_iso_utc(cutoff)
    if state_conn:
        state_conn.close()
    return dict(usage_records=usage, human_records=humans, export_records=exported,
                nudge_packet_events=packet_records, stats=stats)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history-root", action="append", required=True)
    parser.add_argument("--entire-parser", help="Entire parser executable; enables SDK human-message parsing")
    parser.add_argument("--entire-agent", choices=("codex", "claude-code"))
    parser.add_argument("--nudge-packets", help="Optional private human-nudge adjudication packet")
    parser.add_argument("--cutoff", required=True)
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--annotations")
    parser.add_argument("--state-db", help="Optional read-only Codex thread snapshot database")
    parser.add_argument("--session-bindings", action="append", default=None,
                        help="Session-to-PR binding ledger (JSONL); repeatable")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    cutoff = _parse_utc_instant(args.cutoff)
    if cutoff is None:
        parser.error("--cutoff must include a UTC offset")
    if args.entire_parser and not args.entire_agent:
        parser.error("--entire-parser requires --entire-agent")
    if args.nudge_packets and not args.entire_parser:
        parser.error("--nudge-packets requires --entire-parser")
    data = collect_native_history(args.history_root, cutoff=cutoff, days=args.days, annotation_path=args.annotations, state_db=args.state_db,
                                  session_bindings=args.session_bindings,
                                  entire_parser=args.entire_parser, entire_agent=args.entire_agent)
    write_normalized_history(args.output, data["export_records"])
    if args.nudge_packets:
        write_nudge_packets(args.nudge_packets, data["nudge_packet_events"])
    Path(args.output + ".stats.json").write_text(json.dumps(data["stats"], sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(data["stats"], sort_keys=True))
    if data["stats"]["status"] == "FAILED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
