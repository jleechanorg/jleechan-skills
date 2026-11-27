"""Admission and release sanitation for the reviewed Harbor access-only path."""

import base64
import codecs
import fcntl
import hashlib
import json
import math
import os
import re
import stat
from datetime import datetime


REFRESH_WINDOW_SECONDS = 300
CLOCK_UNCERTAINTY_SECONDS = 30
CLEANUP_SECONDS = 60
MAX_AUTH_BYTES = 128 * 1024
MAX_ARTIFACT_BYTES = 32 * 1024 * 1024
MAX_JSONL_RECORDS = 100_000

AUTH_CLAIM = 'https://api.openai.com/auth'
ACCOUNT_CLAIM = 'chatgpt_account_id'
TOKEN_FIELDS = {'account_id', 'access_token', 'id_token', 'refresh_token'}
JWT_SEGMENT = re.compile(r'[A-Za-z0-9_-]+')
TIMESTAMP = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?(?:Z|[+-]\d{2}:[0-5]\d)', re.ASCII)
CONTROL = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]')
JSON_ESCAPE = re.compile(r'\\(?:["\\/bfnrt]|u[dD][89aAbB][0-9a-fA-F]{2}\\u[dD][c-fC-F][0-9a-fA-F]{2}|u[0-9a-fA-F]{4})')
FORMATS = {'.json': 'json', '.jsonl': 'jsonl', '.log': 'log', '.txt': 'text', '.md': 'text', '.tsv': 'text'}
MASK = '[REDACTED]'


class AccessError(ValueError):
    """A nonsecret admission or acquisition-withholding reason."""


def _require(condition, reason):
    if not condition:
        raise AccessError(reason)


def _fingerprint(info):
    return (info.st_dev, info.st_ino, info.st_uid, info.st_mode, info.st_nlink,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _read_regular(file_fd, limit, *, auth=False, links=1):
    _require(type(file_fd) is int and file_fd >= 0, 'input descriptor is invalid')
    try:
        before = os.fstat(file_fd)
        _require(stat.S_ISREG(before.st_mode) and before.st_nlink == links, 'input is not a permitted regular file')
        if auth:
            _require(before.st_uid == os.geteuid() and stat.S_IMODE(before.st_mode) == 0o600,
                     'auth source is not owned and mode 0600')
        _require(0 <= before.st_size <= limit, 'input exceeds size limit')
        chunks = bytearray()
        while len(chunks) <= before.st_size:
            chunk = os.pread(file_fd, min(65536, before.st_size + 1 - len(chunks)), len(chunks))
            if not chunk:
                break
            chunks.extend(chunk)
        after = os.fstat(file_fd)
        _require(len(chunks) == before.st_size and _fingerprint(before) == _fingerprint(after),
                 'input changed during read')
        return bytes(chunks)
    except (OSError, OverflowError, TypeError):
        pass
    raise AccessError('input descriptor is unreadable')


def read_artifact(file_fd):
    """Read a sealed regular artifact without closing the descriptor or moving its offset."""
    return _read_regular(file_fd, MAX_ARTIFACT_BYTES)


def _reference_seals():
    return fcntl.F_SEAL_WRITE | fcntl.F_SEAL_GROW | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL


def _profile_path_key(path):
    return hashlib.sha256(os.fsencode(path)).hexdigest()


def read_account_reference(file_fd, path):
    try:
        _require(os.lseek(file_fd, 0, os.SEEK_CUR) == 0, 'account reference descriptor is not at offset zero')
        required = _reference_seals()
        _require(os.fstat(file_fd).st_nlink == 0
                 and fcntl.fcntl(file_fd, fcntl.F_GET_SEALS) & required == required,
                 'account reference is not sealed')
    except (OSError, TypeError, OverflowError):
        raise AccessError('invalid account reference descriptor') from None
    reference, separator, profile = _utf8(_read_regular(file_fd, 4096, auth=True, links=0)).partition('\n')
    _require(bool(reference) and not any(char.isspace() for char in reference)
             and not CONTROL.search(reference), 'invalid private account reference')
    _require(bool(separator) and profile == _profile_path_key(path), 'selected managed profile path changed')
    return reference


def derivative_not_after(data, wait_seconds):
    expiry = _jwt(_parse_json(_utf8(data))['tokens']['access_token']).get('exp')
    _require(type(expiry) is int and 0 < expiry < 2**63, 'invalid bearer expiry')
    return expiry - wait_seconds - REFRESH_WINDOW_SECONDS - CLOCK_UNCERTAINTY_SECONDS - CLEANUP_SECONDS


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, 'duplicate JSON field')
        result[key] = value
    return result


def _finite_float(value):
    result = float(value)
    _require(math.isfinite(result), 'nonfinite JSON number')
    return result


