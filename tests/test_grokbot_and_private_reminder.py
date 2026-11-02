"""Portable reminder selection and Grok browser workflow contracts."""
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.skill_portability_scan import find_personal_identifiers
class NewSkillContracts(unittest.TestCase):
 def test_private_reminder_override_preserves_fixed_default(self):
  text=(ROOT/'.claude/skills/dot-coordinator/SKILL.md').read_text(encoding="utf-8")
  self.assertIn('~/.config/dot/periodic-reminder.txt',text)
  self.assertIn('payload-unavailable',text)
  self.assertIn('never substitute another file',text)
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
   self.assertIn(f'skills/{name}/SKILL.md',(ROOT/f'.claude/commands/{name}.md').read_text(encoding="utf-8"))
 def test_new_exports_have_no_private_config(self):
  texts=[(ROOT/f'.claude/skills/{n}/SKILL.md').read_text(encoding="utf-8") for n in ['grokbot','grokb']]
  for text in texts:
   self.assertEqual(find_personal_identifiers(text),[])
   import re
   self.assertIsNone(re.search(r'https://grok\.com/bot/[a-f0-9]{8}-',text))

class GrokTransportUrlGuardTest(unittest.TestCase):
    """The read mode must accept only a bot URL and must land back on that exact path."""

    def _guard(self):
        script = (ROOT / '.claude/skills/grokbot/scripts/grok_chrome.mjs').read_text(encoding='utf-8')
        # The script validates with these two expressions; assert them directly so the
        # cases below describe the shipped logic rather than a copy of it.
        import re as _re
        accept = _re.search(r'if \(target\.origin !== .https://grok\.com. \|\| !(/\^\\/bot\\/\[\\w-\]\+\$/)\.test\(target\.pathname\)\)', script)
        arrived = _re.search(r'landed\.pathname !== target\.pathname', script)
        self.assertIsNotNone(accept, 'read must require origin grok.com and an anchored /bot/<id> pathname')
        self.assertIsNotNone(arrived, 'read must compare the landing pathname to the requested one')
        return script

    def test_guard_present(self):
        self._guard()

    def test_script_rejects_traversal_and_redirect_cases(self):
        # Node is the script's own runtime; skip cleanly where it is absent.
        node = shutil.which('node')
        if not node:
            self.skipTest('node not available')
        js = (
            'const ok=(u)=>{try{const t=new URL(u);return t.origin==="https://grok.com"'
            ' && /^\\/bot\\/[\\w-]+$/.test(t.pathname);}catch{return false;}};'
            'const cases={"https://grok.com/bot/abc":true,'
            '"https://grok.com/bot/a/../../settings":false,'
            '"https://grok.com/settings":false,'
            '"https://evil.com/bot/x":false,'
            '"not-a-url":false,'
            '"https://grok.com/bot/abc/extra":false};'
            'let bad=0;for(const[u,want]of Object.entries(cases)){if(ok(u)!==want){'
            'console.log("MISMATCH",u);bad=1;}}process.exit(bad);'
        )
        result = subprocess.run([node, '-e', js], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

if __name__=='__main__':unittest.main()
