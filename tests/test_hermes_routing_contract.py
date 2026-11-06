"""Portable routing contracts; no live Slack or gateway calls."""
from pathlib import Path
import re
import unittest
ROOT=Path(__file__).resolve().parents[1]
class HermesRoutingContract(unittest.TestCase):
    def test_scope_and_portability(self):
        text=(ROOT/'.claude/skills/hermes/SKILL.md').read_text()
        self.assertNotRegex(text,r'\b[DUC][A-Z0-9]{8,}\b')
        self.assertNotRegex(text,r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}')
        self.assertNotIn('/Users/',text)
if __name__=='__main__': unittest.main()
