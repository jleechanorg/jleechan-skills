"""Send a private human-nudge packet to one caller-selected adjudicator."""

import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path


if __package__:
    from .prw_metrics import _safe_pr_id
else:
    from prw_metrics import _safe_pr_id


_PROMPTS = Path(__file__).parent / "prompts"
_INPUT_SCHEMA_VERSION = "human-nudge-input.v1"
_PRESERVED_ANNOTATION_FIELDS = {
    "episode_id", "episode_role", "quality_label", "score_source", "review_id",
    "context_pr_decision", "association_method", "annotation_confidence",
    "effective_association_confidence", "original_association_basis",
    "original_association_confidence", "context_associated_pr",
    "effective_associated_pr", "original_associated_pr", "score", "pr_binding",
    "association_scope", "associated_prs", "association_evidence",
}


def _load_packet(path):
    try:
        packet = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("input packet could not be read as JSON") from exc
    if (
        not isinstance(packet, dict)
        or packet.get("schema_version") != _INPUT_SCHEMA_VERSION
    ):
        raise ValueError("input packet has an unsupported schema")
    events = packet.get("events")
    if not isinstance(events, list):
        raise ValueError("input packet events must be an array")
    ids = []
    for event in events:
        if (
            not isinstance(event, dict)
            or not isinstance(event.get("event_id"), str)
            or not event["event_id"]
        ):
            raise ValueError("each input event must have a non-empty event_id")
        if (
            not isinstance(event.get("text"), str)
            or not isinstance(event.get("context"), list)
        ):
            raise ValueError("each input event must include text and context")
        ids.append(event["event_id"])
    if len(ids) != len(set(ids)):
        raise ValueError("input event IDs must be unique")
    return packet


