#!/usr/bin/env python3
"""Verdict-contract tests for the advice primary-pair runner."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

RUNNER_PATH = Path(__file__).with_name("run_primary_pair.py")
SPEC = importlib.util.spec_from_file_location("advice_primary_pair", RUNNER_PATH)
assert SPEC is not None and SPEC.loader is not None
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class VerdictContractTest(unittest.TestCase):
    def test_output_contract_demands_literal_verdict_line(self) -> None:
        self.assertIn("VERDICT: APPROVED", runner.OUTPUT_CONTRACT)
        self.assertIn("VERDICT: NOT APPROVED", runner.OUTPUT_CONTRACT)

    def test_observed_agy_numbered_executive_heading(self) -> None:
        self.assertTrue(
            runner.has_verdict("### 1. Executive Verdict: APPROVE WITH CONDITIONS\nbody\n")
        )

    def test_observed_bold_final_verdict(self) -> None:
        text = "intro\n**Final verdict:** NOT APPROVED at abc123\n"
        self.assertTrue(runner.has_verdict(text))
        self.assertEqual(runner.parse_verdict(text), "NOT APPROVED")

    def test_plain_and_wrapped_forms_still_parse(self) -> None:
        self.assertEqual(runner.parse_verdict("VERDICT: APPROVED at abc\n"), "APPROVED")
        self.assertEqual(runner.parse_verdict("**VERDICT:** APPROVED\n"), "APPROVED")
        self.assertEqual(runner.parse_verdict("## VERDICT - NOT APPROVED\n"), "NOT APPROVED")

    def test_output_without_verdict_still_fails(self) -> None:
        text = "I reviewed the change.\nThe verdict is unclear to me.\nLooks fine overall.\n"
        self.assertFalse(runner.has_verdict(text))
        self.assertIsNone(runner.parse_verdict(text))


if __name__ == "__main__":
    unittest.main()
