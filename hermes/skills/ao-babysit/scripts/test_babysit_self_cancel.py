#!/usr/bin/env python3
"""
test_babysit_self_cancel.py — regression contract for babysit.py self-cancel.

Bug-ref (2026-07-05): The PR-babysit cron instructions documented self-cancel via
`cronjob action=remove job_id=$CRON_JOB_ID`, but babysit.py had no
`--cron-job-id` parameter and no way to invoke the cronjob CLI. Every cron
prompt that said "issue cronjob action=remove on terminal PR" was therefore
unreachable from the script itself.

This test suite enforces the executable contract:
  1. `babysit.py` MUST have a `--cron-job-id` CLI argument on both subcommands.
  2. `babysit.py` MUST define a `cronjob_remove(job_id)` helper.
  3. `babysit.poll()` MUST invoke `cronjob_remove(cron_job_id)` when the
     terminal-PR branch fires (the gap that produced today's deluge).
  4. `babysit.babysit_loop()` MUST forward `cron_job_id` into `poll()`.
  5. `babysit.main()` MUST pass `args.cron_job_id` to both `poll()` and
     `babysit_loop()`.

Companion to test_babysit_pr_exit.py — that suite covers the PR-extraction
layer (`is_pr_terminal`, `extract_pr_refs`); this one covers the cron-self-
cancel layer that was the actual gap on 2026-07-05.
"""

import ast
import re
import unittest
from pathlib import Path

BABYSIT_PY = Path(__file__).resolve().parent / "babysit.py"
SOURCE = BABYSIT_PY.read_text()
TREE = ast.parse(SOURCE)


def _find_func(name: str) -> ast.FunctionDef | None:
    for node in ast.walk(TREE):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _func_body_source(name: str) -> str:
    """Return the source text of a top-level function's body (after the docstring)."""
    fn = _find_func(name)
    if fn is None:
        return ""
    lines = SOURCE.splitlines()
    # body starts after the def line and any docstring
    body_start = fn.body[0].lineno  # 1-indexed first body line
    # If first statement is a docstring, skip it
    if isinstance(fn.body[0], ast.Expr) and isinstance(fn.body[0].value, ast.Constant):
        body_start = fn.body[1].lineno if len(fn.body) > 1 else body_start
    body_end = fn.end_lineno or body_start
    return "\n".join(lines[body_start - 1 : body_end])


