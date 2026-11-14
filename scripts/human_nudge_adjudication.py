"""Send a private human-nudge packet to one caller-selected adjudicator."""

import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path


_PROMPTS = Path(__file__).parent / "prompts"
_INPUT_SCHEMA_VERSION = "human-nudge-input.v1"
_PRESERVED_ANNOTATION_FIELDS = {
    "episode_id", "episode_role", "quality_label", "score_source", "review_id",
    "context_pr_decision", "association_method", "annotation_confidence",
    "effective_association_confidence", "original_association_basis",
    "original_association_confidence", "context_associated_pr",
    "effective_associated_pr", "original_associated_pr", "score", "pr_binding",
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
        or not isinstance(response.get("annotations"), list)
    ):
        raise ValueError("judge response must contain an annotations array")
    annotations = response["annotations"]
    expected_ids = {event["event_id"] for event in packet["events"]}
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
                )
                if not valid_type:
                    raise ValueError("judge annotation has an invalid field type")
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
        output_annotation.update(annotation)
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
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            for annotation in annotations:
                output.write(json.dumps(annotation, ensure_ascii=False) + "\n")
        os.chmod(destination, 0o600)
    except (OSError, ValueError) as exc:
        print(f"human-nudge adjudication failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
