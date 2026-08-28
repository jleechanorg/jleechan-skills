#!/usr/bin/env python3
"""
Test approval pattern coverage for cmux-codex-autoapprove.

Run with: python3 test_approval_patterns.py

This test verifies that every pattern in YN_APPROVE_RE and APPROVE_OPTION_RE
passes BOTH is_approval_candidate() AND produces a non-empty heuristic_decision().
If a pattern is only wired into one function but not the other, it silently fails.

Pattern wiring rule: new detection patterns must be tested at ALL call sites,
not just the obvious one. See SKILL.md § When To Edit.
"""

import re
import sys
import types
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
WORKER = SCRIPT_DIR / "cmux_codex_approve_launchd.py"

if not WORKER.exists():
    print(f"SKIP: worker not found at {WORKER}", file=sys.stderr)
    sys.exit(0)

# Load the actual worker module
worker_src = WORKER.read_text()
module = types.ModuleType("worker")
exec(compile(worker_src, str(WORKER), "exec"), module.__dict__)

APPROVE_OPTION_RE = module.APPROVE_OPTION_RE
YN_APPROVE_RE = module.YN_APPROVE_RE
is_approval_candidate = module.is_approval_candidate
heuristic_decision = module.heuristic_decision


# ---------------------------------------------------------------------------
# Test cases: (label, screen_text, expected_heuristic_result)
# Screen text must contain BOTH the question/anchor AND the numbered option
# so it represents a real full approval dialog.
# ---------------------------------------------------------------------------
DIALOGS = [
    # (label, screen_text, expected_decision)
    # === Do you want to family ===
    ("Do you want to proceed + 1. Yes",
     "Do you want to proceed?\n  ❯ 1. Yes\n  2. No",
     "1"),

    ("Do you want to create + 1. Yes",
     "Do you want to create zero-touch-metrics.md?\n  ❯ 1. Yes\n  2. No",
     "1"),

    ("Do you want to make this edit + 1. Yes",
     "Do you want to make this edit to .bashrc?\n  ❯ 1. Yes\n  2. No",
     "1"),

    ("Do you want to run + 1. Yes",
     "Do you want to run the following command?\n  ❯ 1. Yes\n  2. No",
     "1"),

    # === Would you like to family ===
    ("Would you like to proceed + 1. Yes",
     "Would you like to proceed?\n  ❯ 1. Yes\n  2. No",
     "1"),

    ("Would you like to run + 1. Yes",
     "Would you like to run the following command?\n  ❯ 1. Yes\n  2. No",
     "1"),

    ("Would you like to install + 1. Yes",
     "Would you like to install Claude in Chrome?\n  ❯ 1. Yes\n  2. No",
     "1"),

    # === Want to family ===
    ("Want to proceed + 1. Yes",
     "Want to proceed?\n  ❯ 1. Yes\n  2. No",
     "1"),

    # === Proceed? / Continue? bare forms ===
    ("Proceed? + 1. Yes",
     "Proceed?\n  ❯ 1. Yes\n  2. No",
     "1"),

    ("Continue? + 1. Yes",
     "Continue?\n  ❯ 1. Yes\n  2. No",
     "1"),

    # === May I / Shall I ===
    ("May I run this command + 1. Yes",
     "May I run this command?\n  ❯ 1. Yes\n  2. No",
     "1"),

    ("Shall I proceed + 1. Yes",
     "Shall I proceed?\n  ❯ 1. Yes\n  2. No",
     "1"),

    # === Bracket y/n forms ===
    ("[y/N] prompt + 1. Yes",
     "Allow this command? [y/N]\n  ❯ 1. Yes\n  2. No",
     "1"),

    ("[Y/n] prompt + 1. Yes",
     "Confirm [Y/n]\n  ❯ 1. Yes\n  2. No",
     "1"),

    # === Bare Confirm ===
    ("Confirm? + 1. Yes",
     "Confirm? [y/N]\n  ❯ 1. Yes\n  2. No",
     "1"),

    # === Standard Claude Code footer patterns ===
    ("esc to cancel + enter to submit",
     "Do you want to make this change?\n  ❯ 1. Yes\n  2. No\n  esc to cancel  ·  enter to submit",
     "1"),

    ("enter to submit + esc to cancel",
     "Would you like to run this command?\n  ❯ 1. Yes\n  2. No\n  enter to submit  |  esc to cancel",
     "1"),

    # === approve-all-style options ===
    ("approve everything option",
     "Tool call needs your approval\n  ❯ 1. Yes\n  2. No\n  3. Yes, and don't ask again",
     "1"),

    # === Claude permission prompts (real dialogs that were missed) ===
    ("permission edit + always allow",
     "Claude requested permissions to edit $HOME/.claude/skills/cmux-codex-autoapprove/scripts/test_approval_patterns.py which is a sensitive file.\n\nDo you want to proceed?\n❯ 1. Yes\n  2. Yes, and always allow access to scripts/ from this project\n  3. No",
     "1"),

    ("permission write + always allow",
     "Claude requested permissions to write to $HOME/.hermes/.claude/skills/deploy-hermes, but you haven't granted it yet.\n\nDo you want to proceed?\n  ❯ 1. Yes\n  2. Yes, and always allow access to skills/ from this project\n  3. No",
     "1"),

    # === Format-robustness against prompt rendering variants ===
    ("permission write + 1) Continue / 2) Cancel",
     "Claude requested permissions to write to $HOME/.claude/projects/-Users-$USER-llm-wiki/memory/, but you haven't granted it yet.\n\nProceed?\n  1) Continue\n  2) Cancel",
     "1"),

    ("permission edit + yes and allow claude settings",
     "Do you want to make this edit to evidence-reviewer.md?\n  1. Yes\n  2. Yes, and allow Claude to edit its own settings for this session\n  3. No",
     "1"),

    ("permission edit + yes allow all during session",
     "Do you want to make this edit to .bashrc?\n  1. Yes\n  2. Yes, allow all edits in $USER/ during this session (shift+tab)\n  3. No",
     "2"),

    ("numbered option with ) style",
     "Do you want to proceed?\n  1) Yes\n  2) No",
     "1"),

    ("ANSI-colored option marker",
     "Do you want to proceed?\n\u001b[36m  ❯ 1. Yes\u001b[0m\n  2. No",
     "1"),

    ("hard-space separator + wrapped prompt text",
     "Claude requested permissions to edit $HOME/.claude/skills/cmux-codex-autoapprove/scripts/test_approval_patterns.py.\n  Do you want to proceed?\n  ❯\u00a01. Yes\n  2. No",
     "1"),

    ("requires approval by policy",
     "requires approval by policy\nWould you like to run the following command?\n  1. Yes\n  2. No",
     "1"),

    ("allow this command",
     "Allow this command?\n  1. Yes\n  2. No",
     "1"),

    # === Just y/n no numbered option ===
    ("bare [y/N] with confirm",
     "Do you want to proceed?\nConfirm? [y/N]",
     "y"),

    ("classic (Y)es /(N)o style",
     "Do you want to proceed? (Y)es / (N)o",
     "y"),

]

