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


def normalize_shell_command(command: str) -> str:
    output = []
    quote = ""
    escaped = False
    comment = False
    i = 0
    while i < len(command):
        char = command[i]
        if comment:
            if char == "\n":
                output.append(";")
                comment = False
            i += 1
            continue
        if escaped:
            output.append(char)
            escaped = False
            i += 1
            continue
        if char == "\\" and quote != "'":
            if i + 1 < len(command) and command[i + 1] == "\n":
                i += 2
                continue
            output.append(char)
            escaped = True
            i += 1
            continue
        if quote:
            if char == quote:
                quote = ""
            output.append(char)
        elif char in ("'", '"'):
            quote = char
            output.append(char)
        elif char == "#" and (
            not output
            or output[-1].isspace()
            or output[-1] in ";&|()<>"
        ):
            comment = True
        elif char == "\n":
            output.append(";")
        else:
            output.append(char)
        i += 1
    return "".join(output)


stripped = normalize_shell_command(strip_heredocs(cmd))

# Match a real `gh ... pr create` invocation in command position; quoted
# strings and shell comments are single tokens or dropped by the lexer.
try:
    lexer = shlex.shlex(stripped, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    tokens = list(lexer)
except Exception:
    sys.exit(0)

SEPARATORS = {";", "&&", "||", "|", "&", "(", ")", "\n"}
SEPARATOR_CHARACTERS = ";&|()<>"


def is_separator(token: str) -> bool:
    return token in SEPARATORS or (
        bool(token) and all(char in SEPARATOR_CHARACTERS for char in token)
    )


def is_pr_create(i: int) -> bool:
    j = i - 1
    while j >= 0 and (
        re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tokens[j]) or tokens[j] == "env"
    ):
        j -= 1
    if j >= 0 and not is_separator(tokens[j]):
        return False
    k = i + 1
    while k < len(tokens) and tokens[k].startswith("-"):
        token = tokens[k]
        attached_short_value = (
            not token.startswith("--") and len(token) > 2
        )
        k += 1 if "=" in token or attached_short_value else 2
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


def get_current_branch():
    try:
        return subprocess.check_output(
            ["git", "-C", cwd, "branch", "--show-current"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=3,
        ).strip()
    except Exception:
        return ""


def get_configured_merge_base(branch):
    if not branch:
        return ""
    try:
        return subprocess.check_output(
            ["git", "-C", cwd, "config", "--get", f"branch.{branch}.gh-merge-base"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=3,
        ).strip()
    except Exception:
        return ""


def get_invocation_flags(i):
    end = i + 1
    while end < len(tokens) and not is_separator(tokens[end]):
        end += 1

    head_branch = ""
    base_branch = None
    repo_slug = ""
    j = i + 1
    while j < end:
        token = tokens[j]
        if token == "--":
            break
        if token in ("--head", "-H") and j + 1 < end:
            head_branch = tokens[j + 1]
            j += 2
            continue
        if token.startswith("--head="):
            head_branch = token.split("=", 1)[1]
        elif token.startswith("-H") and len(token) > 2:
            head_branch = token[2:]
        elif token in ("--base", "-B") and j + 1 < end:
            base_branch = tokens[j + 1]
            j += 2
            continue
        elif token.startswith("--base="):
            base_branch = token.split("=", 1)[1]
        elif token.startswith("-B") and len(token) > 2:
            base_branch = token[2:]
        elif token in ("--repo", "-R") and j + 1 < end:
            repo_slug = tokens[j + 1]
            j += 2
            continue
        elif token.startswith("--repo="):
            repo_slug = token.split("=", 1)[1]
        elif token.startswith("-R") and len(token) > 2:
            repo_slug = token[2:]
        j += 1
    return head_branch, base_branch, repo_slug


if os.environ.get("ALLOW_PR_STACK_OVERRIDE") == "1":
    sys.exit(0)

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


def query_open_prs(repo_slug: str):
    mock_json = os.environ.get("PROTECT_PR_CREATE_MOCK_JSON", "")
    if mock_json:
        try:
            return json.loads(mock_json)
        except Exception:
            return None

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
            return None
        return json.loads(proc.stdout or "[]")
    except Exception:
        return None


for gh_index in gh_create_indices:
    if has_inline_override(gh_index):
        continue

    head_branch, base_branch, repo_slug = get_invocation_flags(gh_index)
    current_branch = ""
    if not head_branch or base_branch is None:
        current_branch = get_current_branch()
    if not head_branch:
        head_branch = current_branch
    if ":" in head_branch:
        head_branch = head_branch.split(":", 1)[1]
    if base_branch is None:
        base_branch = get_configured_merge_base(current_branch) or "main"

    split_prefix = compute_split_prefix(head_branch)
    is_stacked = base_branch not in ("main", "master", "")
    if not split_prefix and not is_stacked:
        continue

    open_prs = query_open_prs(repo_slug)
    if open_prs is None:
        sys.exit(0)

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