def _parse_json(text):
    try:
        return json.loads(text, object_pairs_hook=_unique_object, parse_float=_finite_float, parse_constant=_finite_float)
    except AccessError:
        raise
    except (ValueError, RecursionError):
        pass
    raise AccessError('invalid strict JSON')


def _utf8(raw):
    try:
        return raw.decode('utf-8')
    except UnicodeError:
        pass
    raise AccessError('input is not UTF-8')


def _string(value):
    return isinstance(value, str) and value.isascii() and bool(value) and all(33 <= ord(char) <= 126 for char in value)


def _jwt(token):
    _require(isinstance(token, str), 'invalid JWT')
    parts = token.split('.')
    _require(len(parts) == 3 and all(JWT_SEGMENT.fullmatch(part) for part in parts), 'invalid JWT')
    try:
        decoded = [base64.urlsafe_b64decode(part + '=' * (-len(part) % 4)) for part in parts]
    except ValueError:
        decoded = None
    _require(decoded is not None and all(base64.urlsafe_b64encode(raw).rstrip(b'=').decode() == part
                                         for part, raw in zip(parts, decoded)), 'invalid JWT encoding')
    header, claims = (_parse_json(_utf8(part)) for part in decoded[:2])
    _require(isinstance(header, dict) and isinstance(claims, dict), 'invalid JWT structure')
    _require(_string(header.get('alg')) and header['alg'] != 'none', 'invalid JWT algorithm field')
    return claims


def _match_account(claims, expected, *, required):
    _require(ACCOUNT_CLAIM not in claims, 'unsupported JWT account claim')
    if AUTH_CLAIM not in claims and not required:
        return
    metadata = claims.get(AUTH_CLAIM)
    _require(isinstance(metadata, dict), 'missing or malformed JWT account namespace')
    if ACCOUNT_CLAIM in metadata or required:
        _require(metadata.get(ACCOUNT_CLAIM) == expected, 'JWT account mismatch')


def _valid_timestamp(value):
    if isinstance(value, str) and TIMESTAMP.fullmatch(value):
        try:
            datetime.fromisoformat(value.replace('Z', '+00:00'))
            return True
        except ValueError:
            pass
    return False


def _json_bytes(record):
    return (json.dumps(record, ensure_ascii=True, allow_nan=False, separators=(',', ':')) + '\n').encode('ascii')


def _read_managed_profile(auth_file_fd, expected_account=None):
    source = _parse_json(_utf8(_read_regular(auth_file_fd, MAX_AUTH_BYTES, auth=True)))
    _require(isinstance(source, dict) and source.keys() <= {'auth_mode', 'tokens', 'last_refresh', 'OPENAI_API_KEY'}
             and source.get('auth_mode') == 'chatgpt' and source.get('OPENAI_API_KEY') is None,
             'input is not managed token-only ChatGPT auth')
    tokens = source.get('tokens')
    _require(isinstance(tokens, dict) and TOKEN_FIELDS <= tokens.keys()
             and tokens.keys() <= TOKEN_FIELDS | {'oauth_provenance', 'login_owner_id'}, 'invalid managed token schema')
    provenance = tokens.get('oauth_provenance')
    _require(provenance is None or (isinstance(provenance, dict) and provenance.keys() == {'issuer', 'client_id'}
                                    and all(_string(value) for value in provenance.values())), 'invalid OAuth metadata')
    owner_id = tokens.get('login_owner_id')
    _require(owner_id is None or _string(owner_id), 'invalid login metadata')
    account = tokens['account_id']
    _require(_string(account) and not any(char.isspace() for char in account), 'invalid stored account')
    _require(expected_account is None or account == expected_account, 'stored account mismatch')
    refresh = tokens['refresh_token']
    _require(isinstance(refresh, str) and bool(refresh.strip()) and not CONTROL.search(refresh), 'invalid refresh field')
    _require(_valid_timestamp(source.get('last_refresh')), 'invalid last refresh timestamp')
    bearer = _jwt(tokens['access_token'])
    _match_account(bearer, account, required=True)
    _match_account(_jwt(tokens['id_token']), account, required=False)
    expiry = bearer.get('exp')
    _require(type(expiry) is int and 0 < expiry < 2**63, 'invalid bearer expiry')
    return source, expiry


def freeze_profile_account(auth_file_fd):
    """Read the explicitly selected managed profile and return its account privately to the caller."""
    source, _ = _read_managed_profile(auth_file_fd)
    return source['tokens']['account_id']


