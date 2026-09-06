#!/usr/bin/env python3
"""Evidence-gathering + mechanical-copy tool for repo<->live agent-config sync.

This tool makes NO judgment about which side (repo vs. live) is fresher —
that call belongs to the `sync-live-config` SKILL.md, which reads this
tool's evidence report and decides per-file direction. The tool only:

  report  Diff repo vs. live (and optionally remote hosts), with enough
          context (last-commit metadata on both sides, a capped unified
          diff for small text files, and live-only files invisible to a
          repo-tracked-file scan) for a model to judge staleness itself.
  apply   Mechanically copy an explicit list of paths in an explicit,
          caller-chosen direction, after validating every path stays
          within the allowed roots. Never infers direction.

Scope is either the README's highlighted-skills table (default -- whatever
that table currently lists, parsed live rather than a fixed count) or every
tracked file under .claude/, .codex/hooks/, hermes/skills/ (--full).
"""
from __future__ import annotations

import argparse
import base64
import difflib
import hashlib
import json
import re
import shlex
import subprocess
import sys
import tarfile
import tempfile
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath

TOP_LEVEL_MAP = {
    ".claude/": ".claude/",
    ".codex/hooks/": ".codex/hooks/",
    "hermes/skills/": ".hermes/skills/",
}
DIFF_SNIPPET_MAX_BYTES = 200_000
DIFF_SNIPPET_MAX_LINES = 60
NOISE_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
NOISE_SUFFIXES = {".pyc", ".pyo"}
NOISE_NAMES = {".DS_Store"}
RS, FS, GS = "\x1e", "\x1f", "\x1d"  # record / field / (nested-commit) group separators


def repo_root() -> Path:
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=Path(__file__).resolve().parent,
        capture_output=True, text=True, check=True,
    )
    return Path(out.stdout.strip())


_SAFE_PATH_RE = re.compile(r"^[A-Za-z0-9._/-]+$")


def validate_repo_rel(p: str) -> str:
    """Reject anything that isn't a plain, non-traversing path under an allowed root.

    Every one of these paths eventually becomes an argv element or heredoc
    line sent over `ssh` for a remote target, where OpenSSH flattens trailing
    command arguments into one string re-parsed by the remote shell — a `;`,
    backtick, quote, or newline here is a remote-command-injection vector, not
    just a local filesystem-escape one. The allowlist is deliberately strict:
    every currently tracked path under the allowed roots matches it.
    """
    if not _SAFE_PATH_RE.match(p):
        raise ValueError(f"unsafe path (disallowed characters): {p!r}")
    pure = PurePosixPath(p)
    if pure.is_absolute() or ".." in pure.parts or p != pure.as_posix():
        raise ValueError(f"unsafe path: {p!r}")
    if not any(p.startswith(prefix) for prefix in TOP_LEVEL_MAP):
        raise ValueError(f"path {p!r} is not under an allowed root: {sorted(TOP_LEVEL_MAP)}")
    return p


def _matched_top_level(repo_rel: str) -> tuple[str, str]:
    """Return the (repo_prefix, live_prefix) pair repo_rel actually matched."""
    validate_repo_rel(repo_rel)
    for prefix, live_prefix in TOP_LEVEL_MAP.items():
        if repo_rel.startswith(prefix):
            return prefix, live_prefix
    raise AssertionError("unreachable: validate_repo_rel already checked this")


def live_rel_for(repo_rel: str) -> str:
    """repo-relative path -> live-relative path (relative to `home`, no leading slash)."""
    prefix, live_prefix = _matched_top_level(repo_rel)
    return live_prefix + repo_rel[len(prefix):]


def live_abs_for(repo_rel: str, home: Path) -> Path:
    """Resolve repo_rel to an absolute live path, contained within its specific
    mapped root (e.g. home/.claude), not merely "somewhere under $HOME".

    A containment check against the whole home directory is not enough: a
    symlink at, say, `~/.claude/skills/foo/SKILL.md` pointing at
    `~/.ssh/id_rsa` resolves to a path that IS relative to `$HOME` and would
    pass a home-wide check while still being a write to an arbitrary file
    elsewhere under the user's home directory (reproduced in review).
    """
    _, live_prefix = _matched_top_level(repo_rel)
    live_rel = live_rel_for(repo_rel)
    allowed_root = (home / live_prefix).resolve()
    candidate = (home / live_rel).resolve()
    if not candidate.is_relative_to(allowed_root):
        raise ValueError(f"resolved live path escapes its allowed root {allowed_root}: {candidate}")
    return candidate


