#!/usr/bin/env python3
"""test_parse_fields.py — unit tests for parse_fields.py's JSON-hardening.

Bead rev-1jtb5: PR #8193 round 3 hardened compute_verdict()'s api/docker/jeff
json.loads() calls against empty-string input, but api_fields()/docker_line()/
lima_line()/jeff_line() (the display-line functions used directly by
runner-health.sh) had no such guard, and no isinstance(dict) check existed
against a top-level JSON array. These tests exercise every function against:
empty string, invalid JSON, and a non-dict top-level value (a JSON array) --
the exact shapes an upstream check_*.sh script's stderr-not-stdout mistake
could produce.

Usage: python3 test_parse_fields.py
"""
import contextlib
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import parse_fields  # noqa: E402

MALFORMED_INPUTS = ["", "not json", "[]", "[1, 2, 3]", "null", "42", '"a string"']
# Non-empty malformed inputs are expected to warn to stderr (an empty string
# is the normal "check reported nothing" case and must stay silent).
NOISY_MALFORMED_INPUTS = ["not json", "[]", "[1, 2, 3]", "null", "42", '"a string"']


class TestSafeJsonLoads(unittest.TestCase):
    def test_valid_dict_passes_through(self):
        self.assertEqual(parse_fields._safe_json_loads('{"a": 1}'), {"a": 1})

    def test_empty_string_degrades_to_empty_dict(self):
        self.assertEqual(parse_fields._safe_json_loads(""), {})

    def test_invalid_json_degrades_to_empty_dict(self):
        self.assertEqual(parse_fields._safe_json_loads("not json"), {})

    def test_json_array_degrades_to_empty_dict(self):
        self.assertEqual(parse_fields._safe_json_loads("[1, 2, 3]"), {})

    def test_json_null_degrades_to_empty_dict(self):
        self.assertEqual(parse_fields._safe_json_loads("null"), {})

    def test_json_scalar_degrades_to_empty_dict(self):
        self.assertEqual(parse_fields._safe_json_loads("42"), {})
        self.assertEqual(parse_fields._safe_json_loads('"a string"'), {})

    def test_empty_string_warns_nothing(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            parse_fields._safe_json_loads("")
        self.assertEqual(stderr.getvalue(), "")

    def test_noisy_malformed_input_warns_to_stderr(self):
        for raw in NOISY_MALFORMED_INPUTS:
            with self.subTest(raw=raw):
                stderr = io.StringIO()
                with contextlib.redirect_stderr(stderr):
                    parse_fields._safe_json_loads(raw)
                self.assertIn("WARNING", stderr.getvalue())


class TestDisplayFunctionsAgainstMalformedInput(unittest.TestCase):
    """None of these should raise -- every malformed shape must degrade to
    a placeholder string, matching the existing '?' / '(no instances)'
    conventions each function already uses for missing (but present-dict)
    fields."""

    def test_api_fields_never_raises(self):
        for raw in MALFORMED_INPUTS:
            with self.subTest(raw=raw):
                result = parse_fields.api_fields(raw)
                self.assertIn("?", result)

    def test_docker_line_never_raises(self):
        for raw in MALFORMED_INPUTS:
            with self.subTest(raw=raw):
                result = parse_fields.docker_line(raw)
                self.assertIsInstance(result, str)

    def test_lima_line_never_raises(self):
        for raw in MALFORMED_INPUTS:
            with self.subTest(raw=raw):
                result = parse_fields.lima_line(raw)
                self.assertEqual(result, "(no instances)")

    def test_jeff_line_never_raises(self):
        for raw in MALFORMED_INPUTS:
            with self.subTest(raw=raw):
                result = parse_fields.jeff_line(raw)
                self.assertEqual(result, "?")

    def test_session_conflict_line_never_raises(self):
        for raw in MALFORMED_INPUTS:
            with self.subTest(raw=raw):
                result = parse_fields.session_conflict_line(raw)
                self.assertEqual(result, "none (all runners online)")


class TestComputeVerdictAgainstMalformedInput(unittest.TestCase):
    def test_verdict_degrades_to_amber_on_malformed_api(self):
        for raw in MALFORMED_INPUTS:
            with self.subTest(raw=raw):
                result = parse_fields.compute_verdict(raw, "{}", "{}")
                self.assertTrue(result.startswith("AMBER|API data unavailable"))

    def test_verdict_survives_malformed_docker_and_jeff_with_valid_api(self):
        valid_api = (
            '{"runners":{"online":22,"busy":10,'
            '"by_arch":{"linux_x64":{"online":16,"busy":8},'
            '"mac_arm64":{"online":6,"busy":2}}}}'
        )
        for raw in MALFORMED_INPUTS:
            with self.subTest(raw=raw):
                # Must not raise; docker/jeff degrade to {} and the verdict
                # still resolves off the valid api payload.
                result = parse_fields.compute_verdict(valid_api, raw, raw)
                self.assertTrue(result.startswith(("GREEN|", "AMBER|")))

    def test_verdict_still_correct_on_fully_valid_input(self):
        valid_api = (
            '{"runners":{"online":22,"busy":10,'
            '"by_arch":{"linux_x64":{"online":16,"busy":8},'
            '"mac_arm64":{"online":6,"busy":2}}}}'
        )
        result = parse_fields.compute_verdict(valid_api, "{}", '{"reachable": true}')
        self.assertTrue(result.startswith("GREEN|"))

    def test_session_conflict_error_does_not_mask_red(self):
        critical_linux_api = (
            '{"runners":{"online":8,"busy":0,'
            '"by_arch":{"linux_x64":{"online":8,"busy":0},'
            '"mac_arm64":{"online":6,"busy":0}}}}'
        )
        session_conflict_error = '{"error":"api unavailable","session_conflicts":[]}'
        result = parse_fields.compute_verdict(
            critical_linux_api,
            '{"containers":{"restarting":0}}',
            '{"reachable":true}',
            session_conflict_error,
        )
        self.assertTrue(result.startswith("RED|Linux fleet critically low"))


if __name__ == "__main__":
    unittest.main()
