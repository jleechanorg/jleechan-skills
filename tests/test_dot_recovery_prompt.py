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

    def test_payload_line_carries_captured_minute_and_machine(self):
        text = SKILL.read_text()
        rule = " ".join(text.split('## Payload timestamp and sender', 1)[1].split('## One active sender', 1)[0].split())
        self.assertIn('date -u +%Y-%m-%dT%H:%MZ', rule)
        self.assertIn('COORDINATOR_HOST_LABEL', rule)
        self.assertIn('otherwise `hostname -s`', rule)
        self.assertIn('Sent: 2026-10-30T21:40Z UTC from primary-host', rule)
        self.assertIn('^Sent: [0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}Z UTC from [A-Za-z0-9._-]{1,64}$', rule)
        self.assertIn('that regex matches the complete line', rule)
        self.assertIn('send nothing and report that blocker', rule)
        step6 = " ".join(text.split('6. **Submit at most once', 1)[1].split('7. **Report', 1)[0].split())
        self.assertIn('prefixed by exactly one payload timestamp-and-sender line', step6)

    def test_fixed_priority_decides_the_floor_without_a_lease(self):
        text = SKILL.read_text()
        rule = " ".join(text.split('## One active sender (host standdown)', 1)[1].split('## Exact-duplicate window', 1)[0].split())
        self.assertIn('Ownership is **fixed priority**, not recency', rule)
        self.assertIn('COORDINATOR_HOST_PRIORITY', rule)
        self.assertIn('COORDINATOR_HOST_PRIORITIES', rule)
        self.assertIn('unknown-peer: <label>', rule)
        self.assertIn('COORDINATOR_TAKEOVER_HOURS', rule)
        self.assertIn('1 is primary', rule)
        self.assertIn('If any message from a host with a *lower* priority number than this host is younger than the takeover window', rule)
        self.assertIn('standdown: <machine>, <age> (priority <n> active)', rule)
        self.assertIn('Same-or-lower-priority messages never block', rule)
        self.assertIn('floor: own, priority <n>', rule)
        self.assertIn('takeover: <machine> silent <age>', rule)
        self.assertIn("own label never block it", rule)
        self.assertIn('unknown: it never triggers a standdown', rule)
        self.assertIn('reload the conversation', rule)
        self.assertIn('clear only the text this invocation typed', rule)
        self.assertIn('standdown-late: <machine>, <age>', rule)
        self.assertIn('3 to 12 minutes', rule)
        self.assertIn('visibility rule, not an atomic reservation', rule)
        self.assertNotIn('newest speaker', rule.lower())

    def test_duplicate_is_body_based_and_the_window_is_time_measured(self):
        text = SKILL.read_text()
        rule = " ".join(text.split('## Exact-duplicate window', 1)[1].split('## Reviews and migration', 1)[0].split())
        self.assertIn('the **payload body** is everything below the `Sent:` line', rule)
        self.assertIn('A duplicate is an earlier message **from this same machine**', rule)
        self.assertIn("Another host's copy of the same body is not this", rule)
        self.assertIn('the stamp is what makes that copy\'s age readable', rule)
        self.assertNotIn('same timestamp line and same body', rule)
        self.assertIn('only while it is **less than 10 minutes old**', rule)
        self.assertIn('A copy with no `Sent:` line, an unparseable stamp or a stamp in the future counts as older than the window and does not block', rule)
        self.assertIn('a reply to it, an acknowledgment or newer Dot activity never withholds the next scheduled nudge', rule)
        self.assertIn('Different body wording is never a duplicate', rule)
        self.assertIn('smaller than the shortest configured gap between one account\'s runs', rule)
        step4 = " ".join(text.split('4. **Stay a reminder.**', 1)[1].split('5. **Inspect', 1)[0].split())
        self.assertIn('the last 20 rendered messages in either mode', step4)

    def test_coordinator_has_no_classifier_or_fallback(self):
        text = SKILL.read_text().lower()
        self.assertIn('without code-based routing', text)
        self.assertIn('automatic fallback', text)
        self.assertIn('account rotation', text)


if __name__ == '__main__':
    unittest.main()
