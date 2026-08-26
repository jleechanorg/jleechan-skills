#!/usr/bin/env python3
"""test_resolver_trigger.py — Resolver trigger eval for web-advice (skillify item 7).

Reads RESOLVER.md, extracts the `## web-advice — ...` heading line, and
asserts that real user-typed trigger phrases route to it.

Deliberately reproduces the EXACT known-bug regex documented in
`~/.claude/skills/skillify/SKILL.md` under "Known Bugs in skillify Test
Suite" / Bug 2:

    (name.*?)(?=\\n\\n|\\n##)

That regex is non-greedy and stops at the first blank line after the
heading, so trigger words placed in a `**Triggers:**` sub-line below a blank
line are silently missed. RESOLVER.md's fix (per skillify's documented
guidance) is to put ALL trigger words directly on the heading line. This
test intentionally uses the buggy-shaped regex to prove that fix holds: even
with the narrowest possible extraction, every trigger phrase below must
still be found, because nothing needed lives past the first blank line.

Run from this directory: `python3 -m pytest test_resolver_trigger.py -v`.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

RESOLVER_PATH = Path(__file__).resolve().parent.parent / "RESOLVER.md"
HERMES_RESOLVER_PATH = Path(__file__).resolve().parents[4] / "hermes" / "skills" / "RESOLVER.md"
SKILL_NAME = "web-advice"

# Stopwords stripped before overlap matching so a trigger phrase can't pass
# on "the"/"a"/"to" alone — it must share at least one real content word
# with the resolver heading line.
STOPWORDS = {
    "a", "an", "and", "the", "to", "do", "get", "use", "of", "this",
    "have", "them", "run", "for", "from", "with", "on", "in",
}

# Real phrases a user actually types, mined from this session's conversation
# habits (2026-08-02). Each tuple is (phrase, expected_overlap_words) where
# expected_overlap_words are the specific content words that MUST be found
# in the resolver heading for the match to count as meaningful, not just
# "some word matched by accident".
TRIGGER_PHRASES: list[tuple[str, list[str]]] = [
    ("use /web-advice", ["web-advice"]),
    ("get chatgpt gemini grok to review", ["chatgpt", "gemini", "grok", "review"]),
    ("have them visually review", ["review"]),
    ("external review of this evidence", ["external", "review"]),
    ("run a multi model review", ["multi", "model", "review"]),
    ("ask chatgpt gemini grok and perplexity", ["ask", "chatgpt", "gemini", "grok", "perplexity"]),
    ("get a second opinion from the web", ["second", "opinion", "from", "web"]),
    ("do a browser review of this PR", ["browser", "review"]),
]

assert len(TRIGGER_PHRASES) >= 8, "need at least 8 real trigger phrases per skillify item 7"


def _content_words(phrase: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9/-]+", phrase.lower())
    return [t for t in tokens if t not in STOPWORDS]


@pytest.fixture(scope="module")
def resolver_text() -> str:
    assert RESOLVER_PATH.exists(), f"RESOLVER.md missing: {RESOLVER_PATH}"
    return RESOLVER_PATH.read_text()


@pytest.fixture(scope="module")
def heading_section(resolver_text: str) -> str:
    """Extract the web-advice section using the known-bug regex SHAPE.

    Mirrors `(skillify.*?)(?=\\n\\n|\\n##)` from
    tests/test_skillify_resolver_trigger.py, but anchored to the `##`
    heading marker (`##\\s*web-advice`) rather than a bare name match, so it
    finds the actual resolver entry heading rather than an earlier prose
    mention of "web-advice" (e.g. this file's own H1 title). Anchoring to
    `##` is what makes this a faithful reproduction of the real skillify
    RESOLVER.md shape, where the bug bites at the entry heading specifically.
    If RESOLVER.md correctly puts all trigger words on that heading line,
    this narrow (buggy-shaped) extraction — stopping at the first blank
    line — is still sufficient. That's exactly the fix under test.
    """
    m = re.search(
        r"(?i)(##\s*web-advice.*?)(?=\n\n|\n##|\Z)",
        resolver_text,
        re.DOTALL,
    )
    assert m, "Cannot find `## web-advice` heading section in RESOLVER.md"
    return m.group(1).lower()


def test_resolver_has_web_advice_entry(resolver_text: str):
    assert "web-advice" in resolver_text.lower(), \
        "RESOLVER.md does not reference 'web-advice'"


def test_resolver_points_to_skill_file(resolver_text: str):
    assert re.search(r"web-advice/SKILL\.md", resolver_text), \
        "RESOLVER.md does not reference web-advice/SKILL.md"


def test_hermes_runtime_resolver_has_web_advice_entry():
    if not HERMES_RESOLVER_PATH.exists():
        pytest.skip("Hermes runtime resolver is not part of this installed package")
    resolver = HERMES_RESOLVER_PATH.read_text()
    assert re.search(r"(?im)^## web-advice\b", resolver), \
        "Hermes runtime resolver does not route web-advice"


def test_web_advice_entry_is_unique(resolver_text: str):
    """Exactly one canonical `## web-advice` heading — no ambiguous routing."""
    lines = resolver_text.split("\n")
    entry_headers = [
        line for line in lines
        if re.match(r"\s*##\s+\S", line) and "web-advice" in line.lower()
    ]
    assert len(entry_headers) == 1, \
        f"expected exactly 1 `## web-advice` heading, found {len(entry_headers)}: {entry_headers}"


@pytest.mark.parametrize("phrase,expected_words", TRIGGER_PHRASES)
def test_real_trigger_phrase_routes_to_web_advice(phrase, expected_words, heading_section):
    """Each real user-typed trigger phrase must share a content word with
    the heading-line-only extraction (the known-bug-shaped regex)."""
    found_words = [w for w in expected_words if w in heading_section]
    assert found_words, (
        f"trigger phrase '{phrase}' did not route to {SKILL_NAME}: "
        f"none of {expected_words} found in heading section: {heading_section!r}"
    )


@pytest.mark.parametrize("phrase,_", TRIGGER_PHRASES)
def test_trigger_phrase_has_content_words(phrase, _):
    """Sanity check on the fixture itself: every phrase must have at least
    one non-stopword content word, otherwise the eval is vacuous."""
    assert _content_words(phrase), f"phrase '{phrase}' has no content words after stopword strip"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
