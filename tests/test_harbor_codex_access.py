import base64
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'harbor_codex_access.py'
SPEC = importlib.util.spec_from_file_location('harbor_codex_access', SCRIPT)
access = importlib.util.module_from_spec(SPEC)

ACCOUNT = 'synthetic-account-42'
GRANT = 'fake-grant-"/\\-é'
NOW = 1_800_000_000
REFRESH = '2026-02-03T01:02:03.123456789+00:00'
CLAIM = 'https://api.openai.com/auth'


def jwt(claims):
    def segment(raw):
        return base64.urlsafe_b64encode(raw).rstrip(b'=').decode()

    return '.'.join((segment(b'{"alg":"RS256"}'), segment(json.dumps(claims).encode()), segment(b'fake-signature')))


def bearer(*, account=ACCOUNT, expiry=NOW + 5000):
    claims = {} if expiry is None else {'exp': expiry}
    if account is not None:
        claims[CLAIM] = {'chatgpt_account_id': account}
    return jwt(claims)


def test_rollout_reasoning_part_arrays_are_joined_and_type_checked():
    for field, kind in (('summary', 'summary_text'), ('content', 'text')):
        parts = [{'type': kind, 'text': 'first '}, {'type': kind, 'text': 'second'}]
        record = rollout('response_item', type='reasoning', summary=[], encrypted_content=None)
        record['payload'][field] = parts
        data = jsonl(record)
        assert access.sanitize_bytes(data, (ACCOUNT,), 'native_rollout') == b''
        parts[0]['text'], parts[1]['text'] = ACCOUNT[:7], ACCOUNT[7:]
        with pytest.raises(ValueError):
            access.sanitize_bytes(jsonl(record), (ACCOUNT,), 'native_rollout')
        parts[0]['type'], parts[0]['text'] = 'unknown-fragment', 'ordinary'
        with pytest.raises(ValueError):
            access.sanitize_bytes(jsonl(record), (ACCOUNT,), 'native_rollout')


def auth():
    return {'auth_mode': 'chatgpt', 'OPENAI_API_KEY': None, 'last_refresh': REFRESH,
            'tokens': {'account_id': ACCOUNT, 'id_token': jwt({CLAIM: {'chatgpt_account_id': ACCOUNT}}),
                       'access_token': bearer(), 'refresh_token': GRANT}}


@pytest.fixture(scope='module', autouse=True)
def load_helper():
    SPEC.loader.exec_module(access)


def prepare(tmp_path, source, *, mode=0o600, expected=ACCOUNT, wait=900, clock=lambda: NOW):
    source_path = tmp_path / 'fake-auth.json'
    raw = source if isinstance(source, bytes) else json.dumps(source).encode()
    source_path.write_bytes(raw)
    source_path.chmod(mode)
    with source_path.open('rb') as handle:
        handle.seek(2)
        try:
            return access.prepare_derivative(handle.fileno(), expected, wait, clock)
        finally:
            assert handle.tell() == 2
            assert source_path.read_bytes() == raw
            assert set(tmp_path.iterdir()) == {source_path}


def test_selected_profile_freezes_account_and_rejects_later_account_change(tmp_path):
    selected = tmp_path / 'selected-auth.json'
    original = auth()
    selected.write_text(json.dumps(original))
    selected.chmod(0o600)
    with selected.open('rb') as stream:
        expected = access.freeze_profile_account(stream.fileno())
        assert expected == ACCOUNT
        assert access.prepare_derivative(stream.fileno(), expected, 900, lambda: NOW)[0]

    other = 'different-synthetic-account'
    original['tokens'].update(account_id=other, access_token=bearer(account=other),
                              id_token=jwt({CLAIM: {'chatgpt_account_id': other}}))
    selected.write_text(json.dumps(original))
    with selected.open('rb') as stream:
        with pytest.raises(ValueError, match='stored account mismatch'):
            access.prepare_derivative(stream.fileno(), expected, 900, lambda: NOW)

    original['tokens']['access_token'] = bearer(account=None)
    selected.write_text(json.dumps(original))
    with selected.open('rb') as stream:
        with pytest.raises(ValueError, match='missing or malformed JWT account namespace'):
            access.freeze_profile_account(stream.fileno())