def freeze_account_descriptor(auth_file_fd, path):
    account = (freeze_profile_account(auth_file_fd) + '\n' + _profile_path_key(path)).encode('ascii')
    descriptor = os.memfd_create('harbor-selected-account', os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING)
    try:
        os.fchmod(descriptor, 0o600)
        _require(os.write(descriptor, account) == len(account), 'short write to private account descriptor')
        os.lseek(descriptor, 0, os.SEEK_SET)
        fcntl.fcntl(descriptor, fcntl.F_ADD_SEALS, _reference_seals())
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor


def prepare_derivative(auth_file_fd, expected_account, wait_seconds, clock):
    """Return derivative bytes and private scan values for the already selected account.

    The caller opens the source without symlink traversal and freezes the profile
    account before launching acquisitions. JWT checks here are structural.
    """
    _require(_string(expected_account), 'frozen account reference is missing or invalid')
    _require(type(wait_seconds) is int and 0 < wait_seconds < 2**63, 'invalid wall timeout')
    source, expiry = _read_managed_profile(auth_file_fd, expected_account)
    tokens = source['tokens']
    refresh = tokens['refresh_token']
    try:
        now = clock()
    except Exception:
        now = None
    _require(type(now) in (int, float) and 0 <= now < 2**63, 'invalid admission clock')
    allowance = REFRESH_WINDOW_SECONDS + CLOCK_UNCERTAINTY_SECONDS + CLEANUP_SECONDS
    _require(expiry - wait_seconds - allowance > now, 'bearer lifetime is insufficient for the whole job')
    derivative = _json_bytes({'auth_mode': 'chatgpt', 'last_refresh': source['last_refresh'], 'tokens': {
        **{name: tokens[name] for name in ('account_id', 'access_token', 'id_token')}, 'refresh_token': '',
    }})
    private = (tokens['access_token'], tokens['id_token'], refresh, expected_account,
               *((tokens['login_owner_id'],) if tokens.get('login_owner_id') else ()))
    _scan(derivative.decode('ascii'), _private_pattern((refresh,)))
    return derivative, private


def _private_pattern(values):
    _require(isinstance(values, (tuple, list)) and bool(values), 'private scan values are required')
    variants = set()
    for value in values:
        _require(isinstance(value, str) and bool(value) and not any(0xd800 <= ord(char) <= 0xdfff for char in value),
                 'invalid private scan value')
        variants.add(value)
        for ascii_only in (False, True):
            escaped = json.dumps(value, ensure_ascii=ascii_only)[1:-1]
            variants.update((escaped, escaped.replace('/', '\\/')))
    return re.compile('|'.join(re.escape(value) for value in sorted(variants, key=len, reverse=True)))


def _unescape(text):
    return JSON_ESCAPE.sub(lambda match: json.loads('"' + match[0] + '"'), text)


def _scan(text, pattern):
    _require(not pattern.search(text) and not ('\\' in text and pattern.search(_unescape(text))),
             'private value remains in release')


def verify_private_path(path, private_values):
    _scan(str(path), _private_pattern(private_values))


def safe_artifact_format(relative_name, private_values, *, directory=False):
    """Check a relative tree name; choose native schemas separately using the artifact's role."""
    _require(isinstance(relative_name, str) and '\\' not in relative_name
             and all(part not in ('', '.', '..') for part in relative_name.split('/'))
             and all(char.isprintable() for char in relative_name), 'unsafe artifact path')
    _scan(relative_name, _private_pattern(private_values))
    if directory:
        return None
    format_name = FORMATS.get(os.path.splitext(relative_name)[1])
    _require(format_name is not None, 'unsupported artifact format')
    return format_name


def verify_frozen_release(path, data, private_values):
    pattern = _private_pattern(private_values)
    _scan(path, pattern)
    _scan(data.decode('utf-8', errors='surrogateescape'), pattern)


def _mask_text(text, pattern):
    _require(not any(0xd800 <= ord(char) <= 0xdfff for char in text), 'invalid Unicode scalar')
    masked = pattern.sub(MASK, text)
    _scan(masked, pattern)
    return masked


def _mask_record(record, pattern):
    if isinstance(record, str):
        return _mask_text(record, pattern)
    if isinstance(record, list):
        return [_mask_record(value, pattern) for value in record]
    if isinstance(record, dict):
        result = {}
        for key, value in record.items():
            masked_key = _mask_text(key, pattern)
            _require(masked_key not in result, 'redaction would merge JSON fields')
            result[masked_key] = _mask_record(value, pattern)
        return result
    return record


def _json_strings(record):
    if isinstance(record, str):
        yield record
    elif isinstance(record, list):
        for value in record:
            yield from _json_strings(value)
    elif isinstance(record, dict):
        for key, value in record.items():
            yield key
            yield from _json_strings(value)


def _json_leaf_values(record):
    if isinstance(record, str):
        yield record
    elif isinstance(record, (dict, list)):
        for value in record.values() if isinstance(record, dict) else record:
            yield from _json_leaf_values(value)


