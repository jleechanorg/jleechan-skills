#!/usr/bin/env python3
"""Run one scheduler-bound Dot coordinator turn using Pi and Chrome DevTools MCP."""
import argparse, json, os, re, shutil, signal, subprocess, sys, tempfile, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_native_schedule import node22_bins
SKILL = Path(__file__).resolve().parents[1] / 'SKILL.md'
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36'
TIMEOUT, GRACE = max(int(os.environ.get('COORDINATOR_TIMEOUT_SECS', '720')), 1), 8
class Blocked(RuntimeError):
    pass
def stop(proc):
    if not proc: return
    if proc.poll() is None:
        try: proc.terminate()
        except ProcessLookupError: pass
    deadline = time.monotonic() + GRACE
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            try: os.killpg(proc.pid, 0)
            except ProcessLookupError: return
        time.sleep(.1)
    for sig, pause in ((signal.SIGTERM, True), (signal.SIGKILL, False)):
        try: os.killpg(proc.pid, sig)
        except ProcessLookupError: return
        if pause:
            try: proc.wait(timeout=GRACE)
            except subprocess.TimeoutExpired: pass
            time.sleep(GRACE)

def pinned_mcp(node_bins):
    """Pick the Node 22 tree (or CHROME_DEVTOOLS_MCP_JS) that carries MCP 1.6.0."""
    js_path = Path('lib/node_modules/chrome-devtools-mcp/build/src/bin/chrome-devtools-mcp.js')
    override = os.environ.get('CHROME_DEVTOOLS_MCP_JS', '').strip()
    candidates = ([(None, Path(override).expanduser())] if override else []) + [(b, b.parent / js_path) for b in node_bins]
    for bin_dir, mcp_js in candidates:
        try: version = json.loads((mcp_js.parents[3] / 'package.json').read_text()).get('version')
        except (OSError, ValueError, IndexError): continue
        if mcp_js.is_file() and version == '1.6.0': return bin_dir or node_bins[0], mcp_js
    raise Blocked('pinned Chrome DevTools MCP 1.6.0 not found; searched: ' + ', '.join(str(c) for _, c in candidates))

