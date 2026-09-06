#!/usr/bin/env python3
"""Evidence-gathering + mechanical-copy tool for repo<->live agent-config sync.

This tool makes NO judgment about which side (repo vs. live) is fresher —
that call belongs to the `sync-live-config` SKILL.md, which reads this
tool's evidence report and decides per-file direction. The tool only:

  report  Diff repo vs. live (and optionally remote hosts), with enough
          context (last-commit metadata on both sides, a capped unified
          diff for small text files) for a model to judge staleness itself.
  apply   Mechanically copy an explicit list of paths in an explicit,
          caller-chosen direction. Never infers direction.

Scope is either the README's "top 6" highlighted skills (default) or every
tracked file under .claude/, .codex/hooks/, hermes/skills/ (--full).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

TOP_LEVEL_MAP = {
    ".claude/": "~/.claude/",
    ".codex/": "~/.codex/",
    "hermes/": "~/.hermes/",
}
DIFF_SNIPPET_MAX_BYTES = 200_000
DIFF_SNIPPET_MAX_LINES = 60


def repo_root() -> Path:
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=Path(__file__).resolve().parent,
        capture_output=True, text=True, check=True,
    )
    return Path(out.stdout.strip())


def live_path_for(repo_rel: str) -> str:
    for prefix, live_prefix in TOP_LEVEL_MAP.items():
        if repo_rel.startswith(prefix):
            return live_prefix + repo_rel[len(prefix):]
    raise ValueError(f"no live mapping for {repo_rel}")


def git_tracked_files(root: Path, *paths: str) -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", *paths], cwd=root, capture_output=True, text=True, check=True,
    )
    return [l for l in out.stdout.splitlines() if l.strip()]


def parse_highlighted_skill_dirs(root: Path) -> list[str]:
    readme = (root / "README.md").read_text(encoding="utf-8")
    m = re.search(r"### Highlighted skills.*?\n(.*?)\n\n", readme, re.DOTALL)
    if not m:
        raise RuntimeError("could not find 'Highlighted skills' table in README.md")
    dirs = sorted(set(re.findall(r"(\.claude/skills/[a-zA-Z0-9_-]+)/SKILL\.md", m.group(1))))
    if not dirs:
        raise RuntimeError("found the highlighted-skills table but no skill links in it")
    return dirs


def find_command_files_for_skill(root: Path, skill_dir: str) -> list[str]:
    skill_md_suffix = f"{skill_dir}/SKILL.md"
    name = skill_dir.split("/")[-1]
    hits = []
    for f in sorted((root / ".claude" / "commands").glob("*.md")):
        text = f.read_text(encoding="utf-8", errors="ignore")
        if skill_md_suffix in text or name in text:
            hits.append(str(f.relative_to(root)))
    return hits


def collect_core_scope(root: Path) -> list[str]:
    files: list[str] = []
    for skill_dir in parse_highlighted_skill_dirs(root):
        if not (root / skill_dir).is_dir():
            print(f"WARNING: highlighted skill dir missing in repo: {skill_dir}", file=sys.stderr)
            continue
        for f in git_tracked_files(root, skill_dir):
            if f not in files:
                files.append(f)
        for cmd in find_command_files_for_skill(root, skill_dir):
            if cmd not in files:
                files.append(cmd)
    return files


def collect_full_scope(root: Path) -> list[str]:
    return git_tracked_files(root, ".claude", ".codex/hooks", "hermes/skills")


def sha256_of(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def last_commit(cwd: Path, rel_path: str) -> dict | None:
    out = subprocess.run(
        ["git", "log", "-1", "--format=%H%x1f%aI%x1f%an%x1f%s", "--", rel_path],
        cwd=cwd, capture_output=True, text=True,
    )
    line = out.stdout.strip()
    if not line:
        return None
    sha, date, author, subject = line.split("\x1f", 3)
    return {"sha": sha[:12], "date": date, "author": author, "subject": subject}


def find_enclosing_git_repo(path: Path) -> Path | None:
    """Walk up from `path` looking for a .git dir, distinct from a bare non-repo dir."""
    cur = path.parent if path.suffix or path.is_file() else path
    home = Path.home()
    while cur != cur.parent and cur >= home:
        if (cur / ".git").exists():
            return cur
        cur = cur.parent
    return None


def unified_diff_snippet(repo_abs: Path, live_abs: Path) -> str | None:
    try:
        if repo_abs.stat().st_size > DIFF_SNIPPET_MAX_BYTES or live_abs.stat().st_size > DIFF_SNIPPET_MAX_BYTES:
            return None
        a = repo_abs.read_text(encoding="utf-8", errors="strict").splitlines(keepends=True)
        b = live_abs.read_text(encoding="utf-8", errors="strict").splitlines(keepends=True)
    except (UnicodeDecodeError, OSError):
        return None
    import difflib
    lines = list(difflib.unified_diff(b, a, fromfile="live", tofile="repo", lineterm=""))
    if not lines:
        return None
    truncated = len(lines) > DIFF_SNIPPET_MAX_LINES
    lines = lines[:DIFF_SNIPPET_MAX_LINES]
    if truncated:
        lines.append("... (truncated)")
    return "\n".join(lines)


@dataclass
class FileEvidence:
    repo_rel: str
    live_rel: str
    status: str  # "new" | "modified" | "ok"
    repo_last_commit: dict | None = None
    live_last_commit: dict | None = None
    live_repo_root: str | None = None  # set if live path lives inside its own distinct git repo
    diff_snippet: str | None = None


def evidence_local(root: Path, files: list[str]) -> list[FileEvidence]:
    out = []
    for f in files:
        live_rel = live_path_for(f)
        live_abs = Path(live_rel.replace("~", str(Path.home()), 1))
        repo_abs = root / f
        repo_hash, live_hash = sha256_of(repo_abs), sha256_of(live_abs)
        if live_hash is None:
            status = "new"
        elif live_hash != repo_hash:
            status = "modified"
        else:
            status = "ok"
        ev = FileEvidence(f, live_rel, status, repo_last_commit=last_commit(root, f))
        if status != "ok":
            enclosing = find_enclosing_git_repo(live_abs)
            if enclosing is not None and enclosing != root:
                rel_in_that_repo = str(live_abs.relative_to(enclosing))
                ev.live_repo_root = str(enclosing)
                ev.live_last_commit = last_commit(enclosing, rel_in_that_repo)
            if status == "modified":
                ev.diff_snippet = unified_diff_snippet(repo_abs, live_abs)
        out.append(ev)
    return out


def evidence_remote(root: Path, files: list[str], host: str) -> list[FileEvidence]:
    live_rels = [live_path_for(f) for f in files]
    remote_paths = [lr.replace("~", "$HOME", 1) for lr in live_rels]
    script = "for p in " + " ".join(f'"{p}"' for p in remote_paths) + "; do " \
        'if [ -f "$p" ]; then sha256sum "$p" | cut -d" " -f1; else echo MISSING; fi; done'
    out = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", host, "bash", "-c", script],
        capture_output=True, text=True, check=True,
    )
    remote_hashes = out.stdout.splitlines()
    if len(remote_hashes) != len(files):
        raise RuntimeError(f"remote hash count mismatch on {host}: expected {len(files)}, got {len(remote_hashes)}")
    results = []
    for f, live_rel, remote_hash in zip(files, live_rels, remote_hashes):
        repo_hash = sha256_of(root / f)
        if remote_hash == "MISSING":
            status = "new"
        elif remote_hash != repo_hash:
            status = "modified"
        else:
            status = "ok"
        results.append(FileEvidence(f, live_rel, status, repo_last_commit=last_commit(root, f)))
    return results


def cmd_report(args: argparse.Namespace) -> int:
    root = repo_root()
    files = collect_full_scope(root) if args.full else collect_core_scope(root)
    scope_name = "FULL" if args.full else "CORE (top-6 highlighted skills)"

    targets: dict[str, list[FileEvidence]] = {}
    if not args.local_only:
        targets["local"] = evidence_local(root, files)
    for host in args.remote:
        targets[f"remote:{host}"] = evidence_remote(root, files, host)

    if args.json:
        print(json.dumps({
            "scope": scope_name,
            "file_count": len(files),
            "targets": {name: [asdict(e) for e in evs] for name, evs in targets.items()},
        }, indent=2))
        return 0

    print(f"Scope: {scope_name} — {len(files)} files")
    for name, evs in targets.items():
        new_ = [e for e in evs if e.status == "new"]
        mod_ = [e for e in evs if e.status == "modified"]
        ok_ = [e for e in evs if e.status == "ok"]
        print(f"\n=== {name}: {len(evs)} files — {len(new_)} new, {len(mod_)} modified, {len(ok_)} in sync ===")
        for e in new_:
            print(f"  NEW      {e.live_rel}  (repo: {e.repo_last_commit})")
        for e in mod_:
            note = f" [live tracked in {e.live_repo_root}, last: {e.live_last_commit}]" if e.live_repo_root else ""
            print(f"  MODIFIED {e.live_rel}  (repo: {e.repo_last_commit}){note}")
    print("\nThis is evidence only — nothing was written. Use `apply` with an explicit --direction to write.")
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    root = repo_root()
    paths = args.paths
    if args.direction == "repo-to-live":
        if args.remote:
            _apply_remote_repo_to_live(root, paths, args.remote)
        else:
            for p in paths:
                live_abs = Path(live_path_for(p).replace("~", str(Path.home()), 1))
                live_abs.parent.mkdir(parents=True, exist_ok=True)
                live_abs.write_bytes((root / p).read_bytes())
                print(f"repo -> live: {p}")
    else:  # live-to-repo
        if args.remote:
            _apply_remote_live_to_repo(root, paths, args.remote)
        else:
            for p in paths:
                live_abs = Path(live_path_for(p).replace("~", str(Path.home()), 1))
                (root / p).parent.mkdir(parents=True, exist_ok=True)
                (root / p).write_bytes(live_abs.read_bytes())
                print(f"live -> repo: {p}")
    return 0


def _apply_remote_repo_to_live(root: Path, paths: list[str], host: str) -> None:
    import tarfile
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
        tar_path = tmp.name
    with tarfile.open(tar_path, "w:gz") as tar:
        for p in paths:
            tar.add(root / p, arcname=p)
    remote_tar = "/tmp/sync_live_config_payload.tar.gz"
    subprocess.run(["scp", "-o", "ConnectTimeout=10", tar_path, f"{host}:{remote_tar}"], check=True)
    manifest = "\n".join(f"{p}\t{live_path_for(p).replace('~', '$HOME', 1)}" for p in paths)
    remote_script = f"""set -e
