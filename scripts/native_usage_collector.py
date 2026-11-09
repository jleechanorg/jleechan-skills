"""Recover native usage and prompt metadata from explicit history roots."""
import argparse
import hashlib
import json
import math
from datetime import timedelta
from pathlib import Path

if __package__:
    from .prw_metrics import _parse_utc_instant, _usage_count, _usage_label, format_iso_utc
else:
    from prw_metrics import _parse_utc_instant, _usage_count, _usage_label, format_iso_utc


def write_normalized_history(path, records):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in records), encoding="utf-8")


def collect_native_history(history_roots, *, cutoff, days=14, annotation_path=None):
    if cutoff.tzinfo is None or days <= 0:
        raise ValueError("An aware cutoff and positive window are required")
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
                 human_unannotated=0, pr_bound_usage_records=0)
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
            models, session = {}, None
            digest = hashlib.sha256()
            try:
                with path.open("rb") as stream:
                    for line in stream:
                        digest.update(line)
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
                        if row.get("type") == "turn_context" and payload.get("turn_id"):
                            models[payload["turn_id"]] = _usage_label(payload.get("model"))
                fingerprint = "sha256:" + digest.hexdigest()
                stats["files_scanned"] += 1
                with path.open(encoding="utf-8") as stream:
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
                        if claude_usage or codex_usage:
                            raw = payload["usage"] if codex_usage else message["usage"]
                            request = payload.get("response_id") or row.get("response_id") if codex_usage else row.get("requestId")
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
                            exported.append(dict(record, record_type="usage"))
                            stats["usage_records_in_window"] += 1
                        else:
                            event_id = _usage_label(payload.get("id") if codex_user else row.get("promptId") or row.get("uuid"))
                            event_id = event_id or namespace + ":" + str(ordinal)
                            origin = row.get("origin", {})
                            origin = origin if isinstance(origin, dict) else {}
                            verified = claude_user and (origin.get("kind") == "human" or row.get("turnOrigin") == "human" or row.get("userType") == "human")
                            record = dict(common, event_id=event_id,
                                          origin_status="verified_human" if verified else "unverified_candidate")
                            if claude_user:
                                record["prompt_source"] = _usage_label(row.get("promptSource"))
                            annotation = annotations.get(event_id)
                            if annotation:
                                if annotation.get("human_origin") == "verified_human":
                                    record["origin_status"] = "verified_human"
                                for key in ("episode_id", "episode_role", "quality_label", "score_source", "review_id"):
                                    value = _usage_label(annotation.get(key))
                                    if value is not None:
                                        record[key] = value
                                score = annotation.get("score")
                                if isinstance(score, (int, float)) and not isinstance(score, bool) and math.isfinite(score):
                                    record["score"] = score
                                binding = annotation.get("pr_binding")
                                if isinstance(binding, dict):
                                    record["pr_binding"] = {key: value for key, value in binding.items()
                                        if key in ("pr", "method", "weight") and isinstance(value, (str, int, float))}
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
    return dict(usage_records=usage, human_records=humans, export_records=exported, stats=stats)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history-root", action="append", required=True)
    parser.add_argument("--cutoff", required=True)
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--annotations")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    cutoff = _parse_utc_instant(args.cutoff)
    if cutoff is None:
        parser.error("--cutoff must include a UTC offset")
    data = collect_native_history(args.history_root, cutoff=cutoff, days=args.days, annotation_path=args.annotations)
    write_normalized_history(args.output, data["export_records"])
    Path(args.output + ".stats.json").write_text(json.dumps(data["stats"], sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(data["stats"], sort_keys=True))
    if data["stats"]["status"] == "FAILED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
