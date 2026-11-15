#!/usr/bin/env python3
"""Preflight validator for cold review dispatch (mergeability, HEAD pin, packet integrity).

Prevents wasted cold reviewer rounds (/advice, /cs, /er, static-review) caused by:
1. Base-branch merge conflicts (CONFLICT_WITH_BASE) or stale HEAD pins (HEAD_DRIFT).
2. Incomplete or corrupted non-git review packets (.git present, missing base.diff,
   or SHA-256 mismatches against manifest.json / SHA256SUMS).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

HEX_40_RE = re.compile(r"^[0-9a-fA-F]{40}$")
HEX_64_RE = re.compile(r"^[0-9a-fA-F]{64}$")
SHA256SUM_LINE_RE = re.compile(r"^([0-9a-fA-F]{64})\s+\*?(.+)$")


def _run_git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_packet_member(packet_dir: Path, raw_rel: str) -> tuple[Path | None, str | None]:
    rel = raw_rel.strip()
    while rel.startswith("./"):
        rel = rel[2:]
    if not rel or rel.startswith("/") or "\\" in rel:
        return None, f"unsafe packet path: {raw_rel!r}"
    parts = Path(rel).parts
    if not parts or any(part in ("", ".", "..") for part in parts):
        return None, f"unsafe packet path: {raw_rel!r}"

    packet_root = packet_dir.resolve()
    current = packet_dir
    for part in parts:
        current = current / part
        if current.is_symlink():
            return None, f"symlink not allowed in packet path: {raw_rel!r}"
    try:
        resolved = current.resolve()
    except OSError as exc:
        return None, f"cannot resolve packet path {raw_rel!r}: {exc}"
    if not resolved.is_relative_to(packet_root):
        return None, f"packet path escapes packet root: {raw_rel!r}"
    return current, None


def check_repo(
    repo: Path,
    base: str,
    head: str,
    expected_head: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    errors: list[dict[str, str]] = []
    info: dict[str, Any] = {
        "repo": str(repo),
        "base_ref": base,
        "head_ref": head,
    }
    if expected_head is not None:
        info["expected_head"] = expected_head

    if not repo.exists():
        errors.append({"code": "INVALID_REPO", "message": f"repository path does not exist: {repo}"})
        return info, errors

    git_probe = _run_git(repo, "rev-parse", "--git-dir")
    if git_probe.returncode != 0:
        detail = git_probe.stderr.strip() or "not a git repository"
        errors.append({"code": "INVALID_REPO", "message": f"invalid git repository {repo}: {detail}"})
        return info, errors

    base_res = _run_git(repo, "rev-parse", "--verify", f"{base}^{{commit}}")
    if base_res.returncode != 0:
        detail = base_res.stderr.strip() or f"cannot resolve {base}"
        errors.append({"code": "MISSING_REF", "message": f"cannot resolve base ref {base!r}: {detail}"})

    head_res = _run_git(repo, "rev-parse", "--verify", f"{head}^{{commit}}")
    if head_res.returncode != 0:
        detail = head_res.stderr.strip() or f"cannot resolve {head}"
        errors.append({"code": "MISSING_REF", "message": f"cannot resolve head ref {head!r}: {detail}"})

    if errors:
        return info, errors

    base_sha = base_res.stdout.strip().lower()
    head_sha = head_res.stdout.strip().lower()
    info["base_sha"] = base_sha
    info["head_sha"] = head_sha

    if expected_head is not None:
        normalized_expected = expected_head.strip().lower()
        if not HEX_40_RE.match(normalized_expected) or head_sha != normalized_expected:
            errors.append(
                {
                    "code": "HEAD_DRIFT",
                    "message": (
                        f"head {head!r} resolved to {head_sha}, expected {expected_head.strip()} "
                        "(re-pin or sync before dispatching reviewers)"
                    ),
                }
            )

    merge_res = _run_git(repo, "merge-tree", "--write-tree", base_sha, head_sha)
    if merge_res.returncode == 0:
        lines = [line.strip() for line in merge_res.stdout.splitlines() if line.strip()]
        info["merge_tree"] = lines[0] if lines else ""
    elif merge_res.returncode == 1:
        conflict_lines = [
            line.strip()
            for line in merge_res.stdout.splitlines()
            if line.strip().startswith("CONFLICT ")
        ]
        summary = "; ".join(conflict_lines[:5]) if conflict_lines else "merge conflict detected"
        info["conflicts"] = conflict_lines
        errors.append(
            {
                "code": "CONFLICT_WITH_BASE",
                "message": (
                    f"{head} ({head_sha[:12]}) conflicts with {base} ({base_sha[:12]}): {summary} "
                    "(sync/rebase onto base before dispatching cold reviewers)"
                ),
            }
        )
    else:
        detail = merge_res.stderr.strip() or merge_res.stdout.strip() or f"exit {merge_res.returncode}"
        errors.append(
            {
                "code": "MERGE_TREE_ERROR",
                "message": f"git merge-tree --write-tree failed: {detail}",
            }
        )

    return info, errors


def _extract_manifest_json_entries(
    data: Any,
) -> tuple[list[tuple[str, str]], str | None, list[str]]:
    entries: list[tuple[str, str]] = []
    parse_errors: list[str] = []
    if not isinstance(data, dict):
        return entries, None, ["manifest.json root must be a JSON object"]

    manifest_head: str | None = None
    if "head_sha" in data and data["head_sha"] is not None:
        if not isinstance(data["head_sha"], str) or not data["head_sha"].strip():
            parse_errors.append("manifest.json 'head_sha' must be a non-empty 40-hex string")
        else:
            manifest_head = data["head_sha"].strip()

    files_field = data.get("files")
    if files_field is None:
        return entries, manifest_head, parse_errors

    if isinstance(files_field, dict):
        if not files_field:
            parse_errors.append("manifest.json 'files' mapping must not be empty")
            return entries, manifest_head, parse_errors
        for raw_path, spec in files_field.items():
            digest = spec.get("sha256") if isinstance(spec, dict) else spec
            if not isinstance(raw_path, str) or not isinstance(digest, str) or not HEX_64_RE.match(digest):
                parse_errors.append(f"invalid sha256 entry in manifest.json for {raw_path!r}")
                continue
            entries.append((raw_path, digest.lower()))
    elif isinstance(files_field, list):
        if not files_field:
            parse_errors.append("manifest.json 'files' list must not be empty")
            return entries, manifest_head, parse_errors
        for idx, item in enumerate(files_field):
            if not isinstance(item, dict):
                parse_errors.append(f"manifest.json files[{idx}] must be an object")
                continue
            raw_path = item.get("path")
            digest = item.get("sha256")
            if not isinstance(raw_path, str) or not isinstance(digest, str) or not HEX_64_RE.match(digest):
                parse_errors.append(f"invalid path/sha256 in manifest.json files[{idx}]")
                continue
            entries.append((raw_path, digest.lower()))
    else:
        parse_errors.append("manifest.json 'files' must be an object or array")

    return entries, manifest_head, parse_errors


def _parse_sha256sums(manifest_name: str, text: str) -> tuple[list[tuple[str, str]], list[str]]:
    entries: list[tuple[str, str]] = []
    parse_errors: list[str] = []
    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = SHA256SUM_LINE_RE.match(stripped)
        if not match:
            parse_errors.append(f"{manifest_name}:{lineno}: malformed checksum line")
            continue
        entries.append((match.group(2), match.group(1).lower()))
    if not entries and not parse_errors:
        parse_errors.append(f"{manifest_name} contains no file checksums")
    return entries, parse_errors


def check_packet_dir(
    packet_dir: Path,
    expected_head: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    errors: list[dict[str, str]] = []
    info: dict[str, Any] = {
        "packet_dir": str(packet_dir),
        "manifests_checked": [],
        "verified_files": 0,
    }

    if packet_dir.is_symlink() or not packet_dir.is_dir():
        errors.append(
            {
                "code": "INVALID_PACKET_DIR",
                "message": f"packet directory is missing, not a directory, or a symlink: {packet_dir}",
            }
        )
        return info, errors

    git_marker = packet_dir / ".git"
    if git_marker.exists() or git_marker.is_symlink():
        errors.append(
            {
                "code": "GIT_METADATA_PRESENT",
                "message": f"exported review packet must not contain .git: {git_marker}",
            }
        )

    base_diff, diff_err = _resolve_packet_member(packet_dir, "base.diff")
    if diff_err is not None or base_diff is None or not base_diff.is_file():
        errors.append(
            {
                "code": "MISSING_BASE_DIFF",
                "message": diff_err or f"exported review packet is missing base.diff: {packet_dir / 'base.diff'}",
            }
        )

    manifest_entries: list[tuple[str, str, str]] = []
    manifest_json_path = packet_dir / "manifest.json"
    sha256sums_paths = [
        packet_dir / name
        for name in ("SHA256SUMS", "SHA256SUMS.txt")
        if (packet_dir / name).exists() or (packet_dir / name).is_symlink()
    ]

    if manifest_json_path.exists() or manifest_json_path.is_symlink():
        info["manifests_checked"].append("manifest.json")
        if manifest_json_path.is_symlink() or not manifest_json_path.is_file():
            errors.append(
                {
                    "code": "MANIFEST_INVALID",
                    "message": f"manifest.json must be a regular non-symlink file: {manifest_json_path}",
                }
            )
        else:
            try:
                manifest_data = json.loads(manifest_json_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                errors.append({"code": "MANIFEST_INVALID", "message": f"cannot parse manifest.json: {exc}"})
            else:
                entries, manifest_head, parse_errs = _extract_manifest_json_entries(manifest_data)
                if manifest_head is not None:
                    info["manifest_head_sha"] = manifest_head
                    if not HEX_40_RE.match(manifest_head):
                        errors.append(
                            {
                                "code": "HEAD_DRIFT",
                                "message": f"manifest.json head_sha {manifest_head!r} is not a full 40-hex commit SHA",
                            }
                        )
                    elif expected_head is not None and manifest_head.lower() != expected_head.strip().lower():
                        errors.append(
                            {
                                "code": "HEAD_DRIFT",
                                "message": (
                                    f"manifest.json head_sha {manifest_head.lower()} does not match "
                                    f"expected head {expected_head.strip().lower()}"
                                ),
                            }
                        )
                if not entries and not parse_errs and not sha256sums_paths:
                    parse_errs.append("manifest.json must declare a non-empty 'files' collection")
                for err in parse_errs:
                    errors.append({"code": "MANIFEST_INVALID", "message": err})
                for rel_path, digest in entries:
                    manifest_entries.append(("manifest.json", rel_path, digest))

    for sums_path in sha256sums_paths:
        sums_name = sums_path.name
        info["manifests_checked"].append(sums_name)
        if sums_path.is_symlink() or not sums_path.is_file():
            errors.append(
                {
                    "code": "MANIFEST_INVALID",
                    "message": f"{sums_name} must be a regular non-symlink file: {sums_path}",
                }
            )
            continue
        try:
            sums_text = sums_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            errors.append({"code": "MANIFEST_INVALID", "message": f"cannot read {sums_name}: {exc}"})
            continue
        entries, parse_errs = _parse_sha256sums(sums_name, sums_text)
        for err in parse_errs:
            errors.append({"code": "MANIFEST_INVALID", "message": err})
        for rel_path, digest in entries:
            manifest_entries.append((sums_name, rel_path, digest))

    verified = 0
    for source_name, rel_path, expected_digest in manifest_entries:
        member_path, path_err = _resolve_packet_member(packet_dir, rel_path)
        if path_err is not None or member_path is None:
            errors.append(
                {
                    "code": "MANIFEST_INVALID",
                    "message": f"{source_name}: {path_err or f'invalid path {rel_path!r}'}",
                }
            )
            continue
        if not member_path.is_file():
            errors.append(
                {
                    "code": "HASH_MISMATCH",
                    "message": f"{source_name}: listed file is missing on disk: {rel_path}",
                }
            )
            continue
        actual_digest = _sha256_file(member_path)
        if actual_digest != expected_digest:
            errors.append(
                {
                    "code": "HASH_MISMATCH",
                    "message": (
                        f"{source_name}: sha256 mismatch for {rel_path} "
                        f"(expected {expected_digest}, actual {actual_digest})"
                    ),
                }
            )
            continue
        verified += 1

    info["verified_files"] = verified
    return info, errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate clean base mergeability, pinned HEAD SHA, and/or exported review packet "
            "integrity before spawning cold reviewers."
        )
    )
    parser.add_argument("--repo", type=Path, help="Git worktree or git-dir to check.")
    parser.add_argument(
        "--base",
        default="origin/main",
        help="Base ref to check clean merge-tree against (default: origin/main).",
    )
    parser.add_argument(
        "--head",
        default="HEAD",
        help="Head ref to verify and merge-check (default: HEAD).",
    )
    parser.add_argument(
        "--expected-head",
        help="Expected full 40-char commit SHA for --head (and packet manifest head_sha if present).",
    )
    parser.add_argument(
        "--packet-dir",
        type=Path,
        help="Exported non-git review packet directory to verify (.git absent, base.diff, manifest hashes).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit structured JSON diagnostic report to stdout.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.repo is None and args.packet_dir is None:
        parser.error("at least one of --repo or --packet-dir is required")

    errors: list[dict[str, str]] = []
    report: dict[str, Any] = {"ok": True, "codes": [], "errors": []}

    effective_expected_head = args.expected_head
    if args.repo is not None:
        repo_info, repo_errors = check_repo(
            repo=args.repo,
            base=args.base,
            head=args.head,
            expected_head=args.expected_head,
        )
        report["repo"] = repo_info
        errors.extend(repo_errors)
        if effective_expected_head is None and "head_sha" in repo_info:
            effective_expected_head = repo_info["head_sha"]

    if args.packet_dir is not None:
        packet_info, packet_errors = check_packet_dir(
            packet_dir=args.packet_dir,
            expected_head=effective_expected_head,
        )
        report["packet"] = packet_info
        errors.extend(packet_errors)

    codes: list[str] = []
    for item in errors:
        if item["code"] not in codes:
            codes.append(item["code"])

    report["ok"] = len(errors) == 0
    report["codes"] = codes
    report["errors"] = errors

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        if report["ok"]:
            parts = []
            if "repo" in report:
                repo_summary = report["repo"]
                parts.append(
                    f"repo={repo_summary['head_sha'][:12]} merge_tree={repo_summary.get('merge_tree', '')[:12]}"
                )
            if "packet" in report:
                pkt_summary = report["packet"]
                parts.append(
                    f"packet={pkt_summary['packet_dir']} verified_files={pkt_summary['verified_files']}"
                )
            print(f"OK: review preflight passed ({', '.join(parts)})")
        else:
            for item in errors:
                print(f"FAIL [{item['code']}]: {item['message']}", file=sys.stderr)
            print(f"Preflight failed with: {', '.join(codes)}", file=sys.stderr)

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
