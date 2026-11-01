"""Portable routing contracts; no live Slack or gateway calls."""
from pathlib import Path
import re
import unittest
ROOT=Path(__file__).resolve().parents[1]
class HermesRoutingContract(unittest.TestCase):
    def test_command_is_thin_pointer(self):
        text=(ROOT/'.claude/commands/extended-library/hermes.md').read_text()
        self.assertIn('/skills/hermes/SKILL.md',text)
        self.assertNotIn('curl ',text)
    def test_identity_and_evidence_are_distinct(self):
        text=(ROOT/'.claude/skills/hermes/SKILL.md').read_text()
        for fragment in ['connected owner-identity Slack connector','read back the sent message','receipt/queue evidence','not necessarily a Hermes outage']:
            self.assertIn(fragment,text)
    def test_scope_and_portability(self):
        text=(ROOT/'.claude/skills/hermes/SKILL.md').read_text()
        self.assertIn('Do not switch identities, routes or tools to evade it',text)
        self.assertIn('This skill itself grants no standing permission',text)
        self.assertNotRegex(text,r'\b[DUC][A-Z0-9]{8,}\b')
        self.assertNotRegex(text,r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}')
        self.assertNotIn('/Users/',text)
    def test_gateway_payload_is_safe_and_bounded(self):
        text=(ROOT/'.claude/skills/hermes/SKILL.md').read_text()
        for fragment in ['JSON encoder','Bound timeouts','does not guarantee a Slack DM']:
            self.assertIn(fragment,text)
if __name__=='__main__': unittest.main()
