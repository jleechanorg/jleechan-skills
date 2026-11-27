import hashlib
import importlib.util
import json
import asyncio
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest


def test_access_argv_preserves_typed_harbor_options(tmp_path):
    run_hash = '2' * 64
    egress_image, agent_image = ('sha256:' + char * 64 for char in 'ab')
    experiment = SimpleNamespace(runtime={'auth_mode': adapter.ACCESS_MODE, 'agent': 'codex',
        'agent_version': '0.172.0', 'model': 'gpt-fixture', 'effort': 'medium', 'concurrency': 1},
        case_sha256='3' * 64, trials={'baseline': 2}, egress_image_id=egress_image,
        images={'baseline': {'agent_image_digest': agent_image}}, verifier_env=lambda *_: {})
    argv = adapter.Experiment.argv(experiment, 'baseline', tmp_path, run_sha256=run_hash)
    agent_kwargs = dict(argv[index + 1].split('=', 1) for index, arg in enumerate(argv) if arg == '--agent-kwarg')
    assert agent_kwargs == {'version': '0.172.0', 'config': '{"cli_auth_credentials_store":"file"}'}
    kwargs = dict(argv[index + 1].split('=', 1) for index, arg in enumerate(argv) if arg == '--plugin-kwarg')
    assert {key: json.loads(value) for key, value in kwargs.items()} == {
        'run_sha256': run_hash, 'egress_image': egress_image, 'agent_image': agent_image,
        'scope': adapter.staged_name(experiment, tmp_path) + '__',
    }


def test_access_job_refuses_unreadable_subtree(monkeypatch, tmp_path):
    hidden = tmp_path / 'hidden'
    hidden.mkdir()
    (hidden / 'trace').write_text('fixture')
    original = Path.iterdir

    def unreadable(path):
        if path == hidden:
            raise PermissionError('fixture permission error')
        return original(path)

    monkeypatch.setattr(Path, 'iterdir', unreadable)
    assert adapter.access_job_hash(tmp_path) is None


def test_access_review_binds_egress_plugin_bytes(tmp_path):
    code = []
    for script in ('harbor_experiment.py', 'harbor_codex_access.py', 'harbor_codex_completion.py'):
        data = Path(adapter.__file__).with_name(script).read_bytes()
        (tmp_path / script).write_bytes(data)
        code.append({'path': script, 'sha256': sha(data)})
    experiment = SimpleNamespace(root=tmp_path, runtime={'auth_mode': adapter.ACCESS_MODE})
    manifest = {'design_files': code[:1], 'code_files': code, 'reviews': []}
    with pytest.raises(ValueError, match='reviewed code bundle must contain the executing adapter bytes'):
        adapter.Experiment.check_reviews(experiment, manifest, 'fixture-coordinator')


@pytest.mark.parametrize('changed', ['model', 'effort', 'timeout_sec', 'trials', None])
def test_access_launch_matches_frozen_campaign_policy(changed, tmp_path):
    runtime = {'model': 'example-model', 'effort': 'low', 'timeout_sec': 777}
    policy = tmp_path / 'policy.json'
    adapter.write_json(policy, {'schema': 'experiment-launch-policy.v1', 'cases': {
        'fixture': {'arm': 'baseline', 'runtime': runtime, 'trials': 5}}})
    requested = {**runtime}
    if changed in runtime:
        requested[changed] = 778 if changed == 'timeout_sec' else 'other'
    reference = {'path': policy.name, 'sha256': sha(policy.read_bytes())}
    if changed is None:
        adapter.check_launch_policy(tmp_path, reference, 'fixture', requested, 5)
    else:
        with pytest.raises(ValueError, match='requested launch does not match frozen campaign policy'):
            adapter.check_launch_policy(tmp_path, reference, 'fixture', requested, 6 if changed == 'trials' else 5)


@pytest.mark.parametrize('delay,budget,expected', [(0.12, 5, 'SUCCEEDED'), (5, 0.15, 'TIMED_OUT')])
def test_access_capture_waits_for_detached_output_writers(tmp_path, delay, budget, expected):
    child = f'import sys,time; time.sleep({delay}); print("late"); print("late error", file=sys.stderr)'
    parent = f'import subprocess,sys; subprocess.Popen([sys.executable,"-c",{child!r}],start_new_session=True)'
    with (tmp_path / 'stdout').open('w+b') as stdout, (tmp_path / 'stderr').open('w+b') as stderr:
        status, _ = adapter.invoke([sys.executable, '-c', parent], cwd=tmp_path, env=os.environ,
                                   stdout=stdout, stderr=stderr, timeout=budget, sealed=True)
    assert status == expected
    assert (tmp_path / 'stdout').read_bytes() == (b'late\n' if expected == 'SUCCEEDED' else b'')
    assert (tmp_path / 'stderr').read_bytes() == (b'late error\n' if expected == 'SUCCEEDED' else b'')


@pytest.mark.parametrize('interrupt', [False, True])
def test_access_capture_waits_for_detached_file_writer(tmp_path, interrupt):
    import signal
    import threading

    child = 'from pathlib import Path; import time; time.sleep(.3); Path("late").write_bytes(b"sealed")'
    parent = (f'import subprocess,sys; subprocess.Popen([sys.executable,"-c",{child!r}],start_new_session=True,'
              'stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)')
    timer = threading.Timer(.2, os.kill, (os.getpid(), signal.SIGINT)) if interrupt else None
    try:
        if timer:
            timer.start()
        with (tmp_path / 'stdout').open('w+b') as stdout, (tmp_path / 'stderr').open('w+b') as stderr:
            status, _ = adapter.invoke([sys.executable, '-c', parent], cwd=tmp_path, env=os.environ,
                                       stdout=stdout, stderr=stderr, timeout=5, sealed=True)
    finally:
        if timer:
            timer.cancel()
            timer.join()
    assert status == ('INTERRUPTED' if interrupt else 'SUCCEEDED')
    if interrupt:
        assert not (tmp_path / 'late').exists()
    else:
        assert (tmp_path / 'late').read_bytes() == b'sealed'


def test_capture_does_not_reap_a_collector_subprocess(tmp_path):
    ready, done = threading.Event(), threading.Event()

    def observe():
        with subprocess.Popen([sys.executable, '-c', 'import sys; sys.stdin.read()'], stdin=subprocess.PIPE) as process:
            ready.set()
            done.wait(timeout=8)
            process.stdin.close()

    collector = threading.Thread(target=observe)
    collector.start()
    try:
        assert ready.wait(timeout=2)
        with (tmp_path / 'out').open('wb') as stdout, (tmp_path / 'err').open('wb') as stderr:
            result, _ = adapter.invoke([sys.executable, '-c', 'print("done")'], cwd=tmp_path, env=os.environ,
                                       stdout=stdout, stderr=stderr, timeout=1, sealed=True)
        assert result == 'SUCCEEDED' and collector.is_alive()
    finally:
        done.set()
        collector.join(timeout=9)


def test_listener_remains_live_through_capture_and_stops_before_final_seal(tmp_path):
    stop = threading.Event()
    listener = threading.Thread(target=stop.wait, daemon=True)
    listener.start()
    try:
        with (tmp_path / 'stdout').open('w+b') as stdout, (tmp_path / 'stderr').open('w+b') as stderr:
            status, code = adapter.invoke([sys.executable, '-c', 'print("capture closed")'], cwd=tmp_path,
                                          env=os.environ, stdout=stdout, stderr=stderr, timeout=3,
                                          sealed=True)
        assert listener.is_alive()
        assert (tmp_path / 'stdout').read_text() == 'capture closed\n'
    finally:
        stop.set()
        listener.join(timeout=1)
    assert (status, code) == ('SUCCEEDED', 0)


def test_reviewed_helper_executes_approved_bytes_not_preloaded_module(tmp_path, monkeypatch):
    import py_compile

    name = 'harbor_codex_review_fixture'
    source = tmp_path / f'{name}.py'
    source.write_text('marker = "unreviewed"\n')
    py_compile.compile(str(source), doraise=True, invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH)
    monkeypatch.syspath_prepend(str(tmp_path))
    approved = b'marker = "approved"\n'
    source.write_bytes(approved)
    imported = importlib.import_module(name)
    assert imported.marker == 'unreviewed'
    monkeypatch.delitem(sys.modules, name)
    checked = adapter.checked_script_sources([source], {sha(approved)})
    source.write_text('raise RuntimeError("changed after inspection")\n')
    adapter.load_reviewed_helpers(checked)
    assert importlib.import_module(name).marker == 'approved'


@pytest.mark.parametrize('status', ['SUCCEEDED', 'INTERRUPTED', 'TIMED_OUT'])
def test_writer_cleanup_boundary_does_not_depend_on_listener_exit(tmp_path, monkeypatch, status):
    drained = []

    def confirm(_, **_kwargs):
        drained.append('writers drained')
        return True

    original = adapter.subprocess.Popen
    monkeypatch.setattr(adapter, 'descendants_drained', confirm)
    if status == 'INTERRUPTED':
        class WaitInterrupted:
            def __init__(self, *args, **kwargs):
                self.process = original(*args, **kwargs)
                self.first = True

            def __getattr__(self, name):
                return getattr(self.process, name)

            def wait(self, *args, **kwargs):
                if self.first:
                    self.first = False
                    raise KeyboardInterrupt
                return self.process.wait(*args, **kwargs)

        monkeypatch.setattr(adapter.subprocess, 'Popen', WaitInterrupted)
    body = 'import time; time.sleep(4)' if status == 'TIMED_OUT' else 'print("done")'
    with (tmp_path / 'out').open('w+b') as stdout, (tmp_path / 'err').open('w+b') as stderr:
        result, _ = adapter.invoke([sys.executable, '-c', body], cwd=tmp_path, env=os.environ,
                                   stdout=stdout, stderr=stderr, timeout=0.15 if status == 'TIMED_OUT' else 3,
                                   sealed=True)
    assert result == status
    assert drained == ['writers drained']


def test_docker_barrier_selects_only_its_own_ordered_events():
    def event(identity, action):
        return {'Type': 'volume', 'Action': action, 'Actor': {'ID': identity, 'Attributes': {'driver': 'local'}}}

    first = event('start', 'destroy')
    last = event('stop', 'destroy')
    late = event('writer', 'destroy')
    assert adapter.docker_fenced_events([first, late, last], 'start', 'stop') == [late]
    assert adapter.docker_fenced_events([first, late], 'start', 'stop') is None
    assert adapter.docker_fenced_events([last, late, first], 'start', 'stop') is None
    assert adapter.docker_fenced_events([first, first, late, last], 'start', 'stop') is None


