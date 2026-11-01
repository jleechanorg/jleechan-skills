#!/usr/bin/env python3
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).resolve().parents[2] / "dot-coordinator/scripts/ping-dots.py"), run_name="__main__")

SKILL_MD = Path(__file__).resolve().parents[1] / 'SKILL.md'
def _md_block(tag):
    text = SKILL_MD.read_text()
    start = text.index('```text\n', text.index(f'<!-- PROMPT:{tag} -->')) + len('```text\n')
    return text[start:text.index('\n```', start)]
REMINDER_BODY = _md_block('REMINDER_BODY')
REMINDER_OPENING, MAX_RESPONSE_CHARS = REMINDER_BODY.splitlines()[0], 2600
PROMPT = _md_block('WRITER_PREFIX').format(limit=MAX_RESPONSE_CHARS) + '\n\n' + REMINDER_BODY
CLASSIFY_PROMPT_TEMPLATE, ESCALATION_BODY = _md_block('CLASSIFY_PROMPT_TEMPLATE') + '\n', _md_block('ESCALATION_BODY')
HAIKU_MODEL, MINIMAX_MODEL, MINIMAX_BASE_URL = 'claude-haiku-5-5', 'MiniMax-M3.1-Flash-Preview', 'https://api.minimax.io/anthropic'
LUNA_MODEL = os.environ.get('LUNAROUTE_MODEL') or 'deepseek-4.1-flash'
GEMINI_MODEL = os.environ.get('COORDINATOR_GEMINI_MODEL') or 'gemini-3.8-flash'
PROVIDERS, CLASSIFY_PROVIDERS = ('luna', 'minimax', 'codex', 'gemini'), ('luna', 'minimax', 'gemini')
IDENTITIES = {'agy': 'AGY', 'luna': 'LunaRoute', 'minimax': 'MiniMax Claude',
              'gemini': 'Gemini direct', 'codex': 'Codex', 'haiku': 'Claude Haiku'}
ATTRIBUTION_SUFFIX, MAX_CLASSIFY_REPLY_CHARS = 'coordinator: automated reminder; no new authority.', 6000
VALID_VERDICTS = ('compliant', 'working', 'reaction_only', 'unstructured_text', 'idle_refusal')
def bounded_run(command, stdin_text=None, timeout=180, cwd=None, env=None, check=True):
    stdin_file = tempfile.TemporaryFile(mode='w+') if stdin_text is not None else None
    try:
        if stdin_file is not None:
            stdin_file.write(stdin_text)
            stdin_file.seek(0)
        proc = subprocess.Popen(command, stdin=stdin_file or subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, cwd=cwd, env=env, start_new_session=True)
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            try: os.killpg(proc.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError): proc.kill()
            proc.communicate()
            raise
    finally:
        if stdin_file is not None: stdin_file.close()
    if check and proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, command, stderr=stderr)
    return subprocess.CompletedProcess(command, proc.returncode, stdout, stderr)
def run_with_stdin(command, stdin_text, timeout=180, **kwargs):
    return bounded_run(command, stdin_text=stdin_text, timeout=timeout, **kwargs)
def claude_json(model, env=None, prompt=PROMPT):
    command = [shutil.which('claude') or 'claude', '--strict-mcp-config', '--print', '--model', model, '--output-format', 'json', '--no-session-persistence', '--tools', '', '--disable-slash-commands', prompt]
    response = json.loads(bounded_run(command, timeout=180, cwd='/tmp', env=env).stdout)
    if not isinstance(response, dict) or response.get('is_error') is not False or not isinstance(response.get('result'), str):
        raise ValueError('Claude returned no successful result')
    return response['result']
def gemini_payload(prompt):
    return {'contents': [{'parts': [{'text': prompt}]}]}
def gemini_extract(body):
    try: text = body['candidates'][0]['content']['parts'][0]['text']
    except (KeyError, IndexError, TypeError): raise ValueError('Gemini returned no text candidate')
    if not isinstance(text, str) or not text.strip(): raise ValueError('Gemini returned empty text')
    return text
