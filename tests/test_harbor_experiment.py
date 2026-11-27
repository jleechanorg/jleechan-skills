import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'harbor_experiment.py'

spec = importlib.util.spec_from_file_location('harbor_experiment', SCRIPT)
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


def git(repo, *args):
    return subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def cli(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True)


def test_snapshot_excludes_future_and_preserves_repo(tmp_path):
    repo = tmp_path / 'repo'
    repo.mkdir()
    git(repo, 'init', '-q')
    git(repo, 'config', 'user.name', 'Test')
    git(repo, 'config', 'user.email', 'test@example.invalid')
    (repo / 'old').write_text('old')
    git(repo, 'add', '.')
    git(repo, 'commit', '-qm', 'old')
    old = git(repo, 'rev-parse', 'HEAD')
    (repo / 'future').write_text('future')
    git(repo, 'add', '.')
    git(repo, 'commit', '-qm', 'future')
    (repo / 'dirty').write_text('local')
    before = git(repo, 'status', '--porcelain')
    out = tmp_path / 'snapshot'
    result = cli('snapshot', '--repo', repo, '--commit', old, '--output', out)
    assert result.returncode == 0, result.stderr
    assert (out / 'old').read_text() == 'old'
    assert not (out / 'future').exists() and not (out / '.git').exists()
    assert git(repo, 'status', '--porcelain') == before
    receipt = json.loads((tmp_path / 'snapshot.receipt.json').read_text())
    assert receipt['repository_commit'] == old
    assert receipt['sha256']


def test_snapshot_rejects_symlink_and_existing_destination(tmp_path):
    repo = tmp_path / 'repo'
    repo.mkdir()
    git(repo, 'init', '-q')
    git(repo, 'config', 'user.name', 'Test')
    git(repo, 'config', 'user.email', 'test@example.invalid')
    (repo / 'link').symlink_to('target')
    git(repo, 'add', '.')
    git(repo, 'commit', '-qm', 'link')
    sha = git(repo, 'rev-parse', 'HEAD')
    assert cli('snapshot', '--repo', repo, '--commit', sha, '--output', tmp_path / 'out').returncode != 0
    existing = tmp_path / 'existing'
    existing.mkdir()
    assert cli('snapshot', '--repo', repo, '--commit', sha, '--output', existing).returncode != 0


def test_snapshot_rejects_lfs_gitlink_and_output_inside_repo(tmp_path):
    repo = tmp_path / 'repo'
    repo.mkdir()
    git(repo, 'init', '-q')
    git(repo, 'config', 'user.name', 'Test')
    git(repo, 'config', 'user.email', 'test@example.invalid')
    (repo / 'pointer').write_text('version https://git-lfs.github.com/spec/v1\noid sha256:' + '1' * 64 + '\nsize 1\n')
    git(repo, 'add', '.')
    git(repo, 'commit', '-qm', 'lfs')
    sha = git(repo, 'rev-parse', 'HEAD')
    assert cli('snapshot', '--repo', repo, '--commit', sha, '--output', tmp_path / 'lfs').returncode != 0
    (repo / 'pointer').unlink()
    git(repo, 'rm', 'pointer')
    git(repo, 'update-index', '--add', '--cacheinfo', '160000,' + sha + ',submodule')
    git(repo, 'commit', '-qm', 'gitlink')
    assert cli('snapshot', '--repo', repo, '--commit', git(repo, 'rev-parse', 'HEAD'), '--output', tmp_path / 'gitlink').returncode != 0
    git(repo, 'update-index', '--force-remove', 'submodule')
    (repo / 'file').write_text('x')
    git(repo, 'add', '.')
    git(repo, 'commit', '-qm', 'normal')
    assert cli('snapshot', '--repo', repo, '--commit', git(repo, 'rev-parse', 'HEAD'), '--output', repo / 'output').returncode != 0
    assert not (repo / 'output').exists()


def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