EXEC_FIELDS = {'thread.started': {'thread_id'}, 'turn.started': set(), 'turn.completed': {'usage'},
               'turn.failed': {'error'}, 'error': {'message'}}
EXEC_ITEM_TYPES = {'agent_message', 'reasoning', 'command_execution', 'file_change', 'mcp_tool_call',
                   'collab_tool_call', 'web_search', 'todo_list', 'error'}
FRAGMENT_FIELDS = {'delta', 'fragment', 'fragments', 'chunk', 'stdin'}
ROLLOUT_FRAGMENT_FIELDS = {'agent_message_content_delta': {'delta'}, 'exec_command_output_delta': {'chunk'},
                           'terminal_interaction': {'stdin'}}
ROLLOUT_METADATA = {'session_meta', 'turn_context', 'token_usage_record', 'world_state', 'retained_context',
                    'security_risk_score', 'dynamic_tools_updated', 'inter_agent_communication_metadata'}
ROLLOUT_EVENTS = {'token_count', 'thread_goal_updated', 'thread_rolled_back', 'turn_aborted',
                  'thread_settings_applied', 'user_message', 'agent_message', 'agent_reasoning',
                  'agent_reasoning_raw_content', 'entered_review_mode', 'exited_review_mode', 'patch_apply_end',
                  'context_compacted', 'mcp_tool_call_end', 'web_search_end', 'image_generation_end',
                  'sub_agent_activity'}
RESPONSE_ITEMS = {'additional_tools', 'reasoning', 'local_shell_call', 'function_call', 'tool_search_call',
                  'custom_tool_call', 'web_search_call', 'image_generation_call',
                  'configuration_update'}
COMPLETED_ITEMS = {'UserMessage', 'HookPrompt', 'Reasoning', 'CollabAgentToolCall',
                   'SubAgentActivity', 'WebSearch', 'ImageView', 'Extension', 'ImageGeneration',
                   'McpToolCall', 'EnteredReviewMode', 'ExitedReviewMode', 'ContextCompaction', 'FileChange'}


def _field(record, key):
    value = record.get(key)
    _require(isinstance(value, str), 'native event has an invalid text field')
    return value


def _identifier(record, key):
    value = _field(record, key)
    _require(_string(value), 'native event is missing a valid correlation identifier')
    return value


def _object(record, key):
    value = record.get(key)
    _require(isinstance(value, dict), 'native event has an invalid object field')
    return value


def _joined(fragments, pattern):
    tail = ''
    overlap = len(pattern.pattern)
    for fragment in fragments:
        boundary = len(tail)
        window = tail + fragment[:overlap]
        match = pattern.search(window)
        while match is not None and match.start() < boundary:
            _require(match.end() <= boundary, 'private value split across logical fragments')
            match = pattern.search(window, match.start() + 1)
        tail = (tail + fragment[-overlap:])[-overlap:]
    return ''.join(fragments)


def _check_fragments(fragments, pattern):
    joined = _joined(fragments, pattern)
    if '\\' in joined:
        separately_decoded = _joined([_unescape(fragment) for fragment in fragments], pattern)
        decoded = _unescape(joined)
        _require(decoded == separately_decoded or not pattern.search(decoded),
                 'private value split across logical fragments')
    return joined


def _content(kind, value, pattern):
    _require(isinstance(value, list), 'unsupported native content')
    fragments = []
    for part in value:
        _require(isinstance(part, dict) and part.keys() == {'type', 'text'} and _field(part, 'type') in kind,
                 'unsupported native content fragment')
        fragments.append(_field(part, 'text'))
    return _check_fragments(fragments, pattern)


def _mcp_result(result, pattern):
    if result is not None:
        _require(isinstance(result, dict), 'invalid native tool result')
        _content({'text'}, result.get('content'), pattern)
        _check_fragments(list(_json_leaf_values(result)), pattern)
        for key in ('structuredContent', 'structured_content'):
            _check_fragments(list(_json_strings(result.get(key))), pattern)


