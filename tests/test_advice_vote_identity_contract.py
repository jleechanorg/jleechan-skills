"""Contract: an /advice vote belongs to a separate cold review, not to an account or model."""
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
ADVICE = (ROOT / ".claude/skills/advice/SKILL.md").read_text(encoding="utf-8")
MANAGER = (ROOT / ".claude/skills/pr-workflow-manager/SKILL.md").read_text(encoding="utf-8")


class AdviceVoteIdentityContract(unittest.TestCase):
    def test_same_account_or_model_seats_each_count(self):
        self.assertIn("A vote belongs to a separate cold review, not to an account or model.", ADVICE)
        self.assertIn("including a static reviewer on the host's own account", ADVICE)

    def test_old_one_account_rule_is_gone(self):
        for phrase in ("One account is one vote", "aliases\nof one account independent", "shared identity key"):
            self.assertNotIn(phrase, ADVICE)
        self.assertNotIn("counting one account once", MANAGER)

    def test_caps_and_non_voters_remain(self):
        self.assertIn("Static subagents collectively count as at most one vote", ADVICE)
        self.assertIn("a retry, alias or wrapper of one seat", ADVICE)
        self.assertIn("Neither the author nor the orchestrator awards itself a vote", ADVICE)


if __name__ == "__main__":
    unittest.main()