class Case:
    def __init__(self, root):
        self.root = root
        self.path = root / 'manifest.json'
        self.instruction = 'environment/AGENTS.md'
        self.manifest = {
            'schema': 'harbor-skill-experiment.v1',
            'incident_id': 'incident-1',
            'incident_kind': 'captured',
            'incident_source': 'local incident record',
            'repository_commit': 'f' * 40,
            'runtime': {
                'harbor_version': '0.25.0', 'agent': 'codex', 'agent_version': '1.2.3',
                'model': 'openai/gpt-example', 'effort': 'high', 'concurrency': 2,
                'timeout_sec': 20,
            },
            'trials': {'baseline': 5, 'treatment': 5},
            'intervention_paths': [self.instruction],
        }
        self.file('snapshot/file.txt', 'historical source')
        for arm in ('baseline', 'treatment'):
            self.file(f'{arm}/instruction.md', 'Work on the fixture.')
            self.file(f'{arm}/task.toml', '[verifier]\nenvironment_mode = "separate"\n')
            self.file(f'{arm}/environment/Dockerfile', 'FROM scratch\n')
            self.file(f'{arm}/{self.instruction}', arm)
            self.file(f'{arm}/tests/test.sh', '#!/bin/sh\ntrue\n')
        self.manifest['snapshot'] = self.tree('snapshot')
        self.refresh_tasks()
        evidence = self.file('evidence.txt', 'fixture evidence')
        self.provenance = {
            'schema': 'experiment-provenance.v1',
            'incident_id': self.manifest['incident_id'],
            'repository_commit': self.manifest['repository_commit'],
            'inputs': {
                k: {'status': 'recovered', 'explanation': 'present', 'evidence': [evidence]}
                for k in ('original_request', 'source_state', 'instructions', 'runtime',
                          'dependencies', 'external_state')
            },
        }
        self.manifest['provenance'] = self.json('provenance.json', self.provenance)
        self.images = {
            arm: {'agent_image_digest': 'sha256:' + fill * 64,
                  'verifier_image_digest': 'sha256:' + '3' * 64}
            for arm, fill in (('baseline', '1'), ('treatment', '2'))
        }
        self.manifest['design_files'] = [self.file('design.md', 'design')]
        self.manifest['code_files'] = [self.file('reviewed.py', SCRIPT.read_bytes())]
        self.refresh_reviews()
        self.bind_case()

    def file(self, name, data):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data.encode() if isinstance(data, str) else data)
        return {'path': name, 'sha256': sha(p.read_bytes())}

    def json(self, name, data):
        return self.file(name, canonical_bytes(data))

    def tree(self, name):
        root = self.root / name
        records = [
            {'path': p.relative_to(root).as_posix(), 'sha256': sha(p.read_bytes()),
             'executable': bool(p.stat().st_mode & 0o111)}
            for p in sorted(root.rglob('*'), key=lambda p: p.relative_to(root).as_posix())
            if p.is_file()
        ]
        return {'path': name, 'sha256': sha(canonical_bytes(records))}

    def refresh_tasks(self):
        for arm in ('baseline', 'treatment'):
            self.manifest[f'{arm}_task'] = self.tree(arm)

    def refresh_reviews(self):
        self.manifest['reviews'] = []
        for phase in ('design', 'code'):
            records = sorted(self.manifest[f'{phase}_files'], key=lambda ref: ref['path'])
            bundle = sha(canonical_bytes(records))
            for seat in ('first', 'second'):
                details = {'phase': phase, 'reviewer_id': seat, 'verdict': 'APPROVED',
                           'bundle_sha256': bundle}
                output = self.file(f'{phase}-{seat}.txt',
                                   f'Review by {seat}\nVERDICT: APPROVED at DOCUMENTS sha256:{bundle}\n')
                receipt = self.json(f'{phase}-{seat}.json',
                                    {'schema': 'experiment-review.v1', **details, 'output': output})
                self.manifest['reviews'].append({**details, 'receipt': receipt})

    def bind_case(self):
        excluded = {'reviews', 'design_files', 'code_files', 'packaging', 'qualification'}
        self.case_sha256 = sha(canonical_bytes({k: v for k, v in self.manifest.items() if k not in excluded}))
        evidence = {'path': 'evidence.txt', 'sha256': sha((self.root / 'evidence.txt').read_bytes())}
        self.manifest['packaging'] = self.json('packaging.json', {
            'schema': 'experiment-packaging.v1', 'case_sha256': self.case_sha256,
            'reviewer_id': 'coordinator', 'verdict': 'READY', 'evidence': [evidence],
        })
        self.qualification = {
            'schema': 'experiment-qualification.v1', 'case_sha256': self.case_sha256,
            'verdict': 'READY', 'images': self.images,
            'checks': {
                k: {'passed': True, 'evidence': [evidence]}
                for k in ('immutable_inputs', 'hidden_verifier', 'restricted_network',
                          'credential_isolation', 'arm_isolation', 'cleanup_supported')
            },
        }
        self.manifest['qualification'] = self.json('qualification.json', self.qualification)
        self.save()

    def save(self):
        self.json('manifest.json', self.manifest)


