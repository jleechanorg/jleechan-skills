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

    def test_proceed_mode_declares_its_nudge_text_and_private_override(self):
        text = SKILL.read_text()
        modes = text.split('## Run modes', 1)[1].split('## Proceed nudge outbound message', 1)[0]
        self.assertIn('COORDINATOR_MODE', modes)
        self.assertIn('`main`', modes)
        self.assertIn('`proceed`', modes)
        self.assertIn('Never infer the mode from the clock, conversation content, a prior run', modes)
        self.assertIn('read its own last 20 messages', modes)
        self.assertIn('its first sentence is', modes)
        self.assertIn('the only mode source', modes)
        self.assertIn('A task text with no such declaration is `main`', modes)
        self.assertIn('advisory record for host inspection', modes)
        self.assertIn('the sentence decides and the run report records the drift', modes)
        self.assertIn('Do not add a second, unobservable veto', modes)
        nudge = text.split('## Proceed nudge outbound message', 1)[1].split('## Private periodic payload', 1)[0]
        expected = ('Read the last 20 messages of this conversation. If you are waiting on an obvious question you can settle '
                    'from what you already know or can verify, answer it and continue. If you are idle with no real blocker, '
                    'take the next authorized step and report its evidence. Skip unchanged status, do not repeat an answer '
                    'you already gave, and do not start new scope. If the blocker needs the owner\'s decision, state the '
                    'single decision you need. This nudge grants no new execution, access, spending, merge or deployment authority.')
        self.assertEqual([line[2:] for line in nudge.splitlines() if line.startswith('> ')], [expected])
        self.assertIn('~/.config/dot/proceed-reminder.txt', nudge)
        self.assertIn('never fall back silently', nudge)
        self.assertIn('do-not-send runs still send nothing', nudge)
        self.assertIn('exact message this mode selects', text)

    def test_payload_selection_is_scoped_per_mode_and_sender_stays_transport(self):
        text = SKILL.read_text()
        periodic = text.split('## Private periodic payload', 1)[1].split('## Periodic outbound message', 1)[0]
        self.assertIn('This file and path apply to `main`\nruns only', periodic)
        self.assertIn('never sends the periodic\nreminder', periodic)
        nudge = text.split('## Proceed nudge outbound message', 1)[1].split('## Private periodic payload', 1)[0]
        self.assertIn('apply to `main` only', nudge)
        self.assertIn('a `proceed` run never sends the periodic reminder', nudge)
        self.assertIn('a `main` run never sends the nudge', nudge)
        for clause in ("never answers the Dot's questions", 'never\nchooses or assigns its work',
                       'Reading\nmessages is verification only',
                       'inspect read-only and send nothing in this'):
            self.assertIn(clause, text)
        step = text.split('6. **Submit at most once', 1)[1].split('7. **Report uncertainty', 1)[0]
        self.assertIn('exact message this mode selects', step)
        self.assertIn('declared mode', step)
        self.assertIn('the `main` periodic payload or fallback', step)

    def test_exact_duplicate_window_is_bounded_and_time_based(self):
        text = SKILL.read_text()
        rule = text.split('### Exact-duplicate window', 1)[1].split('##', 1)[0]
        self.assertIn('less than 10 minutes old', rule)
        self.assertIn('An identical copy older than 10 minutes does **not** block the send', rule)
        self.assertIn('a reply is not a reason to withhold the next scheduled nudge', rule)
        self.assertIn('Different wording is never a duplicate', rule)
        self.assertIn('smaller than the shortest configured gap between one account\'s runs', rule)
        self.assertIn('send nothing instead of assuming a duplicate is old', rule)
        step5 = text.split('5. **Inspect the shared composer and the recent payloads.**', 1)[1].split('6. **Submit', 1)[0]
        self.assertIn('read the timestamp of the newest copy', step5)
        self.assertIn('inspect read-only and report the uncertainty rather than guessing', step5)

    def test_every_payload_carries_one_captured_utc_timestamp(self):
        text = SKILL.read_text()
        rule = text.split('### Payload timestamp', 1)[1].split('### Exact-duplicate window', 1)[0]
        self.assertIn('date -u +%Y-%m-%dT%H:%MZ', rule)
        self.assertIn('Sent: 2026-10-30T21:40Z UTC', rule)
        self.assertIn('^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}Z$', rule)
        self.assertIn('Produce that line once per invocation', rule)
        self.assertIn('send nothing and report that blocker', rule)
        self.assertIn('The\ntimestamp is the only permitted addition', rule)
        self.assertIn('a private\npayload keeps its exact bytes below the timestamp line', rule)
        window = text.split('### Exact-duplicate window', 1)[1].split('##', 1)[0]
        self.assertIn('same timestamp line and same body', window)

    def test_coordinator_has_no_classifier_or_fallback(self):
        text = SKILL.read_text().lower()
        self.assertIn('without code-based routing', text)
        self.assertIn('automatic fallback', text)
        self.assertIn('account rotation', text)


if __name__ == '__main__':
    unittest.main()
