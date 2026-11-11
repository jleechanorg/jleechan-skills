"""Execute the benchmark's Genesis launch recipe without starting a provider."""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BenchgLaunchTest(unittest.TestCase):
    def test_genesis_launch_is_detached_and_uses_isolated_workdir(self):
        text = (ROOT / '.claude/skills/benchg/SKILL.md').read_text()
        block = re.search(r'### 3\..*?```bash\n(.*?)```', text, re.S).group(1)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            bins = root / 'bin'
            bins.mkdir()
            checkout = root / 'checkout with spaces'
            (checkout / 'genesis').mkdir(parents=True)
            script = checkout / 'genesis/genesis.py'
            script.write_text('# fixture; never executed\n')
            work = root / 'isolated output'
            work.mkdir()
            trace = root / 'calls.jsonl'
            for name in ['tmux', 'python', 'sleep']:
                stub = bins / name
                stub.write_text('#!/usr/bin/env python3\nimport json,os,sys\n'
                                'with open(os.environ["TRACE"],"a") as f:\n'
                                ' f.write(json.dumps([os.path.basename(sys.argv[0]),*sys.argv[1:]])+"\\n")\n')
                stub.chmod(0o755)
            description = 'quotes " and $(touch SHOULD_NOT_EXIST) stay literal'
            env = dict(os.environ, PATH=str(bins)+os.pathsep+os.environ['PATH'],
                       GENESIS_DIR=str(work), PROJECT_NUM='1',
                       PROJECT_DESCRIPTION=description, TRACE=str(trace))
            result = subprocess.run(['bash', '-c', block], cwd=checkout, env=env,
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            calls = [json.loads(line) for line in trace.read_text().splitlines()]
            launches = [call for call in calls if call[:2] == ['tmux', 'new-session']]
            self.assertEqual(len(launches), 1, calls)
            launch = launches[0]
            self.assertIn('-d', launch)
            self.assertEqual(launch[launch.index('-c')+1], str(work))
            self.assertEqual(launch[launch.index('python'):],
                             ['python', str(script), '--refine', description, '30'])
            self.assertFalse(any(call[0] == 'python' for call in calls), calls)
            self.assertFalse((checkout / 'SHOULD_NOT_EXIST').exists())


if __name__ == '__main__':
    unittest.main()