@pytest.fixture
def case(tmp_path):
    return Case(tmp_path)


def test_plan_never_launches(case, monkeypatch, capsys):
    def unexpected(*args, **kwargs):
        pytest.fail('plan called a subprocess')

    monkeypatch.setattr(subprocess, 'Popen', unexpected)
    assert adapter.main(['plan', str(case.path)]) == 0
    plan = json.loads(capsys.readouterr().out)
    for arm in ('baseline', 'treatment'):
        argv = plan[f'{arm}_argv']
        assert argv[:2] == ['harbor', 'run']
        assert argv[argv.index('--job-name') + 1] == arm
        assert argv[argv.index('--effort') + 1] == 'high'
        assert argv[argv.index('--n-attempts') + 1] == '5'


def test_reviews_bind_exact_files_and_executing_code(case):
    original = (case.root / 'reviewed.py').read_bytes()
    case.file('reviewed.py', original + b'\n')
    assert cli('plan', case.path).returncode != 0
    case.manifest['code_files'] = [case.file('reviewed.py', b'pass')]
    case.refresh_reviews()
    case.save()
    assert 'executing adapter' in cli('plan', case.path).stderr


@pytest.mark.parametrize('invalid', ['unknown', 'duplicate', 'traversal', 'symlink', 'nonfinite', 'bool_count'])
def test_rejects_unknown_duplicate_and_unsafe_input(case, invalid):
    if invalid == 'unknown':
        case.manifest['unexpected'] = None
    elif invalid == 'traversal':
        case.manifest['snapshot']['path'] = 'snapshot/../snapshot'
    elif invalid == 'symlink':
        (case.root / 'alias').symlink_to('snapshot', target_is_directory=True)
        case.manifest['snapshot']['path'] = 'alias'
    elif invalid == 'nonfinite':
        case.manifest['runtime']['timeout_sec'] = float('inf')
    elif invalid == 'bool_count':
        case.manifest['runtime']['concurrency'] = True
    case.save()
    if invalid == 'duplicate':
        case.path.write_bytes(case.path.read_bytes()[:-1] + b',"schema":"harbor-skill-experiment.v1"}')
    assert cli('plan', case.path).returncode != 0


@pytest.mark.parametrize('change', ['unlisted', 'no_delta', 'build_file', 'mode'])
def test_intervention_is_the_only_task_difference(case, change):
    if change == 'unlisted':
        case.file('treatment/tests/test.sh', 'different verifier')
    elif change == 'no_delta':
        case.file(f'treatment/{case.instruction}', 'baseline')
    elif change == 'build_file':
        case.file('treatment/environment/Dockerfile', 'FROM another\n')
        case.manifest['intervention_paths'].append('environment/Dockerfile')
    else:
        (case.root / 'treatment' / case.instruction).chmod(0o755)
    case.refresh_tasks()
    case.bind_case()
    assert cli('plan', case.path).returncode != 0


