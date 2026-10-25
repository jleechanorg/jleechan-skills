"""Documentation contracts for authorized dot-to-dot Slack assignments."""

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class SlackAssignmentIdentityTest(unittest.TestCase):
    def test_identity_policy_precedes_media_dispatch(self):
        command = (ROOT / ".claude/commands/slack.md").read_text()
        self.assertLess(command.index("slack-identity/SKILL.md"),
                        command.index("slack-media-upload/SKILL.md"))
        self.assertIn("$ARGUMENTS", command)
        self.assertIn("slack_upload.py", command)
        self.assertIn("For media", command)
        self.assertLessEqual(len(command.splitlines()), 15)

    def test_assignment_route_is_verified_attributed_and_fail_closed(self):
        policy = (ROOT / ".claude/skills/slack-identity/SKILL.md").read_text()
        section = policy.split("## Authorized dot-to-dot assignments\n", 1)[1].split("\n## ", 1)[0]
        for requirement in (
            "user-account connector", "not the dot's or a bot's identity",
            "connector profile", "private local configuration", "workspace and user ID",
            "authorized operator", "recipient", "[AI Terminal: <workspace-name>]",
            "blocked", "Do not fall back", "copy tokens", "read back",
            "author", "channel", "thread", "uncertain", "duplicate",
            "ordinary bot updates", "does not grant new authority",
        ):
            with self.subTest(requirement=requirement):
                self.assertIn(requirement, section)


if __name__ == "__main__":
    unittest.main()
