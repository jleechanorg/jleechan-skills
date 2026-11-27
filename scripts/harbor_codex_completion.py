#!/usr/bin/env python3
"""Bind Harbor's Codex copy to the actual closed source rollout and process exit."""

import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import socket
import ssl
import stat
import subprocess
import sys
from uuid import UUID


MAX_BYTES = 16 * 1024 * 1024
PRIVATE_RECEIPT = 'completion.private.json'
PUBLIC_RECEIPT = 'completion.json'
AGENT_LOGS = Path('/logs/agent')
PRIVATE_DIAGNOSTICS = 'codex-diagnostics.log'


def require(condition):
    if not condition:
        raise ValueError('native Codex completion could not be verified')


def read_regular(path, limit=MAX_BYTES):
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as file:
        before = os.fstat(file.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= limit)
        data = file.read(limit + 1)
        after = os.fstat(file.fileno())
        require(len(data) == before.st_size == after.st_size
                and (before.st_mtime_ns, before.st_ctime_ns) == (after.st_mtime_ns, after.st_ctime_ns))
        return data


def jsonl(data):
    require(data.endswith(b'\n'))
    try:
        rows = [json.loads(line) for line in data.splitlines()]
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise ValueError('malformed native Codex events') from None
    require(rows and all(isinstance(row, dict) for row in rows))
    return rows


def one_rollout(sessions):
    require(sessions.is_dir() and not sessions.is_symlink())
    paths = list(sessions.rglob('*.jsonl'))
    require(len(paths) == 1)
    path = paths[0]
    require(not any(parent.is_symlink() for parent in path.parents if parent.is_relative_to(sessions)))
    data = read_regular(path)
    rows = jsonl(data)
    require(rows[0].get('type') == 'session_meta' and isinstance(rows[0].get('payload'), dict))
    thread = rows[0]['payload'].get('id')
    require(isinstance(thread, str) and str(UUID(thread)) == thread)
    return data, rows, thread, path


def native_control_seen(trajectory, control, prompt):
    try:
        expected = '# AGENTS.md instructions for /workspace\n\n<INSTRUCTIONS>\n' + control.decode('utf-8') + '\n</INSTRUCTIONS>'
        task = prompt.decode('utf-8')
        records = jsonl(read_regular(trajectory))
        require(records[0].get('type') == 'session_meta')
        turn = context = instructions = task_input = None
        for ordinal, row in enumerate(records[1:], 1):
            payload = row.get('payload')
            require(isinstance(payload, dict))
            kind = payload.get('type')
            if row['type'] == 'event_msg' and kind in ('task_started', 'turn_started'):
                require(turn is None and isinstance(payload.get('turn_id'), str) and payload['turn_id']
                        and payload.get('root_turn_id') == payload['turn_id'])
                turn = payload['turn_id']
            if row['type'] == 'turn_context':
                require(turn is not None and context is None and instructions is not None
                        and payload.get('cwd') == '/workspace' and payload.get('turn_id') == turn
                        and payload.get('root_turn_id') == turn)
                context = ordinal
            if row['type'] == 'response_item' and (kind in ('function_call', 'custom_tool_call')
                    or payload.get('role') == 'assistant'):
                require(task_input is not None)
                return {'turn_id': turn, 'instructions': instructions, 'task_input': task_input}
            if row['type'] == 'response_item' and kind == 'message' and payload.get('role') == 'user':
                info = payload.get('internal_chat_message_metadata_passthrough', {})
                require(isinstance(info, dict))
                kinds = info.get('content_item_kinds')
                content = payload.get('content')
                require(isinstance(kinds, list) and isinstance(content, list) and len(kinds) == len(content))
                for index, (label, part) in enumerate(zip(kinds, content, strict=True)):
                    if label not in ('agents_md.instructions', 'user.text'):
                        continue
                    require(turn is not None and info.get('turn_id') == turn and isinstance(part, dict)
                            and part.get('type') == 'input_text')
                    if label == 'agents_md.instructions':
                        require(instructions is None and context is None and part.get('text') == expected)
                        instructions = [ordinal, index]
                    else:
                        require(context is not None and task_input is None and part.get('text') == task)
                        task_input = [ordinal, index]
        return False
    except (OSError, ValueError, KeyError, TypeError):
        return False