@pytest.mark.parametrize('invalid', ['phase', 'terminal', 'same_seat'])
def test_review_receipt_contents_match(case, invalid):
    review = case.manifest['reviews'][1]
    receipt_path = review['receipt']['path']
    receipt = json.loads((case.root / receipt_path).read_bytes())
    if invalid == 'phase':
        receipt['phase'] = 'code'
    elif invalid == 'terminal':
        receipt['output'] = case.file('approval.txt', 'OK')
    else:
        review['reviewer_id'] = receipt['reviewer_id'] = 'first'
    review['receipt'] = case.json(receipt_path, receipt)
    case.save()
    assert cli('plan', case.path).returncode != 0


def test_packaging_and_qualification_are_case_bound(case):
    case.manifest['incident_source'] = 'changed reference'
    case.save()
    assert 'packaging' in cli('plan', case.path).stderr
    case.bind_case()
    case.qualification['checks']['credential_isolation']['evidence'] = []
    case.manifest['qualification'] = case.json('qualification.json', case.qualification)
    case.save()
    assert 'credential_isolation' in cli('plan', case.path).stderr


def test_captured_requires_complete_provenance(case):
    case.provenance['inputs']['runtime']['status'] = 'reconstructed'
    case.manifest['provenance'] = case.json('provenance.json', case.provenance)
    case.bind_case()
    assert 'captured' in cli('plan', case.path).stderr
    case.manifest['incident_kind'] = 'constructed'
    case.bind_case()
    assert cli('plan', case.path).returncode == 0


def test_hash_known_answer_and_modes(tmp_path):
    (tmp_path / 'a.txt').write_bytes(b'hello\n')
    (tmp_path / 'a.txt').chmod(0o755)
    actual = adapter.digest(adapter.canonical(adapter.inventory(tmp_path)))
    assert actual == 'be988123909426a596481ad090976dac10107fc5afd6cef6b794db4cb5a5df96'
    (tmp_path / 'a.txt').chmod(0o644)
    assert adapter.digest(adapter.canonical(adapter.inventory(tmp_path))) != actual


