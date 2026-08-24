"""RED contract test for scripts/rank_commands_repo_scoped.py (bd-cmdtop40-ranking-test-ohn).

The wrapper does not exist yet. It must consume a frozen `--json` snapshot from
count_command_usage_unified.py (shape: {"human": {cmd: count}, "agent": {...}, "total": {...}})
via `--input <file>`, drop any key without a real `.claude/commands/<key>.md` in THIS repo,
sort each list descending by count, truncate to 20, and print
{"top20_human": [...], "top20_agent": [...], "union": [...]} as JSON on stdout.

Importing the module must have no side effects, so the CLI belongs behind a __main__ guard.
"""

import importlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
COMMANDS_DIR = REPO_ROOT / ".claude" / "commands"
SCRIPT = REPO_ROOT / "scripts" / "rank_commands_repo_scoped.py"
MODULE = "scripts.rank_commands_repo_scoped"

# Real top-20 output from the raw scanner contains these; none has a file in this repo.
PHANTOM_KEYS = ("ready", "a", "document-standards")


def build_snapshot(tmp_path):
    """Realistic scanner snapshot: 25 real repo commands plus the known phantoms on top."""
    real = sorted(p.stem for p in COMMANDS_DIR.glob("*.md"))[:25]
    assert len(real) == 25, f"repo has too few commands to exercise the top-20 cut: {len(real)}"
    human = {key: 500 - i for i, key in enumerate(real)}
    agent = {key: 900 - 3 * i for i, key in enumerate(real)}
    for i, phantom in enumerate(PHANTOM_KEYS):
        human[phantom] = 10_000 - i
        agent[phantom] = 10_000 - i
    snapshot = {"human": human, "agent": agent, "total": {k: human[k] + agent[k] for k in human}}
    path = tmp_path / "usage_snapshot.json"
    path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    return path


class CommandRankingScopeTest(unittest.TestCase):
    def setUp(self):
        if str(REPO_ROOT) not in sys.path:
            sys.path.insert(0, str(REPO_ROOT))
        # Fails today with ModuleNotFoundError: No module named 'scripts.rank_commands_repo_scoped'
        importlib.import_module(MODULE)
        tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(tmp_dir.cleanup)
        self.snapshot = build_snapshot(Path(tmp_dir.name))

    def run_script(self):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--input", str(self.snapshot)],
            capture_output=True,
            cwd=str(REPO_ROOT),
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        return proc.stdout

    def test_union_entries_all_resolve_to_real_command_files(self):
        result = json.loads(self.run_script())
        missing = [k for k in result["union"] if not (COMMANDS_DIR / f"{k}.md").is_file()]
        self.assertEqual(missing, [], f"union contains commands with no file in this repo: {missing}")

    def test_top20_lists_are_capped_deduped_and_descending(self):
        result = json.loads(self.run_script())
        raw = json.loads(self.snapshot.read_text(encoding="utf-8"))
        for list_key, source_key in (("top20_human", "human"), ("top20_agent", "agent")):
            entries = result[list_key]
            self.assertLessEqual(len(entries), 20, f"{list_key} exceeds 20 entries")
            self.assertEqual(len(entries), len(set(entries)), f"{list_key} has duplicates")
            counts = [raw[source_key][k] for k in entries]
            self.assertEqual(counts, sorted(counts, reverse=True), f"{list_key} is not descending")

    def test_repeated_runs_on_frozen_snapshot_are_byte_identical(self):
        self.assertEqual(self.run_script(), self.run_script())


if __name__ == "__main__":
    unittest.main()
