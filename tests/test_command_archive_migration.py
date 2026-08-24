"""Contract test for command archive migration (bd-cmdtop40-migration-test-dhi).

Asserts the post-migration end state under the new binding decision (superseding
the earlier 94-command closure version):
1. Active core commands in .claude/commands/ match the 28-command Promoted list.
2. Extended commands in .claude/commands/extended-library/ match the 211-command list.
3. Every cross-library reference from promoted to extended resolves in extended-library/.
4. All 27 top-20 human / top-20 agent seed commands remain active, plus forced 'innov'.

This test is expected to be RED on active counts, extended-library counts, and
cross-library resolution until bd-cmdtop40-archive-execute-710 executes the moves.
"""

import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.compute_command_closure import (
    NON_COMMAND_TOKENS,
    extract_references_from_text,
)

COMMANDS_DIR = REPO_ROOT / ".claude" / "commands"
EXTENDED_LIBRARY_DIR = COMMANDS_DIR / "extended-library"
DECISION_DOC = REPO_ROOT / "archive" / "ARCHIVE-DECISION-2026-08-23.md"

# 27 seed commands from top-20 human ∪ top-20 agent union (hard floor; 'innov' is 28th include)
SEED_COMMANDS: tuple[str, ...] = (
    "advice", "auto", "browser", "browserclaw", "claw", "copilot",
    "end2end-testing", "er", "es", "execute", "f", "fixpr", "green",
    "harness", "history", "learn", "levelup", "linux", "ms", "nextsteps",
    "repro", "research", "roadmap", "skillify", "smoke", "web-advice",
    "wiki-search",
)


def _parse_decision_list(doc_text: str, heading_prefix: str) -> set[str]:
    """Parse comma-separated backtick names from the section under heading_prefix."""
    lines = doc_text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith(heading_prefix):
            for next_line in lines[i + 1 :]:
                next_line = next_line.strip()
                if not next_line:
                    continue
                if re.match(r"^#{1,6}\s", next_line):
                    break
                names = set(re.findall(r"`([^`]+)`", next_line))
                if names:
                    return names
    return set()


class CommandArchiveMigrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not DECISION_DOC.is_file():
            raise FileNotFoundError(f"Decision ground-truth doc missing: {DECISION_DOC}")
        doc_text = DECISION_DOC.read_text(encoding="utf-8")
        cls.promoted = _parse_decision_list(doc_text, "### Promoted list")
        cls.extended = _parse_decision_list(doc_text, "### extended-library/ list")
        if len(cls.promoted) != 28:
            raise ValueError(f"Expected 28 promoted commands, parsed {len(cls.promoted)}")
        if len(cls.extended) != 211:
            raise ValueError(
                f"Expected 211 extended-library commands, parsed {len(cls.extended)}"
            )

    def test_active_count_matches_decision(self):
        # glob("*.md") is non-recursive so it does NOT count files inside extended-library/
        actual_active = len(list(COMMANDS_DIR.glob("*.md")))
        expected_active = len(self.promoted)
        self.assertEqual(
            actual_active,
            expected_active,
            f"Active count ({actual_active}) != expected promoted count ({expected_active}). "
            f"Expected RED until bd-cmdtop40-archive-execute-710 lands.",
        )

    def test_extended_library_count_matches_decision(self):
        actual_extended = len(list(EXTENDED_LIBRARY_DIR.glob("*.md")))
        expected_extended = len(self.extended)
        self.assertEqual(
            actual_extended,
            expected_extended,
            f"Extended library count ({actual_extended}) != expected count ({expected_extended}). "
            f"Expected RED until bd-cmdtop40-archive-execute-710 lands.",
        )

    def test_every_cross_library_reference_resolves_in_extended_library(self):
        # Post-migration these targets are invocable as /extended-library:<name>, NOT /<name>
        crossings: list[str] = []
        unresolved: set[str] = set()
        for name in sorted(self.promoted):
            cmd_file = COMMANDS_DIR / f"{name}.md"
            if not cmd_file.is_file():
                continue
            text = cmd_file.read_text(encoding="utf-8")
            for ref in sorted(extract_references_from_text(text)):
                if ref in self.extended and ref not in NON_COMMAND_TOKENS:
                    crossings.append(f"{name} -> /extended-library:{ref}")
                    if not (EXTENDED_LIBRARY_DIR / f"{ref}.md").is_file():
                        unresolved.add(ref)
        self.assertTrue(
            crossings,
            "Crossings must be non-empty; the accepted trade-off is real, and if empty "
            "the test has gone vacuous and must be revisited.",
        )
        self.assertEqual(
            sorted(unresolved),
            [],
            f"{len(unresolved)} of {len(crossings)} crossing references have no file in "
            f"{EXTENDED_LIBRARY_DIR}: {sorted(unresolved)}. "
            f"Expected RED until bd-cmdtop40-archive-execute-710 lands.",
        )

    def test_every_seed_command_still_active(self):
        self.assertEqual(
            len(SEED_COMMANDS), 27, f"SEED_COMMANDS must have 27 entries, got {len(SEED_COMMANDS)}"
        )
        missing_promoted = [s for s in sorted(SEED_COMMANDS) if s not in self.promoted]
        self.assertEqual(missing_promoted, [], f"Seed commands missing from promoted: {missing_promoted}")
        self.assertIn("innov", self.promoted, "'innov' must be in promoted set as forced 28th include")
        self.assertNotIn("innov", SEED_COMMANDS, "'innov' is a forced include, not a union seed")
        missing_files = [s for s in sorted(SEED_COMMANDS) if not (COMMANDS_DIR / f"{s}.md").is_file()]
        self.assertEqual(missing_files, [], f"Seed files missing from {COMMANDS_DIR}: {missing_files}")


if __name__ == "__main__":
    unittest.main()
