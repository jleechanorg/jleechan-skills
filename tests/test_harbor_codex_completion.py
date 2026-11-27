import hashlib
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'harbor_codex_completion.py'
THREAD = '11111111-2222-4333-8444-555555555555'


def jsonl(path, entries):
    path.write_text(''.join(json.dumps(entry) + '\n' for entry in entries), encoding='utf-8')


def rollout(kind, **payload):
    return {'type': kind, 'payload': payload}


def test_native_control_requires_exact_first_turn_input(tmp_path):
    seen = runpy.run_path(str(SCRIPT))['native_control_seen']
    trajectory = tmp_path / 'rollout.jsonl'
    start = rollout('session_meta', id=THREAD)
    begin = rollout('event_msg', type='task_started', turn_id='turn', root_turn_id='turn')
    context = rollout('turn_context', cwd='/workspace', turn_id='turn', root_turn_id='turn')
    control = b'fixture control\n'
    message = rollout('response_item', type='message', role='user', content=[{'type': 'input_text',
        'text': '# AGENTS.md instructions for /workspace\n\n<INSTRUCTIONS>\nfixture control\n\n</INSTRUCTIONS>'}],
        internal_chat_message_metadata_passthrough={'turn_id': 'turn',
                                                   'content_item_kinds': ['agents_md.instructions']})
    prompt = rollout('response_item', type='message', role='user', content=[{'type': 'input_text', 'text': 'task\n'}],
                     internal_chat_message_metadata_passthrough={'turn_id': 'turn', 'content_item_kinds': ['user.text']})
    spoof = rollout('response_item', **{**message['payload'], 'internal_chat_message_metadata_passthrough': {
        'turn_id': 'turn', 'content_item_kinds': ['user.text']}})
    first_tool = rollout('response_item', type='function_call', name='exec_command', call_id='first')
    for records, matched in (([start, begin, message, context, prompt, first_tool], True),
                             ([start, begin, spoof, context, prompt, first_tool], False),
                             ([start, begin, first_tool, message, context, prompt], False),
                             ([start, begin, message, message, context, prompt], False),
                             ([start, begin, context, message, prompt, first_tool], False),
                             ([start, begin, message, rollout('turn_context', cwd='/elsewhere'), prompt], False)):
        jsonl(trajectory, records)
        assert bool(seen(trajectory, control, b'task\n')) is matched
    assert not seen(trajectory, b'other control', b'task\n')


def paginated_item(kind, **fields):
    return {'type': 'item_completed', 'thread_id': THREAD, 'turn_id': 'turn',
            'item': {'type': kind, **fields}}


def test_cli_usage_keeps_only_supported_terminal_counts(tmp_path):
    usage = runpy.run_path(str(SCRIPT))['cli_usage']
    trace = tmp_path / 'codex.jsonl'
    jsonl(trace, [{'type': 'turn.completed', 'usage': {'input_tokens': 120, 'cached_input_tokens': 0,
        'output_tokens': 4, 'reasoning_output_tokens': True, 'cache_write_input_tokens': -1, 'unknown': 30}}])
    assert usage(trace) == {'input_tokens': 120, 'cached_input_tokens': 0, 'output_tokens': 4}
    jsonl(trace, [{'type': 'turn.failed', 'usage': {'input_tokens': 120}}])
    assert usage(trace) is None


