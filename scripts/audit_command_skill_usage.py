#!/usr/bin/env python3
"""Analyze command and skill telemetry with BFS reachability closure and independent evidence tiers."""

from __future__ import annotations

import argparse
import base64
import binascii
import csv
import datetime as dt
import hashlib
import json
import re
from collections import Counter, defaultdict, deque
from pathlib import Path

try:
    from scripts.scoped_skill_usage import event_excluded, scoped_rows
except ModuleNotFoundError:
    from scoped_skill_usage import event_excluded, scoped_rows

SLASH_TOKEN_RE = re.compile(
    r"(?<![\w/])/((?:extended-library:)?[A-Za-z][A-Za-z0-9_-]*)(?![\w/])"
)
FILE_EXT_RE = re.compile(
    r"\.(sh|md|py|json|jsonl|ya?ml|dot|txt|log|toml|ts|js|html|png|mp4)\b"
)
SKILL_REF_RE = re.compile(
    r"(?:skills/|\.claude/skills/|~/\.claude/skills/|~/\.hermes/skills/|\$\{CLAUDE_HOME[^}]*\}/skills/)([A-Za-z0-9_-]+)"
)
SKILL_TOOL_CALL_RE = re.compile(r"""Skill\(\s*["']([A-Za-z0-9_-]+)["']\s*\)""")
ALIAS_PROSE_RE = re.compile(
    r"(?:Alias for|Shortcut alias for|points to|alias of)\s+[`/]?([A-Za-z0-9_-]+(?::[A-Za-z0-9_-]+)?)[`]?",
    re.IGNORECASE,
)

REQUIRED_SCANNER_SOURCE_HASHES = frozenset(
    {
        "scripts/audit_command_skill_usage.py",
        "scripts/capture_command_skill_usage.py",
        "scripts/scoped_skill_usage.py",
        "scripts/skill_read_telemetry.py",
    }
)
REQUIRED_CAPTURE_SOURCE_HASHES = frozenset(
    {
        "scripts/capture_command_skill_usage.py",
        "scripts/scoped_skill_usage.py",
        "scripts/skill_read_telemetry.py",
    }
)

NON_COMMAND_TOKENS: dict[str, str] = {
    "tmp": "filesystem path prefix (/tmp/<project-slug>/...), not a command",
    "rate-limit-options": "Claude Code built-in TUI modal, not a repo command",
    "STATE": "mid-path segment from `/tmp/.../STATE.md`, not a command",
    "workflows": "Claude Code built-in Workflow-tool run viewer UI surface, not a repo command file",
    "code": "path fragment from `.../code-quality/`, not a command",
    "config": "path fragment from `~/.claude/teams/session-*/config.json`, not a command",
    "no": "prose false-positive from 'main/no branch', not a command",
    "install": "path fragment of `./install.sh`, not a delegation",
    "reviewer": "slash used as or-separator in `reviewer/subagent` or path segment, not a delegation",
    "pipeline": "Workflow-tool API notation `agent()/parallel()/pipeline()`, not a command",
}

BUILTIN_ALIASES: dict[str, str] = {
    "sq": "superpowers-quick",
    "ds": "document-standards",
    "wa": "web-advice",
    "webadvice": "web-advice",
    "af": "auto-factory",
    "aar": "accept-adapt-reject",
    "es": "evidence-standards",
    "er": "evidence-review",
    "rg": "redgreen",
    "ms": "memory-search",
    "f": "factory",
    "diskm": "disk_magician",
    "meta": "harness-postmortem",
    "parallel": "parallelize-to-ceiling",
    "history": "conversation-history-sparse",
}


def digest(data: bytes | str) -> str:
    return hashlib.sha256(data.encode() if isinstance(data, str) else data).hexdigest()


def parse_time(raw: object) -> dt.datetime | None:
    if not isinstance(raw, str):
        return None
    try:
        return dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_frontmatter(text: str) -> dict[str, object]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    fields: dict[str, object] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return fields
        key, separator, value = line.partition(":")
        if separator and not key.startswith((" ", "\t")):
            k = key.strip()
            v = value.strip()
            if v.startswith("[") and v.endswith("]"):
                items = [item.strip(" '\"") for item in v[1:-1].split(",") if item.strip()]
                fields[k] = items
            else:
                fields[k] = v
    return {}


def _get_containing_word(text: str, start: int, end: int) -> str:
    w_start = start
    while w_start > 0 and not text[w_start - 1].isspace():
        w_start -= 1
    w_end = end
    while w_end < len(text) and not text[w_end].isspace():
        w_end += 1
    return text[w_start:w_end]


def extract_references_from_text(text: str) -> set[str]:
    candidates: set[str] = set()
    for match in SLASH_TOKEN_RE.finditer(text):
        word = _get_containing_word(text, match.start(), match.end())
        if FILE_EXT_RE.search(word):
            continue
        if word.count("/") >= 2:
            continue
        if "~/" in word or "./" in word or "../" in word:
            continue
        token = match.group(1)
        if token not in NON_COMMAND_TOKENS:
            candidates.add(token)
    return candidates