@pytest.mark.skipif(not hasattr(os, 'memfd_create'), reason='Linux private descriptor')
def test_account_reference_is_sealed_and_inheritable_without_account_argv(tmp_path):
    selected = tmp_path / 'selected-auth.json'
    selected.write_text(json.dumps(auth()))
    selected.chmod(0o600)
    with selected.open('rb') as source:
        descriptor = access.freeze_account_descriptor(source.fileno(), selected)
    try:
        assert os.fstat(descriptor).st_nlink == 0
        assert not os.get_inheritable(descriptor)
        assert access.read_account_reference(descriptor, selected) == ACCOUNT
        with pytest.raises(ValueError, match='profile path changed'):
            access.read_account_reference(descriptor, tmp_path / 'same-account-other-profile')
        with pytest.raises(PermissionError):
            os.pwrite(descriptor, b'changed', 0)
        command = ('import sys; from harbor_codex_access import read_account_reference; '
                   'print(len(read_account_reference(int(sys.argv[1]), sys.argv[2])))')
        env = dict(os.environ, PYTHONPATH=str(SCRIPT.parent))
        args = [sys.executable, '-c', command, str(descriptor), str(selected)]
        child = subprocess.run(args, env=env, pass_fds=(descriptor,), capture_output=True, check=True)
        assert child.stdout == f'{len(ACCOUNT)}\n'.encode()
        assert not child.stderr and ACCOUNT not in ' '.join(args)
    finally:
        os.close(descriptor)


def test_managed_file_derivative_is_exact_and_memory_only(tmp_path):
    original = auth()
    derivative, private = prepare(tmp_path, original)
    tokens = original['tokens']
    assert json.loads(derivative) == {'auth_mode': 'chatgpt', 'last_refresh': REFRESH,
                                     'tokens': {**tokens, 'refresh_token': ''}}
    assert set(private) == {tokens['access_token'], tokens['id_token'], ACCOUNT, GRANT}
    assert b'OPENAI_API_KEY' not in derivative and b'fake-grant' not in derivative


def test_released_plain_text_obeys_transformed_byte_limit(monkeypatch):
    private = ('secret',)
    monkeypatch.setattr(access, 'MAX_ARTIFACT_BYTES', len(access.MASK))
    assert access.sanitize_bytes(b'secret', private, 'text') == access.MASK.encode()
    with pytest.raises(access.AccessError, match='release exceeds size'):
        access.sanitize_bytes(b'!secret', private, 'text')


def test_known_source_only_metadata_is_not_copied(tmp_path):
    original = auth()
    original['tokens'].update(login_owner_id='fake-login-owner', oauth_provenance={
        'issuer': 'https://synthetic.invalid', 'client_id': 'fake-client',
    })
    original['tokens']['id_token'] = jwt({'email': 'synthetic@example.invalid'})
    derivative, _ = prepare(tmp_path, original)
    assert set(json.loads(derivative)['tokens']) == {'id_token', 'access_token', 'refresh_token', 'account_id'}
    assert b'fake-login-owner' not in derivative and b'fake-client' not in derivative


@pytest.mark.parametrize('source', [
    {**auth(), 'auth_mode': 'chatgptTokens'}, {**auth(), 'auth_mode': 'apikey'},
    {**auth(), 'OPENAI_API_KEY': 'fake-key'}, {**auth(), 'unrecognized': 'unknown'},
    {**auth(), 'last_refresh': '2026-02-30T12:00:00Z'}, {**auth(), 'last_refresh': '2026-02-03'},
    {**auth(), 'tokens': {**auth()['tokens'], 'alternate': 'fake-token'}},
    {**auth(), 'tokens': {**auth()['tokens'], 'refresh_token': ''}},
    {**auth(), 'tokens': {**auth()['tokens'], 'id_token': 'not-a-jwt'}},
    {**auth(), 'tokens': {**auth()['tokens'], 'account_id': 'fake-other'}},
    {**auth(), 'tokens': {**auth()['tokens'], 'access_token': bearer(account='fake-other')}},
    {**auth(), 'tokens': {**auth()['tokens'], 'access_token': bearer(account=None)}},
    {**auth(), 'tokens': {**auth()['tokens'], 'id_token': jwt({CLAIM: {'chatgpt_account_id': 'fake-other'}})}},
    {**auth(), 'tokens': {**auth()['tokens'], 'access_token': bearer(expiry=None)}},
    {**auth(), 'tokens': {**auth()['tokens'], 'access_token': bearer(expiry=True)}},
    {**auth(), 'tokens': {**auth()['tokens'], 'access_token': bearer(expiry=NOW - 1)}},
    b'{"auth_mode":"apikey","auth_mode":"chatgpt"}',
])
def test_bad_auth_is_rejected_without_fallback_or_private_diagnostics(tmp_path, source, monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'synthetic-environment-fallback')
    with pytest.raises(access.AccessError) as raised:
        prepare(tmp_path, source)
    assert raised.value.__cause__ is None
    assert all(secret not in str(raised.value) for secret in (ACCOUNT, GRANT, 'fake-other', bearer()))


@pytest.mark.parametrize('options', [
    {'mode': 0o640}, {'mode': 0o400}, {'expected': ''}, {'expected': 'fake-other'},
    {'wait': 0}, {'wait': True}, {'clock': lambda: float('nan')},
])
def test_admission_inputs_fail_closed(tmp_path, options):
    with pytest.raises(access.AccessError):
        prepare(tmp_path, auth(), **options)