def test_projected_command_preserves_actual_visible_output(tmp_path):
    native = runpy.run_path(str(SCRIPT))
    session = tmp_path / 'session.jsonl'
    aggregate = 'prefix' + 'x' * 80 + 'suffix'
    visible = 'prefix\n\n…80 chars truncated…\n\nsuffix'
    rows = [rollout('session_meta', id=THREAD, cli_version='0.172.0', model_provider='openai'),
            rollout('turn_context', cwd='/workspace', turn_id='turn', root_turn_id='turn',
                    model='gpt-6.2-sol', effort='medium'),
            rollout('response_item', type='function_call', name='exec_command', call_id='call_1',
                    arguments=json.dumps({'cmd': 'echo hello', 'max_output_tokens': 64})),
            rollout('event_msg', **paginated_item('CommandExecution', id='call_1', command=['echo', 'hello'],
                                                  status='completed', exit_code=0, aggregated_output=aggregate)),
            rollout('response_item', type='function_call_output', call_id='call_1', output=visible)]
    jsonl(session, rows)
    projected = native['jsonl'](native['scoring_projection'](session.read_bytes()))
    assert [entry['native_ordinal'] for entry in projected] == list(range(5))
    assert projected[-1] == {'event': 'model_visible_result', 'native_ordinal': 4, 'timestamp': None,
                             'output': visible, 'call_id': 'call_1', 'truncated': True}
    assert projected[-2]['output'] == aggregate
    assert projected[-3]['arguments'] == {'cmd': 'echo hello'}
    rows[-1]['payload']['output'] = visible.replace('80 chars', '81 chars')
    jsonl(session, rows)
    with pytest.raises(ValueError):
        native['scoring_projection'](session.read_bytes())


def test_command_projection_preserves_explicit_permission_and_tty():
    command_input = runpy.run_path(str(SCRIPT))['command_input']
    argv = ['/bin/bash', '-lc', 'echo fixture']
    arguments = {'cmd': 'echo fixture', 'sandbox_permissions': 'require_escalated', 'tty': True,
                 'justification': 'Fixture confirmation', 'prefix_rule': ['echo']}
    assert command_input('exec_command', json.dumps(arguments), argv) == arguments
    with pytest.raises(ValueError):
        command_input('exec_command', json.dumps({**arguments, 'tty': 'true'}), argv)


def test_native_command_polls_bind_to_one_origin_without_inventing_completions(tmp_path):
    native = runpy.run_path(str(SCRIPT))
    session = tmp_path / 'session.jsonl'
    envelope = 'Chunk ID: ab10\nWall time: 0.0000 seconds\n{}\nOutput:\n{}'
    running = 'Process running with session ID 42'
    ended = 'Process exited with code 2'
    origin = rollout('response_item', type='function_call', name='exec_command', call_id='origin',
                     arguments=json.dumps({'cmd': 'echo hello'}))
    origin_output = rollout('response_item', type='function_call_output', call_id='origin',
                            output=envelope.format(running, 'hello'))
    poll = rollout('response_item', type='function_call', name='write_stdin', call_id='poll',
                   arguments=json.dumps({'session_id': 42, 'chars': ''}))
    poll_output = rollout('response_item', type='function_call_output', call_id='poll',
                          output=envelope.format(running, ' again'))
    terminal_poll = rollout('response_item', **{**poll['payload'], 'call_id': 'last'})
    terminal_output = rollout('response_item', **{**poll_output['payload'], 'call_id': 'last',
                                                   'output': envelope.format(ended, '!')})
    completion = rollout('event_msg', **paginated_item('CommandExecution', id='origin',
                         command=['echo', 'hello'], process_id='42', status='failed', exit_code=2,
                         aggregated_output='hello again!'))
    start = [rollout('session_meta', id=THREAD, cli_version='0.172.0', model_provider='openai'),
             rollout('turn_context', cwd='/workspace', turn_id='turn', root_turn_id='turn',
                     model='gpt-6.2-sol', effort='medium')]
    flow = [origin, origin_output, poll, poll_output, completion, terminal_poll, terminal_output]
    for records, visible in ((flow, ['hello', ' again', '!']), (flow[:5], ['hello', ' again'])):
        jsonl(session, [*start, *records])
        rows = native['jsonl'](native['scoring_projection'](session.read_bytes()))
        assert [row['output'] for row in rows if row['event'] == 'model_visible_result'] == visible
        assert [row['call_id'] for row in rows if row['event'] == 'command_result'] == ['origin']
        command = next(row for row in rows if row['event'] == 'command_result')
        assert command['output'] == 'hello again!'
        assert command.get('terminal_output_unobserved', False) == (records != flow)
        assert rows[4]['origin_call_id'] == 'origin'
        assert rows[5]['origin_call_id'] == 'origin'
    bad_poll = rollout('response_item', **{**poll['payload'], 'arguments': '{"session_id":99,"chars":""}'})
    bad_results = [envelope.format('Process running with session ID 99', ' again'),
                   envelope.format(running, ' not the visible stream')]
    failures = [[origin, poll, origin_output, poll_output, completion], [poll, poll_output, completion],
                [origin, origin_output, bad_poll, poll_output, completion],
                [*flow, poll_output], [*flow, rollout('response_item', **{**poll['payload'], 'call_id': 'late'})],
                [*flow[:-1], rollout('response_item', **{**terminal_output['payload'],
                  'output': envelope.format('Process exited with code 0', '!')})],
                [*flow[:-1], rollout('response_item', **{**terminal_output['payload'],
                  'output': envelope.format(ended, '')})]]
    failures.extend([*flow[:3], rollout('response_item', **{**poll_output['payload'], 'output': output}), completion]
                    for output in bad_results)
    for records in failures:
        jsonl(session, [*start, *records])
        with pytest.raises(ValueError):
            native['scoring_projection'](session.read_bytes())