def repo_abs_for(root: Path, repo_rel: str) -> Path:
    """Resolve repo_rel to an absolute repo path, contained within its specific
    mapped root (same reasoning as live_abs_for)."""
    prefix, _ = _matched_top_level(repo_rel)
    allowed_root = (root / prefix).resolve()
    candidate = (root / repo_rel).resolve()
    if not candidate.is_relative_to(allowed_root):
        raise ValueError(f"resolved repo path escapes its allowed root {allowed_root}: {candidate}")
    return candidate


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
    """Find .claude/commands/*.md that dispatch to this skill.

    Matches on `skills/<name>/SKILL.md` regardless of the path prefix used
    (`${CLAUDE_HOME:-$HOME/.claude}/...`, `~/.claude/...`, etc.) — never a
    bare name substring, which would false-match `advice` inside `web-advice`.
    """
    name = skill_dir.split("/")[-1]
    pattern = re.compile(rf"skills/{re.escape(name)}/SKILL\.md")
    hits = []
    for f in sorted((root / ".claude" / "commands").glob("*.md")):
        text = f.read_text(encoding="utf-8", errors="ignore")
        if pattern.search(text):
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


def scope_live_roots(files: list[str], full: bool) -> list[str]:
    """Live-relative directory roots to walk for live-only-file detection."""
    if full:
        return list(TOP_LEVEL_MAP.values())
    # Core scope: walk exactly the highlighted skill directories, not all of .claude/.
    roots = set()
    for f in files:
        if f.startswith(".claude/skills/"):
            parts = f.split("/")
            roots.add("/".join(parts[:3]) + "/")  # .claude/skills/<name>/
    return [live_rel_for(r.rstrip("/")) + "/" for r in roots]


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


def find_enclosing_git_repo(path: Path, home: Path) -> Path | None:
    """Walk up from `path` looking for a .git dir, without escaping `home`."""
    cur = path.parent if path.is_file() or path.suffix else path
    home_r = home.resolve()
    while cur.is_relative_to(home_r) or cur == home_r:
        if (cur / ".git").exists():
            return cur
        if cur == home_r:
            break
        cur = cur.parent
    return None


def unified_diff_text(a_text: str, b_text: str, a_label: str, b_label: str) -> str | None:
    a_lines = a_text.splitlines(keepends=True)
    b_lines = b_text.splitlines(keepends=True)
    lines = list(difflib.unified_diff(b_lines, a_lines, fromfile=b_label, tofile=a_label, lineterm=""))
    if not lines:
        return None
    truncated = len(lines) > DIFF_SNIPPET_MAX_LINES
    lines = lines[:DIFF_SNIPPET_MAX_LINES]
    if truncated:
        lines.append("... (truncated)")
    return "\n".join(lines)


def unified_diff_snippet(repo_abs: Path, live_abs: Path) -> str | None:
    try:
        if repo_abs.stat().st_size > DIFF_SNIPPET_MAX_BYTES or live_abs.stat().st_size > DIFF_SNIPPET_MAX_BYTES:
            return None
        a = repo_abs.read_text(encoding="utf-8", errors="strict")
        b = live_abs.read_text(encoding="utf-8", errors="strict")
    except (UnicodeDecodeError, OSError):
        return None
    return unified_diff_text(a, b, "repo", "live")


@dataclass
class FileEvidence:
    repo_rel: str
    live_rel: str
    status: str  # "new" | "modified" | "ok" | "live_only" | "symlink"
    repo_last_commit: dict | None = None
    live_last_commit: dict | None = None
    live_repo_root: str | None = None  # set if live path lives inside its own distinct git repo
    diff_snippet: str | None = None


