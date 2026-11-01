"""The advice skill resolves reviewer commands from machine-local env values only."""
import re
import tempfile
import unittest
import unittest.mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".claude/skills/advice/SKILL.md"


class AdviceMachineLocalCliTest(unittest.TestCase):
    def setUp(self):
        self.text = SKILL.read_text(encoding="utf-8")

    def test_every_seat_resolves_from_an_env_variable_with_a_default(self):
        for name in ("ADVICE_CODEX_CMD", "ADVICE_CLAUDE_CMD", "ADVICE_CLAUDE_ALT_CMD", "ADVICE_EXTRA_CLIS"):
            self.assertIn(name, self.text, name)
        self.assertIn("falls back to the default", self.text)
        self.assertIn("so a bare machine still works", self.text)

    def test_extra_cli_registration_is_documented_with_safe_parsing(self):
        section = " ".join(self.text.split("### `ADVICE_EXTRA_CLIS`", 1)[1].split("## 3.", 1)[0].split())
        self.assertIn("seats separated by `|`", section)
        self.assertIn('Seat separation is honoured **outside quotes**', section)
        self.assertIn('duplicate label', section)
        self.assertIn("{prompt}", section)
        self.assertIn("No shell evaluation", section)
        self.assertIn("makes **that seat `UNAVAILABLE`**", section)
        self.assertIn("never becomes a second vote from the same identity", section)

    def test_no_machine_specific_configuration_is_committed(self):
        self.assertIn("Machine-specific configuration never lives in this repository", self.text)
        self.assertIn("belongs in", self.text)
        self.assertIn("never in a skill file, a PR or a document", self.text)
        # concrete machine paths, credential-store dirs and profile names must not appear
        for forbidden in (".claude-wa", "/Users/", "/home/", "user_data_dir", "CLAUDE_CONFIG_DIR="):
            self.assertNotIn(forbidden, self.text, forbidden)
        self.assertIsNone(re.search(r"\b[A-Za-z0-9_.-]+/roadmap(?:/|\b)", self.text))

    def test_wrapper_alternate_is_named_as_a_shape_not_a_path(self):
        self.assertIn("claudewa", self.text)
        self.assertIn("the attempt records the\nactual model it ran", self.text)


class MarkdownOnlyDecisionTest(unittest.TestCase):
    """The slimming decision: this skill stays markdown-first with no new runner code."""

    def setUp(self):
        self.text = (ROOT / ".claude/skills/advice/SKILL.md").read_text(encoding="utf-8")

    def test_late_result_gating_sentence_is_intact(self):
        text = (ROOT / ".claude/skills/advice/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("A late, incomplete, failed, or timed-out result is not an approval.", text)
        self.assertNotIn("A late, e, incomplete", text)

    def test_revision_isolation_records_are_explicit(self):
        text = (ROOT / ".claude/skills/advice/SKILL.md").read_text(encoding="utf-8")
        section = text.split("## 4. Isolate review copies", 1)[1].split("## 5.", 1)[0]
        flat = " ".join(section.split())
        for record in ("isolation: orchestrator-clone", "isolation: self-clone", "isolation: none"):
            self.assertIn(record, flat)
        self.assertIn("Revision mode is available to the first two records only", flat)
        self.assertIn("The donor is internal staging", flat)
        self.assertIn("never a seat's working directory, never inside a clone, never shared", flat)
        self.assertIn("Clones live only in an allocated scratch directory, never `/tmp`", flat)
        self.assertIn("deletion always names the literal absolute path", flat)
        self.assertIn("passes the remote URL, the review SHA **and** the recorded base SHA", flat)
        self.assertIn("`git remote -v`", flat)
        self.assertIn("that path is absent from its own filesystem afterwards", flat)
        self.assertIn("A failed or unverified removal voids the vote", flat)
        for retired in ("taking snapshots", "existing revision-review workflow", "saved-Markdown-byte overlay"):
            self.assertNotIn(retired, flat)
        scripts = ROOT / ".claude/skills/advice/scripts"
        self.assertEqual(sorted(p.name for p in scripts.glob("*") if p.is_file()), [])

    def test_no_active_skill_invokes_the_deleted_runner(self):
        offenders = []
        for path in sorted((ROOT / ".claude/skills").rglob("*.md")):
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "run_primary_pair" in text or "primary-pair runner" in text:
                offenders.append(str(path.relative_to(ROOT)))
        self.assertEqual(offenders, [],
                         "no active skill may invoke or describe the deleted runner")

    def test_skill_declares_it_ships_no_runner(self):
        flat = " ".join(self.text.split())
        self.assertIn("There is **no bundled runner**", flat)
        self.assertIn("markdown only, zero runner code", flat)
        self.assertNotIn("run_primary_pair", flat)

    def test_the_skill_ships_no_runner_code(self):
        scripts = ROOT / ".claude/skills/advice/scripts"
        self.assertFalse((scripts / "run_primary_pair.py").exists(),
                         "the slimming decision removed the bundled runner")
        remaining = sorted(p.name for p in scripts.glob("*.py")) if scripts.is_dir() else []
        self.assertEqual(remaining, [], f"no runner code may return: {remaining}")


if __name__ == "__main__":
    unittest.main()