def test_auth_rejects_unowned_file(tmp_path, monkeypatch):
    monkeypatch.setattr(access.os, 'geteuid', lambda: os.getuid() + 1)
    with pytest.raises(access.AccessError, match='not owned'):
        prepare(tmp_path, auth())


def test_wait_budget_keeps_clock_and_cleanup_allowances(tmp_path):
    original = auth()
    original['tokens']['access_token'] = bearer(expiry=NOW + 900 + 300)
    with pytest.raises(access.AccessError):
        prepare(tmp_path, original)
    expiry = NOW + 900 + access.REFRESH_WINDOW_SECONDS + access.CLOCK_UNCERTAINTY_SECONDS + access.CLEANUP_SECONDS
    original['tokens']['access_token'] = bearer(expiry=expiry)
    with pytest.raises(access.AccessError):
        prepare(tmp_path, original)
    assert prepare(tmp_path, original, clock=lambda: NOW - 1)[0]


def test_nonregular_and_hardlinked_descriptors_are_rejected(tmp_path):
    source = tmp_path / 'fake-auth.json'
    source.write_text(json.dumps(auth()))
    source.chmod(0o600)
    (tmp_path / 'alias').hardlink_to(source)
    with source.open('rb') as handle, pytest.raises(access.AccessError):
        access.read_artifact(handle.fileno())
    with source.open('rb') as handle, pytest.raises(access.AccessError):
        access.prepare_derivative(handle.fileno(), ACCOUNT, 900, lambda: NOW)
    directory_fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        with pytest.raises(access.AccessError):
            access.read_artifact(directory_fd)
    finally:
        os.close(directory_fd)


def jsonl(*records):
    return ''.join(json.dumps(record, ensure_ascii=True) + '\n' for record in records).encode()


def test_text_chunks_and_normalized_json_are_redacted_independently():
    values = (ACCOUNT, GRANT, bearer())
    raw = f'{ACCOUNT} {json.dumps(GRANT)} {bearer()} end'.encode()
    released = access.sanitize_bytes(b''.join(raw[index:index + 3] for index in range(0, len(raw), 3)), values, 'text')
    assert released == b'[REDACTED] "[REDACTED]" [REDACTED] end'
    raw_json = ('{"metadata":{"account":"\\u0073ynthetic-account-42","nested":'
                + json.dumps({'copied': f'{GRANT} and {bearer()}'}) + '}}').encode()
    released = access.sanitize_bytes(raw_json, values, 'json')
    assert json.loads(released) == {'metadata': {'account': '[REDACTED]',
                                                'nested': {'copied': '[REDACTED] and [REDACTED]'}}}
    assert access.sanitize_bytes(released, values, 'json') == released


def test_doubly_serialized_json_strings_and_keys_are_sanitized():
    source = {GRANT: json.dumps({'innermost': GRANT})}
    released = json.loads(access.sanitize_bytes(json.dumps(source).encode(), (GRANT,), 'json'))
    assert json.loads(released['[REDACTED]']) == {'innermost': '[REDACTED]'}


@pytest.mark.parametrize(('data', 'format_name'), [
    (b'\xff', 'text'), (b'hello\x00', 'text'), (b'{broken}', 'json'),
    (b'{"duplicated":1,"duplicated":2}', 'json'), (b'{"x":NaN}', 'json'),
    (b'{"x":1e999}', 'json'), (b'{"x":"\\ud800"}', 'json'),
    (b'{"synthetic-account-42":1,"[REDACTED]":2}', 'json'),
    (b'{"x":1}\n{"x":2', 'jsonl'), (b'{}\n\n{}\n', 'jsonl'),
    (b'{}\n', 'binary'),
])
def test_unsupported_content_is_withheld(data, format_name):
    with pytest.raises(access.AccessError):
        access.sanitize_bytes(data, (ACCOUNT,), format_name)


@pytest.mark.parametrize('name', [
    '/abs.txt', '../escape.txt', 'dir//file.json', 'dir/./file.json', 'dir\\file.log',
    'dir/secret\x1b.log', 'dir/unexpected.zip', f'{ACCOUNT}/result.json',
    f'dir/{json.dumps(GRANT)[1:-1]}.txt',
])
def test_unsafe_artifact_names_are_withheld_without_echo(name):
    with pytest.raises(access.AccessError) as raised:
        access.safe_artifact_format(name, (ACCOUNT, GRANT))
    assert name not in str(raised.value)


