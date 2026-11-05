#!/usr/bin/env bash
# protect-pr-create.sh — PreToolUse(Bash) guard against unbounded PR splitting and deep PR stacks.
#
# Best-effort guard for observable `gh pr create` forms; operator policy remains
# authoritative and this parser is not a shell security boundary. It enforces
# two existing hard caps when `gh pr create` is invoked:
#   1. Split-prefix cap (<= 5): If the head branch matches `split/<feature>/*` (or `split/<feature>-*`),
#      blocks creation when >= 5 open PRs already exist under that same split prefix.
#   2. Stacked-PR cap (< 10): If `--base` is not `main`/`master`, blocks creation when >= 9 open
#      stacked PRs (`baseRefName != main/master`) already exist in the repository (keeping total < 10).
#
# The lower default of <= 3 open PRs per feature scope is NOT enforced here; it is a judgment
# rule owned by the pr-quantity-control skill. This hook only blocks at the hard cap
# (>= 5 open split/* PRs, >= 9 open stacked PRs).
#
# Supported parsing includes direct calls, `$()` command substitutions,
# unquoted heredoc expansions, and explicit `bash -c`/`sh -c` programs. Legacy
# backticks, computed executables, and aliases are outside this best-effort scan.
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
        r"<<-?\s*(['\"]?)([A-Za-z0-9_]+)\1[^\n]*\n(.*?)\n[ \t]*\2\b",
        re.DOTALL,
    )

    def replace(match):
        if match.group(1):
            return ""
        substitutions = command_substitutions(
            match.group(3), ignore_outer_quotes=True
        )
        return " ; ".join(f"$({substitution})" for substitution in substitutions)

    while True:
        new_s, count = pattern.subn(replace, s)
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


def command_substitution_spans(
    command: str, *, ignore_outer_quotes: bool = False
):
    substitutions = []
    quote = ""
    escaped = False
    i = 0
    while i + 1 < len(command):
        char = command[i]
        if escaped:
            escaped = False
            i += 1
            continue
        if char == "\\" and quote != "'":
            escaped = True
            i += 1
            continue
        if not ignore_outer_quotes:
            if quote == "'":
                if char == quote:
                    quote = ""
                i += 1
                continue
            if quote == '"' and command[i : i + 2] != "$(":
                if char == quote:
                    quote = ""
                i += 1
                continue
            if char in ("'", '"'):
                quote = char
                i += 1
                continue
        if command[i : i + 2] != "$(":
            i += 1
            continue

        substitution_start = i
        start = i + 2
        depth = 1
        inner_quote = ""
        inner_escaped = False
        i = start
        while i < len(command) and depth:
            char = command[i]
            if inner_escaped:
                inner_escaped = False
            elif char == "\\" and inner_quote != "'":
                inner_escaped = True
            elif inner_quote:
                if char == inner_quote:
                    inner_quote = ""
            elif char in ("'", '"'):
                inner_quote = char
            elif char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            i += 1
        if depth == 0:
            substitutions.append(
                (substitution_start, i, command[start : i - 1])
            )
        else:
            break
    return substitutions


def command_substitutions(command: str, *, ignore_outer_quotes: bool = False):
    return [
        body
        for _, _, body in command_substitution_spans(
            command, ignore_outer_quotes=ignore_outer_quotes
        )
    ]


stripped = normalize_shell_command(strip_heredocs(cmd))

SEPARATORS = {";", "&&", "||", "|", "&", "(", ")", "\n"}
SEPARATOR_CHARACTERS = ";&|()<>"


def is_separator(token: str) -> bool:
    return token in SEPARATORS or (
        bool(token) and all(char in SEPARATOR_CHARACTERS for char in token)
    )


def is_command_position(index: int, command_tokens) -> bool:
    j = index - 1
    while j >= 0 and (
        re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", command_tokens[j])
        or command_tokens[j] in ("env", "command")
    ):
        j -= 1
    return j < 0 or is_separator(command_tokens[j])


def is_pr_create(index: int, command_tokens) -> bool:
    if not is_command_position(index, command_tokens):
        return False
    k = index + 1
    while k < len(command_tokens) and command_tokens[k].startswith("-"):
        token = command_tokens[k]
        attached_short_value = not token.startswith("--") and len(token) > 2
        k += 1 if "=" in token or attached_short_value else 2
    return command_tokens[k : k + 2] == ["pr", "create"]


def contains_pr_create(command_tokens) -> bool:
    return any(
        (token == "gh" or token.endswith("/gh"))
        and is_pr_create(index, command_tokens)
        for index, token in enumerate(command_tokens)
    )


def tokenize_shell(command: str):
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    return list(lexer)


