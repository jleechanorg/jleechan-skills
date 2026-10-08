"""Fixture-only AGY generation contract; never runs AGY or a provider."""
import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / '.claude/skills/dot-portfolio-coordinator'
sys.path.insert(0, str(PACKAGE / 'scripts'))


class GeneratorTests(unittest.TestCase):
    def setUp(self):
        self.driver = importlib.import_module('reminder_driver')
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.prompt = Path(self.directory.name) / 'prompt.md'
        self.prompt.write_text('Continue current authorized work.\n', encoding='utf-8')

    def invoke(self, output=None, **changes):
        if output is None:
            output = self.envelope('Continue with your next authorized action.')
        receipt = dict(stdout=output, stderr=b'', returncode=0, reason='exited',
                       natural_exit=True, cleanup_ok=True, forced_cleanup=False)
        receipt.update(changes)
        with patch.object(self.driver, 'run', return_value=receipt) as runner:
            result = self.driver.generate('/trusted/agy', self.prompt, 12.5)
        return result, runner

    @staticmethod
    def envelope(response):
        return (json.dumps({'event': 'result', 'result': {
            'status': 'SUCCESS', 'response': response}}) + '\n').encode()

    def test_canonical_argv_stdin_and_process_budget(self):
        result, runner = self.invoke()
        self.assertEqual(result, 'Continue with your next authorized action.')
        args, kwargs = runner.call_args
        self.assertEqual(args[0], ['/trusted/agy', '--dangerously-skip-permissions',
                                  '--new-project', '--print-timeout', '12.5s',
                                  '--input-format', 'stream-json',
                                  '--output-format', 'stream-json'])
        self.assertEqual(json.loads(args[1]), {'event': 'user', 'message': {
            'content': self.prompt.read_text()}})
        self.assertEqual(kwargs['timeout'], 12.5)
        self.assertLessEqual(kwargs['max_output'], 65536)

    def test_valid_nonterminal_events_and_exact_character_boundary(self):
        expected = 'é' * 1200
        result, _ = self.invoke(b'{"event":"progress","text":"working"}\n' + self.envelope(expected))
        self.assertEqual(result, expected)

    def test_rejects_invalid_terminal_envelopes(self):
        valid = self.envelope('Continue.')
        invalid = [b'', b'\xff', b'not-json\n', b'null\n', b'[]\n', b'{}\n',
                   b'{"event":"progress"}\n', valid + valid,
                   valid + b'{"event":"progress"}\n', valid + b'junk\n',
                   b'{"event":"result","result":null}\n',
                   b'{"event":"result","result":{"status":"FAILURE","response":"x"}}\n',
                   b'{"event":"result","result":{"status":"SUCCESS"}}\n',
                   b'{"event":"result","result":{"status":"SUCCESS","response":"x","response":"y"}}\n',
                   self.envelope(''), self.envelope(' \n\t'), self.envelope('x'*1201),
                   self.envelope(None), self.envelope(1), self.envelope(['x']),
                   self.envelope('\ud800')]
        for output in invalid:
            with self.subTest(output=output), self.assertRaises((ValueError, UnicodeError)):
                self.invoke(output)

    def test_rejects_unproven_process_success(self):
        cases = [{'returncode': 1}, {'returncode': False}, {'natural_exit': False},
                 {'cleanup_ok': False}, {'forced_cleanup': True},
                 {'reason': 'timeout'}, {'reason': 'output_limit'},
                 {'reason': 'pipe_drain'}, {'reason': 'observation_or_io_failed'}]
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.invoke(**changes)

    def test_invalid_timeout_does_not_start_process(self):
        for timeout in (0, -1, 601, float('inf'), float('nan'), True, '60'):
            with self.subTest(timeout=timeout), patch.object(self.driver, 'run') as runner:
                with self.assertRaises(ValueError):
                    self.driver.generate('/trusted/agy', self.prompt, timeout)
                runner.assert_not_called()

    def test_empty_oversized_or_missing_prompt_does_not_start_process(self):
        for text in ('', '  \n', 'x' * 65537):
            self.prompt.write_text(text)
            with self.subTest(text_length=len(text)), patch.object(self.driver, 'run') as runner:
                with self.assertRaises(ValueError):
                    self.driver.generate('/trusted/agy', self.prompt, 60)
                runner.assert_not_called()
        self.prompt.unlink()
        with patch.object(self.driver, 'run') as runner, self.assertRaises(OSError):
            self.driver.generate('/trusted/agy', self.prompt, 60)
        runner.assert_not_called()

    def test_runner_failure_does_not_fall_back(self):
        with patch.object(self.driver, 'run', side_effect=TimeoutError) as runner:
            with self.assertRaises(TimeoutError):
                self.driver.generate('/trusted/agy', self.prompt, 60)
        runner.assert_called_once()

    def test_prompt_scope_and_physical_size(self):
        text = (PACKAGE / 'references/reminder.md').read_text()
        for required in ('owners', 'cancellations', 'approval gates', 'authorized work',
                         'next action', 'genuine blocker', '1,200'):
            self.assertIn(required, text)
        self.assertLessEqual(len(text.splitlines()), 20)
        self.assertLessEqual(len(Path(self.driver.__file__).read_text().splitlines()), 50)


if __name__ == '__main__':
    unittest.main()