def extract_skill_references_from_text(text: str) -> set[str]:
    candidates: set[str] = set()
    for match in SKILL_REF_RE.finditer(text):
        candidates.add(match.group(1))
    for match in SKILL_TOOL_CALL_RE.finditer(text):
        candidates.add(match.group(1))
    return candidates


def build_full_reachability_graph(
    repo_root: Path, commands: list[dict], skills: list[dict]
) -> tuple[dict[str, set[str]], dict[str, set[str]], dict[str, set[str]], dict[str, set[str]], dict[str, str]]:
    """Extract full directed bipartite reference graph between commands and skills."""
    known_commands = {row["command"] for row in commands}
    base_to_canonical = {row["base_name"]: row["command"] for row in commands if "base_name" in row}
    known_skills = {row["skill"] for row in skills}
    alias_map: dict[str, str] = dict(BUILTIN_ALIASES)

    cmd_to_cmds: dict[str, set[str]] = defaultdict(set)
    cmd_to_skills: dict[str, set[str]] = defaultdict(set)
    skill_to_skills: dict[str, set[str]] = defaultdict(set)
    skill_to_cmds: dict[str, set[str]] = defaultdict(set)

    for row in commands:
        cmd_name = row["command"]
        text = inventory_text(row)
        fm = parse_frontmatter(text)

        # Parse frontmatter aliases
        fm_aliases = fm.get("aliases")
        if isinstance(fm_aliases, list):
            for a in fm_aliases:
                alias_map[str(a)] = cmd_name
        elif isinstance(fm.get("alias"), str):
            alias_map[str(fm["alias"])] = cmd_name

        # Parse prose aliases
        prose_match = ALIAS_PROSE_RE.search(text)
        if prose_match:
            target = prose_match.group(1)
            if target in known_commands:
                alias_map[row.get("base_name", cmd_name)] = target
                cmd_to_cmds[cmd_name].add(target)
            elif target in base_to_canonical:
                alias_map[row.get("base_name", cmd_name)] = base_to_canonical[target]
                cmd_to_cmds[cmd_name].add(base_to_canonical[target])

        # Extract referenced commands
        for cand in extract_references_from_text(text):
            if cand in known_commands:
                cmd_to_cmds[cmd_name].add(cand)
            elif cand in base_to_canonical:
                cmd_to_cmds[cmd_name].add(base_to_canonical[cand])

        # Extract referenced skills
        for s in extract_skill_references_from_text(text):
            if s in known_skills:
                cmd_to_skills[cmd_name].add(s)

    for row in skills:
        skill_name = row["skill"]
        text = inventory_text(row)
        for s in extract_skill_references_from_text(text):
            if s in known_skills and s != skill_name:
                skill_to_skills[skill_name].add(s)
        for c in extract_references_from_text(text):
            if c in known_commands:
                skill_to_cmds[skill_name].add(c)
            elif c in base_to_canonical:
                skill_to_cmds[skill_name].add(base_to_canonical[c])

    # Add canonical fallback links
    if "harness" in known_commands or "harness" in base_to_canonical:
        h_cmd = base_to_canonical.get("harness", "harness")
        if "harness-engineering" in known_skills:
            cmd_to_skills[h_cmd].add("harness-engineering")
        if "harness-postmortem" in known_skills:
            cmd_to_skills[h_cmd].add("harness-postmortem")

    if "disk_magician" in base_to_canonical:
        d_cmd = base_to_canonical["disk_magician"]
        if "disk-magician" in known_skills:
            cmd_to_skills[d_cmd].add("disk-magician")

    if "callpath" in base_to_canonical:
        cp_cmd = base_to_canonical["callpath"]
        if "callpath" in known_skills:
            cmd_to_skills[cp_cmd].add("callpath")

    if "code-standards" in base_to_canonical:
        cs_cmd = base_to_canonical["code-standards"]
        if "code-standards" in known_skills:
            cmd_to_skills[cs_cmd].add("code-standards")
        if "code-centralization" in known_skills:
            cmd_to_skills[cs_cmd].add("code-centralization")

    if "cmux-steer" in base_to_canonical:
        cm_cmd = base_to_canonical["cmux-steer"]
        if "cmux-steer" in known_skills:
            cmd_to_skills[cm_cmd].add("cmux-steer")

    if "wiki-search" in known_commands or "wiki-search" in base_to_canonical:
        ws_cmd = base_to_canonical.get("wiki-search", "wiki-search")
        if "wiki-search" in known_skills:
            cmd_to_skills[ws_cmd].add("wiki-search")

    return cmd_to_cmds, cmd_to_skills, skill_to_skills, skill_to_cmds, alias_map