def evidence_local(root: Path, files: list[str], home: Path, full: bool) -> list[FileEvidence]:
    out = []
    seen_live_rel = set()
    for f in files:
        live_rel = live_rel_for(f)
        seen_live_rel.add(live_rel)
        live_abs = live_abs_for(f, home)
        repo_abs = repo_abs_for(root, f)
        repo_hash, live_hash = sha256_of(repo_abs), sha256_of(live_abs)
        if live_hash is None:
            status = "new"
        elif live_hash != repo_hash:
            status = "modified"
        else:
            status = "ok"
        ev = FileEvidence(f, live_rel, status, repo_last_commit=last_commit(root, f))
        if status != "ok":
            enclosing = find_enclosing_git_repo(live_abs, home)
            if enclosing is not None and enclosing != root:
                rel_in_that_repo = str(live_abs.relative_to(enclosing))
                ev.live_repo_root = str(enclosing)
                ev.live_last_commit = last_commit(enclosing, rel_in_that_repo)
            if status == "modified":
                ev.diff_snippet = unified_diff_snippet(repo_abs, live_abs)
        out.append(ev)

    for live_root_rel in scope_live_roots(files, full):
        live_root_abs = home / live_root_rel
        if not live_root_abs.is_dir():
            continue
        for f in sorted(live_root_abs.rglob("*")):
            if not f.is_file() or NOISE_DIRS.intersection(f.parts) or f.suffix in NOISE_SUFFIXES or f.name in NOISE_NAMES:
                continue
            live_rel = str(f.relative_to(home))
            if live_rel in seen_live_rel:
                continue
            seen_live_rel.add(live_rel)
            ev = FileEvidence(repo_rel="(not in repo)", live_rel=live_rel, status="live_only")
            enclosing = find_enclosing_git_repo(f, home)
            if enclosing is not None and enclosing != root:
                ev.live_repo_root = str(enclosing)
                ev.live_last_commit = last_commit(enclosing, str(f.relative_to(enclosing)))
            out.append(ev)
    return out


# Shared by every remote script (evidence gathering and both apply directions):
# refuses to follow a symlink anywhere between a base directory and a target
# path -- not just at the final path component, which a leaf-only `[ -L ]`
# check would miss for a symlinked PARENT directory (reproduced in review).
# Requires `bash` (uses `local`/arrays), which every call site already invokes
# via `bash -s`.
_SYMLINK_GUARD_FN = r'''
path_has_symlink_component() {
  local base="$1" target="$2" rel check part
  case "$target" in
    "$base"/*) rel="${target#"$base"/}" ;;
    *) return 0 ;;
  esac
  check="$base"
  local IFS='/'
  for part in $rel; do
    check="$check/$part"
    if [ -L "$check" ]; then
      return 0
    fi
  done
  return 1
}
'''

_REMOTE_BATCH_SCRIPT = r'''
set -e
RS=$'\x1e'
FS=$'\x1f'
GS=$'\x1d'
while IFS= read -r p; do
  if [ ! -f "$p" ]; then
    printf 'MISSING%s' "$RS"
    continue
  fi
  # Check for a symlinked path component BEFORE any inspection at all -- an
  # earlier version only gated the base64 content read here, which still let
  # a symlinked path's exact sha256/size/commit metadata through as a
  # confirmation oracle for an arbitrary file elsewhere on the remote host
  # (reproduced in review: hash+size of a symlinked ~/.ssh/id_rsa-equivalent
  # were still reported even though content_b64 was correctly withheld).
  if path_has_symlink_component "$REMOTE_HOME" "$p"; then
    printf 'SYMLINK%s' "$RS"
    continue
  fi
  # sha256sum is GNU-coreutils-only; `shasum -a 256` is the macOS/BSD equivalent.
  if command -v sha256sum >/dev/null 2>&1; then
    hash=$(sha256sum "$p" | cut -d' ' -f1)
  else
    hash=$(shasum -a 256 "$p" | cut -d' ' -f1)
  fi
  size=$(wc -c < "$p" | tr -d ' ')
  dir=$(dirname "$p")
  repo_root=$(git -C "$dir" rev-parse --show-toplevel 2>/dev/null || true)
  commit=""
  if [ -n "$repo_root" ]; then
    # Pass the absolute path straight to `git -C "$dir" log`, letting git do
    # its own pathspec resolution, instead of manually prefix-stripping
    # against $repo_root -- a prior version did that (to avoid GNU-only
    # `realpath --relative-to`) and silently dropped commit metadata whenever
    # $HOME or any path component was a symlink, since `git rev-parse
    # --show-toplevel` returns the physical (symlink-resolved) path while $p
    # does not.
    #
    # Uses GS (not FS) to join sha/date/author/subject -- this record's OWN
    # fields are FS-delimited, so the commit's subfields must use a
    # different separator or `record.split(FS)` silently misparses every
    # field after this one (a real bug caught in review: content_b64 ended
    # up holding the commit date).
    commit=$(git -C "$dir" log -1 --format="%H${GS}%aI${GS}%an${GS}%s" -- "$p" 2>/dev/null || true)
  fi
  content_b64=""
  if [ "$size" -le 200000 ]; then
    content_b64=$(base64 < "$p" | tr -d '\n')
  fi
  printf 'FOUND%s%s%s%s%s%s%s%s%s' \
    "$FS" "$hash" "$FS" "$repo_root" "$FS" "$commit" "$FS" "$content_b64" "$RS"
done
'''