def _exec_records(records, pattern):
    todo_updates = {}
    for record in records:
        kind = _field(record, 'type')
        if kind in EXEC_FIELDS:
            _require(record.keys() == {'type'} | EXEC_FIELDS[kind], 'unsupported native exec event fields')
            if kind == 'thread.started':
                _identifier(record, 'thread_id')
            elif kind == 'turn.completed':
                _object(record, 'usage')
            elif kind == 'turn.failed':
                _field(_object(record, 'error'), 'message')
            elif kind == 'error':
                _field(record, 'message')
            continue
        _require(kind in {'item.started', 'item.updated', 'item.completed'} and record.keys() == {'type', 'item'},
                 'unsupported native exec event')
        item = _object(record, 'item')
        item_id = _identifier(item, 'id')
        item_kind = _field(item, 'type')
        _require(item_kind in EXEC_ITEM_TYPES and not (item.keys() & FRAGMENT_FIELDS), 'unsupported native exec item')
        _require(kind != 'item.updated' or item_kind == 'todo_list', 'unsupported native progress item')
        if item_kind in {'agent_message', 'reasoning'}:
            _require(kind == 'item.completed' and item.keys() == {'id', 'type', 'text'},
                     'unsupported exec message fragment')
            _field(item, 'text')
        elif item_kind == 'command_execution':
            _require(kind != 'item.updated' and item.keys() == {
                'id', 'type', 'command', 'aggregated_output', 'status', 'exit_code'}, 'unsupported exec tool fragment')
            _field(item, 'aggregated_output')
        elif item_kind == 'mcp_tool_call':
            _require(kind == 'item.completed' or (kind == 'item.started' and item.get('result') is None
                                                  and item.get('error') is None), 'unsupported native MCP fragment')
            _mcp_result(item.get('result'), pattern)
        elif item_kind == 'todo_list':
            _require(item.keys() == {'id', 'type', 'items'} and isinstance(item['items'], list),
                     'invalid native todo item')
            for index, todo in enumerate(item['items']):
                _require(isinstance(todo, dict) and todo.keys() == {'text', 'completed'}
                         and type(todo['completed']) is bool, 'invalid native todo entry')
                todo_updates.setdefault((item_id, index), []).append(_field(todo, 'text'))
            _check_fragments(list(_json_leaf_values(item['items'])), pattern)
        else:
            _check_fragments(list(_json_leaf_values(item)), pattern)
    for updates in todo_updates.values():
        _check_fragments(updates, pattern)


def _command_output(chunks, pattern):
    decoder = codecs.getincrementaldecoder('utf-8')()
    try:
        fragments = [decoder.decode(chunk) for chunk in chunks]
        fragments.append(decoder.decode(b'', final=True))
    except UnicodeError:
        fragments = None
    _require(fragments is not None, 'native command output is not UTF-8')
    joined = _check_fragments(fragments, pattern)
    _require(not CONTROL.search(joined), 'unsupported native command output')
    _scan(joined, pattern)
    return joined


def _close_command(event, streamed, pattern):
    chunks, terminal_inputs = streamed
    if chunks:
        for channel in ('stdout', 'stderr'):
            _command_output((chunk for stream, chunk in chunks if stream == channel), pattern)
        aggregate = _command_output((chunk for _, chunk in chunks), pattern)
        _require(_field(event, 'aggregated_output') == aggregate, 'native tool copies disagree')
    if terminal_inputs:
        joined = _check_fragments([text for _, text in terminal_inputs], pattern)
        _require(_field(event, 'interaction_input') == joined, 'native terminal copies disagree')


def _tool_output(output, pattern):
    if isinstance(output, str):
        from harbor_codex_completion import COMMAND_RESPONSE_HEADER

        header = COMMAND_RESPONSE_HEADER.match(output)
        if header:
            output = output[header.end():]
        decoder = json.JSONDecoder(object_pairs_hook=_unique_object, parse_float=_finite_float,
                                   parse_constant=_finite_float)
        consumed = 0
        for candidate in re.finditer(r'(?m)^[ \t\r]*([\[{])', output):
            start = candidate.start(1)
            if start < consumed:
                continue
            try:
                encoded, consumed = decoder.raw_decode(output, start)
            except json.JSONDecodeError:
                continue
            except RecursionError:
                raise AccessError('native tool output exceeds JSON nesting limit') from None
            _check_fragments(list(_json_leaf_values(encoded)), pattern)
            content = encoded.get('content') if isinstance(encoded, dict) else None
            if isinstance(content, list) and all(isinstance(node, dict) and 'type' in node for node in content):
                _content({'text', 'input_text', 'output_text'}, content, pattern)
    else:
        _content({'input_text', 'output_text'}, output, pattern)


def verify_scoring_release(data, private_values):
    pattern = _private_pattern(private_values)
    visible_by_origin = {}
    for row in _json_lines(_utf8(data), allow_empty=False):
        if row.get('event') in {'command_result', 'model_visible_result'}:
            output = _field(row, 'output')
            _tool_output(output, pattern)
            if row['event'] == 'model_visible_result':
                origin = row.get('origin_call_id', _identifier(row, 'call_id'))
                visible_by_origin.setdefault(origin, []).append(output)
    for chunks in visible_by_origin.values():
        _tool_output(_check_fragments(chunks, pattern), pattern)
    _require(sanitize_bytes(data, private_values, 'jsonl') == data, 'native scoring projection required redaction')


