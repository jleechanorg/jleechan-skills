"""The coordinator skill owns the one-turn judgment and send policy."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / '.claude/skills/dot-coordinator/SKILL.md'


class CoordinatorWorkflowTests(unittest.TestCase):
    def test_identity_and_account_binding_precede_any_send(self):
        text = SKILL.read_text()
        for phrase in ('--account <configured-key>', 'DOT_EXPECTED_IDENTITY_SHA256',
                       'authenticated identity', 'stop without sending'):
            self.assertIn(phrase, text)

    def test_ambiguous_send_is_reported_without_durable_hold(self):
        text = SKILL.read_text().lower()
        self.assertIn('do not retry or send a correction', text)
        self.assertIn('do read-only verification and return', text)
        self.assertIn('no durable record carries this uncertainty', text)
        self.assertIn('send nothing', text)

    def test_periodic_message_is_exact_and_submission_is_terminal(self):
        text = SKILL.read_text()
        outbound = text.split('## Periodic outbound message', 1)[1].split('## Workflow', 1)[0]
        expected = "Review the last four hours of this conversation for new requests, changes and cancellations. Check the owner's authorized private roadmap and canonical backlog at locations supplied through authorized private context for every older unfinished commitment. Preserve task IDs, priorities, owners, checkpoints, approvals, holds and STOPs. Through existing owners, take the next safe authorized step and recover stalled work without duplicate writers or exceeding the shared two-complex/two-short limit. Verify actual results and original execution timestamps; assignments and status claims are not progress. Keep unresolved work until verified completion or cancellation. Report meaningful progress, precise blockers and next actions concisely; skip unchanged status. This reminder grants no new execution, access, spending, merge or deployment authority."
        self.assertEqual([line[2:] for line in outbound.splitlines() if line.startswith('> ')], [expected])
        self.assertIn('Explicit read-only or do-not-send runs still send nothing', outbound)
        self.assertIn('An acknowledgment or changed wording does not authorize another submit', text)
        self.assertIn('do read-only verification and return', text)
        self.assertIn('no destination idempotency or exactly-once guarantee', text)
        self.assertIn('does not create or consume coordinator holds', text)

    def test_review_guidance_does_not_reintroduce_manual_stop(self):
        dot = (ROOT / '.claude/skills/dot/SKILL.md').read_text()
        coordinator = SKILL.read_text()
        # The coordinator STOP marker and per-profile flock were deleted 2026-10-20,
        # in the coordinator source and in the shared dot.sh transport.
        self.assertIn('there is no per-profile flock or coordinator STOP marker any more', dot)
        self.assertIn('`DOT_PROFILE_LOCKED` no longer exists', dot)
        self.assertIn('does not create or consume coordinator holds', coordinator)
        self.assertNotIn('set the coordinator STOP marker', dot)
        self.assertNotIn('dot.sh login` owns its own STOP lifecycle', dot)

    def test_coordinator_has_no_classifier_or_fallback(self):
        text = SKILL.read_text().lower()
        self.assertIn('without code-based routing', text)
        self.assertIn('automatic fallback', text)
        self.assertIn('account rotation', text)


if __name__ == '__main__':
    unittest.main()