def main():
    signal.signal(signal.SIGTERM, lambda signum, frame: sys.exit(128 + signum))
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--account', required=True, help='Exact machine-local Dot account key supplied by scheduler')
    p.add_argument('--instruction', default=os.environ.get('COORDINATOR_TASK', ''), help='Owner-provided task context or mode')
    args = p.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9._@+-]{1,160}', args.account): raise Blocked('invalid account key')
    cli_args = json.loads(os.environ.get('COORDINATOR_CLI_ARGS', '[]'))
    if not isinstance(cli_args, list) or any(not isinstance(arg, str) or any(ord(c) < 32 or ord(c) == 127 for c in arg) for arg in cli_args): raise Blocked('CLI arguments must be a JSON array of strings without control characters')
    expected = os.environ.get('DOT_EXPECTED_IDENTITY_SHA256', '').lower()
    if not re.fullmatch(r'[0-9a-f]{64}', expected): raise Blocked('expected identity binding is missing or invalid')
    node_bins = node22_bins(Path.home())
    if not node_bins: raise Blocked('Node 22 executable is unavailable')
    node_dir, mcp_bin = pinned_mcp(node_bins)
    os.environ['PATH'] = str(node_dir) + os.pathsep + str(Path.home() / '.local/bin') + os.pathsep + os.environ.get('PATH', '')
    config = json.loads(Path(os.environ.get('DOT_CONFIG_FILE', '~/.config/dot/config.json')).expanduser().read_text())
    accounts = config.get('accounts', {})
    if not isinstance(accounts, dict) or args.account not in accounts: raise Blocked('account is not configured')
    info = accounts[args.account]
    if not isinstance(info, dict) or not info.get('user_data_dir'): raise Blocked('account profile root is not configured')
    profile = Path(os.path.abspath(re.sub(r'^~', lambda _: str(Path.home()), info['user_data_dir'])))
    if profile.is_symlink(): raise Blocked('Dot profile root cannot be a symbolic link')
    canonical = profile.resolve()
    subprofile = info.get('profile_directory', 'Default')
    target = info.get('url') or config.get('default_url')
    if (not profile.is_dir() or not isinstance(subprofile, str) or subprofile in ('', '.', '..') or
        '/' in subprofile or '\\' in subprofile or (profile / subprofile).is_symlink() or not (profile / subprofile).is_dir()):
        raise Blocked('configured profile is unavailable')
    if not isinstance(target, str) or not target.startswith(('https://', 'http://')) or any(c.isspace() for c in target):
        raise Blocked('configured target URL is unavailable')
    chrome_root = (Path.home() / ('Library/Application Support/Google/Chrome' if sys.platform == 'darwin' else '.config/google-chrome')).resolve()
    if canonical == chrome_root or canonical in chrome_root.parents or chrome_root in canonical.parents:
        raise Blocked('Dot profile overlaps system Chrome profile')
    if os.path.lexists(profile / 'SingletonLock'):
        raise Blocked(f'SingletonLock present: close Chrome for this profile. Remove {profile}/SingletonLock, {profile}/SingletonCookie and {profile}/SingletonSocket only after verifying this host owns the profile and no Chrome or starting launch uses it; if any of that is uncertain, stop')
    if any(str(profile) in row and 'Chrome' in row for row in subprocess.check_output(['ps', '-Ao', 'args'], text=True).splitlines()):
        raise Blocked('a Chrome process already uses this Dot profile')
    chrome_bin = os.environ.get('DOT_CHROME_BIN') or ('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' if sys.platform == 'darwin' else '/usr/bin/google-chrome')
    pi_bin = os.environ.get('PI_BIN') or shutil.which('pi')
    if not Path(chrome_bin).is_file() or not pi_bin: raise Blocked('system Chrome or Pi is unavailable')
    mcp_args = [str(mcp_bin), '--executablePath=' + chrome_bin, '--userDataDir=' + str(profile),
        '--chromeArg=--profile-directory=' + subprofile, '--chromeArg=--user-agent=' + UA,
        '--chromeArg=--disable-blink-features=AutomationControlled',
        '--chromeArg=--no-first-run', '--chromeArg=--no-default-browser-check',
        '--ignoreDefaultChromeArg=--enable-automation', '--ignoreDefaultChromeArg=--password-store=basic',
        '--ignoreDefaultChromeArg=--use-mock-keychain']
    if sys.platform == 'darwin': mcp_args += ['--headless', '--chromeArg=--password-store=keychain']
    else:
        if not (os.environ.get('DISPLAY') or os.environ.get('DBUS_SESSION_BUS_ADDRESS')): raise Blocked('Linux keychain session is unavailable')
        mcp_args += ['--headless', '--chromeArg=--password-store=gnome-libsecret']
    with tempfile.TemporaryDirectory(prefix='dot-agent-', dir='/tmp') as run_dir:
        project = Path(run_dir) / '.pi'
        project.mkdir(mode=0o700)
        cfg = Path(os.environ.get('PI_CODING_AGENT_DIR', '~/.pi/agent')).expanduser() / 'mcp.json'
        names = json.loads(cfg.read_text()).get('mcpServers', {}) if cfg.exists() else {}
        if not isinstance(names, dict): raise Blocked('global Pi MCP config is invalid')
        servers = {name: {'enabled': False} for name in names}
        servers['dot_browser'] = {'command': str(node_dir / 'node'), 'args': mcp_args, 'exposure': 'direct'}
        mcp_file = project / 'mcp.json'
        mcp_file.write_text(json.dumps({'mcpServers': servers}))
        mcp_file.chmod(0o600)
        prompt = f'Account key: {args.account}\nConfigured target: {target}\nExpected identity SHA-256: {expected} (private binding; compare silently and return booleans only).\nOwner-provided task context: {args.instruction}\nRead and follow the loaded skill.'
        env = dict(os.environ, DOT_EXPECTED_IDENTITY_SHA256=expected, COORDINATOR_SELECTED_ACCOUNT=args.account, COORDINATOR_TARGET_URL=target)
        cmd = [pi_bin, *cli_args, '--print', '--no-session', '--approve', '--no-extensions', '-e', 'builtin:mcp',
            '--no-skills', '--skill', str(SKILL), '--tools', 'read,bash,edit,write,mcp__dot_browser__*', prompt]
        timed_out = False
        with tempfile.NamedTemporaryFile(prefix=f'dot-coordinator-pi-{args.account}-', suffix='.log',
                                         dir=tempfile.gettempdir(), delete=False, mode='w') as log:
            pi_log = Path(log.name)
            os.fchmod(log.fileno(), 0o600)
            proc = subprocess.Popen(cmd, cwd=run_dir, env=env, stdout=log,
                                    stderr=subprocess.STDOUT, text=True, start_new_session=True)
            try:
                proc.wait(timeout=TIMEOUT)
            except subprocess.TimeoutExpired:
                timed_out = True
            finally:
                stop(proc)
                transcript = pi_log.read_text(errors='replace').replace(expected, '[identity redacted]')
                pi_log.write_text(transcript)
        sys.stdout.write(transcript)
        if timed_out or proc.returncode:
            why = 'exceeded the deadline of %ds' % TIMEOUT if timed_out else 'failed (rc=%s)' % proc.returncode
            raise Blocked(f'Pi {why}; output kept at {pi_log}; verify delivery before any retry')
    return proc.returncode

if __name__ == '__main__':
    try: raise SystemExit(main())
    except (OSError, ValueError, subprocess.SubprocessError, Blocked, json.JSONDecodeError) as error:
        print('Dot coordinator blocked: ' + str(error), file=sys.stderr)
        raise SystemExit(2)
