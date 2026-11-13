"""Every documented legacy stage prefix/suffix maps exactly (PR #742 r10; pr-lifecycle/six-stage.md)."""

import unittest

from scripts.prw_metrics import Collector, parse_operational_title

SUFFIXES = {
    "specification": "stage:0-spec",
    "coding": "stage:1-coding",
    "evidence generation": "stage:2-evidence",
    "evidence review": "stage:3-evidence-review",
    "CI and undraft": "stage:4-ci-undraft",
    "final approval": "stage:5-final-approval",
}
PREFIXES = {
    "sp": "stage:0-spec",
    "cd": "stage:1-coding",
    "ev": "stage:2-evidence",
    "er": "stage:3-evidence-review",
    "ci": "stage:4-ci-undraft",
    "fa": "stage:5-final-approval",
}


class TestLegacyStageTokens(unittest.TestCase):
    def test_plain_titles_with_trailing_suffix(self):
        for token, stage in SUFFIXES.items():
            out = parse_operational_title(f"Fix the thing [{token}]")
            self.assertEqual(out["legacy_stage"], stage, token)
            self.assertEqual(out["substantive_title"], "Fix the thing", token)

    def test_operational_titles_with_trailing_suffix_and_provenance(self):
        for token, stage in SUFFIXES.items():
            out = parse_operational_title(f"[working][fixing review] Fix the thing [{token}]")
            self.assertEqual(out["legacy_stage"], stage, token)
            self.assertEqual(out["status"], "working")

    def test_short_prefix_and_suffix_forms(self):
        for token, stage in PREFIXES.items():
            self.assertEqual(parse_operational_title(f"[{token}] Fix the thing")["legacy_stage"], stage, token)
            self.assertEqual(parse_operational_title(f"Fix the thing [{token}]")["legacy_stage"], stage, token)

    def test_case_and_inner_whitespace_normalized(self):
        self.assertEqual(parse_operational_title("x [Evidence  Generation]")["legacy_stage"], "stage:2-evidence")
        self.assertEqual(parse_operational_title("x [ci AND undraft]")["legacy_stage"], "stage:4-ci-undraft")

    def test_unrecognized_tokens_are_not_matched_fuzzily(self):
        for token in ("evidence gen", "evidence reviewed", "ci undraft", "finalapproval", "reviewing", "claude", "gpt-5"):
            self.assertIsNone(parse_operational_title(f"Fix the thing [{token}]")["legacy_stage"], token)

    def test_stage_survives_normalization(self):
        pr = Collector().normalize_pr_record({"number": 1, "repo": "o/r", "title": "Fix [CI and undraft]"})
        self.assertEqual(pr["legacy_stage"], "stage:4-ci-undraft")


if __name__ == "__main__":
    unittest.main()