class TestBabysitSelfCancelContract(unittest.TestCase):
    """Verify babysit.py has the executable self-cancel plumbing."""

    def test_01_has_cronjob_remove_helper(self):
        """`cronjob_remove(job_id)` MUST be defined as a callable helper."""
        self.assertRegex(
            SOURCE,
            r"def\s+cronjob_remove\(\s*job_id[^)]*\)\s*->",
            "babysit.py is missing the `cronjob_remove(job_id)` helper",
        )

    def test_02_helper_invokes_cronjob_cli(self):
        """`cronjob_remove` MUST call `cronjob action=remove job_id=...`."""
        body = _func_body_source("cronjob_remove")
        self.assertTrue(body, "cronjob_remove body not found")
        self.assertIn("cronjob", body)
        self.assertIn("action=remove", body)
        self.assertIn("job_id=", body)

    def test_03_poll_accepts_cron_job_id_kwarg(self):
        """`poll()` MUST accept `cron_job_id` as a keyword arg with default ''."""
        m = re.search(r"def\s+poll\(([^)]*)\)\s*->", SOURCE, re.DOTALL)
        self.assertIsNotNone(m, "poll() signature not found")
        sig = m.group(1)
        self.assertIn(
            "cron_job_id",
            sig,
            "poll() must accept a cron_job_id parameter for self-cancel",
        )

    def test_04_terminal_pr_branch_invokes_cronjob_remove(self):
        """The terminal-PR branch in poll() MUST call cronjob_remove(cron_job_id)."""
        # Find the terminal-PR short-circuit block (between
        # "if is_terminal:" and the next "tmux_session = find_tmux_session")
        m = re.search(
            r"if\s+is_terminal:(.*?)tmux_session\s*=\s*find_tmux_session",
            SOURCE,
            re.DOTALL,
        )
        self.assertIsNotNone(m, "terminal-PR short-circuit block not found")
        block = m.group(1)
        self.assertIn(
            "cronjob_remove",
            block,
            "terminal-PR branch must call cronjob_remove() to self-cancel",
        )
        self.assertIn(
            "cron_job_id",
            block,
            "terminal-PR branch must pass cron_job_id into cronjob_remove()",
        )

    def test_05_babysit_loop_forwards_cron_job_id(self):
        """`babysit_loop()` MUST forward cron_job_id into poll()."""
        m = re.search(r"def\s+babysit_loop\(([^)]*)\)\s*->", SOURCE, re.DOTALL)
        self.assertIsNotNone(m, "babysit_loop() signature not found")
        sig = m.group(1)
        self.assertIn("cron_job_id", sig)
        # Find the recursive poll() call inside babysit_loop
        body = _func_body_source("babysit_loop")
        self.assertTrue(body, "babysit_loop body not found")
        self.assertRegex(
            body,
            r"poll\([^)]*cron_job_id\s*=\s*cron_job_id",
            "babysit_loop() must forward cron_job_id=cron_job_id to poll()",
        )

    def test_06_poll_subcommand_has_cron_job_id_arg(self):
        """`poll` subcommand MUST register --cron-job-id."""
        m = re.search(
            r'poll_cmd\s*=\s*sub\.add_parser\(\s*"poll".*?(?=babysit_cmd\s*=)',
            SOURCE,
            re.DOTALL,
        )
        self.assertIsNotNone(m, "poll subcommand definition not found")
        block = m.group(0)
        self.assertIn(
            '"--cron-job-id"',
            block,
            "poll subcommand must declare --cron-job-id CLI arg",
        )

    def test_07_babysit_subcommand_has_cron_job_id_arg(self):
        """`babysit` subcommand MUST register --cron-job-id."""
        m = re.search(
            r'babysit_cmd\s*=\s*sub\.add_parser\(\s*"babysit".*?(?=\n\s*args\s*=)',
            SOURCE,
            re.DOTALL,
        )
        self.assertIsNotNone(m, "babysit subcommand definition not found")
        block = m.group(0)
        self.assertIn(
            '"--cron-job-id"',
            block,
            "babysit subcommand must declare --cron-job-id CLI arg",
        )

    def test_08_main_dispatches_cron_job_id(self):
        """`main()` MUST pass args.cron_job_id to poll() and babysit_loop()."""
        body = _func_body_source("main")
        self.assertTrue(body, "main() not found")
        self.assertIn(
            "args.cron_job_id",
            body,
            "main() must pass args.cron_job_id into poll() and babysit_loop()",
        )

    def test_09_poll_returns_cron_self_canceled_key(self):
        """`poll()` MUST return a `cron_self_canceled` boolean in the terminal-PR branch."""
        m = re.search(
            r"if\s+is_terminal:(.*?)tmux_session\s*=\s*find_tmux_session",
            SOURCE,
            re.DOTALL,
        )
        self.assertIsNotNone(m)
        block = m.group(1)
        self.assertIn(
            "cron_self_canceled",
            block,
            "poll() must surface cron_self_canceled in the result dict so "
            "the watchdog / caller can detect failed self-cancels",
        )


class TestBabysitCLIRuns(unittest.TestCase):
    """Smoke-test the CLI parses --cron-job-id."""

    def test_10_poll_help_lists_cron_job_id(self):
        import subprocess
        import sys
        r = subprocess.run(
            [sys.executable, str(BABYSIT_PY), "poll", "--help"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(r.returncode, 0)
        self.assertIn("--cron-job-id", r.stdout)

    def test_11_babysit_help_lists_cron_job_id(self):
        import subprocess
        import sys
        r = subprocess.run(
            [sys.executable, str(BABYSIT_PY), "babysit", "--help"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(r.returncode, 0)
        self.assertIn("--cron-job-id", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)