def test_external_semantic_verdict_binds_detector_and_native_evidence(tmp_path):
    trial_id = str(uuid4())
    trace = tmp_path / 'trace.jsonl'
    trace.write_bytes(b'{}\n{}\n{}\n')
    detector = 'a' * 64
    observation = {'path': 'trace.jsonl', 'sha256': sha(trace.read_bytes())}
    row = {'trial_id': trial_id, 'trajectory_sha256': observation['sha256'],
           'exposure': {'result_sha256': 'b' * 64}}
    record = {'trial_id': trial_id, 'result_sha256': 'b' * 64, 'trajectory_sha256': observation['sha256'],
              'detector_sha256': detector, 'verdict': 'VALID', 'evidence_lines': [1, 3],
              'metrics': {'incident_failure': 1, 'task_completed': 0, 'regression_failed': 1}}
    assert adapter.bound_semantic_verdict(record, row, detector, trace)['incident_failure'] == 1
    with pytest.raises(ValueError, match='required fixture evidence was not cited'):
        adapter.bound_semantic_verdict(record, row, detector, trace, fixture_required=True)
    fixture = tmp_path / 'fixture-events.tsv'
    fixture.write_text('read\tstatus\n')
    cited = {**record, 'fixture_evidence': {'sha256': sha(fixture.read_bytes()), 'lines': [1]}}
    with pytest.raises(ValueError, match='no released fixture event log'):
        adapter.bound_semantic_verdict(cited, row, detector, trace, fixture_required=True)
    assert adapter.bound_semantic_verdict(cited, row, detector, trace, fixture_log=fixture)['incident_failure'] == 1
    fixture.write_bytes(b'')
    observed_empty = {**record, 'fixture_evidence': {'sha256': sha(b''), 'lines': []}}
    assert adapter.bound_semantic_verdict(observed_empty, row, detector, trace,
                                          fixture_log=fixture, fixture_required=True)['incident_failure'] == 1
    with pytest.raises(ValueError, match='fixture evidence does not match'):
        adapter.bound_semantic_verdict({**cited, 'fixture_evidence': {'sha256': sha(b''), 'lines': [1]}},
                                       row, detector, trace, fixture_log=fixture, fixture_required=True)
    with pytest.raises(ValueError, match='no released fixture event log'):
        adapter.bound_semantic_verdict(observed_empty, row, detector, trace, fixture_required=True)
    fixture.write_text('read\tother\n')
    with pytest.raises(ValueError, match='fixture evidence does not match'):
        adapter.bound_semantic_verdict(cited, row, detector, trace, fixture_log=fixture)
    for key, value in [('trial_id', str(uuid4())), ('result_sha256', 'c' * 64), ('trajectory_sha256', 'd' * 64),
                       ('detector_sha256', 'f' * 64), ('verdict', 'INVALID'), ('evidence_lines', [4]),
                       ('metrics', {'incident_failure': True, 'task_completed': 0, 'regression_failed': 1})]:
        with pytest.raises(ValueError):
            adapter.bound_semantic_verdict({**record, key: value}, row, detector, trace)


@pytest.mark.parametrize('fault', ['', 'image', 'namespace', 'unhealthy', 'duplicate', 'host-network', 'public', 'broad', 'route'])
def test_harbor_agent_start_checks_actual_sidecar_before_progression(tmp_path, monkeypatch, fault):
    import harbor_codex_egress as egress

    main, sidecar = 'a' * 64, 'b' * 64
    main_image, sidecar_image = 'sha256:' + 'c' * 64, 'sha256:' + 'd' * 64
    trial = 'codex-' + 'e' * 24 + '__Suffix'
    project = trial.lower() + '__env'
    (tmp_path / trial).mkdir()
    calls = []
    allow = False

    def query(*args):
        nonlocal allow
        calls.append(args)
        if args[0] == 'ps':
            assert f'label=com.docker.compose.project={project}' in args
            return [main, sidecar, 'f' * 64] if fault == 'duplicate' else [main, sidecar]
        if args[:3] == ('exec', sidecar, 'network-policy'):
            if args[3] == 'allow':
                assert args[4:] == ('chatgpt.com',)
                allow = True
                return []
            if fault == 'public':
                return ['mode: allow-all (transparent proxy disabled)']
            return [*egress.POLICY_HEADER, *(['1 chatgpt.com', '2 unexpected.test'] if fault == 'broad' and allow else
                    ['1 chatgpt.com'] if allow else ['(empty: deny all controlled TCP egress)'])]
        if args[-1] == '--harbor-check-preupload-route':
            assert allow and not (tmp_path / trial / egress.RECEIPT).exists()
            if fault == 'route':
                raise ValueError('credential-free effective route failed')
            return []
        return [json.dumps(row) for row in [
            [main, main_image, True, f'container:{sidecar}' if fault != 'namespace' else 'bridge', 'main', None, []],
            [sidecar, sidecar_image if fault != 'image' else main_image, True,
             'host' if fault == 'host-network' else project + '_default',
             egress.SIDECAR, 'unhealthy' if fault == 'unhealthy' else 'healthy', []],
        ]]

    class Job:
        def on_agent_started(self, hook):
            self.before_agent = hook

    monkeypatch.setattr(egress, 'docker_lines', query)
    plugin = egress.BindInferenceSidecar(egress_image=sidecar_image, agent_image=main_image,
                                        scope=trial.split('__', 1)[0] + '__', run_sha256='9' * 64)
    job = Job()
    asyncio.run(plugin.on_job_start(job))
    event = SimpleNamespace(trial_name=trial, result=SimpleNamespace(id=uuid4()), config=SimpleNamespace(trials_dir=tmp_path,
                            agent=SimpleNamespace(extra_allowed_hosts=['chatgpt.com'])))
    recorded = tmp_path / trial / egress.RECEIPT
    if fault:
        with pytest.raises(ValueError):
            asyncio.run(job.before_agent(event))
        assert not recorded.exists()
    else:
        asyncio.run(job.before_agent(event))
        assert json.loads(recorded.read_bytes()) == {'project': project, 'main': main, 'sidecar': sidecar,
                                                     'allowed_host': 'chatgpt.com'}
        assert sum(command[-1] == '--harbor-check-preupload-route' for command in calls) == 1
    assert calls


def test_access_job_freeze_bounds_bytes_and_separates_observed_count(tmp_path):
    from harbor_codex_access import MAX_ARTIFACT_BYTES

    job = tmp_path / 'jobs' / 'baseline'
    trial = job / 'trial'
    trial.mkdir(parents=True)
    (trial / 'result.json').write_text('{}')
    assert adapter.access_job_hash(job)
    with (trial / 'oversize').open('wb') as stream:
        stream.truncate(MAX_ARTIFACT_BYTES + 1)
    assert adapter.access_job_hash(job) is None
    assert adapter.sealed_trial_count(tmp_path, 'baseline', 5) == 1
    (trial / 'result.json').rename(trial / 'real.json')
    (trial / 'result.json').symlink_to('real.json')
    assert adapter.sealed_trial_count(tmp_path, 'baseline', 5) is None


def test_access_inventory_does_not_apply_unisolated_job_budget_to_independent_trials(tmp_path):
    for index in range(5):
        trial = tmp_path / f'trial-{index}'
        trial.mkdir()
        for child in range(1650):
            (trial / str(child)).mkdir()
    assert adapter.access_job_hash(tmp_path) is None
    _, withheld = adapter.access_job_inventory(tmp_path, isolate_trials=True)
    assert withheld == set()


def test_access_capture_overflow_stops_writer_without_claiming_it_is_unsealed(monkeypatch, tmp_path):
    import harbor_codex_access

    monkeypatch.setattr(harbor_codex_access, 'MAX_ARTIFACT_BYTES', 20)
    with (tmp_path / 'stdout').open('w+b') as stdout, (tmp_path / 'stderr').open('w+b') as stderr:
        status, _ = adapter.invoke([sys.executable, '-c', 'print("x" * 1000)'], cwd=tmp_path, env=os.environ,
                                   stdout=stdout, stderr=stderr, timeout=5, sealed=True)
    assert status == 'CAPTURE_INVALID'
    assert (tmp_path / 'stdout').stat().st_size <= 20


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


def test_selected_snapshot_accounts_for_committed_tree(tmp_path):
    repo = tmp_path / 'repo'
    repo.mkdir()
    git(repo, 'init', '-q')
    git(repo, 'config', 'user.name', 'Test')
    git(repo, 'config', 'user.email', 'test@example.invalid')
    (repo / 'affected.py').write_text('pinned source')
    (repo / 'irrelevant').symlink_to('/outside-is-not-read')
    git(repo, 'add', '.')
    git(repo, 'commit', '-qm', 'source')
    commit = git(repo, 'rev-parse', 'HEAD')
    tree = git(repo, 'rev-parse', 'HEAD^{tree}')
    blob = git(repo, 'rev-parse', 'HEAD:affected.py')
    policy = tmp_path / 'selection.json'
    selected = {'tree': tree, 'include': ['affected.py'],
                'exclude': [{'path': 'irrelevant', 'reason': 'unrelated to this diagnostic'}]}
    policy.write_text(json.dumps(selected))
    (repo / 'affected.py').write_text('dirty bytes')
    out = tmp_path / 'selected'
    result = cli('snapshot', '--repo', repo, '--commit', commit, '--output', out,
                 '--selection', policy)
    assert result.returncode == 0, result.stderr
    assert (out / 'affected.py').read_text() == 'pinned source'
    assert not (out / 'irrelevant').is_symlink()
    receipt = json.loads((tmp_path / 'selected.receipt.json').read_text())
    assert receipt['schema'] == 'experiment-selected-snapshot.v2'
    assert receipt['repository_tree'] == tree
    assert receipt['selected'][0]['git_oid'] == blob
    assert receipt['selected'][0]['git_mode'] == '100644'
    assert receipt['excluded'] == selected['exclude']
    receipt_path = tmp_path / 'selected.receipt.json'

    def verify(pinned):
        receipt_path.write_text(json.dumps(pinned))
        return adapter.verify_snapshot(tmp_path, {'incident_kind': 'constructed', 'repository_commit': commit,
            'snapshot': {'path': 'selected', 'sha256': receipt['sha256'],
                         'selection_receipt': {'path': receipt_path.name, 'sha256': sha(receipt_path.read_bytes())}}})

    assert verify(receipt) == out
    for key, value in [('repository_tree', 'f' * 40), ('excluded', []), ('catalog', receipt['catalog'][:1])]:
        with pytest.raises(ValueError):
            verify({**receipt, key: value})
    for invalid in ({**selected, 'exclude': []}, {**selected, 'tree': '0' * 40},
                    {**selected, 'include': ['affected.py', 'irrelevant']}):
        policy.write_text(json.dumps(invalid))
        fail = cli('snapshot', '--repo', repo, '--commit', commit, '--output', tmp_path / 'fail',
                   '--selection', policy)
        assert fail.returncode != 0 and not (tmp_path / 'fail').exists()


def test_selected_snapshot_rejects_committed_lfs_pointer_at_consumption(tmp_path):
    repo = tmp_path / 'repo'
    repo.mkdir()
    git(repo, 'init', '-q')
    git(repo, 'config', 'user.name', 'Test')
    git(repo, 'config', 'user.email', 'test@example.invalid')
    pointer = f'version https://git-lfs.github.com/spec/v1\noid sha256:{"a" * 64}\nsize 123\n'
    (repo / 'asset').write_text(pointer)
    git(repo, 'add', 'asset')
    git(repo, 'commit', '-qm', 'pointer')
    commit = git(repo, 'rev-parse', 'HEAD')
    tree = git(repo, 'rev-parse', 'HEAD^{tree}')
    selected_path = tmp_path / 'selected'
    selected_path.mkdir()
    (selected_path / 'asset').write_text(pointer)
    inventory = adapter.inventory(selected_path)
    checksum = sha(canonical_bytes(inventory))
    selected = [{'path': 'asset', 'git_mode': '100644', 'git_oid': git(repo, 'rev-parse', 'HEAD:asset')}]
    receipt = tmp_path / 'receipt.json'
    receipt.write_text(json.dumps({'schema': 'experiment-selected-snapshot.v2', 'inventory': inventory,
                          'sha256': checksum, 'repository_commit': commit, 'repository_tree': tree,
                          'selected': selected, 'catalog': selected, 'excluded': [],
                          'commit_object': adapter.git(repo, 'cat-file', 'commit', commit).hex()}))
    with pytest.raises(ValueError, match='LFS pointers'):
        adapter.verify_snapshot(tmp_path, {'incident_kind': 'constructed', 'repository_commit': commit,
            'snapshot': {'path': 'selected', 'sha256': checksum,
                         'selection_receipt': {'path': receipt.name, 'sha256': sha(receipt.read_bytes())}}})


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
        assert 'HARBOR_EXPERIMENT_RUN_SHA256=<RUN_SHA256>' in argv


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


@pytest.mark.parametrize('invalid', ['phase', 'terminal', 'same_seat', 'same_output'])
def test_review_receipt_contents_match(case, invalid):
    review = case.manifest['reviews'][1]
    receipt_path = review['receipt']['path']
    receipt = json.loads((case.root / receipt_path).read_bytes())
    if invalid == 'phase':
        receipt['phase'] = 'code'
    elif invalid == 'terminal':
        receipt['output'] = case.file('approval.txt', 'OK')
    elif invalid == 'same_output':
        first = json.loads((case.root / case.manifest['reviews'][0]['receipt']['path']).read_bytes())
        receipt['output'] = case.file('duplicate.txt', (case.root / first['output']['path']).read_bytes())
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

