"""Portable reminder selection and Grok browser workflow contracts."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.skill_portability_scan import find_personal_identifiers
class NewSkillContracts(unittest.TestCase):
 def test_grok_alias_and_commands_point_to_one_workflow(self):
  alias=(ROOT/'.claude/skills/grokb/SKILL.md').read_text(encoding="utf-8")
  self.assertIn('../grokbot/SKILL.md',alias)
  for name in ['grokbot','grokb']:
   self.assertIn(f'skills/{name}/SKILL.md',(ROOT/f'.claude/commands/{name}.md').read_text(encoding="utf-8"))
 def test_new_exports_have_no_private_config(self):
  texts=[(ROOT/f'.claude/skills/{n}/SKILL.md').read_text(encoding="utf-8") for n in ['grokbot','grokb']]
  for text in texts:
   self.assertEqual(find_personal_identifiers(text),[])
   import re
   self.assertIsNone(re.search(r'https://grok\.com/bot/[a-f0-9]{8}-',text))

if __name__=='__main__':unittest.main()
