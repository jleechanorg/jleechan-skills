"""Render native definitions only; activation needs a separate coordinated handoff."""
import argparse
import json
from pathlib import Path
import plistlib
import subprocess

LABEL = 'ai.gemini.agy-dot-coordinator'


def quoted(value, expand=True):
    value = value.replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%')
    return '"' + (value.replace('$', '$$') if expand else value) + '"'


def render(config, role):
    if role not in ('mac', 'linux'):
        raise ValueError('role must be mac or linux')
    for key in ('python', 'node', 'worker', 'config', 'state'):
        value = config[key]
        if not isinstance(value, str) or not Path(value).is_absolute() or any(ord(c) < 32 for c in value):
            raise ValueError(f'{key} must be an absolute path without control characters')
    version = subprocess.run([config['node'], '--version'], capture_output=True, text=True, timeout=5, check=True).stdout.strip()
    if not version.startswith('v22.'):
        raise ValueError('Node 22 is required')
    argv = [config['python'], config['worker'], '--role', role, '--config', config['config']]
    environment = {'DOT_NODE': config['node'], 'DOT_ROTATE_ON_LIMIT': '0', 'DOT_ALLOW_REMOTE': '0'}
    if role == 'mac':
        definition = dict(Label=LABEL, ProgramArguments=argv,
                          StartCalendarInterval=[{'Minute': minute} for minute in (0, 20, 40)],
                          EnvironmentVariables=environment, ProcessType='Background',
                          StandardOutPath=str(Path(config['state'])/'native.stdout.log'),
                          StandardErrorPath=str(Path(config['state'])/'native.stderr.log'))
        return {LABEL+'.plist': plistlib.dumps(definition)}
    service = '\n'.join([
        '[Unit]', 'Description=Finite AGY Dot reminder', '', '[Service]', 'Type=oneshot',
        'ExecStart='+' '.join(map(quoted, argv)),
        *['Environment='+quoted(key+'='+value, expand=False) for key, value in environment.items()],
        'TimeoutStartSec=1200', 'TimeoutStopSec=10', 'KillMode=control-group',
        'UMask=0077', 'StandardOutput=journal', 'StandardError=journal', '',
    ])
    timer = '\n'.join([
        '[Unit]', 'Description=Offset AGY Dot reminders', '', '[Timer]',
        'OnCalendar=*-*-* *:10,30,50:00 UTC', 'Persistent=false', 'AccuracySec=1s',
        'RandomizedDelaySec=0', 'Unit='+LABEL+'.service', '', '[Install]',
        'WantedBy=timers.target', '',
    ])
    return {LABEL+'.service': service.encode(), LABEL+'.timer': timer.encode()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--role', required=True, choices=['mac', 'linux'])
    parser.add_argument('--config', required=True)
    parser.add_argument('--output', required=True, help='Render destination; does not install or enable')
    args = parser.parse_args()
    definitions = render(json.loads(Path(args.config).read_text()), args.role)
    destination = Path(args.output)
    destination.mkdir(mode=0o700, parents=True, exist_ok=True)
    for name, data in definitions.items():
        (destination/name).write_bytes(data)