def evidence_remote(root: Path, files: list[str], host: str) -> list[FileEvidence]:
    # Resolve $HOME locally (one short, unambiguous ssh round trip) so every path
    # handed to the remote script is already an absolute literal — the remote
    # side never needs to expand $HOME itself, which is what caused the earlier
    # heredoc-quoting bug in the apply path.
    remote_home = _remote_home(host)
    remote_paths = [f"{remote_home}/{live_rel_for(f)}" for f in files]
    # Script arrives via stdin (immune to ssh's argv-flattening/re-quoting of the
    # command line); paths arrive as trailing argv ("$@") after `--`. validate_repo_rel
    # already restricts these to a safe character allowlist, but OpenSSH still
    # flattens the whole trailing command line into one string for the remote
    # shell to re-parse, so quote each element too — defense in depth for the
    # exact class of bug this whole rewrite exists to close.
    quoted_paths = [shlex.quote(p) for p in remote_paths]
    script = (
        _SYMLINK_GUARD_FN
        + f"REMOTE_HOME={shlex.quote(remote_home)}\n"
        + _REMOTE_BATCH_SCRIPT.replace('while IFS= read -r p; do', 'for p in "$@"; do')
    )
    proc = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", host, "bash", "-s", "--", *quoted_paths],
        input=script, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"remote evidence script failed on {host}: {proc.stderr.strip()}")
    records = [r for r in proc.stdout.split(RS) if r.strip()]
    if len(records) != len(files):
        raise RuntimeError(
            f"remote record count mismatch on {host}: expected {len(files)}, got {len(records)}\n{proc.stderr}"
        )
    results = []
    for f, record in zip(files, records):
        fields = record.split(FS)
        kind = fields[0]
        if kind == "MISSING":
            results.append(FileEvidence(f, live_rel_for(f), "new", repo_last_commit=last_commit(root, f)))
            continue
        if kind == "SYMLINK":
            # No hash, size, commit, or content is computed remotely for this
            # path at all -- even metadata like an exact hash/size is a
            # confirmation oracle for an arbitrary file elsewhere on the
            # remote host if the path is symlinked outside its mapped root.
            results.append(FileEvidence(f, live_rel_for(f), "symlink", repo_last_commit=last_commit(root, f)))
            continue
        if len(fields) != 5:
            # Fail loud, not silently-misparsed: a field-count mismatch here means
            # some value leaked an FS byte (or the wire protocol changed underneath
            # us) — trust nothing rather than guess which field is which.
            raise RuntimeError(f"malformed remote record for {f!r} on {host}: {len(fields)} fields, expected 5")
        _, remote_hash, remote_repo_root, remote_commit_raw, content_b64 = fields
        repo_abs = repo_abs_for(root, f)
        repo_hash = sha256_of(repo_abs)
        status = "modified" if remote_hash != repo_hash else "ok"
        ev = FileEvidence(f, live_rel_for(f), status, repo_last_commit=last_commit(root, f))
        if remote_repo_root:
            ev.live_repo_root = f"{host}:{remote_repo_root}"
        if remote_commit_raw:
            sha, date, author, subject = (remote_commit_raw.split(GS, 3) + ["", "", "", ""])[:4]
            ev.live_last_commit = {"sha": sha[:12], "date": date, "author": author, "subject": subject}
        if status == "modified" and content_b64:
            try:
                remote_text = base64.b64decode(content_b64).decode("utf-8")
                repo_text = repo_abs.read_text(encoding="utf-8")
                ev.diff_snippet = unified_diff_text(repo_text, remote_text, "repo", f"{host}:live")
            except (UnicodeDecodeError, ValueError):
                pass
        results.append(ev)
    return results


