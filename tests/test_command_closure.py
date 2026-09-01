"""Contract test for scripts/compute_command_closure.py (bd-cmdtop40-closure-test-74g).

The closure calculator starts from a seed set of command names, scans each
seed's `.claude/commands/<name>.md` for genuine delegation references, and
iterates to a fixed point.

Precision philosophy is inherited from tests/test_swarm_references.py: a bare
`/word` sweep is NOT a reference detector. Real command files contain slash
tokens that are filesystem paths (`./install.sh`) or `/`-as-or separators
(`reviewer/subagent`), and a closure that follows those emits phantom nodes.
So both fixtures below use REAL repo content at HEAD, one asserting a genuine
reference IS followed and one asserting a false positive is NOT.
"""

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.compute_command_closure import (
    closure_to_json,
    compute_closure,
    extract_references_from_text,
)

COMMANDS_DIR = REPO_ROOT / ".claude" / "commands"

# Fixture A (TRUE POSITIVE), real content of .claude/commands/advice.md line 2:
#   description: Token-efficient second opinion — fans out a concurrent Codex
#   + Opus CLI primary pair plus /research, /extended-library:secondo, and
#   /web-advice. ...
# Prose delegation, and .claude/commands/research.md exists. Both /advice and
# /research are in the Active Core set, so neither is reachable only through
# .claude/commands/extended-library/, which the closure scanner does not scan.
GENUINE_SEED = "advice"
GENUINE_TARGET = "research"
NAMESPACED_TARGET = "extended-library:secondo"

# Fixture B (FALSE POSITIVES), real content of .claude/commands/f.md, whose
# phantom slash tokens are what this fixture exercises.
#   line 22:  **Prerequisite:** `./install.sh` once; ...
#   line 220: - a delegated reviewer/subagent outcome when available ...
# Both match a naive single-segment slash-token regex. Neither is a command:
# `/install` is a path fragment of `./install.sh`, `/reviewer` is `/` used as
# an "or" separator. Neither has a file under .claude/commands/.
PHANTOM_SEED = "f"
PHANTOM_TOKENS = {
    "install": "path fragment of `./install.sh`, not a delegation",
    "reviewer": "`/` as or-separator in `reviewer/subagent`, not a delegation",
}


class CommandClosureTest(unittest.TestCase):
    def setUp(self):
        self.seed_text = {}
        for seed in (GENUINE_SEED, PHANTOM_SEED):
            seed_file = COMMANDS_DIR / f"{seed}.md"
            self.assertTrue(seed_file.is_file(), f"seed command missing: {seed_file}")
            self.seed_text[seed] = seed_file.read_text(encoding="utf-8")

    def test_seed_file_still_contains_the_fixture_lines(self):
        # Guards the fixtures themselves: if a seed file is edited so these
        # lines are gone, this test must fail loudly rather than assert against
        # content that no longer exists.
        self.assertIn("/research", self.seed_text[GENUINE_SEED])
        self.assertIn("/skills/dark-factory/SKILL.md", self.seed_text[PHANTOM_SEED])
        candidates = extract_references_from_text(
            "Prerequisite: `./install.sh`; delegated reviewer/subagent outcome."
        )
        self.assertNotIn("install", candidates)
        self.assertNotIn("reviewer", candidates)

    def test_genuine_reference_is_pulled_into_closure(self):
        result = compute_closure(REPO_ROOT, [GENUINE_SEED])
        closure = result["closure"]
        self.assertIn(GENUINE_SEED, closure, "seed must be in its own closure")
        self.assertIn(
            GENUINE_TARGET,
            closure,
            f"/{GENUINE_SEED} genuinely delegates to `/{GENUINE_TARGET}` "
            f"(.claude/commands/{GENUINE_SEED}.md), so closure must include it",
        )
        self.assertIn(NAMESPACED_TARGET, closure)
        self.assertNotIn("secondo", result["rejected"])
        self.assertTrue(
            (COMMANDS_DIR / "extended-library" / "secondo.md").is_file()
        )

    def test_advice_direct_references_all_resolve_and_secondo_stays_namespaced(self):
        references = extract_references_from_text(self.seed_text[GENUINE_SEED])
        unresolved = []
        for name in sorted(references):
            if name.startswith("extended-library:"):
                path = COMMANDS_DIR / "extended-library" / f"{name.split(':', 1)[1]}.md"
            else:
                path = COMMANDS_DIR / f"{name}.md"
            if not path.is_file():
                unresolved.append(name)

        self.assertFalse(unresolved)
        self.assertIn(NAMESPACED_TARGET, references)
        self.assertFalse((COMMANDS_DIR / "secondo.md").exists())

    def test_false_positive_tokens_are_not_pulled_into_closure(self):
        closure = set(compute_closure(REPO_ROOT, [PHANTOM_SEED])["closure"])
        leaked = sorted(PHANTOM_TOKENS.keys() & closure)
        self.assertFalse(
            leaked,
            "closure followed non-delegation slash tokens: "
            + "; ".join(f"{t}: {PHANTOM_TOKENS[t]}" for t in leaked),
        )

    def test_every_closure_member_resolves_to_a_real_command_file(self):
        closure = compute_closure(REPO_ROOT, [GENUINE_SEED, PHANTOM_SEED])["closure"]
        missing = []
        for name in closure:
            if name.startswith("extended-library:"):
                path = COMMANDS_DIR / "extended-library" / f"{name.split(':', 1)[1]}.md"
            else:
                path = COMMANDS_DIR / f"{name}.md"
            if not path.is_file():
                missing.append(name)
        self.assertFalse(
            missing,
            f"closure emitted names with no .claude/commands/<name>.md: {missing}",
        )

    def test_closure_is_deterministic(self):
        seeds = [GENUINE_SEED, PHANTOM_SEED]
        first = closure_to_json(compute_closure(REPO_ROOT, seeds))
        second = closure_to_json(compute_closure(REPO_ROOT, seeds))
        self.assertEqual(
            first.encode("utf-8"),
            second.encode("utf-8"),
            "two closure runs on the same HEAD must be byte-identical JSON",
        )
        self.assertEqual(json.loads(first)["closure"], sorted(json.loads(first)["closure"]))


if __name__ == "__main__":
    unittest.main()