pairs = list(zip(sys.argv[2::2], sys.argv[3::2]))
args = dict(pairs)
verifier_env = dict(value.split('=', 1) for key, value in pairs if key == '--verifier-env')
task = Path(args['-p'])
jobs = Path(args['--jobs-dir'])
arm = args['--job-name']
assert verifier_env['HARBOR_EXPERIMENT_ARM'] == arm
assert verifier_env['HARBOR_EXPERIMENT_CASE_SHA256'] == settings['case_sha256']
run_sha256 = verifier_env['HARBOR_EXPERIMENT_RUN_SHA256']
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
    'tasks': [{'path': str(task)}], 'verifier': {'env': verifier_env},
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
              'trials_dir': str(job), 'job_id': job_id, 'verifier': {'env': verifier_env}}
    if mode == 'wrong_verifier_env' and i == 0:
        config['verifier'] = {'env': {**verifier_env, 'HARBOR_EXPERIMENT_ARM': 'unrelated'}}
    write(path / 'config.json', config)
    log = 'Host Harbor trial log\n'
    if mode == 'cleanup_warning' and i == 0:
        log += 'WARNING Docker compose down failed: fake cleanup problem\n'
    (path / 'trial.log').write_text(log)
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
    trace.write_text(f'recorded native trajectory {identifier}')
    if mode == 'cross_arm_trajectory' and i == 0:
        trace.write_bytes(Path(settings['baseline_trajectory']).read_bytes())
    evidence = verifier / 'native-read.txt'
    evidence.write_text('verified instruction read')
    exposure = {
        'schema': 'experiment-exposure-observation.v1',
        'arm': verifier_env['HARBOR_EXPERIMENT_ARM'],
        'case_sha256': verifier_env['HARBOR_EXPERIMENT_CASE_SHA256'],
        'run_sha256': run_sha256,
        'instructions': [{'path': item, 'sha256': sha(task / item)}
                         for item in settings['intervention_paths']],
        'trajectory': {'path': 'agent/raw.jsonl', 'sha256': sha(trace)},
        'evidence': [{'path': 'verifier/native-read.txt', 'sha256': sha(evidence)}],
    }
    if i == 0:
        changes = {
            'arm': ('arm', 'treatment'),
            'case': ('case_sha256', 'f' * 64),
            'instruction': ('instructions', [{'path': 'environment/AGENTS.md', 'sha256': 'f' * 64}]),
            'run': ('run_sha256', 'f' * 64),
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
    observation = verifier / 'exposure-observation.json'
    if mode != 'no_exposure' or i != 0:
        write(observation, exposure)
    if mode == 'copied_observation' and i == 1:
        previous = job / 'task__0'
        observation.write_bytes((previous / 'verifier/exposure-observation.json').read_bytes())
        trace.write_bytes((previous / 'agent/raw.jsonl').read_bytes())
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
            'intervention_paths': self.case.manifest['intervention_paths'],
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
        '--verifier-env', f'HARBOR_EXPERIMENT_CASE_SHA256={harbor.case.case_sha256}',
        '--verifier-env', 'HARBOR_EXPERIMENT_ARM=baseline',
        '--verifier-env', f'HARBOR_EXPERIMENT_RUN_SHA256={launch["run_sha256"]}',
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
                                  'wrong_job', 'invalid', 'exception', 'nested', 'boolean_reward', 'wrong_verifier_env'])
def test_invalid_trials_do_not_reproduce(harbor, mode):
    harbor.set_mode(mode)
    launched, directory = harbor.run()
    assert launched.returncode == 0, launched.stderr
    _, _, report = harbor.collect(directory)
    assert report['status'] == 'INCOMPLETE'
    assert report['expected_trials'] == 5
    assert report['missing_trials'] + report['invalid_trials'] >= 1
    assert report['missing_trials'] + report['invalid_trials'] + report['valid_trials'] == 5


@pytest.mark.parametrize('mode', ['no_exposure', 'arm', 'case', 'run', 'instruction',
                                  'trajectory', 'evidence'])
def test_exposure_requires_arm_case_run_instruction_and_trajectory_bindings(harbor, mode):
    harbor.set_mode(mode)
    launched, directory = harbor.run()
    assert launched.returncode == 0, launched.stderr
    _, _, report = harbor.collect(directory)
    assert report['status'] == 'INCOMPLETE'
    assert report['invalid_trials'] == 1
    assert report['incident_failures'] == 0


def test_access_failure_receipt_collects_as_incomplete(tmp_path):
    incident = SimpleNamespace(runtime={'auth_mode': adapter.ACCESS_MODE}, trials={'baseline': 5},
                               manifest_sha256='a' * 64, case_sha256='b' * 64,
                               incident_id='case', incident_kind='constructed')
    output = tmp_path / 'withheld'
    failure = adapter.emit_access_failure(incident, 'baseline', output, 'UNSEALED', None, 'harbor-codex-a234567_')
    assert failure['private_recovery_id'] == 'harbor-codex-a234567_'
    report, protected = adapter.assess(incident, 'baseline', output)
    assert protected == [output]
    assert (report['status'], report['valid_trials'], report['incident_failures']) == ('INCOMPLETE', 0, 0)
    assert report['run_errors'] == ['UNSEALED']
    assert report['observed_trials'] is report['missing_trials'] is report['withheld_trials'] is None
    with pytest.raises(ValueError, match='outside retained'):
        adapter.require_outside_retained_runs(output / 'replacement')


@pytest.mark.parametrize('private_destination', [False, True])
def test_access_failure_does_not_claim_zero_after_launch_or_publish_private_path(tmp_path, monkeypatch, private_destination):
    import harbor_codex_access

    incident = SimpleNamespace(runtime={'auth_mode': adapter.ACCESS_MODE, 'timeout_sec': 900, 'concurrency': 1},
                               trials={'baseline': 5}, manifest_sha256='a' * 64, case_sha256='b' * 64,
                               incident_id='case', incident_kind='constructed')
    reference = tmp_path / 'reference'
    reference.write_text('synthetic-account-reference\n')
    reference.chmod(0o600)
    auth = tmp_path / 'fake-auth'
    auth.write_text('{}')
    output = tmp_path / ('synthetic-account-reference' if private_destination else 'safe-run')
    holder = tmp_path / 'harbor-codex-a234567_'
    holder.mkdir()
    incident.snapshot = tmp_path / 'frozen'
    incident.tasks = {}
    if private_destination:
        output.mkdir()
    monkeypatch.setattr(adapter, 'reserve_access_holder', lambda _: holder)
    monkeypatch.setattr(harbor_codex_access, 'prepare_derivative', lambda *_: (b'{}', ('fake-access-token',)))
    monkeypatch.setattr(harbor_codex_access, 'read_account_reference', lambda *_: 'synthetic-account-reference')
    monkeypatch.setattr(harbor_codex_access, 'derivative_not_after', lambda *_: float('inf'))

    def fail_after_launch(*_args, **_kwargs):
        assert not private_destination
        raise ValueError('seal could not be verified')

    monkeypatch.setattr(adapter, 'run_harbor', fail_after_launch)
    with reference.open('rb') as fd:
        result = adapter.run_access(incident, 'baseline', output, auth, fd.fileno())
    if private_destination:
        assert result == {'status': 'ACCESS_OR_RELEASE_REJECTED', 'run_dir': None}
        assert list(output.iterdir()) == []
    else:
        assert result['status'] == 'UNSEALED'
        assert result['private_recovery_id'] == holder.name
        assert result['withheld_trials'] is None
        assert json.loads((output / 'launch.json').read_bytes())['withheld_trials'] is None
    assert not (holder / 'secret').exists()


def test_dead_launcher_leaves_owner_private_reconcilable_holder(tmp_path, monkeypatch):
    case_sha256 = 'b' * 64
    monkeypatch.setattr(adapter, 'ACCESS_PRIVATE_ROOT', tmp_path)
    script = ('from pathlib import Path; import os, sys; import harbor_experiment as adapter; '
              'adapter.ACCESS_PRIVATE_ROOT = Path(sys.argv[1]); '
              'holder = adapter.reserve_access_holder(sys.argv[2]); '
              'with_path = os.open(holder / "secret", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600); '
              'os.write(with_path, b"synthetic"); os._exit(137)')
    env = dict(os.environ, PYTHONPATH=str(Path(adapter.__file__).parent))
    died = subprocess.run([sys.executable, '-c', script, str(tmp_path), case_sha256], env=env, check=False)
    assert died.returncode == 137
    holder = adapter.access_holder(case_sha256)
    assert holder.stat().st_mode & 0o777 == 0o700
    assert (holder / 'secret').stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        adapter.reserve_access_holder(case_sha256)
    assert adapter.reserve_access_holder('c' * 64) != holder
    assert (holder / 'secret').read_bytes() == b'synthetic'


def test_unsealed_access_process_does_not_collect_partial_output(tmp_path):
    script = ('import subprocess, sys; subprocess.Popen([sys.executable, "-c", '
              '"import time; time.sleep(10); print(123)"])')
    with (tmp_path / 'stdout.log').open('wb') as stdout, (tmp_path / 'stderr.log').open('wb') as stderr:
        status, _ = adapter.invoke([sys.executable, '-c', script], cwd=tmp_path, env={},
                                   stdout=stdout, stderr=stderr, timeout=0.3, sealed=True)
    assert status in {'TIMED_OUT', 'UNSEALED'}
    assert not (tmp_path / 'stdout.log').read_bytes()


def test_access_cleanup_failure_never_publishes_scoreable_release(tmp_path, monkeypatch):
    import harbor_codex_access

    incident = SimpleNamespace(runtime={'auth_mode': adapter.ACCESS_MODE, 'timeout_sec': 900, 'concurrency': 1},
                               trials={'baseline': 5}, manifest_sha256='a' * 64, case_sha256='b' * 64,
                               snapshot=tmp_path / 'snapshot', tasks={})
    reference = tmp_path / 'reference'
    reference.write_text('synthetic-account-reference\n')
    reference.chmod(0o600)
    auth = tmp_path / 'fake-auth'
    auth.write_text('{}')
    output, holder, stage = (tmp_path / name for name in ('output', 'harbor-codex-a234567_', 'stage'))
    for directory in (holder, stage):
        directory.mkdir()
    monkeypatch.setattr(adapter, 'reserve_access_holder', lambda _: holder)
    monkeypatch.setattr(adapter.tempfile, 'mkdtemp', lambda **_: str(stage))
    monkeypatch.setattr(harbor_codex_access, 'prepare_derivative', lambda *_: (b'{}', ('fake-access-token',)))
    monkeypatch.setattr(harbor_codex_access, 'read_account_reference', lambda *_: 'synthetic-account-reference')
    monkeypatch.setattr(harbor_codex_access, 'derivative_not_after', lambda *_: float('inf'))
    monkeypatch.setattr(adapter, 'run_harbor', lambda *_, **options:
                        options['cleanup_clock'].update(deadline=float('inf')) or {'status': 'SUCCEEDED'})
    monkeypatch.setattr(adapter, 'release_access_run', lambda *args, **_: (args[3] / 'launch.json').write_text('{"status":"SUCCEEDED"}'))
    remove = adapter.remove_access_directory

    def refuse_private_cleanup(path, **kwargs):
        if path == holder:
            return False
        return remove(path, **kwargs)

    monkeypatch.setattr(adapter, 'remove_access_directory', refuse_private_cleanup)
    with reference.open('rb') as fd:
        result = adapter.run_access(incident, 'baseline', output, auth, fd.fileno())
    assert result['status'] == 'ACCESS_OR_RELEASE_REJECTED'
    assert result['private_recovery_id'] == holder.name
    assert json.loads((output / 'launch.json').read_text())['status'] == 'ACCESS_OR_RELEASE_REJECTED'
    assert holder.exists() and not stage.exists()


