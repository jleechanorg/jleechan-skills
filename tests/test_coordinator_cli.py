"""Offline portable-adapter contracts; fake executables, never real credentials."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ADAPTER = Path(__file__).resolve().parents[1] / '.claude/skills/dot-coordinator/scripts/pi-lunaroute-adapter.sh'


class AdapterContract(unittest.TestCase):
    def invoke(self, args, *, existing=True, model=None, code=0, forbid_env=False):
        with tempfile.TemporaryDirectory(dir='/tmp') as directory:
            root = Path(directory)
            pi = root / 'pi executable with spaces'
            pi.write_text('#!/usr/bin/env python3\nimport json,os,sys\nprint(json.dumps({"argv":sys.argv[1:],"credential_matches":os.environ.get("LUNAROUTE_API_KEY")==os.environ["EXPECT_KEY"]}))\nsys.exit(int(os.environ["FAKE_EXIT"]))\n')
            pi.chmod(0o700)
            helper = root / 'lunaroute'
            helper.write_text('#!/usr/bin/env python3\nimport os,pathlib\npathlib.Path(os.environ["HELPER_MARKER"]).write_text("called")\nprint("fixture-helper")\n')
            helper.chmod(0o700)
            if forbid_env:
                env_command = root / 'env'
                env_command.write_text('#!/bin/sh\nexit 91\n')
                env_command.chmod(0o700)
            marker = root / 'helper-called'
            env = {**os.environ, 'PI_EXECUTABLE': str(pi), 'PATH': str(root) + os.pathsep + os.environ['PATH'],
                   'HELPER_MARKER': str(marker), 'FAKE_EXIT': str(code),
                   'EXPECT_KEY': 'fixture-existing' if existing else 'fixture-helper'}
            env.pop('LUNAROUTE_API_KEY', None)
            env.pop('PIL_MODEL', None)
            if existing:
                env['LUNAROUTE_API_KEY'] = 'fixture-existing'
            if model is not None:
                env['PIL_MODEL'] = model
            result = subprocess.run(['/bin/sh', str(ADAPTER), *args], env=env, capture_output=True, text=True)
            return result, marker.exists()

    def test_pi_contract_and_literal_args_preserved(self):
        args = ['--thinking', 'medium', '--print', '--no-session', '-e', 'builtin:mcp',
                '--skill', '/tmp/a skill.md', '--tools', 'read,mcp__dot_browser__*',
                'Literal $HOME $(never-run); task\nsecond line']
        result, called = self.invoke(args)
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertEqual(data['argv'], ['--provider', 'lunaroute', '--model', 'deepseek-4.1-flash', *args])
        self.assertTrue(data['credential_matches'])
        self.assertFalse(called)

    def test_optional_model_override_is_one_literal_argument(self):
        model = 'configured model; $HOME $(never-run)'
        result, _ = self.invoke(['task'], model=model)
        self.assertEqual(json.loads(result.stdout)['argv'], ['--provider', 'lunaroute', '--model', model, 'task'])

    def test_existing_credential_helper_used_only_when_environment_missing(self):
        result, called = self.invoke(['task'], existing=False)
        self.assertEqual(result.returncode, 0)
        self.assertTrue(called)
        self.assertTrue(json.loads(result.stdout)['credential_matches'])

    def test_credential_is_not_passed_through_env_command_argv(self):
        result, _ = self.invoke(['task'], forbid_env=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)['credential_matches'])

    def test_child_failure_propagates_without_fallback(self):
        result, _ = self.invoke(['task'], code=23)
        self.assertEqual(result.returncode, 23)


if __name__ == '__main__':
    unittest.main()
