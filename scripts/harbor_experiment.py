#!/usr/bin/env python3
"""Validate, run and collect control-first Harbor skill experiments."""

import argparse
from collections import Counter, defaultdict
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
import tomllib
from uuid import UUID


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode('utf-8')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def inventory(root, *, allow_empty_dirs=True):
    records = []
    directories = set()
    file_parents = set()
    for path in root.rglob('*'):
        require(not path.is_symlink(), 'symlinks are unsupported')
        relative = path.relative_to(root)
        relative_parts(relative.as_posix())
        if path.is_dir():
            directories.add(relative)
            continue
        require(path.is_file(), 'non-regular files are unsupported')
        records.append({'path': relative.as_posix(), 'sha256': file_digest(path),
                        'executable': bool(path.stat().st_mode & 0o111)})
        file_parents.update(relative.parents)
    require(allow_empty_dirs or directories <= file_parents, 'task tree has an empty directory')
    return sorted(records, key=lambda record: record['path'])


def git(repo, *args):
    return subprocess.run(['git', '-C', str(repo), *args], check=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE).stdout


def snapshot(repo, commit, output):
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('commit must be a full lowercase SHA-1')
    if git(repo, 'rev-parse', '--verify', commit + '^{commit}').decode().strip() != commit:
        raise ValueError('commit must identify a commit object')
    output = Path(output)
    root = Path(git(repo, 'rev-parse', '--show-toplevel').decode().strip()).resolve()
    if output.resolve().is_relative_to(root):
        raise ValueError('snapshot destination must be outside the source worktree')
    receipt = output.with_name(output.name + '.receipt.json')
    if output.exists() or output.is_symlink() or receipt.exists() or receipt.is_symlink():
        raise ValueError('snapshot destination or receipt already exists')
    raw = git(repo, 'ls-tree', '-rz', '--full-tree', commit)
    entries = []
    for item in raw.split(b'\0'):
        if not item:
            continue
        meta, name = item.split(b'\t', 1)
        mode, kind, oid = meta.split(b' ')
        if mode not in (b'100644', b'100755') or kind != b'blob':
            raise ValueError('unsupported Git object or mode')
        relative = name.decode('utf-8')
        parts = relative.split('/')
        if any(p in ('', '.', '..', '.git') for p in parts):
            raise ValueError('unsafe Git tree path')
        data = git(repo, 'cat-file', 'blob', oid.decode('ascii'))
        if data.startswith(b'version https://git-lfs.github.com/spec/v1\n'):
            raise ValueError('Git LFS pointers are unsupported')
        entries.append((parts, mode, data))
    output.mkdir()
    try:
        for parts, mode, data in entries:
            path = output.joinpath(*parts)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            path.chmod(0o755 if mode == b'100755' else 0o644)
        records = inventory(output)
        body = {'schema': 'experiment-snapshot.v1', 'repository_commit': commit,
                'inventory': records, 'sha256': digest(canonical(records))}
        with receipt.open('x', encoding='utf-8') as stream:
            json.dump(body, stream, sort_keys=True, indent=2)
            stream.write('\n')
    except BaseException:
        shutil.rmtree(output)
        raise
    return body


ARMS = ('baseline', 'treatment')
RUNTIME_FIELDS = ('harbor_version', 'agent', 'agent_version', 'model', 'effort',
                  'concurrency', 'timeout_sec')
CASE_FIELDS = ('schema', 'incident_id', 'incident_kind', 'incident_source', 'repository_commit',
               'snapshot', 'baseline_task', 'treatment_task', 'runtime', 'trials',
               'intervention_paths', 'provenance')
PROVENANCE_INPUTS = ('original_request', 'source_state', 'instructions', 'runtime',
                     'dependencies', 'external_state')
QUALIFICATION_CHECKS = ('immutable_inputs', 'hidden_verifier', 'restricted_network',
                        'credential_isolation', 'arm_isolation', 'cleanup_supported')
IMAGE_FIELDS = ('agent_image_digest', 'verifier_image_digest')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fields(value, expected, label):
    require(isinstance(value, dict), f'{label} must be an object')
    missing = set(expected) - value.keys()
    unknown = value.keys() - set(expected)
    require(not missing, f'{label} missing fields: {", ".join(sorted(missing))}')
    require(not unknown, f'{label} unknown fields: {", ".join(sorted(unknown))}')


def text(value, label):
    require(isinstance(value, str) and value.strip(), f'{label} must be nonempty text')
    return value


def matches(value, pattern, label):
    require(re.fullmatch(pattern, text(value, label)) is not None, f'invalid {label}')
    return value


def positive_integer(value, label, minimum=1):
    require(type(value) is int and value >= minimum, f'{label} must be an integer >= {minimum}')


def array(value, label, *, nonempty=True):
    require(isinstance(value, list) and (bool(value) or not nonempty),
            f'{label} must be {"a nonempty" if nonempty else "an"} array')
    return value


def parse_json(data, label):
    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, f'{label} contains duplicate key {key!r}')
            result[key] = value
        return result

    def finite(number):
        value = float(number)
        require(math.isfinite(value), f'{label} contains a non-finite number')
        return value

    try:
        return json.loads(data.decode('utf-8'), object_pairs_hook=object_pairs,
                          parse_float=finite, parse_constant=finite)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError(f'{label} is not valid JSON') from exc


def relative_parts(value):
    path = text(value, 'relative path')
    parts = path.split('/')
    require(
        not any(part in ('', '.', '..') for part in parts)
        and not any(char in path for char in ('\\', '\0'))
        and not any(re.match(r'^[A-Za-z]:', part) for part in parts),
        f'unsafe relative path {path!r}',
    )
    return parts