def test_private_reference_rejects_mutable_file_and_pipe(tmp_path):
    from harbor_codex_access import read_account_reference
    reference = tmp_path / 'reference'
    reference.write_text('synthetic-account-reference\n')
    reference.chmod(0o600)
    with reference.open('rb') as stream:
        with pytest.raises(ValueError):
            read_account_reference(stream.fileno(), reference)
    read_fd, write_fd = os.pipe()
    try:
        os.write(write_fd, b'synthetic-account-reference')
        with pytest.raises(ValueError):
            read_account_reference(read_fd, reference)
    finally:
        os.close(read_fd)
        os.close(write_fd)


def test_access_failure_cleanup_does_not_disclose_private_filename(tmp_path, monkeypatch, capsys):
    import harbor_codex_access
    incident = SimpleNamespace(runtime={'auth_mode': adapter.ACCESS_MODE, 'timeout_sec': 900, 'concurrency': 1},
                               trials={'baseline': 5}, manifest_sha256='a' * 64, case_sha256='b' * 64,
                               snapshot=tmp_path / 'snapshot', tasks={})
    reference = tmp_path / 'reference'
    reference.write_text('synthetic-account-reference\n')
    reference.chmod(0o600)
    auth = tmp_path / 'fake-auth'
    auth.write_text('{}')
    output, holder, stage = (tmp_path / name for name in ('output', 'harbor-codex-a234567_', 'stage'))
    for directory in (holder, stage):
        directory.mkdir()
    canary = 'fixture-fake-private-token'
    (holder / canary).write_text('fixture')
    monkeypatch.setattr(adapter, 'reserve_access_holder', lambda _: holder)
    monkeypatch.setattr(adapter.tempfile, 'mkdtemp', lambda **_: str(stage))
    monkeypatch.setattr(harbor_codex_access, 'prepare_derivative', lambda *_: (b'{}', (canary,)))
    monkeypatch.setattr(harbor_codex_access, 'read_account_reference', lambda *_: 'synthetic-account-reference')
    monkeypatch.setattr(harbor_codex_access, 'derivative_not_after', lambda *_: float('inf'))
    monkeypatch.setattr(adapter, 'run_harbor', lambda *_, **options:
                        options['cleanup_clock'].update(deadline=float('inf')) or {'status': 'SUCCEEDED'})
    def reject_release(*_, **__):
        raise ValueError('unsafe artifact path')
    def reject_cleanup(command, **kwargs):
        if command[-1] == str(holder):
            raise OSError(13, 'fixture cleanup failure', str(holder / canary))
        return invoke(command, **kwargs)
    monkeypatch.setattr(adapter, 'release_access_run', reject_release)
    invoke = adapter.subprocess.run
    monkeypatch.setattr(adapter.subprocess, 'run', reject_cleanup)
    with reference.open('rb') as fd:
        result = adapter.run_access(incident, 'baseline', output, auth, fd.fileno())
    capture = capsys.readouterr()
    assert result['private_recovery_id'] == holder.name
    assert canary not in capture.out + capture.err + (output / 'launch.json').read_text()


def test_access_release_checks_raw_capture_but_does_not_publish_it(tmp_path):
    private_values = ('fake-access-bearer', 'fake-account-id')
    raw = tmp_path / 'raw'
    task = raw / 'staged' / 'task'
    trial = raw / 'jobs' / 'baseline' / 'trial'
    logs = trial / 'agent'
    for directory in (task, logs):
        directory.mkdir(parents=True)
    (task / 'instruction.md').write_text('Run the local fixture.')
    (task / 'tests').mkdir()
    (task / 'tests' / 'detector.md').write_text('Private detector')
    (task / 'tests' / 'answer.json').write_text('{"private":true}')
    (raw / 'stdout.log').write_text('stdout fake-access-bearer')
    (raw / 'stderr.log').write_text('stderr fake-account-id')
    (logs / 'completion.private.json').write_text('{"exit_code":1}')
    (trial / 'trial.log').write_text('agent fake-account-id')
    incident = SimpleNamespace(tasks={'baseline': task}, runtime={'model': 'gpt-example', 'effort': 'medium'},
                               trials={'baseline': 1})
    launch = {'staged_after': adapter.staged_inventory(raw), 'staged_before': adapter.staged_inventory(raw),
              'job_sha256': adapter.access_job_hash(trial.parent), 'run_sha256': 'a' * 64,
              'capture_sha256': adapter.access_capture_hashes(raw)}
    adapter.write_json(raw / 'launch.json', launch)
    stage = tmp_path / 'stage'
    stage.mkdir()
    output = tmp_path / 'released'
    (raw / 'stdout.log').write_text('changed after capture seal')
    with pytest.raises(ValueError, match='sealed acquisition changed'):
        adapter.release_access_run(incident, 'baseline', raw, stage, output, private_values, launch)
    assert not list(stage.iterdir())
    (raw / 'stdout.log').write_text('stdout fake-access-bearer')
    adapter.release_access_run(incident, 'baseline', raw, stage, output, private_values, launch)
    assert not (stage / 'stdout.log').exists()
    assert not (stage / 'stderr.log').exists()
    assert not (stage / 'staged').exists()
    retained = stage / 'jobs' / 'baseline' / 'trial' / 'agent'
    assert not (retained.parent / 'trial.log').exists()
    assert not (retained / 'completion.private.json').exists()
    proof = json.loads((retained / 'completion.json').read_bytes())
    assert proof == {'verified': False, 'thread_id': None, 'raw_observation_verified': False}
    record = json.loads((stage / 'launch.json').read_bytes())
    assert record['retained_root'] == str(output)
    assert record['release_status'] == 'INCOMPLETE'
    assert record['verified_native_trials'] == 0
    assert record['job_sha256'] == adapter.tree_hash_if_available(retained.parent.parent)
    (task / 'instruction.md').write_text('Fixture with fake-access-bearer')
    launch['staged_before'] = launch['staged_after'] = adapter.staged_inventory(raw)
    launch['job_sha256'] = adapter.access_job_hash(trial.parent)
    launch['capture_sha256'] = adapter.access_capture_hashes(raw)
    launch.pop('retained_root')
    launch.pop('release_status')
    adapter.write_json(raw / 'launch.json', launch, replace=True)
    fresh = tmp_path / 'unsafe-stage'
    fresh.mkdir()
    with pytest.raises(ValueError, match='private value remains'):
        adapter.release_access_run(incident, 'baseline', raw, fresh, output, private_values, launch)
    assert not (fresh / 'staged' / 'task' / 'instruction.md').exists()
    assert not output.exists()


def test_release_cannot_use_observation_for_unrelated_native_trace(monkeypatch, tmp_path):
    import harbor_codex_completion

    private_values = ('fake-access-bearer',)
    raw = tmp_path / 'raw'
    task = raw / 'staged' / 'task'
    agent = raw / 'jobs' / 'baseline' / 'trial' / 'agent'
    agent.mkdir(parents=True)
    task.mkdir(parents=True)
    (task / 'instruction.md').write_text('Run the local fixture.')
    (agent / 'completion.private.json').write_text(json.dumps({'exit_code': 0, 'sha256': 'a' * 64}))
    (agent / 'codex.txt').write_text('{"type":"turn.completed"}\n')
    incident = SimpleNamespace(tasks={'baseline': task}, runtime={'model': 'gpt-example', 'effort': 'medium'},
                               trials={'baseline': 1})
    launch = {'staged_before': adapter.staged_inventory(raw), 'staged_after': adapter.staged_inventory(raw),
              'job_sha256': adapter.access_job_hash(agent.parent.parent), 'run_sha256': 'b' * 64,
              'capture_sha256': adapter.access_capture_hashes(raw)}
    adapter.write_json(raw / 'launch.json', launch)
    monkeypatch.setattr(harbor_codex_completion, 'verify_completion',
                        lambda *args: ('thread', 'a' * 64, agent / 'sessions' / 'rollout.jsonl'))
    monkeypatch.setattr(adapter, 'check_observation', lambda *args, **kwargs: ({}, 'b' * 64))
    stage = tmp_path / 'sealed'
    stage.mkdir()
    adapter.release_access_run(incident, 'baseline', raw, stage, tmp_path / 'out', private_values, launch)
    receipt = json.loads((stage / agent.relative_to(raw) / 'completion.json').read_bytes())
    assert receipt['verified'] and not receipt['raw_observation_verified']


def test_access_namespace_is_bound_to_acquisition(tmp_path):
    experiment = SimpleNamespace(case_sha256='a' * 64, runtime={'auth_mode': adapter.ACCESS_MODE})
    first, second = (adapter.staged_name(experiment, tmp_path / name) for name in ('first', 'second'))
    assert first != second
    assert adapter.staged_name(experiment, tmp_path / 'first') == first