def _response_item(payload, pattern):
    kind = _field(payload, 'type')
    _require(not (payload.keys() & FRAGMENT_FIELDS), 'unsupported native response fragment')
    if kind in {'message', 'agent_message'}:
        _content({'input_text', 'output_text'}, payload.get('content'), pattern)
    elif kind == 'reasoning':
        _require({'type', 'summary'} <= payload.keys() <= {
            'type', 'id', 'summary', 'content', 'encrypted_content', 'internal_chat_message_metadata_passthrough',
        }, 'unsupported native reasoning item')
        groups = []
        for field, kinds in (('summary', {'summary_text'}), ('content', {'reasoning_text', 'text'})):
            value = payload.get(field)
            if field == 'content' and value is None:
                continue
            _require(isinstance(value, list) and all(isinstance(part, dict)
                     and part.keys() == {'type', 'text'} for part in value), 'unsupported native reasoning fragment')
            groups.append(_content(kinds, value, pattern))
        _check_fragments(groups, pattern)
        opaque = payload.get('encrypted_content')
        _require(opaque is None or isinstance(opaque, str), 'unsupported native encrypted reasoning')
    elif kind in {'function_call_output', 'custom_tool_call_output'}:
        _tool_output(payload.get('output'), pattern)
    else:
        _require(kind in RESPONSE_ITEMS, 'unsupported native response item')