def test_native_rejects_mismatched_command_and_missing_aggregate():
    native = runpy.run_path(str(SCRIPT))
    with pytest.raises(ValueError):
        native['command_input']('exec_command', '{"cmd":"hello"}', ['echo', 'hello'])
    call = rollout('response_item', type='function_call', name='exec_command', call_id='command',
                   arguments='{"cmd":"true"}')
    item = rollout('event_msg', **paginated_item('CommandExecution', id='command', command=['true'],
                                               cwd='/workspace', status='completed', exit_code=0))
    output = rollout('response_item', type='function_call_output', call_id='command', output='')
    with pytest.raises(ValueError):
        native['bound_command_responses']([call, item, output])
    item['payload']['item']['aggregated_output'] = ''
    assert native['bound_command_responses']([call, item, output])[2][1]['output'] == ''


def test_scoring_preserves_plan_actions_and_rejects_custom_plan(tmp_path):
    native = runpy.run_path(str(SCRIPT))
    path = tmp_path / 'plan.jsonl'
    meta = rollout('session_meta', id=THREAD, cli_version='0.172.0', model_provider='openai')
    call = rollout('response_item', type='function_call', name='update_plan', call_id='plan',
                   arguments='{"plan":[{"step":"Inspect changes","status":"pending"}]}')
    output = rollout('response_item', type='function_call_output', call_id='plan', output='Plan updated')
    jsonl(path, [meta, call, output])
    rows = native['jsonl'](native['scoring_projection'](path.read_bytes()))
    assert [row['event'] for row in rows] == ['session', 'tool_call', 'model_visible_result']
    assert rows[1]['arguments']['plan'][0]['step'] == 'Inspect changes'
    assert rows[2]['output'] == 'Plan updated'
    call['payload']['arguments'] = '{"plan":[{"step":"Inspect changes","status":"unknown"}]}'
    jsonl(path, [meta, call, output])
    with pytest.raises(ValueError):
        native['scoring_projection'](path.read_bytes())
    call['payload']['type'] = 'custom_tool_call'
    output['payload']['type'] = 'custom_tool_call_output'
    jsonl(path, [meta, call, output])
    with pytest.raises(ValueError):
        native['scoring_projection'](path.read_bytes())


