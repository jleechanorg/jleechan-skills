import importlib
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

SKILLS_ROOT = REPO_ROOT / ".claude" / "skills"

BATCH3 = (
    "no-second-llm-calls",
    "org-runner-audit",
    "pr-description-format",
    "pr-efficiency-audit",
    "pre-cr-checklist",
    "repo-and-infra-locations",
    "repro-copy",
    "second-call-boundary",
)


@pytest.mark.parametrize("name", BATCH3)
def test_batch3_skill_is_proper(name):
    result = importlib.import_module("scripts.skill_portability_scan").scan(SKILLS_ROOT)
    assert name in result["proper"]
    assert name not in result["orphan"]
