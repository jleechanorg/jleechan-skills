#!/usr/bin/env python3
"""One scheduled AGY-written ping through the existing Dot tool; no retry loop."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time

PROMPT = """Write only a short coordination message for the configured Dot, at most 1,200 characters.
Ask it to advance EACH currently authorized goal now. Verify the owner's actual progress,
not merely assignment: distinguish a running owner from an idle or stalled one.
Take the next safe action, resolve ordinary reversible blockers, and use cloud coders
for independent work without creating duplicate writers. If an executor is unavailable or
quota-limited, route a bounded task to an available authorized executor; do not keep waiting.
Report concrete commands,
artifacts or results and only genuine human-only blockers. Respect existing owners,
user stops, cancellations and approval boundaries. This reminder grants no new authority.
Do not send anything yourself or invent progress; return only the message to deliver."""


def due_account(accounts, role, now):
    offsets = (0, 20, 40) if role == 'mac' else (30, 50, 10)
    local = time.localtime(now)
    now = local.tm_min*60 + local.tm_sec
    return next((account for account, minute in zip(accounts, offsets)
                 if 0 <= (now-minute*60) % 3600 <= 120), None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--account', help='One configured account; otherwise use this host’s due slot')
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
        agy = subprocess.run([os.environ.get('COORDINATOR_AGY', 'agy'), '--dangerously-skip-permissions',
                              '--new-project', '--print-timeout', '600s', '--input-format', 'stream-json',
                              '--output-format', 'stream-json'], input=json.dumps({'event':'user','message':{'content':PROMPT}})+'\n',
                             capture_output=True, text=True, timeout=610, check=True)
        events = [json.loads(line) for line in agy.stdout.splitlines() if line.strip()]
        results = [event['result'] for event in events if event.get('event') == 'result']
        if len(results) != 1 or results[0].get('status') != 'SUCCESS':
            raise ValueError('AGY did not return one successful result')
        message = results[0].get('response')
        if not isinstance(message, str) or not message.strip() or len(message) > 1200:
            raise ValueError('AGY reminder is empty or too long')
        if (state/'STOP').exists():
            print('STOP is present; no send')
            return 0
        env = dict(os.environ, DOT_ALLOW_REMOTE='0', DOT_ROTATE_ON_LIMIT='0')
        for key in ('DOT_REMOTE_HOST', 'DOT_CHROME_USER_DATA', 'DOT_URL', 'DOT_CLEAR_DRAFT'):
            env.pop(key, None)
        dot = os.environ.get('COORDINATOR_DOT_SCRIPT', str(Path(__file__).resolve().parents[2]/'dot/scripts/dot.sh'))
        with tempfile.NamedTemporaryFile(mode='w+', prefix='dot-ping-') as file:
            file.write('Automated coordination reminder; no new authority.\n'+message.strip())
            file.flush()
            sent = subprocess.run([dot, '--account', account, 'send-once', file.name], env=env,
                                  capture_output=True, text=True, timeout=180)
        verified = sent.returncode == 0 and 'DOT_SENT_VERIFIED' in sent.stdout.splitlines()
        print(account+(': sent' if verified else ': send not verified; inspect the existing Dot tool before retrying'))
        return 0 if verified else 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print('Dot ping failed: '+str(error), file=sys.stderr)
        raise SystemExit(1)