def generate_gemini(prompt=PROMPT):
    key = os.environ.get('GEMINI_API_KEY') or os.environ.get('WORLDAI_DEV_GEMINI_API_KEY')
    if not key: raise ValueError('GEMINI_API_KEY unavailable')
    url = 'https://generativelanguage.googleapis.com/v1beta/models/' + GEMINI_MODEL + ':generateContent'
    req = urllib.request.Request(url, data=json.dumps(gemini_payload(prompt)).encode(),
                                 headers={'Content-Type': 'application/json', 'x-goog-api-key': key})
    with urllib.request.urlopen(req, timeout=180) as response:
        return gemini_extract(json.loads(response.read().decode()))
def generate(provider, prompt=PROMPT):
    if provider == 'gemini': return generate_gemini(prompt=prompt)
    if provider == 'agy':
        command = [os.environ.get('COORDINATOR_AGY') or shutil.which('agy') or 'agy',
                   '--dangerously-skip-permissions', '--new-project', '--print-timeout', '180s',
                   '--input-format', 'stream-json', '--output-format', 'stream-json']
        request = json.dumps({'event': 'user', 'message': {'content': prompt}}) + '\n'
        with tempfile.TemporaryDirectory(prefix='dot-ping-agy-', dir='/tmp') as workdir:
            result = run_with_stdin(command, request, cwd=workdir)
        events = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
        if any(not isinstance(event, dict) for event in events): raise ValueError('AGY returned malformed event data')
        results = [event.get('result') for event in events if event.get('event') == 'result']
        if len(results) != 1 or not isinstance(results[0], dict) or results[0].get('status') != 'SUCCESS':
            raise ValueError('AGY returned no single successful result')
        if not isinstance(results[0].get('response'), str): raise ValueError('AGY returned no text response')
        return results[0]['response']
    if provider == 'luna':
        key = os.environ.get('LUNAROUTE_API_KEY') or bounded_run([shutil.which('lunaroute') or 'lunaroute', 'key'], timeout=30).stdout.strip()
        if not key: raise ValueError('LunaRoute key unavailable')
        command = [shutil.which('pi') or 'pi', '--provider', 'lunaroute', '--model', LUNA_MODEL, '--print', '--mode',
                   'text', '--no-session', '--no-tools', '--no-extensions', '--no-skills', '--no-mcp', '--no-prompt-templates', prompt]
        return bounded_run(command, timeout=180, cwd='/tmp', env=dict(os.environ, LUNAROUTE_API_KEY=key)).stdout
    if provider == 'minimax':
        key = os.environ.get('MINIMAX_API_KEY')
        if not key: raise ValueError('MINIMAX_API_KEY unavailable')
        env = dict(os.environ, ANTHROPIC_BASE_URL=MINIMAX_BASE_URL, ANTHROPIC_AUTH_TOKEN=key, ANTHROPIC_MODEL=MINIMAX_MODEL)
        env.pop('ANTHROPIC_API_KEY', None)
        return claude_json(MINIMAX_MODEL, env, prompt=prompt)
    if provider == 'codex':
        gen = os.environ.get('COORDINATOR_GENERATOR') or shutil.which('codex-luna') or shutil.which('codex') or 'codex'
        cmd = [gen] + ([] if Path(gen).name == 'codex-luna' else ['exec', '--yolo', '-m', 'gpt-6-luna'])
        with tempfile.TemporaryDirectory(prefix='dot-ping-codex-', dir='/tmp') as workdir:
            with tempfile.NamedTemporaryFile(mode='r+', dir=workdir, prefix='message-') as output:
                run_with_stdin(cmd + ['--ephemeral', '--skip-git-repo-check', '--config', 'project_doc_max_bytes=0',
                                      '--output-last-message', output.name], prompt, cwd=workdir)
                output.seek(0)
                return output.read()
    if provider == 'haiku': return claude_json(HAIKU_MODEL, prompt=prompt)
    raise ValueError('Unknown generator: ' + provider)
