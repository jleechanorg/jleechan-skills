import hashlib
import importlib.util
import json
import subprocess
import sys
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
