"""Batch 2 of the skill portability migration (bd-11g.15).

Each name below is still a loose <name>.md and must become a
<name>/SKILL.md directory with name/description frontmatter.
"""

import importlib
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

SKILLS_ROOT = REPO_ROOT / ".claude" / "skills"

BATCH2 = (
    "evidence-coverage",
    "evolve_loop",
    "fetch-x-tweet",
    "field-ownership-contracts",
    "game-evidence-reviewer",
    "harness-guardrails",
    "hermes-models",
    "llm-testing",
)


@pytest.mark.parametrize("name", BATCH2)
def test_batch2_skill_is_proper(name):
    result = importlib.import_module("scripts.skill_portability_scan").scan(SKILLS_ROOT)
    assert name in result["proper"]
    assert name not in result["orphan"]