def child_shell_tokens(command_tokens, depth=0):
    if depth >= 8:
        return command_tokens
    ordered_tokens = []
    index = 0
    while index < len(command_tokens):
        token = command_tokens[index]
        if not is_command_position(index, command_tokens):
            ordered_tokens.append(token)
            index += 1
            continue
        if token.rsplit("/", 1)[-1] not in ("bash", "sh"):
            ordered_tokens.append(token)
            index += 1
            continue
        end = index + 1
        while end < len(command_tokens) and not is_separator(command_tokens[end]):
            end += 1
        args = command_tokens[index + 1 : end]
        child_tokens = []
        for option_index, option in enumerate(args[:-1]):
            if option != "-c":
                continue
            try:
                child_tokens = ordered_shell_tokens(
                    args[option_index + 1], depth + 1
                )
            except Exception:
                child_tokens = []
            break
        ordered_tokens.extend(command_tokens[index:end])
        if child_tokens:
            ordered_tokens.extend([";"] + child_tokens)
        index = end
    return ordered_tokens


def ordered_shell_tokens(command: str, depth=0):
    if depth >= 8:
        return tokenize_shell(command)
    spans = command_substitution_spans(command)
    if not spans:
        return child_shell_tokens(tokenize_shell(command), depth)

    substitutions = []
    marked_command = command
    for index, (start, end, body) in reversed(list(enumerate(spans))):
        placeholder = f"__PR_CREATE_SUBST_{index}__"
        while placeholder in command:
            placeholder += "_"
        substitutions.insert(0, (placeholder, body))
        marked_command = (
            marked_command[:start] + placeholder + marked_command[end:]
        )

    command_tokens = tokenize_shell(marked_command)
    ordered_tokens = []
    index = 0
    while index < len(command_tokens):
        if is_separator(command_tokens[index]):
            ordered_tokens.append(command_tokens[index])
            index += 1
            continue
        end = index + 1
        while end < len(command_tokens) and not is_separator(command_tokens[end]):
            end += 1
        segment = command_tokens[index:end]
        active = [
            (placeholder, body)
            for placeholder, body in substitutions
            if any(placeholder in token for token in segment)
        ]
        values = list(segment)
        nested_calls = []
        for placeholder, body in active:
            values = [
                token.replace(placeholder, "__PR_CREATE_SUBST_VALUE__")
                for token in values
            ]
            nested = ordered_shell_tokens(body, depth + 1)
            if contains_pr_create(nested):
                if nested_calls:
                    nested_calls.append(";")
                nested_calls.extend(nested)
        if nested_calls and contains_pr_create(values):
            ordered_tokens.extend([";"] + nested_calls + [";"])
        ordered_tokens.extend(values)
        if nested_calls and not contains_pr_create(values):
            ordered_tokens.extend([";"] + nested_calls + [";"])
        index = end
    return child_shell_tokens(ordered_tokens, depth)


try:
    tokens = ordered_shell_tokens(stripped)
except Exception:
    sys.exit(0)


gh_create_indices = [
    i
    for i, token in enumerate(tokens)
    if (token == "gh" or token.endswith("/gh")) and is_pr_create(i, tokens)
]
if not gh_create_indices:
    sys.exit(0)


def has_inline_override(i: int) -> bool:
    j = i - 1
    while j >= 0 and (
        re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tokens[j])
        or tokens[j] in ("env", "command")
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
    return ""


def query_open_prs(repo_slug: str):
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


invocations = []
for gh_index in gh_create_indices:
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
    invocations.append(
        (gh_index, head_branch, base_branch, repo_slug, compute_split_prefix(head_branch))
    )

for gh_index, head_branch, base_branch, repo_slug, split_prefix in invocations:
    if has_inline_override(gh_index):
        continue
    is_stacked = base_branch not in ("main", "master", "")
    if not split_prefix and not is_stacked:
        continue

    open_prs = query_open_prs(repo_slug)
    if open_prs is None:
        sys.exit(0)

    if split_prefix:
        projected_creates = sum(
            1
            for item in invocations
            if item[0] <= gh_index and item[4] == split_prefix
        )
        matching_split_prs = [
            p
            for p in open_prs
            if (p.get("headRefName") or "").startswith(split_prefix)
        ]
        if len(matching_split_prs) + projected_creates > 5:
            nums = ", ".join(f"#{p.get('number')}" for p in matching_split_prs[:10])
            sys.stderr.write(
                f"BLOCKED by protect-pr-create.sh: split PR quantity cap exceeded for prefix '{split_prefix}'.\n"
                f"Found {len(matching_split_prs)} open PRs already matching '{split_prefix}*' ({nums}); ceiling is <= 5.\n"
                f"Do NOT atomize features into unbounded micro-PRs. Consolidate into an existing PR or a single unified PR targeting 'main'.\n"
                f"If the human operator explicitly authorized >5 split PRs, set ALLOW_PR_STACK_OVERRIDE=1.\n"
            )
            sys.exit(2)

    if is_stacked:
        projected_creates = sum(
            1
            for item in invocations
            if item[0] <= gh_index
            if item[2] not in ("main", "master", "")
        )
        stacked_prs = [
            p
            for p in open_prs
            if (p.get("baseRefName") or "main") not in ("main", "master")
        ]
        if len(stacked_prs) + projected_creates >= 10:
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