def generate_message(providers):
    for provider in providers:
        try:
            message = generate(provider)
            if not isinstance(message, str): raise ValueError('response is not text')
            stripped = message.strip()
            if not stripped: raise ValueError(f'response empty after trimming ({len(message):,} raw characters)')
            if len(stripped) > MAX_RESPONSE_CHARS:
                raise ValueError(f'response exceeds {MAX_RESPONSE_CHARS:,} characters ({len(stripped):,} stripped; {len(message):,} raw)')
            collapse = lambda text: ' '.join(text.replace('’', "'").split())
            if not stripped.startswith(REMINDER_OPENING):
                raise ValueError('response does not begin with the required inventory sentence')
            if collapse(stripped) != collapse(REMINDER_BODY):
                raise ValueError('response changed the required recovery instructions')
            print('Generation succeeded with ' + provider)
            return provider, REMINDER_BODY
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            print(provider + ' generation failed: ' + str(error), file=sys.stderr)
            if isinstance(error, subprocess.CalledProcessError) and error.stderr:
                print(error.stderr[:4000], file=sys.stderr)
    raise ValueError('All generation providers failed; no Dot send')
def extract_reply_after_reminder(page_text):
    if not isinstance(page_text, str) or not page_text.strip(): return ''
    cut = page_text.rfind(ATTRIBUTION_SUFFIX)
    if cut == -1 or page_text.find(REMINDER_OPENING, 0, cut) == -1: return ''
    return page_text[cut + len(ATTRIBUTION_SUFFIX):].strip()
def parse_verdict(raw_text):
    if not isinstance(raw_text, str) or not raw_text.strip(): raise ValueError('Empty classifier output')
    cleaned = raw_text.strip()
    if cleaned.startswith('```'):
        lines = cleaned.splitlines()[1:]
        cleaned = '\n'.join(lines[:-1] if lines and lines[-1].strip() == '```' else lines).strip()
    try: obj = json.loads(cleaned)
    except ValueError as error: raise ValueError('Invalid classifier JSON: ' + str(error)) from error
    if not isinstance(obj, dict) or obj.get('verdict') not in VALID_VERDICTS:
        raise ValueError('Invalid classifier verdict: ' + repr(obj))
    return obj['verdict']
def classify_response(page_text, providers=CLASSIFY_PROVIDERS):
    reply = extract_reply_after_reminder(page_text)
    if not reply: return 'no_response'
    prompt = CLASSIFY_PROMPT_TEMPLATE.format(reply_text=reply[:MAX_CLASSIFY_REPLY_CHARS].replace('</', '<\\/'))
    for provider in providers:
        if provider in CLASSIFY_PROVIDERS:
            try: return parse_verdict(generate(provider, prompt))
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                print(provider + ' classification failed: ' + str(error), file=sys.stderr)
    return 'classification_unavailable'
def read_tail(dot, account, env, chars=12000, timeout=180):
    return bounded_run([dot, '--account', account, 'read', str(chars)], timeout=timeout, env=env, check=False).stdout
def read_and_classify(dot, account, env, windows=None, providers=CLASSIFY_PROVIDERS):
    windows = windows or tuple(int(n) for n in os.environ.get('COORDINATOR_READ_WINDOWS', '12000,40000').split(','))
    verdict = 'no_response'
    for chars in windows:
        verdict = classify_response(read_tail(dot, account, env, chars=chars), providers=providers)
        if verdict != 'no_response': return verdict
    return verdict
