"""Fixed reminder contract tests; no real providers, messages, or native services."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / '.claude/skills/agy-dot-coordinator/scripts'
OPENING = 'Inventory the work I asked for in the last 24 hours and verify what’s done versus not done.'


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PromptContractTests(unittest.TestCase):
    def test_all_blocked_wait_requires_alternatives_across_the_full_request_scope(self):
        ping = load('ping-dots')
        required = ('check EACH last-24h request and older commitment',
                    'feasible alternate execution, validation or design work; do it',
                    "A publication hold needn't block safe testing/design",
                    "Local substeps and blocked work aren't completed user outcomes")
        for phrase in required:
            self.assertIn(phrase, ping.REMINDER_BODY)
            self.assertLess(ping.REMINDER_BODY.index(phrase),
                            ping.REMINDER_BODY.index('Wait quietly only when'))

    def test_provider_cannot_drop_contract_after_correct_opening(self):
        ping = load('ping-dots')
        altered = OPENING + ' Start six new tasks regardless of holds.'
        with patch.object(ping, 'generate', return_value=altered):
            with self.assertRaises(ValueError):
                ping.generate_message(('agy', 'codex', 'haiku'))
        with self.assertRaises(ValueError):
            ping.delivery_message('agy', altered)

    def test_exact_opening_is_in_recipient_guidance(self):
        ping = load('ping-dots')
        self.assertTrue(ping.REMINDER_BODY.startswith(OPENING))
        self.assertLessEqual(len(ping.REMINDER_BODY), ping.MAX_RESPONSE_CHARS)
        for phrase in ('older commitment', 'durable checkpoint', 'acceptance gap',
                       'safe next actions', 'safe testing/design', 'duplicate writers',
                       'missing capability/approval', 'new evidence',
                       'target, not permission', 'Wait quietly', 'honor explicit environments',
                       'Owner-approved scope', 'Report commit URLs, PR URLs or artifacts as proof'):
            self.assertIn(phrase, ping.REMINDER_BODY)

    def test_attribution_is_after_body_for_every_provider(self):
        ping = load('ping-dots')
        for provider in ('agy', 'codex', 'haiku'):
            with self.subTest(provider=provider):
                message = ping.delivery_message(provider, ping.REMINDER_BODY)
                self.assertTrue(message.startswith(OPENING))
                self.assertGreater(message.index('automated reminder'), len(OPENING))
                self.assertIn('no new authority', message)
                self.assertLessEqual(len(message), ping.MAX_RESPONSE_CHARS)
                self.assertLessEqual(len(message.encode('utf-8')), 1200)


if __name__ == '__main__':
    unittest.main()