def cmd_report(args: argparse.Namespace) -> int:
    root = repo_root()
    home = Path(args.home).expanduser() if args.home else Path.home()
    if args.full:
        files = collect_full_scope(root)
        scope_name = "FULL"
    else:
        files = collect_core_scope(root)
        highlighted_count = len(parse_highlighted_skill_dirs(root))
        scope_name = f"CORE ({highlighted_count} highlighted skills from README)"

    targets: dict[str, list[FileEvidence]] = {}
    if not args.remote_only:
        targets["local"] = evidence_local(root, files, home, args.full)
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
        live_only_ = [e for e in evs if e.status == "live_only"]
        symlink_ = [e for e in evs if e.status == "symlink"]
        print(f"\n=== {name}: {len(evs)} evidence rows — {len(new_)} new, {len(mod_)} modified, "
              f"{len(ok_)} in sync, {len(live_only_)} live-only, {len(symlink_)} symlinked (withheld) ===")
        for e in new_:
            print(f"  NEW       {e.live_rel}  (repo: {e.repo_last_commit})")
        for e in mod_:
            note = f" [live tracked in {e.live_repo_root}, last: {e.live_last_commit}]" if e.live_repo_root else ""
            print(f"  MODIFIED  {e.live_rel}  (repo: {e.repo_last_commit}){note}")
        for e in live_only_:
            note = f" [live tracked in {e.live_repo_root}, last: {e.live_last_commit}]" if e.live_repo_root else " [not in any repo]"
            print(f"  LIVE-ONLY {e.live_rel}{note}")
        for e in symlink_:
            print(f"  SYMLINK   {e.live_rel}  [path has a symlinked component; hash/size/content withheld — inspect manually]")
    print("\nThis is evidence only — nothing was written. Use `apply` with an explicit --direction to write.")
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    root = repo_root()
    home = Path(args.home).expanduser() if args.home else Path.home()
    paths = [validate_repo_rel(p) for p in args.paths]
    if args.direction == "repo-to-live":
        if args.remote:
            _apply_remote_repo_to_live(root, paths, args.remote)
        else:
            for p in paths:
                live_abs = live_abs_for(p, home)
                live_abs.parent.mkdir(parents=True, exist_ok=True)
                live_abs.write_bytes(repo_abs_for(root, p).read_bytes())
                print(f"repo -> live: {p}")
    else:  # live-to-repo
        if args.remote:
            _apply_remote_live_to_repo(root, paths, args.remote)
        else:
            for p in paths:
                repo_abs = repo_abs_for(root, p)
                repo_abs.parent.mkdir(parents=True, exist_ok=True)
                repo_abs.write_bytes(live_abs_for(p, home).read_bytes())
                print(f"live -> repo: {p}")
    return 0


def _validate_host(host: str) -> str:
    """Reject a host string OpenSSH's own argument parser could interpret as
    an option instead of a hostname (e.g. `-oProxyCommand=...`) -- ssh does
    not reliably treat a positional-looking argument as "not an option" just
    because of where it appears on the command line (verified: `-oProxyCommand=...`
    is parsed as an option even in the hostname position)."""
    if not host or host.startswith("-"):
        raise ValueError(f"unsafe host (looks like an ssh option): {host!r}")
    return host


def _remote_home(host: str) -> str:
    host = _validate_host(host)
    out = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", host, "printf", "%s", "$HOME"],
        capture_output=True, text=True, check=True,
    )
    remote_home = out.stdout.strip()
    if not remote_home.startswith("/"):
        raise RuntimeError(f"could not resolve $HOME on {host}: got {remote_home!r}")
    return remote_home


