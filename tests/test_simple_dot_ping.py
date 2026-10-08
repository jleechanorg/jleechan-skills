"""Tiny scheduled ping tests use fake generator/Dot executables and temporary state."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT/'.claude/skills/agy-dot-coordinator/scripts/ping-dots.py'


class SimplePingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = self.root/'config.json'
        self.config.write_text(json.dumps({'rotation': ['alpha', 'beta', 'gamma'], 'accounts': {a: {} for a in ['alpha','beta','gamma']}}))
        self.calls = self.root/'calls'
        self.message = self.root/'message'
        self.generator = self.root/'generator'
        self.generator.write_text('#!/usr/bin/env python3\nimport os,sys\nargs=sys.argv\nassert args[1:5]==["exec","--yolo","-m","gpt-6-luna"]\nassert "--ephemeral" in args and "--skip-git-repo-check" in args\nassert args[args.index("--config")+1]=="project_doc_max_bytes=0"\nopen(os.environ["CALLS"],"a").write("generator\\n")\nopen(args[args.index("--output-last-message")+1],"w").write("Advance each authorized goal now and report the next safe action.")\n')
        self.dot = self.root/'dot'
        self.dot.write_text('#!/usr/bin/env python3\nimport os,sys\nfrom pathlib import Path\nassert sys.argv[1:4]==["--account","alpha","send-once"]\nassert os.environ["DOT_ALLOW_REMOTE"]=="0" and os.environ["DOT_ROTATE_ON_LIMIT"]=="0"\nopen(os.environ["CALLS"],"a").write("dot\\n")\nPath(os.environ["MESSAGE"]).write_text(Path(sys.argv[4]).read_text())\nprint(os.environ.get("RECEIPT","DOT_SENT_VERIFIED"))\nsys.exit(int(os.environ.get("SEND_RC","0")))\n')
        self.generator.chmod(0o700)
        self.dot.chmod(0o700)
        self.env = dict(os.environ, DOT_CONFIG_FILE=str(self.config), COORDINATOR_STATE_DIR=str(self.root/'state'), COORDINATOR_LOCK_FILE=str(self.root/'state/ping.lock'), COORDINATOR_GENERATOR=str(self.generator), COORDINATOR_DOT_SCRIPT=str(self.dot), CALLS=str(self.calls), MESSAGE=str(self.message))

    def run_ping(self):
        return subprocess.run(['python3', str(SCRIPT), '--account', 'alpha'], env=self.env, text=True, capture_output=True, timeout=5)

    def test_one_generator_and_one_existing_send_once(self):
        result = self.run_ping()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls.read_text().splitlines(), ['generator','dot'])
        self.assertIn('Advance each authorized goal', self.message.read_text())
        self.assertIn('From Codex coordinator', self.message.read_text())
        self.assertIn('sent', result.stdout)

    def test_generation_failure_does_not_send(self):
        self.generator.write_text('#!/bin/sh\nexit 7\n')
        self.assertNotEqual(self.run_ping().returncode, 0)
        self.assertFalse(self.message.exists())

    def test_unverified_send_is_reported_once_without_retry(self):
        self.env['RECEIPT'] = 'DOT_SEND_UNVERIFIED'
        result = self.run_ping()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls.read_text().splitlines(), ['generator','dot'])

    def test_stop_and_existing_hold_prevent_generation(self):
        state = self.root/'state'
        state.mkdir()
        (state/'STOP').touch()
        self.assertEqual(self.run_ping().returncode, 0)
        self.assertFalse(self.calls.exists())
        (state/'STOP').unlink()
        (state/'state_alpha.json').write_text(json.dumps({'delivery_unverified': True}))
        self.assertEqual(self.run_ping().returncode, 0)
        self.assertFalse(self.calls.exists())

    def test_native_offsets_cover_all_six_pairs(self):
        spec = importlib.util.spec_from_file_location('simple_ping', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        accounts = ['alpha','beta','gamma']
        for role, offsets in [('mac',(0,20,40)),('linux',(30,50,10))]:
            for account, minute in zip(accounts, offsets):
                self.assertEqual(module.due_account(accounts, role, minute*60+15), account)
        self.assertIsNone(module.due_account(accounts, 'mac', 7*60))

    def test_unknown_account_rejected_before_generation(self):
        self.config.write_text(json.dumps({'rotation':['beta','gamma','delta']}))
        self.assertNotEqual(self.run_ping().returncode, 0)
        self.assertFalse(self.calls.exists())

    def test_lock_contention_does_not_generate_or_send(self):
        import fcntl
        state = self.root/'state'
        state.mkdir()
        with (state/'ping.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertEqual(self.run_ping().returncode, 0)
        self.assertFalse(self.calls.exists())

    def test_existing_native_wrapper_uses_small_script_without_token_lookup(self):
        wrapper = (SCRIPT.parent/'agy-dot-coordinator-wrapper.sh').read_text()
        self.assertIn('WORKER="$SCRIPT_DIR/ping-dots.py"', wrapper)
        self.assertIn('exec python3 "$WORKER" "$@"', wrapper)
        self.assertNotIn('gh auth token', wrapper)
        timer = (SCRIPT.parents[1]/'systemd/ai.gemini.agy-dot-coordinator.timer').read_text()
        self.assertIn('OnCalendar=*:10,30,50:00', timer)
        self.assertIn('Persistent=false', timer)

    def test_empty_generation_output_does_not_send(self):
        self.generator.write_text('#!/bin/sh\nfor arg do target="$arg"; done\n: > "$target"\n')
        self.assertNotEqual(self.run_ping().returncode, 0)
        self.assertFalse(self.message.exists())