def test_safe_artifact_names_and_bounded_read(tmp_path, monkeypatch):
    assert access.safe_artifact_format('job/trial', (ACCOUNT,), directory=True) is None
    assert access.safe_artifact_format('job/trial/stdout.log', (ACCOUNT,)) == 'log'
    assert access.safe_artifact_format('job/trial/result.json', (ACCOUNT,)) == 'json'
    assert access.safe_artifact_format('job/trial/session.jsonl', (ACCOUNT,)) == 'jsonl'
    source = tmp_path / 'stdout.log'
    source.write_bytes(b'01234')
    with source.open('rb') as handle:
        assert access.read_artifact(handle.fileno()) == b'01234'
        monkeypatch.setattr(access, 'MAX_ARTIFACT_BYTES', 4)
        with pytest.raises(access.AccessError):
            access.read_artifact(handle.fileno())


def rollout(record_type, **payload):
    return {'timestamp': '2026-02-03T01:02:03Z', 'type': record_type, 'payload': payload}


def event(event_type, **payload):
    return rollout('event_msg', type=event_type, **payload)


def assistant_fragments(first, second, *, complete=None):
    identifiers = {'thread_id': 'fake-thread', 'turn_id': 'fake-turn'}
    return (
        rollout('session_meta', id='fake-thread'),
        event('task_started', turn_id='fake-turn'),
        event('agent_message_content_delta', **identifiers, item_id='fake-item', delta=first),
        event('agent_message_content_delta', **identifiers, item_id='fake-item', delta=second),
        event('item_completed', **identifiers, item={'id': 'fake-item', 'type': 'AgentMessage',
              'content': [{'type': 'Text', 'text': first + second if complete is None else complete}]}),
        event('task_complete', turn_id='fake-turn'),
    )


def test_rollout_plain_fragments_join_and_match_complete_output():
    records = assistant_fragments('clean ', 'évidence')
    released = access.sanitize_bytes(jsonl(*records), (GRANT, ACCOUNT), 'native_rollout')
    assert [json.loads(line) for line in released.splitlines()] == list(records)
    with pytest.raises(access.AccessError):
        access.sanitize_bytes(jsonl(*assistant_fragments('clean ', 'évidence', complete='different')),
                              (GRANT,), 'native_rollout')


def test_rollout_projection_removes_reasoning_but_preserves_scoring_records():
    header, start, first, second, final, end = assistant_fragments('usable ', 'evidence')
    omitted = (
        rollout('response_item', type='reasoning', summary=[], encrypted_content='opaque-reasoning'),
        event('agent_reasoning', text='summary private to acquisition'),
        event('agent_reasoning_raw_content', text=ACCOUNT),
        event('item_completed', thread_id='fake-thread', turn_id='fake-turn',
              item={'id': 'reasoning-id', 'type': 'Reasoning', 'summary_text': ['reasoning'],
                    'raw_content': ['reasoning']})
    )
    records = tuple(dict(record, ordinal=index) for index, record in enumerate(
        (header, start, *omitted, first, second, final, end)))
    released = access.sanitize_bytes(jsonl(*records), (ACCOUNT,), 'native_rollout')
    assert [json.loads(line) for line in released.splitlines()] == list(records[:2] + records[6:])


def test_rollout_accepts_pinned_paginated_envelopes_and_scans_response_metadata():
    header, turn, first, second, finish, end = assistant_fragments('clean ', 'evidence')
    response = rollout('response_item', type='message', role='developer',
                       content=[{'type': 'input_text', 'text': 'source instructions'}])
    response['metadata'] = {'history_sequence': 2, 'sampled_through_sequence': 1,
                            'retained_source': {'source_id': ACCOUNT}}
    records = [dict(record, ordinal=index) for index, record in
               enumerate((header, turn, response, first, second, finish, end))]
    with pytest.raises(access.AccessError, match='required native evidence'):
        access.sanitize_bytes(jsonl(*records), (ACCOUNT,), 'native_rollout')
    response['metadata']['retained_source']['source_id'] = 'clean-source'
    released = access.sanitize_bytes(jsonl(*records), (ACCOUNT,), 'native_rollout')
    sanitized = [json.loads(line) for line in released.splitlines()]
    assert [record['ordinal'] for record in sanitized] == list(range(len(records)))
    assert sanitized[2]['metadata']['retained_source']['source_id'] == 'clean-source'
    response['metadata']['retained_source']['extra'] = {'parts': ['synthetic-', 'account-42']}
    with pytest.raises(access.AccessError):
        access.sanitize_bytes(jsonl(*records), (ACCOUNT,), 'native_rollout')
    del response['metadata']['retained_source']['extra']
    for invalid in (dict(records[1], ordinal=True), dict(records[1], ordinal=2),
                    dict(records[1], metadata={}), turn):
        with pytest.raises(access.AccessError):
            access.sanitize_bytes(jsonl(records[0], invalid, *records[2:]), (ACCOUNT,), 'native_rollout')


