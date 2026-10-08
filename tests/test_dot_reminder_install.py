"""Render-only native scheduling tests; never installs or starts services."""
import importlib.util
import os
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT/'.claude/skills/dot-portfolio-coordinator/scripts/reminder_native.py'


def load_renderer():
    spec = importlib.util.spec_from_file_location('reminder_native', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class NativeRenderTests(unittest.TestCase):
    def setUp(self):
        self.native = load_renderer()
        self.config = dict(python=sys.executable, node=os.environ['REMINDER_TEST_NODE'],
                           worker='/opt/reminder package/coordinator-reminder.py',
                           config='/opt/private config/account.json', state='/opt/private state')

    def test_mac_exact_offsets_and_argument_boundaries(self):
        files = self.native.render(self.config, 'mac')
        self.assertEqual(len(files), 1)
        plist = plistlib.loads(next(iter(files.values())))
        self.assertEqual([slot['Minute'] for slot in plist['StartCalendarInterval']], [0, 20, 40])
        self.assertEqual(plist['ProgramArguments'], [sys.executable, self.config['worker'], '--role', 'mac', '--config', self.config['config']])
        self.assertFalse(plist.get('KeepAlive', False))
        self.assertFalse(plist.get('RunAtLoad', False))
        self.assertEqual(plist['EnvironmentVariables']['DOT_NODE'], self.config['node'])

    def test_linux_exact_offsets_no_catchup_and_finite_service(self):
        files = self.native.render(self.config, 'linux')
        self.assertEqual(len(files), 2)
        service = files[self.native.LABEL+'.service'].decode()
        timer = files[self.native.LABEL+'.timer'].decode()
        self.assertIn('OnCalendar=*-*-* *:10,30,50:00 UTC', timer)
        self.assertIn('Persistent=false', timer)
        self.assertIn('Type=oneshot', service)
        self.assertIn('TimeoutStartSec=1200', service)
        self.assertIn('KillMode=control-group', service)
        self.assertNotIn('Restart=', service)
        self.assertIn('"/opt/reminder package/coordinator-reminder.py"', service)

    def test_percent_dollar_quote_and_backslash_are_escaped(self):
        self.config['config'] = '/opt/a%name/$value/quote"and\\slash'
        service = self.native.render(self.config, 'linux')[self.native.LABEL+'.service'].decode()
        self.assertIn('/opt/a%%name/$$value/quote\\"and\\\\slash', service)

    def test_environment_dollars_are_literal_not_argument_expansions(self):
        with tempfile.TemporaryDirectory() as tmp:
            node = Path(tmp)/'$node'
            node.symlink_to(self.config['node'])
            service = self.native.render(dict(self.config, node=str(node)), 'linux')[self.native.LABEL+'.service'].decode()
            self.assertIn('Environment="DOT_NODE='+str(node)+'"', service)
            self.assertNotIn('$$node', service)

    def test_relative_or_control_character_paths_rejected(self):
        for bad in ['relative/path', '/tmp/a\nb', '/tmp/a\x00b']:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.native.render(dict(self.config, config=bad), 'linux')

    def test_wrong_node_major_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            node = Path(tmp)/'node'
            node.write_text('#!/bin/sh\necho v24.0.0\n')
            node.chmod(0o700)
            with self.assertRaisesRegex(ValueError, 'Node 22'):
                self.native.render(dict(self.config, node=str(node)), 'linux')

    def test_render_has_no_home_install_side_effect(self):
        with tempfile.TemporaryDirectory() as tmp:
            before = set(Path(tmp).rglob('*'))
            self.native.render(dict(self.config, state=tmp), 'linux')
            self.assertEqual(set(Path(tmp).rglob('*')), before)

    def test_one_replacement_owner_label(self):
        self.assertEqual(self.native.LABEL, 'ai.gemini.agy-dot-coordinator')
        for host in ['mac', 'linux']:
            self.assertTrue(all(name.startswith(self.native.LABEL) for name in self.native.render(self.config, host)))


if __name__ == '__main__':
    unittest.main()