def make_completion(code, sessions):
    receipt = {'exit_code': code}
    if code == 0:
        data, _, thread, _ = one_rollout(sessions)
        receipt.update(thread_id=thread, size=len(data), sha256=hashlib.sha256(data).hexdigest())
    return receipt


def command_signature(command, status, code, output):
    require(isinstance(command, str) and status in ('completed', 'failed', 'declined')
            and type(code) is int and isinstance(output, str))
    return (tuple(shlex.split(command)), status, code, output)


def completed_stdout_items(stdout):
    require(len(stdout) >= 3 and stdout[1].get('type') == 'turn.started')
    active, closed, commands, completed = {}, set(), [], []
    for row in stdout[2:-1]:
        phase = row.get('type')
        require(phase in ('item.started', 'item.updated', 'item.completed'))
        item = row.get('item')
        require(isinstance(item, dict))
        item_id, kind = item.get('id'), item.get('type')
        require(isinstance(item_id, str) and item_id and isinstance(kind, str) and item_id not in closed)
        require(kind in {'agent_message', 'command_execution', 'file_change', 'reasoning', 'todo_list'})
        if phase == 'item.started':
            require(item_id not in active)
            active[item_id] = item
        elif phase == 'item.updated':
            require(item_id in active and active[item_id]['type'] == kind
                    and kind not in {'command_execution', 'file_change'})
        else:
            opened = active.pop(item_id, None)
            require(opened is None or opened['type'] == kind)
            if kind == 'command_execution':
                require(opened is not None and opened.get('status') == 'in_progress'
                        and opened.get('command') == item.get('command'))
                commands.append(command_signature(item.get('command'), item.get('status'),
                                                  item.get('exit_code'), item.get('aggregated_output')))
            if kind == 'file_change':
                require(opened is not None and opened.get('status') == 'in_progress'
                        and opened.get('changes') == item.get('changes'))
                patch_signature(item)
            completed.append(item)
            closed.add(item_id)
    require(not active)
    return completed, commands


def completed_rollout_items(events, terminals, thread):
    starts = [index for index, event in enumerate(events) if event.get('type') in ('task_started', 'turn_started')]
    require(len(starts) == 1 and len(terminals) == 1 and events[-1] is terminals[0]
            and terminals[0].get('type') in ('task_complete', 'turn_complete') and starts[0] < len(events) - 1)
    turn_id = events[starts[0]].get('turn_id')
    require(isinstance(turn_id, str) and turn_id and terminals[0].get('turn_id') == turn_id
            and terminals[0].get('error') is None)
    closed, messages, ordered = set(), [], []
    last_message_phase = None
    for index, event in enumerate(events):
        require(event.get('type') not in UNSUPPORTED_ROLLOUT_ACTIONS)
        if event.get('type') != 'item_completed':
            continue
        item = event.get('item')
        require(starts[0] < index < len(events) - 1 and event.get('turn_id') == turn_id
                and event.get('thread_id') == thread and isinstance(item, dict))
        identity, kind = item.get('id'), item.get('type')
        require(isinstance(identity, str) and identity and identity not in closed and isinstance(kind, str))
        closed.add(identity)
        if kind == 'CommandExecution':
            argv, output = item.get('command'), item.get('aggregated_output')
            require(isinstance(argv, list) and argv and all(isinstance(arg, str) for arg in argv))
            command = command_signature(shlex.join(argv), item.get('status'), item.get('exit_code'),
                                        output)
            ordered.append(('command', command))
        elif kind == 'FileChange':
            ordered.append(('patch', patch_signature(item, native=True)))
        elif kind == 'AgentMessage':
            content = item.get('content')
            require(isinstance(content, list) and content and all(isinstance(part, dict)
                    and part.get('type') == 'Text' and isinstance(part.get('text'), str) for part in content))
            messages.append(''.join(part['text'] for part in content))
            ordered.append(('message', messages[-1]))
            last_message_phase = item.get('phase')
        else:
            require(kind in {'UserMessage', 'Reasoning', 'Plan', 'FunctionCallOutput'})
    require(not messages or last_message_phase == 'final_answer')
    return messages, ordered


