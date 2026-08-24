"""Contract test for command archival migration (bd-cmdtop40-migration-test-dhi).

Asserts the post-migration end state where:
1. Active commands in .claude/commands/ match the 94-command KEEP list.
2. Archived commands in archive/commands/ match PRE_EXISTING_ARCHIVED (51) + 145 ARCHIVE.
3. Zero active commands delegate to archived commands (reference closure preserved).
4. All 27 top-20 human / top-20 agent seed commands remain active.

This test is expected to be RED (failing on active and archive counts) until
bd-cmdtop40-archive-execute-710 executes the file moves.
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
ARCHIVE_DIR = REPO_ROOT / "archive" / "commands"
DECISION_DOC = REPO_ROOT / "archive" / "ARCHIVE-DECISION-2026-08-23.md"

# Count of command markdown files archived in prior PRs
PRE_EXISTING_ARCHIVED = 51

# 27 seed commands from top-20 human ∪ top-20 agent union (hard floor)
SEED_COMMANDS: tuple[str, ...] = (
    "advice", "green", "repro", "research", "ms", "claw", "history", "er",
    "linux", "f", "es", "web-advice", "browser", "skillify", "browserclaw",
    "auto", "wiki-search", "smoke", "roadmap", "levelup", "execute",
    "copilot", "fixpr", "nextsteps", "harness", "learn", "end2end-testing",
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
                if next_line.startswith("## "):
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
        cls.keep = _parse_decision_list(doc_text, "## KEEP list")
        cls.archive = _parse_decision_list(doc_text, "## ARCHIVE list")
        if len(cls.keep) != 94:
            raise ValueError(f"Expected 94 KEEP commands, parsed {len(cls.keep)}")
        if len(cls.archive) != 145:
            raise ValueError(f"Expected 145 ARCHIVE commands, parsed {len(cls.archive)}")

    def test_active_count_matches_decision(self):
        actual_active = len(list(COMMANDS_DIR.glob("*.md")))
        expected_active = len(self.keep)
        self.assertEqual(
            actual_active,
            expected_active,
            f"Active count ({actual_active}) != expected KEEP count ({expected_active}). "
            f"Expected RED until bd-cmdtop40-archive-execute-710 lands.",
        )

    def test_archive_count_matches_decision(self):
        actual_archived = len(list(ARCHIVE_DIR.glob("*.md")))
        expected_archived = PRE_EXISTING_ARCHIVED + len(self.archive)
        self.assertEqual(
            actual_archived,
            expected_archived,
            f"Archive count ({actual_archived}) != expected total ({expected_archived} = "
            f"{PRE_EXISTING_ARCHIVED} pre-existing + {len(self.archive)} newly archived). "
            f"Expected RED until bd-cmdtop40-archive-execute-710 lands.",
        )

    def test_zero_dangling_references_from_active_to_archived(self):
        dangling_edges: list[str] = []
        for name in sorted(self.keep):
            cmd_file = COMMANDS_DIR / f"{name}.md"
            if not cmd_file.is_file():
                continue
            text = cmd_file.read_text(encoding="utf-8")
            refs = extract_references_from_text(text)
            for ref in sorted(refs):
                if ref in self.archive and ref not in NON_COMMAND_TOKENS:
                    dangling_edges.append(f"{name} -> /{ref}")
        self.assertEqual(
            dangling_edges,
            [],
            f"Dangling references from active KEEP to ARCHIVE: {dangling_edges}",
        )

    def test_every_seed_command_still_active(self):
        self.assertEqual(
            len(SEED_COMMANDS),
            27,
            f"SEED_COMMANDS must have exactly 27 entries, got {len(SEED_COMMANDS)}",
        )
        missing_from_keep = [s for s in sorted(SEED_COMMANDS) if s not in self.keep]
        self.assertEqual(
            missing_from_keep,
            [],
            f"Seed commands missing from KEEP set: {missing_from_keep}",
        )
        missing_files = [
            s for s in sorted(SEED_COMMANDS) if not (COMMANDS_DIR / f"{s}.md").is_file()
        ]
        self.assertEqual(
            missing_files,
            [],
            f"Seed command files missing from {COMMANDS_DIR}: {missing_files}",
        )


if __name__ == "__main__":
    unittest.main()
