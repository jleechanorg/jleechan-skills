"""Group B reconciliation: every duplicate loose .md is archived, never hard-deleted.

"Zero duplicates" is satisfiable by `git rm`, which destroys recoverable content.
These tests close that loophole: files must land in _archived_loose_md_2026-08-23/
and stay reachable via `git log --all --follow` under their original path.
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ARCHIVE = REPO_ROOT / ".claude" / "skills" / "_archived_loose_md_2026-08-23"


def run(*argv):
    return subprocess.run(argv, cwd=REPO_ROOT, capture_output=True, text=True)


def test_no_duplicate_skill_names_remain():
    result = run(sys.executable, "scripts/skill_portability_scan.py", "--check-duplicates")
    assert result.returncode == 0, f"duplicates remain: {result.stderr.strip()}"


def test_archive_directory_documents_the_move():
    assert ARCHIVE.is_dir(), f"missing archive dir: {ARCHIVE}"
    assert (ARCHIVE / "README.md").is_file(), "archive dir needs a README.md rationale"


def test_archived_files_stay_recoverable_from_history():
    archived = sorted(p for p in ARCHIVE.glob("*.md") if p.name != "README.md")
    assert archived, f"no archived skill files under {ARCHIVE}"
    for path in archived[:5]:
        original = f".claude/skills/{path.name}"
        log = run("git", "log", "--all", "--follow", "--oneline", "--", original)
        assert log.stdout.strip(), f"{original} has no history; hard-deleted instead of git mv?"
