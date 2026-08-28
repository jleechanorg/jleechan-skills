"""Contract test: the 5-minute checkpoint cadence is documented consistently
across /sidekick, /swarm, and /team-claude.

Adapted from PR #329's tests/test_real_claude_team_contract.py. That PR's
version also asserted a "tmux-only, no Agent Teams" stance (forbidding tokens
like `TaskCreate`, `SendMessage`, `Agent(` in the sidekick/team-claude docs) —
this repo's current content documents the OPPOSITE and more recent policy
(named in-session Agent Teams as the DEFAULT, tmux as the fallback; see the
"DEFAULT (user directive 2026-07-11)" language in .claude/skills/swarm/SKILL.md
and .claude/skills/sidekick/SKILL.md). Those two assertions are intentionally
NOT carried over here since they'd just be re-litigating a policy call that's
out of scope for a checkpoint-cadence regression test. Everything below is
policy-neutral: it only checks that the cadence contract (heartbeat interval,
`br update`/`br sync`, single-writer rule, commit-safety escape hatch) is
actually documented, regardless of which durability mechanism (in-session vs
tmux) a given mission ends up using.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
COMMANDS_DIR = REPO_ROOT / ".claude" / "commands"


def _resolve_command(filename: str) -> Path:
    # Commands live flat when in the Active Core set, else under extended-library/.
    flat = COMMANDS_DIR / filename
    return flat if flat.is_file() else COMMANDS_DIR / "extended-library" / filename


TEAM_CLAUDE = _resolve_command("team-claude.md")
SIDEKICK_CMD = _resolve_command("sidekick.md")
SIDEKICK_SKILL = REPO_ROOT / ".claude" / "skills" / "sidekick" / "SKILL.md"
SWARM_SKILL = REPO_ROOT / ".claude" / "skills" / "swarm" / "SKILL.md"

CHECKPOINT_CADENCE_RE = re.compile(r"5-minute checkpoint cadence", re.IGNORECASE)
CADENCE_TIME_RE = re.compile(r"≤\s*5\s*min", re.IGNORECASE)
BR_UPDATE_RE = re.compile(r"br\s+update", re.IGNORECASE)
SINGLE_WRITER_RE = re.compile(
    r"single-?writer|one\s+writer|one\s+bead\s+writer", re.IGNORECASE
)
CHECKPOINT_KEYWORDS = ("STATE.md", "br sync")
COMMIT_SAFETY_KEYWORDS = (
    "git add -A",
    "isolated state repo",
    "WIP branch",
    "path-scoped",
)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class CheckpointCadenceContractTest(unittest.TestCase):
    def test_sidekick_skill_declares_cadence(self):
        text = read(SIDEKICK_SKILL)
        self.assertRegex(text, CHECKPOINT_CADENCE_RE)
        self.assertRegex(text, CADENCE_TIME_RE)
        self.assertRegex(text, BR_UPDATE_RE)
        for kw in CHECKPOINT_KEYWORDS:
            self.assertIn(kw, text)
        self.assertTrue(any(k in text for k in COMMIT_SAFETY_KEYWORDS))

    def test_swarm_skill_declares_cadence(self):
        text = read(SWARM_SKILL)
        self.assertRegex(text, CHECKPOINT_CADENCE_RE)
        self.assertRegex(text, CADENCE_TIME_RE)
        self.assertRegex(text, BR_UPDATE_RE)
        self.assertRegex(text, SINGLE_WRITER_RE)
        for kw in CHECKPOINT_KEYWORDS:
            self.assertIn(kw, text)
        self.assertTrue(any(k in text for k in COMMIT_SAFETY_KEYWORDS))

    def test_sidekick_command_carries_cadence_contract(self):
        text = read(SIDEKICK_CMD)
        self.assertIn("/skills/sidekick/SKILL.md", text)
        self.assertIn("$ARGUMENTS", text)
        skill_text = read(SIDEKICK_SKILL)
        self.assertRegex(skill_text, CHECKPOINT_CADENCE_RE)
        self.assertRegex(skill_text, CADENCE_TIME_RE)
        self.assertRegex(skill_text, SINGLE_WRITER_RE)
        self.assertIn("STATE.md", skill_text)
        self.assertIn("br update", skill_text)
        self.assertIn("br sync", skill_text)
        self.assertTrue(any(k in skill_text for k in COMMIT_SAFETY_KEYWORDS))

    def test_team_claude_command_carries_cadence_contract(self):
        text = read(TEAM_CLAUDE)
        self.assertRegex(text, CHECKPOINT_CADENCE_RE)
        self.assertRegex(text, CADENCE_TIME_RE)
        self.assertTrue(any(k in text for k in COMMIT_SAFETY_KEYWORDS))


if __name__ == "__main__":
    unittest.main()