FAKE_HARBOR = r'''
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from uuid import uuid4


def write(path, value):
    path.write_text(json.dumps(value))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checksum(path):
    rows = []
    for entry in path.iterdir():
        kind, value = ('dirhash', checksum(entry)) if entry.is_dir() else ('data', sha(entry))
        rows.append(f'{kind}:{value}\0name:{entry.name}')
    return hashlib.sha256('\0\0'.join(sorted(rows)).encode()).hexdigest()


control = Path(__file__).with_suffix('.json')
settings = json.loads(control.read_text())
if sys.argv[1:] == ['--version']:
    assert 'OPENAI_API_KEY' not in os.environ
    assert 'CODEX_API_KEY' not in os.environ
    print(settings.get('version', '0.25.0'))
    sys.exit(0)
mode = settings.get('mode')
with control.with_suffix('.calls').open('a') as calls:
    calls.write(json.dumps(sys.argv[1:]) + '\n')
print('fake stdout', flush=True)
print('fake stderr', file=sys.stderr, flush=True)
assert 'CODEX_HOME' not in os.environ
assert 'CODEX_SQLITE_HOME' not in os.environ
assert 'GH_TOKEN' not in os.environ
assert os.environ.get('OPENAI_API_KEY') == 'fake-provider-key'
assert 'CODEX_API_KEY' not in os.environ
assert not (Path(os.environ['HOME']) / '.codex').exists()
if mode in ('timeout', 'interrupt'):
    child = subprocess.Popen([sys.executable, '-c',
                              'import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(60)'])
    control.with_suffix('.pid').write_text(str(child.pid))
    if mode == 'interrupt':
        os.kill(os.getppid(), signal.SIGTERM)
    time.sleep(60)
if mode == 'failed':
    sys.exit(23)

args = dict(zip(sys.argv[2::2], sys.argv[3::2]))
task = Path(args['-p'])
jobs = Path(args['--jobs-dir'])
arm = args['--job-name']
job = jobs / arm
job.mkdir(parents=True)
agent = {'name': args['-a'], 'model_name': args['-m'],
         'kwargs': {'version': args['--agent-kwarg'].split('=')[1],
                    'reasoning_effort': args['--effort']}}
n = int(args['--n-attempts'])
job_id = str(uuid4())
job_config = {
    'job_name': arm, 'jobs_dir': str(jobs), 'n_attempts': n,
    'n_concurrent_trials': int(args['--n-concurrent']), 'agents': [agent],
    'tasks': [{'path': str(task)}],
}
write(job / 'config.json', job_config)
results = []
stamp = '2026-11-26T12:00:00Z'
for i in range(n):
    name = f'task__{i}'
    path = job / name
    path.mkdir()
    identifier = str(uuid4()) if mode != 'duplicate' or i == 0 else results[0]['id']
    config = {'task': {'path': str(task)}, 'agent': agent, 'trial_name': name,
              'trials_dir': str(job), 'job_id': job_id}
    write(path / 'config.json', config)
    observed = i == 0 and arm == 'baseline' and mode != 'no_reproduction'
    rewards = {'valid': 1.0, 'exposure_verified': 1, 'incident_failure': int(observed),
               'task_completed': int(not observed and (mode != 'regression' or i != 0)),
               'regression_failed': int(mode == 'regression' and i == 0)}
    if mode == 'invalid' and i == 0:
        rewards['valid'] = 0
    if mode == 'boolean_reward' and i == 0:
        rewards['incident_failure'] = True
    provider, model = args['-m'].split('/', 1)
    result = {
        'id': identifier, 'trial_name': name, 'trial_uri': path.as_uri(),
        'task_name': task.name, 'task_id': {'path': str(task)}, 'task_checksum': checksum(task),
        'config': config, 'verifier_environment_mode': 'separate',
        'agent_info': {'name': 'codex', 'version': agent['kwargs']['version'],
                       'model_info': {'name': model, 'provider': provider}},
        'verifier_result': {'rewards': rewards},
        'exception_info': None, 'started_at': stamp, 'finished_at': stamp,
        'agent_execution': {'started_at': stamp, 'finished_at': stamp}, 'step_results': None,
    }
    verifier = path / 'verifier'
    verifier.mkdir()
    trace = path / 'agent' / 'raw.jsonl'
    trace.parent.mkdir()
    trace.write_text('recorded trajectory')
    evidence = verifier / 'native-read.txt'
    evidence.write_text('verified instruction read')
    exposure = {
        'schema': 'experiment-exposure.v1', 'trial_id': identifier, 'arm': arm,
        'case_sha256': settings['case_sha256'],
        'instructions': [{'path': item, 'sha256': sha(task / item)}
                         for item in settings['intervention_paths']],
        'trajectory': {'path': 'agent/raw.jsonl', 'sha256': sha(trace)},
        'evidence': [{'path': 'verifier/native-read.txt', 'sha256': sha(evidence)}],
        **settings['images'][arm],
    }
    if i == 0:
        changes = {
            'trial': ('trial_id', str(uuid4())),
            'arm': ('arm', 'treatment'),
            'case': ('case_sha256', 'f' * 64),
            'instruction': ('instructions', [{'path': 'environment/AGENTS.md', 'sha256': 'f' * 64}]),
            'image': ('agent_image_digest', settings['images']['treatment']['agent_image_digest']),
            'trajectory': ('trajectory', {'path': 'agent/raw.jsonl', 'sha256': 'f' * 64}),
            'evidence': ('evidence', []),
            'missing_instruction': ('instructions', exposure['instructions'][:-1]),
        }
        if mode in changes:
            k, v = changes[mode]
            exposure[k] = v
        if mode == 'wrong_runtime':
            result['agent_info']['model_info']['name'] = 'unrelated'
        if mode == 'wrong_checksum':
            result['task_checksum'] = 'f' * 64
        if mode == 'wrong_job':
            result['config'] = {**config, 'job_id': str(uuid4())}
        if mode == 'exception':
            result['exception_info'] = {'exception_type': 'SetupError'}
        if mode == 'nested':
            write(verifier / 'result.json', result)
    if mode != 'no_exposure' or i != 0:
        write(verifier / 'exposure.json', exposure)
    if mode != 'missing' or i != 0:
        write(path / 'result.json', result)
    results.append(result)
write(job / 'result.json', {
    'id': job_id, 'finished_at': stamp, 'n_total_trials': n,
    'stats': {'n_retries': 0, 'n_completed_trials': n, 'n_pending_trials': 0,
              'n_running_trials': 0, 'n_cancelled_trials': 0},
})
if mode == 'mutate':
    (task / 'instruction.md').write_text('mutated during invocation')
if mode == 'empty_dir':
    (task / 'unexpected-empty').mkdir()
'''