def compute_bfs_closure(
    observed_cmds: set[str],
    observed_skills: set[str],
    all_commands: set[str],
    all_skills: set[str],
    cmd_to_cmds: dict[str, set[str]],
    cmd_to_skills: dict[str, set[str]],
    skill_to_skills: dict[str, set[str]],
    skill_to_cmds: dict[str, set[str]],
    alias_map: dict[str, str],
) -> tuple[set[str], set[str], dict[str, list[str]], dict[str, list[str]]]:
    """Run full Breadth-First Search closure from observed commands and skills.

    Every set is walked in sorted order.  Reachability reasons record the first
    parent to claim a node, so unordered iteration made that attribution depend
    on per-process string hash randomization and two runs over the same frozen
    snapshot could disagree.
    """
    queue = deque()
    reachable_cmds = set(observed_cmds)
    reachable_skills = set(observed_skills)
    cmd_reach_reasons: dict[str, list[str]] = defaultdict(list)
    skill_reach_reasons: dict[str, list[str]] = defaultdict(list)

    for c in sorted(observed_cmds):
        queue.append(("cmd", c))
        cmd_reach_reasons[c].append("direct telemetry seed")
    for s in sorted(observed_skills):
        queue.append(("skill", s))
        skill_reach_reasons[s].append("direct tool-selection seed")

    while queue:
        kind, item = queue.popleft()
        if kind == "cmd":
            # Alias expansion
            if item in alias_map:
                target = alias_map[item]
                if target in all_commands and target not in reachable_cmds:
                    reachable_cmds.add(target)
                    cmd_reach_reasons[target].append(f"alias from /{item}")
                    queue.append(("cmd", target))
                if target in all_skills and target not in reachable_skills:
                    reachable_skills.add(target)
                    skill_reach_reasons[target].append(f"alias from /{item}")
                    queue.append(("skill", target))

            # Outgoing command edges
            for next_c in sorted(cmd_to_cmds.get(item, ())):
                if next_c not in reachable_cmds:
                    reachable_cmds.add(next_c)
                    cmd_reach_reasons[next_c].append(f"invoked by /{item}")
                    queue.append(("cmd", next_c))

            # Outgoing skill edges
            for next_s in sorted(cmd_to_skills.get(item, ())):
                if next_s not in reachable_skills:
                    reachable_skills.add(next_s)
                    skill_reach_reasons[next_s].append(f"called by /{item}")
                    queue.append(("skill", next_s))

        elif kind == "skill":
            # Skill-to-skill edges
            for next_s in sorted(skill_to_skills.get(item, ())):
                if next_s not in reachable_skills:
                    reachable_skills.add(next_s)
                    skill_reach_reasons[next_s].append(f"referenced by skill:{item}")
                    queue.append(("skill", next_s))

            # Skill-to-command edges
            for next_c in sorted(skill_to_cmds.get(item, ())):
                if next_c not in reachable_cmds:
                    reachable_cmds.add(next_c)
                    cmd_reach_reasons[next_c].append(f"invoked by skill:{item}")
                    queue.append(("cmd", next_c))

    return reachable_cmds, reachable_skills, dict(cmd_reach_reasons), dict(skill_reach_reasons)


def load_bound_json(base: Path, manifest: dict, path_key: str, hash_key: str) -> dict:
    frozen_path = base / manifest[path_key]
    if not frozen_path.is_file():
        raise ValueError(f"missing mandatory frozen input: {frozen_path}")
    if digest(frozen_path.read_bytes()) != manifest.get(hash_key):
        raise ValueError(f"frozen input hash mismatch: {frozen_path}")
    payload = json.loads(frozen_path.read_text())
    if payload.get("snapshot_id") != manifest["snapshot_id"]:
        raise ValueError(f"snapshot_id mismatch: {frozen_path}")
    return payload


# sha256 of the empty document. An empty inventory row may attest this or
# nothing at all; anything else is a digest borrowed from another document.
EMPTY_DIGEST = digest(b"")