def _apply_remote_repo_to_live(root: Path, paths: list[str], host: str) -> None:
    remote_home = _remote_home(host)
    # Unpredictable staging paths: a fixed /tmp name is a race/collision target
    # for another concurrent run (or, on a shared multi-user host, another
    # user) on the same machine.
    token = uuid.uuid4().hex
    remote_tar = f"/tmp/sync_live_config_{token}.tar.gz"
    remote_extract = f"/tmp/sync_live_config_{token}_extract"
    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
        tar_path = tmp.name
    try:
        with tarfile.open(tar_path, "w:gz") as tar:
            for p in paths:
                tar.add(repo_abs_for(root, p), arcname=p)
        subprocess.run(["scp", "-o", "ConnectTimeout=10", tar_path, f"{host}:{remote_tar}"], check=True)
        # Destinations are fully resolved here (Python-side), never left for the
        # remote shell to expand — that literal-$HOME expansion bug is what this fixes.
        manifest = "\n".join(f"{p}\t{remote_home}/{live_rel_for(p)}" for p in paths)
        remote_script = _SYMLINK_GUARD_FN + f"""set -e
mkdir -p {remote_extract}
tar -xzf {remote_tar} -C {remote_extract}
REMOTE_HOME={shlex.quote(remote_home)}
while IFS=$'\\t' read -r src dest; do
  # Refuse to follow a pre-existing symlink anywhere between $REMOTE_HOME and
  # dest, not just at the leaf: a symlinked PARENT directory (e.g.
  # .claude/skills/foo -> ~/.ssh) would let `cp` write through it even though
  # dest itself is not a symlink (reproduced in review -- a leaf-only `-L`
  # check misses exactly this case).
  if path_has_symlink_component "$REMOTE_HOME" "$dest"; then
    echo "refusing to write through a symlinked path component: $dest" >&2
    exit 1
  fi
  mkdir -p "$(dirname "$dest")"
  cp "{remote_extract}/$src" "$dest"
done <<'MANIFEST_EOF'
{manifest}
MANIFEST_EOF
rm -rf {remote_extract} {remote_tar}
"""
        subprocess.run(["ssh", "-o", "ConnectTimeout=15", host, "bash", "-s"], input=remote_script, text=True, check=True)
    finally:
        Path(tar_path).unlink(missing_ok=True)
    for p in paths:
        print(f"repo -> {host}: {p}")


def _apply_remote_live_to_repo(root: Path, paths: list[str], host: str) -> None:
    remote_home = _remote_home(host)
    for p in paths:
        remote_path = f"{remote_home}/{live_rel_for(p)}"
        # A bare `ssh host cat path` follows symlinks with no containment check
        # at all -- reproduced in review: a remote path symlinked to a private
        # key pulled its content straight into the repo. Route through the
        # same shared guard used by the write side, refusing to `cat` through
        # any symlinked path component before it ever reaches stdout.
        remote_script = _SYMLINK_GUARD_FN + f"""set -e
REMOTE_HOME={shlex.quote(remote_home)}
TARGET={shlex.quote(remote_path)}
if path_has_symlink_component "$REMOTE_HOME" "$TARGET"; then
  echo "refusing to read through a symlinked path component: $TARGET" >&2
  exit 1
fi
cat "$TARGET"
"""
        out = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=15", host, "bash", "-s"],
            input=remote_script.encode(), capture_output=True, check=True,
        )
        repo_abs = repo_abs_for(root, p)
        repo_abs.parent.mkdir(parents=True, exist_ok=True)
        repo_abs.write_bytes(out.stdout)
        print(f"{host} -> repo: {p}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)

    rp = sub.add_parser("report", help="gather diff evidence (no writes)")
    rp.add_argument("--full", action="store_true")
    rp.add_argument("--remote", action="append", default=[], metavar="HOST")
    rp.add_argument("--remote-only", action="store_true", help="skip this machine's own live config; only check --remote hosts")
    rp.add_argument("--json", action="store_true", help="machine-readable evidence for the skill to reason over")
    rp.add_argument("--home", metavar="DIR", help="override home directory (for tests)")
    rp.set_defaults(func=cmd_report)

    ap_apply = sub.add_parser("apply", help="mechanically copy explicit paths in an explicit direction")
    ap_apply.add_argument("--direction", required=True, choices=["repo-to-live", "live-to-repo"])
    ap_apply.add_argument("--paths", required=True, nargs="+", metavar="REPO_REL_PATH")
    ap_apply.add_argument("--remote", metavar="HOST", help="target this SSH host instead of the local machine")
    ap_apply.add_argument("--home", metavar="DIR", help="override home directory (for tests)")
    ap_apply.set_defaults(func=cmd_apply)

    args = ap.parse_args()
    try:
        return args.func(args)
    except (ValueError, RuntimeError, subprocess.CalledProcessError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
