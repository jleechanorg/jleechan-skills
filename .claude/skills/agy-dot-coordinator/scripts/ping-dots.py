#!/usr/bin/env python3
"""One scheduled model-written ping through the existing Dot tool; no retry loop."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import time

REMINDER_OPENING = 'Inventory the work I asked for in the last 24 hours and verify what’s done versus not done.'
REMINDER_BODY = (
    'Inventory the work I asked for in the last 24 hours and verify what’s done versus not done. '
    'Resume every unfinished authorized request within capacity. '
    'Recover outcome, durable checkpoint and acceptance gap; check latest scope. '
    'Give owners safe next actions, not status queries; verify owner state before reassignment. '
    'Diagnose failures and safely repair/retry; avoid duplicate writers. '
    'Before waiting, check EACH last-24h request and older commitment for feasible alternate execution, validation or design work; do it. '
    'A publication hold needn\'t block safe testing/design. '
    'Local substeps and blocked work aren\'t completed user outcomes. '
    'Name blocked action, cause, missing capability/approval and concrete unblock; recheck only on new evidence. '
    'Use authorized cloud coders; honor explicit environments. '
    'Six useful tasks is a target, not permission or filler. '
    'Owner-approved scope needs no re-approval; merge, destructive, credential gates still need the user. '
    'Report commit URLs, PR URLs or artifacts as proof; Working/timestamps/HEARTBEAT_OK prove nothing. '
    'Wait quietly only when all such work is blocked, with exact blockers.'
)
PROMPT = (
    'Writer: return the recipient paragraph below unchanged, at most 1,200 characters. '
    'The recipient executes these instructions; you only write the reminder. '
    'Return only that paragraph, without a heading, list, attribution, or claims of progress.\n\n'
    + REMINDER_BODY
)
HAIKU_MODEL = 'claude-haiku-5-5'
MAX_RESPONSE_CHARS = 1200


def generate(provider):
    if provider == 'agy':
        command = [os.environ.get('COORDINATOR_AGY') or shutil.which('agy') or 'agy',
                   '--dangerously-skip-permissions', '--new-project', '--print-timeout', '180s',
                   '--input-format', 'stream-json', '--output-format', 'stream-json']
        request = json.dumps({'event': 'user', 'message': {'content': PROMPT}})+'\n'
        with tempfile.TemporaryDirectory(prefix='dot-ping-agy-', dir='/tmp') as workdir:
            result = subprocess.run(command, input=request, capture_output=True, text=True,
                                    cwd=workdir, timeout=180, check=True)
        events = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
        if any(not isinstance(event, dict) for event in events):
            raise ValueError('AGY returned malformed event data')
        results = [event.get('result') for event in events if event.get('event') == 'result']
        if (len(results) != 1 or not isinstance(results[0], dict)
                or results[0].get('status') != 'SUCCESS'):
            raise ValueError('AGY returned no single successful result')
        response = results[0].get('response')
        if not isinstance(response, str):
            raise ValueError('AGY returned no text response')
        return response

    if provider == 'codex':
        generator = os.environ.get('COORDINATOR_GENERATOR') or shutil.which('codex-luna') or shutil.which('codex') or 'codex'
        command = [generator]
        if Path(generator).name != 'codex-luna':
            command += ['exec', '--yolo', '-m', 'gpt-6-luna']
        with tempfile.TemporaryDirectory(prefix='dot-ping-codex-', dir='/tmp') as workdir:
            with tempfile.NamedTemporaryFile(mode='r+', dir=workdir, prefix='message-') as output:
                subprocess.run(command + ['--ephemeral', '--skip-git-repo-check',
                                           '--config', 'project_doc_max_bytes=0',
                                           '--output-last-message', output.name], input=PROMPT,
                               cwd=workdir, capture_output=True, text=True, timeout=180, check=True)
                output.seek(0)
                return output.read()

    if provider == 'haiku':
        command = [shutil.which('claude') or 'claude', '--dangerously-skip-permissions',
                   '--print', '--model', HAIKU_MODEL, '--output-format', 'json',
                   '--no-session-persistence', '--tools', '', '--disable-slash-commands', PROMPT]
        result = subprocess.run(command, cwd='/tmp', capture_output=True,
                                text=True, timeout=180, check=True)
        response = json.loads(result.stdout)
        if (not isinstance(response, dict) or response.get('is_error') is not False
                or not isinstance(response.get('result'), str)):
            raise ValueError('Claude returned no successful result')
        return response['result']

    raise ValueError('Unknown generator: '+provider)


def generate_message(providers):
    for provider in providers:
        try:
            message = generate(provider)
            if not isinstance(message, str):
                raise ValueError('response is not text')
            stripped = message.strip()
            if not stripped:
                raise ValueError(
                    f'response empty after trimming ({len(message):,} raw characters)'
                )
            if len(stripped) > MAX_RESPONSE_CHARS:
                raise ValueError(
                    f'response exceeds {MAX_RESPONSE_CHARS:,} characters '
                    f'({len(stripped):,} stripped; {len(message):,} raw)'
                )
            if not stripped.startswith(REMINDER_OPENING):
                raise ValueError('response does not begin with the required inventory sentence')
            if stripped != REMINDER_BODY:
                raise ValueError('response changed the required recovery instructions')
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            print(provider+' generation failed: '+str(error), file=sys.stderr)
            if isinstance(error, subprocess.CalledProcessError) and error.stderr:
                print(error.stderr[:4000], file=sys.stderr)
            continue
        print('Generation succeeded with '+provider)
        return provider, stripped
    raise ValueError('All generation providers failed; no Dot send')


def delivery_message(provider, message):
    if message != REMINDER_BODY:
        raise ValueError('The complete required recovery instructions must be delivered')
    identity = {'agy': 'AGY', 'codex': 'Codex', 'haiku': 'Claude Haiku'}[provider]
    return message + '\nFrom ' + identity + ' coordinator: automated reminder; no new authority.'


def due_account(accounts, role, now):
    offsets = (0, 20, 40) if role == 'mac' else (30, 50, 10)
    local = time.localtime(now)
    now = local.tm_min*60 + local.tm_sec
    return next((account for account, minute in zip(accounts, offsets)
                 if 0 <= (now-minute*60) % 3600 <= 120), None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--account', help='One configured account; otherwise use this host’s due slot')
    parser.add_argument('--generator', choices=('auto', 'agy', 'codex', 'haiku'), default='auto')
    parser.add_argument('--generate-only', action='store_true', help='Generate and print one message without sending')
    args = parser.parse_args()
    config = json.loads(Path(os.environ.get('DOT_CONFIG_FILE', '~/.config/dot/config.json')).expanduser().read_text())
    accounts = config.get('rotation') or list(config.get('accounts', {}))
    if not isinstance(accounts, list) or len(accounts) != 3 or len(set(accounts)) != 3:
        raise ValueError('Configure exactly three distinct Dot account keys')
    role = 'mac' if platform.system() == 'Darwin' else 'linux'
    account = args.account or due_account(accounts, role, time.time())
    if account is None:
        print('No account due; no send')
        return 0
    if account not in accounts:
        raise ValueError('Unknown configured account')
    state = Path(os.environ.get('COORDINATOR_STATE_DIR', '~/.local/state/ai.gemini.agy-dot-coordinator')).expanduser()
    state.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock_path = Path(os.environ.get('COORDINATOR_LOCK_FILE', '/tmp/ai.gemini.agy-dot-coordinator.lock'))
    with lock_path.open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('Another ping is running; no send')
            return 0
        if (state/'STOP').exists():
            print('STOP is present; no send')
            return 0
        for path in (state/'state.json', state/('state_'+account+'.json')):
            if path.exists():
                record = json.loads(path.read_text())
                record = record.get('accounts', {}).get(account, record)
                if record.get('delivery_unverified') or str(record.get('last_status', '')).startswith('UNVERIFIED_SEND'):
                    print(account+': existing delivery hold; no send')
                    return 0
        providers = ('agy', 'codex', 'haiku') if args.generator == 'auto' else (args.generator,)
        provider, message = generate_message(providers)
        if args.generate_only:
            print(message)
            return 0
        if (state/'STOP').exists():
            print('STOP is present; no send')
            return 0
        env = dict(os.environ, DOT_ROTATE_ON_LIMIT='0')
        for key in ('DOT_REMOTE_HOST', 'DOT_CHROME_USER_DATA', 'DOT_URL', 'DOT_CLEAR_DRAFT'):
            env.pop(key, None)
        dot = os.environ.get('COORDINATOR_DOT_SCRIPT', str(Path(__file__).resolve().parents[2]/'dot/scripts/dot.sh'))
        with tempfile.NamedTemporaryFile(mode='w+', prefix='dot-ping-', dir='/tmp') as file:
            file.write(delivery_message(provider, message))
            file.flush()
            sent = subprocess.run([dot, '--account', account, 'send-once', file.name], env=env,
                                  capture_output=True, text=True, timeout=180)
        sys.stdout.write(sent.stdout)
        sys.stderr.write(sent.stderr)
        verified = sent.returncode == 0 and 'DOT_SENT_VERIFIED' in sent.stdout.splitlines()
        print(account+(': sent' if verified else ': send not verified; inspect the existing Dot tool before retrying'))
        return 0 if verified else 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print('Dot ping failed: '+str(error), file=sys.stderr)
        raise SystemExit(1)
