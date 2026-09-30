#!/usr/bin/env python3
"""Verify falsifiable claims in a PR body against ground truth.

Extracts test counts, CI check counts, review-thread counts, git SHAs, and
file paths mentioned in a PR body, then re-derives each from a live source
(git objects, `gh pr view`, GitHub GraphQL) and reports PASS/FAIL/UNVERIFIABLE
per claim. This is lexical extraction of numbers/hashes near known keywords,
not semantic intent classification.

Design: never print PASS for something that was not actually checked (an
unverifiable claim is not a passing claim), so the exit code cannot be
satisfied by prose alone.

Usage:
    ./vpython scripts/verify_pr_claims.py --pr 9739
    ./vpython scripts/verify_pr_claims.py --pr 9739 --body-file draft.md

Exit 0 only if every detected claim verifies as PASS. Exit 1 otherwise
(any FAIL or UNVERIFIABLE claim, or a hard error reaching ground truth).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

# Global repo directory, set by main() from command-line argument
_repo_dir: Path | None = None  # noqa: PLW0603 -- module-level config set at startup
_repo_slug: str | None = None  # noqa: PLW0603 -- module-level config set at startup

GH_PACE_SECONDS = 1.0  # avoid secondary rate limits on rapid `gh` calls
GH_TIMEOUT = 30

_last_gh_call = [0.0]


def run(cmd: list[str], timeout: int = GH_TIMEOUT, cwd: Path | None = None):
    try:
        p = subprocess.run(  # noqa: S603 -- fixed argv arrays, no shell, read-only calls
            cmd, cwd=cwd or _repo_dir, capture_output=True, text=True, timeout=timeout, check=False
        )
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "TIMEOUT"
    except FileNotFoundError as exc:
        return 127, "", str(exc)


def gh_call(args: list[str], timeout: int = GH_TIMEOUT):
    """Run a `gh` subcommand, paced to avoid secondary rate limits."""
    wait = GH_PACE_SECONDS - (time.time() - _last_gh_call[0])
    if wait > 0:
        time.sleep(wait)
    cmd = ["gh"]
    # Add --repo if slug is known and not already in args
    if _repo_slug and "--repo" not in args:
        cmd.extend(["--repo", _repo_slug])
    cmd.extend(args)
    rc, out, err = run(cmd, timeout=timeout)
    _last_gh_call[0] = time.time()
    return rc, out, err


@dataclass
class Verdict:
    claim: str
    derived: str
    verdict: str  # PASS | FAIL | UNVERIFIABLE


# --------------------------------------------------------------------------
# Ground-truth lookups
# --------------------------------------------------------------------------


def get_pr_info(pr_number: int) -> dict | None:
    rc, out, err = gh_call(
        [
            "pr",
            "view",
            str(pr_number),
            "--json",
            "body,headRefOid,url,number",
        ]
    )
    if rc != 0:
        print(f"ERROR: gh pr view {pr_number} failed: {err.strip()}", file=sys.stderr)
        return None
    return json.loads(out)


def derive_repo_slug_from_git() -> str | None:
    """Extract owner/repo from git remote origin URL."""
    rc, out, err = run(["git", "remote", "get-url", "origin"])
    if rc != 0:
        if err:
            print(f"WARNING: git remote get-url failed: {err.strip()}", file=sys.stderr)
        return None
    url = out.strip()
    # Handle both git@github.com:owner/repo.git and https://github.com/owner/repo.git
    if "@" in url and ":" in url:
        url = url.split(":", 1)[1]
    if url.endswith(".git"):
        url = url[:-4]
    # Extract last two path components
    parts = url.rstrip("/").split("/")
    if len(parts) >= 2:
        return f"{parts[-2]}/{parts[-1]}"
    return None


def get_repo_slug() -> str | None:
    """Get the repo slug, trying git first, then gh as fallback."""
    # Try to get from git remote first (more reliable when not in a git repo's cwd)
    slug = derive_repo_slug_from_git()
    if slug:
        return slug
    # Fallback to gh (this requires being in the correct directory)
    rc, out, err = gh_call(["repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"])
    if rc != 0:
        if err:
            print(f"WARNING: gh repo view failed: {err.strip()}", file=sys.stderr)
        return None
    return out.strip()


def ensure_commit_local(sha: str) -> bool:
    """Best-effort: make sure `sha` is present in the local object DB."""
    rc, _, _ = run(["git", "cat-file", "-e", sha])
    if rc == 0:
        return True
    # Read-only network fetch of a single object; does not touch branches,
    # tags, or the working tree.
    run(["git", "fetch", "-q", "origin", sha], timeout=60)
    rc, _, _ = run(["git", "cat-file", "-e", sha])
    return rc == 0


def git_show(sha: str, path: str) -> str | None:
    if not ensure_commit_local(sha):
        return None
    rc, out, _ = run(["git", "show", f"{sha}:{path}"])
    if rc != 0:
        return None
    return out


def path_exists_at(sha: str, path: str) -> bool:
    if not ensure_commit_local(sha):
        return False
    rc, _, _ = run(["git", "cat-file", "-e", f"{sha}:{path}"])
    return rc == 0


def commit_exists(sha: str) -> bool:
    if not ensure_commit_local(sha):
        return False
    rc, kind, _ = run(["git", "cat-file", "-t", sha])
    return rc == 0 and kind.strip() == "commit"


def commit_time(sha: str) -> float | None:
    if not ensure_commit_local(sha):
        return None
    rc, out, _ = run(["git", "show", "-s", "--format=%ct", sha])
    if rc != 0 or not out.strip():
        return None
    try:
        return float(out.strip())
    except ValueError:
        return None


def get_status_rollup(pr_number: int) -> list | None:
    rc, out, err = gh_call(
        ["pr", "view", str(pr_number), "--json", "statusCheckRollup"]
    )
    if rc != 0:
        print(f"ERROR: gh pr view --json statusCheckRollup failed: {err.strip()}", file=sys.stderr)
        return None
    try:
        return json.loads(out).get("statusCheckRollup", [])
    except json.JSONDecodeError:
        return None


def analyze_rollup(rollup: list):
    counts: dict[str, int] = {}
    for item in rollup:
        state = (item.get("conclusion") or item.get("state") or "UNKNOWN").upper()
        counts[state] = counts.get(state, 0) + 1
    total = len(rollup)
    success = counts.get("SUCCESS", 0)
    return total, success, counts


def get_unresolved_review_threads(pr_number: int, slug: str) -> tuple[int, int] | None:
    """Return (unresolved_count, total_count) via GraphQL, or None on failure."""
    if "/" not in slug:
        return None
    owner, repo = slug.split("/", 1)
    query = (
        "query($owner:String!,$repo:String!,$pr:Int!,$cursor:String){"
        "repository(owner:$owner,name:$repo){"
        "pullRequest(number:$pr){"
        "reviewThreads(first:100,after:$cursor){nodes{isResolved}"
        "pageInfo{hasNextPage,endCursor}}}}}"
    )
    cursor: str | None = None
    seen_cursors: set[str] = set()
    unresolved = 0
    total = 0
    while True:
        args = [
            "api",
            "graphql",
            "-f",
            f"query={query}",
            "-F",
            f"owner={owner}",
            "-F",
            f"repo={repo}",
            "-F",
            f"pr={pr_number}",
        ]
        if cursor is not None:
            args.extend(["-F", f"cursor={cursor}"])
        rc, out, err = gh_call(args)
        if rc != 0:
            print(f"ERROR: reviewThreads GraphQL query failed: {err.strip()}", file=sys.stderr)
            return None
        try:
            connection = json.loads(out)["data"]["repository"]["pullRequest"]["reviewThreads"]
            nodes = connection["nodes"]
            page_info = connection["pageInfo"]
            has_next = page_info["hasNextPage"]
            next_cursor = page_info["endCursor"]
            if not isinstance(nodes, list) or not isinstance(page_info, dict):
                return None
            if not isinstance(has_next, bool):
                return None
            if has_next and (not isinstance(next_cursor, str) or not next_cursor):
                return None
            if not all(isinstance(node, dict) and isinstance(node.get("isResolved"), bool) for node in nodes):
                return None
        except (KeyError, TypeError, json.JSONDecodeError):
            return None
        total += len(nodes)
        unresolved += sum(1 for node in nodes if not node["isResolved"])
        if not has_next:
            return unresolved, total
        if next_cursor in seen_cursors or next_cursor == cursor:
            print("ERROR: reviewThreads GraphQL cursor did not advance", file=sys.stderr)
            return None
        seen_cursors.add(next_cursor)
        cursor = next_cursor


# --------------------------------------------------------------------------
# Claim extraction (lexical: numbers/hashes near known keywords, not intent)
# --------------------------------------------------------------------------

TEST_PATH_RE = re.compile(r"[\w][\w\-./]*\.(?:py|js|jsx|ts|tsx)")
SHA_RE = re.compile(r"\b(?=[0-9A-Fa-f]*[A-Fa-f])[0-9A-Fa-f]{7,40}\b")
ANY_PATH_RE = re.compile(r"(?:~|/)?(?:[\w.\-]+/)+[\w.\-]+\.[A-Za-z0-9]{1,6}")
URL_RE = re.compile(r"https?://\S+")

TEST_COUNT_PATTERNS = [
    re.compile(r"\((\d+)\s*tests?\)", re.IGNORECASE),
    re.compile(r"(\d+)\s*/\s*(\d+)\s*(?:tests?)?\b"),
    re.compile(r"(\d+)\s*tests?\s*passing", re.IGNORECASE),
    re.compile(r"(\d+)\s*passed\b", re.IGNORECASE),
]

NON_REPRO_PREFIXES = ("~", "/tmp", "/var", "/Users", "/private")  # noqa: S108 -- prefix strings, not a temp-file path
EVIDENCE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "mp4", "mov", "webm", "pdf"}


def is_evidence_artifact(path: str) -> bool:
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return ext in EVIDENCE_EXTENSIONS


def is_test_path(path: str) -> bool:
    base = path.rsplit("/", 1)[-1]
    return (
        base.startswith("test_")
        or base.endswith("_test.py")
        or ".test." in base
        or ".spec." in base
    )


def strip_urls(line: str) -> str:
    return URL_RE.sub(" ", line)


def extract_test_count_claims(body: str):
    """Yield (path, claimed_count, raw_line) for lines mentioning a test path
    plus a nearby count."""
    claims = []
    for line in body.splitlines():
        clean = strip_urls(line)
        for m in TEST_PATH_RE.finditer(clean):
            path = m.group(0)
            if not is_test_path(path):
                continue
            for pat in TEST_COUNT_PATTERNS:
                cm = pat.search(clean)
                if not cm:
                    continue
                if cm.re is TEST_COUNT_PATTERNS[1]:  # N/N pattern
                    claimed = int(cm.group(2))  # denominator = claimed total
                else:
                    claimed = int(cm.group(1))
                claims.append((path, claimed, line.strip()))
                break
    return claims


CI_KEYWORD_RE = re.compile(r"\bCI\b|status\s*check|required\s*checks?", re.IGNORECASE)
CI_PROXIMITY_CHARS = 20  # "CI 35/35 PASS" style claims keep the keyword adjacent


def _span_gap(a: tuple[int, int], b: tuple[int, int]) -> int:
    (s1, e1), (s2, e2) = a, b
    if e1 <= s2:
        return s2 - e1
    if e2 <= s1:
        return s1 - e2
    return 0


def extract_ci_claims(body: str):
    """Yield (claimed_pass, claimed_total, raw_line) for CI-context N/N claims.

    Requires the CI keyword to sit close to the N/N figure (not merely
    somewhere on the same line) so prose like "the same runner CI uses"
    doesn't get misread as a CI-rollup total.
    """
    claims = []
    for line in body.splitlines():
        clean = strip_urls(line)
        # Skip lines that are actually per-file test-count claims.
        if any(is_test_path(m.group(0)) for m in TEST_PATH_RE.finditer(clean)):
            continue
        ci_spans = [m.span() for m in CI_KEYWORD_RE.finditer(clean)]
        if not ci_spans:
            continue
        for m in re.finditer(r"(\d+)\s*/\s*(\d+)", clean):
            if any(_span_gap(m.span(), ci_span) <= CI_PROXIMITY_CHARS for ci_span in ci_spans):
                claims.append((int(m.group(1)), int(m.group(2)), line.strip()))
    return claims


def extract_review_claims(body: str):
    """Yield (claimed_unresolved, raw_line) for review-thread claims."""
    claims = []
    for line in body.splitlines():
        clean = strip_urls(line)
        if not re.search(r"review|thread", clean, re.IGNORECASE):
            continue
        m = re.search(r"(\d+)\s*(?:unresolved|open)\b", clean, re.IGNORECASE)
        if m:
            claims.append((int(m.group(1)), line.strip()))
            continue
        if re.search(r"\ball\s+resolved\b|\b0\s*(?:unresolved|open)\b|\bno\s+unresolved\b", clean, re.IGNORECASE):
            claims.append((0, line.strip()))
    return claims


def extract_sha_claims(body: str):
    """Yield (sha, raw_line) for hex tokens that look like commit SHAs."""
    seen = set()
    claims = []
    for line in body.splitlines():
        clean = strip_urls(line)
        for m in SHA_RE.finditer(clean):
            sha = m.group(0)
            if len(sha) < 7 or sha in seen:
                continue
            seen.add(sha)
            claims.append((sha, line.strip()))
    return claims


def extract_path_claims(body: str):
    """Yield (path, raw_line) for repo-relative or absolute paths cited as evidence."""
    seen = set()
    claims = []
    for line in body.splitlines():
        clean = strip_urls(line)
        for m in ANY_PATH_RE.finditer(clean):
            path = m.group(0)
            if path in seen:
                continue
            seen.add(path)
            claims.append((path, line.strip()))
    return claims


# --------------------------------------------------------------------------
# Re-derivation / verdicts
# --------------------------------------------------------------------------


def static_test_count(head: str, path: str) -> int | None:
    content = git_show(head, path)
    if content is None:
        return None
    if path.endswith(".py"):
        return sum(1 for line in content.splitlines() if re.match(r"^\s*def test_", line))
    return sum(1 for line in content.splitlines() if re.match(r"^\s*(?:test|it)\(", line))


def verify_test_counts(head: str, body: str) -> list[Verdict]:
    out = []
    for path, claimed, raw in extract_test_count_claims(body):
        label = f"test count: `{path}` claims {claimed} ({raw[:80]})"
        actual = static_test_count(head, path)
        if actual is None:
            out.append(Verdict(label, "file not found at PR head", "UNVERIFIABLE"))
            continue
        derived = (
            f"static declarations at {head[:12]} = {actual}; "
            "test discovery and execution were not performed"
        )
        out.append(Verdict(label, derived, "UNVERIFIABLE"))
    return out


def verify_ci_claims(pr_number: int, body: str) -> list[Verdict]:
    out = []
    claims = extract_ci_claims(body)
    if not claims:
        return out
    rollup = get_status_rollup(pr_number)
    if rollup is None:
        for _, _, raw in claims:
            out.append(Verdict(f"CI claim: {raw[:80]}", "could not fetch statusCheckRollup", "UNVERIFIABLE"))
        return out
    total, success, counts = analyze_rollup(rollup)
    breakdown = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
    for claimed_pass, claimed_total, raw in claims:
        label = f"CI claim: {claimed_pass}/{claimed_total} ({raw[:80]})"
        derived = f"actual: {success}/{total} SUCCESS ({breakdown})"
        if claimed_total == total and claimed_pass == claimed_total and success < total:
            out.append(
                Verdict(
                    label,
                    f"{derived} -- claimed total equals rollup length but not all succeeded (classic inflation)",
                    "FAIL",
                )
            )
        elif claimed_pass == success and claimed_total == total:
            out.append(Verdict(label, derived, "PASS"))
        else:
            out.append(Verdict(label, derived, "FAIL"))
    return out


def verify_review_claims(pr_number: int, slug: str, body: str) -> list[Verdict]:
    out = []
    claims = extract_review_claims(body)
    if not claims:
        return out
    result = get_unresolved_review_threads(pr_number, slug)
    if result is None:
        for _, raw in claims:
            out.append(Verdict(f"review claim: {raw[:80]}", "could not fetch reviewThreads", "UNVERIFIABLE"))
        return out
    unresolved, total = result
    for claimed, raw in claims:
        label = f"review claim: {claimed} unresolved ({raw[:80]})"
        derived = f"actual unresolved={unresolved} of {total} threads"
        out.append(Verdict(label, derived, "PASS" if claimed == unresolved else "FAIL"))
    return out


def verify_sha_claims(body: str) -> list[Verdict]:
    out = []
    for sha, raw in extract_sha_claims(body):
        label = f"SHA claim: `{sha}` ({raw[:80]})"
        if not commit_exists(sha):
            out.append(Verdict(label, "not found locally or on origin (dangling/rewritten?)", "FAIL"))
            continue
        derived = "resolves to a real commit object"
        # Provenance check: if this line also references a captured evidence
        # artifact (screenshot/video, or anything outside the repo tree),
        # flag artifacts that predate the claimed commit's time. Tracked
        # source files are excluded -- their local mtime reflects the last
        # checkout/edit, not a meaningful "capture time".
        for path_match in ANY_PATH_RE.finditer(strip_urls(raw)):
            candidate = path_match.group(0)
            if not (candidate.startswith(NON_REPRO_PREFIXES) or is_evidence_artifact(candidate)):
                continue
            local = Path(candidate).expanduser()
            if not local.is_absolute():
                if _repo_dir is None:
                    out.append(
                        Verdict(
                            f"provenance: `{candidate}` claimed at SHA `{sha}`",
                            "no repo directory resolved",
                            "UNVERIFIABLE",
                        )
                    )
                    continue
                local = _repo_dir / candidate
            if local.exists():
                ctime = commit_time(sha)
                mtime = local.stat().st_mtime
                if ctime is not None and mtime < ctime - 1:
                    out.append(
                        Verdict(
                            f"provenance: `{candidate}` claimed at SHA `{sha}`",
                            f"artifact mtime {mtime:.0f} predates commit time {ctime:.0f}",
                            "FAIL",
                        )
                    )
        out.append(Verdict(label, derived, "PASS"))
    return out


def verify_path_claims(head: str, body: str) -> list[Verdict]:
    out = []
    for path, raw in extract_path_claims(body):
        label = f"path claim: `{path}` ({raw[:80]})"
        if path.startswith(NON_REPRO_PREFIXES) or path.startswith("~"):
            out.append(Verdict(label, "path is outside the repo", "FAIL (NON-REPRODUCIBLE)"))
            continue
        rel = path.lstrip("/")
        if path_exists_at(head, rel):
            out.append(Verdict(label, f"exists at {head[:12]}:{rel}", "PASS"))
        else:
            out.append(Verdict(label, f"not found at {head[:12]}:{rel}", "FAIL"))
    return out


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------


def print_table(verdicts: list[Verdict]):
    if not verdicts:
        print("(no claims of this class detected)")
        return
    for v in verdicts:
        mark = {"PASS": "PASS", "FAIL": "FAIL", "UNVERIFIABLE": "UNVERIFIABLE"}
        vv = v.verdict if v.verdict in mark else v.verdict  # e.g. "FAIL (NON-REPRODUCIBLE)"
        print(f"| {v.claim} | {v.derived} | {vv} |")


def main() -> int:
    global _repo_dir, _repo_slug  # noqa: PLW0603 -- config set once at startup from CLI args

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pr", type=int, required=True, help="PR number")
    ap.add_argument("--body-file", type=str, default=None, help="Read the body from a local file instead of gh pr view")
    ap.add_argument("--repo-dir", type=str, default=None, help="Repository directory (defaults to current working directory)")
    args = ap.parse_args()

    # Initialize repo directory
    _repo_dir = Path(args.repo_dir) if args.repo_dir else Path.cwd()

    # Derive repo slug before calling gh commands
    _repo_slug = get_repo_slug()
    if not _repo_slug:
        print("ERROR: could not determine repository (tried git remote and gh)", file=sys.stderr)
        return 1

    pr_info = get_pr_info(args.pr)
    if pr_info is None:
        print(f"ERROR: could not load PR #{args.pr} metadata via gh", file=sys.stderr)
        return 1
    head = pr_info["headRefOid"]

    if args.body_file:
        body = Path(args.body_file).read_text()
    else:
        body = pr_info.get("body") or ""

    slug = _repo_slug

    print(f"PR #{args.pr}  head={head}  ({pr_info.get('url', '')})")
    if args.body_file:
        print(f"body source: {args.body_file} (metadata/ground-truth still live for PR #{args.pr})")
    print()

    # Count extracted claims for sanity check
    extracted_count = (
        len(extract_test_count_claims(body))
        + len(extract_ci_claims(body))
        + len(extract_review_claims(body))
        + len(extract_sha_claims(body))
        + len(extract_path_claims(body))
    )

    sections = [
        ("Test counts", lambda: verify_test_counts(head, body)),
        ("CI check counts", lambda: verify_ci_claims(args.pr, body)),
        ("Review threads", lambda: verify_review_claims(args.pr, slug, body)),
        ("SHA claims", lambda: verify_sha_claims(body)),
        ("File-path claims", lambda: verify_path_claims(head, body)),
    ]
    all_verdicts: list[Verdict] = []
    for title, fn in sections:
        print(f"## {title}")
        section_verdicts = fn()
        print_table(section_verdicts)
        all_verdicts += section_verdicts
        print()

    return summarize(all_verdicts, extracted_count)


def summarize(all_verdicts: list[Verdict], extracted_count: int = 0) -> int:
    if not all_verdicts:
        print("No falsifiable claims detected in this body.")
        return 0
    total = len(all_verdicts)
    # Sanity check: verdict count should match extracted count (each claim gets a verdict)
    if extracted_count > 0 and total != extracted_count:
        print(
            f"INTERNAL ERROR: extracted {extracted_count} claims but got {total} verdicts — some claims were silently dropped!",
            file=sys.stderr,
        )
        return 1
    failing = [v for v in all_verdicts if v.verdict != "PASS"]
    print(f"SUMMARY: {total - len(failing)}/{total} claims verified PASS.")
    if not failing:
        return 0
    print(f"{len(failing)} claim(s) FAILED or UNVERIFIABLE:")
    for v in failing:
        print(f"  - {v.claim} -> {v.verdict}: {v.derived}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