def test_rollout_split_secret_in_separate_escaped_records_is_withheld():
    records = assistant_fragments('fake-grant-"', '/\\-é', complete='no full literal in any record')
    raw = jsonl(*records)
    assert json.dumps(GRANT)[1:-1].encode() not in raw
    with pytest.raises(access.AccessError, match='split'):
        access.sanitize_bytes(raw, (GRANT,), 'native_rollout')


def test_rollout_nested_json_escape_split_inside_escape_is_withheld():
    records = assistant_fragments(r'\u007', '3ynthetic-account-42', complete='no full literal in any record')
    with pytest.raises(access.AccessError, match='split'):
        access.sanitize_bytes(jsonl(*records), (ACCOUNT,), 'native_rollout')


def test_rollout_unsupported_or_unclosed_fragments_are_withheld():
    header, turn, first, second, finish, end = assistant_fragments('first', 'second')
    unknown = event('unknown_output_delta', id='fake-item', delta='second')
    wrong_item = event('agent_message_content_delta', thread_id='fake-thread', turn_id='fake-turn',
                       item_id='unknown-item', delta='second')
    for records in ((header, turn, first, unknown, finish, end), (header, turn, first, second, end),
                    (header, turn, first, wrong_item, finish, end), (first, second, finish, end)):
        with pytest.raises(access.AccessError):
            access.sanitize_bytes(jsonl(*records), (GRANT,), 'native_rollout')


def test_rollout_scans_ordered_message_content_without_joining_metadata():
    record = rollout('response_item', type='message', role='assistant',
                     content=[{'type': 'output_text', 'text': 'synthetic-'},
                              {'type': 'output_text', 'text': 'account-42'}])
    with pytest.raises(access.AccessError, match='split'):
        access.sanitize_bytes(jsonl(record), (ACCOUNT,), 'native_rollout')
    record['payload']['content'] = [{'type': 'output_text', 'text': 'synthetic-', 'metadata': 'account-42'}]
    with pytest.raises(access.AccessError, match='unsupported native content fragment'):
        access.sanitize_bytes(jsonl(record), (ACCOUNT,), 'native_rollout')


@pytest.mark.parametrize('header', ['', 'Chunk ID: ab10\nWall time: 0.0000 seconds\nProcess exited with code 0\nOutput:\n'])
def test_rollout_withholds_private_text_split_in_json_string_tool_output(header):
    call = rollout('response_item', type='function_call', name='exec_command', call_id='command')
    encoded = json.dumps({'content': [{'type': 'text', 'text': 'synthetic-'},
                                      {'type': 'text', 'text': 'account-42'}]})
    output = rollout('response_item', type='function_call_output', call_id='command', output=header + encoded)
    with pytest.raises(access.AccessError, match='split'):
        access.sanitize_bytes(jsonl(call, output), (ACCOUNT,), 'native_rollout')


@pytest.mark.parametrize('prefix,suffix', [('', ''), ('diagnostic: ', ''), ('', '\n[INFO] diagnostic text'),
    ('qualification-native-command\n', '\n[INFO] diagnostic text'),
    ('{"notice":"other output"}\n', '\n[INFO] diagnostic text')])
def test_rollout_completed_function_output_scans_embedded_json_fragments(prefix, suffix):
    encoded = json.dumps({'content': [{'type': 'text', 'text': 'synthetic-'},
                                      {'type': 'text', 'text': 'account-42'}]})
    records = (rollout('session_meta', id='fake-thread'), event('task_started', turn_id='fake-turn'),
               event('item_completed', thread_id='fake-thread', turn_id='fake-turn',
                     item={'type': 'FunctionCallOutput', 'id': 'command', 'output': prefix + encoded + suffix}),
               event('task_complete', turn_id='fake-turn'))
    with pytest.raises(access.AccessError, match='split'):
        access.sanitize_bytes(jsonl(*records), (ACCOUNT,), 'native_rollout')


def test_scoring_withholds_malformed_recognized_embedded_tool_output():
    value = {'event': 'command_result', 'call_id': 'origin', 'output': 'diagnostic: {"content": [{"type": "text"'}
    with pytest.raises(access.AccessError, match='malformed embedded tool output'):
        access.verify_scoring_release(access._json_bytes(value), (ACCOUNT,))


def test_native_exec_withholds_same_line_structured_output_fragments():
    output = 'diagnostic: ' + json.dumps({'content': [{'type': 'text', 'text': 'synthetic-'},
                                                       {'type': 'text', 'text': 'account-42'}]})
    row = {'type': 'item.completed', 'item': {'id': 'item_0', 'type': 'command_execution', 'command': 'fixture',
           'aggregated_output': output, 'status': 'completed', 'exit_code': 0}}
    with pytest.raises(access.AccessError, match='split'):
        access.sanitize_bytes(jsonl(row), (ACCOUNT,), 'native_exec')