def verify_and_escalate(dot, account, env, provider, state_file, wait_secs=180, recheck_secs=120, providers=None):
    c_provs = tuple(providers) if providers is not None else (
        (provider,) + tuple(p for p in CLASSIFY_PROVIDERS if p != provider) if provider in CLASSIFY_PROVIDERS else CLASSIFY_PROVIDERS)
    time.sleep(min(max(wait_secs, 0), 900))
    verdict = read_and_classify(dot, account, env, providers=c_provs)
    if verdict not in ('compliant', 'classification_unavailable') and recheck_secs > 0:
        time.sleep(min(max(recheck_secs, 0), 600))
        verdict = read_and_classify(dot, account, env, providers=c_provs)
    record = json.loads(state_file.read_text()) if state_file.exists() else {}
    record.update(last_response_status=verdict, last_response_checked_epoch=int(time.time()))
    if verdict == 'compliant':
        record.update(consecutive_noncompliance=0, consecutive_classification_failures=0)
        print(account + ': response compliant')
    elif verdict == 'working':
        record['consecutive_classification_failures'] = 0
        print(account + ': response working; no escalation')
    elif verdict == 'classification_unavailable':
        record['consecutive_classification_failures'] = int(record.get('consecutive_classification_failures', 0)) + 1
        print(account + ': response classification_unavailable; no escalation')
    else:
        record['consecutive_classification_failures'] = 0
        if record.get('escalation_unverified'):
            print(account + ': escalation delivery remains unverified; no retry')
        else:
            record.update(escalation_verified=False, escalation_unverified=True, delivery_unverified=True, last_status='UNVERIFIED_SEND_ESCALATION_PENDING'); delivery_state(state_file, **record)
            with tempfile.NamedTemporaryFile(mode='w+', prefix='dot-escalation-', dir='/tmp') as file:
                file.write(ESCALATION_BODY + '\nFrom ' + IDENTITIES.get(provider, 'Coordinator') + ' coordinator: automated escalation; no new authority.')
                file.flush()
                sent = bounded_run([dot, '--account', account, 'send-once', file.name], timeout=180, env=env, check=False)
            authoritative = sent.returncode == 0 and 'DOT_SERVER_ACCEPTED' in sent.stdout.splitlines()
            no_dispatch = sent.returncode == 3 and any(line == 'DOT_DRAFT_PRESENT' or line.startswith('DOT_DRAFT_PRESENT:') for line in sent.stdout.splitlines()) and not any(marker in sent.stdout for marker in ('DOT_SERVER_ACCEPTED', 'DOT_SENT_VERIFIED', 'DOT_SEND_UNVERIFIED'))
            record.update(escalation_sent_epoch=int(time.time()) if not no_dispatch else record.get('escalation_sent_epoch', 0), escalation_verified=authoritative, escalation_unverified=not (authoritative or no_dispatch), delivery_unverified=not (authoritative or no_dispatch), last_status='SUCCESS' if authoritative else 'SKIPPED_COMPOSER_BUSY' if no_dispatch else 'UNVERIFIED_SEND_ESCALATION', consecutive_noncompliance=int(record.get('consecutive_noncompliance', 0)) + 1)
            print(account + ': response ' + verdict + '; escalation ' + ('sent' if authoritative else 'peer draft; no dispatch' if no_dispatch else 'unverified hold; no retry'))
    delivery_state(state_file, **record)
    return verdict
def delivery_message(provider, message):
    if message != REMINDER_BODY: raise ValueError('The complete required recovery instructions must be delivered')
    return message + '\nFrom ' + IDENTITIES[provider] + ' coordinator: automated reminder; no new authority.'
def delivery_state(path, **fields):
    marker = path.with_name(path.name + '.hold') if fields.get('last_status') in ('SUCCESS', 'SKIPPED_COMPOSER_BUSY') and not path.name.endswith('.hold') else None
    if marker: delivery_state(marker, delivery_unverified=True)
    record = json.loads(path.read_text()) if path.exists() else {}; record.update(fields); record.setdefault('last_sent_epoch', 0)
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, prefix='.delivery-', delete=False) as file:
        json.dump(record, file, indent=2, sort_keys=True); file.write('\n'); file.flush(); os.fsync(file.fileno())
    os.replace(file.name, path); directory = os.open(path.parent, os.O_RDONLY)
    try: os.fsync(directory)
    finally: os.close(directory)
    if marker: marker.unlink(missing_ok=True)