def safe_path(root, relative, *, directory=False):
    path = root
    for part in relative_parts(relative):
        path /= part
        require(not path.is_symlink(), f'symlink in path {relative!r}')
    valid = path.is_dir() if directory else path.is_file()
    require(valid, f'missing {"directory" if directory else "regular file"} {relative!r}')
    return path


def verify_ref(root, ref, label):
    fields(ref, ('path', 'sha256'), label)
    matches(ref['sha256'], r'[0-9a-f]{64}', f'{label} sha256')
    path = safe_path(root, ref['path'])
    require(file_digest(path) == ref['sha256'], f'{label} hash mismatch: {ref["path"]!r}')
    return path


def verify_refs(root, refs, label, *, nonempty=True):
    seen = set()
    for ref in array(refs, label, nonempty=nonempty):
        verify_ref(root, ref, label)
        require(ref['path'] not in seen, f'{label} contains a duplicate path')
        seen.add(ref['path'])
    return sorted(refs, key=lambda ref: ref['path'])


def record(root, ref, label, schema, keys):
    data = parse_json(verify_ref(root, ref, label).read_bytes(), label)
    fields(data, ('schema', *keys), label)
    require(data['schema'] == schema, f'invalid {label} schema')
    return data


def verify_tree(root, ref, label, *, allow_empty_dirs=True):
    fields(ref, ('path', 'sha256'), label)
    matches(ref['sha256'], r'[0-9a-f]{64}', f'{label} sha256')
    tree = safe_path(root, ref['path'], directory=True)
    files = inventory(tree, allow_empty_dirs=allow_empty_dirs)
    require(digest(canonical(files)) == ref['sha256'], f'{label} tree hash mismatch')
    return tree, {entry['path']: entry for entry in files}


def validate_task(tree, files, label):
    required = {'instruction.md', 'task.toml', 'environment/Dockerfile', 'tests/test.sh'}
    require(required <= files.keys(), f'{label} missing required task files')
    require(all(Path(name).name != '.harborignore' for name in files),
            f'{label} cannot use .harborignore: it changes the Harbor task checksum')
    task = tomllib.loads((tree / 'task.toml').read_text(encoding='utf-8'))
    verifier = task.get('verifier')
    require(isinstance(verifier, dict) and verifier.get('environment_mode') == 'separate',
            f'{label} requires a separate verifier')
    require(not task.get('steps'), f'{label} must be a single-step Harbor task')
    meta = task.get('task')
    if meta is not None:
        require(isinstance(meta, dict), f'{label} task metadata must be an object')
        return text(meta.get('name'), f'{label} task name')
    return 'task'  # the task is staged under this fixed name


