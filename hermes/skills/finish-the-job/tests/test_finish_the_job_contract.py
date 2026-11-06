"""Unit tests for the finish-the-job skill contract.

These tests assert:
- SKILL.md is valid YAML frontmatter
- Required sections are present (Contract, Phases, Anti-patterns, Related skills)
- Trigger phrases in the YAML match the user's actual phrasing (verified against the
  source message from 2026-06-19)
- The 4 end-state proof-artifact types are all documented
- The 5 anti-patterns are all present and named
- Cross-references to companion skills are valid (file exists)
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import yaml

SKILL_DIR = Path(__file__).resolve().parent.parent
SKILL_MD = SKILL_DIR / "SKILL.md"
# Test path: prefer HERMES_PROD_SKILLS env var, fall back to $HERMES_HOME/skills,
# fall back to $HOME/.hermes_prod/skills. (CodeRabbit MAJOR: hardcoded
# $HOME broke portability for any other developer.)
def _resolve_hermes_prod_skills() -> Path:
    if env := os.environ.get("HERMES_PROD_SKILLS"):
        return Path(env)
    if home := os.environ.get("HERMES_HOME"):
        return Path(home) / "skills"
    return Path.home() / ".hermes_prod" / "skills"


HERMES_PROD_SKILLS = _resolve_hermes_prod_skills()


def load_frontmatter() -> dict:
    text = SKILL_MD.read_text()
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert m, "SKILL.md must start with YAML frontmatter delimited by ---"
    return yaml.safe_load(m.group(1))


def load_body() -> str:
    text = SKILL_MD.read_text()
    m = re.match(r"^---\n.*?\n---\n(.*)$", text, re.DOTALL)
    return m.group(1)


# ── 1. Frontmatter shape ────────────────────────────────────────────────────


def test_frontmatter_has_required_keys():
    fm = load_frontmatter()
    for key in ("name", "description", "triggers", "related_skills"):
        assert key in fm, f"frontmatter missing required key: {key}"


def test_frontmatter_name_is_finish_the_job():
    assert load_frontmatter()["name"] == "finish-the-job"


def test_frontmatter_has_at_least_10_triggers():
    triggers = load_frontmatter()["triggers"]
    assert isinstance(triggers, list)
    assert len(triggers) >= 10, f"need >=10 trigger phrases, got {len(triggers)}"


# ── 2. Trigger coverage (the user's actual phrasing from 2026-06-19) ────────


def test_trigger_covers_users_actual_phrasing():
    """The user's verbatim phrases from 2026-06-19 must route to this skill."""
    fm = load_frontmatter()
    triggers_lower = [t.lower() for t in fm["triggers"]]

    user_phrases = [
        "finish the job",
        "drive to conclusion",
        "don't stop halfway",
        "hands off",
        "fullsend",
        "stalled thread",
        "work started but didn't finish",
        "skillify hermes",
        "make hermes hands off",
        "take it all the way",
    ]
    for phrase in user_phrases:
        assert any(phrase in t for t in triggers_lower), (
            f"trigger phrase '{phrase}' (from user message) not covered by triggers: {triggers_lower}"
        )


# ── 3. Required body sections ───────────────────────────────────────────────


def test_body_has_contract_section():
    body = load_body()
    assert "## Contract" in body, "missing '## Contract' section"


def test_body_has_phases_section():
    body = load_body()
    assert "## Phases" in body, "missing '## Phases' section"


def test_body_has_anti_patterns_section():
    body = load_body()
    assert "## Anti-patterns" in body, "missing '## Anti-patterns' section"


def test_body_has_related_skills_section():
    body = load_body()
    assert "## Related skills" in body or "## Related Skills" in body, (
        "missing '## Related skills' section"
    )


# ── 4. End-state proof-artifact coverage ─────────────────────────────────────


def test_all_four_end_states_documented():
    body = load_body()
    required = [
        "Green PR merged",
        "PR open with green CI",
        "Local state change verified",
        "Dry-run to local machine",
    ]
    for state in required:
        assert state in body, f"end-state '{state}' not documented in Contract"


def test_anti_patterns_enumerated():
    body = load_body()
    # 5 anti-patterns documented in the SKILL.md Anti-patterns section.
    # Match the actual wording in the skill body, not paraphrased.
    required_patterns = [
        "I started the worker",  # anti-pattern #1
        "want me to ship it",  # anti-pattern #2 (design-proposal)
        "want me to push",  # anti-pattern #3 (local-commit-ask)
        "Tests pass locally",  # anti-pattern #4 (silent PR open)
        "Investigation complete",  # anti-pattern #5
        "asked AO to spawn a worker",  # anti-pattern #6 (ack-and-walk-away)
    ]
    for p in required_patterns:
        assert p in body, f"anti-pattern '{p}' not enumerated in body"


# ── 5. Cross-references resolve ─────────────────────────────────────────────


def test_related_skills_exist_on_disk():
    """Each related skill in the YAML frontmatter resolves to an existing SKILL.md.
    Skills can live at root, under workflow/, or under software-development/.
    """
    fm = load_frontmatter()
    related = fm["related_skills"]
    for name in related:
        candidates = [
            HERMES_PROD_SKILLS / name / "SKILL.md",
            HERMES_PROD_SKILLS / "workflow" / name / "SKILL.md",
            HERMES_PROD_SKILLS / "software-development" / name / "SKILL.md",
            HERMES_PROD_SKILLS / "devops" / name / "SKILL.md",
            HERMES_PROD_SKILLS / "hermes" / name / "SKILL.md",
        ]
        assert any(p.exists() for p in candidates), (
            f"related skill '{name}' not found at any of: {[str(p) for p in candidates]}"
        )


def test_spec_step_routes_to_write_goal():
    """Phase 1 specs come from `write-goal`; the retired /fs and /f routes stay gone."""
    body = load_body()
    assert "write-goal" in load_frontmatter().get("related_skills", [])
    assert "### Phase 1 — Spec first (`write-goal`)" in body
    assert "`/fs`" not in body and "`/f`" not in body


# ── 6. The user's verbatim rule is quoted ───────────────────────────────────


def test_users_rule_is_quoted():
    body = load_body()
    # The exact phrasing from the user's 2026-06-19 message
    assert "correct but misinterpret is fine" in body, (
        "user's verbatim rule 'correct but misinterpret is fine' must be quoted "
        "in the skill body so future agents cannot silently drop it"
    )


# ── 7. No follow-up question language ───────────────────────────────────────


def test_no_open_follow_up_question_in_contract():
    body = load_body()
    # The contract explicitly forbids "want me to X?" follow-ups.
    assert "want me to" in body, "Contract must explicitly forbid 'want me to' follow-ups"


if __name__ == "__main__":
    # Manual run: print pass/fail per test
    import unittest

    suite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
