"""Contract tests for the active-core and extended-library command boundary."""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

COMMANDS_DIR = REPO_ROOT / ".claude" / "commands"
EXTENDED_LIBRARY_DIR = COMMANDS_DIR / "extended-library"
PLUGIN_COMMANDS_GLOB = "plugins/*/commands/*.md"

# 26 seed commands from top-20 human ∪ top-20 agent union, less the retired /f (hard floor; 'innov' is an extra include)
SEED_COMMANDS: tuple[str, ...] = (
    "advice", "auto", "browser", "browserclaw", "claw", "copilot",
    "end2end-testing", "er", "es", "execute", "fixpr", "green",
    "harness", "history", "learn", "levelup", "linux", "ms", "nextsteps",
    "repro", "research", "roadmap", "skillify", "smoke", "web-advice",
    "wiki-search",
)


class CommandArchiveMigrationTest(unittest.TestCase):
    def test_every_cross_library_reference_resolves_in_extended_library(self):
        """Every explicitly namespaced reference must have an installed command file."""
        crossings: list[tuple[Path, str]] = []
        unresolved: set[str] = set()
        for cmd_file in COMMANDS_DIR.glob("*.md"):
            text = cmd_file.read_text(encoding="utf-8")
            for ref in re.findall(r"/extended-library:([A-Za-z0-9_.-]+)", text):
                crossings.append((cmd_file, ref))
                if not (EXTENDED_LIBRARY_DIR / f"{ref}.md").is_file():
                    unresolved.add(ref)
        self.assertTrue(
            crossings,
            "Namespaced command references must remain covered.",
        )
        self.assertEqual(
            sorted(unresolved),
            [],
            f"Namespaced commands absent from "
            f"{EXTENDED_LIBRARY_DIR}: {sorted(unresolved)}. "
        )

    def test_every_seed_command_still_active(self):
        self.assertEqual(
            len(SEED_COMMANDS), 26, f"SEED_COMMANDS must have 26 entries, got {len(SEED_COMMANDS)}"
        )
        # A seed command stays active when it is installed from the default export or
        # from an opt-in plugin whose skill it dispatches to; /levelup moved into the
        # worldarchitect plugin with its skill, so the export path alone is not the
        # whole active surface.
        active = {p.stem for p in COMMANDS_DIR.glob("*.md")}
        active |= {p.stem for p in REPO_ROOT.glob(PLUGIN_COMMANDS_GLOB)}
        missing_files = [s for s in sorted(SEED_COMMANDS) if s not in active]
        self.assertEqual(missing_files, [], f"Seed commands missing from the active surface: {missing_files}")


if __name__ == "__main__":
    unittest.main()