mkdir -p /tmp/sync_live_config_extract
tar -xzf {remote_tar} -C /tmp/sync_live_config_extract
while IFS=$'\\t' read -r src dest; do
  mkdir -p "$(dirname "$dest")"
  cp "/tmp/sync_live_config_extract/$src" "$dest"
done <<'MANIFEST_EOF'
{manifest}
MANIFEST_EOF
rm -rf /tmp/sync_live_config_extract {remote_tar}
"""
    subprocess.run(["ssh", "-o", "ConnectTimeout=15", host, "bash", "-c", remote_script], check=True)
    Path(tar_path).unlink(missing_ok=True)
    for p in paths:
        print(f"repo -> {host}: {p}")


def _apply_remote_live_to_repo(root: Path, paths: list[str], host: str) -> None:
    for p in paths:
        remote_path = live_path_for(p).replace("~", "$HOME", 1)
        out = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=15", host, "cat", remote_path],
            capture_output=True, check=True,
        )
        (root / p).parent.mkdir(parents=True, exist_ok=True)
        (root / p).write_bytes(out.stdout)
        print(f"{host} -> repo: {p}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)

    rp = sub.add_parser("report", help="gather diff evidence (no writes)")
    rp.add_argument("--full", action="store_true")
    rp.add_argument("--remote", action="append", default=[], metavar="HOST")
    rp.add_argument("--local-only", action="store_true")
    rp.add_argument("--json", action="store_true", help="machine-readable evidence for the skill to reason over")
    rp.set_defaults(func=cmd_report)

    ap_apply = sub.add_parser("apply", help="mechanically copy explicit paths in an explicit direction")
    ap_apply.add_argument("--direction", required=True, choices=["repo-to-live", "live-to-repo"])
    ap_apply.add_argument("--paths", required=True, nargs="+", metavar="REPO_REL_PATH")
    ap_apply.add_argument("--remote", metavar="HOST", help="target this SSH host instead of the local machine")
    ap_apply.set_defaults(func=cmd_apply)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
