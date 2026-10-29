"""Portable reminder selection and Grok browser workflow contracts."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.skill_portability_scan import find_personal_identifiers
class NewSkillContracts(unittest.TestCase):
 def test_private_reminder_override_preserves_fixed_default(self):
  text=(ROOT/'.claude/skills/dot-coordinator/SKILL.md').read_text(encoding="utf-8")
  self.assertIn('~/.config/dot/periodic-reminder.txt',text)
  self.assertIn('missing or empty',text)
  self.assertIn('do not silently fall back',text)
  self.assertIn('recipient',text.lower())
  self.assertIn('No private inventory',text)
  import re
  self.assertIsNone(re.search(r'\b[A-Za-z0-9_.-]+/roadmap(?:/|\b)',text))
  self.assertIn('locations supplied through authorized private context',text)
  self.assertIn('An acknowledgment or changed wording does not authorize another submit',text)
 def test_grok_identity_target_and_uncertain_send(self):
  text=(ROOT/'.claude/skills/grokbot/SKILL.md').read_text(encoding="utf-8")
  for phrase in ['expected signed-in identity','https://grok.com/bot/','one writer','UNCERTAIN','do not resend','PICKED_UP','EXECUTING','read-only','Do not copy cookies']:
   self.assertIn(phrase,text)
 def test_grok_alias_and_commands_point_to_one_workflow(self):
  alias=(ROOT/'.claude/skills/grokb/SKILL.md').read_text(encoding="utf-8")
  self.assertIn('../grokbot/SKILL.md',alias)
  for name in ['grokbot','grokb']:
   self.assertIn('grokbot/SKILL.md',(ROOT/f'.claude/commands/{name}.md').read_text(encoding="utf-8"))
 def test_new_exports_have_no_private_config(self):
  texts=[(ROOT/f'.claude/skills/{n}/SKILL.md').read_text(encoding="utf-8") for n in ['grokbot','grokb']]
  for text in texts:
   self.assertEqual(find_personal_identifiers(text),[])
   import re
   self.assertIsNone(re.search(r'https://grok\.com/bot/[a-f0-9]{8}-',text))

if __name__=='__main__':unittest.main()