NEGATIVE_DIALS = [
    # ---------------------------------------------------------------------
    # Real-world text that should NOT be treated as an approval prompt
    # ---------------------------------------------------------------------
    (
        "plain statement with words do you want",
        "Would you like to check this note? No action required.",
        "",
    ),
    (
        "status line with bypass permissions mention",
        "bypass permissions mode is enabled for this profile.",
        "",
    ),
    (
        "status line with yes/no snippet",
        "(Y)es / (N)o appears in docs",
        "",
    ),
    (
        "numbered list in prose should not trigger",
        "Build steps:\n1. Gather files\n2. Run checks\n3. Publish",
        "",
    ),
    (
        "plain y/n ratio text",
        "Compression ratio is y/n-like, not an interactive prompt.",
        "",
    ),
    (
        "question but no choices",
        "Do you want to proceed? This is a status update and no input is expected.",
        "",
    ),
    (
        "yes/no words in prose",
        "Yes/no is used as a shorthand internally; this is not a permission dialog.",
        "",
    ),
]

SOCKET_DISCOVER_PATTERNS = [
    ("cmux.sock", True),
    ("cmux-debug-appclick.sock", True),
    ("cmux-foo.sock", True),
    ("foo-cmux.txt", False),
    ("cmux.sock.bak", False),
    ("not-a-socket.cmux", False),
]


def run_tests():
    failures = []
    for label, screen_text, expected in DIALOGS:
        cand = is_approval_candidate(screen_text)
        if not cand:
            failures.append(f"FAIL {label!r}: is_approval_candidate() returned False (should be True)")
            continue

        result = heuristic_decision(screen_text)
        if result != expected:
            failures.append(
                f"FAIL {label!r}: heuristic_decision() returned {result!r}, expected {expected!r}"
            )
        else:
            print(f"PASS: {label}")

    for label, screen_text, expected in NEGATIVE_DIALS:
        cand = is_approval_candidate(screen_text)
        if cand:
            failures.append(
                f"FAIL {label!r}: is_approval_candidate() returned True (should be False)"
            )
            continue
        result = heuristic_decision(screen_text)
        if result != expected:
            failures.append(
                f"FAIL {label!r}: heuristic_decision() returned {result!r}, expected {expected!r}"
            )
        else:
            print(f"PASS: {label}")

    for filename, expected in SOCKET_DISCOVER_PATTERNS:
        result = bool(module.CMUX_SOCKET_DISCOVER_RE.search(filename))
        if result != expected:
            failures.append(
                f"FAIL socket-pattern {filename!r}: regex returned {result!r}, expected {expected!r}"
            )
        else:
            print(f"PASS: socket-pattern {filename!r}")

    if failures:
        print("\n" + "\n".join(failures), file=sys.stderr)
        sys.exit(1)
    print(
        f"\nAll {len(DIALOGS)} dialog patterns, {len(NEGATIVE_DIALS)} negative cases, "
        f"and {len(SOCKET_DISCOVER_PATTERNS)} socket-name patterns passed."
    )
    sys.exit(0)


if __name__ == "__main__":
    run_tests()