@pytest.mark.parametrize('copy_at_wrong_path,malformed_result,missing_egress,private_trace,fixture_fault', [
    (False, False, False, False, ''), (True, False, False, False, ''), (False, True, False, False, ''),
    (False, False, True, False, ''), (False, False, False, True, ''),
    (False, False, False, False, 'private_tsv'), (False, False, False, False, 'missing_native_control'),
    (False, False, False, False, 'unsealable_sibling'), (False, False, False, False, 'stale_witness'),
    (False, False, False, False, 'ineligible_duplicate'), (False, False, False, False, 'unsafe_trial_name'),
])
def test_access_release_scopes_jobs_and_withholds_only_malformed_trial(monkeypatch, tmp_path, copy_at_wrong_path,
                                                                       malformed_result, missing_egress,
                                                                       private_trace, fixture_fault):
    import harbor_codex_completion

    raw = tmp_path / 'raw'
    incident = SimpleNamespace(runtime={'model': 'gpt-example', 'effort': 'medium', 'auth_mode': adapter.ACCESS_MODE,
                                       'agent': 'codex', 'agent_version': '0.172.0'}, case_sha256='b' * 64,
                               trials={'baseline': 2}, task_names={'baseline': 'task'}, images={'baseline': {}},
                               run_sha256=lambda arm, directory: 'a' * 64,
                               verifier_env=lambda arm, run: {'HARBOR_EXPERIMENT_ARM': arm})
    namespace = adapter.staged_name(incident, raw)
    task = raw / 'staged' / namespace
    job = raw / 'jobs' / 'baseline'
    good = job / 'good'
    bad = job / ('fake-access-bearer' if fixture_fault == 'unsafe_trial_name' else 'bad')
    for directory in (task, bad / 'agent', good / 'agent', good / 'verifier'):
        directory.mkdir(parents=True)
    (task / 'instruction.md').write_text('Run the local fixture.')
    control = task / 'environment' / 'workspace' / 'AGENTS.md'
    control.parent.mkdir(parents=True)
    control.write_text('fixture control\n')
    (bad / 'result.json').write_text('{}')
    (bad / 'agent' / 'codex.txt').write_text('unterminated native record')
    rollout = good / 'agent' / 'sessions' / '2026/11/26/rollout-unit.jsonl'
    rollout.parent.mkdir(parents=True)
    thread = str(uuid4())
    records = [
        {'type': 'session_meta', 'payload': {'id': thread, 'cli_version': '0.172.0', 'model_provider': 'openai'}},
        {'type': 'event_msg', 'payload': {'type': 'task_started', 'turn_id': 'root', 'root_turn_id': 'root'}},
        {'type': 'response_item', 'payload': {'type': 'message', 'role': 'user', 'content': [{
            'type': 'input_text', 'text': '# AGENTS.md instructions for /workspace\n\n<INSTRUCTIONS>\nfixture control\n\n</INSTRUCTIONS>'}],
            'internal_chat_message_metadata_passthrough': {'turn_id': 'root', 'content_item_kinds': ['agents_md.instructions']}}},
        {'type': 'turn_context', 'payload': {'cwd': '/workspace', 'turn_id': 'root', 'root_turn_id': 'root',
                                            'model': 'gpt-example', 'effort': 'medium'}},
        {'type': 'response_item', 'payload': {'type': 'message', 'role': 'user', 'content': [{
            'type': 'input_text', 'text': 'Run the local fixture.'}], 'internal_chat_message_metadata_passthrough': {
                'turn_id': 'root', 'content_item_kinds': ['user.text']}}},
        {'type': 'response_item', 'payload': {'type': 'message', 'role': 'assistant', 'content': [{
            'type': 'output_text', 'text': 'usable result'}]}},
        {'type': 'event_msg', 'payload': {'type': 'agent_message',
                                         'message': 'fake-access-bearer' if private_trace else 'usable result'}},
        {'type': 'event_msg', 'payload': {'type': 'item_completed', 'thread_id': thread, 'turn_id': 'root',
             'item': {'id': 'answer', 'type': 'AgentMessage', 'phase': 'final_answer',
                      'content': [{'type': 'Text', 'text': 'usable result'}]}}},
        {'type': 'event_msg', 'payload': {'type': 'task_complete', 'turn_id': 'root'}},
    ]
    if fixture_fault == 'missing_native_control':
        records.pop(2)
    rollout.write_bytes(b''.join(adapter.canonical({'timestamp': '2026-11-26T12:00:00Z', **record}) + b'\n'
                                 for record in records))
    raw_trace = good / 'agent' / 'copy.log' if copy_at_wrong_path else rollout
    if copy_at_wrong_path:
        raw_trace.write_bytes(rollout.read_bytes())
    reference = {'path': raw_trace.relative_to(good).as_posix(), 'sha256': sha(rollout.read_bytes())}
    records = adapter.staged_inventory(raw, namespace)
    incident.tasks = {'baseline': task}
    incident.intervention_paths = [control.relative_to(task).as_posix()]
    incident.inventories = {'baseline': {row['path']: row for row in records}}
    timestamp = '2026-11-26T12:00:00Z'
    timing = {'started_at': timestamp, 'finished_at': timestamp}
    harbor_config = {'trial_name': good.name, 'trials_dir': str(job), 'job_id': str(uuid4()),
        'task': {'path': str(task)}, 'agent': {'name': 'codex', 'model_name': 'gpt-example',
        'kwargs': {'version': '0.172.0', 'reasoning_effort': 'medium', 'config': adapter.ACCESS_AGENT_CONFIG},
        'extra_allowed_hosts': ['chatgpt.com']}, 'verifier': {'env': {'HARBOR_EXPERIMENT_ARM': 'baseline'}}}
    result = {} if malformed_result else {
        'id': str(uuid4()), 'task_name': 'task', 'trial_name': good.name, 'trial_uri': good.as_uri(),
        'task_id': {'path': str(task)}, 'task_checksum': adapter.harbor_checksum(records), 'config': harbor_config,
        'agent_info': {'name': 'codex', 'version': '0.172.0', 'model_info': {'name': 'gpt-example'}},
        'agent_execution': timing, 'verifier_environment_mode': 'separate',
        'verifier_result': {'rewards': {'exposure_verified': 1}}, 'exception_info': None, **timing}
    adapter.write_json(good / 'result.json', result)
    adapter.write_json(good / 'config.json', harbor_config)
    adapter.write_json(good / 'access-egress.json', {'project': 'good__env', 'main': '1' * 64, 'sidecar': '2' * 64,
                                                   'allowed_host': 'chatgpt.com'})
    fixture_log = good / 'artifacts' / 'approved' / 'fixture-events.tsv'
    fixture_log.parent.mkdir(parents=True)
    fixture_log.write_text('read\t' + ('fake-access-bearer' if fixture_fault == 'private_tsv' else 'status') + '\n')
    witness = fixture_log.with_name('exposure.json')
    adapter.write_json(witness, {'trial': good.name, 'trial_id': result.get('id'), 'thread_id': thread,
        'run_sha256': ('d' if fixture_fault == 'stale_witness' else 'a') * 64, 'raw_rollout_sha256': reference['sha256'],
        'first_turn': {'turn_id': 'root', 'instructions': [2, 0], 'task_input': [4, 0]},
        'control_sha256': sha(control.read_bytes()), 'prompt_sha256': sha((task / 'instruction.md').read_bytes())})
    observation = good / 'verifier' / 'exposure-observation.json'
    observation.write_text(json.dumps({'schema': 'experiment-exposure-observation.v1', 'arm': 'baseline',
                                       'case_sha256': 'b' * 64, 'run_sha256': 'a' * 64,
                                       'trial': good.name, 'trial_id': result.get('id'), 'thread_id': thread,
                                       'instructions': [{'path': control.relative_to(task).as_posix(),
                                                         'sha256': sha(control.read_bytes())}],
                                       'trajectory': reference, 'evidence': [{'path': witness.relative_to(good).as_posix(),
                                                                             'sha256': sha(witness.read_bytes())}]}))
    native_digest = reference['sha256']
    (good / 'agent' / 'completion.private.json').write_text(json.dumps({'exit_code': 0, 'sha256': native_digest}))
    (good / 'agent' / 'codex.txt').write_text(
        '{"type":"turn.completed","usage":{"input_tokens":31,"output_tokens":4}}\n')
    original_bad_digest = 'f' * 64
    (bad / 'agent' / 'completion.private.json').write_text(json.dumps({'exit_code': 0, 'sha256': original_bad_digest}))
    (raw / 'stdout.log').write_text(original_bad_digest)
    (good / 'trial.log').write_text(native_digest)
    if fixture_fault == 'unsealable_sibling':
        (bad / 'unreadable.json').symlink_to(tmp_path / 'absent')
    def verified(receipt, *_):
        if good in receipt.parents or fixture_fault == 'ineligible_duplicate':
            return thread, native_digest, rollout
        raise ValueError('copied rollout changed')

    monkeypatch.setattr(harbor_codex_completion, 'verify_completion', verified)
    launch = {'staged_after': records, 'staged_before': records,
              'job_sha256': adapter.access_job_inventory(job, isolate_trials=True)[0], 'run_sha256': 'a' * 64,
              'docker_sealed_resources': {'eligible_trials': [] if missing_egress else [good.name]},
              'capture_sha256': adapter.access_capture_hashes(raw)}
    if fixture_fault == 'unsafe_trial_name':
        launch['docker_sealed_resources'] = {'eligible_trials': sorted((bad.name, good.name)),
                                            'started_trials': sorted((bad.name.lower(), good.name.lower()))}
    adapter.write_json(raw / 'launch.json', launch)
    sibling = job.parent / 'unexpected.log'
    sibling.write_text('unexpected')
    stage = tmp_path / 'stage'
    stage.mkdir()
    with pytest.raises(ValueError, match='unexpected job scope'):
        adapter.release_access_run(incident, 'baseline', raw, stage, tmp_path / 'out', ('fake-access-bearer',), launch)
    assert not list(stage.iterdir())
    sibling.unlink()
    unexpected = raw / 'work' / 'unrecognized.bin'
    unexpected.parent.mkdir()
    unexpected.write_bytes(b'fixture')
    with pytest.raises(ValueError, match='unexpected private work output'):
        adapter.release_access_run(incident, 'baseline', raw, stage, tmp_path / 'out', ('fake-access-bearer',), launch)
    assert not list(stage.iterdir())
    unexpected.unlink()
    adapter.release_access_run(incident, 'baseline', raw, stage, tmp_path / 'out', ('fake-access-bearer',), launch)
    if fixture_fault == 'unsafe_trial_name':
        assert not (stage / bad.relative_to(raw)).exists()
        retained_bad, = (path.parent for path in (stage / job.relative_to(raw)).glob('*/access-withheld.json'))
        assert launch['docker_sealed_resources'] == {'eligible_trials': [good.name],
                                                      'started_trials': [good.name.lower()]}
    else:
        retained_bad = stage / bad.relative_to(raw)
    assert sorted(path.name for path in retained_bad.iterdir()) == ['access-withheld.json']
    assert json.loads((retained_bad / 'access-withheld.json').read_bytes()) == {'result_present': True}
    assert not (stage / 'stdout.log').exists()
    assert launch['release_status'] == 'INCOMPLETE'
    if copy_at_wrong_path or malformed_result or missing_egress or private_trace or fixture_fault == 'private_tsv':
        assert sorted(path.name for path in (stage / good.relative_to(raw)).iterdir()) == ['access-withheld.json']
        assert launch['verified_native_trials'] == 0
        return
    retained_rollout = stage / rollout.relative_to(raw)
    assert b'usable result' in retained_rollout.read_bytes()
    assert b'fixture control' not in retained_rollout.read_bytes()
    if fixture_fault in ('missing_native_control', 'stale_witness'):
        assert not (stage / observation.relative_to(raw)).exists()
        assert launch['verified_native_trials'] == 0
        return
    retained_observation = json.loads((stage / observation.relative_to(raw)).read_bytes())
    assert retained_observation['trajectory']['sha256'] == sha(retained_rollout.read_bytes())
    retained_result = stage / (good / 'result.json').relative_to(raw)
    assessed = adapter.check_trial(incident, 'baseline', retained_result.parent, raw, result['task_checksum'],
        harbor_config['job_id'], json.loads(retained_result.read_bytes()), sha(retained_result.read_bytes()))
    assert assessed['exposure']['observation']['sha256'] == sha((stage / observation.relative_to(raw)).read_bytes())
    assert assessed['trajectory_sha256'] == sha(retained_rollout.read_bytes())
    assert assessed['native_completion']['usage'] == {'input_tokens': 31, 'output_tokens': 4}
    assert not (stage / good.relative_to(raw) / 'trial.log').exists()


def test_release_projects_diagnostics_without_dropping_valid_runtime_metrics():
    result_path = Path('jobs/baseline/trial/result.json')
    payload = {'id': 'fixture', 'agent_result': {'n_input_tokens': 21, 'diagnostic': {'parts': ['pri', 'vate']}},
               'exception_info': {'exception_type': 'Cancelled', 'exception_message': 'sample secret',
                                  'exception_traceback': 'private backtrace'}, 'unknown': {'unsafe': 'data'}}
    actual = adapter.access_json_projection(result_path, payload)
    assert actual == {'id': 'fixture', 'agent_result': {'n_input_tokens': 21},
                      'exception_info': {'exception_type': 'Cancelled'}}
    with pytest.raises(ValueError):
        adapter.access_json_projection(Path('jobs/baseline/config.json'), {'agents': [{'mcp_servers': {'external': {}}}]})
    with pytest.raises(ValueError):
        adapter.access_json_projection(Path('jobs/baseline/config.json'), {'agents': [{'kwargs': {
            'config': {**adapter.ACCESS_AGENT_CONFIG, 'chatgpt_base_url': 'https://fixture.invalid/'}}}]})


def test_live_verifier_identity_requires_expected_image_offline_mounts_and_no_credentials(tmp_path, monkeypatch):
    from harbor_codex_egress import OFFLINE_POLICY, SIDECAR

    main, image, sidecar = '2'*64, 'sha256:' + '3'*64, 'sha256:' + '4'*64
    prefix = 'owned__'
    job = tmp_path / 'jobs' / 'baseline'
    source = job / 'owned__Case' / 'verifier'
    source.mkdir(parents=True)
    event = {'Type': 'container', 'Action': 'start', 'Actor': {'ID': main, 'Attributes': {
        'com.docker.compose.project': 'owned__case__verifier__task', 'com.docker.compose.service': 'main'}}}
    record = [main, image, True, 'none', 'main', None, [
        {'Type': 'bind', 'Source': str(source), 'Destination': '/logs/verifier'}]]
    flags = []

    def inspect(_env, *argv, **_):
        return ''.join(flags) if 'CODEX_AUTH_JSON_PATH' in argv[-2] else json.dumps(record)

    monkeypatch.setattr(adapter, 'docker_query', inspect)
    qualify = lambda: adapter.verifier_start_identity({}, event, prefix, job, image, sidecar)
    assert qualify() is None
    flags.append('present')
    assert qualify() is None
    flags.clear()
    record[3] = 'bridge'
    assert qualify() is None
    record[3] = 'none'
    record[-1][0]['Type'] = 'volume'
    assert qualify() is None
    record[-1] = []
    record[1] = sidecar
    assert qualify() is None
    project = event['Actor']['Attributes']['com.docker.compose.project']
    sidecar_id = '8' * 64
    record[1] = image
    record[3] = 'container:' + sidecar_id
    label = [project]
    effective = OFFLINE_POLICY.copy()

    def sidecar_query(_env, *argv, **_):
        if argv[0] == 'exec':
            return '\n'.join(effective)
        if 'CODEX_AUTH_JSON_PATH' in argv[-2]:
            return ''
        if 'com.docker.compose.project' in argv[-2]:
            return project if argv[-1] == main else label[0]
        return json.dumps(record if argv[-1] == main else
                          [sidecar_id, sidecar, True, project + '_default', SIDECAR, 'healthy', []])

    monkeypatch.setattr(adapter, 'docker_query', sidecar_query)
    assert qualify() == main
    effective[-1] = 'chatgpt.com'
    assert qualify() is None
    effective[:] = OFFLINE_POLICY
    label[0] = 'unrelated'
    assert qualify() is None


