"""Build lossless full-code, base/diff, and /es packets for browser review."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import subprocess
from pathlib import Path

from web_advice_transport import assert_review_packet_complete


def _git(repo: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        timeout=60,
    ).stdout


def _metadata(path: str, content: bytes) -> dict:
    if "\n" in path or "\r" in path:
        raise ValueError(f"Packet paths cannot contain newlines: {path!r}")
    return {
        "path": path,
        "size_bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def _write_entry(handle, path: str, content: bytes, status: str = "present") -> None:
    digest = hashlib.sha256(content).hexdigest()
    try:
        content.decode("utf-8")
        payload = content
        encoding = "utf-8"
    except UnicodeDecodeError:
        payload = base64.b64encode(content)
        encoding = "base64"
    header = (
        f"BEGIN FILE {path} status={status} source_size={len(content)} "
        f"source_sha256={digest} encoding={encoding} "
        f"payload_bytes={len(payload)}\n"
    )
    handle.write(header.encode("utf-8"))
    handle.write(payload)
    handle.write(f"END FILE {path}\n\n".encode("utf-8"))


def _changed_file_contents(repo: Path, base: str, head: str) -> list[tuple]:
    current_paths = _git(
        repo,
        "diff",
        "--diff-filter=ACMRTUXB",
        "--name-only",
        "-z",
        f"{base}...{head}",
    ).decode().rstrip("\0").split("\0")
    deleted_paths = _git(
        repo,
        "diff",
        "--diff-filter=D",
        "--name-only",
        "-z",
        f"{base}...{head}",
    ).decode().rstrip("\0").split("\0")
    entries = []
    for path in filter(None, current_paths):
        entries.append((path, _git(repo, "show", f"{head}:{path}"), "present"))
    for path in filter(None, deleted_paths):
        entries.append((path, _git(repo, "show", f"{base}:{path}"), "deleted"))
    return sorted(entries, key=lambda item: item[0])


def _base_file_contents(
    repo: Path, base: str, changed_entries: list[tuple]
) -> list[tuple]:
    entries = []
    for path, _, _ in changed_entries:
        result = subprocess.run(
            ["git", "-C", str(repo), "show", f"{base}:{path}"],
            check=False,
            capture_output=True,
            timeout=60,
        )
        if result.returncode == 0:
            entries.append((path, result.stdout, "base"))
    return sorted(entries, key=lambda item: item[0])


def _diff_bytes(repo: Path, base: str, head: str) -> bytes:
    return _git(
        repo,
        "diff",
        "--binary",
        "--full-index",
        "--find-renames",
        f"{base}...{head}",
        "--",
    )


def _verify_sha256sums(evidence_by_path: dict[str, bytes]) -> None:
    manifest = evidence_by_path.get("SHA256SUMS.txt")
    if manifest is None:
        raise ValueError("Evidence bundle is missing SHA256SUMS.txt")
    checked = 0
    for line_number, line in enumerate(manifest.decode("utf-8").splitlines(), 1):
        if not line.strip():
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2 or len(parts[0]) != 64:
            raise ValueError(f"Invalid SHA256SUMS.txt line {line_number}: {line!r}")
        digest, path = parts
        if path.startswith("*"):
            path = path[1:]
        if path.startswith("./"):
            path = path[2:]
        content = evidence_by_path.get(path)
        if content is None:
            raise ValueError(f"SHA256SUMS.txt references missing file: {path}")
        actual = hashlib.sha256(content).hexdigest()
        if actual != digest:
            raise ValueError(
                f"SHA256SUMS.txt mismatch for {path}: expected={digest}, actual={actual}"
            )
        checked += 1
    if checked == 0:
        raise ValueError("SHA256SUMS.txt contains no file checksums")


def _verify_evidence_head(evidence_by_path: dict[str, bytes], head_sha: str) -> None:
    metadata_bytes = evidence_by_path.get("metadata.json")
    if metadata_bytes is None:
        raise ValueError("Evidence bundle is missing metadata.json")
    metadata = json.loads(metadata_bytes)
    evidence_head = (
        (metadata.get("git_provenance") or {}).get("git_head")
        or (metadata.get("provenance") or {}).get("git_head")
        or metadata.get("git_head")
    )
    if evidence_head != head_sha:
        raise ValueError(
            f"Evidence metadata head mismatch: expected={head_sha}, "
            f"evidence={evidence_head}"
        )


def build_review_packets(
    repo: Path,
    base: str,
    head: str,
    evidence_dir: Path,
    output_dir: Path,
    evidence_index_paths: list[str],
    prefix: str,
    force: bool = False,
) -> dict:
    """Write four packet files plus a validated machine-readable manifest."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", prefix):
        raise ValueError(
            "Packet prefix must match [A-Za-z0-9][A-Za-z0-9._-]* and "
            "cannot contain path separators"
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    head_sha = _git(repo, "rev-parse", head).decode().strip()
    base_sha = _git(repo, "rev-parse", base).decode().strip()

    changed_entries = _changed_file_contents(repo, base_sha, head_sha)
    if not changed_entries:
        raise ValueError("No changed files found between base and head")
    code_manifest = [_metadata(path, content) for path, content, _ in changed_entries]
    base_entries = _base_file_contents(repo, base_sha, changed_entries)
    base_manifest = [_metadata(path, content) for path, content, _ in base_entries]
    diff_content = _diff_bytes(repo, base_sha, head_sha)
    if not diff_content:
        raise ValueError("Git diff index is empty between base and head")
    diff_manifest = _metadata("base...head.patch", diff_content)

    evidence_entries = []
    evidence_root = evidence_dir.resolve()
    for path in sorted(item for item in evidence_dir.rglob("*") if item.is_file()):
        if path.is_symlink() or not path.resolve().is_relative_to(evidence_root):
            raise ValueError(f"Evidence bundle contains an unsafe symlink: {path}")
        relative = path.relative_to(evidence_dir).as_posix()
        evidence_entries.append((relative, path.read_bytes()))
    if not evidence_entries:
        raise ValueError("Evidence directory contains no files")
    evidence_manifest = [_metadata(path, content) for path, content in evidence_entries]

    evidence_by_path = dict(evidence_entries)
    _verify_sha256sums(evidence_by_path)
    _verify_evidence_head(evidence_by_path, head_sha)
    missing_index = sorted(set(evidence_index_paths) - set(evidence_by_path))
    if missing_index:
        raise ValueError(f"Evidence index paths are missing: {missing_index}")

    names = {
        "code": f"{prefix}_FULL_CODE_FILES.txt",
        "base_diff": f"{prefix}_BASE_CODE_FILES_AND_DIFF.txt",
        "index": f"{prefix}_ES_REVIEW_INDEX.txt",
        "evidence": f"{prefix}_FULL_ES_EVIDENCE.txt",
        "manifest": f"{prefix}_REVIEW_PACKET_MANIFEST.json",
    }
    existing = [name for name in names.values() if (output_dir / name).exists()]
    if existing and not force:
        raise FileExistsError(
            f"Refusing to overwrite existing review packets without --force: {existing}"
        )
    with (output_dir / names["code"]).open("wb") as handle:
        for path, content, status in changed_entries:
            _write_entry(handle, path, content, status)
    with (output_dir / names["base_diff"]).open("wb") as handle:
        for path, content, status in base_entries:
            _write_entry(handle, path, content, status)
        _write_entry(handle, "base...head.patch", diff_content, "diff")
    with (output_dir / names["index"]).open("wb") as handle:
        for path in evidence_index_paths:
            _write_entry(handle, path, evidence_by_path[path])
    with (output_dir / names["evidence"]).open("wb") as handle:
        for path, content in evidence_entries:
            _write_entry(handle, path, content)

    packet_attachments = {
        names[key]: (output_dir / names[key]).stat().st_size
        for key in ("code", "base_diff", "index", "evidence")
    }
    packet = {
        "manifest_source": "build_review_packets.py/v1",
        "review_kind": "pr_with_evidence",
        "base_sha": base_sha,
        "head_sha": head_sha,
        "changed_files": code_manifest,
        "authoritative_changed_files": list(code_manifest),
        "full_code_files": list(code_manifest),
        "base_code_files": base_manifest,
        "diff_index": diff_manifest,
        "expected_evidence_files": evidence_manifest,
        "authoritative_evidence_files": list(evidence_manifest),
        "full_evidence_files": list(evidence_manifest),
        "evidence_index_paths": evidence_index_paths,
        "diff_index_attached": True,
        "packet_attachment_names": [
            names["code"],
            names["base_diff"],
            names["index"],
            names["evidence"],
        ],
        "packet_attachments": packet_attachments,
    }
    assert_review_packet_complete(packet)
    (output_dir / names["manifest"]).write_text(
        json.dumps(packet, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return packet


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--evidence-index", action="append", required=True)
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    packet = build_review_packets(
        args.repo.resolve(),
        args.base,
        args.head,
        args.evidence_dir.resolve(),
        args.output_dir.resolve(),
        args.evidence_index,
        args.prefix,
        args.force,
    )
    print(json.dumps({"head_sha": packet["head_sha"], "status": "PASS"}))


if __name__ == "__main__":
    main()
