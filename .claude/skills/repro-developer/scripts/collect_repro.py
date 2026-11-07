#!/usr/bin/env python3
"""Collect raw agent-review repro artifacts into a portable bundle."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import secrets
import shutil
import subprocess
import sys
import tarfile
from typing import Iterable


PROFILE_LIST_KEYS = {
    "claude_sessions": "claude_session",
    "claude_session_dirs": "claude_session_dir",
    "codex_sessions": "codex_session",
    "repo_files": "repo_file",
    "beads": "bead",
}
PROFILE_TEXT_KEYS = ("incident", "claim", "incident_commit", "artifact_commit")


def expand_path(raw: str) -> pathlib.Path:
    """Expand $VARS and ~ the way a shell would, so profiles and args can say $CLAUDE_HOME."""
    return pathlib.Path(os.path.expanduser(os.path.expandvars(raw)))


def load_profile(path_s: str) -> dict[str, object]:
    """Read an incident profile JSON (keys: PROFILE_TEXT_KEYS plus PROFILE_LIST_KEYS)."""
    profile = json.loads(expand_path(path_s).read_text(encoding="utf-8"))
    if not isinstance(profile, dict):
        raise SystemExit(f"--incident-profile {path_s}: expected a JSON object")
    return profile


def run(cmd: list[str], cwd: pathlib.Path | None = None) -> dict[str, object]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
            check=False,
        )
        return {
            "cmd": cmd,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
    except Exception as exc:
        return {"cmd": cmd, "error": repr(exc)}


def sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_rel(path: pathlib.Path) -> pathlib.Path:
    parts = []
    for part in path.parts:
        if part in ("", os.sep):
            continue
        if part == str(pathlib.Path.home()).strip(os.sep):
            parts.append("HOME")
        else:
            parts.append(part.replace(":", "_"))
    return pathlib.Path(*parts)


def copy_file(src: pathlib.Path, dest_root: pathlib.Path, prefix: str, manifest: list[dict[str, object]]) -> None:
    if not src.exists() or not src.is_file():
        manifest.append({"source": str(src), "missing": True, "prefix": prefix})
        return
    rel = pathlib.Path(prefix) / safe_rel(src)
    dest = dest_root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    manifest.append(
        {
            "source": str(src),
            "bundle_path": str(rel),
            "size": src.stat().st_size,
            "sha256": sha256(dest),
        }
    )


def copy_tree_files(src_root: pathlib.Path, dest_root: pathlib.Path, prefix: str, manifest: list[dict[str, object]]) -> None:
    if not src_root.exists():
        manifest.append({"source": str(src_root), "missing": True, "prefix": prefix})
        return
    for src in sorted(p for p in src_root.rglob("*") if p.is_file()):
        copy_file(src, dest_root, prefix, manifest)


def iter_session_files(session_dir: pathlib.Path) -> Iterable[pathlib.Path]:
    patterns = ("*.jsonl", "*.json", "*.md", "*.txt")
    for pattern in patterns:
        yield from session_dir.rglob(pattern)


def write_text(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def iter_files(root: pathlib.Path) -> list[pathlib.Path]:
    return sorted(p for p in root.rglob("*") if p.is_file())


def write_checksums(root: pathlib.Path) -> None:
    checksum_lines = []
    for path in iter_files(root):
        rel = path.relative_to(root)
        if str(rel) == "checksums.sha256":
            continue
        checksum_lines.append(f"{sha256(path)}  {rel}")
    write_text(root / "checksums.sha256", "\n".join(checksum_lines) + "\n")


def parse_porcelain_z(raw: str) -> list[tuple[str, str]]:
    parts = raw.split("\0")
    out = []
    i = 0
    while i < len(parts):
        entry = parts[i]
        i += 1
        if not entry:
            continue
        status = entry[:2]
        path = entry[3:]
        out.append((status, path))
        if status.startswith("R") or status.startswith("C"):
            i += 1
    return out


def capture_dirty_state(repo: pathlib.Path, bundle_dir: pathlib.Path, manifest: list[dict[str, object]]) -> None:
    dirty_dir = bundle_dir / "repo" / "dirty-state"
    dirty_dir.mkdir(parents=True, exist_ok=True)
    status = run(["git", "status", "--porcelain=v1", "-z"], repo)
    raw_status = str(status.get("stdout") or "")
    write_text(dirty_dir / "git-status-porcelain-z.txt", raw_status.replace("\0", "\n"))
    write_text(dirty_dir / "git-diff.patch", str(run(["git", "diff", "--binary"], repo).get("stdout") or ""))
    write_text(dirty_dir / "git-diff-cached.patch", str(run(["git", "diff", "--cached", "--binary"], repo).get("stdout") or ""))
    entries = parse_porcelain_z(raw_status)
    write_text(dirty_dir / "paths.json", json.dumps(entries, indent=2))
    for status_code, rel_s in entries:
        rel = pathlib.Path(rel_s)
        src = repo / rel
        if not src.is_file():
            continue
        if src.stat().st_size > 2_000_000:
            manifest.append({"source": str(src), "skipped": "dirty file larger than 2MB"})
            continue
        prefix = "repo/dirty-state/untracked" if status_code == "??" else "repo/dirty-state/worktree"
        copy_file(src, bundle_dir, prefix, manifest)


def env_report(repo: pathlib.Path) -> dict[str, object]:
    return {
        "platform": run(["uname", "-a"]),
        "date_utc": run(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"]),
        "python": run([sys.executable, "--version"]),
        "git": run(["git", "--version"]),
        "git_lfs": run(["git", "lfs", "version"]),
        "gitleaks": run(["gitleaks", "version"]),
        "gh": run(["gh", "--version"]),
        "br": run(["br", "--version"]),
        "zstd": run(["zstd", "--version"]),
        "gpg": run(["gpg", "--version"]),
        "repo_hookspath": run(["git", "config", "core.hooksPath"], repo),
        "git_lfs_track": run(["git", "lfs", "track"], repo),
        "git_lfs_status": run(["git", "lfs", "status"], repo),
    }


def sensitive_review(bundle_dir: pathlib.Path) -> str:
    patterns = {
        "api_key": ("api_key", "apikey", "x-api-key"),
        "token": ("token", "bearer ", "authorization"),
        "password": ("password", "passwd"),
        "private_key": ("BEGIN PRIVATE KEY", "BEGIN RSA PRIVATE KEY", "BEGIN OPENSSH PRIVATE KEY"),
    }
    findings: dict[str, list[str]] = {k: [] for k in patterns}
    for path in sorted(p for p in bundle_dir.rglob("*") if p.is_file()):
        rel = str(path.relative_to(bundle_dir))
        if rel in {"SENSITIVE_REVIEW.md", "checksums.sha256", "manifest.json", "SANITIZATION.md"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        lower = text.lower()
        for label, needles in patterns.items():
            for needle in needles:
                haystack = text if needle != needle.lower() else lower
                if needle in haystack:
                    findings[label].append(rel)
                    break

    lines = [
        "# Sensitive Review",
        "",
        "This is a coarse local scan. It does not prove the bundle is safe to share externally.",
        "Review raw transcripts before sending outside trusted engineering channels.",
        "",
    ]
    any_findings = False
    for label, files in findings.items():
        unique = sorted(set(files))
        if unique:
            any_findings = True
            lines.append(f"## {label}: {len(unique)} file(s)")
            lines.extend(f"- `{p}`" for p in unique[:50])
            if len(unique) > 50:
                lines.append(f"- ... {len(unique) - 50} more")
            lines.append("")
    if not any_findings:
        lines.append("No coarse sensitive-pattern hits found.")
        lines.append("")
    return "\n".join(lines)


def package(bundle_dir: pathlib.Path, incident: str) -> pathlib.Path:
    zstd = shutil.which("zstd")
    if zstd:
        tar_path = bundle_dir.parent / f"{incident}.tar"
        with tarfile.open(tar_path, "w") as tar:
            tar.add(bundle_dir, arcname=bundle_dir.name)
        proc = subprocess.run([zstd, "-f", "-q", str(tar_path)], check=False)
        if proc.returncode == 0:
            tar_path.unlink(missing_ok=True)
            return pathlib.Path(str(tar_path) + ".zst")
    gz_path = bundle_dir.parent / f"{incident}.tar.gz"
    with tarfile.open(gz_path, "w:gz") as tar:
        tar.add(bundle_dir, arcname=bundle_dir.name)
    return gz_path


TEXT_SUFFIXES = {
    ".jsonl",
    ".json",
    ".md",
    ".txt",
    ".toml",
    ".yaml",
    ".yml",
    ".sh",
    ".py",
    ".rs",
}


REDACTIONS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
        "[REDACTED_PRIVATE_KEY_BLOCK]",
    ),
    (
        re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
        "[REDACTED_JWT]",
    ),
    (
        re.compile(
            r"(?i)((?:api[_-]?key|access[_-]?token|refresh[_-]?token|id[_-]?token|auth[_-]?token|password|secret|receipt|authorization)"
            r"[\w\"'\s:-]{0,30}[:=]\s*[\"']?)([^\"'\s,}]{12,})"
        ),
        r"\1[REDACTED_SECRET]",
    ),
    (
        re.compile(r"(?i)(bearer\s+)([A-Za-z0-9._~+/=-]{12,})"),
        r"\1[REDACTED_BEARER]",
    ),
    (
        re.compile(r"(dark-factory-holdouts|\$DARK_FACTORY_HOLDOUTS|DARK_FACTORY_HOLDOUTS)"),
        "[REDACTED_HOLDOUT_PATH]",
    ),
]


def holdout_path_redactions() -> list[tuple[re.Pattern[str], str]]:
    """Redact the configured sealed-holdouts checkout, wherever it lives."""
    configured = os.environ.get("DARK_FACTORY_HOLDOUTS", "").strip()
    if not configured:
        return []
    forms = {configured, str(expand_path(configured))}
    forms.discard("")
    alternation = "|".join(re.escape(f) for f in sorted(forms, key=len, reverse=True))
    return [(re.compile(alternation), "[REDACTED_HOLDOUT_PATH]")]


def sanitize_text(text: str) -> str:
    for pattern, repl in holdout_path_redactions() + REDACTIONS:
        text = pattern.sub(repl, text)
    return text


def make_sanitized_copy(bundle_dir: pathlib.Path) -> pathlib.Path:
    dest = bundle_dir.with_name(bundle_dir.name + "-sanitized")
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(bundle_dir, dest)
    changed = []
    for path in sorted(p for p in dest.rglob("*") if p.is_file()):
        if path.suffix not in TEXT_SUFFIXES:
            continue
        try:
            original = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        sanitized = sanitize_text(original)
        if sanitized != original:
            path.write_text(sanitized, encoding="utf-8")
            changed.append(str(path.relative_to(dest)))
    write_text(
        dest / "SANITIZATION.md",
        "# Sanitization\n\n"
        "This bundle preserves file layout and conversation chronology but redacts token-shaped values, "
        "private-key blocks, and authorization values.\n\n"
        f"Redacted files: {len(changed)}\n\n"
        + "\n".join(f"- `{p}`" for p in changed[:200])
        + ("\n" if changed else ""),
    )
    write_text(dest / "SENSITIVE_REVIEW.md", sensitive_review(dest))
    raw_manifest = dest / "manifest.json"
    if raw_manifest.exists():
        try:
            manifest = json.loads(raw_manifest.read_text(encoding="utf-8"))
        except Exception:
            manifest = {}
        manifest["sanitized"] = True
        manifest["sanitized_file_count"] = len(iter_files(dest))
        manifest["redacted_file_count"] = len(changed)
        manifest["redacted_files"] = changed
        write_text(raw_manifest, json.dumps(manifest, indent=2, sort_keys=True))
    write_text(dest / "SENSITIVE_REVIEW.md", sensitive_review(dest))
    write_checksums(dest)
    return dest


def run_gitleaks(source: pathlib.Path, report_path: pathlib.Path) -> dict[str, object]:
    result = run(
        [
            "gitleaks",
            "detect",
            "--no-git",
            "--source",
            str(source),
            "--report-format",
            "json",
            "--report-path",
            str(report_path),
            "--redact=100",
            "--no-banner",
        ]
    )
    findings = []
    if report_path.exists() and report_path.stat().st_size:
        try:
            findings = json.loads(report_path.read_text(encoding="utf-8"))
        except Exception:
            findings = []
    result["findings"] = findings
    result["finding_count"] = len(findings)
    return result


def encrypt_symmetric(src: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    passphrase = secrets.token_urlsafe(48)
    secret_dir = pathlib.Path.home() / ".local" / "share" / "repro-developer" / "secrets"
    secret_dir.mkdir(parents=True, exist_ok=True)
    secret_dir.parent.chmod(0o700)
    secret_dir.chmod(0o700)
    pass_path = secret_dir / f"{src.name}.passphrase.txt"
    fd = os.open(pass_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(passphrase + "\n")
    encrypted = src.with_suffix(src.suffix + ".gpg")
    proc = subprocess.run(
        [
            "gpg",
            "--batch",
            "--yes",
            "--pinentry-mode",
            "loopback",
            "--passphrase-file",
            str(pass_path),
            "--symmetric",
            "--cipher-algo",
            "AES256",
            "--output",
            str(encrypted),
            str(src),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"gpg failed: {proc.stderr}")
    return encrypted, pass_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=os.getcwd())
    parser.add_argument("--incident", default="")
    parser.add_argument(
        "--incident-profile",
        default="",
        help="JSON file with incident, claim, commits, and session/repo-file/bead lists; paths may use $VARS and ~",
    )
    parser.add_argument("--out", default="/tmp")
    parser.add_argument("--claim", default="")
    parser.add_argument("--incident-commit", default="")
    parser.add_argument("--artifact-commit", default="")
    parser.add_argument("--claude-session-dir", action="append", default=[])
    parser.add_argument("--claude-session", action="append", default=[])
    parser.add_argument("--codex-session", action="append", default=[])
    parser.add_argument("--repo-file", action="append", default=[])
    parser.add_argument("--bead", action="append", default=[])
    parser.add_argument("--extra", action="append", default=[])
    parser.add_argument("--sanitize", action="store_true")
    parser.add_argument("--require-gitleaks-clean", action="store_true")
    parser.add_argument("--encrypt-raw", action="store_true")
    parser.add_argument("--publish-dir", default="")
    parser.add_argument("--include-dirty-diff", action="store_true")
    parser.add_argument("--include-beads-jsonl", action="store_true")
    parser.add_argument("--write-env-report", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    if args.incident_profile:
        profile = load_profile(args.incident_profile)
        for key in PROFILE_TEXT_KEYS:
            if not getattr(args, key) and profile.get(key):
                setattr(args, key, str(profile[key]))
        for key, dest in PROFILE_LIST_KEYS.items():
            raw_list = profile.get(key, [])
            if isinstance(raw_list, list):
                getattr(args, dest).extend(str(v) for v in raw_list)
        args.include_dirty_diff = True
        args.include_beads_jsonl = True
        args.write_env_report = True
        args.verify = True

    if not args.incident:
        parser.error("--incident is required unless the --incident-profile file sets it")

    repo = expand_path(args.repo).resolve()
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bundle_dir = expand_path(args.out).resolve() / f"repro-developer-{args.incident}-{stamp}"
    bundle_dir.mkdir(parents=True, exist_ok=False)

    copied: list[dict[str, object]] = []

    for session_dir_s in args.claude_session_dir:
        session_dir = expand_path(session_dir_s).resolve()
        if session_dir.exists():
            for src in iter_session_files(session_dir):
                copy_file(src, bundle_dir, "raw/claude/session_dirs", copied)
        else:
            copied.append({"source": str(session_dir), "missing": True, "prefix": "raw/claude/session_dirs"})

    for src_s in args.claude_session:
        copy_file(expand_path(src_s).resolve(), bundle_dir, "raw/claude/sessions", copied)

    for src_s in args.codex_session:
        copy_file(expand_path(src_s).resolve(), bundle_dir, "raw/codex/sessions", copied)

    for rel_s in args.repo_file:
        src = expand_path(rel_s)
        if not src.is_absolute():
            src = repo / src
        copy_file(src.resolve(), bundle_dir, "repo/files", copied)

    for src_s in args.extra:
        copy_file(expand_path(src_s).resolve(), bundle_dir, "extra", copied)

    if args.include_beads_jsonl:
        copy_file(repo / ".beads" / "issues.jsonl", bundle_dir, "repo/beads", copied)
        copy_tree_files(repo / ".beads" / ".br_history", bundle_dir, "repo/beads-history", copied)

    if args.include_dirty_diff:
        capture_dirty_state(repo, bundle_dir, copied)

    commands = {
        "git_status_short": run(["git", "status", "--short"], repo),
        "git_log_20": run(["git", "log", "--oneline", "-20"], repo),
        "git_remote_v": run(["git", "remote", "-v"], repo),
        "git_rev_parse_head": run(["git", "rev-parse", "HEAD"], repo),
        "git_diff_name_status": run(["git", "diff", "--name-status"], repo),
        "git_diff_cached_name_status": run(["git", "diff", "--cached", "--name-status"], repo),
        "git_ls_files_others": run(["git", "ls-files", "--others", "--exclude-standard"], repo),
        "git_lfs_status": run(["git", "lfs", "status"], repo),
        "br_list_open": run(["br", "list", "--status", "open"], repo),
    }
    for bead in args.bead:
        commands[f"br_show_{bead}"] = run(["br", "show", bead], repo)
    write_text(bundle_dir / "repo/command_outputs.json", json.dumps(commands, indent=2, sort_keys=True))

    if args.write_env_report:
        write_text(bundle_dir / "repo/environment.json", json.dumps(env_report(repo), indent=2, sort_keys=True))

    script_path = pathlib.Path(__file__).resolve()

    reading_order = [
        f"{n}. `{entry['bundle_path']}` - copied from `{entry['source']}`"
        for n, entry in enumerate((e for e in copied if "bundle_path" in e), start=1)
        if n <= 20
    ]

    replay = [
        f"# Developer Repro: {args.incident}",
        "",
        f"Created: {stamp}",
        f"Repo: {repo}",
        f"Incident capture commit: {args.incident_commit or '(not specified)'}",
        f"Artifact transport commit: {args.artifact_commit or '(not specified)'}",
        "",
        "## Claim",
        "",
        args.claim or "A prior adversarial Claude/subagent workflow missed plan-level issues that a later Codex review caught.",
        "",
        "## Verification Question",
        "",
        "Verify that the Claude/fable workflow had the relevant facts available in its own review context, "
        "but its adversarial machinery checked current-state findings rather than attacking the synthesized "
        "future plan; then verify that the later Codex review identified those cross-finding plan hazards.",
        "",
        "## Suggested Reading Order",
        "",
        *reading_order,
        f"{len(reading_order) + 1}. `repo/command_outputs.json`, `repo/environment.json`, `repo/dirty-state/`, `repo/beads/`, `manifest.json`, and `checksums.sha256` - captured repo state and integrity metadata.",
        "",
        "## Notes",
        "",
        "- This bundle intentionally preserves raw JSONL/session state instead of summarizing it away.",
        "- Sanitized archives are structurally replayable. Encrypted raw archives preserve exact raw local transcript state.",
        "- Review for secrets or private data before sharing outside trusted engineering channels.",
        "- Large transcript artifacts should be shared via Google Drive, Git LFS, or another explicit artifact store rather than pasted into issues.",
    ]
    write_text(bundle_dir / "REPLAY.md", "\n".join(replay) + "\n")
    write_text(bundle_dir / "SENSITIVE_REVIEW.md", sensitive_review(bundle_dir))

    all_files = iter_files(bundle_dir)
    write_checksums(bundle_dir)

    manifest = {
        "incident": args.incident,
        "created_utc": stamp,
        "repo": str(repo),
        "claim": args.claim,
        "argv": sys.argv,
        "script_path": str(script_path),
        "script_sha256": sha256(script_path) if script_path.exists() else None,
        "incident_commit": args.incident_commit,
        "artifact_commit": args.artifact_commit,
        "copied": copied,
        "commands": list(commands.keys()),
        "file_count": len(iter_files(bundle_dir)),
    }
    write_text(bundle_dir / "manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
    write_checksums(bundle_dir)

    archive = package(bundle_dir, args.incident)
    output: dict[str, object] = {"bundle_dir": str(bundle_dir), "archive": str(archive)}

    sanitized_archive = None
    sanitized_dir = None
    if args.sanitize:
        sanitized_dir = make_sanitized_copy(bundle_dir)
        report_path = sanitized_dir / "gitleaks-report.json"
        gitleaks_result = run_gitleaks(sanitized_dir, report_path)
        write_text(sanitized_dir / "GITLEAKS_RESULT.json", json.dumps(gitleaks_result, indent=2, sort_keys=True))
        output["sanitized_bundle_dir"] = str(sanitized_dir)
        output["gitleaks_findings"] = gitleaks_result.get("finding_count")
        if args.require_gitleaks_clean and gitleaks_result.get("finding_count"):
            print(json.dumps(output, indent=2), file=sys.stderr)
            return 2
        raw_manifest = sanitized_dir / "manifest.json"
        if raw_manifest.exists():
            manifest = json.loads(raw_manifest.read_text(encoding="utf-8"))
            manifest["sanitized_final_file_count"] = len(iter_files(sanitized_dir))
            manifest["gitleaks_findings"] = gitleaks_result.get("finding_count")
            write_text(raw_manifest, json.dumps(manifest, indent=2, sort_keys=True))
        write_checksums(sanitized_dir)
        sanitized_archive = package(sanitized_dir, args.incident + "-sanitized")
        output["sanitized_archive"] = str(sanitized_archive)

    encrypted_archive = None
    passphrase_path = None
    if args.encrypt_raw:
        encrypted_archive, passphrase_path = encrypt_symmetric(archive)
        output["encrypted_raw_archive"] = str(encrypted_archive)
        output["raw_archive_passphrase_file"] = str(passphrase_path)

    if args.publish_dir:
        publish_dir = pathlib.Path(args.publish_dir)
        if not publish_dir.is_absolute():
            publish_dir = repo / publish_dir
        publish_dir.mkdir(parents=True, exist_ok=True)
        origin = run(["git", "remote", "get-url", "origin"], repo)
        clone_url = str(origin.get("stdout") or "").strip() or "<repo-clone-url>"
        clone_dir = clone_url.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git") or repo.name
        if sanitized_archive:
            shutil.copy2(sanitized_archive, publish_dir / sanitized_archive.name)
        if encrypted_archive:
            shutil.copy2(encrypted_archive, publish_dir / encrypted_archive.name)
        write_text(
            publish_dir / "README.md",
            f"# Repro Developer Artifact: {args.incident}\n\n"
            "This directory is a git-native repro handoff for an agent-review failure.\n\n"
            "## Artifacts\n\n"
            f"- `{sanitized_archive.name if sanitized_archive else '<missing sanitized archive>'}`: gitleaks-clean sanitized repro for normal repo access.\n"
            f"- `{encrypted_archive.name if encrypted_archive else '<missing encrypted archive>'}`: exact raw repro archive encrypted with GPG symmetric encryption.\n"
            "- Do not commit the passphrase file. Share the passphrase only out of band with the intended engineer.\n\n"
            "## Reproduce\n\n"
            "```bash\n"
            f"git clone {clone_url}\n"
            f"cd {clone_dir}\n"
            "git checkout main  # or the specific commit containing this artifact directory\n"
            "git lfs pull\n"
            "mkdir -p /tmp/df-repro\n"
            f"tar --use-compress-program=zstd -xf artifacts/repro-developer/{args.incident}/{sanitized_archive.name if sanitized_archive else '<sanitized>'} -C /tmp/df-repro\n"
            "sed -n '1,220p' /tmp/df-repro/repro-developer-*/REPLAY.md\n"
            "```\n\n"
            "For exact raw state, get the GPG passphrase out of band and decrypt the `.gpg` archive.\n",
        )
        output["publish_dir"] = str(publish_dir)

    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