def test_access_release_format_rejects_unbound_plaintext_transcript():
    with pytest.raises(ValueError, match='unrecognized retained output role'):
        adapter.retained_native_format(Path('jobs/baseline/trial/agent/renamed.txt'))
    assert adapter.retained_native_format(Path('jobs/baseline/trial/verifier/test-stdout.txt')) is None
    assert adapter.retained_native_format(Path('jobs/baseline/trial/agent/codex.txt')) is None


@pytest.mark.parametrize('result_present', [True, False, 'invalid_duplicate'])
def test_access_collection_counts_valid_siblings_of_withheld_trial(monkeypatch, tmp_path, result_present):
    task = tmp_path / 'fixture'
    task.mkdir()
    (task / 'task.toml').write_text('version = "1"\n')
    grade_path = tmp_path / 'cohort.json'
    tmp_path = tmp_path / 'release'
    native = Path('/dev/shm/harbor-codex-a234567_/acquisition-' + '1' * 32)
    experiment = SimpleNamespace(runtime={'auth_mode': adapter.ACCESS_MODE, 'harbor_version': '0.25.0',
                                          'agent_version': '0.172.0', 'agent': 'codex', 'model': 'gpt-example',
                                          'effort': 'medium', 'concurrency': 1},
                                 case_sha256='a' * 64, manifest_sha256='b' * 64, incident_id='fixture',
                                 incident_kind='constructed', trials={'baseline': 5}, tasks={'baseline': task},
                                 harbor_install_sha256='c' * 64, docker_client_sha256='d' * 64,
                                 egress_image_id='sha256:' + 'e' * 64,
                                 run_sha256=lambda *_: 'f' * 64, verifier_env=lambda *_: {})
    scope = adapter.staged_name(experiment, native)
    staged = tmp_path / 'staged' / scope
    staged.mkdir(parents=True)
    (staged / 'instruction.md').write_text('Run the fixture.\n')
    (staged / 'tests').mkdir()
    (staged / 'tests' / 'detector.md').write_text('Private semantic rubric.\n')
    records = adapter.staged_inventory(tmp_path, scope)
    for path in (staged / 'tests' / 'detector.md', staged / 'instruction.md'):
        path.unlink()
    for path in (staged / 'tests', staged, staged.parent):
        path.rmdir()
    experiment.inventories = {'baseline': {item['path']: item for item in records}}
    job = tmp_path / 'jobs' / 'baseline'
    grades = []
    for ordinal in range(5):
        trial = job / f'{scope}__{ordinal}'
        trial.mkdir(parents=True)
        if ordinal == 4 and result_present == 'invalid_duplicate':
            adapter.write_json(trial / 'result.json', {'id': grades[0]['trial_id'], 'invalid_test_result': True})
        elif ordinal == 4:
            adapter.write_json(trial / 'access-withheld.json', {'result_present': result_present})
        else:
            trial_id = str(uuid4())
            adapter.write_json(trial / 'result.json', {'id': trial_id})
            trace = trial / 'trace.jsonl'
            trace.write_text(json.dumps({'semantic_trial': ordinal}) + '\n')
            observation = trial / adapter.OBSERVATION_PATH
            observation.parent.mkdir()
            adapter.write_json(observation, {'trajectory': {'path': 'trace.jsonl'}})
            grades.append({'trial_id': trial_id, 'result_sha256': sha((trial / 'result.json').read_bytes()),
                           'trajectory_sha256': sha(trace.read_bytes()), 'verdict': 'VALID', 'evidence_lines': [1],
                           'detector_sha256': experiment.inventories['baseline'][adapter.PRIVATE_DETECTOR]['sha256'],
                           'metrics': {'incident_failure': int(ordinal == 0), 'task_completed': 1, 'regression_failed': 0}})
    command = '/fixture/bin/harbor'
    experiment.argv = lambda *_, command_prefix: [*command_prefix, command, 'run']
    adapter.write_json(job / 'config.json', {'job_name': 'baseline', 'jobs_dir': str(native / 'jobs'),
                       'n_attempts': 5, 'n_concurrent_trials': 1, 'tasks': [{'path': str(native / 'staged' / scope)}],
                       'agents': [{'name': 'codex', 'model_name': 'gpt-example', 'extra_allowed_hosts': ['chatgpt.com'],
                                   'kwargs': {'version': '0.172.0', 'reasoning_effort': 'medium',
                                              'config': adapter.ACCESS_AGENT_CONFIG}}], 'verifier': {'env': {}}})
    adapter.write_json(job / 'result.json', {'id': str(uuid4()), 'n_total_trials': 5, 'finished_at': None,
                       'stats': {'n_completed_trials': 4, 'n_cancelled_trials': 1}})
    def check_trial(_experiment, _arm, trial, _native, _checksum, _job, result, result_sha):
        if result.get('invalid_test_result'):
            raise ValueError('invalid sibling observation')
        return {'rewards': {'exposure_verified': 1}, 'trajectory_sha256': sha((trial / 'trace.jsonl').read_bytes()),
                'exposure': {'result_sha256': result_sha,
                             'observation': {'sha256': sha(str(trial).encode())}}}

    monkeypatch.setattr(adapter, 'check_trial', check_trial)
    launch = {'schema': adapter.LAUNCH_SCHEMA, 'run_dir': str(native), 'retained_root': str(tmp_path),
              'run_sha256': experiment.run_sha256(), 'arm': 'baseline', 'runtime': experiment.runtime,
              'manifest_sha256': experiment.manifest_sha256, 'case_sha256': experiment.case_sha256,
              'argv': experiment.argv(command_prefix=['/fixture/bin/python', *adapter.ACCESS_PYTHON_FLAGS]),
              'task_sha256': adapter.digest(adapter.canonical(records)), 'status': 'INTERRUPTED',
              'exit_code': -15, 'cleanup': 'docker_sealed', 'harbor_version': '0.25.0',
              'staged_before': records, 'staged_after': records, 'harbor_install_sha256': experiment.harbor_install_sha256,
              'docker_client_sha256': experiment.docker_client_sha256, 'egress_image_id': experiment.egress_image_id,
              'release_status': 'INCOMPLETE', 'docker_scope': scope + '__',
              'docker_sealed_resources': {'trial_projects': 5, 'container': 20,
                                           'started_trials': sorted(f'{scope}__{index}' for index in range(5)),
                                           'eligible_trials': sorted(f'{scope}__{index}' for index in
                                                                     range(5 if result_present == 'invalid_duplicate' else 4))},
              'job_sha256': adapter.tree_hash_if_available(job), 'capture_sha256': adapter.access_capture_hashes(tmp_path)}
    adapter.write_json(tmp_path / 'launch.json', launch)

    missing, _ = adapter.assess(experiment, 'baseline', tmp_path)
    assert missing['valid_trials'] == 0
    assert sum('independent semantic verdict not delivered' in row['errors'] for row in missing['trials']) == 4
    adapter.write_json(grade_path, {'schema': 'harbor-semantic-cohort.v1', 'case_sha256': experiment.case_sha256,
                                   'arm': 'baseline', 'launch_sha256': sha((tmp_path / 'launch.json').read_bytes()),
                                   'adjudicator': 'synthetic-test', 'trials': grades})
    unbound = experiment.inventories['baseline'].pop(adapter.PRIVATE_DETECTOR)
    rows, _ = adapter.trial_reports(experiment, 'baseline', tmp_path, native, launch['job_sha256'], [])
    assert sum('frozen detector is missing' in row['errors'] for row in rows) == 4
    experiment.inventories['baseline'][adapter.PRIVATE_DETECTOR] = unbound
    report, _ = adapter.assess(experiment, 'baseline', tmp_path, grade_path)

    assert report['status'] == 'INCOMPLETE'
    assert (report['observed_trials'], report['valid_trials'], report['invalid_trials']) == (5, 4, 1)
    assert (report['withheld_trials'], report['incident_failures'], report['run_errors']) == (int(result_present is True), 1, [])
    assert report['setup_starts'] == 5
    assert report['minimum_verified_subject_starts'] == 0
    assert all(row['setup_started'] and not row['native_start_verified'] for row in report['trials'])

    bound = json.loads(grade_path.read_bytes())
    bound['trials'] = [*grades, ['malformed row'], {'trial_id': str(uuid4())}, grades[1]]
    adapter.write_json(grade_path, bound, replace=True)
    partial, _ = adapter.assess(experiment, 'baseline', tmp_path, grade_path)
    assert (partial['valid_trials'], partial['incident_failures'], partial['ignored_adjudication_rows']) == (3, 1, 4)
    assert partial['run_errors'] == []


def test_access_quiescence_detects_resources_without_trial_metadata(monkeypatch, tmp_path):
    def query(env, *args):
        return 'unrelated\nbaseline-test-long__orphan_default' if args[0] == 'network' else 'other'

    monkeypatch.setattr(adapter, 'docker_query', query)
    assert not adapter.docker_quiescent('baseline-test-long__', {'HOME': str(tmp_path)})
    assert adapter.docker_quiescent('another-test-long__', {'HOME': str(tmp_path)})


@pytest.mark.parametrize('later_mount', [False, True])
def test_access_cleanup_removes_only_verified_compose_scope(monkeypatch, tmp_path, later_mount):
    prefix = 'codex-' + 'a' * 24 + '__'
    owned = prefix + 'trial__env'
    sibling = 'codex-' + 'b' * 24 + '__trial__env'
    resources = {kind: {kind + '-owned': owned, kind + '-sibling': sibling}
                 for kind in ('container', 'network', 'volume')}
    transcript = []

    def fake_query(env, *argv, timeout=10):
        assert 0 < timeout <= 10
        transcript.append(argv)
        kind = argv[0]
        if kind == 'info':
            return 'qualified-daemon'
        if kind == 'inspect':
            kind = argv[2]
            if argv[4] == '{{json .Mounts}}':
                return '\n'.join(json.dumps([{'Source': str(tmp_path)}] if later_mount else [])
                                 for identity in argv[5:])
            return '\n'.join(json.dumps({'com.docker.compose.project': resources[kind][identity]})
                             for identity in argv[5:])
        if kind in ('ps', 'rm'):
            kind = 'container'
        if 'rm' in argv:
            assert argv[-1] == kind + '-owned'
            del resources[kind][argv[-1]]
            return ''
        if '--format' in argv:
            return '\n'.join(resources[kind].values())
        return '\n'.join(resources[kind])

    monkeypatch.setattr(adapter, 'docker_query', fake_query)
    assert adapter.reconcile_access_docker(prefix, {}, tmp_path, 'wrong-daemon') is False
    assert len(transcript) == 1
    assert adapter.reconcile_access_docker(prefix, {}, tmp_path, 'qualified-daemon') is not later_mount
    assert all(list(groups.values()) == [sibling] for groups in resources.values())
    assert [argv[0] for argv in transcript if 'rm' in argv] == ['rm', 'network', 'volume']