def inventory_text(row: dict) -> str:
    """Return the attested bytes for an inventory row as text.

    The snapshot is a frozen input, so a row produced by a current capture is
    served from the snapshot and never re-read from disk, whatever its size.
    Against such a snapshot the audit is a pure function of its frozen inputs
    and immune to writes landing under the inventory roots between the capture
    and audit phases.  Bytes are only trusted when the row also attests their
    digest.

    ``resolved_target`` is deliberately not re-checked on this path: symlink
    identity was resolved and recorded at capture time, and consulting the live
    target would reintroduce the very filesystem dependency being removed.

    Rows from snapshots captured before this contract carry no
    ``content_encoding`` and keep the original live-read drift guard, so
    replaying a historical snapshot still depends on a quiet filesystem.
    """
    path = Path(row["path"])
    expected = row.get("content_sha256")
    if "content_encoding" in row:
        if row["content_encoding"] != "base64":
            raise ValueError(f"inventory content drift: {path}")
        encoded = row.get("content_b64")
        if not isinstance(encoded, str):
            raise ValueError(f"inventory content drift: {path}")
        try:
            content = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error):
            raise ValueError(f"inventory content drift: {path}") from None
        if not row.get("content_captured", True):
            # Capture could not read this file, so the row attests nothing and
            # must carry nothing. The flag is not a way past the checks below,
            # and the live filesystem is not a substitute for bytes never read.
            if content or expected:
                raise ValueError(f"inventory content drift: {path}")
            return ""
        if content:
            # Bytes are trusted only alongside a digest that matches them.
            if not expected:
                raise ValueError(
                    f"inventory content drift: missing attestation for {path}"
                )
            if digest(content) != expected:
                raise ValueError(f"inventory content drift: {path}")
        elif expected and expected != EMPTY_DIGEST:
            # An empty document may attest its own digest or none at all; a
            # digest belonging to some other document is drift.
            raise ValueError(f"inventory content drift: {path}")
        return content.decode("utf-8", errors="replace")
    try:
        content = path.read_bytes()
    except OSError:
        if expected:
            raise ValueError(f"inventory content drift: missing {path}")
        return ""
    if expected and digest(content) != expected:
        raise ValueError(f"inventory content drift: {path}")
    if row.get("resolved_target") and str(path.resolve()) != row["resolved_target"]:
        raise ValueError(f"inventory target drift: {path}")
    return content.decode("utf-8", errors="replace")


def verify_source_hashes(
    manifest: dict, key: str, source_root: Path, label: str
) -> None:
    values = manifest.get(key, {})
    if not isinstance(values, dict):
        raise TypeError(f"{label} source hashes must be a mapping")
    for relative, expected in values.items():
        candidate = (source_root / relative).resolve(strict=False)
        if not candidate.is_relative_to(source_root):
            raise ValueError(
                f"{label} source hash path escapes source root: {relative}"
            )
        try:
            actual = digest(candidate.read_bytes())
        except OSError as exc:
            raise ValueError(f"{label} source is unavailable: {relative}") from exc
        if actual != expected:
            raise ValueError(f"{label} source hash does not match manifest: {relative}")


def source_provenance_status(
    manifest: dict, source_root: Path, ignore_scanner_hash: bool
) -> str:
    """Verify source bindings and return an explicit status for the output."""
    if ignore_scanner_hash:
        return "unverified_explicit_override"

    verify_source_hashes(manifest, "scanner_source_sha256", source_root, "scanner")
    verify_source_hashes(manifest, "capture_source_sha256", source_root, "capture")
    scanner_hashes = manifest.get("scanner_source_sha256", {})
    capture_hashes = manifest.get("capture_source_sha256", {})
    scanner_keys = set(scanner_hashes) if isinstance(scanner_hashes, dict) else set()
    capture_keys = set(capture_hashes) if isinstance(capture_hashes, dict) else set()
    complete = (
        scanner_keys == REQUIRED_SCANNER_SOURCE_HASHES
        and capture_keys == REQUIRED_CAPTURE_SOURCE_HASHES
    )
    if manifest.get("schema") == "claude_usage_audit_manifest.v3":
        if not complete:
            raise ValueError("complete source hash maps are required for manifest v3")
        return "verified"
    if complete:
        return "verified"
    if not scanner_keys and not capture_keys and not manifest.get("scanner_sha256"):
        return "unverified_legacy_missing_source_hashes"
    return "unverified_legacy_incomplete_source_hashes"