def test_terminal_input_fragments_join_only_for_the_same_command():
    envelope = 'Chunk ID: ab10\nWall time: 0.0000 seconds\nProcess running with session ID {}\nOutput:\n'

    def rows(session_id):
        trace, native = [], []
        for name, ident, origin, session, text in (
                ('exec_command', 'alpha', None, 42, ''), ('exec_command', 'beta', None, 43, ''),
                ('write_stdin', 'send-alpha', 'alpha', 42, 'synthetic-'),
                ('write_stdin', 'send-last', 'alpha' if session_id == 42 else 'beta', session_id, 'account-42')):
            arguments = {'session_id': session, 'chars': text} if origin else {'cmd': 'fixture'}
            native.extend((rollout('response_item', type='function_call', name=name, call_id=ident,
                                   arguments=json.dumps(arguments)),
                           rollout('response_item', type='function_call_output', call_id=ident,
                                   output=envelope.format(session))))
            if origin:
                trace.append({'event': 'tool_call', 'name': name, 'call_id': ident, 'origin_call_id': origin,
                              'arguments': arguments})
        return b''.join(map(access._json_bytes, trace)), jsonl(*native)

    for session_id in (42, 43):
        scoring, raw = rows(session_id)
        checks = ((access.verify_scoring_release, (scoring, (ACCOUNT,))),
                  (access.sanitize_bytes, (raw, (ACCOUNT,), 'native_rollout')))
        for check, args in checks:
            if session_id == 42:
                with pytest.raises(access.AccessError, match='split'):
                    check(*args)
            else:
                check(*args)


def test_scoring_scans_logical_command_continuations_without_parsing_each_as_json():
    def trace(first, second):
        return b''.join(map(access._json_bytes, (
            {'event': 'model_visible_result', 'call_id': 'command', 'output': first},
            {'event': 'model_visible_result', 'call_id': 'poll', 'origin_call_id': 'command', 'output': second})))

    for first, second in (('[INFO] ', 'done'), ('[1, ', '2]'), ('{"ready": ', 'true}')):
        access.verify_scoring_release(trace(first, second), (ACCOUNT,))
    with pytest.raises(access.AccessError, match='split'):
        access.verify_scoring_release(trace('{"values":["synthetic-', '","account-42"]}'), (ACCOUNT,))


def test_native_exec_tool_snapshot_and_other_channels_mask_literal():
    record = {'type': 'item.completed', 'item': {'id': 'item_0', 'type': 'command_execution',
              'command': 'echo fake', 'aggregated_output': f'output {ACCOUNT}', 'status': 'completed', 'exit_code': 0}}
    released = access.sanitize_bytes(jsonl(record), (ACCOUNT,), 'native_exec')
    assert json.loads(released)['item']['aggregated_output'] == 'output [REDACTED]'
    with pytest.raises(access.AccessError):
        access.sanitize_bytes(jsonl({'type': 'terminal.delta', 'delta': ACCOUNT}), (ACCOUNT,), 'native_exec')
    with pytest.raises(access.AccessError):
        access.sanitize_bytes(jsonl(record), (ACCOUNT,), 'jsonl')


def test_native_exec_withholds_unsupported_mcp_progress_fragments():
    item = {'id': 'tool', 'type': 'mcp_tool_call', 'result': None}
    start = {'type': 'item.started', 'item': item}
    def record(phase, text):
        return {'type': phase, 'item': {**item, 'result': {'content': [{'type': 'text', 'text': text}]}}}
    done = record('item.completed', 'fixture response')
    access.sanitize_bytes(jsonl(start, done), (ACCOUNT,), 'native_exec')
    with pytest.raises(access.AccessError):
        access.sanitize_bytes(jsonl(start, record('item.updated', 'synthetic-'),
                                    record('item.updated', 'account-42'), done), (ACCOUNT,), 'native_exec')


@pytest.mark.parametrize('kind', ['collab_tool_call', 'file_change', 'todo_list'])
def test_native_exec_rejects_nested_progress_that_can_split_credentials(kind):
    def record(phase, value):
        return {'type': phase, 'item': {'id': 'item_0', 'type': kind, 'metadata': {'output': value}}}

    with pytest.raises(access.AccessError):
        access.sanitize_bytes(jsonl(record('item.updated', 'synthetic-'), record('item.updated', 'account-42')),
                              (ACCOUNT,), 'native_exec')


def test_native_exec_accepts_typed_todo_updates_but_checks_continuations():
    def record(value):
        return {'type': 'item.updated', 'item': {'id': 'item_0', 'type': 'todo_list',
                'items': [{'text': value, 'completed': False}]}}

    access.sanitize_bytes(jsonl(record('first'), record('second')), (ACCOUNT,), 'native_exec')
    with pytest.raises(access.AccessError, match='split across logical fragments'):
        access.sanitize_bytes(jsonl(record('synthetic-'), record('account-42')), (ACCOUNT,), 'native_exec')