COMMAND_RESPONSE_HEADER = re.compile(
    r'(?:Chunk ID: [a-f0-9]+\n)?Wall time: (?P<wall>\d+\.\d{4}) seconds\n'
    r'(?:Process exited with code (?P<exit>-?\d+)\n|Process running with session ID (?P<session>[1-9]\d*)\n)?'
    r'(?:Original token count: \d+\n)?Output:\n'
)
COMMAND_TOOLS = {'exec_command', 'shell', 'shell_command'}
LOCAL_RESPONSE_TOOLS = COMMAND_TOOLS | {'write_stdin', 'update_plan'}
UNSUPPORTED_RESPONSE_ACTIONS = {'local_shell_call', 'tool_search_call', 'web_search_call', 'image_generation_call'}
UNSUPPORTED_ROLLOUT_ACTIONS = {'mcp_tool_call_end', 'patch_apply_end', 'web_search_end', 'image_generation_end',
                              'sub_agent_activity'}


def patch_signature(item, native=False):
    status, changes = item.get('status'), item.get('changes')
    require(status in (('completed', 'failed', 'declined') if native else ('completed', 'failed')))
    if native:
        require(isinstance(changes, dict) and all(isinstance(path, str) and path
                and isinstance(change, dict) for path, change in changes.items()))
        for change in changes.values():
            kind = change.get('type')
            require(kind in ('add', 'delete', 'update'))
            if kind == 'update':
                require(isinstance(change.get('unified_diff'), str)
                        and (change.get('move_path') is None or isinstance(change['move_path'], str)))
            else:
                require(isinstance(change.get('content'), str))
        require(isinstance(item.get('stdout'), str) and isinstance(item.get('stderr'), str))
        changes = [{'path': path, 'kind': change['type']} for path, change in changes.items()]
    require(isinstance(changes, list) and all(isinstance(change, dict)
            and set(change) == {'path', 'kind'} and isinstance(change['path'], str) and change['path']
            and change['kind'] in ('add', 'delete', 'update') for change in changes))
    return (tuple((change['path'], change['kind']) for change in changes),
            'failed' if status == 'declined' else status)


PATCH_RESPONSE_HEADER = re.compile(r'Wall time: (?P<wall>\d+\.\d{4}) seconds\nOutput:\n')


def bound_patch_responses(records):
    patches = {}
    for ordinal, row in enumerate(records):
        payload = row['payload']
        if row['type'] == 'event_msg' and payload.get('type') == 'item_completed':
            item = payload['item']
            if item.get('type') == 'FileChange':
                call = item.get('id')
                require(isinstance(call, str) and call and call not in patches)
                patch_signature(item, native=True)
                patches[call] = (ordinal, item)
    openings, closed, projected = {}, set(), {}
    for ordinal, row in enumerate(records):
        if row['type'] != 'response_item':
            continue
        payload = row['payload']
        kind, call = payload.get('type'), payload.get('call_id')
        if kind == 'custom_tool_call' and payload.get('name') == 'apply_patch':
            require(call in patches)
        if kind in ('function_call', 'custom_tool_call') and call in patches:
            require(call not in openings and call not in closed and ordinal < patches[call][0])
            name = payload.get('name')
            if kind == 'custom_tool_call':
                require(name == 'apply_patch' and isinstance(payload.get('input'), str))
                fields = {'input': payload['input']}
            else:
                require(name == 'exec_command' and isinstance(payload.get('arguments'), str))
                arguments = json.loads(payload['arguments'])
                require(isinstance(arguments, dict) and isinstance(arguments.get('cmd'), str))
                # The native FileChange call ID binds intercepted shell patches; do not
                # reimplement the shell/patch parser or pretend a process was executed.
                fields = {'arguments': command_input(name, payload['arguments'],
                                                     ['bash', '-lc', arguments['cmd']])}
            openings[call] = kind
            projected[ordinal] = ('tool_call', {'call_id': call, 'name': name, **fields})
        elif kind in ('function_call_output', 'custom_tool_call_output') and call in patches:
            require(openings.pop(call, None) == kind.removesuffix('_output') and call not in closed
                    and patches[call][0] < ordinal)
            output = payload.get('output')
            if isinstance(output, str):
                text = output
            else:
                require(kind == 'custom_tool_call_output' and isinstance(output, list) and output
                        and all(isinstance(part, dict) and set(part) == {'type', 'text'}
                                and part['type'] == 'input_text' and isinstance(part['text'], str)
                                for part in output))
                text = ''.join(part['text'] for part in output)
            header = PATCH_RESPONSE_HEADER.match(text)
            body = text[header.end():] if header else text
            patch = patches[call][1]
            # Exact observed stdout, or a source-emitted failure message in stderr.
            require(body == patch['stdout'] if not patch['stderr'] else
                    not patch['stdout'] and body == patch['stderr'])
            closed.add(call)
            projected[ordinal] = ('model_visible_result', {'call_id': call, 'output': output,
                'truncated': False,
                **({'command_wall_seconds': float(header['wall'])} if header else {})})
    require(not openings and closed == patches.keys())
    return projected