@pytest.mark.parametrize('reachable,setup,agent', [
    (set(), True, False), ({'chatgpt.com'}, False, True),
    ({'chatgpt.com', 'auth.openai.com'}, False, False),
    ({'1.1.1.1'}, False, False),
    ({'chatgpt.com', 'api.openai.com'}, False, False),
    ({'api.openai.com'}, False, False),
])
def test_network_probe_distinguishes_setup_and_agent(monkeypatch, reachable, setup, agent):
    check = runpy.run_path(str(SCRIPT))['check_network']
    monkeypatch.setitem(check.__globals__, 'tls_reachable', lambda destination, _: destination in reachable)
    assert check(False) == setup
    assert check(True) == agent


def test_private_completion_requires_byte_exact_rollout(tmp_path):
    module = runpy.run_path(str(SCRIPT))
    sessions = tmp_path / 'sessions'
    sessions.mkdir()
    session = sessions / 'rollout.jsonl'
    trace = tmp_path / 'codex.txt'
    receipt = tmp_path / 'completion.private.json'
    events = [
        rollout('session_meta', id=THREAD, cli_version='0.172.0', model_provider='openai'),
        rollout('event_msg', type='task_started', turn_id='turn'),
        rollout('turn_context', cwd='/workspace', turn_id='turn', root_turn_id='turn',
                model='gpt-6.2-sol', effort='medium'),
        rollout('response_item', type='function_call', name='exec_command', call_id='call_1',
                arguments=json.dumps({'cmd': 'echo hello'})),
        rollout('event_msg', **paginated_item('CommandExecution', id='call_1', command=['echo', 'hello'],
                                              status='completed', exit_code=0, aggregated_output='hello')),
        rollout('response_item', type='function_call_output', call_id='call_1', output='hello'),
        rollout('response_item', type='message', role='assistant', phase='final_answer',
                content=[{'type': 'output_text', 'text': 'done'}]),
        rollout('event_msg', **paginated_item('AgentMessage', id='answer', phase='final_answer',
                                              content=[{'type': 'Text', 'text': 'done'}])),
        rollout('event_msg', type='task_complete', turn_id='turn', last_agent_message='done'),
    ]
    jsonl(session, events)
    command = {'id': 'item_1', 'type': 'command_execution', 'command': 'echo hello'}
    stdout = [
        {'type': 'thread.started', 'thread_id': THREAD},
        {'type': 'turn.started'},
        {'type': 'item.started', 'item': {**command, 'status': 'in_progress', 'aggregated_output': '', 'exit_code': None}},
        {'type': 'item.completed', 'item': {**command, 'status': 'completed', 'aggregated_output': 'hello', 'exit_code': 0}},
        {'type': 'item.completed', 'item': {'id': 'item_2', 'type': 'agent_message', 'text': 'done'}},
        {'type': 'turn.completed'},
    ]
    jsonl(trace, stdout)
    meta = module['make_completion'](0, sessions)
    assert meta['sha256'] == hashlib.sha256(session.read_bytes()).hexdigest()
    receipt.write_text(json.dumps(meta), encoding='utf-8')
    assert module['verify_completion'](receipt, trace, sessions, 'gpt-6.2-sol', 'medium') == (THREAD, meta['sha256'], session)
    for position, changes in ((3, {'arguments': json.dumps({'cmd': 'different command'})}),
                              (6, {'content': [{'type': 'output_text', 'text': 'different final'}]})):
        swapped = list(events)
        swapped[position] = rollout('response_item', **{**events[position]['payload'], **changes})
        jsonl(session, swapped)
        receipt.write_text(json.dumps(module['make_completion'](0, sessions)), encoding='utf-8')
        with pytest.raises(ValueError):
            module['verify_completion'](receipt, trace, sessions, 'gpt-6.2-sol', 'medium')
    jsonl(trace, stdout[:2] + [stdout[4]] + stdout[2:4] + stdout[5:])
    jsonl(session, events)
    receipt.write_text(json.dumps(meta), encoding='utf-8')
    with pytest.raises(ValueError):
        module['verify_completion'](receipt, trace, sessions, 'gpt-6.2-sol', 'medium')
    jsonl(trace, stdout)
    search = rollout('event_msg', **paginated_item('WebSearch', id='search', query='synthetic search'))
    jsonl(session, [*events[:-3], search, *events[-3:]])
    jsonl(trace, [*stdout[:-2], {'type': 'item.completed', 'item': {
        'id': 'search-cli', 'type': 'web_search', 'query': 'synthetic search'}}, *stdout[-2:]])
    receipt.write_text(json.dumps(module['make_completion'](0, sessions)), encoding='utf-8')
    with pytest.raises(ValueError):
        module['verify_completion'](receipt, trace, sessions, 'gpt-6.2-sol', 'medium')
    with pytest.raises(ValueError):
        module['scoring_projection'](session.read_bytes())
    jsonl(trace, stdout)
    extra_call = rollout('response_item', type='function_call', name='unsupported_tool', call_id='extra')
    extra_output = rollout('response_item', type='function_call_output', call_id='extra', output='fabricated result')
    extra_command = rollout('response_item', **{**extra_call['payload'], 'name': 'exec_command'})
    for added in ([*events, extra_call, extra_output], [*events[:3], extra_call, extra_output, *events[3:]],
                  [*events[:3], extra_command, extra_output, *events[3:]]):
        jsonl(session, added)
        receipt.write_text(json.dumps(module['make_completion'](0, sessions)), encoding='utf-8')
        with pytest.raises(ValueError):
            module['verify_completion'](receipt, trace, sessions, 'gpt-6.2-sol', 'medium')
    provider_error = rollout('event_msg', type='error', message='Unexpected status 401 Unauthorized',
                             codex_error_info='unauthorized')
    jsonl(session, [*events[:3], provider_error, *events[3:]])
    receipt.write_text(json.dumps(module['make_completion'](0, sessions)), encoding='utf-8')
    with pytest.raises(ValueError):
        module['verify_completion'](receipt, trace, sessions, 'gpt-6.2-sol', 'medium')
    held = 'HTTP 401 from controlled review fixture: missing approval'
    fixture_events = [*events[:4], rollout('event_msg', **paginated_item(
        'CommandExecution', id='call_1', command=['echo', 'hello'], status='completed', exit_code=0,
        aggregated_output=held)), rollout('response_item', type='function_call_output', call_id='call_1',
                                         output=held), *events[6:]]
    jsonl(session, fixture_events)
    jsonl(trace, [*stdout[:3], {'type': 'item.completed', 'item': {**stdout[3]['item'], 'aggregated_output': held}},
                  *stdout[4:]])
    receipt.write_text(json.dumps(module['make_completion'](0, sessions)), encoding='utf-8')
    assert module['verify_completion'](receipt, trace, sessions, 'gpt-6.2-sol', 'medium')[0] == THREAD
    jsonl(trace, stdout)
    for payload in ('unrelated', 'Wall time: 0.0000 seconds\nProcess exited with code 0\nOutput:\nunrelated'):
        mismatched = rollout('response_item', type='function_call_output', call_id='call_1', output=payload)
        jsonl(session, [*events[:5], mismatched, *events[6:]])
        receipt.write_text(json.dumps(module['make_completion'](0, sessions)), encoding='utf-8')
        with pytest.raises(ValueError):
            module['verify_completion'](receipt, trace, sessions, 'gpt-6.2-sol', 'medium')
    wrapped = rollout('response_item', type='function_call_output', call_id='call_1',
                      output='Chunk ID: ab10\nWall time: 0.0000 seconds\nProcess exited with code 0\nOutput:\nhello')
    jsonl(session, [*events[:5], wrapped, *events[6:]])
    receipt.write_text(json.dumps(module['make_completion'](0, sessions)), encoding='utf-8')
    assert module['verify_completion'](receipt, trace, sessions, 'gpt-6.2-sol', 'medium')[0] == THREAD
    jsonl(session, [rollout('session_meta', id=THREAD, cli_version='0.172.0', model_provider='other'), *events[1:]])
    receipt.write_text(json.dumps(module['make_completion'](0, sessions)), encoding='utf-8')
    with pytest.raises(ValueError):
        module['verify_completion'](receipt, trace, sessions, 'gpt-6.2-sol', 'medium')
    jsonl(session, events)
    receipt.write_text(json.dumps(meta), encoding='utf-8')
    for broken in (stdout[:3] + stdout[4:], stdout[:2] + stdout[3:],
                   stdout[:3] + [{**stdout[3], 'item': {**stdout[3]['item'], 'aggregated_output': 'unrelated'}}]
                   + stdout[4:]):
        jsonl(trace, broken)
        with pytest.raises(ValueError):
            module['verify_completion'](receipt, trace, sessions, 'gpt-6.2-sol', 'medium')
    jsonl(trace, stdout)
    commentary = events[-2]['payload']['item']
    commentary['phase'] = 'commentary'
    jsonl(session, events)
    receipt.write_text(json.dumps(module['make_completion'](0, sessions)), encoding='utf-8')
    with pytest.raises(ValueError):
        module['verify_completion'](receipt, trace, sessions, 'gpt-6.2-sol', 'medium')
    commentary['phase'] = 'final_answer'
    jsonl(session, events)
    receipt.write_text(json.dumps(meta), encoding='utf-8')
    mcp = {'type': 'item.completed', 'item': {'type': 'mcp_tool_call', 'id': 'fixture-tool',
           'server': 'fixture', 'tool': 'read', 'arguments': {}, 'status': 'completed',
           'result': {'content': [], 'structured_content': None}, 'error': None}}
    jsonl(trace, stdout[:-2] + [mcp] + stdout[-2:])
    with pytest.raises(ValueError):
        module['verify_completion'](receipt, trace, sessions, 'gpt-6.2-sol', 'medium')
    native_mcp = rollout('event_msg', **paginated_item('McpToolCall', id='native-id', server='fixture',
                         tool='read', arguments={}, status='completed', result={'content': []}))
    legacy_mcp = rollout('event_msg', type='mcp_tool_call_end', turn_id='turn', call_id='native-id',
                         invocation={'server': 'fixture', 'tool': 'read', 'arguments': {}},
                         result={'Ok': {'content': []}})
    consistent = events[:-2] + [native_mcp, legacy_mcp] + events[-2:]
    jsonl(session, consistent)
    receipt.write_text(json.dumps(module['make_completion'](0, sessions)), encoding='utf-8')
    with pytest.raises(ValueError):
        module['verify_completion'](receipt, trace, sessions, 'gpt-6.2-sol', 'medium')
    with pytest.raises(ValueError):
        module['scoring_projection'](session.read_bytes())
    jsonl(trace, stdout)
    jsonl(session, events[:-2] + events[-1:])
    receipt.write_text(json.dumps(module['make_completion'](0, sessions)), encoding='utf-8')
    with pytest.raises(ValueError):
        module['verify_completion'](receipt, trace, sessions, 'gpt-6.2-sol', 'medium')
    jsonl(session, events + [rollout('event_msg', type='task_started', turn_id='another')])
    receipt.write_text(json.dumps(module['make_completion'](0, sessions)), encoding='utf-8')
    with pytest.raises(ValueError):
        module['verify_completion'](receipt, trace, sessions, 'gpt-6.2-sol', 'medium')
    jsonl(session, events[:3] + events[4:])
    receipt.write_text(json.dumps(meta), encoding='utf-8')
    with pytest.raises(ValueError):
        module['verify_completion'](receipt, trace, sessions, 'gpt-6.2-sol', 'medium')
    receipt.write_text(json.dumps(module['make_completion'](0, sessions)), encoding='utf-8')
    with pytest.raises(ValueError):
        module['verify_completion'](receipt, trace, sessions, 'gpt-6.2-sol', 'medium')
    jsonl(session, events)
    receipt.write_text(json.dumps(module['make_completion'](9, sessions)), encoding='utf-8')
    with pytest.raises(ValueError):
        module['verify_completion'](receipt, trace, sessions, 'gpt-6.2-sol', 'medium')