class Experiment:
    def __init__(self, path):
        path = Path(path)
        require(not path.is_symlink() and path.is_file(), 'manifest must be a regular file')
        self.path = path.resolve()
        self.root = self.path.parent
        raw = self.path.read_bytes()
        self.manifest_sha256 = digest(raw)
        m = parse_json(raw, 'manifest')
        fields(m, (*CASE_FIELDS, 'design_files', 'code_files', 'reviews',
                   'packaging', 'qualification'), 'manifest')
        require(m['schema'] == 'harbor-skill-experiment.v1', 'invalid manifest schema')
        text(m['incident_id'], 'incident_id')
        text(m['incident_source'], 'incident_source')
        require(m['incident_kind'] in ('captured', 'constructed'), 'invalid incident_kind')
        matches(m['repository_commit'], r'[0-9a-f]{40}', 'repository_commit')
        self.incident_kind = m['incident_kind']
        self.incident_id = m['incident_id']
        self.snapshot, _ = verify_tree(self.root, m['snapshot'], 'snapshot')
        self.tasks = {}
        self.inventories = {}
        self.task_names = {}
        for arm in ARMS:
            self.tasks[arm], self.inventories[arm] = verify_tree(
                self.root, m[f'{arm}_task'], arm, allow_empty_dirs=False,
            )
            self.task_names[arm] = validate_task(self.tasks[arm], self.inventories[arm], arm)
        self.check_intervention(m['intervention_paths'])
        fields(m['runtime'], RUNTIME_FIELDS, 'runtime')
        self.runtime = m['runtime']
        require(self.runtime['harbor_version'] == '0.25.0' and self.runtime['agent'] == 'codex',
                'runtime must use Harbor 0.25.0 and codex')
        matches(self.runtime['agent_version'], r'[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?',
                'runtime.agent_version')
        for key in ('model', 'effort'):
            matches(self.runtime[key], r'[A-Za-z0-9][A-Za-z0-9._:/+-]*', f'runtime.{key}')
        for key in ('concurrency', 'timeout_sec'):
            positive_integer(self.runtime[key], f'runtime.{key}')
        fields(m['trials'], ARMS, 'trials')
        self.trials = m['trials']
        for arm in ARMS:
            positive_integer(self.trials[arm], f'trials.{arm}', 5)
        require(self.trials['baseline'] == self.trials['treatment'], 'arm trial counts must match')
        self.check_provenance(m)
        self.case_sha256 = digest(canonical({key: m[key] for key in CASE_FIELDS}))
        coordinator = self.check_packaging(m['packaging'])
        self.images = self.check_qualification(m['qualification'])
        self.check_reviews(m, coordinator)

    def check_intervention(self, paths):
        before, after = (self.inventories[arm] for arm in ARMS)
        self.intervention_paths = sorted(
            '/'.join(relative_parts(path)) for path in array(paths, 'intervention_paths')
        )
        declared = set(self.intervention_paths)
        require(len(declared) == len(paths), 'duplicate intervention path')
        for path in declared:
            require(path.startswith('environment/') and Path(path).suffix == '.md',
                    f'intervention must name a Markdown instruction file: {path!r}')
            require(path in before and path in after, f'instruction must exist in both arms: {path!r}')
            require(before[path]['executable'] == after[path]['executable'],
                    f'instruction executable mode changed: {path!r}')
        changed = {path for path in before.keys() | after.keys() if before.get(path) != after.get(path)}
        require(changed == declared,
                f'task differences must be exactly the declared instruction files: {sorted(changed ^ declared)}')

    def check_provenance(self, manifest):
        info = record(self.root, manifest['provenance'], 'provenance', 'experiment-provenance.v1',
                      ('incident_id', 'repository_commit', 'inputs'))
        for key in ('incident_id', 'repository_commit'):
            require(info[key] == manifest[key], f'provenance {key} mismatch')
        fields(info['inputs'], PROVENANCE_INPUTS, 'provenance inputs')
        for key, source in info['inputs'].items():
            label = f'provenance.inputs.{key}'
            fields(source, ('status', 'explanation', 'evidence'), label)
            status = source['status']
            require(status in ('recovered', 'reconstructed', 'missing'), f'invalid {label} status')
            require(self.incident_kind != 'captured' or status == 'recovered',
                    f'captured incident requires recovered {key}')
            text(source['explanation'], f'{label} explanation')
            verify_refs(self.root, source['evidence'], f'{label} evidence', nonempty=status == 'recovered')

    def check_packaging(self, ref):
        info = record(self.root, ref, 'packaging', 'experiment-packaging.v1',
                      ('reviewer_id', 'verdict', 'case_sha256', 'evidence'))
        require(info['verdict'] == 'READY' and info['case_sha256'] == self.case_sha256,
                'packaging is not READY for this case')
        verify_refs(self.root, info['evidence'], 'packaging evidence')
        return text(info['reviewer_id'], 'packaging reviewer_id')

    def check_qualification(self, ref):
        info = record(self.root, ref, 'qualification', 'experiment-qualification.v1',
                      ('verdict', 'case_sha256', 'images', 'checks'))
        require(info['verdict'] == 'READY' and info['case_sha256'] == self.case_sha256,
                'qualification is not READY for this case')
        fields(info['images'], ARMS, 'qualification images')
        for arm, images in info['images'].items():
            fields(images, IMAGE_FIELDS, f'qualification {arm} images')
            for key, value in images.items():
                matches(value, r'sha256:[0-9a-f]{64}', f'qualification {arm} {key}')
        fields(info['checks'], QUALIFICATION_CHECKS, 'qualification checks')
        for key, check in info['checks'].items():
            fields(check, ('passed', 'evidence'), key)
            require(check['passed'] is True, f'qualification check failed: {key}')
            verify_refs(self.root, check['evidence'], f'qualification {key} evidence')
        return info['images']

    def check_reviews(self, manifest, coordinator):
        phases = ('design', 'code')
        bundles = {}
        for phase in phases:
            refs = verify_refs(self.root, manifest[f'{phase}_files'], f'{phase} files')
            if phase == 'code':
                running = file_digest(Path(__file__).resolve())
                require(any(ref['sha256'] == running for ref in refs),
                        'reviewed code bundle must contain the executing adapter bytes')
            bundles[phase] = digest(canonical(refs))
        seats = {phase: set() for phase in phases}
        keys = ('phase', 'reviewer_id', 'verdict', 'bundle_sha256')
        for review in array(manifest['reviews'], 'reviews'):
            fields(review, (*keys, 'receipt'), 'review')
            phase = review['phase']
            require(phase in phases, 'invalid review phase')
            require(review['verdict'] == 'APPROVED' and review['bundle_sha256'] == bundles[phase],
                    f'stale or unapproved {phase} review')
            reviewer = text(review['reviewer_id'], 'reviewer_id')
            require(reviewer == reviewer.strip() and reviewer != coordinator
                    and reviewer not in seats[phase], f'ineligible or duplicate {phase} reviewer')
            info = record(self.root, review['receipt'], f'{phase} review receipt',
                          'experiment-review.v1', (*keys, 'output'))
            require(all(info[key] == review[key] for key in keys), f'{phase} review receipt mismatch')
            output = verify_ref(self.root, info['output'], f'{phase} reviewer output')
            lines = output.read_text(encoding='utf-8').rstrip('\r\n').splitlines()
            terminal = f'VERDICT: APPROVED at DOCUMENTS sha256:{bundles[phase]}'
            require(lines and lines[-1] == terminal, f'{phase} review lacks the exact terminal approval')
            seats[phase].add(reviewer)
        for phase in phases:
            require(len(seats[phase]) >= 2, f'{phase} requires two independent reviewers')

    def run_sha256(self, arm, directory):
        return digest(canonical({
            'manifest_sha256': self.manifest_sha256, 'arm': arm, 'run_dir': str(directory),
        }))

    def verifier_env(self, arm, run_sha256):
        return {
            'HARBOR_EXPERIMENT_CASE_SHA256': self.case_sha256,
            'HARBOR_EXPERIMENT_ARM': arm,
            'HARBOR_EXPERIMENT_RUN_SHA256': run_sha256,
        }

    def argv(self, arm, directory, executable='harbor', *, run_sha256=None):
        root = Path(directory)
        runtime = self.runtime
        argv = [
            executable, 'run', '-p', str(root / 'staged' / 'task'), '-a', runtime['agent'],
            '-m', runtime['model'], '--agent-kwarg', 'version=' + runtime['agent_version'],
            '--effort', runtime['effort'], '--jobs-dir', str(root / 'jobs'), '--job-name', arm,
            '--n-attempts', str(self.trials[arm]), '--n-concurrent', str(runtime['concurrency']),
        ]
        if run_sha256 is None:
            run_sha256 = self.run_sha256(arm, root)
        for key, value in self.verifier_env(arm, run_sha256).items():
            argv.extend(('--verifier-env', f'{key}={value}'))
        return argv


