"""Attribute observations without treating names or read attempts as execution."""

from collections import Counter, defaultdict
from pathlib import Path


def event_excluded(event: dict, manifest: dict) -> bool:
    if event.get("session_id") in manifest.get("excluded_session_ids", []):
        return True
    cwd = event.get("cwd")
    if not cwd:
        return False
    path = Path(cwd).expanduser().resolve()
    return any(
        path.is_relative_to(Path(root).expanduser().resolve())
        for root in manifest.get("excluded_cwds", [])
    )


def scoped_rows(skills, events, legacy_rows, operator_notes):
    by_name = defaultdict(list)
    by_path = defaultdict(list)
    by_target = defaultdict(list)
    rows = {}
    for original in skills:
        identity = original.get("skill_id", original["skill"])
        rows[identity] = original
        by_name[original["skill"]].append(identity)
        by_path[str(Path(original["path"]).absolute())].append(identity)
        if original.get("resolved_target"):
            by_target[original["resolved_target"]].append(identity)
    selections, reads, name_only = Counter(), Counter(), Counter()
    selection_runtime, read_runtime = defaultdict(Counter), defaultdict(Counter)
    seen = set()
    observations = []
    for event in events:
        if event.get("kind") not in {"skill_selection", "skill_read"}:
            continue
        name = event.get("canonical_skill", event.get("selected_name"))
        path = event.get("selected_path")
        key = (
            event.get("runtime", "claude"),
            event["event_id"],
            event["kind"],
            path or name,
        )
        if key in seen:
            continue
        seen.add(key)
        matches = []
        if path:
            expanded = Path(path).expanduser()
            if not expanded.is_absolute() and event.get("cwd"):
                expanded = Path(event["cwd"]) / expanded
            if expanded.is_absolute():
                matches = by_path.get(str(expanded.absolute()), [])
                if not matches:
                    matches = by_target.get(str(expanded.resolve()), [])
        elif name:
            matches = by_name.get(name, [])
            # A bare invocation identifies a name, not its installed scope.
            if any("skill_id" in rows[identity] for identity in matches):
                name_only[name] += 1
                matches = []
        identity = matches[0] if len(matches) == 1 else None
        observations.append(
            {
                **event,
                "attributed_skill_id": identity,
                "attribution": "exact_path"
                if identity and path
                else "legacy_unique_name"
                if identity
                else "unresolved_scope",
            }
        )
        if identity is None:
            continue
        runtime = event.get("runtime", "claude")
        if event["kind"] == "skill_read":
            reads[identity] += 1
            read_runtime[identity][runtime] += 1
        else:
            selections[identity] += 1
            selection_runtime[identity][runtime] += 1
    result = []
    for identity, original in sorted(rows.items()):
        name = original["skill"]
        row = {**legacy_rows.get(name, {}), **original}
        confirmed = identity in operator_notes or (
            "skill_id" not in original and name in operator_notes
        )
        row.update(
            skill_id=identity,
            explicit_skill_selections=selections[identity],
            file_read_attempts=reads[identity],
            name_only_selection_events=name_only[name],
            claude_direct_events=selection_runtime[identity]["claude"],
            codex_direct_events=selection_runtime[identity]["codex"],
            claude_file_read_attempts=read_runtime[identity]["claude"],
            codex_file_read_attempts=read_runtime[identity]["codex"],
            operator_confirmed_use=confirmed,
            operator_note=operator_notes.get(identity, ""),
            positive_evidence=bool(selections[identity] or confirmed),
            archive_eligible_from_usage_alone=False,
            coverage_status="partial",
            static_reachability_scope_resolved=False,
        )
        row["no_evidence_in_source"] = not (
            selections[identity]
            or reads[identity]
            or name_only[name]
            or row.get("bfs_reachable")
            or row.get("reachable_from_commands")
            or confirmed
        )
        row["reachability_only"] = not (
            selections[identity] or reads[identity] or confirmed
        ) and bool(row.get("bfs_reachable") or row.get("reachable_from_commands"))
        row["usage_status"] = (
            "observed_selection"
            if selections[identity]
            else "operator_confirmed"
            if confirmed
            else "observed_read_attempt"
            if reads[identity]
            else "observed_name_scope_unknown"
            if name_only[name]
            else "no_observed_use_coverage_unknown"
        )
        result.append(row)
    return result, sorted(
        observations, key=lambda item: (item["timestamp"], item["event_id"])
    )
