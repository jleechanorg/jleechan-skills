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

from scripts.compute_command_closure import closure_to_json, compute_closure

COMMANDS_DIR = REPO_ROOT / ".claude" / "commands"

# Fixture A (TRUE POSITIVE), real content of .claude/commands/f.md line 10:
#   Shortcut for `/factory` oriented toward **full production loops**. The
# Backtick-wrapped, prose delegation, and .claude/commands/factory.md exists.
SEED = "f"
GENUINE_TARGET = "factory"

# Fixture B (FALSE POSITIVES), real content of .claude/commands/f.md:
#   line 22:  **Prerequisite:** `./install.sh` once; ...
#   line 220: - a delegated reviewer/subagent outcome when available ...
# Both match a naive single-segment slash-token regex. Neither is a command:
# `/install` is a path fragment of `./install.sh`, `/reviewer` is `/` used as
# an "or" separator. Neither has a file under .claude/commands/.
PHANTOM_TOKENS = {
    "install": "path fragment of `./install.sh`, not a delegation",
    "reviewer": "`/` as or-separator in `reviewer/subagent`, not a delegation",
}


class CommandClosureTest(unittest.TestCase):
    def setUp(self):
        seed_file = COMMANDS_DIR / f"{SEED}.md"
        self.assertTrue(seed_file.is_file(), f"seed command missing: {seed_file}")
        self.seed_text = seed_file.read_text(encoding="utf-8")

    def test_seed_file_still_contains_the_fixture_lines(self):
        # Guards the fixtures themselves: if f.md is edited so these lines are
        # gone, this test must fail loudly rather than assert against content
        # that no longer exists.
        self.assertIn("`/factory`", self.seed_text)
        self.assertIn("`./install.sh`", self.seed_text)
        self.assertIn("reviewer/subagent", self.seed_text)

    def test_genuine_reference_is_pulled_into_closure(self):
        closure = compute_closure(REPO_ROOT, [SEED])["closure"]
        self.assertIn(SEED, closure, "seed must be in its own closure")
        self.assertIn(
            GENUINE_TARGET,
            closure,
            f"/{SEED} genuinely delegates to `/{GENUINE_TARGET}` "
            f"(.claude/commands/{SEED}.md), so closure must include it",
        )

    def test_false_positive_tokens_are_not_pulled_into_closure(self):
        closure = set(compute_closure(REPO_ROOT, [SEED])["closure"])
        leaked = sorted(PHANTOM_TOKENS.keys() & closure)
        self.assertFalse(
            leaked,
            "closure followed non-delegation slash tokens: "
            + "; ".join(f"{t}: {PHANTOM_TOKENS[t]}" for t in leaked),
        )

    def test_every_closure_member_resolves_to_a_real_command_file(self):
        closure = compute_closure(REPO_ROOT, [SEED])["closure"]
        missing = [n for n in closure if not (COMMANDS_DIR / f"{n}.md").is_file()]
        self.assertFalse(
            missing,
            f"closure emitted names with no .claude/commands/<name>.md: {missing}",
        )

    def test_closure_is_deterministic(self):
        first = closure_to_json(compute_closure(REPO_ROOT, [SEED]))
        second = closure_to_json(compute_closure(REPO_ROOT, [SEED]))
        self.assertEqual(
            first.encode("utf-8"),
            second.encode("utf-8"),
            "two closure runs on the same HEAD must be byte-identical JSON",
        )
        self.assertEqual(json.loads(first)["closure"], sorted(json.loads(first)["closure"]))


if __name__ == "__main__":
    unittest.main()