def audit(
    manifest_path: Path,
    output_dir: Path,
    repo_root: Path | None = None,
    operator_confirmations: dict[str, str] | None = None,
    ignore_scanner_hash: bool = False,
) -> dict:
    manifest = json.loads(manifest_path.read_text())
    start = parse_time(manifest["window_start_inclusive"])
    end = parse_time(manifest["window_end_exclusive"])
    if (
        start is None
        or end is None
        or start.utcoffset() != dt.timedelta(0)
        or end.utcoffset() != dt.timedelta(0)
        or end - start != dt.timedelta(days=30)
    ):
        raise ValueError("manifest must define one exact 30-day UTC window")

    if (
        not ignore_scanner_hash
        and manifest.get("scanner_sha256")
        and digest(Path(__file__).read_bytes()) != manifest.get("scanner_sha256")
    ):
        raise ValueError("scanner hash does not match manifest")
    source_root = Path(__file__).resolve().parents[1]
    provenance_status = source_provenance_status(
        manifest, source_root, ignore_scanner_hash
    )

    base = manifest_path.parent
    root = repo_root or base
    inventory = load_bound_json(base, manifest, "inventory_snapshot", "inventory_snapshot_sha256")
    corpus = load_bound_json(base, manifest, "normalized_event_corpus", "normalized_event_corpus_sha256")
    if (
        corpus.get("window_start_inclusive") != manifest["window_start_inclusive"]
        or corpus.get("window_end_exclusive") != manifest["window_end_exclusive"]
    ):
        raise ValueError("normalized corpus window does not match manifest")
    if "exclusions" in corpus:
        current_exclusions = {
            "excluded_session_ids": sorted(
                {str(item) for item in manifest.get("excluded_session_ids", [])}
            ),
            "excluded_cwds": sorted(
                {
                    str(Path(item).expanduser().resolve(strict=False))
                    for item in manifest.get("excluded_cwds", [])
                    if isinstance(item, str)
                }
            ),
        }
        if any(
            corpus["exclusions"].get(key, []) != value
            for key, value in current_exclusions.items()
        ):
            raise ValueError("normalized corpus exclusions do not match manifest")

    commands = inventory["commands"]
    skills = inventory["skills"]
    command_names = [row["command"] for row in commands]
    skill_names = [row.get("skill_id", row["skill"]) for row in skills]
    if len(command_names) != len(set(command_names)) or len(skill_names) != len(set(skill_names)):
        raise ValueError("duplicate identity in inventory snapshot")

    exclusions = manifest.get("excluded_command_documents", {})
    for row in commands:
        cmd_id = row["command"]
        base_id = row.get("base_name", cmd_id)
        is_excl = cmd_id in exclusions or base_id in exclusions
        if row.get("callable") != (not is_excl):
            raise ValueError(f"command callable mismatch: {cmd_id}")

    callable_names = {row["command"] for row in commands if row.get("callable", True)}
    base_to_canonical = {
        row.get("base_name", row["command"]): row["command"]
        for row in commands
        if row.get("callable", True)
    }
    active_skills = {row["skill"] for row in skills}

    # Extract reference graph
    cmd_to_cmds, cmd_to_skills, skill_to_skills, skill_to_cmds, alias_map = build_full_reachability_graph(
        root, commands, skills
    )

    operator_notes = operator_confirmations or manifest.get("operator_confirmations", {})

    # Evidence Counters
    command_counts: dict[str, Counter] = defaultdict(Counter)
    skill_counts: Counter = Counter()
    skill_alias_counts: Counter = Counter()

    command_events: dict[tuple[str, str], dict] = {}
    skill_events: dict[tuple[str, str], dict] = {}

    analysis = Counter(
        {
            "duplicate_skill_events_suppressed": 0,
            "ambiguous_multi_command_tag_records_suppressed": 0,
            "duplicate_command_branch_events_suppressed": 0,
            "ambiguous_cross_branch_command_records_suppressed": 0,
            "alias_resolved_events_attributed": 0,
        }
    )
    command_runtime_counts: dict[str, Counter] = defaultdict(Counter)
    skill_runtime_counts: dict[str, Counter] = defaultdict(Counter)

    retained_events = [event for event in corpus["events"] if not event_excluded(event, manifest)]
    analysis["excluded_observations"] = len(corpus["events"]) - len(retained_events)
    for event in retained_events:
        rt = event.get("runtime", "claude")
        stamp = parse_time(event.get("timestamp"))
        if stamp is None or not (start <= stamp < end):
            raise ValueError(f"normalized event outside bound window: {event.get('event_id')}")

        if event.get("kind") == "skill_read":
            continue  # Path-qualified read attempts are attributed separately below.

        # Explicit Skill Selection
        if event.get("kind") == "skill_selection":
            name = event["selected_name"]
            key = (rt, event["event_id"], name)
            if key in skill_events:
                analysis["duplicate_skill_events_suppressed"] += 1
                continue
            canonical_skill = name
            if canonical_skill not in active_skills and name in alias_map:
                resolved = alias_map[name]
                if resolved in active_skills:
                    canonical_skill = resolved
            skill_events[key] = {
                **event,
                "canonical_skill": canonical_skill,
                "active_at_capture": canonical_skill in active_skills,
            }
            if canonical_skill in active_skills:
                skill_counts[canonical_skill] += 1
                skill_runtime_counts[canonical_skill][rt] += 1
            else:
                skill_alias_counts[name] += 1
            continue

        if event.get("kind") != "command_candidate":
            raise ValueError(f"unknown normalized event kind: {event.get('kind')}")

        matches: list[tuple[str, str, str]] = []  # (target_cmd, branch_type, original_token)
        if event.get("entrypoint") == "cli":
            tags = set(event.get("distinct_command_tags") or [])
            valid_tags = []
            for t in tags:
                if t in callable_names:
                    valid_tags.append((t, t))
                elif t in base_to_canonical:
                    valid_tags.append((base_to_canonical[t], t))
                elif t in alias_map:
                    target = alias_map[t]
                    if target in callable_names:
                        valid_tags.append((target, t))
                    elif target in base_to_canonical:
                        valid_tags.append((base_to_canonical[target], t))

            if len(valid_tags) == 1:
                target_cmd, orig_tok = valid_tags[0]
                branch = "canonical_tag_direct_cli" if orig_tok in callable_names or orig_tok in base_to_canonical else "alias_tag_direct_cli"
                matches.append((target_cmd, branch, orig_tok))
            elif len(valid_tags) > 1:
                analysis["ambiguous_multi_command_tag_records_suppressed"] += 1

        leading = event.get("leading_slash")
        if event.get("prompt_source") in {"typed", "queued"} and event.get("origin_kind") == "human" and leading:
            if leading in callable_names:
                matches.append((leading, "typed_or_queued_human_leading_slash", leading))
            elif leading in base_to_canonical:
                matches.append((base_to_canonical[leading], "typed_or_queued_human_leading_slash", leading))
            elif leading in alias_map:
                target = alias_map[leading]
                if target in callable_names:
                    matches.append((target, "alias_resolved_human_leading_slash", leading))
                elif target in base_to_canonical:
                    matches.append((base_to_canonical[target], "alias_resolved_human_leading_slash", leading))

        # Check embedded slash tokens if no tag or leading slash matched
        if not matches and event.get("prompt_source") in {"typed", "queued"} and event.get("origin_kind") == "human":
            for tok in (event.get("embedded_slash_tokens") or []):
                if tok in callable_names:
                    matches.append((tok, "typed_or_queued_human_embedded_slash", tok))
                elif tok in base_to_canonical:
                    matches.append((base_to_canonical[tok], "typed_or_queued_human_embedded_slash", tok))
                elif tok in alias_map:
                    target = alias_map[tok]
                    if target in callable_names:
                        matches.append((target, "alias_resolved_human_embedded_slash", tok))
                    elif target in base_to_canonical:
                        matches.append((base_to_canonical[target], "alias_resolved_human_embedded_slash", tok))

        matched_targets = {target for target, _, _ in matches}
        if len(matched_targets) > 1:
            analysis["ambiguous_cross_branch_command_records_suppressed"] += 1
            continue

        for target_cmd, branch, orig_tok in matches:
            key = (event["event_id"], target_cmd)
            selected = command_events.setdefault(
                key,
                {
                    "event_id": event["event_id"],
                    "timestamp": event["timestamp"],
                    "command": target_cmd,
                    "runtime": rt,
                    "branches": [],
                    "original_tokens": [],
                },
            )
            if branch in selected["branches"]:
                analysis["duplicate_command_branch_events_suppressed"] += 1
                continue
            selected["branches"].append(branch)
            selected["original_tokens"].append(orig_tok)
            command_counts[target_cmd][branch] += 1
            command_runtime_counts[target_cmd][rt] += 1
            if "alias" in branch:
                analysis["alias_resolved_events_attributed"] += 1

    for event in command_events.values():
        command_counts[event["command"]]["unique_events"] += 1

    # Run BFS closure starting from observed commands and skills
    observed_cmds_set = {
        name for name in callable_names if command_counts[name]["unique_events"] > 0 or name in operator_notes
    }
    observed_skills_set = {
        name for name in active_skills if skill_counts[name] > 0 or name in operator_notes
    }

    bfs_cmds, bfs_skills, cmd_reasons, skill_reasons = compute_bfs_closure(
        observed_cmds_set,
        observed_skills_set,
        callable_names,
        active_skills,
        cmd_to_cmds,
        cmd_to_skills,
        skill_to_skills,
        skill_to_cmds,
        alias_map,
    )

    # Precompute static skill-to-commands reverse map
    skill_to_static_cmds: dict[str, set[str]] = defaultdict(set)
    for c, sks in cmd_to_skills.items():
        for s in sks:
            skill_to_static_cmds[s].add(c)

    command_by_name = {row["command"]: row for row in commands}
    skill_by_name = {row["skill"]: row for row in skills}

    command_rows = []
    for name in sorted(callable_names):
        row = dict(command_by_name[name])
        direct_cli = command_counts[name]["canonical_tag_direct_cli"]
        human_slash = (
            command_counts[name]["typed_or_queued_human_leading_slash"]
            + command_counts[name]["typed_or_queued_human_embedded_slash"]
        )
        alias_events = (
            command_counts[name]["alias_tag_direct_cli"]
            + command_counts[name]["alias_resolved_human_leading_slash"]
            + command_counts[name]["alias_resolved_human_embedded_slash"]
        )
        unique_events = command_counts[name]["unique_events"]
        op_confirmed = name in operator_notes
        is_bfs_reachable = name in bfs_cmds
        statically_reachable_skills = sorted(cmd_to_skills.get(name, set()))

        row["canonical_direct_events"] = direct_cli + human_slash
        row["alias_resolved_events"] = alias_events
        row["total_observed_events"] = unique_events
        row["claude_direct_events"] = command_runtime_counts[name]["claude"]
        row["codex_direct_events"] = command_runtime_counts[name]["codex"]
        row["reachable_skills"] = statically_reachable_skills
        row["bfs_reachable"] = is_bfs_reachable
        row["reachability_reasons"] = cmd_reasons.get(name, [])
        row["operator_confirmed_use"] = op_confirmed
        row["operator_note"] = operator_notes.get(name, "")
        row["no_evidence_in_source"] = (unique_events == 0 and not is_bfs_reachable and not op_confirmed)
        row["positive_evidence"] = (unique_events > 0 or op_confirmed)
        # CRITICAL INVARIANT: Archive eligibility is NEVER derived from telemetry absence
        row["archive_eligible_from_usage_alone"] = False
        command_rows.append(row)

    skill_rows = []
    for name in sorted(active_skills):
        row = dict(skill_by_name[name])
        direct_selections = skill_counts[name]
        op_confirmed = name in operator_notes
        is_bfs_reachable = name in bfs_skills
        reached_by_cmds = sorted(skill_to_static_cmds.get(name, set()))

        row["explicit_skill_selections"] = direct_selections
        row["claude_direct_events"] = skill_runtime_counts[name]["claude"]
        row["codex_direct_events"] = skill_runtime_counts[name]["codex"]
        row["reachable_from_commands"] = reached_by_cmds
        row["bfs_reachable"] = is_bfs_reachable
        row["reachability_reasons"] = skill_reasons.get(name, [])
        row["reachability_only"] = (direct_selections == 0 and (is_bfs_reachable or len(reached_by_cmds) > 0))
        row["operator_confirmed_use"] = op_confirmed
        row["operator_note"] = operator_notes.get(name, "")
        row["no_evidence_in_source"] = (direct_selections == 0 and not is_bfs_reachable and not reached_by_cmds and not op_confirmed)
        row["positive_evidence"] = (direct_selections > 0 or op_confirmed)
        # CRITICAL INVARIANT: Archive eligibility is NEVER derived from telemetry absence
        row["archive_eligible_from_usage_alone"] = False
        skill_rows.append(row)

    skill_rows, skill_observations = scoped_rows(
        skills, [*skill_events.values(), *(event for event in retained_events
                 if event.get("kind") == "skill_read")],
        {row["skill"]: row for row in skill_rows}, operator_notes)
    output_dir.mkdir(parents=True, exist_ok=True)
    # An inventory file capture could not read contributes no outbound references,
    # so its edges are missing from the reachability graph. Count it rather than
    # letting it look like a document that genuinely references nothing.
    uncaptured_inventory = sorted(
        row["path"]
        for row in list(inventory.get("commands", [])) + list(inventory.get("skills", []))
        if "content_encoding" in row and not row.get("content_captured", True)
    )
    common = {
        "snapshot_id": manifest["snapshot_id"],
        "window_start_inclusive": manifest["window_start_inclusive"],
        "window_end_exclusive": manifest["window_end_exclusive"],
        "boundary_convention": manifest["boundary_convention"],
        "inventory_sha256": manifest["inventory_snapshot_sha256"],
        "normalized_event_corpus_sha256": manifest["normalized_event_corpus_sha256"],
        "capture_coverage": corpus["coverage"],
        "uncaptured_inventory_count": len(uncaptured_inventory),
        "uncaptured_inventory_paths": uncaptured_inventory,
        "analysis_counters": dict(analysis),
        "provenance_status": provenance_status,
        "provenance_verified": provenance_status == "verified",
    }

    command_payload = {
        "schema": "hardened_claude_command_usage.v2",
        **common,
        "filesystem_markdown_entries": len(commands),
        "invocable_active_command_entries": len(command_rows),
        "excluded_metadata_entries": len(commands) - len(command_rows),
        "observed_active_command_count": sum(r["positive_evidence"] for r in command_rows),
        "bfs_reachable_command_count": sum(r["bfs_reachable"] for r in command_rows),
        "unobserved_active_command_count": sum(not r["positive_evidence"] for r in command_rows),
        "total_unique_command_events": len(command_events),
        "commands": command_rows,
        "events": sorted(command_events.values(), key=lambda r: (r["timestamp"], r["command"])),
        "excluded_documents": [row for row in commands if not row.get("callable", True)],
    }

    skill_payload = {
        "schema": "scoped_skill_usage.v3",
        **common,
        "active_skill_count": len(skill_rows),
        "observed_direct_skill_count": sum(r["explicit_skill_selections"] > 0 for r in skill_rows),
        "bfs_reachable_total_skill_count": sum(r["bfs_reachable"] for r in skill_rows),
        "workflow_reachable_only_skill_count": sum(r["reachability_only"] for r in skill_rows),
        "no_evidence_skill_count": sum(r["no_evidence_in_source"] for r in skill_rows),
        "total_structured_skill_selections": sum(e["kind"] == "skill_selection" for e in skill_observations),
        "scope_attributed_selections": sum(r["explicit_skill_selections"] for r in skill_rows),
        "total_file_read_attempts": sum(e["kind"] == "skill_read" for e in skill_observations),
        "scope_attributed_read_attempts": sum(r["file_read_attempts"] for r in skill_rows),
        "unresolved_scope_observations": sum(e["attributed_skill_id"] is None for e in skill_observations),
        "coverage_status": "partial",
        "limitations": ["File reads are attempts, not proof of successful workflow execution.",
                        "Name-only invocations cannot identify an installed scope.",
                        "Static reachability is name-level supporting evidence, not execution.",
                        "Missing logs, dynamic shell reads, and uninstrumented runtimes prevent unused classification."],
        "skills": skill_rows,
        "events": skill_observations,
    }

    (output_dir / "strict-claude-command-usage-30d.json").write_text(
        json.dumps(command_payload, indent=2) + "\n"
    )
    (output_dir / "skill-usage-30d.json").write_text(
        json.dumps(skill_payload, indent=2) + "\n"
    )

    # Emit CSV tables
    with (output_dir / "active-commands-30d.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "command",
                "callable",
                "canonical_direct_events",
                "alias_resolved_events",
                "total_observed_events",
                "claude_direct_events",
                "codex_direct_events",
                "bfs_reachable",
                "reachability_reasons",
                "operator_confirmed_use",
                "no_evidence_in_source",
                "positive_evidence",
                "archive_eligible_from_usage_alone",
            ],
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(command_rows)

    with (output_dir / "active-skills-30d.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "skill",
                "skill_id",
                "scope",
                "path",
                "usage_status",
                "coverage_status",
                "file_read_attempts",
                "claude_file_read_attempts",
                "codex_file_read_attempts",
                "name_only_selection_events",
                "explicit_skill_selections",
                "claude_direct_events",
                "codex_direct_events",
                "bfs_reachable",
                "reachability_reasons",
                "reachability_only",
                "operator_confirmed_use",
                "no_evidence_in_source",
                "positive_evidence",
                "archive_eligible_from_usage_alone",
            ],
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(skill_rows)

    with (output_dir / "all-observed-skill-names-30d.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["skill", "structured_selection_count", "active_at_capture"],
        )
        writer.writeheader()
        all_skill_counts = {**skill_counts, **skill_alias_counts}
        writer.writerows(
            {
                "skill": name,
                "structured_selection_count": count,
                "active_at_capture": name in active_skills,
            }
            for name, count in sorted(all_skill_counts.items())
        )

    with (output_dir / "observed-skill-paths-30d.csv").open("w", newline="") as handle:
        path_counts = Counter((event.get("runtime", "claude"), event["selected_path"],
                               event.get("attributed_skill_id") or "")
                              for event in skill_observations if event.get("selected_path"))
        writer = csv.writer(handle)
        writer.writerow(["runtime", "selected_path", "attributed_skill_id", "read_or_selection_attempts"])
        writer.writerows((*key, count) for key, count in sorted(path_counts.items()))

    return {
        "command_summary": {
            "total": len(command_rows),
            "observed_direct": sum(r["positive_evidence"] for r in command_rows),
            "bfs_reachable": sum(r["bfs_reachable"] for r in command_rows),
            "unreached": sum(r["no_evidence_in_source"] for r in command_rows),
        },
        "skill_summary": {
            "total": len(skill_rows),
            "direct_selections": sum(r["explicit_skill_selections"] > 0 for r in skill_rows),
            "observed_read_attempts": sum(r["file_read_attempts"] > 0 for r in skill_rows),
            "name_only_scope_unknown": sum(r["name_only_selection_events"] > 0 for r in skill_rows),
            "bfs_reachable_total": sum(r["bfs_reachable"] for r in skill_rows),
            "reachability_only": sum(r["reachability_only"] for r in skill_rows),
            "no_evidence": sum(r["no_evidence_in_source"] for r in skill_rows),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit command and skill telemetry with BFS reachability closure."
    )
    parser.add_argument(
        "--manifest", type=Path, required=True, help="Path to audit manifest JSON"
    )
    parser.add_argument(
        "--output-dir", type=Path, required=True, help="Path to directory for outputs"
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Optional path to repo root",
    )
    parser.add_argument(
        "--ignore-scanner-hash",
        action="store_true",
        help="Bypass scanner/capture source validation (marks output unverified)",
    )
    args = parser.parse_args()
    res = audit(
        args.manifest.resolve(),
        args.output_dir.resolve(),
        repo_root=args.repo_root.resolve() if args.repo_root else None,
        ignore_scanner_hash=args.ignore_scanner_hash,
    )
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