def bound_command_responses(records):
    require(all(isinstance(row.get('type'), str) and isinstance(row.get('payload'), dict) for row in records))
    commands = {item['id']: (ordinal, item) for ordinal, row in enumerate(records)
                if row['type'] == 'event_msg' and row['payload']['type'] == 'item_completed'
                and (item := row['payload']['item'])['type'] == 'CommandExecution'}
    projected = bound_patch_responses(records)
    openings, closed, sessions, seen_origins = {}, set(), {}, set()
    for ordinal, row in enumerate(records):
        if row['type'] != 'response_item' or ordinal in projected:
            continue
        payload = row['payload']
        kind = payload.get('type')
        call = payload.get('call_id')
        if kind == 'function_call' and payload.get('name') in (COMMAND_TOOLS | {'write_stdin'}):
            name = payload['name']
            require(isinstance(call, str) and call and call not in openings and call not in closed)
            if name == 'write_stdin':
                require(isinstance(payload.get('arguments'), str))
                arguments = json.loads(payload['arguments'])
                require(isinstance(arguments, dict) and type(arguments.get('session_id')) is int
                        and isinstance(arguments.get('chars'), str))
                session = arguments['session_id']
                require(session in sessions and not sessions[session]['closed'] and call not in commands)
                origin = sessions[session]['origin']
                arguments = {'session_id': session, 'chars': arguments['chars']}
                fields = {'origin_call_id': origin}
            else:
                require(call in commands and ordinal < commands[call][0])
                origin, session, fields = call, None, {}
                arguments = command_input(name, payload.get('arguments'), commands[origin][1]['command'])
                seen_origins.add(origin)
            openings[call] = (name, origin, session, fields)
            projected[ordinal] = ('tool_call', {'call_id': call, 'name': name, 'arguments': arguments, **fields})
        elif kind == 'function_call_output' and (call in openings or call in closed):
            require(call in openings and isinstance(payload.get('output'), str))
            name, origin, session, fields = openings.pop(call)
            completed_at, command = commands[origin]
            aggregate = command.get('aggregated_output')
            require(isinstance(aggregate, str))
            response = payload['output']
            header = COMMAND_RESPONSE_HEADER.match(response) if response != aggregate or session is not None else None
            running = int(header['session']) if header and header['session'] else None
            exit_code = int(header['exit']) if header and header['exit'] is not None else None
            body = response[header.end():] if header else response
            require(exit_code is None or exit_code == command['exit_code'])
            if session is None and running is not None:
                require(name == 'exec_command' and running not in sessions
                        and command.get('process_id') == str(running))
                sessions[running] = {'origin': origin, 'length': 0, 'closed': False}
                session = running
            if session is not None:
                state = sessions[session]
                require(header is not None and not state['closed'] and (running == session or exit_code is not None))
                offset = state['length']
                require(aggregate.startswith(body, offset))
                state['length'] += len(body)
                if exit_code is not None:
                    require(completed_at < ordinal and state['length'] == len(aggregate))
                    state['closed'] = True
                truncated = False
                fields = {**fields, 'session_id': session, 'process_running': running is not None}
            else:
                truncated = visible_output(body, aggregate)
            closed.add(call)
            projected[ordinal] = ('model_visible_result', {'call_id': call, 'output': body,
                'truncated': truncated, **({'command_wall_seconds': float(header['wall'])} if header else {}), **fields})
    require(not openings and seen_origins == commands.keys())
    for state in sessions.values():
        if not state['closed']:
            completion_ordinal = commands[state['origin']][0]
            projected[completion_ordinal] = ('unobserved_terminal', {})
    return projected


