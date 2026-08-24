"""Contract test: every slash-command/skill reference in swarm/SKILL.md resolves.

`.claude/skills/swarm/SKILL.md` names other commands (`/sidekick`, `/advice`, ...)
and skills (`~/.claude/skills/sidekick/SKILL.md`, ...) that must actually exist in
this repo so a reader following the playbook never hits a dead reference.

This test intentionally does NOT scan every bare `/word` token in the file and
assume each one is a command — that misclassifies things like `/tmp/<project-
slug>/...` (a path), `/rate-limit-options` (a Claude Code TUI modal, not a repo
command), or `pr-retro/` inside a longer `docs/plans/<retro>/pr-retro/` path.
Instead:

1. REFERENCED_COMMANDS / REFERENCED_SKILLS are a curated, reviewed list of the
   genuine references extracted from the file. Each is asserted to resolve to a
   real file in this repo.
2. A secondary sweep (SLASH_TOKEN_RE) finds every single-path-segment slash
   token in the file — backtick-wrapped OR bare in prose — and requires it to
   be accounted for by either the curated list above or NON_COMMAND_TOKENS
   (documented non-command tokens: paths, TUI modals, prose false-positives).
   An unrecognized token fails the test with a clear message — forcing a human
   to triage it into one of the two buckets — instead of silently passing or
   silently false-positiving.

   The sweep originally only matched backtick-wrapped tokens
   (`` `/foo` ``), which missed genuine prose references like `/research` and
   `/innov` in this file (found by Codex's automated review of PR #330,
   2026-07-14 — `/er` was independently found the same way during triage).
   Widened to also catch bare prose tokens via negative lookaround (no `/` or
   word-char immediately before/after), which in turn surfaces path-fragment
   false positives like `/pr` (from `pr-retro/`) or `/code` (from
   `code-quality/`) — those are triaged into NON_COMMAND_TOKENS below rather
   than narrowing the regex back down, since a wider net + an explicit
   denylist is more resistant to silently missing the next genuine reference
   than a narrower net that requires guessing every future backtick convention.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SWARM_SKILL = REPO_ROOT / ".claude" / "skills" / "swarm" / "SKILL.md"

# Genuine slash-command references found in swarm/SKILL.md, mapped to their
# expected command file under .claude/commands/.
REFERENCED_COMMANDS = {
    "/harness": "harness.md",
    "/swarm": "swarm.md",
    "/advice": "advice.md",
    "/sidekick": "sidekick.md",
    "/team-claude": "team-claude.md",
    "/history": "history.md",
    "/ms": "ms.md",
    "/learn": "learn.md",
    "/secondo": "secondo.md",
    "/research": "research.md",
    "/innov": "innov.md",
    "/er": "er.md",
    "/claw": "claw.md",
}

# Genuine skill references found in swarm/SKILL.md, mapped to their expected
# skill file under .claude/skills/.
REFERENCED_SKILLS = {
    "sidekick": ".claude/skills/sidekick/SKILL.md",
    "swarm": ".claude/skills/swarm/SKILL.md",
    "advice": ".claude/skills/advice/SKILL.md",
}

# Single-path-segment slash tokens that match the sweep regex but are NOT
# commands: filesystem paths, Claude Code built-in TUI surfaces, path
# fragments split out of a longer path, prose false-positives, etc. Document
# *why* each one is excluded so a future reader can re-triage if it changes.
NON_COMMAND_TOKENS = {
    "/tmp": "filesystem path prefix (/tmp/<project-slug>/...), not a command",
    "/rate-limit-options": "Claude Code built-in TUI modal, not a repo command",
    "/STATE": "mid-path segment from `/tmp/.../STATE.md`, not a command",
    "/workflows": "Claude Code built-in Workflow-tool run viewer UI surface, not a repo command file",
    "/roadmap": "directory path fragment from `~/roadmap`, not a command",
    "/pr": "path fragment from `docs/plans/<retro>/pr-retro/`, not a command",
    "/code": "path fragment from `.../code-quality/`, not a command",
    "/config": "path fragment from `~/.claude/teams/session-*/config.json`, not a command",
    "/no": "prose false-positive from 'main/no branch', not a command",
    "/team-claude-class": "prose descriptor ('the real /team-claude-class feature' = "
    "'a feature of the team-claude class'), not a literal command invocation",
    "/parallel": "`/` used as an 'or' separator in `agent()/parallel()/pipeline()` "
    "Workflow-tool API notation, not a command",
    "/pipeline": "same `agent()/parallel()/pipeline()` API notation as /parallel above",
}

# Regex: single path segment (no further `/` before or after), starts with a
# letter, not preceded by a word char or `/` (so it doesn't match mid-path
# segments like the second `/STATE` in `/tmp/x/STATE.md` — wait, STATE is
# still isolated by `/` on both sides there, hence NON_COMMAND_TOKENS above).
# Matches both backtick-wrapped (`` `/foo` ``) and bare prose (`/foo`) tokens.
SLASH_TOKEN_RE = re.compile(r"(?<![\w/])/([A-Za-z][A-Za-z0-9_-]*)(?![\w/])")


class SwarmReferencesResolveTest(unittest.TestCase):
    def setUp(self):
        self.assertTrue(
            SWARM_SKILL.is_file(), f"swarm SKILL.md missing at {SWARM_SKILL}"
        )
        self.text = SWARM_SKILL.read_text(encoding="utf-8")

    def test_referenced_commands_exist(self):
        commands_dir = REPO_ROOT / ".claude" / "commands"
        # Commands live flat when in the Active Core set, else under extended-library/.
        extended_dir = commands_dir / "extended-library"
        missing = []
        for ref, filename in REFERENCED_COMMANDS.items():
            if not (
                (commands_dir / filename).is_file()
                or (extended_dir / filename).is_file()
            ):
                missing.append(
                    f"{ref} -> .claude/commands/{filename} or "
                    f".claude/commands/extended-library/{filename}"
                )
        self.assertFalse(
            missing,
            "swarm/SKILL.md references commands with no matching file:\n"
            + "\n".join(missing),
        )

    def test_referenced_skills_exist(self):
        missing = []
        for name, relpath in REFERENCED_SKILLS.items():
            if not (REPO_ROOT / relpath).is_file():
                missing.append(f"{name} -> {relpath}")
        self.assertFalse(
            missing,
            "swarm/SKILL.md references skills with no matching file:\n"
            + "\n".join(missing),
        )

    def test_no_untriaged_slash_tokens(self):
        found = {f"/{m.group(1)}" for m in SLASH_TOKEN_RE.finditer(self.text)}
        known = set(REFERENCED_COMMANDS) | set(NON_COMMAND_TOKENS)
        untriaged = sorted(found - known)
        self.assertFalse(
            untriaged,
            "swarm/SKILL.md has slash-token(s) not triaged into "
            "REFERENCED_COMMANDS or NON_COMMAND_TOKENS in this test — add each "
            f"one to the correct bucket: {untriaged}",
        )

    def test_curated_command_list_is_still_referenced(self):
        # Guards the other direction: if a reference is deleted from the doc,
        # the curated list should shrink too, not silently keep asserting a
        # file exists for a reference that no longer appears anywhere.
        stale = [ref for ref in REFERENCED_COMMANDS if ref not in self.text]
        self.assertFalse(
            stale,
            "REFERENCED_COMMANDS lists reference(s) no longer present in "
            f"swarm/SKILL.md — remove from the curated list: {stale}",
        )


if __name__ == "__main__":
    unittest.main()