def due_account(accounts, role, now):
    offsets = (0, 20, 40) if role == 'mac' else (30, 50, 10)
    sec = time.localtime(now).tm_min * 60 + time.localtime(now).tm_sec
    return next((a for a, m in zip(accounts, offsets) if 0 <= (sec - m * 60) % 3600 <= 120), None)
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--account', help='One configured account; otherwise use this host’s due slot')
    parser.add_argument('--generator', choices=('auto',) + tuple(IDENTITIES), default='auto')
    parser.add_argument('--generate-only', action='store_true', help='Generate and print one message without sending')
    args = parser.parse_args()
    config = json.loads(Path(os.environ.get('DOT_CONFIG_FILE', '~/.config/dot/config.json')).expanduser().read_text())
    accounts = config.get('rotation') or list(config.get('accounts', {}))
    if not isinstance(accounts, list) or len(accounts) != 3 or len(set(accounts)) != 3:
        raise ValueError('Configure exactly three distinct Dot account keys')
    account = args.account or due_account(accounts, 'mac' if platform.system() == 'Darwin' else 'linux', time.time())
    if account is None: print('No account due; no send'); return 0
    if account not in accounts: raise ValueError('Unknown configured account')
    state = Path(os.environ.get('COORDINATOR_STATE_DIR', '~/.local/state/ai.gemini.agy-dot-coordinator')).expanduser()
    state.mkdir(mode=0o700, parents=True, exist_ok=True)
    with Path(os.environ.get('COORDINATOR_LOCK_FILE', '/tmp/ai.gemini.agy-dot-coordinator.lock')).open('a') as lock:
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('Another ping is running; no send')
            return 0
        if (state / 'STOP').exists():
            print('STOP is present; no send')
            return 0
        for path in (state / 'state.json', state / ('state_' + account + '.json')):
            if path.with_name(path.name + '.hold').exists(): print(account + ': existing delivery hold; no send'); return 0
            rec = json.loads(path.read_text()) if path.exists() else {}
            rec = rec.get('accounts', {}).get(account, rec)
            if rec.get('delivery_unverified') or str(rec.get('last_status', '')).startswith('UNVERIFIED_SEND'): print(account + ': existing delivery hold; no send'); return 0
        provider, message = generate_message(PROVIDERS if args.generator == 'auto' else (args.generator,))
        if args.generate_only: print(message); return 0
        if (state / 'STOP').exists():
            print('STOP is present; no send')
            return 0
        env = {k: v for k, v in dict(os.environ, DOT_ROTATE_ON_LIMIT='0').items() if k not in ('DOT_REMOTE_HOST', 'DOT_CHROME_USER_DATA', 'DOT_URL', 'DOT_CLEAR_DRAFT')}
        dot = os.environ.get('COORDINATOR_DOT_SCRIPT', str(Path(__file__).resolve().parents[2] / 'dot/scripts/dot.sh'))
        hold = state / ('state_' + account + '.json'); delivery_state(hold, account=account, last_status='UNVERIFIED_SEND_PENDING', last_summary='Awaiting authoritative receipt', delivery_unverified=True)
        with tempfile.NamedTemporaryFile(mode='w+', prefix='dot-ping-', dir='/tmp') as file:
            file.write(delivery_message(provider, message))
            file.flush()
            sent = bounded_run([dot, '--account', account, 'send-once', file.name], timeout=180, env=env, check=False)
        sys.stdout.write(sent.stdout); sys.stderr.write(sent.stderr)
        if sent.returncode == 0 and 'DOT_SERVER_ACCEPTED' in sent.stdout.splitlines():
            delivery_state(hold, account=account, last_status='SUCCESS', last_summary='Authoritative server acceptance receipt', last_sent_epoch=int(time.time()), delivery_unverified=False); print(account + ': sent')
        elif sent.returncode == 0 and 'DOT_SENT_VERIFIED' in sent.stdout.splitlines():
            delivery_state(hold, account=account, last_status='UNVERIFIED_SEND_UI_OBSERVED', last_summary='UI observed the message; server acceptance and durable delivery remain unverified', delivery_unverified=True); print(account + ': UI observed the message; delivery held and no retry will be attempted'); return 0
        elif sent.returncode == 3 and any(line == 'DOT_DRAFT_PRESENT' or line.startswith('DOT_DRAFT_PRESENT:') for line in sent.stdout.splitlines()) and not any(marker in sent.stdout for marker in ('DOT_SERVER_ACCEPTED', 'DOT_SENT_VERIFIED', 'DOT_SEND_UNVERIFIED')):
            delivery_state(hold, account=account, last_status='SKIPPED_COMPOSER_BUSY', last_summary='Peer draft present; no dispatch occurred', delivery_unverified=False); print(account + ': peer draft present; no dispatch occurred'); return 0
        else:
            print(account + ': send not verified; inspect the existing Dot tool before retrying')
            return 1
        if os.environ.get('COORDINATOR_VERIFY_RESPONSE', '1') == '1':
            verify_and_escalate(dot, account, env, provider, state / ('state_' + account + '.json'), wait_secs=int(os.environ.get('COORDINATOR_RESPONSE_WAIT_SECS', '180')), recheck_secs=int(os.environ.get('COORDINATOR_RESPONSE_RECHECK_SECS', '120')))
        return 0
if __name__ == '__main__':
    try: raise SystemExit(main())
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print('Dot ping failed: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