def visible_output(body, aggregate):
    if body == aggregate:
        return False
    marker = re.search(r'\n\n…([1-9]\d*) (chars|tokens) truncated…\n\n', body)
    require(marker is not None and len(body) < len(aggregate))
    prefix, suffix = body[:marker.start()], body[marker.end():]
    omitted = len(aggregate) - len(prefix) - len(suffix)
    require(bool(prefix and suffix) and omitted > 0 and aggregate.startswith(prefix) and aggregate.endswith(suffix))
    require(marker[2] != 'chars' or int(marker[1]) == omitted)
    return True


def command_input(name, encoded, argv):
    require(isinstance(encoded, str))
    arguments = json.loads(encoded)
    require(isinstance(arguments, dict))
    if name == 'exec_command' and len(argv) == 3 and argv[1] in ('-c', '-lc') and Path(argv[0]).name == 'bash':
        require(arguments.get('cmd') == argv[-1])
    elif name in ('exec_command', 'shell_command'):
        command = arguments.get('cmd') if name == 'exec_command' else arguments.get('command')
        require(isinstance(command, str) and tuple(shlex.split(command)) == tuple(argv))
        arguments = {**arguments, 'cmd': command}
    elif name == 'shell':
        require(arguments.get('command') == list(argv))
    else:
        raise ValueError('unsupported native command continuation')
    require(arguments.get('workdir') is None or isinstance(arguments['workdir'], str))
    permissions = ('sandbox_permissions', 'tty', 'justification', 'prefix_rule', 'login')
    require(arguments.get('sandbox_permissions') in (None, 'use_default', 'require_escalated')
            and all(arguments.get(flag) is None or type(arguments[flag]) is bool for flag in ('tty', 'login'))
            and (arguments.get('justification') is None or isinstance(arguments['justification'], str))
            and (arguments.get('prefix_rule') is None or isinstance(arguments['prefix_rule'], list)
                 and all(isinstance(part, str) for part in arguments['prefix_rule'])))
    return {field: arguments[field] for field in ('cmd', 'command', 'workdir', *permissions) if field in arguments}


def verify_completion(receipt_file, trace, sessions, model, effort):
    meta = json.loads(read_regular(receipt_file, 2048))
    require(isinstance(meta, dict) and type(meta.get('exit_code')) is int and meta['exit_code'] == 0)
    data, rollout, thread, path = one_rollout(sessions)
    session_meta = rollout[0]['payload']
    require(session_meta.get('cli_version') == '0.172.0' and session_meta.get('model_provider') == 'openai')
    require(meta == {'exit_code': 0, 'thread_id': thread, 'size': len(data),
                     'sha256': hashlib.sha256(data).hexdigest()})
    stdout = jsonl(read_regular(trace))
    require(stdout[0].get('type') == 'thread.started' and stdout[0].get('thread_id') == thread
            and stdout[-1].get('type') == 'turn.completed'
            and not any(row.get('type') in ('turn.failed', 'error') for row in stdout))
    payloads = [row.get('payload') for row in rollout]
    require(all(isinstance(payload, dict) for payload in payloads))
    turns = [row['payload'] for row in rollout if row.get('type') == 'turn_context']
    require(turns and all(turn.get('model') == model and turn.get('effort') == effort for turn in turns))
    events = [row['payload'] for row in rollout if row.get('type') == 'event_msg']
    require(not any(event.get('type') == 'error' for event in events))
    terminals = [event for event in events if event.get('type') in ('task_complete', 'turn_complete', 'turn_aborted')]
    items, commands = completed_stdout_items(stdout)
    native_messages, expected_order = completed_rollout_items(events, terminals, thread)
    command_items = iter(commands)
    order = []
    for item in items:
        if item['type'] == 'command_execution':
            order.append(('command', next(command_items)))
        elif item['type'] == 'file_change':
            order.append(('patch', patch_signature(item)))
        elif item['type'] == 'agent_message':
            order.append(('message', item.get('text')))
    require(order == expected_order)
    messages = [item.get('text') for item in items if item.get('type') == 'agent_message']
    require(messages and isinstance(messages[-1], str) and messages[-1]
            and messages == native_messages and messages[-1] == terminals[0].get('last_agent_message'))
    active = False
    calls, outputs, final_responses = {}, set(), []
    for row, payload in zip(rollout, payloads, strict=True):
        kind = payload.get('type')
        if row.get('type') == 'event_msg':
            if kind in ('task_started', 'turn_started'):
                active = True
            elif payload is terminals[0]:
                active = False
        if row.get('type') != 'response_item':
            continue
        require(kind not in UNSUPPORTED_RESPONSE_ACTIONS)
        if kind == 'message' and payload.get('role') == 'assistant' and payload.get('phase') == 'final_answer':
            content = payload.get('content')
            require(active and isinstance(content, list) and all(isinstance(part, dict)
                    and part.get('type') == 'output_text' and isinstance(part.get('text'), str) for part in content))
            final_responses.append(''.join(part['text'] for part in content))
        if kind in ('function_call', 'custom_tool_call', 'function_call_output', 'custom_tool_call_output'):
            call = payload.get('call_id')
            require(active and isinstance(call, str) and bool(call))
            if kind.endswith('_output'):
                require(calls.get(call) == kind.removesuffix('_output') and call not in outputs)
                outputs.add(call)
            else:
                require(call not in calls and (
                    kind == 'function_call' and payload.get('name') in LOCAL_RESPONSE_TOOLS
                    or kind == 'custom_tool_call' and payload.get('name') == 'apply_patch'))
                calls[call] = kind
    require(calls.keys() == outputs)
    require(final_responses == [messages[-1]])
    bound_command_responses(rollout)
    return thread, meta['sha256'], path