def _rollout_records(records, pattern):
    thread = turn = None
    messages, commands, completed_messages, completed_commands = {}, {}, set(), set()
    command_items, legacy_outputs = {}, {}
    response_calls = set()
    base_fields = {'timestamp', 'type', 'payload'}
    paginated = 'ordinal' in records[0]
    for index, record in enumerate(records):
        record_kind = _field(record, 'type')
        optional_fields = {'ordinal'} if paginated else set()
        if record_kind == 'response_item':
            optional_fields.add('metadata')
        _require(base_fields <= record.keys() <= base_fields | optional_fields
                 and _valid_timestamp(record.get('timestamp')), 'invalid native rollout envelope')
        if paginated:
            ordinal = record.get('ordinal')
            _require(type(ordinal) is int and ordinal == index, 'invalid native rollout ordinal')
        if 'metadata' in record:
            metadata = _object(record, 'metadata')
            _require(metadata.keys() <= {'history_sequence', 'sampled_through_sequence', 'retained_source'},
                     'unsupported native response metadata')
            for field in metadata.keys() - {'retained_source'}:
                _require(type(metadata[field]) is int and metadata[field] >= 0, 'invalid native sequence')
            source = metadata.get('retained_source')
            _require(source is None or (isinstance(source, dict) and source.keys() == {'source_id'}
                     and _string(source['source_id'])), 'unsupported native retained source metadata')
        payload = _object(record, 'payload')
        if record_kind == 'response_item':
            _response_item(payload, pattern)
            kind = _field(payload, 'type')
            if kind in {'function_call', 'custom_tool_call'}:
                identity = (kind, _identifier(payload, 'call_id'))
                _require(identity not in response_calls, 'duplicate native tool call')
                response_calls.add(identity)
            elif kind in {'function_call_output', 'custom_tool_call_output'}:
                identity = (kind.removesuffix('_output'), _identifier(payload, 'call_id'))
                _require(identity in response_calls, 'uncorrelated or duplicate native tool output')
                response_calls.remove(identity)
            continue
        if record_kind in ROLLOUT_METADATA:
            _require(not (payload.keys() & FRAGMENT_FIELDS), 'unsupported native rollout metadata fragment')
            if record_kind == 'session_meta':
                _require(thread is None, 'ambiguous native thread')
                thread = _identifier(payload, 'id')
            continue
        _require(record_kind == 'event_msg', 'unsupported native rollout record')
        kind = _field(payload, 'type')
        _require(payload.keys() & FRAGMENT_FIELDS <= ROLLOUT_FRAGMENT_FIELDS.get(kind, set()),
                 'unsupported native rollout fragment fields')
        if kind in {'task_started', 'turn_started'}:
            _require(not messages and not commands, 'unclosed native logical fragments')
            turn = _identifier(payload, 'turn_id')
            completed_messages.clear()
            completed_commands.clear()
            command_items.clear()
            legacy_outputs.clear()
        elif kind in {'task_complete', 'turn_complete'}:
            _require(not messages and not commands, 'unclosed native logical fragments')
            _require(_identifier(payload, 'turn_id') == turn, 'uncorrelated native turn')
            turn = None
        elif kind in {'agent_message_content_delta', 'item_completed'}:
            _require(_identifier(payload, 'thread_id') == thread and _identifier(payload, 'turn_id') == turn,
                     'uncorrelated native message')
            if kind == 'agent_message_content_delta':
                item_id = _identifier(payload, 'item_id')
                _require(item_id not in completed_messages, 'native message fragment after completion')
                messages.setdefault(item_id, []).append(_field(payload, 'delta'))
                continue
            item = _object(payload, 'item')
            item_id = _identifier(item, 'id')
            item_kind = _field(item, 'type')
            _require(not (item.keys() & FRAGMENT_FIELDS), 'unsupported native completed fragment')
            if item_kind == 'AgentMessage':
                _require(item_id not in completed_messages, 'duplicate native message completion')
                completed_messages.add(item_id)
                fragments = messages.pop(item_id, None)
                if fragments is not None:
                    joined = _check_fragments(fragments, pattern)
                final = _content({'Text'}, item.get('content'), pattern)
                if fragments is not None:
                    _require(joined == final, 'native message copies disagree')
            elif item_kind == 'CommandExecution':
                _require(item_id not in command_items, 'duplicate native command completion')
                output = item.get('aggregated_output')
                command_items[item_id] = '' if output is None else _field(item, 'aggregated_output')
                if item_id in legacy_outputs:
                    _require(command_items[item_id] == legacy_outputs[item_id], 'native tool copies disagree')
            elif item_kind == 'Plan':
                _field(item, 'text')
            elif item_kind == 'FunctionCallOutput':
                _tool_output(item.get('output'), pattern)
            elif item_kind == 'McpToolCall':
                _mcp_result(item.get('result'), pattern)
            elif item_kind == 'Reasoning':
                groups = []
                for key in ('summary_text', 'raw_content'):
                    value = item.get(key, [])
                    _require(isinstance(value, list) and all(isinstance(fragment, str) for fragment in value),
                             'unsupported native reasoning item fragment')
                    groups.append(_check_fragments(value, pattern))
                _check_fragments(groups, pattern)
            else:
                _require(item_kind in COMPLETED_ITEMS, 'unsupported native completed item')
        elif kind in {'exec_command_begin', 'exec_command_output_delta', 'terminal_interaction', 'exec_command_end'}:
            call = _identifier(payload, 'call_id')
            if kind in {'exec_command_begin', 'exec_command_end'}:
                _require(thread is not None and _identifier(payload, 'turn_id') == turn, 'uncorrelated native tool call')
            if kind == 'exec_command_begin':
                _require(call not in commands and call not in completed_commands, 'duplicate native tool call')
                commands[call] = ([], [])
                continue
            _require(call in commands, 'uncorrelated native tool fragment')
            if kind == 'exec_command_end':
                _close_command(payload, commands.pop(call), pattern)
                completed_commands.add(call)
                output = payload.get('aggregated_output')
                legacy_outputs[call] = '' if output is None else _field(payload, 'aggregated_output')
                if call in command_items:
                    _require(legacy_outputs[call] == command_items[call], 'native tool copies disagree')
            elif kind == 'terminal_interaction':
                process = _identifier(payload, 'process_id')
                _, inputs = commands[call]
                _require(not inputs or inputs[0][0] == process, 'ambiguous native terminal process')
                inputs.append((process, _field(payload, 'stdin')))
            else:
                stream, encoded = _field(payload, 'stream'), _field(payload, 'chunk')
                _require(stream in {'stdout', 'stderr'}, 'unsupported native command stream')
                try:
                    chunk = base64.b64decode(encoded, validate=True)
                except ValueError:
                    chunk = None
                _require(chunk is not None, 'invalid native command fragment encoding')
                commands[call][0].append((stream, chunk))
        elif kind == 'mcp_tool_call_end':
            result = _object(payload, 'result')
            _require(result.keys() in ({'Ok'}, {'Err'}), 'invalid native tool result')
            _mcp_result(result.get('Ok'), pattern)
        else:
            _require(kind in ROLLOUT_EVENTS, 'unsupported native rollout event')
    _require(not messages and not commands and not response_calls, 'unclosed native logical fragments')


def _json_lines(text, *, allow_empty):
    if not text and allow_empty:
        return []
    _require(text.endswith('\n'), 'JSONL is missing its record terminator')
    _require(text.count('\n') <= MAX_JSONL_RECORDS, 'JSONL exceeds record limit')
    records = [_parse_json(line) for line in text[:-1].split('\n')]
    _require(all(isinstance(record, dict) for record in records), 'JSONL record is not an object')
    return records


def _check_log(text, pattern):
    lines = text.splitlines()
    _require(len(lines) <= MAX_JSONL_RECORDS, 'log exceeds record limit')
    _check_fragments(lines, pattern)
    for line in lines:
        _require(not re.search(r'(?:\{\s*(?:"|\})|\[\s*(?:[\[{"\]]|-?\d|true\b|false\b|null\b))', line),
                 'structured output in a plain diagnostic stream')


