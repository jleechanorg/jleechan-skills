#!/usr/bin/env python3
"""Validate, run and collect control-first Harbor skill experiments."""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tomllib


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode('utf-8')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def inventory(root):
    records = []
    for path in sorted(root.rglob('*'), key=lambda path: path.relative_to(root).as_posix()):
        if path.is_symlink():
            raise ValueError('symlinks are unsupported')
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError('non-regular files are unsupported')
        records.append({'path': path.relative_to(root).as_posix(), 'sha256': file_digest(path),
                        'executable': bool(path.stat().st_mode & 0o111)})
    return records


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
NATIVE_INSTRUCTIONS = {'AGENTS.md', 'AGENTS.override.md', 'CLAUDE.md', 'SKILL.md'}


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
        and not re.match(r'^[A-Za-z]:', path),
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


def verify_tree(root, ref, label):
    fields(ref, ('path', 'sha256'), label)
    matches(ref['sha256'], r'[0-9a-f]{64}', f'{label} sha256')
    tree = safe_path(root, ref['path'], directory=True)
    files = inventory(tree)
    require(digest(canonical(files)) == ref['sha256'], f'{label} tree hash mismatch')
    return tree, {entry['path']: entry for entry in files}


def validate_task(tree, files, label):
    required = {'instruction.md', 'task.toml', 'environment/Dockerfile', 'tests/test.sh'}
    require(required <= files.keys(), f'{label} missing required task files')
    # Directory-only changes affect build contexts but have no inventory entry.
    parents = {parent.as_posix() for name in files for parent in Path(name).parents}
    for path in tree.rglob('*'):
        if path.is_dir():
            require(path.relative_to(tree).as_posix() in parents, f'{label} has an empty directory')
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
            self.tasks[arm], self.inventories[arm] = verify_tree(self.root, m[f'{arm}_task'], arm)
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
            require(path.startswith('environment/') and Path(path).name in NATIVE_INSTRUCTIONS,
                    f'intervention must name a native instruction file: {path!r}')
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

    def argv(self, arm, directory, executable='harbor'):
        root = Path(directory)
        runtime = self.runtime
        return [
            executable, 'run', '-p', str(root / 'staged' / 'task'), '-a', runtime['agent'],
            '-m', runtime['model'], '--agent-kwarg', 'version=' + runtime['agent_version'],
            '--effort', runtime['effort'], '--jobs-dir', str(root / 'jobs'), '--job-name', arm,
            '--n-attempts', str(self.trials[arm]), '--n-concurrent', str(runtime['concurrency']),
        ]


def plan(experiment):
    return {
        'case_sha256': experiment.case_sha256,
        'manifest_sha256': experiment.manifest_sha256,
        'baseline_argv': experiment.argv('baseline', '<NEW_RUN_DIR>'),
        'treatment_argv': experiment.argv('treatment', '<NEW_RUN_DIR>'),
        'treatment_gate': 'requires a matching REPRODUCED baseline receipt',
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    planning = sub.add_parser('plan')
    planning.add_argument('manifest', type=Path)
    snap = sub.add_parser('snapshot')
    snap.add_argument('--repo', required=True)
    snap.add_argument('--commit', required=True)
    snap.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'snapshot':
            print(json.dumps(snapshot(args.repo, args.commit, args.output), sort_keys=True))
        else:
            print(json.dumps(plan(Experiment(args.manifest)), sort_keys=True, indent=2))
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