CLI_USAGE_FIELDS = ('input_tokens', 'cached_input_tokens', 'cache_write_input_tokens', 'output_tokens',
                    'reasoning_output_tokens')


def cli_usage(trace):
    records = jsonl(read_regular(trace))
    if not records:
        return None
    terminal = records[-1]
    usage = terminal.get('usage')
    if terminal.get('type') != 'turn.completed' or not isinstance(usage, dict):
        return None
    return {key: usage[key] for key in CLI_USAGE_FIELDS if type(usage.get(key)) is int and usage[key] >= 0} or None


def scoring_projection(data):
    records = jsonl(data)
    meta = records[0]['payload']
    rows = []
    command_events = bound_command_responses(records)
    names = {}
    for ordinal, row in enumerate(records):
        role, payload = row['type'], row['payload']
        kind = payload.get('type')
        timestamp = row.get('timestamp')
        require(timestamp is None or isinstance(timestamp, str))

        def emit(event, **fields):
            rows.append({'event': event, 'native_ordinal': ordinal, 'timestamp': timestamp, **fields})

        if role == 'session_meta':
            emit('session', thread_id=meta['id'], cli_version=meta['cli_version'], provider=meta['model_provider'])
        elif role == 'turn_context':
            fields = {key: payload[key] for key in ('cwd', 'turn_id', 'root_turn_id', 'model', 'effort')}
            require(all(isinstance(value, str) and value for value in fields.values()))
            emit('turn', **fields)
        elif ordinal in command_events and command_events[ordinal][0] != 'unobserved_terminal':
            event, fields = command_events[ordinal]
            emit(event, **fields)
        elif role == 'response_item' and kind == 'function_call':
            call, name = payload['call_id'], payload['name']
            require(name == 'update_plan' and call not in names and isinstance(payload.get('arguments'), str))
            arguments = json.loads(payload['arguments'])
            require(isinstance(arguments, dict) and 'plan' in arguments
                    and set(arguments) <= {'plan', 'explanation'}
                    and (arguments.get('explanation') is None or isinstance(arguments['explanation'], str))
                    and isinstance(arguments['plan'], list)
                    and all(isinstance(step, dict) and set(step) == {'step', 'status'}
                            and isinstance(step['step'], str)
                            and step['status'] in ('pending', 'in_progress', 'completed')
                            for step in arguments['plan']))
            names[call] = name
            emit('tool_call', call_id=call, name=name, arguments=arguments)
        elif role == 'response_item' and kind == 'function_call_output':
            call = payload['call_id']
            require(names.pop(call, None) == 'update_plan' and isinstance(payload.get('output'), str))
            emit('model_visible_result', call_id=call, output=payload['output'], truncated=False)
        elif role == 'event_msg' and kind == 'item_completed':
            item = payload['item']
            if item['type'] == 'CommandExecution':
                require(item.get('cwd') is None or isinstance(item['cwd'], str))
                emit('command_result', call_id=item['id'], argv=item['command'], cwd=item.get('cwd'),
                     status=item['status'], exit_code=item['exit_code'], output=item['aggregated_output'],
                     **({'terminal_output_unobserved': True} if ordinal in command_events else {}))
            if item['type'] == 'FileChange':
                emit('file_change_result', call_id=item['id'], changes=item['changes'],
                     status=item['status'], stdout=item['stdout'], stderr=item['stderr'])
            if item['type'] == 'AgentMessage':
                emit('final_answer' if item['phase'] == 'final_answer' else 'assistant_message',
                     text=''.join(part['text'] for part in item['content']))
            require(item['type'] in {'CommandExecution', 'FileChange', 'AgentMessage', 'UserMessage', 'Reasoning', 'Plan',
                                     'FunctionCallOutput'})
        elif role == 'response_item':
            require(kind not in UNSUPPORTED_RESPONSE_ACTIONS | {'custom_tool_call', 'custom_tool_call_output'})
        elif role == 'event_msg' and kind in ('task_complete', 'turn_complete'):
            duration = payload.get('duration_ms')
            require(duration is None or type(duration) is int and duration >= 0)
            emit('terminal', turn_id=payload['turn_id'], duration_ms=duration)
        elif role == 'event_msg':
            require(kind not in UNSUPPORTED_ROLLOUT_ACTIONS)
    require(not names)
    return b''.join((json.dumps(row, sort_keys=True, separators=(',', ':')) + '\n').encode() for row in rows)


