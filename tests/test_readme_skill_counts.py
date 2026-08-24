"""README's skill-count sentence must track the live scanner, not a stale literal."""

import importlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

SKILLS_ROOT = REPO_ROOT / ".claude" / "skills"
README = REPO_ROOT / "README.md"
STALE = "129 reference docs"


def test_readme_skill_count_matches_scanner():
    text = README.read_text(encoding="utf-8")
    proper = len(importlib.import_module("scripts.skill_portability_scan").scan(SKILLS_ROOT)["proper"])
    assert STALE not in text, f"README.md still contains the stale count string {STALE!r}"
    assert f"{proper} skill" in text, f"README.md does not state the live proper count ({proper} skill directories)"