class FakeHarbor:
    def __init__(self, case, monkeypatch):
        self.case = case
        self.binary = case.root / 'bin' / 'harbor'
        self.binary.parent.mkdir()
        self.binary.write_text(f'#!{sys.executable}\n' + FAKE_HARBOR)
        self.binary.chmod(0o755)
        monkeypatch.setenv('PATH', str(self.binary.parent) + os.pathsep + os.environ['PATH'])
        monkeypatch.setenv('CODEX_HOME', 'private')
        monkeypatch.setenv('CODEX_SQLITE_HOME', 'private')
        monkeypatch.setenv('GH_TOKEN', 'private')
        monkeypatch.setenv('OPENAI_API_KEY', 'fake-provider-key')
        monkeypatch.delenv('CODEX_API_KEY', raising=False)
        monkeypatch.delenv('DOCKER_HOST', raising=False)

    def set_mode(self, mode=None, **kwargs):
        self.binary.with_suffix('.json').write_bytes(canonical_bytes({
            'mode': mode, 'case_sha256': self.case.case_sha256,
            'intervention_paths': self.case.manifest['intervention_paths'], 'images': self.case.images,
            **kwargs,
        }))

    @property
    def calls(self):
        path = self.binary.with_suffix('.calls')
        return path.read_text().splitlines() if path.exists() else []

    def run(self, arm='baseline', name=None, *args):
        out = self.case.root / (name or f'{arm}-run')
        return cli('run', self.case.path, '--arm', arm, '--output', out, *args), out

    def collect(self, run, arm='baseline'):
        out = self.case.root / f'{run.name}-receipt.json'
        result = cli('collect', self.case.path, '--arm', arm, '--run', run, '--output', out)
        assert out.is_file(), result.stderr
        return result, out, json.loads(out.read_bytes())


@pytest.fixture
def harbor(case, monkeypatch):
    fake = FakeHarbor(case, monkeypatch)
    fake.set_mode()
    return fake


def test_baseline_launch_uses_pinned_harbor_argv(harbor, monkeypatch):
    launched, directory = harbor.run()
    assert launched.returncode == 0, launched.stderr
    launch = json.loads((directory / 'launch.json').read_bytes())
    assert launch['argv'] == [
        str(harbor.binary.resolve()), 'run', '-p', str(directory / 'staged' / 'task'),
        '-a', 'codex', '-m', 'openai/gpt-example', '--agent-kwarg', 'version=1.2.3',
        '--effort', 'high', '--jobs-dir', str(directory / 'jobs'), '--job-name', 'baseline',
        '--n-attempts', '5', '--n-concurrent', '2',
    ]
    assert len(harbor.calls) == 1
    assert (directory / 'stdout.log').read_text() == 'fake stdout\n'
    assert (directory / 'stderr.log').read_text() == 'fake stderr\n'
    assert harbor.run()[0].returncode != 0

    # An isolated interpreter and subprocess guard test the same collection entry point.
    def unexpected(*args, **kwargs):
        pytest.fail('collect called a subprocess')

    monkeypatch.setattr(subprocess, 'Popen', unexpected)
    assert adapter.main(['collect', str(harbor.case.path), '--arm', 'baseline',
                         '--run', str(directory), '--output', str(directory.parent / 'collected.json')]) == 0
    receipt = json.loads((directory.parent / 'collected.json').read_bytes())
    assert receipt['status'] == 'REPRODUCED'
    assert receipt['incident_failures'] == 1
    assert receipt['valid_trials'] == receipt['expected_trials'] == 5