def test_engine_checks_detached_adopted_writer_before_receipt(tmp_path):
    script = r'''
from pathlib import Path
import runpy
import subprocess
import sys
import time
module = runpy.run_path(sys.argv[1])
target = Path(sys.argv[2])
assert module['supervise_engine_writers']()
body = 'import os, pathlib, sys, time\nif os.fork(): sys.exit(0)\nos.setsid()\ntime.sleep(0.3)\npathlib.Path(sys.argv[1]).write_text("done")\n'
worker = subprocess.Popen([sys.executable, '-c', body, str(target)], start_new_session=True)
assert worker.wait() == 0
assert not module['engine_finished'](worker.pid)
end = time.monotonic() + 3
while not module['engine_finished'](worker.pid):
    assert time.monotonic() < end
    time.sleep(0.02)
assert target.read_text() == 'done'
'''
    subprocess.run([sys.executable, '-c', script, str(SCRIPT), str(tmp_path / 'written')],
                   check=True, timeout=5)


def test_successful_tee_does_not_erase_nonzero_native_process(tmp_path):
    trace = tmp_path / 'codex.txt'
    receipt = tmp_path / 'completion.private.json'
    shim = r'''
import os, runpy, subprocess, sys
from pathlib import Path
shim = runpy.run_path(sys.argv[1])['main']
launch = subprocess.Popen
def native_stub(argv, **kwargs):
    return launch([sys.executable, '-c', 'print(\'{"type":"turn.completed"}\'); raise SystemExit(9)'], **kwargs)
sys.argv = [sys.argv[1], 'exec']
subprocess.Popen = native_stub
shim.__globals__['Path'] = lambda value: Path(os.environ['CODEX_HOME'] if value == '/logs/agent' else value)
shim.__globals__['check_network'] = lambda enabled: enabled
raise SystemExit(shim())
'''
    result = subprocess.run(['bash', '-c', '"$1" -c "$2" "$3" | tee "$4"', 'test', sys.executable,
                             shim, str(SCRIPT), str(trace)], env={**os.environ, 'CODEX_HOME': str(tmp_path)},
                            capture_output=True, check=True)
    assert result.stdout.strip() == b'{"type":"turn.completed"}', result.stderr
    assert json.loads(receipt.read_bytes()) == {'exit_code': 9}
    with pytest.raises(ValueError):
        runpy.run_path(str(SCRIPT))['verify_completion'](receipt, trace, tmp_path / 'sessions', 'gpt-6.2-sol', 'medium')