def _atif_content(value, pattern):
    if isinstance(value, str):
        return value
    return _content({'text'}, value, pattern)


def _check_atif(trajectory, pattern):
    _require(isinstance(trajectory, dict) and trajectory.get('schema_version') == 'ATIF-v1.7'
             and not trajectory.get('subagent_trajectories') and not trajectory.get('continued_trajectory_ref'),
             'unqualified Harbor trajectory shape')
    steps = trajectory.get('steps')
    _require(isinstance(steps, list) and 0 < len(steps) <= MAX_JSONL_RECORDS, 'invalid Harbor trajectory steps')
    by_call = {}
    for step_id, step in enumerate(steps, 1):
        _require(isinstance(step, dict) and step.get('step_id') == step_id, 'invalid Harbor trajectory step order')
        _atif_content(step.get('message'), pattern)
        observation = step.get('observation')
        if observation is None:
            continue
        results = observation.get('results') if isinstance(observation, dict) else None
        _require(isinstance(results, list), 'unqualified Harbor observation')
        for result in results:
            _require(isinstance(result, dict) and not result.get('subagent_trajectory_ref'), 'unqualified Harbor result')
            if result.get('content') is not None:
                content = _atif_content(result['content'], pattern)
                call = result.get('source_call_id')
                _require(_string(call) and bool(call), 'unqualified Harbor result identity')
                by_call.setdefault(call, []).append(content)
    for fragments in by_call.values():
        _check_fragments(fragments, pattern)


def rollout_reasoning(record):
    kind, payload = record['type'], record['payload']
    if kind == 'response_item':
        return payload['type'] == 'reasoning'
    if kind != 'event_msg':
        return False
    event = payload['type']
    return (event in {'agent_reasoning', 'agent_reasoning_raw_content'}
            or (event == 'item_completed' and payload['item']['type'] == 'Reasoning'))


def sanitize_bytes(data, private_values, artifact_format):
    """Return sanitized bytes, or withhold the artifact by raising AccessError.

    Pass complete, drained bytes and the known artifact format. Native completion,
    same-origin cross-artifact binding and final tree publication are caller-owned.
    """
    _require(isinstance(data, bytes) and len(data) <= MAX_ARTIFACT_BYTES, 'unsupported artifact size or type')
    _require(isinstance(artifact_format, str), 'unsupported artifact format')
    text = _utf8(data)
    _require(not CONTROL.search(text), 'unrecognized binary input')
    pattern = _private_pattern(private_values)
    if artifact_format in ('text', 'log'):
        if artifact_format == 'log':
            _check_log(text, pattern)
        masked = _mask_text(text, pattern)
        output = masked.encode('utf-8')
        _require(len(output) <= MAX_ARTIFACT_BYTES, 'release exceeds size limit')
        return output
    try:
        if artifact_format in ('json', 'atif'):
            record = _parse_json(text)
            _require(isinstance(record, (dict, list)), 'unsupported JSON root')
            _check_fragments(list(_json_strings(record)), pattern)
            _check_fragments(list(_json_leaf_values(record)), pattern)
            if artifact_format == 'atif':
                _check_atif(record, pattern)
            masked = _mask_record(record, pattern)
            if artifact_format == 'atif':
                _check_atif(masked, pattern)
            output = _json_bytes(masked)
        else:
            _require(artifact_format in {'jsonl', 'native_exec', 'native_rollout'}, 'unsupported artifact format')
            records = _json_lines(text, allow_empty=artifact_format == 'jsonl')
            if artifact_format == 'native_exec':
                _exec_records(records, pattern)
            elif artifact_format == 'native_rollout':
                _rollout_records(records, pattern)
                records = [record for record in records if not rollout_reasoning(record)]
            else:
                _check_fragments(list(_json_leaf_values(records)), pattern)
                for record in records:
                    kind = record.get('type')
                    _require(not ((FRAGMENT_FIELDS | {'item', 'payload'}) & record.keys())
                             and not (isinstance(kind, str) and kind in EXEC_FIELDS),
                             'JSONL with native records or logical fragments needs a known schema')
            masked = [_mask_record(record, pattern) for record in records]
            if artifact_format == 'native_exec':
                _exec_records(masked, pattern)
            elif artifact_format == 'native_rollout':
                _require(masked == records, 'required native evidence would change under masking')
            output = b''.join(map(_json_bytes, masked))
        _require(len(output) <= MAX_ARTIFACT_BYTES, 'release exceeds size limit')
        _scan(output.decode('ascii'), pattern)
        return output
    except RecursionError:
        pass
    raise AccessError('JSON structure exceeds depth limit')