@pytest.mark.parametrize('field', ['structuredContent', 'structured_content'])
def test_native_mcp_rejects_credentials_split_in_structured_result(field):
    item = {'id': 'tool', 'type': 'mcp_tool_call', 'result': {'content': [], field: {'parts': ['result', 'ok']}}}
    done = {'type': 'item.completed', 'item': item}
    access.sanitize_bytes(jsonl(done), (ACCOUNT,), 'native_exec')
    item['result'][field]['parts'] = ['synthetic-', 'account-42']
    with pytest.raises(access.AccessError, match='split'):
        access.sanitize_bytes(jsonl(done), (ACCOUNT,), 'native_exec')


def test_other_json_artifacts_withhold_split_output_values():
    nested = {'stdout': ['synthetic-', {'continued': 'account-42'}]}
    with pytest.raises(access.AccessError, match='split'):
        access.sanitize_bytes(json.dumps(nested).encode(), (ACCOUNT,), 'json')
    with pytest.raises(access.AccessError, match='split'):
        access.sanitize_bytes(jsonl({'output': 'synthetic-'}, {'output': 'account-42'}), (ACCOUNT,), 'jsonl')


def test_terminal_encoded_tool_chunks_are_correlated_and_scanned():
    def command_records(*chunks):
        return (rollout('session_meta', id='fake-thread'), event('task_started', turn_id='fake-turn'),
                event('exec_command_begin', call_id='fake-call', turn_id='fake-turn'),
                *(event('exec_command_output_delta', call_id='fake-call', stream='stdout',
                        chunk=base64.b64encode(chunk).decode()) for chunk in chunks),
                event('exec_command_end', call_id='fake-call', turn_id='fake-turn',
                      aggregated_output=b''.join(chunks).decode()), event('task_complete', turn_id='fake-turn'))

    clean = command_records(b'clean ', b'evidence')
    assert [json.loads(line) for line in access.sanitize_bytes(jsonl(*clean), (ACCOUNT,),
                                                              'native_rollout').splitlines()] == list(clean)
    completed = lambda text: event('item_completed', thread_id='fake-thread', turn_id='fake-turn',
                                   item={'id': 'fake-call', 'type': 'CommandExecution', 'aggregated_output': text})
    for sequence in (clean[:-2] + (completed('other evidence'),) + clean[-2:],
                     clean[:-1] + (completed('other evidence'),) + clean[-1:]):
        with pytest.raises(access.AccessError, match='copies disagree'):
            access.sanitize_bytes(jsonl(*sequence), (ACCOUNT,), 'native_rollout')
    access.sanitize_bytes(jsonl(*clean[:-1], completed('clean evidence'), clean[-1]), (ACCOUNT,), 'native_rollout')
    with pytest.raises(access.AccessError, match='split'):
        access.sanitize_bytes(jsonl(*command_records(b'synthetic-', b'account-42')), (ACCOUNT,), 'native_rollout')


@pytest.mark.parametrize('prefix', [b'INFO ', b'2026-11-26T21:22:05Z INFO ', b'[source] DEBUG: '])
def test_log_with_embedded_records_cannot_release_split_credential(prefix):
    entries = jsonl({'text': 'synthetic-', 'sequence': 1}, {'text': 'account-42', 'sequence': 2}).splitlines()
    mixed_log = b'\n'.join(prefix + entry for entry in entries) + b'\n'
    with pytest.raises(access.AccessError):
        access.sanitize_bytes(mixed_log, (ACCOUNT,), 'log')
    assert access.sanitize_bytes(b'normal diagnostic\n', (ACCOUNT,), 'log') == b'normal diagnostic\n'
    text = b'INFO helper described /fixture/result in the error\n'
    assert access.sanitize_bytes(text, (ACCOUNT,), 'log') == text


def test_unqualified_native_tool_output_is_rejected():
    unsupported = ({'type': 'tool_search_output', 'tools': [{'text': 'synthetic-'}, {'text': 'account-42'}]},
                   {'type': 'tool_search_output', 'tools': [{'text': 'clean'}]})
    for payload in unsupported:
        with pytest.raises(access.AccessError, match='unsupported native response item'):
            access._response_item(payload, access._private_pattern((ACCOUNT,)))


def test_harbor_atif_correlates_tool_results_across_steps():
    def trace(second):
        return json.dumps({'schema_version': 'ATIF-v1.7', 'steps': [
            {'step_id': index, 'message': 'run', 'observation': {'results': [
                {'source_call_id': 'same', 'content': fragment, 'extra': {'frame': 'metadata'}}]}}
            for index, fragment in enumerate(('synthetic-', second), 1)]}).encode()

    assert json.loads(access.sanitize_bytes(trace('safe'), (ACCOUNT,), 'atif')) == json.loads(trace('safe'))
    with pytest.raises(access.AccessError, match='split across logical fragments'):
        access.sanitize_bytes(trace('account-42'), (ACCOUNT,), 'atif')