def test_access_interruption_unlinks_before_docker_reconciliation(monkeypatch, tmp_path):
    task = tmp_path / 'fixture'
    task.mkdir()
    (task / 'task.toml').write_text('version = "1"\n')
    secret = tmp_path / 'secret'
    secret.write_text('fake-access-file')
    prefix = 'codex-' + 'a' * 24 + '__'
    output = tmp_path / 'acquisition'
    invocations = []
    experiment = SimpleNamespace(path=tmp_path / 'manifest', snapshot=tmp_path / 'snapshot',
                                 runtime={'auth_mode': adapter.ACCESS_MODE, 'harbor_version': '0.25.0',
                                          'concurrency': 1, 'timeout_sec': 1},
                                 tasks={'baseline': task}, inventories={'baseline': {'task.toml':
                                     adapter.inventory(task, allow_empty_dirs=False)[0]}},
                                 trials={'baseline': 1}, case_sha256='a' * 64, manifest_sha256='b' * 64,
                                 docker_server_id='same-daemon', harbor_install_sha256='c' * 64,
                                 docker_client_sha256='d' * 64, egress_image_id='sha256:' + 'e' * 64,
                                 images={'baseline': {'verifier_image_digest': 'sha256:' + 'e' * 64}},
                                 run_sha256=lambda *_: 'f' * 64,
                                 argv=lambda *_args, **_kwargs: ['synthetic-harbor', 'run'])
    monkeypatch.setattr(adapter.shutil, 'which', lambda *_: '/synthetic/bin/harbor')
    monkeypatch.setattr(adapter, 'qualified_harbor_install', lambda *_: None)
    monkeypatch.setattr(adapter, 'access_docker_env', lambda *_: {'PATH': '/usr/bin'})
    monkeypatch.setattr(adapter, 'access_harbor_command', lambda *_: ['/synthetic/bin/harbor'])
    monkeypatch.setattr(adapter, 'qualified_docker_prefix', lambda *_: prefix)
    monkeypatch.setattr(adapter, 'docker_quiescent', lambda *_: True)
    monkeypatch.setattr(adapter, 'qualified_access_executables', lambda *_: 'synthetic-egress')
    no_op = lambda *_, **__: None

    def invoke(argv, *, env, stdout, **_kwargs):
        if argv[-1] == '--version':
            stdout.write(b'0.25.0\n')
            stdout.flush()
            return 'SUCCEEDED', 0
        assert env['CODEX_AUTH_JSON_PATH'] == str(secret) and secret.exists()
        invocations.append('interrupted')
        return 'INTERRUPTED', -15

    def finish(**_):
        assert not secret.exists()
        return []

    def reconcile(scope, env, acquisition, daemon, **_):
        assert (scope, acquisition, daemon) == (prefix, tmp_path, 'same-daemon')
        assert not secret.exists() and 'CODEX_AUTH_JSON_PATH' not in env
        invocations.append('reconciled')
        return True

    monkeypatch.setattr(adapter, 'invoke', invoke)
    monkeypatch.setattr(adapter, 'DockerEvents', lambda *_, **__: SimpleNamespace(
        thread=SimpleNamespace(start=no_op), fence=no_op, first='start', finish=finish, close=no_op,
        verified_verifiers=set()))
    monkeypatch.setattr(adapter, 'docker_seal', lambda *_args, **_kwargs: None)
    monkeypatch.setattr(adapter, 'docker_fenced_volumes_clear', lambda *_: True)
    monkeypatch.setattr(adapter, 'reconcile_access_docker', reconcile)
    actual = adapter.run_harbor(experiment, 'baseline', output, None, derivative=secret, not_after=float('inf'))
    assert actual['status'] == 'UNSEALED' and actual['cleanup'] == 'docker_reconciled'
    assert invocations == ['interrupted', 'reconciled']
    assert not secret.exists()


def test_access_docker_seal_checks_lifecycle_ids_and_late_bind_mount(monkeypatch, tmp_path):
    prefix = 'owned__'
    identity = 'a' * 64
    events = []
    live = []
    mounts = []

    def event(action, identity, project, service):
        return json.dumps({'Type': 'container', 'Action': action, 'Actor': {
            'ID': identity, 'Attributes': {'com.docker.compose.project': project, 'com.docker.compose.service': service}}})

    def query(env, *args, **_):
        if args[0] == 'info':
            return 'same-daemon'
        if args[0] == 'events':
            return '\n'.join(events)
        if args[:3] == ('ps', '-aq', '--no-trunc'):
            return '\n'.join(live)
        if args[0] == 'inspect':
            return json.dumps(mounts)
        return ''

    monkeypatch.setattr(adapter, 'docker_query', query)
    def seal(expected=1, daemon='same-daemon', job=None, starts=()):
        receipt = adapter.docker_seal(prefix, {}, tmp_path, daemon, expected, events, job=job,
                                      verified_verifiers={'2' * 64})
        if receipt is not None:
            assert receipt.pop('started_trials') == list(starts)
        return receipt

    assert seal() == {'trial_projects': 0, 'eligible_trials': []}
    events.append(event('create', identity, 'owned__case__env', 'main'))
    assert seal() is None
    events.append(event('destroy', identity, 'owned__case__env', 'main'))
    assert seal() == {'container': 1, 'trial_projects': 1, 'eligible_trials': []}
    for index, (role, service) in enumerate((('env', 'harbor-docker-egress-control-sidecar'),
                                              ('verifier__task', 'main'),
                                              ('verifier__task', 'harbor-docker-egress-control-sidecar')), start=1):
        events.extend(event(action, str(index)*64, 'owned__case__' + role, service) for action in ('create', 'destroy'))
    assert seal() == {'container': 4, 'trial_projects': 1, 'eligible_trials': []}
    job = tmp_path / 'acquisition' / 'jobs' / 'baseline'
    trial = job / 'owned__Case'
    trial.mkdir(parents=True)
    receipt = trial / 'access-egress.json'
    proof = {'project': 'owned__case__env', 'main': identity, 'sidecar': '1' * 64, 'allowed_host': 'chatgpt.com'}
    receipt.write_text(json.dumps(proof))
    assert seal(job=job) == {'container': 4, 'trial_projects': 1, 'eligible_trials': []}
    events.insert(5, event('start', '2' * 64, 'owned__case__verifier__task', 'main'))
    assert seal(job=job, starts=('owned__case',)) == {
        'container': 4, 'trial_projects': 1, 'eligible_trials': ['owned__Case']}
    anonymous = {'Type': 'volume', 'Action': 'mount', 'Actor': {'ID': 'anonymous', 'Attributes': {'container': identity}}}
    events.append(anonymous)
    assert seal(job=job) is None
    assert adapter.docker_fenced_volumes_clear(prefix, {}, events, float('inf'))
    events.append({'Type': 'volume', 'Action': 'destroy', 'Actor': {'ID': 'anonymous', 'Attributes': {}}})
    assert seal(job=job, starts=('owned__case',)) == {
        'container': 4, 'trial_projects': 1, 'eligible_trials': ['owned__Case']}
    receipt.write_text(json.dumps({**proof, 'sidecar': '2' * 64}))
    assert seal(job=job) == {'container': 4, 'trial_projects': 1, 'eligible_trials': []}
    receipt.write_text(json.dumps(proof))
    receiptless = job / 'owned__missing'
    receiptless.mkdir()
    second_id = '9' * 64
    events.extend(event(action, second_id, 'owned__missing__env', 'main') for action in ('create', 'destroy'))
    events.insert(-1, event('start', second_id, 'owned__missing__env', 'main'))
    assert seal(2, job=job, starts=('owned__case', 'owned__missing')) == {
        'container': 5, 'trial_projects': 2, 'eligible_trials': ['owned__Case']}
    assert seal(1, job=job) is None
    destroyed = events[1]
    events[1] = event('destroy', identity, 'owned__different__env', 'main')
    assert seal() is None
    events[1] = destroyed
    live.append('b' * 64)
    (tmp_path / 'jobs').mkdir()
    alias = tmp_path.with_name(tmp_path.name + '-alias')
    alias.symlink_to(tmp_path / 'jobs', target_is_directory=True)
    mounts.append({'Source': str(alias / 'late-writer')})
    assert seal() is None
    assert seal(daemon='different-daemon') is None


def test_access_runtime_requires_qualified_local_image_ids_and_daemon(monkeypatch, tmp_path):
    image = 'sha256:' + 'a' * 64
    tmp_path = tmp_path / ('codex-' + 'a' * 24)
    tmp_path.mkdir()
    (tmp_path / 'task.toml').write_text(
        f'[agent]\ntimeout_sec=900\nnetwork_mode="allowlist"\nallowed_hosts=["chatgpt.com"]\n'
        f'[environment]\ndocker_image="{image}"\nnetwork_mode="no-network"\n'
        '[environment.healthcheck]\ncommand="/usr/local/bin/codex --harbor-check-denied"\nretries=1\n'
        f'[verifier]\nnetwork_mode="no-network"\n[verifier.environment]\ndocker_image="{image}"\n'
        'network_mode="no-network"\n')
    trial = SimpleNamespace(task_names={'baseline': 'local/baseline-test-long'},
                            runtime={'timeout_sec': 900},
                            images={'baseline': dict.fromkeys(adapter.IMAGE_FIELDS, image)}, docker_server_id='known')
    monkeypatch.setattr(adapter, 'docker_query', lambda env, *args: image if args[0] == 'image' else 'unknown')
    with pytest.raises(ValueError, match='Docker server does not match'):
        adapter.qualified_docker_prefix(trial, 'baseline', tmp_path, {})
    monkeypatch.setattr(adapter, 'docker_query', lambda env, *args: image if args[0] == 'image' else 'known')
    assert adapter.qualified_docker_prefix(trial, 'baseline', tmp_path, {}) == tmp_path.name + '__'
    task_path = tmp_path / 'task.toml'
    exact = task_path.read_text()
    task_path.write_text(exact.replace('["chatgpt.com"]', '["chatgpt.com", "auth.openai.com"]'))
    with pytest.raises(ValueError, match='network policy'):
        adapter.qualified_docker_prefix(trial, 'baseline', tmp_path, {})
    task_path.write_text(exact)
    trial.images['baseline']['agent_image_digest'] = 'sha256:' + 'b' * 64
    with pytest.raises(ValueError, match='qualified local image ID'):
        adapter.qualified_docker_prefix(trial, 'baseline', tmp_path, {})


def test_access_harbor_identity_binds_more_than_version_banner(tmp_path):
    launcher = tmp_path / 'bin' / 'harbor'
    launcher.parent.mkdir()
    launcher.write_text('#!/bin/sh\necho 0.25.0\n')
    launcher.chmod(0o700)
    interpreter = launcher.parent / 'python'
    interpreter.write_bytes(b'fixture interpreter')
    interpreter.chmod(0o700)
    assert adapter.access_harbor_command(launcher) == [str(interpreter), '-I', '-B', '-X',
                                                       'pycache_prefix=/dev/null', str(launcher)]
    (tmp_path / 'pyvenv.cfg').write_text('include-system-site-packages = false\n')
    package = tmp_path / 'lib' / 'python3.13' / 'site-packages' / 'harbor'
    package.mkdir(parents=True)
    core = package / '__init__.py'
    core.write_text('fixture = True\n')
    expected = adapter.access_harbor_identity(launcher)
    assert adapter.access_harbor_identity(launcher) == expected
    core.write_text('fixture = False\n')
    assert adapter.access_harbor_identity(launcher) != expected


def test_access_subprocess_ignores_stale_import_cache(tmp_path):
    import py_compile

    launcher = tmp_path / 'harbor'
    launcher.write_text('import sys\nsys.path.insert(0, sys.argv[1])\nimport guard\nprint(guard.route)\n')
    (tmp_path / 'python').symlink_to(sys.executable)
    module = tmp_path / 'guard.py'
    module.write_text('route = "wrong-source"\n')
    stale = module.stat()
    py_compile.compile(str(module), doraise=True, invalidation_mode=py_compile.PycInvalidationMode.TIMESTAMP)
    module.write_text('route = "right-bytes!"\n')
    assert module.stat().st_size == stale.st_size
    os.utime(module, ns=(stale.st_atime_ns, stale.st_mtime_ns))
    execute = lambda command: subprocess.check_output([*command, str(tmp_path)], text=True).strip()
    assert execute([sys.executable, '-I', '-B', str(launcher)]) == 'wrong-source'
    assert execute(adapter.access_harbor_command(launcher)) == 'right-bytes!'


