#!/usr/bin/env python3
"""Propagate this repo's .claude/ (+ .codex/hooks, hermes/skills) content to
live agent-config directories: this machine's ~/.claude (+ ~/.codex, ~/.hermes)
and, optionally, remote hosts over SSH.

Default scope: only the "top 6" highlighted skills from README.md's
"Highlighted skills" table (plus any command dispatcher .md files that
reference them). Use --full to compare/sync the entire tracked .claude/,
.codex/hooks/, and hermes/skills/ trees instead.

This is one-directional: repo -> live. It never deletes a live-only file and
never reads live state back into the repo. Default is a dry-run report;
pass --apply to actually write.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

TOP_LEVEL_MAP = {
    ".claude/": "~/.claude/",
    ".codex/": "~/.codex/",
    "hermes/": "~/.hermes/",
}


def repo_root() -> Path:
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=Path(__file__).resolve().parent,
        capture_output=True,
        text=True,
        check=True,
    )
    return Path(out.stdout.strip())


def live_path_for(repo_rel: str) -> str:
    for prefix, live_prefix in TOP_LEVEL_MAP.items():
        if repo_rel.startswith(prefix):
            return live_prefix + repo_rel[len(prefix):]
    raise ValueError(f"no live mapping for {repo_rel}")


def parse_highlighted_skill_dirs(root: Path) -> list[str]:
    readme = (root / "README.md").read_text(encoding="utf-8")
    m = re.search(
        r"### Highlighted skills.*?\n(.*?)\n\n", readme, re.DOTALL
    )
    if not m:
        raise RuntimeError("could not find 'Highlighted skills' table in README.md")
    table = m.group(1)
    dirs = sorted(set(re.findall(r"(\.claude/skills/[a-zA-Z0-9_-]+)/SKILL\.md", table)))
    if not dirs:
        raise RuntimeError("found the highlighted-skills table but no skill links in it")
    return dirs


def find_command_files_for_skill(root: Path, skill_dir: str) -> list[str]:
    skill_md_suffix = f"{skill_dir}/SKILL.md"
    hits = []
    commands_dir = root / ".claude" / "commands"
    for f in sorted(commands_dir.glob("*.md")):
        text = f.read_text(encoding="utf-8", errors="ignore")
        if skill_md_suffix in text or skill_dir.split("/")[-1] in text:
            hits.append(str(f.relative_to(root)))
    return hits


def git_tracked_files(root: Path, *paths: str) -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", *paths],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return [l for l in out.stdout.splitlines() if l.strip()]


def collect_core_scope(root: Path) -> list[str]:
    """Top-6 highlighted skills (tracked dir contents) + their command dispatchers."""
    files: list[str] = []
    for skill_dir in parse_highlighted_skill_dirs(root):
        skill_path = root / skill_dir
        if not skill_path.is_dir():
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
    """Every tracked file under .claude/, .codex/hooks/, hermes/skills/."""
    return git_tracked_files(root, ".claude", ".codex/hooks", "hermes/skills")


def sha256_of(path: Path) -> str | None:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


@dataclass
class Diff:
    repo_rel: str
    live_rel: str
    status: str  # "new" | "modified" | "ok"


def diff_local(root: Path, files: list[str]) -> list[Diff]:
    diffs = []
    for f in files:
        live_rel = live_path_for(f)
        live_abs = Path(live_rel.replace("~", str(Path.home()), 1))
        repo_abs = root / f
        repo_hash = sha256_of(repo_abs)
        live_hash = sha256_of(live_abs)
        if live_hash is None:
            status = "new"
        elif live_hash != repo_hash:
            status = "modified"
        else:
            status = "ok"
        diffs.append(Diff(f, live_rel, status))
    return diffs


def diff_remote(root: Path, files: list[str], host: str) -> list[Diff]:
    live_rels = [live_path_for(f) for f in files]
    # Ask the remote host for sha256 of each candidate path in one round trip.
    remote_paths = [lr.replace("~", "$HOME", 1) for lr in live_rels]
    script = "for p in " + " ".join(f'"{p}"' for p in remote_paths) + "; do " \
        'if [ -f "$p" ]; then sha256sum "$p" | cut -d" " -f1; else echo MISSING; fi; done'
    out = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", host, "bash", "-c", script],
        capture_output=True, text=True, check=True,
    )
    remote_hashes = out.stdout.splitlines()
    if len(remote_hashes) != len(files):
        raise RuntimeError(
            f"remote hash count mismatch on {host}: expected {len(files)}, got {len(remote_hashes)}"
        )
    diffs = []
    for f, live_rel, remote_hash in zip(files, live_rels, remote_hashes):
        repo_hash = sha256_of(root / f)
        if remote_hash == "MISSING":
            status = "new"
        elif remote_hash != repo_hash:
            status = "modified"
        else:
            status = "ok"
        diffs.append(Diff(f, live_rel, status))
    return diffs


def apply_local(root: Path, diffs: list[Diff]) -> None:
    for d in diffs:
        if d.status == "ok":
            continue
        live_abs = Path(d.live_rel.replace("~", str(Path.home()), 1))
        live_abs.parent.mkdir(parents=True, exist_ok=True)
        live_abs.write_bytes((root / d.repo_rel).read_bytes())


def apply_remote(root: Path, diffs: list[Diff], host: str) -> None:
    to_copy = [d for d in diffs if d.status != "ok"]
    if not to_copy:
        return
    import tarfile
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
        tar_path = tmp.name
    with tarfile.open(tar_path, "w:gz") as tar:
        for d in to_copy:
            tar.add(root / d.repo_rel, arcname=d.repo_rel)
    remote_tar = "/tmp/sync_live_config_payload.tar.gz"
    subprocess.run(["scp", "-o", "ConnectTimeout", "10", tar_path, f"{host}:{remote_tar}"], check=True)
    manifest = "\n".join(f"{d.repo_rel}\t{d.live_rel.replace('~', '$HOME', 1)}" for d in to_copy)
    remote_script = f"""