def _judge(packet, command, timeout):
    argv = shlex.split(command)
    if not argv:
        raise ValueError("judge command is empty")
    response_schema = json.loads(
        (_PROMPTS / "human_nudge_adjudication.schema.json").read_text(
            encoding="utf-8"
        )
    )
    annotation_schema = response_schema["properties"]["annotations"]["items"]
    annotation_properties = annotation_schema["properties"]
    annotation_fields = set(annotation_properties)
    annotation_required = set(annotation_schema["required"])
    event_ids = [event["event_id"] for event in packet["events"]]
    value_schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {key: value for key, value in annotation_properties.items() if key != "event_id"},
        "required": [key for key in annotation_schema["required"] if key != "event_id"],
    }
    response_schema["properties"]["annotations"] = {
        "type": "object", "additionalProperties": False,
        "properties": {event_id: value_schema for event_id in event_ids},
        "required": event_ids,
    }
    request = {
        "prompt": (_PROMPTS / "human_nudge_adjudication.md").read_text(
            encoding="utf-8"
        ),
        "response_schema": response_schema,
        "packet": packet,
    }
    try:
        result = subprocess.run(
            argv, input=json.dumps(request, ensure_ascii=False), text=True,
            capture_output=True, timeout=timeout, check=False, shell=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError("judge command failed or timed out") from exc
    if result.returncode:
        raise ValueError("judge command returned a failure status")
    try:
        response = json.loads(result.stdout)
    except ValueError as exc:
        raise ValueError("judge response was not valid JSON") from exc
    if (
        not isinstance(response, dict)
        or not isinstance(response.get("annotations"), (dict, list))
    ):
        raise ValueError("judge response must contain annotations")
    expected_ids = set(event_ids)
    annotations = response["annotations"]
    if isinstance(annotations, dict):
        if set(annotations) != expected_ids:
            raise ValueError("judge response event IDs do not match the input packet")
        if any(not isinstance(value, dict) or "event_id" in value for value in annotations.values()):
            raise ValueError("judge annotation has an invalid keyed value")
        annotations = [{"event_id": event_id, **annotations[event_id]} for event_id in event_ids]
    events_by_id = {event["event_id"]: event for event in packet["events"]}
    received_ids = []
    normalized = []
    for annotation in annotations:
        if (
            not isinstance(annotation, dict)
            or not isinstance(annotation.get("event_id"), str)
        ):
            raise ValueError("judge annotation is missing an event_id")
        if set(annotation) - annotation_fields:
            raise ValueError("judge annotation contains unsupported fields")
        if not annotation_required.issubset(annotation):
            raise ValueError("judge annotation is missing required fields")
        for key, value in annotation.items():
            enum = annotation_properties[key].get("enum")
            if enum is not None and value not in enum:
                raise ValueError("judge annotation contains an unsupported label")
            accepted_types = annotation_properties[key].get("type")
            if accepted_types is not None:
                accepted_types = (
                    accepted_types if isinstance(accepted_types, list)
                    else [accepted_types]
                )
                valid_type = (
                    ("string" in accepted_types and isinstance(value, str))
                    or ("boolean" in accepted_types and isinstance(value, bool))
                    or ("null" in accepted_types and value is None)
                    or ("array" in accepted_types and isinstance(value, list))
                )
                if not valid_type:
                    raise ValueError("judge annotation has an invalid field type")
        association_keys = {"association_scope", "associated_prs", "association_evidence"}
        if association_keys & annotation.keys():
            if not association_keys <= annotation.keys():
                raise ValueError("judge association is incomplete")
            scope, prs, evidence = (annotation[k] for k in ("association_scope", "associated_prs", "association_evidence"))
            if (any(not _safe_pr_id(pr) for pr in prs) or len(set(prs)) != len(prs)
                    or any(not isinstance(item, str) or item not in {"conversation", "session_binding", "git_context", "prior_review"} for item in evidence)
                    or (scope == "single" and len(prs) != 1)
                    or (scope == "multi" and len(prs) < 2)
                    or (scope in ("global", "unknown") and prs)
                    or (prs and not evidence)):
                raise ValueError("judge association is invalid")
        received_ids.append(annotation["event_id"])
    if (
        len(received_ids) != len(set(received_ids))
        or set(received_ids) != expected_ids
    ):
        raise ValueError("judge response event IDs do not match the input packet")
    for annotation in annotations:
        output_annotation = {"event_id": annotation["event_id"]}
        output_annotation.update({
            key: value
            for key, value in events_by_id[annotation["event_id"]].items()
            if key in _PRESERVED_ANNOTATION_FIELDS
        })
        prior = events_by_id[annotation["event_id"]]
        legacy_multi = (prior.get("context_pr_decision") == "unassigned_multi_pr"
                        and not prior.get("pr_binding") and not prior.get("associated_prs")
                        and annotation.get("association_scope") == "multi")
        if not legacy_multi and (any(key in prior for key in ("context_pr_decision", "pr_binding"))
                or prior.get("association_retracted")
                or (prior.get("review_id") and "association_scope" in prior)):
            annotation = {k: v for k, v in annotation.items() if k not in {
                "association_scope", "associated_prs", "association_evidence"}}
        output_annotation.update(annotation)
        prior_review = prior.get("prior_review")
        if isinstance(prior_review, dict):
            for key in ("actor_kind", "human_origin", "message_kind", "human_nudge_eligible"):
                if key not in prior_review:
                    continue
                value = prior_review[key]
                if key == "human_origin":
                    allowed = ("verified_human", "unknown", "unverified_candidate", "automated_watch", "automated_watch_excluded", None)
                else:
                    allowed = annotation_properties[key]["enum"]
                    if key == "actor_kind":
                        allowed = [*allowed, None]
                if value in allowed and (key != "human_nudge_eligible" or value is None or isinstance(value, bool)):
                    output_annotation[key] = value
            if "human_origin" in output_annotation and "actor_kind" not in prior_review:
                output_annotation.pop("actor_kind", None)
        normalized.append(output_annotation)
    return normalized


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", required=True, help="Private human-nudge packet JSON"
    )
    parser.add_argument(
        "--judge-command", required=True,
        help="Caller-selected command; receives JSON on stdin",
    )
    parser.add_argument(
        "--output", required=True, help="Reviewed annotation JSONL destination"
    )
    parser.add_argument(
        "--timeout", type=float, default=180,
        help="Single judge-command timeout in seconds",
    )
    args = parser.parse_args(argv)
    try:
        packet = _load_packet(args.input)
        annotations = _judge(packet, args.judge_command, args.timeout)
        destination = Path(args.output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        fd = os.open(destination, flags, 0o600)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            for annotation in annotations:
                output.write(json.dumps(annotation, ensure_ascii=False) + "\n")
    except (OSError, ValueError) as exc:
        print(f"human-nudge adjudication failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
