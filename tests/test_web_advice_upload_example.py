"""Execute the published JS template with a fake provider DOM, not a live account."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('node'), 'Node is required for the JS example fixture')
class UploadExampleTests(unittest.TestCase):
    def test_complete_packet_and_fail_closed_attachment_or_composer_gates(self):
        path = Path(os.environ.get('WEB_ADVICE_TEST_PATH', ROOT / '.claude/skills/web-advice/SKILL.md'))
        text = path.read_text()
        marker = '**Illustrative Playwright pattern:**' if '**Illustrative Playwright pattern:**' in text else '**Pattern (proven to work across all 3 providers):**'
        example = text[text.index(marker):].split('```javascript\n', 1)[1].split('```', 1)[0]
        for scenario in ['complete', 'missing', 'processing', 'truncated', 'unconfigured', 'no-send-button', 'disabled-send', 'chatgpt-send-message', 'chatgpt-send', 'chatgpt-no-send-button', 'gemini-no-send-button', 'unconfigured-provider']:
            prefix = '''const scenario = SCENARIO;
const state = {uploads: [], sent: 0, enter: 0, composer: ''};
const pwd = '/tmp/fixture-session';
let clock = 0;
Date.now = () => clock;
globalThis.setTimeout = (callback) => queueMicrotask(callback);
const input = {first() {return this;}, async setInputFiles(files) {state.uploads.push(files);}};
const textbox = {first() {return this;}, async fill(text) {state.composer = text;}, async inputValue() {return scenario === 'truncated' ? 'partial' : state.composer;}};
const send = {first() {return this;}, last() {return this;}, async isVisible() {if (scenario.endsWith('no-send-button')) return false; const label = scenario === 'chatgpt-send-message' ? 'Send message' : scenario === 'chatgpt-send' ? 'Send' : 'Send prompt'; return state.sendSelector.includes('aria-label=\"' + label + '\"');}, async isEnabled() {return scenario !== 'disabled-send';}, async click() {if (scenario === 'no-send-button') throw new Error('Locator has no matching send button'); state.sent++;}};
const chips = {async allTextContents() {
  clock = 120001;
  const names = state.uploads.flat().map((path) => path.split('/').pop());
  if (scenario === 'missing') return names.slice(0, 1);
  if (scenario === 'processing') return names.concat(['Processing']);
  return names;
}};
const modelPage = {locator(selector) {
  if (selector === 'verified-chip') return chips;
  if (selector.startsWith('input[type=')) return input;
  if (selector.startsWith('button[')) {state.sendSelector=selector; return send;}
  return textbox;
}, keyboard: {async press(key) {if (key !== 'Enter') throw new Error('wrong key'); state.enter++; state.sent++;}}};
try {
'''.replace('SCENARIO', json.dumps(scenario))
            configured = example if scenario == 'unconfigured' else example.replace('REPLACE_WITH_INSPECTED_COMPOSER_ATTACHMENT_CHIP_SELECTOR', 'verified-chip')
            if scenario != 'unconfigured-provider':
                provider = 'perplexity' if scenario == 'no-send-button' else 'gemini' if scenario == 'gemini-no-send-button' else 'chatgpt'
                configured = configured.replace('REPLACE_WITH_INSPECTED_PROVIDER', provider)
            script = prefix + configured + "\nstate.success=true; } catch(error) {state.error=error.message;}\nconsole.log(JSON.stringify(state));"
            with tempfile.TemporaryDirectory() as folder:
                runner = Path(folder) / 'fixture.mjs'
                runner.write_text(script)
                result = subprocess.run([shutil.which('node'), str(runner)], text=True, capture_output=True, check=True)
            proof = json.loads(result.stdout)
            if scenario in ['complete', 'no-send-button', 'chatgpt-send-message', 'chatgpt-send']:
                self.assertTrue(proof.get('success'), proof)
                self.assertEqual(len(proof['uploads']), 1)
                self.assertEqual(len(proof['uploads'][0]), 5)
                self.assertEqual(proof['sent'], 1)
                self.assertEqual(proof['enter'], int(scenario == 'no-send-button'))
            else:
                self.assertIn('error', proof)
                self.assertEqual(proof['sent'], 0)


if __name__ == '__main__':
    unittest.main()
