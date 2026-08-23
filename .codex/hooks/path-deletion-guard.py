#!/usr/bin/env python3
"""
Codex / Claude PreToolUse hook: allow deletions inside /tmp, block outside.

Design goals (2026-07, derived from X community + Codex 0.144 release notes):
  - Allow rm/rmdir/shred/find -delete/git clean/apply_patch deletes/shutil.rmtree
    that operate ONLY inside allowed temp directories.
  - Block the same operations when any resolved target path is outside the
    allowlist. The hook is fail-closed: if parsing fails OR no targets can be
    resolved, deny.
  - Allowlist: $TMPDIR (if set), /tmp, /private/tmp, $HOME/.codex/.tmp,
    $HOME/.cache/codex-tmp (configurable via PATH_DELETION_GUARD_ALLOW).
  - Forbidden paths: anywhere else under $HOME, /etc, /usr, /var, /opt,
    plus any path that resolves through a symlink landing outside allowlist.
  - Deny schema: Codex PreToolUse JSON
      {"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"..."}}
  - Allow schema: exit 0 with no stdout. Codex 0.144.5 rejects an explicit
    permissionDecision:"allow" when no input rewrite is being requested.

Failure modes:
  - Unreadable stdin / malformed JSON  → deny (fail-closed)
  - Empty tool_input on a watched tool  → deny (cannot inspect safely)
  - Tool name not in watched set        → allow (let other guards handle it)

Performance budget: < 50ms typical, < 200ms p99. Pure stdlib, no subprocess.

Refs:
  - X thread 2077396515975307273 (Codex PreToolUse schema, permissionDecision)
  - X thread 2077820292622372866 (defense in depth, full-access incidents)
  - X thread 2037523396876173783 (exit 2 vs exit 0 vs exit 1 semantics)
  - Local neighbor: ~/.codex/hooks/rtk-hook-guard.sh
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
from datetime import UTC, datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Tools we inspect. Anything else passes through unchanged.
WATCHED_TOOLS = frozenset({
    "Bash", "bash", "shell", "exec_command",
    "apply_patch", "Edit", "Write", "Delete",
    "mcp__filesystem__delete",  # future-proofing
})
SHELL_TOOLS = frozenset({"Bash", "bash", "shell", "exec_command"})
DELETE_TOOLS = frozenset({"Delete", "mcp__filesystem__delete"})

# Allowlist: paths under any of these roots are deletable.
# Order matters; first match wins.
DEFAULT_ALLOW_ROOTS = (
    "/tmp",
    "/private/tmp",
    "/var/folders",  # macOS per-user temp ($TMPDIR usually lives here)
)

# Extra roots from $HOME, configurable via env so user can extend without
# editing source.
EXTRA_ENV = "PATH_DELETION_GUARD_ALLOW"
HOME = os.environ.get("HOME", "/Users/$USER")


def _allow_roots() -> tuple[str, ...]:
    roots = list(DEFAULT_ALLOW_ROOTS)
    # Honor $TMPDIR (macOS sets it to /var/folders/.../T/).
    tmpdir = os.environ.get("TMPDIR")
    if tmpdir:
        roots.append(tmpdir)
    # Configurable extras (colon-separated absolute paths).
    extras = os.environ.get(EXTRA_ENV, "")
    for extra in extras.split(":"):
        extra = extra.strip()
        if extra and extra.startswith("/"):
            roots.append(extra)
    # Per-user codex scratch dirs are commonly considered disposable.
    roots.append(f"{HOME}/.codex/.tmp")
    roots.append(f"{HOME}/.cache/codex-tmp")
    return tuple(roots)


# Patterns that count as a deletion attempt. Order matters: more specific
# first so we don't accidentally swallow a benign command.
DELETION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    # rm variants — most dangerous, check first
    ("rm -rf", re.compile(r"\brm\s+(?:-[a-zA-Z]*[rRfF][a-zA-Z]*)+")),
    ("rm -r", re.compile(r"\brm\s+-[a-zA-Z]*r")),
    ("rm -f", re.compile(r"\brm\s+-[a-zA-Z]*f")),
    ("rmdir", re.compile(r"\brmdir\b")),
    ("shred", re.compile(r"\bshred\b")),
    ("unlink", re.compile(r"\bunlink\b")),
    # find -delete / -exec rm
    ("find -delete", re.compile(r"\bfind\b[^\n]*\s-delete\b")),
    ("find -exec rm", re.compile(r"\bfind\b[^\n]*-exec\b[^\n]*\brm\b")),
    ("find -exec rm {}", re.compile(r"\bfind\b[^\n]*-exec\b[^\n]*rm\s+\{\}")),
    # rsync --delete (mass delete)
    ("rsync --delete", re.compile(r"\brsync\b[^\n]*--delete(?:-excluded|-after|--|-[a-z]+)?\b")),
    # git destructive
    ("git clean -fdx", re.compile(r"\bgit\s+clean\b[^\n]*-[a-zA-Z]*[fdx]+")),
    ("git clean -f", re.compile(r"\bgit\s+clean\b[^\n]*-[a-zA-Z]*f")),
    ("git reset --hard", re.compile(r"\bgit\s+reset\s+--hard\b")),
    ("git rm -rf", re.compile(r"\bgit\s+rm\b[^\n]*-[a-zA-Z]*[rRfF]+")),
    # Python / Node one-liners doing mass delete
    ("shutil.rmtree", re.compile(r"\bshutil\.rmtree\b")),
    ("os.remove", re.compile(r"\bos\.(?:remove|unlink|rmdir)\b")),
    ("fs.rm", re.compile(r"\bfs\.(?:rm(?:Sync)?|unlink|rmdir)\b")),
    # DB / system
    ("DROP TABLE", re.compile(r"\bDROP\s+(?:TABLE|DATABASE|SCHEMA)\b", re.IGNORECASE)),
    ("DELETE FROM", re.compile(r"\bDELETE\s+FROM\b", re.IGNORECASE)),
    ("truncate", re.compile(r":\s*>\s*/|\btruncate\s+-s\s*0\b")),
    # Disk-level nukes (always denied regardless of path)
    ("mkfs", re.compile(r"\bmkfs(?:\.[a-z0-9]+)?\b")),
    ("dd to disk", re.compile(r"\bdd\s+[^\n]*of=/dev/(?:sd|hd|nvme|disk|vd)")),
    ("format c:", re.compile(r"\bformat\s+[a-zA-Z]:", re.IGNORECASE)),
)


# ---------------------------------------------------------------------------
# Path extraction
# ---------------------------------------------------------------------------

# Tokens that look like absolute paths or path-like args (./foo, ../foo, ~/foo).
PATH_TOKEN = re.compile(
    r"(?P<q>['\"]?)(?P<path>(?:/[\w.\-]+){2,}"
    r"|(?:~|\$HOME)/[\w.\-/]+"
    r"|\./[\w.\-/]+"
    r"|\.\./[\w.\-/]+"
    r"|[\w.\-]+/[\w.\-/]+"          # bare relative like some/dir, foo/bar/baz
    r")(?P=q)"
)


def _expand(p: str) -> str:
    """Expand ~ and $HOME and $TMPDIR, normalize, then resolve symlinks."""
    if not p:
        return p
    expanded = os.path.expandvars(os.path.expanduser(p))
    try:
        return str(Path(expanded).resolve(strict=False))
    except (OSError, RuntimeError):
        return expanded


def _is_under_allowed(abs_path: str, roots: tuple[str, ...]) -> bool:
    """True iff abs_path is strictly under one of the allowed roots."""
    if not abs_path:
        return False
    p = abs_path.rstrip("/") or "/"
    for root in roots:
        root_abs = _expand(root)
        root_n = root_abs.rstrip("/") or "/"
        if p == root_n:
            return True
        if p.startswith(root_n + "/"):
            return True
    return False


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def _extract_command(payload: dict) -> str:
    """Pull the command string from a hook payload (Codex + Claude shape).

    Returns the string, or the empty string when the payload is well-formed
    but tool_input is something we don't understand (no command). Callers
    MUST treat empty + watched-tool as an unparseable / suspicious event and
    refuse (not silently allow).

    Verified bug 2026-07-17 by Reviewer C — previous behaviour returned ""
    for non-dict tool_input like [1,2,3] and the caller implicitly allowed.
    """
    ti = payload.get("tool_input") or payload.get("input")
    if ti is None:
        # No tool_input at all → caller will require this; effectively "empty cmd".
        return ""
    if isinstance(ti, dict):
        for key in ("command", "cmd", "shell_command", "bash_command"):
            v = ti.get(key)
            if isinstance(v, str):
                return v
        # apply_patch / Edit / Write: serialize so we can grep it.
        return json.dumps(ti)
    if isinstance(ti, str):
        return ti
    # Unknown type (list/int/bool/float) → forced sentinel so caller fails closed.
    return "<UNREADABLE tool_input type=%s>" % type(ti).__name__


def _extract_paths(cmd: str, cwd: str | None = None) -> list[str]:
    """Pull path-like tokens out of a shell command.

    Bare relative paths (e.g. `some/dir`) are resolved against `cwd` so the
    allowlist check works against an absolute path.
    """
    out: list[str] = []
    for m in PATH_TOKEN.finditer(cmd):
        tok = m.group("path")
        # Skip pure flag-looking tokens (`-rf/x`, `--foo/bar`).
        if tok.startswith("-"):
            continue
        # Bare relative → make absolute using cwd.
        if not tok.startswith(("/", "~", "./", "../")) and cwd:
            tok = os.path.join(cwd, tok)
        out.append(tok)
    return out


def _classify(cmd: str) -> tuple[str, str] | None:
    """Return (name, regex) of first matching deletion pattern, or None."""
    for name, pat in DELETION_PATTERNS:
        if pat.search(cmd):
            return (name, pat.pattern)
    return None


# Commands that always operate on CWD when no path is given, so the
# working_dir from the payload IS the target path. Apply only to
# destructive git commands where this is the documented behavior.
_CWD_TARGETING: frozenset[str] = frozenset({
    "git clean -fdx", "git clean -f", "git reset --hard",
})


def _extract_tool_paths(payload: dict) -> list[str]:
    """Extract explicit path fields from a structured file-tool payload."""
    ti = payload.get("tool_input") or payload.get("input") or {}
    if not isinstance(ti, dict):
        return []
    paths: list[str] = []
    # Common field names
    for key in ("path", "file_path", "filepath", "target", "filename"):
        v = ti.get(key)
        if isinstance(v, str):
            paths.append(v)
    files = ti.get("files")
    if isinstance(files, list):
        for f in files:
            if isinstance(f, dict):
                p = f.get("path") or f.get("file_path")
                if isinstance(p, str):
                    paths.append(p)
            elif isinstance(f, str):
                paths.append(f)
    return paths


def _extract_apply_patch_targets(payload: dict) -> list[str]:
    """Extract only actual Delete File targets from apply_patch payloads."""
    ti = payload.get("tool_input") or payload.get("input") or {}
    if not isinstance(ti, dict):
        return []
    paths: list[str] = []
    for key in ("patch", "command"):
        patch = ti.get(key)
        if not isinstance(patch, str):
            continue
        for line in patch.splitlines():
            match = re.match(r"\*\*\*\s+delete file:\s+(.+)", line, re.IGNORECASE)
            if match:
                paths.append(match.group(1).strip())
    return paths


# ---------------------------------------------------------------------------
# Decision
# ---------------------------------------------------------------------------

def _deny(reason: str) -> dict:
    """Emit the Codex-canonical PreToolUse denial shape.

    Per learn.chatgpt.com/docs/hooks.md (verified 2026-07-17):
      "permissionDecision:"ask", legacy decision:"approve",
       continue:false, stopReason, and suppressOutput are parsed
       but not supported yet. Codex marks the hook run as failed,
       reports the error, and continues the tool call."

    In other words, emitting `continue:false` and `stopReason` makes Codex
    treat the deny as a BROKEN HOOK and run the tool anyway. We emit only
    `hookSpecificOutput.permissionDecision:"deny"` + the reason. The Claude
    JSON Schema does accept `continue:false`, but Codex does NOT — we
    prioritize Codex since this hook is registered there.

    Exit code 2 is the alternative blocking channel — Codex reads stderr
    for the reason when the script exits 2. We use BOTH (JSON decision +
    exit 2 + stderr line) so the blocking reason is captured whichever
    transport codex happens to honor.
    """
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        },
    }


def _allow() -> None:
    """Allow implicitly: Codex treats exit 0 with no stdout as success."""
    return None


def _audit_deny(payload: dict) -> None:
    """Append one best-effort record for an actual guard denial."""
    try:
        log_dir = Path(
            os.environ.get(
                "CODEX_PATH_GUARD_LOG_DIR", f"{HOME}/.codex/log"
            )
        )
        log_dir.mkdir(parents=True, exist_ok=True)
        tool = str(payload.get("tool_name") or payload.get("name") or "unknown")
        command = _extract_command(payload)[:512]
        command = command.replace("\r", "\\r").replace("\n", "\\n")
        timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        with (log_dir / "path-deletion-guard.log").open(
            "a", encoding="utf-8"
        ) as handle:
            handle.write(f"{timestamp} tool={tool} cmd={command}\n")
    except (OSError, ValueError):
        pass


def evaluate(payload: dict) -> dict | None:
    """Return the hook decision for a parsed payload."""
    tool = payload.get("tool_name") or payload.get("name") or ""
    if tool not in WATCHED_TOOLS:
        return _allow()

    cmd = _extract_command(payload)
    # Verified bug 2026-07-17 by Reviewer C: when tool_input is something
    # unknown (list/int/bool/non-dict), `_extract_command` returns a sentinel
    # "<UNREADABLE …>". On watched tools we MUST fail closed for that, not
    # allow. Empty cmd + watched tool also denies (we can't inspect what
    # we're authorizing).
    if cmd.startswith("<UNREADABLE") or cmd == "":
        return _deny(
            f"path-deletion-guard: cannot parse {tool} payload "
            f"(fail-closed). tool_input={cmd[:120]!r}"
        )
    roots = _allow_roots()
    # Codex 0.144+ nests cwd inside tool_input (Claude puts it at payload root
    # under "working_dir"). Read BOTH shapes so relative paths resolve to the
    # caller's actual cwd instead of the hook process's cwd.
    # Verified bug 2026-07-17 by Reviewer A.
    ti = payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else {}
    cwd = (
        payload.get("working_dir")
        or payload.get("cwd")
        or ti.get("working_dir")
        or ti.get("cwd")
        or os.getcwd()
    )

    # Case 1: deletion pattern in a shell command. File-tool content is not
    # shell code and must not be classified by keyword-like text it contains.
    hit = _classify(cmd) if tool in SHELL_TOOLS else None
    if hit:
        name, _ = hit
        # Find path tokens. If ANY resolved path falls outside allowlist, deny.
        targets = _extract_paths(cmd, cwd=cwd)
        # For CWD-targeting destructive commands, the working_dir IS a target.
        if name in _CWD_TARGETING:
            targets = list(targets) + [cwd]
        out_of_bounds: list[str] = []
        for t in targets:
            abs_p = _expand(t)
            if not _is_under_allowed(abs_p, roots):
                out_of_bounds.append(abs_p or t)
        if out_of_bounds:
            return _deny(
                f"Blocked {name} targeting path outside /tmp allowlist: "
                f"{', '.join(out_of_bounds[:3])}"
                f"{' …' if len(out_of_bounds) > 3 else ''}. "
                f"Move to /tmp (or $TMPDIR) first, or use the OS Trash."
            )
        # All targets in allowlist → safe deletion, allow.
        return _allow()

    # Case 2: structured deletion tools. Edit and Write mutate files but do not
    # delete them; apply_patch is destructive only for an actual Delete File.
    targets: list[str] = []
    if tool == "apply_patch":
        targets = _extract_apply_patch_targets(payload)
    elif tool in DELETE_TOOLS:
        targets = _extract_tool_paths(payload)
        if not targets:
            return _deny(f"path-deletion-guard: cannot resolve {tool} target")

    if targets:
        out_of_bounds: list[str] = []
        for t in targets:
            if not t.startswith(("/", "~", "./", "../")):
                t = os.path.join(cwd, t)
            abs_p = _expand(t)
            if not _is_under_allowed(abs_p, roots):
                out_of_bounds.append(abs_p or t)
        if out_of_bounds:
            return _deny(
                f"Blocked {tool} deleting file outside /tmp allowlist: "
                f"{', '.join(out_of_bounds[:3])}"
                f"{' …' if len(out_of_bounds) > 3 else ''}."
            )

    return _allow()


def main() -> int:
    try:
        raw = sys.stdin.read()
    except (OSError, ValueError):
        sys.stdout.write(json.dumps(_deny("path-deletion-guard: cannot read stdin")) + "\n")
        sys.stdout.flush()
        return 2

    if not raw.strip():
        # Codex may invoke the hook with no input for some events — allow.
        return 0

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        sys.stdout.write(json.dumps(_deny(
            f"path-deletion-guard: malformed JSON payload (fail-closed)"
        )) + "\n")
        sys.stdout.flush()
        return 2

    if not isinstance(payload, dict):
        sys.stdout.write(json.dumps(_deny(
            "path-deletion-guard: payload is not a JSON object"
        )) + "\n")
        sys.stdout.flush()
        return 2

    decision = evaluate(payload)
    if decision is not None:
        sys.stdout.write(json.dumps(decision) + "\n")
        sys.stdout.flush()
    # Per learn.chatgpt.com/docs/hooks.md (verified 2026-07-17):
    # Exit code 2 is a valid blocking channel — Codex reads the reason
    # from stderr when the hook exits 2. We use BOTH the JSON decision and
    # exit 2 so the denial is captured whichever transport codex honors.
    is_deny = (
        (decision or {}).get("hookSpecificOutput", {})
        .get("permissionDecision") == "deny"
    )
    if is_deny:
        _audit_deny(payload)
        # Write the blocking reason to stderr as well, per the Codex docs.
        reason = (
            decision.get("hookSpecificOutput", {})
            .get("permissionDecisionReason", "")
        )
        print(reason, file=sys.stderr)
        sys.stderr.flush()
        return 2
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 — fail-closed on any crash
        sys.stdout.write(json.dumps(_deny(
            f"path-deletion-guard: unhandled error ({type(exc).__name__})"
        )) + "\n")
        sys.stdout.flush()
        sys.exit(2)