def test_docker_identity_binds_discovered_compose_bytes(monkeypatch, tmp_path):
    docker = tmp_path / 'docker'
    compose = tmp_path / 'docker-compose'
    for executable in (docker, compose):
        executable.write_text('#!/bin/sh\nexit 0\n')
        executable.chmod(0o700)
    env = {'PATH': str(tmp_path)}
    monkeypatch.setattr(adapter, 'docker_query', lambda env, *args: json.dumps([{'Name': 'compose', 'Path': str(compose)}]))
    expected = adapter.access_docker_identity(env)
    compose.write_text('#!/bin/sh\nexit 1\n')
    assert adapter.access_docker_identity(env) != expected
    monkeypatch.setenv('PATH', str(tmp_path))
    assert adapter.access_docker_env(tmp_path)['PATH'] == os.defpath


def test_access_checks_sidecar_and_actual_image_files(monkeypatch, tmp_path):
    import harbor_codex_completion

    qualified = 'a' * 64
    shim = sha(Path(harbor_codex_completion.__file__).read_bytes())
    experiment = SimpleNamespace(docker_client_sha256=qualified, egress_image_id='sha256:' + qualified,
                                 codex_binary_sha256=qualified,
                                 images={'baseline': {'agent_image_digest': 'sha256:' + qualified}})
    tag = 'harbor-prebuilt:harbor-docker-egress-control-sidecar--' + qualified
    calls = []
    monkeypatch.setattr(adapter, 'access_docker_identity', lambda env: qualified)
    monkeypatch.setattr(adapter.subprocess, 'run', lambda *args, **kwargs: SimpleNamespace(stdout=tag + '\n'))

    def query(env, *args):
        calls.append(args)
        if args[0] == 'image':
            assert args[-1] == tag
            return experiment.egress_image_id
        assert '--network=none' in args and '--pull=never' in args
        return '\n'.join(f'{digest}  {path}' for digest, path in zip((shim, qualified), adapter.CODEX_IMAGE_EXECUTABLES))

    monkeypatch.setattr(adapter, 'docker_query', query)
    assert adapter.qualified_access_executables(experiment, 'baseline', ['python', '-I', '-B', 'harbor'], {}) == tag
    assert [call[0] for call in calls] == ['image', 'run']
    experiment.codex_binary_sha256 = 'b' * 64
    with pytest.raises(ValueError, match='reviewed shim and Codex binary'):
        adapter.qualified_access_executables(experiment, 'baseline', ['python', '-I', '-B', 'harbor'], {})


def test_access_output_roles_are_not_guessed_by_extension():
    for filename, expected in [('jobs/baseline/task__1/trial.log', None),
                               ('jobs/baseline/task__1/agent/codex.txt', None),
                               ('jobs/baseline/task__1/agent/sessions/2026/01/01/rollout-unit.jsonl', 'native_rollout')]:
        assert adapter.retained_native_format(Path(filename)) == expected
    for filename in ('jobs/baseline/task__1/agent/copy.log', 'jobs/baseline/task__1/arbitrary.jsonl'):
        with pytest.raises(ValueError, match='unrecognized retained output role'):
            adapter.retained_native_format(Path(filename))


def test_access_seal_includes_empty_directories(tmp_path):
    original = adapter.access_job_hash(tmp_path)
    (tmp_path / 'new-work').mkdir()
    assert adapter.access_job_hash(tmp_path) != original


def test_access_lifetime_covers_entire_serial_cohort():
    experiment = SimpleNamespace(runtime={'auth_mode': adapter.ACCESS_MODE, 'timeout_sec': 900, 'concurrency': 1},
                                 trials={'baseline': 5})
    assert adapter.wall_budget(experiment, 'baseline') == 5460
    experiment.runtime['concurrency'] = 2
    assert adapter.wall_budget(experiment, 'baseline') == 3300


def test_access_open_rejects_symlink_parent(tmp_path):
    owner = tmp_path / 'owner'
    owner.mkdir()
    (owner / 'auth.json').write_text('{}')
    link = tmp_path / 'redirect'
    link.symlink_to(owner, target_is_directory=True)
    with os.fdopen(adapter.open_auth_path(owner / 'auth.json'), 'rb') as stream:
        assert stream.read() == b'{}'
    with pytest.raises(OSError):
        adapter.open_auth_path(link / 'auth.json')


def test_access_rejected_release_distinguishes_withheld_and_missing(tmp_path):
    incident = SimpleNamespace(runtime={'auth_mode': adapter.ACCESS_MODE}, trials={'baseline': 5},
                               manifest_sha256='a' * 64, case_sha256='b' * 64,
                               incident_id='case', incident_kind='constructed')
    raw = tmp_path / 'raw'
    job = raw / 'jobs' / 'baseline'
    for name in ('one', 'two', 'missing'):
        (job / name).mkdir(parents=True)
        if name != 'missing':
            (job / name / 'result.json').write_text('{}')
    count = adapter.sealed_trial_count(raw, 'baseline', 5)
    output = tmp_path / 'withheld'
    adapter.emit_access_failure(incident, 'baseline', output, 'ACCESS_OR_RELEASE_REJECTED', count)
    report, _ = adapter.assess(incident, 'baseline', output)
    assert (report['missing_trials'], report['observed_trials'], report['invalid_trials']) == (3, 2, 2)
    assert all(row['status'] == 'WITHHELD' for row in report['trials'])


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


def test_verifier_metadata_handoff_and_host_envelope(harbor):
    launched, directory = harbor.run()
    assert launched.returncode == 0, launched.stderr
    launch = json.loads((directory / 'launch.json').read_bytes())
    expected = sha(canonical_bytes({
        'manifest_sha256': sha(harbor.case.path.read_bytes()),
        'arm': 'baseline',
        'run_dir': str(directory.resolve()),
    }))
    assert launch['run_sha256'] == expected
    trial = directory / 'jobs/baseline/task__0'
    observation = trial / 'verifier/exposure-observation.json'
    original_bytes = observation.read_bytes()
    _, _, report = harbor.collect(directory)
    assert report['status'] == 'REPRODUCED'
    assert observation.read_bytes() == original_bytes
    assert not (trial / 'verifier/exposure.json').exists()
    raw = json.loads(original_bytes)
    assert raw['run_sha256'] == expected
    assert 'trial_id' not in raw
    result_bytes = (trial / 'result.json').read_bytes()
    result = json.loads(result_bytes)
    assert report['trials'][0]['exposure'] == {
        'schema': 'experiment-exposure.v1',
        'trial_id': result['id'],
        'job_id': result['config']['job_id'],
        'arm': 'baseline',
        'case_sha256': harbor.case.case_sha256,
        'run_sha256': expected,
        'result_sha256': sha(result_bytes),
        'observation': {'path': 'verifier/exposure-observation.json', 'sha256': sha(original_bytes)},
        'qualified_images': harbor.case.images['baseline'],
    }


def test_copied_observation_and_native_trajectory_are_invalid(harbor):
    harbor.set_mode('copied_observation')
    launched, directory = harbor.run()
    assert launched.returncode == 0, launched.stderr
    _, _, report = harbor.collect(directory)
    assert report['status'] == 'INCOMPLETE'
    assert report['invalid_trials'] == 2
    for row in report['trials'][:2]:
        assert not row['valid']
        assert 'duplicate exposure observation' in row['errors']
        assert 'duplicate native trajectory' in row['errors']


def test_harbor_shutdown_warning_invalidates_collection(harbor):
    harbor.set_mode('cleanup_warning')
    launched, directory = harbor.run()
    assert launched.returncode != 0
    launch = json.loads((directory / 'launch.json').read_bytes())
    assert launch['exit_code'] == 0
    assert launch['cleanup'] == 'unverified'
    _, _, report = harbor.collect(directory)
    assert report['status'] == 'INCOMPLETE'
    assert report['incident_failures'] == 0
    assert any('cleanup' in reason for reason in report['trials'][0]['errors'])


def test_treatment_rejects_baseline_trajectory_with_a_fresh_observation(harbor):
    launched, baseline_run = harbor.run()
    assert launched.returncode == 0, launched.stderr
    _, baseline, baseline_report = harbor.collect(baseline_run)
    assert baseline_report['status'] == 'REPRODUCED'
    trace = baseline_run / 'jobs/baseline/task__0/agent/raw.jsonl'
    harbor.set_mode('cross_arm_trajectory', baseline_trajectory=str(trace))

    launched, treatment_run = harbor.run('treatment', None, '--baseline', baseline)
    assert launched.returncode == 0, launched.stderr
    _, _, report = harbor.collect(treatment_run, 'treatment')
    assert report['status'] == 'INCOMPLETE'
    assert report['valid_trials'] == report['task_completions'] == 4
    assert report['invalid_trials'] == 1
    reused = report['trials'][0]
    original = baseline_report['trials'][0]
    assert reused['trajectory_sha256'] == original['trajectory_sha256']
    assert reused['exposure']['observation']['sha256'] != original['exposure']['observation']['sha256']
    assert 'native trajectory was reused from the baseline' in reused['errors']


def test_treatment_output_cannot_modify_retained_baseline(harbor):
    launched, baseline_run = harbor.run()
    assert launched.returncode == 0, launched.stderr
    _, baseline, baseline_report = harbor.collect(baseline_run)
    assert baseline_report['status'] == 'REPRODUCED'
    alias = harbor.case.root / 'baseline-alias'
    alias.symlink_to(baseline_run, target_is_directory=True)
    output = alias / 'staged/task/treatment-output'

    launched = cli('run', harbor.case.path, '--arm', 'treatment',
                   '--baseline', baseline, '--output', output)
    assert launched.returncode != 0
    assert 'outside frozen task, snapshot and run directories' in launched.stderr
    assert not output.exists()
    assert len(harbor.calls) == 1


@pytest.mark.parametrize('corrupt_marker', [False, True])
def test_treatment_collection_preserves_retained_run_directories(harbor, corrupt_marker):
    launched, baseline_run = harbor.run()
    assert launched.returncode == 0, launched.stderr
    _, baseline, baseline_report = harbor.collect(baseline_run)
    assert baseline_report['status'] == 'REPRODUCED'
    launched, treatment_run = harbor.run('treatment', None, '--baseline', baseline)
    assert launched.returncode == 0, launched.stderr
    if corrupt_marker:
        (baseline_run / 'launch.json').write_text('unreadable launch record')

    for arm, retained in (('baseline', baseline_run), ('treatment', treatment_run)):
        alias = harbor.case.root / f'{arm}-collection-alias'
        alias.symlink_to(retained, target_is_directory=True)
        output = alias / 'jobs' / arm / 'nested-collection.json'
        collected = cli('collect', harbor.case.path, '--arm', 'treatment',
                        '--run', treatment_run, '--output', output)
        assert collected.returncode != 0
        assert not output.exists()

    _, _, report = harbor.collect(treatment_run, 'treatment')
    assert report['status'] == ('INCOMPLETE' if corrupt_marker else 'OBSERVED_FIXED')


@pytest.mark.parametrize('command', ['run', 'snapshot'])
def test_other_outputs_cannot_nest_in_retained_evidence(harbor, command):
    launched, retained = harbor.run()
    assert launched.returncode == 0, launched.stderr
    nested = retained / 'jobs/baseline/nested'
    if command == 'run':
        result, _ = harbor.run('baseline', nested)
    else:
        repo = harbor.case.root / 'repo'
        repo.mkdir()
        git(repo, 'init', '-q')
        git(repo, 'config', 'user.name', 'Test')
        git(repo, 'config', 'user.email', 'test@example.invalid')
        (repo / 'source.txt').write_text('source')
        git(repo, 'add', 'source.txt')
        git(repo, 'commit', '-qm', 'source')
        result = cli('snapshot', '--repo', repo, '--commit', git(repo, 'rev-parse', 'HEAD'),
                     '--output', nested)
    assert result.returncode != 0
    assert len(harbor.calls) == 1
    assert not nested.exists()
    assert not nested.with_name('nested.receipt.json').exists()
