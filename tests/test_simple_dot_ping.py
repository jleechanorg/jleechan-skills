"""Scheduled ping tests use fake generation providers and Dot executables."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT/'.claude/skills/agy-dot-coordinator/scripts/ping-dots.py'
MESSAGE = 'Advance each authorized goal now and report the next safe action.'


class SimplePingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir="/tmp")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bindir = self.root/'bin'
        self.bindir.mkdir()
        self.config = self.root/'config.json'
        self.config.write_text(json.dumps({'rotation': ['alpha', 'beta', 'gamma'], 'accounts': {a: {} for a in ['alpha','beta','gamma']}}))
        self.calls = self.root/'calls'
        self.message = self.root/'message'
        self.agy = self.bindir/'agy'
        self.agy.write_text('#!/usr/bin/env python3\nimport json,os,sys\nopen(os.environ["CALLS"],"a").write("agy\\n")\nmode=os.environ.get("AGY_MODE","success")\nif mode=="error": print("agy diagnostic",file=sys.stderr);sys.exit(7)\nif mode=="malformed": print("not-json");sys.exit(0)\nresponse="" if mode=="empty" else ("x"*1201 if mode=="long" else os.environ.get("GENERATED",'+repr(MESSAGE)+'))\nprint(json.dumps({"event":"result","result":{"status":"SUCCESS","response":response}}))\n')
        self.codex = self.bindir/'codex'
        self.codex.write_text('#!/usr/bin/env python3\nimport os,sys\nargs=sys.argv\nassert args[1:5]==["exec","--yolo","-m","gpt-6-luna"]\nassert "--ephemeral" in args and "--skip-git-repo-check" in args\nassert args[args.index("--config")+1]=="project_doc_max_bytes=0"\nopen(os.environ["CALLS"],"a").write("codex\\n")\nmode=os.environ.get("CODEX_MODE","success")\nif mode=="error": print("codex diagnostic",file=sys.stderr);sys.exit(8)\ncontent="" if mode=="empty" else ("x"*1201 if mode=="long" else os.environ.get("GENERATED",'+repr(MESSAGE)+'))\nopen(args[args.index("--output-last-message")+1],"w").write(content)\n')
        self.haiku = self.bindir/'claude'
        self.haiku.write_text('#!/usr/bin/env python3\nimport json,os,sys\nargs=sys.argv\nassert "--model" in args and args[args.index("--model")+1]=="claude-haiku-5-5"\nassert args[args.index("--tools")+1]=="" and "--no-session-persistence" in args\nopen(os.environ["CALLS"],"a").write("haiku\\n")\nmode=os.environ.get("HAIKU_MODE","success")\nif mode=="error": print("haiku diagnostic",file=sys.stderr);sys.exit(9)\nprint(json.dumps({"is_error":False,"result":os.environ.get("GENERATED",'+repr(MESSAGE)+')}))\n')
        self.dot = self.root/'dot'
        self.dot.write_text('#!/usr/bin/env python3\nimport os,sys\nfrom pathlib import Path\nassert sys.argv[1:4]==["--account","alpha","send-once"]\nassert os.environ["DOT_ROTATE_ON_LIMIT"]=="0"\nopen(os.environ["CALLS"],"a").write("dot\\n")\nPath(os.environ["MESSAGE"]).write_text(Path(sys.argv[4]).read_text())\nprint(os.environ.get("RECEIPT","DOT_SENT_VERIFIED"))\nprint("dot diagnostic",file=sys.stderr)\nsys.exit(int(os.environ.get("SEND_RC","0")))\n')
        for executable in (self.agy, self.codex, self.haiku, self.dot):
            executable.chmod(0o700)
        self.env = dict(os.environ, PATH=str(self.bindir)+os.pathsep+os.environ['PATH'],
                        DOT_CONFIG_FILE=str(self.config), COORDINATOR_STATE_DIR=str(self.root/'state'),
                        COORDINATOR_LOCK_FILE=str(self.root/'state/ping.lock'),
                        COORDINATOR_AGY=str(self.agy), COORDINATOR_GENERATOR=str(self.codex),
                        COORDINATOR_DOT_SCRIPT=str(self.dot), CALLS=str(self.calls), MESSAGE=str(self.message))

    def run_ping(self, *args):
        return subprocess.run(['python3', str(SCRIPT), '--account', 'alpha', *args], env=self.env,
                              text=True, capture_output=True, timeout=8)

    def calls_made(self):
        return self.calls.read_text().splitlines() if self.calls.exists() else []

    def test_prompt_requires_receipts_for_six_actual_work_slots(self):
        source = SCRIPT.read_text()
        prompt = source.split('PROMPT = """', 1)[1].split('"""', 1)[0]
        for contract in (
            'FIRST to inventory current authorized work in progress',
            'count only distinct tasks', 'require an execution', 'receipt: goal/item',
            'exact action happening now',
            'fresh artifact or command result', 'Idle, stalled, finished, queued, or waiting-for-review',
            'at least six distinct tasks are truly active', 'Do not gate work on a priority rank',
            'If fewer than six', 'active tasks are proven', 'cloud coders', 'never this Mac',
            'permission/approval hold or measured resource limit', 'name its evidence and exact blocked action',
            'user stops', 'preserve owners and all approval', 'boundaries',
        ):
            self.assertIn(contract, prompt)
        self.assertNotIn('six highest-priority', prompt)

        dot_skill = (ROOT/'.claude/skills/dot/SKILL.md').read_text()
        self.assertIn('before declining an authorized task, ask the Dot to inventory current work',
                      dot_skill)
        self.assertIn('at least six distinct active tasks', dot_skill)
        self.assertNotIn('asks whether the task is in the dot\'s current top 6', dot_skill)

        coordinator_skill = (SCRIPT.parents[1]/'SKILL.md').read_text()
        self.assertIn('inventory real active work first', coordinator_skill)
        self.assertIn('at least six distinct tasks', coordinator_skill)

    def test_primary_agy_success_uses_one_send(self):
        result = self.run_ping()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls_made(), ['agy', 'dot'])
        self.assertIn(MESSAGE, self.message.read_text())
        self.assertIn('From AGY coordinator', self.message.read_text())
        self.assertIn('Generation succeeded with agy', result.stdout)
        self.assertIn('DOT_SENT_VERIFIED', result.stdout)
        self.assertIn('dot diagnostic', result.stderr)

    def test_agy_failure_falls_back_to_codex(self):
        self.env['AGY_MODE'] = 'error'
        result = self.run_ping()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls_made(), ['agy', 'codex', 'dot'])
        self.assertIn('From Codex coordinator', self.message.read_text())
        self.assertIn('agy generation failed', result.stderr)

    def test_agy_and_codex_failure_fall_back_to_haiku(self):
        self.env.update(AGY_MODE='error', CODEX_MODE='error')
        result = self.run_ping()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls_made(), ['agy', 'codex', 'haiku', 'dot'])
        self.assertIn('From Claude Haiku coordinator', self.message.read_text())
        self.assertIn('codex generation failed', result.stderr)

    def test_all_provider_failures_do_not_send(self):
        self.env.update(AGY_MODE='error', CODEX_MODE='error', HAIKU_MODE='error')
        result = self.run_ping()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls_made(), ['agy', 'codex', 'haiku'])
        self.assertFalse(self.message.exists())

    def test_malformed_structured_results_fall_through_without_send(self):
        self.agy.write_text('#!/usr/bin/env python3\nimport json,os\nopen(os.environ["CALLS"],"a").write("agy\\n")\nprint(json.dumps({"event":"result","result":[]}))\n')
        self.codex.write_text('#!/usr/bin/env python3\nimport os,sys\nopen(os.environ["CALLS"],"a").write("codex\\n")\nprint("codex diagnostic",file=sys.stderr)\nsys.exit(8)\n')
        self.haiku.write_text('#!/usr/bin/env python3\nimport json,os\nopen(os.environ["CALLS"],"a").write("haiku\\n")\nprint("[]")\n')
        result = self.run_ping()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls_made(), ['agy', 'codex', 'haiku'])
        self.assertIn('agy generation failed', result.stderr)
        self.assertIn('haiku generation failed', result.stderr)
        self.assertFalse(self.message.exists())

    def test_malformed_primary_falls_back_and_generator_flag_forces_provider(self):
        self.env['AGY_MODE'] = 'malformed'
        result = self.run_ping()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls_made(), ['agy', 'codex', 'dot'])
        self.calls.unlink()
        self.message.unlink()
        self.env['AGY_MODE'] = 'error'
        result = self.run_ping('--generator', 'haiku')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls_made(), ['haiku', 'dot'])

    def test_generate_only_exercises_provider_without_dot(self):
        result = self.run_ping('--generator', 'haiku', '--generate-only')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls_made(), ['haiku'])
        self.assertIn(MESSAGE, result.stdout)
        self.assertFalse(self.message.exists())

    def test_unverified_send_is_reported_once_without_retry(self):
        self.env['RECEIPT'] = 'DOT_SEND_UNVERIFIED'
        result = self.run_ping()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('DOT_SEND_UNVERIFIED', result.stdout)
        self.assertIn('dot diagnostic', result.stderr)
        self.assertEqual(self.calls_made(), ['agy', 'dot'])

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
