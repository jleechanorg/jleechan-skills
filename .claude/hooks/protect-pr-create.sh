#!/usr/bin/env bash
# protect-pr-create.sh — PreToolUse(Bash) guard against unbounded PR splitting and deep PR stacks.
#
# Enforces the HARD CAPS only, two mechanical caps when `gh pr create` is invoked:
#   1. Split-prefix cap (<= 5): If the head branch matches `split/<feature>/*` (or `split/<feature>-*`),
#      blocks creation when >= 5 open PRs already exist under that same split prefix.
#   2. Stacked-PR cap (< 10): If `--base` is not `main`/`master`, blocks creation when >= 9 open
#      stacked PRs (`baseRefName != main/master`) already exist in the repository (keeping total < 10).
#
# The lower default of <= 3 open PRs per feature scope is NOT enforced here; it is a judgment
# rule owned by the pr-quantity-control skill. This hook only blocks at the hard cap
# (>= 5 open split/* PRs, >= 9 open stacked PRs).
#
# Escape hatch: prefix the command with `ALLOW_PR_STACK_OVERRIDE=1` when explicitly authorized by the user.
# Fail-open on offline/timeout so routine work never hangs if GitHub API is unreachable.

set -uo pipefail

input="$(cat 2>/dev/null || true)"
[ -z "$input" ] && exit 0

# Fast bail unless the payload mentions both "gh" and "create"
case "$input" in
  *gh*create*) : ;;
  *) exit 0 ;;
esac

INPUT_JSON="$input" python3 -I -W ignore - <<'PYEOF'
import json
import os
import re
import shlex
import subprocess
import sys

raw = os.environ.get("INPUT_JSON", "")
try:
    payload = json.loads(raw)
except Exception:
    sys.exit(0)

if payload.get("tool_name") not in ("Bash", "run_shell_command"):
    sys.exit(0)

cmd = (payload.get("tool_input") or {}).get("command") or ""
cwd = payload.get("cwd") or os.getcwd()
if not cmd:
    sys.exit(0)


def strip_heredocs(s: str) -> str:
    pattern = re.compile(
        r"<<-?\s*['\"]?([A-Za-z0-9_]+)['\"]?[^\n]*\n.*?\n\1\b",
        re.DOTALL,
    )
    while True:
        new_s, count = pattern.subn("", s)
        if count == 0:
            return s
        s = new_s


stripped = strip_heredocs(cmd)

# Match a real `gh ... pr create` invocation in command position; quoted
# strings and shell comments are single tokens or dropped by the lexer.
try:
    lexer = shlex.shlex(stripped.replace("\n", " ; "), posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    tokens = list(lexer)
except Exception:
    sys.exit(0)

SEPARATORS = {";", "&&", "||", "|", "&", "(", ")", "\n"}


def is_pr_create(i: int) -> bool:
    j = i - 1
    while j >= 0 and (re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tokens[j]) or tokens[j] == "env"):
        j -= 1
    if j >= 0 and tokens[j] not in SEPARATORS:
        return False
    k = i + 1
    while k < len(tokens) and tokens[k].startswith("-"):
        k += 1 if "=" in tokens[k] else 2
    return tokens[k : k + 2] == ["pr", "create"]


gh_create_indices = [
    i
    for i, token in enumerate(tokens)
    if (token == "gh" or token.endswith("/gh")) and is_pr_create(i)
]
if not gh_create_indices:
    sys.exit(0)


def has_inline_override(i: int) -> bool:
    j = i - 1
    while j >= 0 and (
        re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tokens[j]) or tokens[j] == "env"
    ):
        if tokens[j] == "ALLOW_PR_STACK_OVERRIDE=1":
            return True
        j -= 1
    return False


if os.environ.get("ALLOW_PR_STACK_OVERRIDE") == "1" or any(
    has_inline_override(i) for i in gh_create_indices
):
    sys.exit(0)

head_branch = ""
base_branch = "main"
repo_slug = ""

# Locate the `pr` -> `create` token pair
for idx in range(len(tokens) - 1):
    if tokens[idx] == "pr" and tokens[idx + 1] == "create":
        # Scan surrounding tokens for --head/-H, --base/-B, --repo/-R
        j = 0
        while j < len(tokens):
            tok = tokens[j]
            if tok in ("--head", "-H") and j + 1 < len(tokens):
                head_branch = tokens[j + 1]
                j += 2
                continue
            if tok.startswith("--head="):
                head_branch = tok.split("=", 1)[1]
            elif tok in ("--base", "-B") and j + 1 < len(tokens):
                base_branch = tokens[j + 1]
                j += 2
                continue
            elif tok.startswith("--base="):
                base_branch = tok.split("=", 1)[1]
            elif tok in ("--repo", "-R") and j + 1 < len(tokens):
                repo_slug = tokens[j + 1]
                j += 2
                continue
            elif tok.startswith("--repo="):
                repo_slug = tok.split("=", 1)[1]
            j += 1
        break