def engine_finished(pid):
    try:
        os.killpg(pid, 0)
    except ProcessLookupError:
        try:
            while True:
                child, _ = os.waitpid(-1, os.WNOHANG)
                if child == 0:
                    return False
        except ChildProcessError:
            return True
    return False


def supervise_engine_writers():
    return ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0) == 0


def tls_reachable(destination, server_name):
    try:
        with socket.create_connection((destination, 443), timeout=3) as connection:
            with ssl.create_default_context().wrap_socket(connection, server_hostname=server_name):
                return True
    except OSError:
        return False


def check_network(inference_allowed):
    return (tls_reachable('chatgpt.com', 'chatgpt.com') == inference_allowed
            and not tls_reachable('auth.openai.com', 'auth.openai.com')
            and not tls_reachable('api.openai.com', 'api.openai.com')
            and not tls_reachable('www.example.com', 'www.example.com')
            and not tls_reachable('1.1.1.1', 'one.one.one.one'))


def main():
    if sys.argv[1:] == ['--harbor-check-denied']:
        return 0 if check_network(False) else 1
    if sys.argv[1:] == ['--harbor-check-preupload-route']:
        absent = not any(os.path.lexists(path) for path in ('/tmp/codex-secrets/auth.json',
                                                            '/installed-agent/codex-home/auth.json'))
        return 0 if absent and check_network(True) else 1
    executable = '/opt/harbor-codex/codex-real'
    argv = [executable, *sys.argv[1:]]
    if sys.argv[1:2] != ['exec']:
        os.execv(executable, argv)
    if not check_network(True):
        print('Harbor Codex network precondition failed', file=sys.stderr)
        return 78
    if not supervise_engine_writers():
        print('Harbor Codex writer supervision unavailable', file=sys.stderr)
        return 78
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    with os.fdopen(os.open(AGENT_LOGS / PRIVATE_DIAGNOSTICS, flags, 0o600), 'w') as diagnostics:
        process = subprocess.Popen(argv, start_new_session=True, stderr=diagnostics)
        code = process.wait()
        try:
            require(engine_finished(process.pid))
            receipt = make_completion(code, Path(os.environ['CODEX_HOME']) / 'sessions')
            with (AGENT_LOGS / PRIVATE_RECEIPT).open('x', encoding='utf-8') as file:
                json.dump(receipt, file)
                file.write('\n')
        except (OSError, ValueError, KeyError):
            print('Native Codex completion receipt unavailable', file=diagnostics)
    return code if code >= 0 else 128 - code


if __name__ == '__main__':
    sys.exit(main())