set -e
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


def report(target: str, diffs: list[Diff]) -> bool:
    new_ = [d for d in diffs if d.status == "new"]
    mod_ = [d for d in diffs if d.status == "modified"]
    ok_ = [d for d in diffs if d.status == "ok"]
    print(f"\n=== {target}: {len(diffs)} files in scope — {len(new_)} new, {len(mod_)} modified, {len(ok_)} already in sync ===")
    for d in new_:
        print(f"  NEW      {d.live_rel}")
    for d in mod_:
        print(f"  MODIFIED {d.live_rel}")
    return bool(new_ or mod_)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--full", action="store_true", help="sync/compare the full .claude+.codex/hooks+hermes/skills tree instead of just the top-6 highlighted skills")
    ap.add_argument("--remote", action="append", default=[], metavar="HOST", help="also target this SSH host's live config (repeatable)")
    ap.add_argument("--apply", action="store_true", help="actually write changes (default is dry-run/report only)")
    ap.add_argument("--local-only", action="store_true", help="skip this machine's own ~/.claude and only touch --remote hosts")
    args = ap.parse_args()

    root = repo_root()
    files = collect_full_scope(root) if args.full else collect_core_scope(root)
    scope_name = "FULL" if args.full else "CORE (top-6 highlighted skills)"
    print(f"Scope: {scope_name} — {len(files)} files")

    any_diff = False

    if not args.local_only:
        local_diffs = diff_local(root, files)
        any_diff |= report("local (~)", local_diffs)
        if args.apply:
            apply_local(root, local_diffs)
            print("  -> applied")

    for host in args.remote:
        remote_diffs = diff_remote(root, files, host)
        any_diff |= report(f"remote:{host}", remote_diffs)
        if args.apply:
            apply_remote(root, remote_diffs, host)
            print("  -> applied")

    if not args.apply and any_diff:
        print("\nDry run only — rerun with --apply to write these changes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