def test_treatment_requires_reproduced_matching_baseline(harbor):
    assert harbor.run('treatment')[0].returncode != 0
    assert not harbor.calls
    harbor.set_mode('no_reproduction')
    launched, nonreproduced = harbor.run('baseline', 'nonreproduced')
    assert launched.returncode == 0, launched.stderr
    _, denied, receipt = harbor.collect(nonreproduced)
    assert receipt['status'] == 'NOT_REPRODUCED'
    assert harbor.run('treatment', 'denied', '--baseline', denied)[0].returncode != 0
    receipt['status'] = 'REPRODUCED'
    denied.write_bytes(canonical_bytes(receipt))
    assert harbor.run('treatment', 'forged', '--baseline', denied)[0].returncode != 0
    assert len(harbor.calls) == 1

    harbor.set_mode()
    launched, directory = harbor.run()
    assert launched.returncode == 0, launched.stderr
    _, approved, _ = harbor.collect(directory)
    trace = directory / 'jobs/baseline/task__0/agent/raw.jsonl'
    previous = trace.read_bytes()
    trace.write_bytes(previous + b' altered')
    assert harbor.run('treatment', 'altered', '--baseline', approved)[0].returncode != 0
    trace.write_bytes(previous)
    case = harbor.case
    case.path.write_bytes(case.path.read_bytes() + b'\n')
    assert harbor.run('treatment', 'different-manifest', '--baseline', approved)[0].returncode != 0
    case.save()
    launched, treated = harbor.run('treatment', None, '--baseline', approved)
    assert launched.returncode == 0, launched.stderr
    _, _, result = harbor.collect(treated, 'treatment')
    assert result['status'] == 'OBSERVED_FIXED'
    assert len(harbor.calls) == 3


@pytest.mark.parametrize('mode', ['missing', 'duplicate', 'wrong_runtime', 'wrong_checksum',
                                  'wrong_job', 'invalid', 'exception', 'nested', 'boolean_reward'])
def test_invalid_trials_do_not_reproduce(harbor, mode):
    harbor.set_mode(mode)
    launched, directory = harbor.run()
    assert launched.returncode == 0, launched.stderr
    _, _, report = harbor.collect(directory)
    assert report['status'] == 'INCOMPLETE'
    assert report['expected_trials'] == 5
    assert report['invalid_trials'] >= 1


@pytest.mark.parametrize('mode', ['no_exposure', 'trial', 'arm', 'case', 'instruction',
                                  'image', 'trajectory', 'evidence'])
def test_exposure_requires_trial_arm_instruction_image_and_trajectory_bindings(harbor, mode):
    harbor.set_mode(mode)
    launched, directory = harbor.run()
    assert launched.returncode == 0, launched.stderr
    _, _, report = harbor.collect(directory)
    assert report['status'] == 'INCOMPLETE'
    assert report['invalid_trials'] == 1
    assert report['incident_failures'] == 0


def test_collect_reports_completion_and_regressions(harbor):
    launched, directory = harbor.run()
    assert launched.returncode == 0, launched.stderr
    _, baseline, _ = harbor.collect(directory)
    harbor.set_mode('regression')
    launched, treated = harbor.run('treatment', None, '--baseline', baseline)
    assert launched.returncode == 0, launched.stderr
    _, _, report = harbor.collect(treated, 'treatment')
    assert report['status'] == 'NOT_OBSERVED_FIXED'
    assert report['valid_trials'] == 5
    assert report['task_completions'] == 4
    assert report['regression_failures'] == 1


