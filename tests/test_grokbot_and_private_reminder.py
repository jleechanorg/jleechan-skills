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
    """read must accept only a bot URL and must land back on that exact path.

    These import the SHIPPED predicates from scripts/url-guard.mjs, so a change to the
    guard is caught here rather than shadowed by a re-implementation in the test.
    """

    GUARD = ROOT / '.claude/skills/grokbot/scripts/url-guard.mjs'

    def _run(self, js):
        node = shutil.which('node')
        if not node:
            self.skipTest('node not available')
        mod = self.GUARD.as_uri()
        script = f'import {{isBotUrl, landedOnRequested}} from "{mod}";\n{js}'
        return subprocess.run([node, '--input-type=module', '-e', script],
                              capture_output=True, text=True)

    def test_guard_module_exists_and_exports_both_predicates(self):
        text = self.GUARD.read_text(encoding='utf-8')
        self.assertIn('export const isBotUrl', text)
        self.assertIn('export const landedOnRequested', text)

    def test_requested_url_matrix(self):
        js = (
            'const cases={"https://grok.com/bot/abc":true,'
            '"https://grok.com/bot/a/../../settings":false,'
            '"https://grok.com/settings":false,'
            '"https://evil.com/bot/x":false,'
            '"not-a-url":false,'
            '"https://grok.com/bot/abc/extra":false};'
            'let bad=0;for(const[u,w]of Object.entries(cases)){if(isBotUrl(u)!==w){'
            'console.log("MISMATCH",u);bad=1;}}process.exit(bad);'
        )
        r = self._run(js)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_redirect_landing_matrix(self):
        # The cases the review asked for: a redirect must never be reported as the
        # requested conversation.
        js = (
            'const cases=['
            '["https://grok.com/bot/a","https://grok.com/bot/a",true],'
            '["https://grok.com/bot/a","https://grok.com/bot/other",false],'
            '["https://grok.com/bot/a","https://grok.com/bot/a/settings",false],'
            '["https://grok.com/bot/a","https://grok.com/settings",false],'
            '["https://grok.com/bot/a","https://evil.com/bot/a",false],'
            '["https://grok.com/bot/a","https://grok.com/bot/a?x=1",true]'
            '];let bad=0;for(const[q,l,w]of cases){if(landedOnRequested(q,l)!==w){'
            'console.log("MISMATCH",q,l);bad=1;}}process.exit(bad);'
        )
        r = self._run(js)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_transport_uses_the_shared_guard(self):
        # A transport that inlined its own regex would drift from the tested predicate.
        text = (ROOT / '.claude/skills/grokbot/scripts/grok_chrome.mjs').read_text(encoding='utf-8')
        self.assertIn("from './url-guard.mjs'", text)
        self.assertIn('isBotUrl(', text)
        self.assertIn('landedOnRequested(', text)

if __name__=='__main__':unittest.main()