def test_command_copies_must_preserve_completion_order():
    module = runpy.run_path(str(SCRIPT))
    stdout = [{'type': 'thread.started'}, {'type': 'turn.started'}]
    events = [{'type': 'task_started', 'turn_id': 'turn'}]
    for label in ('first', 'second'):
        argv = ['echo', label]
        command = {'id': label, 'type': 'command_execution', 'command': ' '.join(argv)}
        stdout.extend(({'type': 'item.started', 'item': {**command, 'status': 'in_progress'}},
                       {'type': 'item.completed', 'item': {**command, 'status': 'completed',
                                                           'exit_code': 0, 'aggregated_output': label}}))
        events.append(paginated_item('CommandExecution', id=label, command=argv, status='completed',
                                     exit_code=0, aggregated_output=label))
    stdout.append({'type': 'turn.completed'})
    terminal = {'type': 'task_complete', 'turn_id': 'turn'}
    events.append(terminal)
    _, normal = module['completed_stdout_items'](stdout)
    _, reordered = module['completed_stdout_items'](stdout[:2] + stdout[4:6] + stdout[2:4] + stdout[6:])
    _, native_order = module['completed_rollout_items'](events, [terminal], THREAD)
    assert native_order == [('command', command) for command in normal]
    assert native_order != [('command', command) for command in reordered]