if ":" in head_branch:
    head_branch = head_branch.split(":", 1)[1]

if not head_branch:
    try:
        head_branch = (
            subprocess.check_output(
                ["git", "-C", cwd, "branch", "--show-current"],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=3,
            ).strip()
        )
    except Exception:
        head_branch = ""


def compute_split_prefix(branch: str) -> str:
    if not branch.startswith("split/"):
        return ""
    rest = branch[len("split/") :]
    if "/" in rest:
        feature = rest.split("/", 1)[0]
        return f"split/{feature}/"
    if "-" in rest:
        feature = rest.split("-", 1)[0]
        return f"split/{feature}-"
    return "split/"


split_prefix = compute_split_prefix(head_branch)
is_stacked = base_branch not in ("main", "master", "")

# Only query GitHub if we are either on a split/* branch or targeting a non-main base branch
if not split_prefix and not is_stacked:
    sys.exit(0)

mock_json = os.environ.get("PROTECT_PR_CREATE_MOCK_JSON", "")
if mock_json:
    try:
        open_prs = json.loads(mock_json)
    except Exception:
        sys.exit(0)
else:
    gh_cmd = [
        "gh",
        "pr",
        "list",
        "--state",
        "open",
        "--limit",
        "100",
        "--json",
        "number,headRefName,baseRefName",
    ]
    if repo_slug:
        gh_cmd.extend(["--repo", repo_slug])
    env = dict(os.environ)
    env["GH_PROMPT_DISABLED"] = "1"
    env["GH_NO_UPDATE_NOTIFIER"] = "1"
    env["GH_PAGER"] = ""
    try:
        proc = subprocess.run(
            gh_cmd,
            cwd=cwd if os.path.isdir(cwd) else None,
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if proc.returncode != 0:
            sys.exit(0)
        open_prs = json.loads(proc.stdout or "[]")
    except Exception:
        # Fail-open on timeout or offline
        sys.exit(0)

# Rule 1: Split-prefix ceiling (<= 5 open PRs under the same split/<feature>/ prefix)
if split_prefix:
    matching_split_prs = [
        p
        for p in open_prs
        if (p.get("headRefName") or "").startswith(split_prefix)
    ]
    if len(matching_split_prs) >= 5:
        nums = ", ".join(f"#{p.get('number')}" for p in matching_split_prs[:10])
        sys.stderr.write(
            f"BLOCKED by protect-pr-create.sh: split PR quantity cap exceeded for prefix '{split_prefix}'.\n"
            f"Found {len(matching_split_prs)} open PRs already matching '{split_prefix}*' ({nums}); ceiling is <= 5.\n"
            f"Do NOT atomize features into unbounded micro-PRs. Consolidate into an existing PR or a single unified PR targeting 'main'.\n"
            f"If the human operator explicitly authorized >5 split PRs, set ALLOW_PR_STACK_OVERRIDE=1.\n"
        )
        sys.exit(2)

# Rule 2: Stacked PR ceiling (< 10 open non-main-base PRs in the active 100-PR window)
if is_stacked:
    stacked_prs = [
        p
        for p in open_prs
        if (p.get("baseRefName") or "main") not in ("main", "master")
    ]
    if len(stacked_prs) >= 9:
        nums = ", ".join(
            f"#{p.get('number')} (base={p.get('baseRefName')})"
            for p in stacked_prs[:10]
        )
        sys.stderr.write(
            f"BLOCKED by protect-pr-create.sh: stacked PR ceiling (< 10) reached.\n"
            f"Attempted to create a stacked PR with --base '{base_branch}', but {len(stacked_prs)} open stacked PRs "
            f"(baseRefName != main) already exist ({nums}).\n"
            f"Target 'main' directly (--base main) or fold this change into an existing open PR.\n"
            f"If the human operator explicitly authorized this stack, set ALLOW_PR_STACK_OVERRIDE=1.\n"
        )
        sys.exit(2)

sys.exit(0)
PYEOF
exit $?