def test_harbor_withholds_unbound_atif_observation_fragments():
    trajectory = {'schema_version': 'ATIF-v1.7', 'steps': [
        {'step_id': index, 'message': 'run', 'observation': {'results': [
            {'content': fragment, 'extra': {'frame': index}}]}}
        for index, fragment in enumerate(('synthetic-', 'account-42'), 1)]}
    with pytest.raises(access.AccessError, match='unqualified Harbor result identity'):
        access.sanitize_bytes(json.dumps(trajectory).encode(), (ACCOUNT,), 'atif')


def test_terminal_input_requires_consistent_process_and_is_scanned():
    def terminal_records(first, second, process='fake-process'):
        return (rollout('session_meta', id='fake-thread'), event('task_started', turn_id='fake-turn'),
                event('exec_command_begin', call_id='fake-call', turn_id='fake-turn'),
                event('terminal_interaction', call_id='fake-call', process_id='fake-process', stdin=first),
                event('terminal_interaction', call_id='fake-call', process_id=process, stdin=second),
                event('exec_command_end', call_id='fake-call', turn_id='fake-turn',
                      interaction_input=first + second), event('task_complete', turn_id='fake-turn'))

    clean = terminal_records('clean ', 'terminal')
    assert [json.loads(line) for line in access.sanitize_bytes(jsonl(*clean), (ACCOUNT,),
                                                              'native_rollout').splitlines()] == list(clean)
    with pytest.raises(access.AccessError, match='split'):
        access.sanitize_bytes(jsonl(*terminal_records('synthetic-', 'account-42')), (ACCOUNT,), 'native_rollout')
    with pytest.raises(access.AccessError, match='ambiguous'):
        access.sanitize_bytes(jsonl(*terminal_records('clean ', 'terminal', 'other')), (ACCOUNT,), 'native_rollout')


def test_malformed_native_fragment_fields_fail_with_nonsecret_error():
    record = rollout('response_item', type='message', role='assistant',
                     content=[{'type': [ACCOUNT], 'text': 'fake'}])
    with pytest.raises(access.AccessError) as raised:
        access.sanitize_bytes(jsonl(record), (ACCOUNT,), 'native_rollout')
    assert ACCOUNT not in str(raised.value)


def test_mcp_tool_output_blocks_are_scanned_as_one_logical_output():
    record = {'type': 'item.completed', 'item': {'id': 'item_0', 'type': 'mcp_tool_call',
              'result': {'content': [{'type': 'text', 'text': 'synthetic-'},
                                     {'type': 'text', 'text': 'account-42'}]}}}
    with pytest.raises(access.AccessError, match='split'):
        access.sanitize_bytes(jsonl(record), (ACCOUNT,), 'native_exec')
    record['item']['result']['content'] = [{'type': 'image', 'data': 'ZmFrZQ=='}]
    with pytest.raises(access.AccessError):
        access.sanitize_bytes(jsonl(record), (ACCOUNT,), 'native_exec')


def test_known_native_envelopes_do_not_accept_unrecognized_fragment_fields():
    starter = {'type': 'turn.started', 'delta': 'synthetic-'}
    terminal = {'type': 'turn.completed', 'usage': {}, 'delta': 'account-42'}
    with pytest.raises(access.AccessError):
        access.sanitize_bytes(jsonl(starter, terminal), (ACCOUNT,), 'native_exec')


def test_patch_text_projection_preserves_typed_output_and_withholds_private_fragments():
    call = 'dummy-patch'
    change = {'event': 'file_change_result', 'call_id': call, 'stdout': '', 'stderr': '',
              'changes': {'first.txt': {'type': 'add', 'content': 'first\n'}}, 'status': 'completed'}
    result = {'event': 'model_visible_result', 'call_id': call,
              'output': [{'type': 'input_text', 'text': 'patch '}, {'type': 'input_text', 'text': 'applied'}]}
    access.verify_scoring_release(access._json_bytes(change) + access._json_bytes(result), (ACCOUNT,))
    split = {**result, 'output': [{'type': 'input_text', 'text': 'synthetic-'},
                                  {'type': 'input_text', 'text': 'account-42'}]}
    with pytest.raises(access.AccessError, match='split'):
        access.verify_scoring_release(jsonl(change, split), (ACCOUNT,))
    with pytest.raises(access.AccessError, match='redaction'):
        access.verify_scoring_release(jsonl({**change, 'stderr': ACCOUNT}, result), (ACCOUNT,))