@pytest.mark.parametrize('mode,status', [('timeout', 'TIMED_OUT'), ('interrupt', 'INTERRUPTED')])
def test_timeout_or_interrupt_preserves_failure_and_cleans_child(harbor, mode, status):
    harbor.case.manifest['runtime']['timeout_sec'] = 2
    harbor.case.bind_case()
    harbor.set_mode(mode)
    result, directory = harbor.run()
    assert result.returncode != 0
    launch = json.loads((directory / 'launch.json').read_bytes())
    assert launch['status'] == status
    assert launch['cleanup'] == 'unverified'
    pid = harbor.binary.with_suffix('.pid').read_text()
    for _ in range(30):
        state = subprocess.run(['ps', '-o', 'stat=', '-p', pid],
                               capture_output=True, text=True).stdout.strip()
        if not state or 'Z' in state:
            break
        time.sleep(0.05)
    assert not state or 'Z' in state
    assert (directory / 'stdout.log').read_text() == 'fake stdout\n'
    _, baseline, report = harbor.collect(directory)
    assert report['status'] == 'INCOMPLETE'
    assert report['missing_trials'] == 5
    assert harbor.run('treatment', None, '--baseline', baseline)[0].returncode != 0
    assert len(harbor.calls) == 1


def test_changed_inputs_and_unsupported_version_invalidate_run(harbor):
    harbor.set_mode(version='0.25.1')
    result, directory = harbor.run('baseline', 'bad-version')
    assert result.returncode != 0
    assert not harbor.calls
    assert json.loads((directory / 'launch.json').read_bytes())['status'] == 'VERSION_MISMATCH'
    harbor.set_mode('mutate')
    result, directory = harbor.run()
    assert result.returncode != 0
    launch = json.loads((directory / 'launch.json').read_bytes())
    assert launch['status'] == 'INPUTS_CHANGED'
    assert launch['staged_before'] != launch['staged_after']
    assert (harbor.case.root / 'baseline' / 'instruction.md').read_text() == 'Work on the fixture.'
    _, _, report = harbor.collect(directory)
    assert report['status'] == 'INCOMPLETE'


def test_harbor_checksum_matches_dirhash_0_5_0(tmp_path):
    # Obtained from the actual dirhash 0.5.0 package with its default SHA-256 protocol.
    (tmp_path / 'environment').mkdir()
    (tmp_path / 'instruction.md').write_bytes(b'fixture\n')
    (tmp_path / 'environment/Dockerfile').write_bytes(b'FROM scratch\n')
    (tmp_path / 'environment/AGENTS.md').write_bytes(b'rule\n')
    assert adapter.harbor_checksum(adapter.inventory(tmp_path)) == (
        '63dd4cda9159e45b275d2e7ef498e5595ad65681f4102a6bb5083fa1fcd57125'
    )


def test_all_declared_markdown_instructions_must_have_exposure(harbor):
    case = harbor.case
    extra = 'environment/pr-lifecycle/review-routing.md'
    case.manifest['intervention_paths'].append(extra)
    case.file(f'baseline/{extra}', 'before routing')
    case.file(f'treatment/{extra}', 'after routing')
    case.refresh_tasks()
    case.bind_case()
    harbor.set_mode('missing_instruction')
    launched, directory = harbor.run()
    assert launched.returncode == 0, launched.stderr
    _, _, report = harbor.collect(directory)
    assert report['status'] == 'INCOMPLETE'
    assert report['valid_trials'] == 4


def test_collect_rejects_post_launch_trial_edit(harbor):
    launched, directory = harbor.run()
    assert launched.returncode == 0, launched.stderr
    trial = directory / 'jobs/baseline/task__0/result.json'
    trial.write_bytes(trial.read_bytes() + b'\n')
    _, _, report = harbor.collect(directory)
    assert report['status'] == 'INCOMPLETE'
    assert report['observed_trials'] == 5
    assert any('output inventory' in reason for reason in report['run_errors'])


def test_added_empty_staging_directory_invalidates_launch(harbor):
    harbor.set_mode('empty_dir')
    launched, directory = harbor.run()
    assert launched.returncode != 0
    assert json.loads((directory / 'launch.json').read_bytes())['status'] == 'INPUTS_CHANGED'