def plan(experiment):
    return {
        'case_sha256': experiment.case_sha256,
        'manifest_sha256': experiment.manifest_sha256,
        'baseline_argv': experiment.argv('baseline', '<NEW_RUN_DIR>', run_sha256='<RUN_SHA256>'),
        'treatment_argv': experiment.argv('treatment', '<NEW_RUN_DIR>', run_sha256='<RUN_SHA256>'),
        'treatment_gate': 'requires a matching REPRODUCED baseline receipt',
    }


LAUNCH_SCHEMA = 'experiment-launch.v1'
COLLECTION_SCHEMA = 'experiment-collection.v1'
OBSERVATION_PATH = 'verifier/exposure-observation.json'
CLEANUP_WARNINGS = (b'Docker compose down failed:', b'Docker compose stop failed:',
                    b'Cleanup interrupted for ', b'Warning: Agent environment cleanup failed for ')
REWARDS = ('valid', 'incident_failure', 'exposure_verified', 'task_completed', 'regression_failed')
PROVIDER_ENV = ('OPENAI_API_KEY', 'CODEX_API_KEY')
PROCESS_ENV = ('PATH', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TZ', 'DOCKER_HOST')


def write_json(path, data, *, replace=False):
    target = path.with_name(path.name + '.tmp') if replace else path
    with target.open('xb') as stream:
        stream.write(canonical(data) + b'\n')
    if replace:
        target.replace(path)


def read_object(path, label):
    data = parse_json(path.read_bytes(), label)
    require(isinstance(data, dict), f'{label} must be an object')
    return data


def resolve_input(path, *, directory=False):
    path = Path(path)
    require(not path.is_symlink(), f'input must not be a symlink: {path}')
    valid = path.is_dir() if directory else path.is_file()
    require(valid, f'missing input: {path}')
    return path.resolve()


def new_output(experiment, path, *, outside=()):
    path = Path(path)
    require(not path.exists() and not path.is_symlink(), f'output already exists: {path}')
    path = path.resolve()
    frozen = (experiment.snapshot, *experiment.tasks.values(), *outside)
    require(not any(path.is_relative_to(tree) for tree in frozen),
            'output must be outside frozen task, snapshot and run directories')
    return path


def harbor_checksum(records):
    # Harbor 0.25.0 uses dirhash 0.5's default name/data protocol. Task validation
    # excludes symlinks, empty directories and .harborignore filtering.
    entries = defaultdict(list)
    for item in records:
        path = Path(item['path'])
        entries[path.parent].append(f'data:{item["sha256"]}\0name:{path.name}')
        for parent in path.parents:
            entries.setdefault(parent, [])
    for directory in sorted(entries, key=lambda path: len(path.parts), reverse=True):
        checksum = digest('\0\0'.join(sorted(entries[directory])).encode('utf-8'))
        if directory == Path('.'):
            return checksum
        entries[directory.parent].append(f'dirhash:{checksum}\0name:{directory.name}')
    raise ValueError('Harbor task inventory is empty')


def process_group_alive(pid):
    try:
        os.killpg(pid, 0)
    except ProcessLookupError:
        return False
    return True


def stop_process_group(process):
    try:
        os.killpg(process.pid, signal.SIGTERM)
        # Reap the leader even if children keep its process group alive.
        deadline = time.monotonic() + 0.75
        while time.monotonic() < deadline:
            process.poll()
            if not process_group_alive(process.pid):
                return
            time.sleep(0.05)
    except ProcessLookupError:
        pass
    finally:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            pass


def invoke(argv, *, cwd, env, stdout, stderr, timeout):
    try:
        process = subprocess.Popen(
            argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
            start_new_session=True, shell=False,
        )
    except OSError:
        return 'START_FAILED', None
    try:
        code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        stop_process_group(process)
        return 'TIMED_OUT', process.returncode
    except KeyboardInterrupt:
        stop_process_group(process)
        return 'INTERRUPTED', process.returncode
    if process_group_alive(process.pid):
        stop_process_group(process)
        return 'ORPHANED', code
    return ('SUCCEEDED' if code == 0 else 'FAILED'), code


def tree_hash_if_available(root):
    if not root.is_dir() or root.is_symlink():
        return None
    try:
        return digest(canonical(inventory(root)))
    except (OSError, ValueError):
        return None


def staged_inventory(directory):
    staged = directory / 'staged'
    if staged.is_symlink() or (staged / 'task').is_symlink():
        return None
    try:
        return inventory(safe_path(directory, 'staged/task', directory=True), allow_empty_dirs=False)
    except (OSError, ValueError):
        return None


def cleanup_warning(path):
    with path.open('rb') as stream:
        return any(marker in line for line in stream for marker in CLEANUP_WARNINGS)


def run(experiment, arm, output, baseline):
    require(os.name == 'posix', 'run requires POSIX process groups')
    require((baseline is not None) == (arm == 'treatment'),
            'only treatment requires --baseline RECEIPT')
    baseline_ref = None
    protected = ()
    if arm == 'treatment':
        baseline_path = resolve_input(baseline)
        raw_baseline = baseline_path.read_bytes()
        baseline_report = validate_baseline(experiment, raw_baseline)
        protected = (Path(baseline_report['run_dir']),)
        baseline_ref = {'path': str(baseline_path), 'sha256': digest(raw_baseline)}

    directory = new_output(experiment, output, outside=protected)
    executable = shutil.which('harbor')
    require(executable is not None, 'Harbor 0.25.0 executable is required on PATH')
    argv = experiment.argv(arm, directory, str(Path(executable).absolute()))
    directory.mkdir(mode=0o700)
    receipt = {
        'schema': LAUNCH_SCHEMA,
        'manifest_sha256': experiment.manifest_sha256,
        'case_sha256': experiment.case_sha256,
        'run_dir': str(directory),
        'run_sha256': experiment.run_sha256(arm, directory),
        'arm': arm,
        'runtime': experiment.runtime,
        'task_sha256': digest(canonical(list(experiment.inventories[arm].values()))),
        'argv': argv,
        'baseline_receipt': baseline_ref,
        'status': 'RUNNING',
        'cleanup': 'unverified',
        'exit_code': None,
        'harbor_version': None,
        'staged_before': None,
        'staged_after': None,
        'job_sha256': None,
    }
    receipt_path = directory / 'launch.json'
    write_json(receipt_path, receipt)
    status, code = 'START_FAILED', None
    try:
        (directory / 'staged').mkdir()
        (directory / 'home').mkdir()
        (directory / 'work').mkdir()
        staged = directory / 'staged' / 'task'
        shutil.copytree(experiment.tasks[arm], staged, symlinks=True)
        receipt['staged_before'] = staged_inventory(directory)
        require(receipt['staged_before'] is not None
                and digest(canonical(receipt['staged_before'])) == receipt['task_sha256'],
                'staged task inputs do not match the manifest')
        write_json(receipt_path, receipt, replace=True)

        env = {key: os.environ[key] for key in PROCESS_ENV if key in os.environ}
        env['HOME'] = str(directory / 'home')
        common = {'cwd': directory / 'work', 'env': env}
        timeout = experiment.runtime['timeout_sec']
        with (
            (directory / 'version.stdout.log').open('xb') as version_stdout,
            (directory / 'version.stderr.log').open('xb') as version_stderr,
            (directory / 'stdout.log').open('xb') as stdout,
            (directory / 'stderr.log').open('xb') as stderr,
        ):
            status, code = invoke(
                [argv[0], '--version'], **common, stdout=version_stdout, stderr=version_stderr,
                timeout=min(10, timeout),
            )
            if status == 'SUCCEEDED':
                actual = (directory / 'version.stdout.log').read_bytes().strip()
                desired = experiment.runtime['harbor_version']
                if actual == desired.encode():
                    receipt['harbor_version'] = desired
                    env.update({key: os.environ[key] for key in PROVIDER_ENV if key in os.environ})
                    status, code = invoke(
                        argv, **common, stdout=stdout, stderr=stderr, timeout=timeout,
                    )
                else:
                    status = 'VERSION_MISMATCH'
    except KeyboardInterrupt:
        status = 'INTERRUPTED'
    finally:
        receipt['staged_after'] = staged_inventory(directory)
        jobs = directory / 'jobs'
        job = jobs / arm
        if not jobs.is_symlink():
            receipt['job_sha256'] = tree_hash_if_available(job)
        if status == 'SUCCEEDED':
            if receipt['staged_after'] == receipt['staged_before']:
                try:
                    current = Experiment(experiment.path)
                    require(current.manifest_sha256 == experiment.manifest_sha256,
                            'manifest changed during execution')
                except (OSError, ValueError):
                    status = 'INPUTS_CHANGED'
            else:
                status = 'INPUTS_CHANGED'
        if status == 'SUCCEEDED' and receipt['job_sha256'] is not None:
            try:
                if any(cleanup_warning(log) for log in job.glob('*/trial.log') if log.is_file()):
                    status = 'CLEANUP_FAILED'
            except OSError:
                status = 'CLEANUP_UNVERIFIED'
        receipt['status'] = status
        receipt['exit_code'] = code
        if status == 'SUCCEEDED':
            receipt['cleanup'] = 'harbor_completed'
        write_json(receipt_path, receipt, replace=True)
    return receipt


def check_job(experiment, arm, job, staged, verifier_env):
    config = read_object(safe_path(job, 'config.json'), 'Harbor job config')
    result = read_object(safe_path(job, 'result.json'), 'Harbor job result')
    expected = experiment.trials[arm]
    require(config.get('job_name') == arm and config.get('jobs_dir') == str(job.parent)
            and type(config.get('n_attempts')) is int and config['n_attempts'] == expected
            and config.get('n_concurrent_trials', 4) == experiment.runtime['concurrency'],
            'job config does not match the invocation')
    tasks = array(config.get('tasks'), 'Harbor job tasks')
    agents = array(config.get('agents'), 'Harbor job agents')
    require(len(tasks) == len(agents) == 1, 'job does not contain one task and one agent')
    check_local_task(tasks[0], staged)
    check_agent_config(agents[0], experiment.runtime)
    check_fresh_config(config)
    check_verifier_config(config, verifier_env)
    job_id = uuid_string(result.get('id'), 'job id')
    require(type(result.get('n_total_trials')) is int and result['n_total_trials'] == expected,
            'job result has the wrong scheduled trial count')
    require(result.get('finished_at') is not None, 'Harbor job did not finish')
    stats = result.get('stats')
    require(isinstance(stats, dict) and stats.get('n_completed_trials') == expected
            and all(stats.get(key, 0) == 0 for key in ('n_retries', 'n_pending_trials',
                                                      'n_running_trials', 'n_cancelled_trials')),
            'Harbor job reports incomplete, cancelled or retried trials')
    return job_id


def check_local_task(config, staged):
    require(isinstance(config, dict) and config.get('path') == str(staged)
            and not any(config.get(key) is not None
                        for key in ('git_url', 'git_commit_id', 'name', 'ref', 'download_dir', 'source')),
            'job or trial does not bind the staged local task')


def check_agent_config(config, runtime):
    require(isinstance(config, dict) and config.get('name') == runtime['agent']
            and config.get('model_name') == runtime['model']
            and config.get('kwargs') == {'version': runtime['agent_version'],
                                         'reasoning_effort': runtime['effort']}
            and not any(config.get(key) for key in ('import_path', 'load_trajectory', 'skills',
                                                    'resume_trajectory', 'skip_model_parsing',
                                                    'mcp_servers', 'env')),
            'job or trial has a mismatched agent configuration')


def check_verifier_config(config, expected_env):
    verifier = config.get('verifier')
    require(isinstance(verifier, dict) and verifier.get('env') == expected_env
            and verifier.get('import_path') is None and not verifier.get('kwargs')
            and verifier.get('disable', False) is False,
            'job or trial has mismatched native verifier environment')


def check_fresh_config(config):
    require(not any(config.get(key) for key in ('install_only', 'user_agent', 'source_trial',
                                                'source_jobs', 'datasets', 'extra_instruction_paths',
                                                'extra_instructions')),
            'job or trial is not a fresh single-task invocation')


def uuid_string(value, label):
    value = text(value, label)
    require(str(UUID(value)) == value, f'invalid {label}')
    return value


def timestamps(start, finish):
    started = datetime.fromisoformat(text(start, 'trial start time'))
    finished = datetime.fromisoformat(text(finish, 'trial finish time'))
    require(started.tzinfo is not None and finished.tzinfo is not None and started <= finished,
            'invalid trial timestamps')


def check_observation(experiment, arm, trial, run_sha256):
    path = safe_path(trial, OBSERVATION_PATH)
    raw = path.read_bytes()
    exposure = parse_json(raw, 'exposure observation')
    fields(exposure, ('schema', 'arm', 'case_sha256', 'run_sha256', 'instructions',
                      'trajectory', 'evidence'), 'exposure observation')
    require(exposure['schema'] == 'experiment-exposure-observation.v1'
            and exposure['arm'] == arm and exposure['case_sha256'] == experiment.case_sha256
            and exposure['run_sha256'] == run_sha256,
            'exposure observation does not bind this arm, case and run')
    expected = [
        {'path': name, 'sha256': experiment.inventories[arm][name]['sha256']}
        for name in experiment.intervention_paths
    ]
    instructions = array(exposure['instructions'], 'exposure instructions')
    require(all(isinstance(item, dict) and isinstance(item.get('path'), str) for item in instructions)
            and sorted(instructions, key=lambda item: item['path']) == expected,
            'exposure receipt does not bind all intervention files')
    trace = verify_ref(trial, exposure['trajectory'], 'raw trajectory')
    require(trace != path and trace.stat().st_size > 0,
            'raw trajectory is empty or is the exposure observation')
    verify_refs(trial, exposure['evidence'], 'exposure evidence')
    return {'path': OBSERVATION_PATH, 'sha256': digest(raw)}, exposure['trajectory']['sha256']


def check_trial(experiment, arm, trial, expected_checksum, job_id, result, result_sha256):
    directory = trial.parent.parent.parent
    staged = directory / 'staged' / 'task'
    run_sha256 = experiment.run_sha256(arm, directory)
    verifier_env = experiment.verifier_env(arm, run_sha256)
    trial_id = uuid_string(result.get('id'), 'trial id')
    require(result.get('trial_name') == trial.name and result.get('trial_uri') == trial.as_uri(),
            'trial result does not bind its direct trial location')
    require(result.get('task_name') == experiment.task_names[arm]
            and result.get('task_id') == {'path': str(staged)}
            and result.get('task_checksum') == expected_checksum,
            'trial task identity or checksum mismatch')
    config = result.get('config')
    require(isinstance(config, dict) and config.get('trial_name') == trial.name
            and config.get('trials_dir') == str(trial.parent)
            and config.get('job_id') == job_id,
            'trial config does not bind this job and trial')
    persisted = read_object(safe_path(trial, 'config.json'), 'Harbor trial config')
    # Harbor writes config.json with defaults omitted, and result.config with defaults.
    for key in ('trial_name', 'trials_dir', 'job_id'):
        require(persisted.get(key) == config.get(key), 'retained trial config identity mismatch')
    for source in (config, persisted):
        check_local_task(source.get('task'), staged)
        check_agent_config(source.get('agent'), experiment.runtime)
        check_fresh_config(source)
        check_verifier_config(source, verifier_env)

    log = safe_path(trial, 'trial.log')
    require(not cleanup_warning(log), 'Harbor trial log reports a cleanup failure')
    require('exception_info' in result and result['exception_info'] is None,
            'trial contains a Harbor exception or lacks exception metadata')
    require(result.get('verifier_environment_mode') == 'separate' and not result.get('step_results'),
            'trial did not use the single-step separate verifier')
    agent = result.get('agent_info')
    require(isinstance(agent, dict) and agent.get('name') == experiment.runtime['agent']
            and agent.get('version') == experiment.runtime['agent_version'],
            'trial reported a mismatched agent or agent version')
    model = agent.get('model_info')
    require(isinstance(model, dict), 'trial lacks model identity')
    name = text(model.get('name'), 'trial model')
    configured = experiment.runtime['model']
    provider, separator, model_name = configured.partition('/')
    if separator:
        require(model.get('provider') == provider and name in (model_name, configured),
                'trial reported a mismatched model or provider')
    else:
        require(name == configured, 'trial reported a mismatched model')
    timestamps(result.get('started_at'), result.get('finished_at'))
    execution = result.get('agent_execution')
    require(isinstance(execution, dict), 'trial lacks agent execution timing')
    timestamps(execution.get('started_at'), execution.get('finished_at'))

    verifier = result.get('verifier_result')
    require(isinstance(verifier, dict), 'trial lacks a verifier result')
    rewards = verifier.get('rewards')
    fields(rewards, REWARDS, 'verifier rewards')
    for key, value in rewards.items():
        require(type(value) in (int, float) and value in (0, 1), f'invalid binary reward {key}')
    require(rewards['valid'] == rewards['exposure_verified'] == 1,
            'verifier did not validate trial setup and exposure')
    observation, trajectory_sha = check_observation(experiment, arm, trial, run_sha256)
    return {
        'trial_id': trial_id,
        'trajectory_sha256': trajectory_sha,
        'exposure': {
            'schema': 'experiment-exposure.v1',
            'trial_id': trial_id,
            'job_id': job_id,
            'arm': arm,
            'case_sha256': experiment.case_sha256,
            'run_sha256': run_sha256,
            'result_sha256': result_sha256,
            'observation': observation,
            'qualified_images': experiment.images[arm],
        },
        'rewards': {key: int(value) for key, value in rewards.items()},
        'started_at': result['started_at'],
        'finished_at': result['finished_at'],
        'agent_execution': {key: execution[key] for key in ('started_at', 'finished_at')},
    }


def trial_reports(experiment, arm, directory, job_sha, errors):
    staged = directory / 'staged' / 'task'
    try:
        job = safe_path(directory, f'jobs/{arm}', directory=True)
    except (OSError, ValueError):
        errors.append('Harbor job directory is missing or unsafe')
        return [], []
    if job_sha is None or tree_hash_if_available(job) != job_sha:
        errors.append('Harbor job output inventory is missing or changed')
    try:
        bindings = experiment.verifier_env(arm, experiment.run_sha256(arm, directory))
        job_id = check_job(experiment, arm, job, staged, bindings)
    except (OSError, ValueError) as exc:
        errors.append(str(exc))
        job_id = None

    # The v0.25.0 job-level result intentionally omits trial_results, including
    # at finish. Each direct trial config instead binds the completed job UUID.
    unexpected = sorted(
        path.relative_to(job).as_posix()
        for path in job.rglob('result.json')
        if len(path.relative_to(job).parts) > 2
    )
    if unexpected:
        errors.append('unexpected nested Harbor result files')
    trials = sorted(path for path in job.iterdir() if not path.is_symlink() and path.is_dir())
    if len(trials) > experiment.trials[arm]:
        errors.append('more direct trial directories than scheduled')
    checksum = harbor_checksum(experiment.inventories[arm].values())
    reports = []
    for trial in trials:
        row = {'trial_name': trial.name, 'result_path': None, 'result_sha256': None,
               'trial_id': None, 'valid': False, 'errors': []}
        reports.append(row)
        try:
            relative = f'{trial.name}/result.json'
            candidate = job / relative
            if candidate.exists() or candidate.is_symlink():
                row['result_path'] = relative
            path = safe_path(job, relative)
            data = path.read_bytes()
            row['result_sha256'] = digest(data)
            result = parse_json(data, 'Harbor trial result')
            require(isinstance(result, dict), 'Harbor trial result must be an object')
            if isinstance(result.get('id'), str):
                row['trial_id'] = result['id']
            exception = result.get('exception_info')
            if isinstance(exception, dict):
                kind = exception.get('exception_type')
                if isinstance(kind, str) and re.fullmatch(r'[A-Za-z][A-Za-z0-9_.]{0,127}', kind):
                    row['exception_type'] = kind
            require(job_id is not None, 'trial cannot be attributed to a complete Harbor job')
            row.update(check_trial(experiment, arm, trial, checksum, job_id, result,
                                   row['result_sha256']))
            row['valid'] = True
        except (OSError, ValueError) as exc:
            row['errors'].append(str(exc))
    ids = Counter(row['trial_id'] for row in reports if row['trial_id'] is not None)
    observations = Counter(row['exposure']['observation']['sha256']
                           for row in reports if 'exposure' in row)
    trajectories = Counter(row['trajectory_sha256'] for row in reports if 'exposure' in row)
    for row in reports:
        if ids[row['trial_id']] > 1:
            row['valid'] = False
            row['errors'].append('duplicate trial id')
        if 'exposure' in row:
            if observations[row['exposure']['observation']['sha256']] > 1:
                row['valid'] = False
                row['errors'].append('duplicate exposure observation')
            if trajectories[row['trajectory_sha256']] > 1:
                row['valid'] = False
                row['errors'].append('duplicate native trajectory')
    return reports, unexpected


def assess(experiment, arm, directory):
    directory = resolve_input(directory, directory=True)
    raw = safe_path(directory, 'launch.json').read_bytes()
    launch = parse_json(raw, 'launch')
    run_sha256 = experiment.run_sha256(arm, directory)
    require(isinstance(launch, dict) and launch.get('schema') == LAUNCH_SCHEMA
            and launch.get('run_dir') == str(directory) and launch.get('run_sha256') == run_sha256
            and launch.get('arm') == arm and launch.get('runtime') == experiment.runtime
            and launch.get('manifest_sha256') == experiment.manifest_sha256
            and launch.get('case_sha256') == experiment.case_sha256,
            'launch record does not bind this run, manifest, arm and runtime')
    records = list(experiment.inventories[arm].values())
    task_sha = digest(canonical(records))
    argv = array(launch.get('argv'), 'launch argv')
    executable = text(argv[0], 'recorded Harbor executable')
    require(Path(executable).is_absolute() and argv == experiment.argv(arm, directory, executable)
            and launch.get('task_sha256') == task_sha,
            'launch record does not bind the staged task and exact argv')
    baseline = launch.get('baseline_receipt')
    baseline_trajectories = set()
    errors = []
    if arm == 'baseline':
        require(baseline is None, 'baseline launch must not use a baseline receipt')
    else:
        try:
            fields(baseline, ('path', 'sha256'), 'baseline receipt reference')
            path = resolve_input(text(baseline['path'], 'baseline receipt path'))
            require(str(path) == baseline['path'], 'baseline receipt path changed')
            data = path.read_bytes()
            require(digest(data) == baseline['sha256'], 'baseline receipt hash changed')
            baseline_report = validate_baseline(experiment, data)
            baseline_trajectories = {row['trajectory_sha256'] for row in baseline_report['trials']}
        except (OSError, ValueError) as exc:
            errors.append(str(exc))
    if (launch.get('status') != 'SUCCEEDED' or launch.get('exit_code') != 0
            or type(launch.get('exit_code')) is not int
            or launch.get('cleanup') != 'harbor_completed'
            or launch.get('harbor_version') != experiment.runtime['harbor_version']):
        errors.append('launch failed, did not finish or has unverified cleanup')
    if (launch.get('staged_before') != records or launch.get('staged_after') != records
            or staged_inventory(directory) != records):
        errors.append('staged task inputs were missing or changed')
    reports, unexpected = trial_reports(experiment, arm, directory, launch.get('job_sha256'), errors)
    expected = experiment.trials[arm]
    for row in reports:
        if row.get('trajectory_sha256') in baseline_trajectories:
            row['valid'] = False
            row['errors'].append('native trajectory was reused from the baseline')
        if errors:
            row['valid'] = False
            row['errors'].append('run evidence is incomplete')
    valid = [row for row in reports if row['valid']]
    observed = sum(row['result_path'] is not None for row in reports)
    counts = {key: sum(row['rewards'][key] for row in valid)
              for key in ('incident_failure', 'task_completed', 'regression_failed')}
    if len(valid) != expected:
        status = 'INCOMPLETE'
    elif arm == 'baseline':
        status = 'REPRODUCED' if counts['incident_failure'] else 'NOT_REPRODUCED'
    else:
        fixed = (counts['task_completed'] == expected and not counts['incident_failure']
                 and not counts['regression_failed'])
        status = 'OBSERVED_FIXED' if fixed else 'NOT_OBSERVED_FIXED'
    return {
        'schema': COLLECTION_SCHEMA,
        'status': status,
        'run_dir': str(directory),
        'run_sha256': run_sha256,
        'launch_sha256': digest(raw),
        'manifest_sha256': experiment.manifest_sha256,
        'case_sha256': experiment.case_sha256,
        'incident_id': experiment.incident_id,
        'incident_kind': experiment.incident_kind,
        'arm': arm,
        'runtime': experiment.runtime,
        'task_sha256': task_sha,
        'provider_revision': 'unavailable',
        'expected_trials': expected,
        'observed_trials': observed,
        'missing_trials': max(0, expected - observed),
        'valid_trials': len(valid),
        'invalid_trials': expected - len(valid),
        'incident_failures': counts['incident_failure'],
        'task_completions': counts['task_completed'],
        'regression_failures': counts['regression_failed'],
        'trials': reports,
        'unexpected_results': unexpected,
        'run_errors': errors,
    }


def validate_baseline(experiment, raw):
    receipt = parse_json(raw, 'baseline receipt')
    require(isinstance(receipt, dict) and receipt.get('schema') == COLLECTION_SCHEMA
            and receipt.get('arm') == 'baseline' and receipt.get('status') == 'REPRODUCED'
            and receipt.get('manifest_sha256') == experiment.manifest_sha256,
            'treatment requires a REPRODUCED baseline receipt for the same manifest')
    directory = text(receipt.get('run_dir'), 'baseline run directory')
    require(Path(directory).is_absolute(), 'baseline run directory must be absolute')
    actual = assess(experiment, 'baseline', directory)
    require(actual['status'] == 'REPRODUCED' and canonical(actual) == canonical(receipt),
            'baseline receipt no longer matches reproduced trial evidence')
    return actual


def interrupt(_signum, _frame):
    raise KeyboardInterrupt


def main(argv=None):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    planning = sub.add_parser('plan')
    planning.add_argument('manifest', type=Path)
    runner = sub.add_parser('run')
    collector = sub.add_parser('collect')
    for command in (runner, collector):
        command.add_argument('manifest', type=Path)
        command.add_argument('--arm', choices=ARMS, required=True)
        command.add_argument('--output', required=True, type=Path)
    runner.add_argument('--baseline', type=Path)
    collector.add_argument('--run', required=True, type=Path)
    snap = sub.add_parser('snapshot')
    snap.add_argument('--repo', required=True)
    snap.add_argument('--commit', required=True)
    snap.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'snapshot':
            print(json.dumps(snapshot(args.repo, args.commit, args.output), sort_keys=True))
        else:
            experiment = Experiment(args.manifest)
            if args.command == 'plan':
                print(json.dumps(plan(experiment), sort_keys=True, indent=2))
            elif args.command == 'run':
                prior = signal.signal(signal.SIGTERM, interrupt)
                try:
                    launch = run(experiment, args.arm, args.output, args.baseline)
                finally:
                    signal.signal(signal.SIGTERM, prior)
                print(json.dumps({'status': launch['status'], 'run_dir': launch['run_dir']}))
                return int(launch['status'] != 'SUCCEEDED')
            else:
                result = assess(experiment, args.arm, args.run)
                output = new_output(experiment, args.output, outside=(Path(result['run_dir']),))
                write_json(output, result)
                print(json.dumps(result, sort_keys=True, indent=2))
                return int(result['status'] == 'INCOMPLETE')
    except KeyboardInterrupt:
        print('error: interrupted', file=sys.stderr)
        return 1
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
