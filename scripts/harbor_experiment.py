#!/usr/bin/env python3
"""Validate, run and collect control-first Harbor skill experiments."""

import argparse
from collections import Counter, defaultdict
import ctypes
from datetime import datetime
import hashlib
from http.client import HTTPConnection, HTTPException
import json
import math
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
import tomllib
import types
from urllib.parse import urlencode
from uuid import UUID, uuid4


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode('utf-8')


def checked_script_sources(scripts, approved_hashes):
    sources = [(script, script.read_bytes()) for script in scripts]
    require(all(digest(data) in approved_hashes for _, data in sources),
            'reviewed code bundle must contain the executing adapter bytes')
    return sources


def load_reviewed_helpers(sources):
    loaded = {}
    for path, data in sources:
        module = types.ModuleType(path.stem)
        module.__file__ = str(path)
        exec(compile(data, str(path), 'exec', dont_inherit=True), module.__dict__)
        loaded[path.stem] = module
    sys.modules.update(loaded)


CODEX_IMAGE_EXECUTABLES = ('/usr/local/bin/codex', '/opt/harbor-codex/codex-real')
ACCESS_PRIVATE_ROOT = Path('/dev/shm')
SIDECAR_TAG_SCRIPT = '''
import asyncio
from harbor.environments.docker import EGRESS_CONTROL_SIDECAR_CONTEXT_PATH as context
from harbor.environments.docker.docker import DockerEnvironment
from harbor.environments.docker.utils import _compute_image_name, default_docker_platform, docker_build_context_hash
print(_compute_image_name(DockerEnvironment._EGRESS_CONTROL_SIDECAR_DOCKER_NAME,
    docker_build_context_hash(context=context, dockerfile_path=context / "Dockerfile",
                              build_args={}, platform=asyncio.run(default_docker_platform()))))
'''


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def walk_tree(root):
    stack = [iter(root.iterdir())]
    while stack:
        path = next(stack[-1], None)
        if path is None:
            stack.pop()
            continue
        info = path.lstat()
        yield path, info
        if stat.S_ISDIR(info.st_mode):
            stack.append(iter(path.iterdir()))


def inventory(root, *, allow_empty_dirs=True):
    records = []
    directories = set()
    file_parents = set()
    for path, info in walk_tree(root):
        require(not stat.S_ISLNK(info.st_mode), 'symlinks are unsupported')
        relative = path.relative_to(root)
        relative_parts(relative.as_posix())
        if stat.S_ISDIR(info.st_mode):
            directories.add(relative)
            continue
        require(stat.S_ISREG(info.st_mode), 'non-regular files are unsupported')
        records.append({'path': relative.as_posix(), 'sha256': file_digest(path),
                        'executable': bool(info.st_mode & 0o111)})
        file_parents.update(relative.parents)
    require(allow_empty_dirs or directories <= file_parents, 'task tree has an empty directory')
    return sorted(records, key=lambda record: record['path'])


def git(repo, *args):
    return subprocess.run(['git', '-C', str(repo), '--no-replace-objects', *args], check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout


def selector(value):
    text(value, 'source selector')
    relative_parts(value.removesuffix('/'))
    return value


def git_blob_oid(data):
    return git_object_oid('blob', data)


def git_object_oid(kind, data):
    return hashlib.sha1(f'{kind} {len(data)}\0'.encode('ascii') + data).hexdigest()


def committed_inventory(commit, tree, commit_hex, catalog):
    raw_commit = bytes.fromhex(text(commit_hex, 'commit object'))
    require(git_object_oid('commit', raw_commit) == commit
            and raw_commit.partition(b'\n')[0] == f'tree {tree}'.encode('ascii'),
            'selected source commit does not bind the tree')
    nodes = defaultdict(list)
    directories = {'.': tree}
    tracked, seen = {}, set()
    for entry in array(catalog, 'committed tree catalog'):
        fields(entry, ('path', 'git_mode', 'git_oid'), 'committed tree entry')
        path, mode, oid = entry['path'], entry['git_mode'], entry['git_oid']
        parts = relative_parts(path)
        require(path not in seen and '.git' not in parts, 'invalid committed path')
        seen.add(path)
        require(mode in ('040000', '100644', '100755', '120000', '160000'), 'unsupported committed mode')
        matches(oid, r'[0-9a-f]{40}', 'committed object identity')
        parent = '/'.join(parts[:-1]) or '.'
        name = parts[-1].encode('utf-8')
        nodes[parent].append((name + (b'/' if mode == '040000' else b''),
                              mode.lstrip('0').encode('ascii') + b' ' + name + b'\0' + bytes.fromhex(oid)))
        if mode == '040000':
            directories[path] = oid
        else:
            tracked[path] = entry
    require(nodes.keys() <= directories.keys(), 'committed file is missing its parent tree')
    for path, oid in directories.items():
        require(git_object_oid('tree', b''.join(data for _, data in sorted(nodes[path]))) == oid,
                'committed catalog does not reproduce the Git tree')
    return tracked


def select_source(selection, tree, tracked):
    fields(selection, ('tree', 'include', 'exclude'), 'source selection')
    require(selection['tree'] == tree, 'source selection tree mismatch')
    includes = [selector(path) for path in array(selection['include'], 'included paths')]
    excludes = {}
    for entry in array(selection['exclude'], 'excluded paths', nonempty=False):
        fields(entry, ('path', 'reason'), 'source exclusion')
        path = selector(entry['path'])
        require(path not in excludes, 'duplicate source exclusion')
        excludes[path] = text(entry['reason'], 'reason for source exclusion')
    declared = includes + list(excludes)
    require(len(declared) == len(set(declared)), 'duplicate source selector')
    by_path = set(declared)
    consumed = set()
    selected = set()
    for path in tracked:
        matches = ({path} & by_path) | {
            f'{ancestor.as_posix()}/' for ancestor in Path(path).parents
            if f'{ancestor.as_posix()}/' in by_path
        }
        require(len(matches) == 1, f'source selection does not cover exactly once: {path!r}')
        picked = next(iter(matches))
        consumed.add(picked)
        if picked not in excludes:
            selected.add(path)
    require(consumed == by_path and selected, 'source selection does not resolve all selectors')
    return selected


def snapshot(repo, commit, output, selection=None):
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('commit must be a full lowercase SHA-1')
    if git(repo, 'rev-parse', '--verify', commit + '^{commit}').decode().strip() != commit:
        raise ValueError('commit must identify a commit object')
    output = Path(output)
    root = Path(git(repo, 'rev-parse', '--show-toplevel').decode().strip()).resolve()
    if output.resolve().is_relative_to(root):
        raise ValueError('snapshot destination must be outside the source worktree')
    require_outside_retained_runs(output.resolve())
    receipt = output.with_name(output.name + '.receipt.json')
    if output.exists() or output.is_symlink() or receipt.exists() or receipt.is_symlink():
        raise ValueError('snapshot destination or receipt already exists')
    raw = git(repo, 'ls-tree', '-rtz' if selection is not None else '-rz', '--full-tree', commit)
    tracked, catalog = {}, []
    for item in raw.split(b'\0'):
        if not item:
            continue
        meta, name = item.split(b'\t', 1)
        mode, kind, oid = meta.split(b' ')
        relative = name.decode('utf-8')
        parts = relative.split('/')
        if any(p in ('', '.', '..', '.git') for p in parts):
            raise ValueError('unsafe Git tree path')
        mode, oid = mode.decode('ascii'), oid.decode('ascii')
        if selection is not None:
            catalog.append({'path': relative, 'git_mode': mode, 'git_oid': oid})
        if kind != b'tree':
            tracked[relative] = (mode, kind, oid)
    tree = git(repo, 'rev-parse', commit + '^{tree}').decode().strip()
    if selection is not None:
        commit_object = git(repo, 'cat-file', 'commit', commit).hex()
        require(committed_inventory(commit, tree, commit_object, catalog).keys() == tracked.keys(),
                'committed catalog does not match source paths')
    chosen = tracked if selection is None else select_source(selection, tree, tracked)
    entries = []
    for relative in sorted(chosen):
        mode, kind, oid = tracked[relative]
        require(mode in ('100644', '100755') and kind == b'blob', 'unsupported Git object or mode')
        data = git(repo, 'cat-file', 'blob', oid)
        require(git_blob_oid(data) == oid, 'source blob content does not match its Git identity')
        if data.startswith(b'version https://git-lfs.github.com/spec/v1\n'):
            raise ValueError('Git LFS pointers are unsupported')
        entries.append((relative, mode, oid, data))
    output.mkdir()
    try:
        for relative, mode, _, data in entries:
            path = output / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            path.chmod(0o755 if mode == '100755' else 0o644)
        records = inventory(output)
        body = {'schema': 'experiment-snapshot.v1', 'repository_commit': commit,
                'inventory': records, 'sha256': digest(canonical(records))}
        if selection is not None:
            body.update(schema='experiment-selected-snapshot.v2', repository_tree=tree,
                        commit_object=commit_object, catalog=catalog,
                        selected=[{'path': path, 'git_mode': mode, 'git_oid': oid}
                                  for path, mode, oid, _ in entries],
                        excluded=selection['exclude'])
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
ACCESS_MODE = 'codex_access_only'
ACCESS_AGENT_CONFIG = {'cli_auth_credentials_store': 'file'}
ACCESS_PYTHON_FLAGS = ('-I', '-B', '-X', 'pycache_prefix=/dev/null')
ACCESS_HEALTHCHECK = {'command': '/usr/local/bin/codex --harbor-check-denied', 'retries': 1}
ACCESS_CAPTURES = ('stdout.log', 'stderr.log', 'version.stdout.log', 'version.stderr.log')
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


def check_launch_policy(root, reference, incident_id, runtime, trials):
    policy = record(root, reference, 'campaign launch policy', 'experiment-launch-policy.v1', ('cases',))
    cases = policy['cases']
    expected = {'arm': 'baseline', 'runtime': runtime, 'trials': trials}
    require(isinstance(cases, dict) and incident_id in cases
            and canonical(cases[incident_id]) == canonical(expected),
            'requested launch does not match frozen campaign policy')


def verify_tree(root, ref, label, *, allow_empty_dirs=True):
    fields(ref, ('path', 'sha256'), label)
    matches(ref['sha256'], r'[0-9a-f]{64}', f'{label} sha256')
    tree = safe_path(root, ref['path'], directory=True)
    files = inventory(tree, allow_empty_dirs=allow_empty_dirs)
    require(digest(canonical(files)) == ref['sha256'], f'{label} tree hash mismatch')
    return tree, {entry['path']: entry for entry in files}


def verify_snapshot(root, manifest):
    reference = manifest['snapshot']
    if not isinstance(reference, dict) or 'selection_receipt' not in reference:
        return verify_tree(root, reference, 'snapshot')[0]
    fields(reference, ('path', 'sha256', 'selection_receipt'), 'selected snapshot')
    require(manifest['incident_kind'] == 'constructed', 'selected source requires a constructed case')
    tree, files = verify_tree(root, {key: reference[key] for key in ('path', 'sha256')}, 'snapshot')
    receipt = record(root, reference['selection_receipt'], 'selected source receipt',
                     'experiment-selected-snapshot.v2', ('repository_commit', 'repository_tree',
                     'inventory', 'sha256', 'selected', 'excluded', 'commit_object', 'catalog'))
    require(receipt['repository_commit'] == manifest['repository_commit']
            and receipt['sha256'] == reference['sha256']
            and receipt['inventory'] == list(files.values()), 'selected snapshot does not match receipt')
    matches(receipt['repository_tree'], r'[0-9a-f]{40}', 'selected source tree')
    tracked = committed_inventory(receipt['repository_commit'], receipt['repository_tree'],
                                  receipt['commit_object'], receipt['catalog'])
    observed = set()
    for entry in array(receipt['selected'], 'selected source entries'):
        fields(entry, ('path', 'git_mode', 'git_oid'), 'selected source entry')
        path = text(entry['path'], 'selected path')
        require(path in files and path not in observed and tracked.get(path) == entry,
                'selected source paths do not match the snapshot or committed tree')
        observed.add(path)
        data = safe_path(tree, path).read_bytes()
        require(entry['git_mode'] == ('100755' if files[path]['executable'] else '100644')
                and entry['git_oid'] == git_blob_oid(data),
                'selected source entry mode or Git object identity does not match')
        require(not data.startswith(b'version https://git-lfs.github.com/spec/v1\n'),
                'Git LFS pointers are unsupported')
    require(observed == files.keys(), 'selected receipt does not cover the snapshot')
    require(select_source({'tree': receipt['repository_tree'], 'include': sorted(observed),
                           'exclude': receipt['excluded']}, receipt['repository_tree'], tracked) == observed,
            'selection does not cover the committed tree')
    return tree


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
    return None


class Experiment:
    def __init__(self, path):
        path = Path(path)
        require(not path.is_symlink() and path.is_file(), 'manifest must be a regular file')
        self.path = path.resolve()
        self.root = self.path.parent
        raw = self.path.read_bytes()
        self.manifest_sha256 = digest(raw)
        m = parse_json(raw, 'manifest')
        access_only = isinstance(m, dict) and isinstance(m.get('runtime'), dict) and m['runtime'].get('auth_mode') == ACCESS_MODE
        case_fields = (*CASE_FIELDS, 'launch_policy') if access_only else CASE_FIELDS
        fields(m, (*case_fields, 'design_files', 'code_files', 'reviews',
                   'packaging', 'qualification'), 'manifest')
        require(m['schema'] == 'harbor-skill-experiment.v1', 'invalid manifest schema')
        text(m['incident_id'], 'incident_id')
        text(m['incident_source'], 'incident_source')
        require(m['incident_kind'] in ('captured', 'constructed'), 'invalid incident_kind')
        matches(m['repository_commit'], r'[0-9a-f]{40}', 'repository_commit')
        self.incident_kind = m['incident_kind']
        self.incident_id = m['incident_id']
        if access_only:
            require(isinstance(m['snapshot'], dict) and 'selection_receipt' in m['snapshot'],
                    'access-only snapshot requires committed-object provenance')
        self.snapshot = verify_snapshot(self.root, m)
        self.tasks = {}
        self.inventories = {}
        self.task_names = {}
        for arm in ARMS:
            self.tasks[arm], self.inventories[arm] = verify_tree(
                self.root, m[f'{arm}_task'], arm, allow_empty_dirs=False,
            )
            self.task_names[arm] = validate_task(self.tasks[arm], self.inventories[arm], arm)
        self.check_intervention(m['intervention_paths'])
        runtime_keys = (*RUNTIME_FIELDS, 'auth_mode') if isinstance(m['runtime'], dict) and 'auth_mode' in m['runtime'] else RUNTIME_FIELDS
        fields(m['runtime'], runtime_keys, 'runtime')
        self.runtime = m['runtime']
        require(self.runtime['harbor_version'] == '0.25.0' and self.runtime['agent'] == 'codex',
                'runtime must use Harbor 0.25.0 and codex')
        if 'auth_mode' in self.runtime:
            require(self.runtime['auth_mode'] == ACCESS_MODE and self.runtime['agent_version'] == '0.172.0'
                    and self.incident_kind == 'constructed', 'unsupported access-only runtime')
            require(PRIVATE_DETECTOR in self.inventories['baseline'], 'access-only baseline lacks its frozen detector')
            require(self.intervention_paths == ['environment/workspace/AGENTS.md'],
                    'access-only native exposure currently requires the workspace AGENTS.md control')
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
        if access_only:
            check_launch_policy(self.root, m['launch_policy'], self.incident_id, self.runtime, self.trials['baseline'])
        self.check_provenance(m)
        self.case_sha256 = digest(canonical({key: m[key] for key in case_fields}))
        coordinator = self.check_packaging(m['packaging'])
        code_bundle = self.check_reviews(m, coordinator)
        self.images = self.check_qualification(m['qualification'], code_bundle)

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

    def check_qualification(self, ref, code_bundle):
        local = self.runtime.get('auth_mode') == ACCESS_MODE
        info = record(self.root, ref, 'qualification', 'experiment-qualification.v1',
                      ('verdict', 'case_sha256', 'images', 'checks')
                      + (('docker_server_id', 'docker_client_sha256', 'egress_image_id', 'codex_binary_sha256',
                          'code_bundle_sha256', 'harbor_install_sha256') if local else ()))
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
        if local:
            require(info['code_bundle_sha256'] == code_bundle, 'access-only qualification does not bind approved code')
            self.docker_server_id = matches(info['docker_server_id'], r'[A-Za-z0-9:._-]+', 'Docker server identity')
            self.harbor_install_sha256 = matches(info['harbor_install_sha256'], r'[0-9a-f]{64}', 'Harbor installation identity')
            self.docker_client_sha256 = matches(info['docker_client_sha256'], r'[0-9a-f]{64}', 'Docker and Compose identity')
            self.egress_image_id = matches(info['egress_image_id'], r'sha256:[0-9a-f]{64}', 'egress sidecar image identity')
            self.codex_binary_sha256 = matches(info['codex_binary_sha256'], r'[0-9a-f]{64}', 'qualified Codex bytes')
        return info['images']

    def check_reviews(self, manifest, coordinator):
        phases = ('design', 'code')
        bundles = {}
        for phase in phases:
            refs = verify_refs(self.root, manifest[f'{phase}_files'], f'{phase} files')
            if phase == 'code':
                scripts = [Path(__file__).resolve()]
                if self.runtime.get('auth_mode') == ACCESS_MODE:
                    scripts.extend(scripts[0].with_name(name) for name in
                                   ('harbor_codex_access.py', 'harbor_codex_completion.py', 'harbor_codex_egress.py'))
                reviewed_sources = checked_script_sources(scripts, {ref['sha256'] for ref in refs})
                if self.runtime.get('auth_mode') == ACCESS_MODE:
                    require(manifest.get('launch_policy') in refs,
                            'reviewed code bundle must contain the exact campaign launch policy reference')
            bundles[phase] = digest(canonical(refs))
        seats = {phase: set() for phase in phases}
        outputs = {phase: set() for phase in phases}
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
            output_hash = info['output']['sha256']
            require(output_hash not in outputs[phase], f'duplicate {phase} reviewer output')
            lines = output.read_text(encoding='utf-8').rstrip('\r\n').splitlines()
            terminal = f'VERDICT: APPROVED at DOCUMENTS sha256:{bundles[phase]}'
            require(lines and lines[-1] == terminal, f'{phase} review lacks the exact terminal approval')
            seats[phase].add(reviewer)
            outputs[phase].add(output_hash)
        for phase in phases:
            require(len(seats[phase]) >= 2, f'{phase} requires two independent reviewers')
        load_reviewed_helpers(reviewed_sources[1:])
        return bundles['code']

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

    def argv(self, arm, directory, executable='harbor', *, run_sha256=None, command_prefix=()):
        root = Path(directory)
        runtime = self.runtime
        if run_sha256 is None:
            run_sha256 = self.run_sha256(arm, root)
        argv = [
            *command_prefix, executable, 'run', '-p', str(root / 'staged' / staged_name(self, root)), '-a', runtime['agent'],
            '-m', runtime['model'], '--agent-kwarg', 'version=' + runtime['agent_version'],
            '--effort', runtime['effort'], '--jobs-dir', str(root / 'jobs'), '--job-name', arm,
            '--n-attempts', str(self.trials[arm]), '--n-concurrent', str(runtime['concurrency']),
        ]
        if runtime.get('auth_mode') == ACCESS_MODE:
            from harbor_codex_egress import PLUGIN, plugin_cli_args

            argv.extend(('--env', 'docker', '--no-force-build', '--allow-agent-host', 'chatgpt.com', '--agent-kwarg',
                         'config_source=' + canonical(ACCESS_AGENT_CONFIG).decode()))
            argv.extend(plugin_cli_args(PLUGIN, egress_image=self.egress_image_id,
                agent_image=self.images[arm]['agent_image_digest'], run_sha256=run_sha256,
                scope=staged_name(self, root) + '__'))
        for key, value in self.verifier_env(arm, run_sha256).items():
            argv.extend(('--verifier-env', f'{key}={value}'))
        return argv


def plan(experiment):
    result = {
        'case_sha256': experiment.case_sha256,
        'manifest_sha256': experiment.manifest_sha256,
        'baseline_argv': experiment.argv('baseline', '<NEW_RUN_DIR>', run_sha256='<RUN_SHA256>'),
        'treatment_argv': experiment.argv('treatment', '<NEW_RUN_DIR>', run_sha256='<RUN_SHA256>'),
        'treatment_gate': 'requires a matching REPRODUCED baseline receipt',
    }
    if experiment.runtime.get('auth_mode') == ACCESS_MODE:
        result.update(treatment_argv=None, treatment_gate='reserved; not runnable in access-only mode')
    return result


LAUNCH_SCHEMA = 'experiment-launch.v1'
COLLECTION_SCHEMA = 'experiment-collection.v1'
OBSERVATION_PATH = 'verifier/exposure-observation.json'
CLEANUP_WARNINGS = (b'Docker compose down failed:', b'Docker compose stop failed:',
                    b'Cleanup interrupted for ', b'Warning: Agent environment cleanup failed for ')
REWARDS = ('valid', 'incident_failure', 'exposure_verified', 'task_completed', 'regression_failed')
SEMANTIC_METRICS = ('incident_failure', 'task_completed', 'regression_failed')
PRIVATE_DETECTOR = 'tests/detector.md'
FIXTURE_EVIDENCE = 'artifacts/approved/fixture-events.tsv'
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
    require(not path.exists() and not path.is_symlink(), 'output already exists')
    path = path.resolve()
    frozen = (experiment.snapshot, *experiment.tasks.values(), *outside)
    require(not any(path.is_relative_to(tree) for tree in frozen),
            'output must be outside frozen task, snapshot and run directories')
    require_outside_retained_runs(path)
    return path


def require_outside_retained_runs(path):
    for directory in path.parents:
        marker = directory / 'launch.json'
        if marker.is_symlink() or not marker.is_file():
            continue
        try:
            launch = read_object(marker, 'Harbor launch marker')
        except (OSError, ValueError):
            continue
        require(not (launch.get('schema') in (LAUNCH_SCHEMA, 'experiment-access-failure.v1')
                     and str(directory) in (launch.get('run_dir'), launch.get('retained_root'))),
                'output must be outside retained Harbor run directories')


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


def invoke(argv, *, cwd, env, stdout, stderr, timeout, sealed=False):
    if sealed:
        return invoke_drained(argv, cwd, env, stdout, stderr, timeout)
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


def invoke_drained(argv, cwd, env, stdout, stderr, timeout):
    require(sys.platform == 'linux' and threading.get_native_id() == os.getpid(),
            'sealed acquisition requires Linux main-thread child accounting')
    prctl = ctypes.CDLL(None, use_errno=True).prctl
    previous = ctypes.c_int()
    require(prctl(37, ctypes.byref(previous), 0, 0, 0) == 0 and prctl(36, 1, 0, 0, 0) == 0,
            'sealed acquisition could not enable child accounting')
    try:
        return capture_drained(argv, cwd, env, stdout, stderr, timeout)
    finally:
        require(prctl(36, previous.value, 0, 0, 0) == 0, 'could not restore child accounting')


def descendants_drained(deadline, *, terminate=False):
    children = Path(f'/proc/self/task/{os.getpid()}/children')
    not_other_threads = 0x20000000
    while True:
        try:
            child, _ = os.waitpid(-1, os.WNOHANG | not_other_threads)
        except ChildProcessError:
            return True
        if time.monotonic() >= deadline:
            return False
        if child == 0:
            if terminate:
                for identity in children.read_text().split():
                    try:
                        descriptor = os.pidfd_open(int(identity))
                        try:
                            if identity in children.read_text().split():
                                signal.pidfd_send_signal(descriptor, signal.SIGKILL)
                        finally:
                            os.close(descriptor)
                    except ProcessLookupError:
                        pass
            time.sleep(min(0.025, max(0, deadline - time.monotonic())))


def capture_drained(argv, cwd, env, stdout, stderr, timeout):
    from harbor_codex_access import MAX_ARTIFACT_BYTES

    try:
        process = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    except OSError:
        return 'START_FAILED', None
    with process.stdout, process.stderr, selectors.DefaultSelector() as streams:
        deadline = time.monotonic() + timeout
        capture_valid = True

        def drain(until):
            while streams.get_map() and time.monotonic() < until:
                for key, _ in streams.select(max(0, until - time.monotonic())):
                    chunk = os.read(key.fd, 65536)
                    if not chunk:
                        key.data.flush()
                        streams.unregister(key.fileobj)
                    elif capture_valid:
                        require(key.data.tell() + len(chunk) <= MAX_ARTIFACT_BYTES, 'capture exceeds limit')
                        key.data.write(chunk)
            return not streams.get_map()

        failure = None
        registered = False
        try:
            streams.register(process.stdout, selectors.EVENT_READ, stdout)
            streams.register(process.stderr, selectors.EVENT_READ, stderr)
            registered = True
            if not drain(deadline):
                raise subprocess.TimeoutExpired(argv, timeout)
            code = process.wait(timeout=max(0, deadline - time.monotonic()))
            if not process_group_alive(process.pid) and descendants_drained(deadline):
                return ('SUCCEEDED' if code == 0 else 'FAILED'), code
            failure = 'ORPHANED' if time.monotonic() < deadline else 'TIMED_OUT'
        except subprocess.TimeoutExpired:
            failure = 'TIMED_OUT'
        except KeyboardInterrupt:
            failure = 'INTERRUPTED'
        except (OSError, ValueError):
            capture_valid = False
            failure = 'CAPTURE_INVALID'
        stop_process_group(process)
        try:
            cleanup_deadline = time.monotonic() + 1
            if (process.poll() is not None and not process_group_alive(process.pid)
                    and descendants_drained(cleanup_deadline, terminate=True) and registered
                    and drain(cleanup_deadline)):
                return failure, process.returncode
        except (KeyboardInterrupt, OSError, ValueError):
            pass
        return 'UNSEALED', process.returncode


def access_bytes(path):
    from harbor_codex_access import read_artifact

    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as stream:
        return read_artifact(stream.fileno())


def access_job_inventory(root, *, isolate_trials=False, max_trials=None):
    records, total = [], 0
    if not root.is_dir() or root.is_symlink():
        return None
    try:
        def record(path, info):
            entry = {'path': path.relative_to(root).as_posix(), 'mode': stat.S_IMODE(info.st_mode)}
            if stat.S_ISDIR(info.st_mode):
                return {**entry, 'kind': 'directory'}, 0
            data = access_bytes(path)
            return {**entry, 'kind': 'file', 'sha256': digest(data)}, len(data)

        withheld = set()
        children = sorted(root.iterdir())
        if max_trials is not None:
            require(sum(stat.S_ISDIR(child.lstat().st_mode) for child in children) <= max_trials,
                    'raw job has more trial directories than scheduled')
        for child in children:
            info = child.lstat()
            first, local_bytes = record(child, info)
            local = [first]
            if stat.S_ISDIR(info.st_mode):
                try:
                    for path, node in walk_tree(child):
                        require(len(local) < (2048 if isolate_trials else 8192), 'raw trial exceeds entry limit')
                        entry, size = record(path, node)
                        local_bytes += size
                        require(local_bytes <= (128 if isolate_trials else 512) * 1024 * 1024,
                                'raw trial exceeds size limit')
                        local.append(entry)
                except (OSError, ValueError):
                    if not isolate_trials:
                        raise
                    withheld.add(child.name)
                    local, local_bytes = ([{**first, 'kind': 'unsealable_trial'}], 0)
            if not (isolate_trials and stat.S_ISDIR(info.st_mode)):
                total += local_bytes
                require(total <= 512 * 1024 * 1024 and (isolate_trials or len(records) + len(local) <= 8192),
                        'raw job exceeds aggregate limit')
            records.extend(local)
        return digest(canonical(sorted(records, key=lambda item: item['path']))), withheld
    except (OSError, ValueError):
        return None


def access_job_hash(root):
    result = access_job_inventory(root)
    return result[0] if result is not None else None


def access_capture_hashes(root):
    return {name: digest(access_bytes(root / name)) for name in ACCESS_CAPTURES
            if (root / name).exists() or (root / name).is_symlink()}


def tree_hash_if_available(root):
    if not root.is_dir() or root.is_symlink():
        return None
    try:
        return digest(canonical(inventory(root)))
    except (OSError, ValueError):
        return None


def staged_name(experiment, directory):
    if experiment.runtime.get('auth_mode') == ACCESS_MODE:
        return 'codex-' + digest(canonical([experiment.case_sha256, str(directory)]))[:24]
    return 'task'


def staged_inventory(directory, name='task'):
    staged = directory / 'staged'
    if staged.is_symlink() or (staged / name).is_symlink():
        return None
    try:
        return inventory(safe_path(directory, f'staged/{name}', directory=True), allow_empty_dirs=False)
    except (OSError, ValueError):
        return None


def cleanup_warning(path):
    with path.open('rb') as stream:
        return any(marker in line for line in stream for marker in CLEANUP_WARNINGS)


def access_docker_env(home):
    env = {key: os.environ[key] for key in PROCESS_ENV if key in os.environ and key not in {'DOCKER_HOST', 'PATH'}}
    return {**env, 'HOME': str(home), 'PATH': os.defpath, 'DOCKER_HOST': 'unix:///var/run/docker.sock'}


def access_harbor_command(launcher):
    launcher = Path(launcher).resolve(strict=True)
    return [str(launcher.parent / 'python'), *ACCESS_PYTHON_FLAGS, str(launcher)]


def access_harbor_identity(launcher):
    launcher = Path(launcher).resolve(strict=True)
    require(launcher.name == 'harbor' and launcher.parent.name == 'bin' and launcher.is_file()
            and os.access(launcher, os.X_OK), 'Harbor launcher is not a virtualenv executable')
    root = launcher.parent.parent
    config = safe_path(root, 'pyvenv.cfg')
    config_bytes = config.read_bytes()
    require(re.findall(rb'^\s*include-system-site-packages\s*=\s*(\S+)\s*$', config_bytes, re.M) == [b'false'],
            'Harbor virtualenv must not inherit system packages')
    packages = list((root / 'lib').glob('python*/site-packages'))
    require(len(packages) == 1, 'Harbor package directory is ambiguous')
    site = safe_path(root, packages[0].relative_to(root).as_posix(), directory=True)
    safe_path(site, 'harbor/__init__.py')
    command = access_harbor_command(launcher)
    interpreter = Path(command[0]).resolve(strict=True)
    require(interpreter.is_file() and os.access(interpreter, os.X_OK), 'invalid Harbor interpreter')
    return digest(canonical({'command': command, 'launcher_sha256': file_digest(launcher),
                             'interpreter': str(interpreter), 'interpreter_sha256': file_digest(interpreter),
                             'config_sha256': digest(config_bytes), 'packages': inventory(site)}))


def qualified_harbor_install(experiment, executable):
    import harbor_codex_egress

    require(executable is not None and access_harbor_identity(executable) == experiment.harbor_install_sha256,
            'Harbor installation differs from qualification')
    site = list((Path(executable).resolve().parent.parent / 'lib').glob('python*/site-packages'))
    require(len(site) == 1 and file_digest(safe_path(site[0], 'harbor_codex_egress.py'))
            == file_digest(Path(harbor_codex_egress.__file__)), 'installed inference guard differs from approved adapter')


def docker_quiescent(prefix, env, *, query=None):
    if query is None:
        query = lambda *args: docker_query(env, *args)
    try:
        commands = (('ps', '-a', '{{.Names}}'), ('network', 'ls', '{{.Name}}'), ('volume', 'ls', '{{.Name}}'))
        return all(not any(name.lstrip('/').startswith(prefix) for name in
                           query(*command[:-1], '--format', command[-1]).splitlines())
                   for command in commands)
    except (OSError, subprocess.SubprocessError):
        return False


def docker_query(env, *argv, timeout=10):
    return subprocess.run(docker_command(env, *argv), env=env, capture_output=True, timeout=timeout,
                          check=True, text=True).stdout.strip()


def docker_command(env, *argv):
    executable = shutil.which('docker', path=env['PATH'])
    require(executable is not None, 'Docker is unavailable in the isolated runtime PATH')
    return [executable, *argv]


def docker_mounts_clear(query, acquisition, forbidden=()):
    containers = query('ps', '-aq', '--no-trunc').splitlines()
    if len(containers) > 256 or any(identity in forbidden for identity in containers):
        return False
    for offset in range(0, len(containers), 32):
        identities = containers[offset:offset+32]
        inspected = query('inspect', '--type', 'container', '--format', '{{json .Mounts}}', *identities).splitlines()
        require(len(inspected) == len(identities), 'incomplete live Docker mount inventory')
        for row in inspected:
            for mount in json.loads(row) or []:
                source = Path(mount['Source'])
                if source.is_absolute():
                    source = source.resolve()
                    if source.is_relative_to(acquisition) or acquisition.is_relative_to(source):
                        return False
    return True


def cleanup_remaining(deadline, limit=10):
    remaining = deadline - time.monotonic()
    require(remaining > 0, 'access-only cleanup budget exhausted')
    return min(limit, remaining)


def reconcile_access_docker(prefix, env, acquisition, daemon, *, deadline=None):
    from harbor_codex_access import CLEANUP_SECONDS

    if deadline is None:
        deadline = time.monotonic() + CLEANUP_SECONDS
    label = 'com.docker.compose.project'
    project = re.compile(re.escape(prefix) + r'[a-z0-9_-]+?__(?:env|verifier__[a-z0-9_-]+)')

    def query(*argv):
        return docker_query(env, *argv, timeout=cleanup_remaining(deadline))

    scopes = (('container', ('ps', '-aq', '--no-trunc'), ('ps', '-a'), '{{.Names}}', ('rm', '-f'), '.Config.Labels'),
              ('network', ('network', 'ls', '-q', '--no-trunc'), ('network', 'ls'), '{{.Name}}', ('network', 'rm'), '.Labels'),
              ('volume', ('volume', 'ls', '-q'), ('volume', 'ls'), '{{.Name}}', ('volume', 'rm'), '.Labels'))

    def owned(kind, listing, label_field):
        identities = query(*listing, '--filter', 'label=' + label).splitlines()
        require(len(identities) <= 256 and len(set(identities)) == len(identities)
                and all(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', identity) for identity in identities),
                'unexpected access-only Docker inventory')
        selected = []
        for offset in range(0, len(identities), 32):
            batch = identities[offset:offset+32]
            rows = query('inspect', '--type', kind, '--format', '{{json ' + label_field + '}}', *batch).splitlines()
            require(len(rows) == len(batch), 'incomplete access-only Docker ownership inventory')
            for identity, row in zip(batch, rows, strict=True):
                candidate = (json.loads(row) or {}).get(label, '')
                require(isinstance(candidate, str), 'unknown access-only Docker ownership')
                if candidate.startswith(prefix):
                    require(project.fullmatch(candidate) is not None, 'unknown access-only Docker project')
                    selected.append(identity)
        return selected

    try:
        require(re.fullmatch(r'codex-[0-9a-f]{24}__', prefix) is not None
                and query('info', '--format', '{{.ID}}') == daemon, 'unqualified Docker cleanup scope')
        planned = [owned(kind, ids, labels) for kind, ids, _, _, _, labels in scopes]
        for (_, _, _, _, remove, _), identities in zip(scopes, planned, strict=True):
            if identities:
                query(*remove, *identities)
        return (query('info', '--format', '{{.ID}}') == daemon
                and all(not owned(kind, ids, labels) and not any(name.lstrip('/').startswith(prefix) for name in
                            query(*names, '--format', name_field).splitlines())
                        for kind, ids, names, name_field, _, labels in scopes)
                and docker_mounts_clear(query, acquisition))
    except (OSError, ValueError, KeyError, TypeError, AttributeError, subprocess.SubprocessError):
        return False


def access_docker_identity(env):
    executable = shutil.which('docker', path=env['PATH'])
    require(executable is not None, 'Docker is unavailable in the isolated runtime PATH')
    docker = Path(executable).resolve(strict=True)
    plugins = array(parse_json(docker_query(env, 'info', '--format', '{{json .ClientInfo.Plugins}}').encode(),
                               'Docker plugins'), 'Docker plugins')
    paths = [Path(text(plugin.get('Path'), 'Compose plugin path')) for plugin in plugins
             if isinstance(plugin, dict) and plugin.get('Name') == 'compose']
    require(len(paths) == 1 and paths[0].is_absolute(), 'Docker Compose plugin is ambiguous')
    compose = paths[0].resolve(strict=True)
    require(compose.is_file() and os.access(compose, os.X_OK), 'Docker Compose plugin is not executable')
    return digest(canonical({'docker': str(docker), 'docker_sha256': file_digest(docker),
                             'compose': str(compose), 'compose_sha256': file_digest(compose)}))


def qualified_access_executables(experiment, arm, command, env):
    require(access_docker_identity(env) == experiment.docker_client_sha256,
            'Docker and Compose bytes do not match qualification')
    tag = subprocess.run([*command[:-1], '-c', SIDECAR_TAG_SCRIPT], env=env, capture_output=True, timeout=10,
                         check=True, text=True).stdout.strip()
    matches(tag, r'harbor-prebuilt:harbor-docker-egress-control-sidecar--[a-f0-9]+', 'Harbor sidecar tag')
    require(docker_query(env, 'image', 'inspect', '--format', '{{.Id}}', tag) == experiment.egress_image_id,
            'effective Harbor egress sidecar is not the qualified image')
    import harbor_codex_completion

    image = experiment.images[arm]['agent_image_digest']
    output = docker_query(env, 'run', '--rm', '--pull=never', '--network=none', '--read-only',
                          '--cap-drop=ALL', '--security-opt=no-new-privileges', '--entrypoint=sha256sum',
                          image, *CODEX_IMAGE_EXECUTABLES)
    expected = (file_digest(Path(harbor_codex_completion.__file__)), experiment.codex_binary_sha256)
    require(output.splitlines() == [f'{value}  {path}' for value, path in zip(expected, CODEX_IMAGE_EXECUTABLES, strict=True)],
            'qualified agent image does not contain the reviewed shim and Codex binary')
    return tag


class DockerEventsConnection(HTTPConnection):
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX)
        self.transport = self.sock
        self.sock.settimeout(self.timeout)
        self.sock.connect('/var/run/docker.sock')


def docker_fenced_events(events, first, last):
    fences = {first: [], last: []}
    for index, event in enumerate(events):
        actor = event['Actor']
        if event['Type'] == 'volume' and event['Action'] == 'destroy' and actor['ID'] in fences:
            fences[actor['ID']].append(index)
    start, stop = fences[first], fences[last]
    return events[start[0] + 1:stop[0]] if len(start) == len(stop) == 1 and start[0] < stop[0] else None


class DockerEvents:
    def __init__(self, env, budget):
        self.env = env
        self.label = 'harbor-event-fence-' + uuid4().hex
        self.first, self.last = (self.label + '-' + phase for phase in ('start', 'stop'))
        self.connection = DockerEventsConnection('localhost', timeout=budget + 45)
        self.condition = threading.Condition()
        self.events = []
        self.verifier_spec = None
        self.verified_verifiers = set()
        self.closed = False
        self.thread = threading.Thread(target=self.read, daemon=True)

    def read(self):
        filters = {'type': ['container', 'network', 'volume'], 'event': ['create', 'start', 'destroy', 'mount']}
        since = time.time_ns() - 10**9
        query = urlencode({'since': f'{since // 10**9}.{since % 10**9:09d}', 'filters': json.dumps(filters)})
        total = 0
        limit = 8 * 1024 * 1024
        try:
            self.connection.request('GET', '/events?' + query)
            with self.connection.getresponse() as response:
                require(response.status == 200, 'Docker event stream unavailable')
                while total < limit:
                    line = response.readline(min(65537, limit - total))
                    if not line or not line.endswith(b'\n'):
                        break
                    total += len(line)
                    event = parse_json(line, 'Docker lifecycle event')
                    require(isinstance(event, dict) and isinstance(event.get('Actor'), dict),
                            'invalid Docker event stream envelope')
                    if self.verifier_spec:
                        verified = verifier_start_identity(self.env, event, *self.verifier_spec)
                        if verified:
                            self.verified_verifiers.add(verified)
                    with self.condition:
                        self.events.append(event)
                        self.condition.notify_all()
        except (OSError, HTTPException, ValueError):
            pass
        finally:
            with self.condition:
                self.closed = True
                self.condition.notify_all()

    def fence(self, identity, *, deadline=None):
        def query(*args):
            if deadline is None:
                return docker_query(self.env, *args)
            return docker_query(self.env, *args, timeout=cleanup_remaining(deadline))

        created = query('volume', 'create', '--driver', 'local', '--label',
                        f'com.docker.compose.project={self.label}', identity)
        try:
            require(created == identity, 'Docker event fence identity mismatch')
        finally:
            query('volume', 'rm', identity)
        with self.condition:
            def received():
                return self.closed or any(event.get('Type') == 'volume' and event.get('Action') == 'destroy'
                                          and event.get('Actor', {}).get('ID') == identity for event in self.events)

            timeout = 5 if deadline is None else cleanup_remaining(deadline, 5)
            require(self.condition.wait_for(received, timeout=timeout) and not self.closed,
                    'Docker event stream did not reach the writer boundary')

    def finish(self, *, deadline=None):
        self.fence(self.last, deadline=deadline)
        with self.condition:
            events = docker_fenced_events(self.events, self.first, self.last)
        require(events is not None, 'incomplete Docker event fences')
        return events

    def close(self, *, deadline=None):
        transport = getattr(self.connection, 'transport', None)
        if transport is not None:
            try:
                transport.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        timeout = 5 if deadline is None else max(0, min(5, deadline - time.monotonic()))
        self.thread.join(timeout=timeout)
        self.connection.close()
        require(not self.thread.is_alive(), 'Docker event stream did not terminate')


def verifier_start_identity(env, event, prefix, job, verifier_image, egress_image):
    from harbor_codex_egress import INSPECT, OFFLINE_POLICY, SIDECAR

    if event.get('Type') != 'container' or event.get('Action') != 'start':
        return None
    try:
        actor = event['Actor']
        identity = actor['ID']
        attributes = actor['Attributes']
        project = attributes.get('com.docker.compose.project', '')
        if not project.startswith(prefix) or attributes.get('com.docker.compose.service') != 'main':
            return None
        match = re.fullmatch(r'(.+)__verifier__[a-z0-9_-]+', project)
        if match is None or not re.fullmatch('[0-9a-f]{64}', identity):
            return None
        trial_name = match[1]
        main = json.loads(docker_query(env, 'inspect', '--type', 'container', '--format', INSPECT, identity, timeout=3))
        if main[:3] != [identity, verifier_image, True] or main[4] != 'main':
            return None
        secret_env = '{{range .Config.Env}}{{$k := index (split . "=") 0}}{{if or (eq $k "CODEX_AUTH_JSON_PATH") (eq $k "CODEX_API_KEY") (eq $k "OPENAI_API_KEY")}}present{{end}}{{end}}'
        if docker_query(env, 'inspect', '--format', secret_env, identity, timeout=3):
            return None
        for mount in main[6] or []:
            source = Path(mount['Source']).resolve().relative_to(job.resolve())
            if (mount['Type'] != 'bind' or len(source.parts) != 2 or source.parts[0].lower() != trial_name
                    or source.parts[1] != 'verifier' or mount['Destination'] != '/logs/verifier'):
                return None
        scope = main[3]
        if not isinstance(scope, str) or not re.fullmatch(r'container:[0-9a-f]{64}', scope):
            return None
        sidecar_id = scope.removeprefix('container:')
        sidecar = json.loads(docker_query(env, 'inspect', '--type', 'container', '--format', INSPECT,
                                         sidecar_id, timeout=3))
        if (sidecar[:4] != [sidecar_id, egress_image, True, f'{project}_default']
                or sidecar[4:6] != [SIDECAR, 'healthy']
                or sidecar[6]):
            return None
        label = '{{index .Config.Labels "com.docker.compose.project"}}'
        for container in (identity, sidecar_id):
            if docker_query(env, 'inspect', '--format', label, container, timeout=3) != project:
                return None
        effective = docker_query(env, 'exec', sidecar_id, 'network-policy', 'show', timeout=3).splitlines()
        return identity if effective == OFFLINE_POLICY else None
    except (OSError, KeyError, IndexError, TypeError, ValueError, subprocess.SubprocessError):
        return None


def docker_fenced_volumes_clear(prefix, env, events, deadline):
    try:
        rows = [json.loads(event) if isinstance(event, str) else event for event in events]
        containers = {row['Actor']['ID'] for row in rows if row['Type'] == 'container'
                      and row['Actor']['Attributes'].get('com.docker.compose.project', '').startswith(prefix)}
        mounted = {row['Actor']['ID'] for row in rows if row['Type'] == 'volume' and row['Action'] == 'mount'
                   and row['Actor']['Attributes'].get('container') in containers}
        current = docker_query(env, 'volume', 'ls', '-q', timeout=cleanup_remaining(deadline)).splitlines()
        return not mounted.intersection(current)
    except (OSError, KeyError, AttributeError, TypeError, ValueError, subprocess.SubprocessError):
        return False


def docker_seal(prefix, env, acquisition, daemon, expected_trials, events, *, job=None, deadline=None,
                verified_verifiers=()):
    from harbor_codex_egress import INFERENCE_HOST, RECEIPT, SIDECAR

    def query(*args):
        if deadline is None:
            return docker_query(env, *args)
        return docker_query(env, *args, timeout=cleanup_remaining(deadline))

    try:
        if query('info', '--format', '{{.ID}}') != daemon:
            return None
        ends = {'container': ('create', 'destroy'), 'network': ('create', 'destroy'), 'volume': ('create', 'destroy')}
        resources, roles, identity_roles, started = {}, {}, {}, set()
        volume_mounts, removed_volumes = [], set()
        services = {'main', SIDECAR}
        for event in events:
            if not isinstance(event, dict):
                event = json.loads(event)
            actor = event['Actor']
            project = actor['Attributes'].get('com.docker.compose.project', '')
            kind, action = event['Type'], event['Action']
            identity = (kind, actor['ID'])
            if kind == 'container' and action == 'start' and project.startswith(prefix):
                started.add(identity[1])
            if kind == 'volume' and action == 'mount':
                volume_mounts.append((actor['Attributes'].get('container'), identity[1]))
            if kind == 'volume' and action == 'destroy':
                removed_volumes.add(identity[1])
            owned_volume_end = kind == 'volume' and action == 'destroy' and not project and identity in resources
            if kind not in ends or action not in ends[kind] or (not owned_volume_end and not project.startswith(prefix)):
                continue
            require(isinstance(identity[1], str) and identity[1], 'Docker lifecycle lacks an identity')
            history = resources.setdefault(identity, [])
            require(len(history) < 2 and action == ends[kind][len(history)], 'inconsistent Docker lifecycle')
            history.append(action)
            if kind == 'container':
                match = re.fullmatch(r'([a-z0-9_-]+?)__(env|verifier__[a-z0-9_-]+)', project[len(prefix):])
                service = actor['Attributes'].get('com.docker.compose.service')
                require(match is not None and service in services, 'unexpected Docker writer role')
                trial, phase = match.groups()
                role = (trial, phase, service)
                require(roles.setdefault(role, identity) == identity
                        and identity_roles.setdefault(identity, role) == role, 'inconsistent Docker writer role')
        by_trial = defaultdict(lambda: defaultdict(set))
        for trial, phase, service in roles:
            by_trial[trial][phase].add(service)
        if (len(by_trial) > expected_trials or any(len(phases) > 2 for phases in by_trial.values())
                or any(len(history) != 2 for history in resources.values())):
            return None
        mounted = {volume for container, volume in volume_mounts if ('container', container) in identity_roles}
        if mounted - removed_volumes or mounted.intersection(query('volume', 'ls', '-q').splitlines()):
            return None
        eligible = []
        if job is not None and (job.exists() or job.is_symlink()):
            job = safe_path(acquisition, job.relative_to(acquisition).as_posix(), directory=True)
            for trial in job.iterdir():
                proof = trial / RECEIPT
                if not proof.exists() and not proof.is_symlink():
                    continue
                name = trial.name.lower()
                suffix = name[len(prefix):]
                phases = by_trial.get(suffix, {})
                if (not name.startswith(prefix) or 'env' not in phases or len(phases) != 2
                        or any(group != services for group in phases.values())):
                    continue
                main = roles[(suffix, 'env', 'main')][1]
                sidecar = roles[(suffix, 'env', SIDECAR)][1]
                verifier_phase, = set(phases) - {'env'}
                verifier = roles[(suffix, verifier_phase, 'main')][1]
                if verifier not in started or verifier not in verified_verifiers:
                    continue
                try:
                    observed = read_object(safe_path(job, f'{trial.name}/{RECEIPT}'), 'inference proof')
                    if observed == {'project': name + '__env', 'main': main, 'sidecar': sidecar,
                                    'allowed_host': INFERENCE_HOST}:
                        eligible.append(trial.name)
                except (OSError, ValueError):
                    continue
        if not docker_quiescent(prefix, env, query=query):
            return None
        if not docker_mounts_clear(query, acquisition,
                                   {identity for kind, identity in resources if kind == 'container'}):
            return None
        started_trials = {prefix + trial for (trial, phase, service), identity in roles.items()
                          if phase == 'env' and service == 'main' and identity[1] in started}
        return {**Counter(kind for kind, _ in resources), 'trial_projects': len(by_trial),
                'eligible_trials': sorted(eligible),
                'started_trials': sorted(started_trials | {name.lower() for name in eligible})}
    except (OSError, ValueError, KeyError, TypeError, AttributeError, subprocess.SubprocessError):
        return None


def qualified_docker_prefix(experiment, arm, staged, env):
    task = tomllib.loads((staged / 'task.toml').read_text(encoding='utf-8'))
    name = matches(staged.name, r'codex-[0-9a-f]{24}', 'stable access-only Docker namespace')
    require(task.get('agent', {}).get('timeout_sec') == experiment.runtime['timeout_sec'],
            'access-only agent timeout does not match the frozen per-trial budget')
    require(not any(path.name.startswith(('docker-compose', 'compose.')) for path, _ in walk_tree(staged)),
            'custom Compose prohibited in access-only tasks')
    configured = (task.get('environment', {}), task.get('verifier', {}).get('environment', {}))
    require(all(config.get('network_mode') == 'no-network' and not config.get('allowed_hosts')
                and 'allow_internet' not in config for config in (*configured, task.get('verifier', {})))
            and task['agent'].get('network_mode') == 'allowlist'
            and task['agent'].get('allowed_hosts') == ['chatgpt.com'],
            'access-only network policy does not match the isolated setup, agent and verifier contract')
    require(configured[0].get('healthcheck') == ACCESS_HEALTHCHECK,
            'missing access-only pre-upload network healthcheck')
    for key, definition in zip(IMAGE_FIELDS, configured, strict=True):
        image = experiment.images[arm][key]
        require(definition.get('docker_image') == image
                and docker_query(env, 'image', 'inspect', '--format', '{{.Id}}', image) == image,
                'access-only image is not bound to its qualified local image ID')
    require(docker_query(env, 'info', '--format', '{{.ID}}') == experiment.docker_server_id,
            'local Docker server does not match qualification')
    return name + '__'


def open_auth_path(path):
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts and len(path.parts) > 1,
            'access-only auth path must be absolute without traversal')
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY
    directory = os.open(path.anchor, flags)
    try:
        for part in path.parts[1:-1]:
            parent = directory
            directory = os.open(part, flags, dir_fd=parent)
            os.close(parent)
        return os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    finally:
        os.close(directory)


def wall_budget(experiment, arm):
    runtime = experiment.runtime
    if runtime.get('auth_mode') != ACCESS_MODE:
        return runtime['timeout_sec']
    waves = (experiment.trials[arm] + runtime['concurrency'] - 1) // runtime['concurrency']
    return waves * (runtime['timeout_sec'] + 180) + 60


def access_failure_record(experiment, arm, output, status, withheld=0, recovery=None):
    require(status in ('UNSEALED', 'ACCESS_OR_RELEASE_REJECTED', 'QUALIFICATION_MISMATCH'), 'unknown access failure status')
    require(withheld is None or (type(withheld) is int and 0 <= withheld <= experiment.trials[arm]
            and (status != 'UNSEALED' or not withheld)), 'invalid withheld trial count')
    result = {'schema': 'experiment-access-failure.v1', 'run_dir': str(output),
              'manifest_sha256': experiment.manifest_sha256, 'case_sha256': experiment.case_sha256,
              'arm': arm, 'status': status, 'withheld_trials': withheld}
    if recovery is not None:
        require(isinstance(recovery, str) and re.fullmatch(r'harbor-codex-(?:[a-z0-9_]{8}|[a-f0-9]{24})', recovery),
                'invalid private recovery locator')
        result['private_recovery_id'] = recovery
    return result


def emit_access_failure(experiment, arm, output, status, withheld=0, recovery=None):
    failure = access_failure_record(experiment, arm, output, status, withheld, recovery)
    output.mkdir(mode=0o700)
    write_json(output / 'launch.json', failure)
    return failure


def retained_native_format(path):
    parts = path.parts
    if len(parts) == 1 and parts[0] in ACCESS_CAPTURES:
        return None
    if len(parts) == 3 and parts[0] == 'jobs':
        if parts[2] in {'job.log', 'lock.json'}:
            return None
        if parts[2] in {'config.json', 'result.json'}:
            return 'json'
    trial_path = parts[3:] if len(parts) >= 4 and parts[0] == 'jobs' else ()
    if trial_path in {('agent', 'codex.txt'), ('agent', 'trajectory.json'), ('lock.json',),
                      ('trial.log',), ('exception.txt',), ('verifier', 'reward.txt'),
                      ('verifier', 'test-stdout.txt'), ('verifier', 'test-stderr.txt'), ('artifacts', 'manifest.json')}:
        return None
    if (len(trial_path) == 6 and trial_path[:2] == ('agent', 'sessions')
            and re.fullmatch(r'\d{4}/\d{2}/\d{2}/rollout-[\w.-]+\.jsonl', '/'.join(trial_path[2:]))):
        return 'native_rollout'
    if trial_path == ('artifacts', 'approved', 'fixture-events.tsv'):
        return 'log'
    if trial_path in {('config.json',), ('result.json',),
                      ('access-egress.json',),
                      ('verifier', 'reward.json'),
                      ('artifacts', 'approved', 'exposure.json')}:
        return 'json'
    raise ValueError('unrecognized retained output role')


def verify_acquisition_scope(raw, name):
    leaf_files = {'launch.json', *ACCESS_CAPTURES}
    allowed_dirs = {'staged', 'jobs', 'home', 'work'}
    for path in raw.iterdir():
        mode = path.lstat().st_mode
        require((path.name in leaf_files and stat.S_ISREG(mode))
                or (path.name in allowed_dirs and stat.S_ISDIR(mode)), 'unexpected private acquisition output')
    for private in ('work', 'home'):
        path = raw / private
        require(not path.exists() or not any(path.iterdir()), f'unexpected private {private} output')
    require(all(path.name == name for path in (raw / 'staged').iterdir()), 'unexpected staged task scope')


def sealed_trial_count(raw, arm, expected):
    job = raw / 'jobs' / arm
    try:
        if (raw / 'jobs').is_symlink() or job.is_symlink():
            return None
        if not job.exists():
            return 0
        observed = 0
        for index, trial in enumerate(job.iterdir()):
            if index >= 8192:
                return None
            if not stat.S_ISDIR(trial.lstat().st_mode):
                continue
            try:
                result_mode = (trial / 'result.json').lstat().st_mode
                if not stat.S_ISREG(result_mode):
                    return None
                observed += 1
            except FileNotFoundError:
                pass
        return observed if observed <= expected else None
    except OSError:
        return None


def project_fields(obj, schema):
    if obj is None:
        return None
    if schema is None:
        require(type(obj) in (bool, int, float, str), 'invalid retained scalar')
        return obj
    if isinstance(schema, list):
        return [project_fields(value, schema[0]) for value in array(obj, 'retained list', nonempty=False)]
    require(isinstance(obj, dict), 'invalid retained object')
    return {key: project_fields(obj[key], value) for key, value in schema.items() if key in obj}


def access_json_projection(relative, record, *, expected_config_source=None):
    require(isinstance(record, dict), 'invalid private Harbor record')
    def scalars(*names):
        return dict.fromkeys(names)

    control_env = scalars('HARBOR_EXPERIMENT_CASE_SHA256', 'HARBOR_EXPERIMENT_ARM', 'HARBOR_EXPERIMENT_RUN_SHA256')
    task = scalars('path', 'git_url', 'git_commit_id', 'name', 'ref', 'download_dir', 'source')
    agent = {**scalars('name', 'model_name'), 'extra_allowed_hosts': [None],
             'kwargs': {**scalars('version', 'reasoning_effort'), 'config_source': dict.fromkeys(ACCESS_AGENT_CONFIG)}}
    verifier = {**scalars('disable', 'import_path'), 'env': control_env}
    config = {**scalars('trial_name', 'trials_dir', 'job_id'), 'task': task, 'agent': agent, 'verifier': verifier}
    timing = scalars('started_at', 'finished_at')
    leaves = relative.parts[2:]
    config_input = record if relative.name == 'config.json' else record.get('config') if relative.name == 'result.json' else None
    if config_input is not None:
        require(isinstance(config_input, dict), 'invalid raw config')
        check_fresh_config(config_input)
        native_agents = config_input.get('agents', [config_input.get('agent', {})])
        expected_source = ACCESS_AGENT_CONFIG if expected_config_source is None else expected_config_source
        require(all(isinstance(entry, dict) and not any(entry.get(key) for key in (
            'import_path', 'load_trajectory', 'skills', 'resume_trajectory', 'skip_model_parsing', 'mcp_servers', 'env'))
            and isinstance(entry.get('kwargs') or {}, dict)
            and set(entry.get('kwargs') or {}) <= {'version', 'reasoning_effort', 'config_source'}
            and (entry.get('kwargs') or {}).get('config_source') == expected_source
            for entry in array(native_agents, 'raw agent configs', nonempty=False)), 'unexpected raw agent options')
        native_verifier = config_input.get('verifier') or {}
        require(isinstance(native_verifier, dict) and not native_verifier.get('kwargs')
                and set(native_verifier.get('env') or {}) <= control_env.keys(), 'unexpected raw verifier options')
    if leaves == ('config.json',):
        schema = {**scalars('job_name', 'jobs_dir', 'n_attempts', 'n_concurrent_trials'),
                  'tasks': [task], 'agents': [agent], 'verifier': verifier}
    elif leaves == ('result.json',):
        schema = {**timing, **scalars('id', 'n_total_trials'), 'stats': scalars('n_completed_trials',
                  'n_cancelled_trials', 'n_running_trials', 'n_pending_trials', 'n_retries', 'n_errored_trials',
                  'n_input_tokens', 'n_cache_tokens', 'n_output_tokens', 'cost_usd')}
    elif leaves[1:] == ('config.json',):
        schema = config
    elif leaves[1:] == ('result.json',):
        schema = {**timing, **scalars('id', 'task_name', 'trial_name', 'trial_uri', 'task_checksum',
                      'verifier_environment_mode'), 'task_id': scalars('path'), 'config': config,
                  'agent_info': {**scalars('name', 'version'), 'model_info': scalars('name', 'provider')},
                  'agent_result': scalars('n_input_tokens', 'n_cache_tokens', 'n_output_tokens', 'cost_usd'),
                  'verifier_result': {'rewards': scalars('exposure_verified')}, 'agent_execution': timing,
                  'exception_info': scalars('exception_type', 'occurred_at'), 'step_results': [{}]}
    elif leaves[1:] == ('access-egress.json',):
        schema = scalars('project', 'main', 'sidecar', 'allowed_host')
    elif leaves[1:] == ('verifier', 'reward.json'):
        schema = scalars('exposure_verified')
    elif leaves[1:] == ('artifacts', 'approved', 'exposure.json'):
        schema = {**scalars('schema', 'trial', 'trial_id', 'run_sha256', 'thread_id', 'native_path',
                            'raw_rollout_sha256', 'control_sha256', 'prompt_sha256'),
                  'first_turn': {'turn_id': None, 'instructions': [None], 'task_input': [None]}}
    else:
        raise ValueError('no supported JSON release projection')
    return project_fields(record, schema)


def release_access_run(experiment, arm, raw, stage, output, private_values, launch, *, deadline=None,
                       expected_config_source=None):
    from harbor_codex_access import (read_artifact, safe_artifact_format, sanitize_bytes, verify_frozen_release,
                                    verify_scoring_release)
    from harbor_codex_completion import (PRIVATE_RECEIPT, PUBLIC_RECEIPT, cli_usage, native_control_seen,
                                         scoring_projection, verify_completion)

    def check_deadline():
        if deadline is not None:
            cleanup_remaining(deadline)

    job = raw / 'jobs' / arm
    eligible = set(launch.get('docker_sealed_resources', {}).get('eligible_trials', ()))
    name = staged_name(experiment, raw)
    verify_acquisition_scope(raw, name)
    sealed_job = access_job_inventory(job, isolate_trials=True, max_trials=experiment.trials[arm])
    job_hash, withheld_names = sealed_job if sealed_job is not None else (None, set())
    before = (staged_inventory(raw, name), job_hash, access_capture_hashes(raw))
    require(before == (launch['staged_after'], launch['job_sha256'], launch['capture_sha256']),
            'sealed acquisition changed')
    require(not (raw / 'jobs').is_symlink() and (not (raw / 'jobs').exists()
            or all(path == job for path in (raw / 'jobs').iterdir())), 'unexpected job scope')
    require(not job.exists() or before[1] is not None, 'job has no sealed inventory')
    with_private_completions = {}
    if job.is_dir():
        for trial in job.iterdir():
            check_deadline()
            if not trial.is_dir() or trial.is_symlink() or trial.name in withheld_names:
                continue
            private = trial / 'agent' / PRIVATE_RECEIPT
            public = trial / 'agent' / PUBLIC_RECEIPT
            rollout_path = None
            try:
                thread, rollout_hash, rollout_path = verify_completion(
                    private, private.with_name('codex.txt'), private.with_name('sessions'),
                    experiment.runtime['model'], experiment.runtime['effort'],
                )
                usage = cli_usage(private.with_name('codex.txt'))
                proof = {'verified': True, 'thread_id': thread, **({'usage': usage} if usage else {})}
            except (OSError, TypeError, ValueError, KeyError):
                rollout_hash = None
                proof = {'verified': False, 'thread_id': None}
            observation_verified = False
            try:
                require(rollout_path is not None, 'raw trajectory is not verified')
                _, observed_rollout = check_observation(experiment, arm, trial, launch['run_sha256'],
                                                        bounded=True, expected_trace=rollout_path,
                                                        expected_thread=proof['thread_id'])
                staged_control = safe_path(raw / 'staged' / name, 'environment/workspace/AGENTS.md')
                staged_prompt = safe_path(raw / 'staged' / name, 'instruction.md')
                control, prompt = access_bytes(staged_control), access_bytes(staged_prompt)
                exposure = native_control_seen(rollout_path, control, prompt) if observed_rollout == rollout_hash else False
                if exposure:
                    witness_path = safe_path(trial, 'artifacts/approved/exposure.json')
                    witness = parse_json(access_bytes(witness_path), 'private acquisition witness')
                    require(isinstance(witness, dict) and witness.get('first_turn') == exposure
                            and witness.get('control_sha256') == digest(control)
                            and witness.get('prompt_sha256') == digest(prompt), 'acquisition exposure does not match')
                    proof['first_turn'] = {**exposure, 'instructions_sha256': digest(control),
                                           'task_input_sha256': digest(prompt), 'raw_rollout_sha256': rollout_hash}
                    observation_verified = True
            except (OSError, ValueError, TypeError, KeyError):
                pass
            proof['raw_observation_verified'] = observation_verified
            with_private_completions[private.relative_to(raw)] = (public.relative_to(raw), proof)
    def release_file(source, target, relative):
        check_deadline()
        form = retained_native_format(relative)
        if form is None:
            return
        safe_artifact_format(relative.as_posix(), private_values)
        data = access_bytes(source)
        if form == 'json':
            raw_object = parse_json(data, 'private Harbor record')
            if len(relative.parts) == 4 and relative.name == 'result.json':
                check_trial_result_envelope(raw_object, source.parent, raw / 'staged' / name)
            data = canonical(access_json_projection(relative, raw_object,
                                                     expected_config_source=expected_config_source)) + b'\n'
        released = sanitize_bytes(data, private_values, form)
        if form == 'native_rollout':
            released = scoring_projection(data)
            verify_scoring_release(released, private_values)
        if form == 'log':
            require(released == data, 'required fixture evidence would change under masking')
        if len(relative.parts) == 4 and relative.name == 'result.json':
            task = raw / 'staged' / name
            check_trial_result_envelope(parse_json(released, 'released Harbor trial result'), source.parent, task,
                                        projected=True)
        if form == 'json':
            require(parse_json(released, 'held JSON record') == parse_json(data, 'projected JSON record'),
                    'required Harbor evidence would change under masking')
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(released)

    def withhold_trial(trial, target):
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True)
        result = trial / 'result.json'
        write_json(target / 'access-withheld.json', {'result_present': result.is_file() and not result.is_symlink()})

    unsafe_trial_names = set()
    if job.is_dir():
        for trial in sorted(job.iterdir()):
            check_deadline()
            trial_relative = trial.relative_to(raw)
            target = stage / trial_relative
            if not trial.is_dir():
                release_file(trial, target, trial_relative)
                continue
            try:
                safe_artifact_format(trial_relative.as_posix(), private_values, directory=True)
            except ValueError:
                unsafe_trial_names.add(trial.name)
                alias = f'withheld-{uuid4().hex}'
                require(not (job / alias).exists() and not (job / alias).is_symlink(), 'withheld trial alias collision')
                relative = job.relative_to(raw) / alias
                safe_artifact_format(relative.as_posix(), private_values, directory=True)
                withhold_trial(trial, stage / relative)
                continue
            private = trial / 'agent' / PRIVATE_RECEIPT
            raw_observation = trial / OBSERVATION_PATH
            marker = 'access-withheld.json'
            try:
                require(trial.name not in withheld_names, 'trial has no bounded sealed inventory')
                require(not (trial / marker).exists(), 'unexpected release marker')
                require(not (trial / 'result.json').exists() or trial.name in eligible,
                        'trial has no qualified live egress receipt')
                relative, proof = with_private_completions[private.relative_to(raw)]
                for source, info in walk_tree(trial):
                    source_relative = source.relative_to(raw)
                    if stat.S_ISDIR(info.st_mode):
                        safe_artifact_format(source_relative.as_posix(), private_values, directory=True)
                    elif source not in (private, raw_observation):
                        form = retained_native_format(source_relative)
                        if form == 'native_rollout':
                            require(proof['verified'], 'unverified or ambiguous native output')
                        release_file(source, stage / source_relative, source_relative)
                safe_artifact_format(relative.as_posix(), private_values)
                public = stage / relative
                public.parent.mkdir(parents=True, exist_ok=True)
                if proof['raw_observation_verified']:
                    observation_path = target / OBSERVATION_PATH
                    observation = parse_json(access_bytes(safe_path(trial, OBSERVATION_PATH)), 'sealed exposure observation')
                    for reference in (observation['trajectory'], *observation['evidence']):
                        reference['sha256'] = digest(safe_path(target, reference['path']).read_bytes())
                    proof['first_turn']['scoring_sha256'] = observation['trajectory']['sha256']
                    safe_artifact_format(observation_path.relative_to(stage).as_posix(), private_values)
                    observation_path.parent.mkdir(parents=True, exist_ok=True)
                    observation_path.write_bytes(sanitize_bytes(canonical(observation) + b'\n', private_values, 'json'))
                public.write_bytes(sanitize_bytes(canonical(proof) + b'\n', private_values, 'json'))
            except (OSError, ValueError, TypeError, KeyError):
                withhold_trial(trial, target)

    raw_task = raw / 'staged' / name
    for entry in launch['staged_before']:
        path = entry['path']
        source = safe_path(raw_task, path)
        with os.fdopen(os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as stream:
            data = read_artifact(stream.fileno())
        verify_frozen_release(path, data, private_values)
        require(digest(data) == entry['sha256'], 'frozen task changed')
    verify_acquisition_scope(raw, name)
    require((staged_inventory(raw, name), access_job_inventory(job, isolate_trials=True,
             max_trials=experiment.trials[arm]), access_capture_hashes(raw))
            == (before[0], sealed_job, before[2]),
            'sealed acquisition changed')
    require(parse_json(access_bytes(raw / 'launch.json'), 'sealed launch') == launch, 'sealed launch changed')
    if unsafe_trial_names:
        resources = launch['docker_sealed_resources']
        for field in ('eligible_trials', 'started_trials'):
            if field in resources:
                omitted = unsafe_trial_names if field == 'eligible_trials' else {name.lower() for name in unsafe_trial_names}
                resources[field] = [name for name in resources[field] if name not in omitted]
    launch['job_sha256'] = tree_hash_if_available(stage / 'jobs' / arm)
    launch['capture_sha256'] = access_capture_hashes(stage)
    launch['retained_root'] = str(output)
    completed = list((stage / 'jobs' / arm).glob('*/result.json'))
    quarantined = list((stage / 'jobs' / arm).glob('*/access-withheld.json'))
    verified = 0
    for result in completed:
        completion = read_object(safe_path(result.parent, f'agent/{PUBLIC_RECEIPT}'), 'native completion proof')
        verified += completion.get('verified') is True and completion.get('raw_observation_verified') is True
    complete = ((launch.get('status'), launch.get('exit_code')) == ('SUCCEEDED', 0)
                and verified == len(completed) == experiment.trials[arm]
                and not quarantined and all(path.parent.name in eligible for path in completed))
    if complete and semantic_fixture_required(experiment, arm):
        complete = all((path.parent / FIXTURE_EVIDENCE).is_file() for path in completed)
    launch['release_status'] = 'COMPLETE' if complete else 'INCOMPLETE'
    launch['verified_native_trials'] = verified
    secure = canonical(launch) + b'\n'
    safe = sanitize_bytes(secure, private_values, 'json')
    require(parse_json(safe, 'sanitized launch') == launch, 'release metadata required redaction')
    write_json(stage / 'launch.json', launch)


def remove_access_directory(path, *, deadline=None):
    if path is None:
        return True
    try:
        if path.exists() or path.is_symlink():
            require(path.is_absolute() and path.is_dir() and not path.is_symlink(), 'unsafe access cleanup root')
            if deadline is None:
                shutil.rmtree(path)
            else:
                subprocess.run([sys.executable, '-I', '-B', '-c',
                                'import shutil, sys; shutil.rmtree(sys.argv[1])', str(path)],
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               check=True, timeout=cleanup_remaining(deadline))
        return not path.exists() and not path.is_symlink()
    except (OSError, ValueError, KeyboardInterrupt, subprocess.SubprocessError):
        return False


def access_holder(case_sha256):
    return ACCESS_PRIVATE_ROOT / ('harbor-codex-' + matches(case_sha256, r'[a-f0-9]{64}', 'case identity')[:24])


def reserve_access_holder(case_sha256):
    holder = access_holder(case_sha256)
    holder.mkdir(mode=0o700)
    return holder


def finish_unsealed_access(experiment, arm, output, holder, launch, deadline):
    require(launch['status'] == 'UNSEALED', 'unsealed terminal requires failed seal')
    recovery = holder.name
    if launch.get('cleanup') == 'docker_reconciled' and remove_access_directory(holder, deadline=deadline):
        recovery = None
    return emit_access_failure(experiment, arm, output, 'UNSEALED', None, recovery)


def run_access(experiment, arm, output, auth_file, account_fd):
    from harbor_codex_access import CLEANUP_SECONDS, derivative_not_after, prepare_derivative, read_account_reference, verify_private_path

    holder = None
    stage = None
    recovery = None
    cleanup_failed = False
    acquisition_unsealed = False
    withheld = 0
    destination_checked = False
    cleanup_clock = {}

    def remove(path):
        if path is None:
            return True
        return remove_access_directory(path, deadline=cleanup_clock.setdefault('deadline', time.monotonic() + CLEANUP_SECONDS))

    try:
        expected = read_account_reference(account_fd, auth_file)
        verify_private_path(Path(output), (expected,))
        directory = new_output(experiment, output)
        verify_private_path(directory, (expected,))
        with os.fdopen(open_auth_path(auth_file), 'rb') as source:
            derivative_bytes, private_values = prepare_derivative(source.fileno(), expected,
                                                                   wall_budget(experiment, arm), time.time)
        private_values = (*private_values, str(auth_file))
        verify_private_path(directory, private_values)
        destination_checked = True
        not_after = derivative_not_after(derivative_bytes, wall_budget(experiment, arm))
        holder = reserve_access_holder(experiment.case_sha256)
        verify_private_path(holder.name, private_values)
        recovery = holder.name
        derivative = holder / 'secret'
        with os.fdopen(os.open(derivative, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as stream:
            stream.write(derivative_bytes)
        raw = holder / f'acquisition-{uuid4().hex}'
        acquisition_unsealed = True
        try:
            withheld = None
            launch = run_harbor(experiment, arm, raw, None, derivative=derivative, not_after=not_after,
                                cleanup_clock=cleanup_clock)
        finally:
            try:
                derivative.unlink(missing_ok=True)
            except OSError:
                acquisition_unsealed = True
                raise
        acquisition_unsealed = launch['status'] == 'UNSEALED'
        if acquisition_unsealed:
            return finish_unsealed_access(experiment, arm, directory, holder, launch, cleanup_clock['deadline'])
        withheld = sealed_trial_count(raw, arm, experiment.trials[arm])
        if launch['status'] == 'CAPTURE_INVALID':
            return emit_access_failure(experiment, arm, directory, 'ACCESS_OR_RELEASE_REJECTED', withheld,
                                       None if remove(holder) else recovery)
        if launch['status'] == 'QUALIFICATION_MISMATCH':
            return emit_access_failure(experiment, arm, directory, 'QUALIFICATION_MISMATCH', withheld,
                                       None if remove(holder) else recovery)
        cleanup_remaining(cleanup_clock['deadline'])
        stage = Path(tempfile.mkdtemp(prefix='.harbor-release-', dir=directory.parent))
        release_access_run(experiment, arm, raw, stage, directory, private_values, launch,
                           deadline=cleanup_clock['deadline'])
        require(not directory.exists() and not directory.is_symlink(), 'output already exists')
        cleanup_failed = not remove(holder)
        require(not cleanup_failed, 'private acquisition cleanup unverified')
        cleanup_remaining(cleanup_clock['deadline'])
        stage.rename(directory)
        return {**launch, 'run_dir': str(directory)}
    except (OSError, ValueError, subprocess.SubprocessError, KeyboardInterrupt):
        if not acquisition_unsealed and not cleanup_failed:
            cleanup_failed = not remove(holder)
        if not destination_checked:
            return {'status': 'ACCESS_OR_RELEASE_REJECTED', 'run_dir': None}
        if acquisition_unsealed:
            return emit_access_failure(experiment, arm, directory, 'UNSEALED', None, recovery)
        return emit_access_failure(experiment, arm, directory, 'ACCESS_OR_RELEASE_REJECTED', withheld,
                                   recovery if cleanup_failed else None)
    finally:
        remove(stage)


def run(experiment, arm, output, baseline, *, auth_file=None, account_fd=None):
    if experiment.runtime.get('auth_mode') == ACCESS_MODE:
        require(arm == 'baseline' and baseline is None, 'access-only runtime permits baseline only')
        require(auth_file is not None and account_fd is not None, 'access-only credential and account reference required')
        qualified_harbor_install(experiment, shutil.which('harbor'))
        return run_access(experiment, arm, output, auth_file, account_fd)
    require(auth_file is None and account_fd is None, 'access-only inputs require the access-only runtime')
    return run_harbor(experiment, arm, output, baseline)


def run_harbor(experiment, arm, output, baseline, *, derivative=None, not_after=None, cleanup_clock=None):
    from harbor_codex_access import CLEANUP_SECONDS

    if cleanup_clock is None:
        cleanup_clock = {}
    require(os.name == 'posix', 'run requires POSIX process groups')
    require((baseline is not None) == (arm == 'treatment'),
            'only treatment requires --baseline RECEIPT')
    baseline_ref = None
    protected = ()
    if arm == 'treatment':
        baseline_path = resolve_input(baseline)
        raw_baseline = baseline_path.read_bytes()
        baseline_report = validate_baseline(experiment, parse_baseline_receipt(experiment, raw_baseline))
        protected = (Path(baseline_report['run_dir']),)
        baseline_ref = {'path': str(baseline_path), 'sha256': digest(raw_baseline)}

    directory = new_output(experiment, output, outside=protected)
    executable = shutil.which('harbor')
    require(executable is not None, 'Harbor 0.25.0 executable is required on PATH')
    if derivative is not None:
        qualified_harbor_install(experiment, executable)
    command = access_harbor_command(executable) if derivative is not None else [str(Path(executable).absolute())]
    argv = experiment.argv(arm, directory, command[-1], command_prefix=command[:-1])
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
    docker_scope = None
    event_stream = None
    event_lines = None
    egress_tag = None
    process_drained = False
    name = staged_name(experiment, directory)

    try:
        (directory / 'staged').mkdir()
        (directory / 'home').mkdir()
        (directory / 'work').mkdir()
        staged = directory / 'staged' / name
        shutil.copytree(experiment.tasks[arm], staged, symlinks=True)
        receipt['staged_before'] = staged_inventory(directory, name)
        require(receipt['staged_before'] is not None
                and digest(canonical(receipt['staged_before'])) == receipt['task_sha256'],
                'staged task inputs do not match the manifest')
        write_json(receipt_path, receipt, replace=True)

        env = {key: os.environ[key] for key in PROCESS_ENV if key in os.environ}
        env['HOME'] = str(directory / 'home')
        if derivative is not None:
            env = access_docker_env(directory / 'home')
        common = {'cwd': directory / 'work', 'env': env}
        timeout = wall_budget(experiment, arm)
        with (
            (directory / 'version.stdout.log').open('xb') as version_stdout,
            (directory / 'version.stderr.log').open('xb') as version_stderr,
            (directory / 'stdout.log').open('xb') as stdout,
            (directory / 'stderr.log').open('xb') as stderr,
        ):
            status, code = invoke(
                [*command, '--version'], **common, stdout=version_stdout, stderr=version_stderr,
                timeout=min(10, timeout), sealed=derivative is not None,
            )
            if status == 'SUCCEEDED':
                actual = (directory / 'version.stdout.log').read_bytes().strip()
                desired = experiment.runtime['harbor_version']
                if actual == desired.encode():
                    receipt['harbor_version'] = desired
                    if derivative is None:
                        env.update({key: os.environ[key] for key in PROVIDER_ENV if key in os.environ})
                    else:
                        try:
                            qualified_harbor_install(experiment, command[-1])
                            prefix = qualified_docker_prefix(experiment, arm, staged, env)
                            require(docker_quiescent(prefix, env), 'qualified Docker namespace is not empty')
                            egress_tag = qualified_access_executables(experiment, arm, command, env)
                            event_stream = DockerEvents(env, timeout)
                            event_stream.verifier_spec = (prefix, directory / 'jobs' / arm,
                                                          experiment.images[arm]['verifier_image_digest'],
                                                          experiment.egress_image_id)
                            event_stream.thread.start()
                            event_stream.fence(event_stream.first)
                        except (OSError, ValueError, subprocess.SubprocessError):
                            status = 'QUALIFICATION_MISMATCH'
                            return receipt
                        if not_after is None or time.time() >= not_after:
                            status = 'BEARER_WINDOW_ELAPSED'
                            return receipt
                        docker_scope = prefix
                        receipt['docker_scope'] = prefix
                        receipt['harbor_install_sha256'] = experiment.harbor_install_sha256
                        receipt['docker_client_sha256'] = experiment.docker_client_sha256
                        receipt['egress_image_id'] = experiment.egress_image_id
                        env['CODEX_AUTH_JSON_PATH'] = str(derivative)
                    try:
                        status, code = invoke(
                            argv, **common, stdout=stdout, stderr=stderr, timeout=timeout,
                            sealed=derivative is not None,
                        )
                        process_drained = status != 'UNSEALED'
                    finally:
                        if derivative is not None:
                            cleanup_clock.setdefault('deadline', time.monotonic() + CLEANUP_SECONDS)
                            env.pop('CODEX_AUTH_JSON_PATH', None)
                            try:
                                derivative.unlink(missing_ok=True)
                            except OSError:
                                status = 'UNSEALED'
                    if event_stream is not None and process_drained and status != 'START_FAILED':
                        try:
                            event_lines = event_stream.finish(deadline=cleanup_clock['deadline'])
                        except (OSError, KeyError, TypeError, ValueError, subprocess.SubprocessError):
                            status = 'UNSEALED'
                else:
                    status = 'VERSION_MISMATCH'
    except KeyboardInterrupt:
        status = 'UNSEALED' if derivative is not None else 'INTERRUPTED'
    finally:
        if derivative is not None:
            cleanup_clock.setdefault('deadline', time.monotonic() + CLEANUP_SECONDS)
            try:
                derivative.unlink(missing_ok=True)
            except OSError:
                status = 'UNSEALED'
        if event_stream is not None:
            try:
                event_stream.close(deadline=cleanup_clock.get('deadline'))
            except (OSError, ValueError, KeyboardInterrupt):
                status = 'UNSEALED'
        if docker_scope is not None:
            resources = None if status == 'UNSEALED' or event_lines is None else docker_seal(
                docker_scope, env, directory.parent, experiment.docker_server_id,
                experiment.trials[arm], event_lines, job=directory / 'jobs' / arm,
                deadline=cleanup_clock['deadline'],
                verified_verifiers=event_stream.verified_verifiers,
            )
            if resources is None:
                status = 'UNSEALED'
                if process_drained:
                    reconciled = reconcile_access_docker(docker_scope, env, directory.parent,
                                                         experiment.docker_server_id, deadline=cleanup_clock['deadline'])
                    no_remaining_mounts = event_lines is not None and docker_fenced_volumes_clear(
                        docker_scope, env, event_lines, cleanup_clock['deadline'])
                    receipt['cleanup'] = 'docker_reconciled' if reconciled and no_remaining_mounts else 'unverified'
            else:
                receipt['docker_sealed_resources'] = resources
                receipt['cleanup'] = 'docker_sealed'
                try:
                    require(docker_query(env, 'image', 'inspect', '--format', '{{.Id}}', egress_tag,
                                         timeout=cleanup_remaining(cleanup_clock['deadline']))
                            == experiment.egress_image_id, 'sidecar image changed during the job')
                except (OSError, ValueError, subprocess.SubprocessError):
                    status = 'QUALIFICATION_MISMATCH'
        if status != 'UNSEALED':
            receipt['staged_after'] = staged_inventory(directory, name)
        jobs = directory / 'jobs'
        job = jobs / arm
        if status != 'UNSEALED' and not jobs.is_symlink():
            if derivative is not None:
                sealed_job = access_job_inventory(job, isolate_trials=True, max_trials=experiment.trials[arm])
                if sealed_job is not None:
                    receipt['job_sha256'] = sealed_job[0]
            else:
                receipt['job_sha256'] = tree_hash_if_available(job)
        if status != 'UNSEALED' and derivative is not None:
            receipt['capture_sha256'] = access_capture_hashes(directory)
        if status == 'SUCCEEDED' or (receipt['cleanup'] == 'docker_sealed'
                                    and status in {'FAILED', 'TIMED_OUT', 'INTERRUPTED'}):
            if receipt['staged_after'] == receipt['staged_before']:
                try:
                    current = Experiment(experiment.path)
                    require(current.manifest_sha256 == experiment.manifest_sha256,
                            'manifest changed during execution')
                except (OSError, ValueError):
                    status = 'INPUTS_CHANGED'
            else:
                status = 'INPUTS_CHANGED'
        if derivative is None and status == 'SUCCEEDED' and receipt['job_sha256'] is not None:
            try:
                if any(cleanup_warning(log) for log in job.glob('*/trial.log') if log.is_file()):
                    status = 'CLEANUP_FAILED'
            except OSError:
                status = 'CLEANUP_UNVERIFIED'
        receipt['status'] = status
        receipt['exit_code'] = code
        if status == 'SUCCEEDED' and derivative is None:
            receipt['cleanup'] = 'harbor_completed'
        write_json(receipt_path, receipt, replace=True)
    return receipt


def check_job(experiment, arm, job, native_job, staged, verifier_env):
    config = read_object(safe_path(job, 'config.json'), 'Harbor job config')
    result = read_object(safe_path(job, 'result.json'), 'Harbor job result')
    expected = experiment.trials[arm]
    require(config.get('job_name') == arm and config.get('jobs_dir') == str(native_job.parent)
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
    stats = result.get('stats')
    if experiment.runtime.get('auth_mode') == ACCESS_MODE:
        counts = ('n_completed_trials', 'n_cancelled_trials', 'n_running_trials', 'n_pending_trials')
        require(isinstance(stats, dict) and stats.get('n_retries', 0) == 0
                and all(type(stats.get(key, 0)) is int and 0 <= stats.get(key, 0) <= expected for key in counts)
                and sum(stats.get(key, 0) for key in counts) <= expected,
                'Harbor job accounting does not bind the scheduled cohort')
    else:
        require(result.get('finished_at') is not None, 'Harbor job did not finish')
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
    expected = {'version': runtime['agent_version'], 'reasoning_effort': runtime['effort']}
    if runtime.get('auth_mode') == ACCESS_MODE:
        expected['config_source'] = ACCESS_AGENT_CONFIG
    require(isinstance(config, dict) and config.get('name') == runtime['agent']
            and config.get('model_name') == runtime['model']
            and config.get('kwargs') == expected
            and config.get('extra_allowed_hosts', []) == (['chatgpt.com'] if runtime.get('auth_mode') == ACCESS_MODE else [])
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


def check_observation(experiment, arm, trial, run_sha256, *, bounded=False, expected_trace=None,
                      expected_thread=None):
    path = safe_path(trial, OBSERVATION_PATH)
    raw = access_bytes(path) if bounded else path.read_bytes()
    exposure = parse_json(raw, 'exposure observation')
    extras = () if expected_thread is None else ('trial', 'trial_id', 'thread_id')
    fields(exposure, ('schema', 'arm', 'case_sha256', 'run_sha256', 'instructions',
                      'trajectory', 'evidence', *extras), 'exposure observation')
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
    def artifact(reference, label):
        if not bounded:
            return verify_ref(trial, reference, label)
        fields(reference, ('path', 'sha256'), label)
        artifact_path = safe_path(trial, reference['path'])
        require(digest(access_bytes(artifact_path)) == reference['sha256'], 'private observation hash mismatch')
        return artifact_path

    trace = artifact(exposure['trajectory'], 'raw trajectory')
    require(expected_trace is None or trace == expected_trace, 'observation names a different native trajectory')
    require(trace != path and trace.stat().st_size > 0,
            'raw trajectory is empty or is the exposure observation')
    evidence = array(exposure['evidence'], 'exposure evidence')
    require(not bounded or len(evidence) <= 32, 'too many private observation references')
    evidence_paths = {artifact(ref, 'exposure evidence') for ref in evidence}
    require(len(evidence_paths) == len(evidence), 'duplicate exposure evidence')
    if expected_thread is not None:
        result = parse_json(access_bytes(safe_path(trial, 'result.json')), 'observed trial')
        trial_id = uuid_string(result.get('id'), 'trial id')
        require(exposure['trial'] == trial.name and exposure['trial_id'] == trial_id
                and exposure['thread_id'] == expected_thread,
                'exposure observation does not bind this trial and native thread')
        witness_path = safe_path(trial, 'artifacts/approved/exposure.json')
        require(witness_path in evidence_paths, 'exposure witness was not verified')
        witness = parse_json(access_bytes(witness_path), 'native exposure witness')
        require(isinstance(witness, dict) and witness.get('run_sha256') == run_sha256 and witness.get('trial') == trial.name
                and witness.get('trial_id') == trial_id
                and witness.get('thread_id') == expected_thread and (not bounded
                    or witness.get('raw_rollout_sha256') == exposure['trajectory']['sha256']),
                'native witness does not bind this acquisition and trial')
    return {'path': OBSERVATION_PATH, 'sha256': digest(raw)}, exposure['trajectory']['sha256']


def check_trial_result_envelope(result, native_trial, staged, *, projected=False):
    require(isinstance(result, dict), 'Harbor trial result must be an object')
    trial_id = uuid_string(result.get('id'), 'trial id')
    require(result.get('trial_name') == native_trial.name and result.get('trial_uri') == native_trial.as_uri(),
            'trial result does not bind its direct trial location')
    text(result.get('task_name'), 'trial task name')
    require(result.get('task_id') == {'path': str(staged)}, 'trial task identity mismatch')
    matches(result.get('task_checksum'), r'[0-9a-f]{64}', 'trial task checksum')
    config = result.get('config')
    require(isinstance(config, dict) and config.get('trial_name') == native_trial.name
            and config.get('trials_dir') == str(native_trial.parent)
            and all(isinstance(config.get(field), dict) for field in ('task', 'agent', 'verifier')),
            'invalid Harbor trial config envelope')
    uuid_string(config.get('job_id'), 'trial config job id')
    agent = result.get('agent_info')
    require(isinstance(agent, dict), 'invalid Harbor trial agent info')
    text(agent.get('name'), 'trial agent name')
    text(agent.get('version'), 'trial agent version')
    require('exception_info' in result, 'trial lacks exception metadata')
    exception = result['exception_info']
    if exception is not None:
        required = ('exception_type', 'occurred_at')
        fields(exception, required if projected else (*required, 'exception_message', 'exception_traceback'), 'trial exception')
        require(all(isinstance(value, str) for value in exception.values()), 'invalid Harbor trial exception')
    for field in ('agent_result', 'verifier_result', 'agent_execution'):
        require(result.get(field) is None or isinstance(result[field], dict), 'invalid Harbor trial result field')
    return trial_id


def check_trial(experiment, arm, trial, directory, expected_checksum, job_id, result, result_sha256):
    staged = directory / 'staged' / staged_name(experiment, directory)
    run_sha256 = experiment.run_sha256(arm, directory)
    verifier_env = experiment.verifier_env(arm, run_sha256)
    trial_id = uuid_string(result.get('id'), 'trial id')
    native_trial = directory / 'jobs' / arm / trial.name
    if experiment.runtime.get('auth_mode') == ACCESS_MODE:
        check_trial_result_envelope(result, native_trial, staged, projected=True)
    require(result.get('trial_name') == trial.name and result.get('trial_uri') == native_trial.as_uri(),
            'trial result does not bind its direct trial location')
    require(result.get('task_name') == (experiment.task_names[arm] or staged.name)
            and result.get('task_id') == {'path': str(staged)}
            and result.get('task_checksum') == expected_checksum,
            'trial task identity or checksum mismatch')
    config = result.get('config')
    require(isinstance(config, dict) and config.get('trial_name') == trial.name
            and config.get('trials_dir') == str(native_trial.parent)
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

    if experiment.runtime.get('auth_mode') != ACCESS_MODE:
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
    completion = None
    if experiment.runtime.get('auth_mode') == ACCESS_MODE:
        from harbor_codex_completion import CLI_USAGE_FIELDS, PUBLIC_RECEIPT
        from harbor_codex_egress import INFERENCE_HOST, RECEIPT

        network = read_object(safe_path(trial, RECEIPT), 'live inference Docker proof')
        fields(network, ('project', 'main', 'sidecar', 'allowed_host'), 'live inference Docker proof')
        require(network['project'] == trial.name.lower() + '__env' and network['main'] != network['sidecar']
                and network['allowed_host'] == INFERENCE_HOST,
                'live inference Docker proof does not bind this trial')
        for identity in ('main', 'sidecar'):
            matches(network[identity], r'[a-f0-9]{64}', 'live inference Docker identity')

        completion = read_object(safe_path(trial, f'agent/{PUBLIC_RECEIPT}'), 'native completion proof')
        fields({key: value for key, value in completion.items() if key != 'usage'},
               ('verified', 'thread_id', 'raw_observation_verified', 'first_turn'),
               'native completion proof')
        if 'usage' in completion:
            usage = completion['usage']
            require(isinstance(usage, dict) and usage and usage.keys() <= set(CLI_USAGE_FIELDS)
                    and all(type(count) is int and count >= 0 for count in usage.values()), 'invalid native usage')
        require(completion['verified'] is True, 'native Codex completion was not verified')
        require(completion['raw_observation_verified'] is True, 'raw exposure observation was not verified')
        uuid_string(completion['thread_id'], 'native Codex thread')

    verifier = result.get('verifier_result')
    require(isinstance(verifier, dict), 'trial lacks a verifier result')
    rewards = verifier.get('rewards')
    deferred = completion is not None
    fields(rewards, ('exposure_verified',) if deferred else REWARDS, 'verifier rewards')
    for key, value in rewards.items():
        require(type(value) in (int, float) and value in (0, 1), f'invalid binary reward {key}')
    require(rewards['exposure_verified'] == 1 and (deferred or rewards['valid'] == 1),
            'verifier did not validate trial setup and exposure')
    observation, trajectory_sha = check_observation(experiment, arm, trial, run_sha256,
                                                     expected_thread=completion['thread_id'] if completion else None)
    if completion is not None:
        control = access_bytes(safe_path(experiment.tasks[arm], 'environment/workspace/AGENTS.md'))
        prompt = access_bytes(safe_path(experiment.tasks[arm], 'instruction.md'))
        first_turn = completion['first_turn']
        fields(first_turn, ('turn_id', 'instructions', 'task_input', 'instructions_sha256', 'task_input_sha256',
                            'raw_rollout_sha256', 'scoring_sha256'), 'first-turn exposure receipt')
        witness = read_object(safe_path(trial, 'artifacts/approved/exposure.json'), 'observed exposure witness')
        require(first_turn.get('scoring_sha256') == trajectory_sha
                and first_turn.get('raw_rollout_sha256') == witness.get('raw_rollout_sha256')
                and first_turn['turn_id'] == witness.get('first_turn', {}).get('turn_id')
                and all(first_turn[key] == witness['first_turn'][key] for key in ('instructions', 'task_input'))
                and digest(control) == first_turn['instructions_sha256'] and digest(prompt) == first_turn['task_input_sha256'],
                'native first-turn instructions were not observed')
    return {
        'trial_id': trial_id,
        'trajectory_sha256': trajectory_sha,
        **({'native_thread_id': completion['thread_id']}
           if completion else {}),
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
        **({'native_completion': completion} if completion is not None else {}),
    }


def collects_fixture_ledger(task_config):
    return any(isinstance(entry, dict) and entry.get('destination') == FIXTURE_EVIDENCE.removeprefix('artifacts/')
               for entry in task_config.get('artifacts', ()))


def semantic_fixture_required(experiment, arm):
    if 'task.toml' not in experiment.inventories[arm]:
        return False
    config = tomllib.loads(safe_path(experiment.tasks[arm], 'task.toml').read_text(encoding='utf-8'))
    return collects_fixture_ledger(config)


def bound_semantic_verdict(record, row, detector_sha, trace, *, fixture_log=None, fixture_required=False):
    base = ('trial_id', 'result_sha256', 'trajectory_sha256', 'detector_sha256', 'verdict', 'evidence_lines', 'metrics')
    fields(record, (*base, 'fixture_evidence') if 'fixture_evidence' in record else base, 'independent semantic verdict')
    require(record['trial_id'] == row['trial_id'] and record['result_sha256'] == row['exposure']['result_sha256']
            and record['trajectory_sha256'] == row['trajectory_sha256'] and record['detector_sha256'] == detector_sha,
            'semantic verdict identities do not match released evidence')
    data = access_bytes(trace)
    require(digest(data) == row['trajectory_sha256'], 'semantic evidence trajectory changed')
    lines = array(record['evidence_lines'], 'semantic evidence lines')
    require(0 < len(lines) <= 32 and all(type(line) is int and 0 < line <= data.count(b'\n') for line in lines)
            and lines == sorted(set(lines)), 'semantic evidence lines are invalid')
    require(not fixture_required or 'fixture_evidence' in record, 'required fixture evidence was not cited')
    if 'fixture_evidence' in record:
        fixture = record['fixture_evidence']
        fields(fixture, ('sha256', 'lines'), 'independent fixture evidence')
        require(fixture_log is not None, 'no released fixture event log for cited evidence')
        raw = access_bytes(fixture_log)
        fixture_lines = array(fixture['lines'], 'semantic fixture evidence lines', nonempty=False)
        require(fixture['sha256'] == digest(raw) and len(fixture_lines) <= 32
                and (bool(fixture_lines) if raw else not fixture_lines)
                and all(type(line) is int and 0 < line <= raw.count(b'\n') for line in fixture_lines)
                and fixture_lines == sorted(set(fixture_lines)), 'semantic fixture evidence does not match release')
    require(record['verdict'] == 'VALID', 'independent grading did not establish semantic validity')
    metrics = record['metrics']
    fields(metrics, SEMANTIC_METRICS, 'independent semantic metrics')
    require(all(type(value) is int and value in (0, 1) for value in metrics.values()), 'invalid binary semantic metric')
    return metrics


def semantic_cohort(path, experiment, arm, launch_sha):
    data = access_bytes(path)
    content = parse_json(data, 'independent semantic cohort')
    fields(content, ('schema', 'case_sha256', 'arm', 'launch_sha256', 'adjudicator', 'trials'),
           'independent semantic cohort')
    require(content['schema'] == 'harbor-semantic-cohort.v1' and content['case_sha256'] == experiment.case_sha256
            and content['arm'] == arm and content['launch_sha256'] == launch_sha, 'semantic cohort does not bind this run')
    matches(content['adjudicator'], r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}', 'independent adjudicator identity')
    trials = array(content['trials'], 'independent semantic trials', nonempty=False)
    rows, ambiguous = {}, set()
    for trial in trials:
        try:
            require(isinstance(trial, dict), 'semantic verdict is not an object')
            identity = uuid_string(trial.get('trial_id'), 'semantic trial identity')
        except ValueError:
            continue
        if identity in rows or identity in ambiguous:
            rows.pop(identity, None)
            ambiguous.add(identity)
        else:
            rows[identity] = trial
    return rows, {'path': str(path), 'sha256': digest(data), 'adjudicator': content['adjudicator']}, len(trials) - len(rows)


def trial_reports(experiment, arm, directory, native_dir, job_sha, errors, *, adjudications=None):
    staged = native_dir / 'staged' / staged_name(experiment, native_dir)
    try:
        job = safe_path(directory, f'jobs/{arm}', directory=True)
    except (OSError, ValueError):
        errors.append('Harbor job directory is missing or unsafe')
        return [], []
    if job_sha is None or tree_hash_if_available(job) != job_sha:
        errors.append('Harbor job output inventory is missing or changed')
    try:
        bindings = experiment.verifier_env(arm, experiment.run_sha256(arm, native_dir))
        job_id = check_job(experiment, arm, job, native_dir / 'jobs' / arm, staged, bindings)
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
            if experiment.runtime.get('auth_mode') == ACCESS_MODE and (trial / 'access-withheld.json').exists():
                withheld = read_object(safe_path(trial, 'access-withheld.json'), 'withheld trial')
                fields(withheld, ('result_present',), 'withheld trial')
                require(type(withheld['result_present']) is bool, 'invalid withheld trial marker')
                row.update(status='WITHHELD', result_withheld=withheld['result_present'])
                row['errors'].append('trial artifacts did not pass safe release')
                continue
            relative = f'{trial.name}/result.json'
            path = safe_path(job, relative)
            data = access_bytes(path) if experiment.runtime.get('auth_mode') == ACCESS_MODE else path.read_bytes()
            row['result_path'] = relative
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
            row.update(check_trial(experiment, arm, trial, native_dir, checksum, job_id, result,
                                   row['result_sha256']))
            if experiment.runtime.get('auth_mode') == ACCESS_MODE:
                require(PRIVATE_DETECTOR in experiment.inventories[arm], 'frozen detector is missing')
                fixture_required = semantic_fixture_required(experiment, arm)
                fixture_log = safe_path(trial, FIXTURE_EVIDENCE) if fixture_required else None
                require(adjudications is not None and row['trial_id'] in adjudications,
                        'independent semantic verdict not delivered')
                grade = adjudications[row['trial_id']]
                evidence = read_object(safe_path(trial, OBSERVATION_PATH), 'released exposure observation')
                trace = safe_path(trial, evidence['trajectory']['path'])
                if fixture_log is None and 'fixture_evidence' in grade:
                    fixture_log = safe_path(trial, FIXTURE_EVIDENCE)
                metrics = bound_semantic_verdict(grade, row, experiment.inventories[arm][PRIVATE_DETECTOR]['sha256'], trace,
                                                 fixture_log=fixture_log, fixture_required=fixture_required)
                row['rewards'].update({'valid': 1, **metrics})
                row['semantic_evidence_lines'] = grade['evidence_lines']
                if 'fixture_evidence' in grade:
                    row['semantic_fixture_evidence'] = grade['fixture_evidence']
            row['valid'] = True
        except (OSError, ValueError) as exc:
            row['errors'].append(str(exc))
    ids = Counter(row['trial_id'] for row in reports if row['trial_id'] is not None
                  and (experiment.runtime.get('auth_mode') != ACCESS_MODE or 'exposure' in row))
    observations = Counter(row['exposure']['observation']['sha256']
                           for row in reports if 'exposure' in row)
    trajectories = Counter(row['trajectory_sha256'] for row in reports if 'exposure' in row)
    threads = Counter(row['native_thread_id'] for row in reports if 'native_thread_id' in row)
    for row in reports:
        if ids[row['trial_id']] > 1:
            row['valid'] = False
            row['errors'].append('duplicate trial id')
        if 'exposure' in row:
            if observations[row['exposure']['observation']['sha256']] > 1:
                row['valid'] = False
                row['errors'].append('duplicate exposure observation')
            if trajectories[row['trajectory_sha256']] > 1 or threads[row.get('native_thread_id')] > 1:
                row['valid'] = False
                row['errors'].append('duplicate native trajectory')
    return reports, unexpected


def assess(experiment, arm, directory, adjudication_path=None):
    directory = resolve_input(directory, directory=True)
    protected = [directory]
    raw = safe_path(directory, 'launch.json').read_bytes()
    launch = parse_json(raw, 'launch')
    require(isinstance(launch, dict), 'launch record must be an object')
    if experiment.runtime.get('auth_mode') == ACCESS_MODE and launch.get('schema') == 'experiment-access-failure.v1':
        withheld = launch.get('withheld_trials')
        expected = access_failure_record(experiment, arm, directory, launch.get('status'), withheld,
                                         launch.get('private_recovery_id'))
        require(launch == expected, 'access failure receipt does not bind this run')
        expected_trials = experiment.trials[arm]
        return ({'schema': COLLECTION_SCHEMA, 'status': 'INCOMPLETE', 'run_dir': str(directory),
                 'launch_sha256': digest(raw), 'manifest_sha256': experiment.manifest_sha256,
                 'case_sha256': experiment.case_sha256, 'incident_id': experiment.incident_id,
                 'incident_kind': experiment.incident_kind, 'arm': arm, 'runtime': experiment.runtime,
                 'expected_trials': expected_trials, 'observed_trials': withheld, 'valid_trials': 0,
                 'missing_trials': None if withheld is None else expected_trials - withheld,
                 'invalid_trials': withheld,
                 'withheld_trials': withheld,
                 'incident_failures': 0, 'task_completions': 0, 'regression_failures': 0,
                 'trials': [{'sealed_result_ordinal': ordinal, 'valid': False, 'status': 'WITHHELD'}
                            for ordinal in range(1, (withheld or 0) + 1)], 'run_errors': [launch['status']]}, protected)
    native_dir = directory
    if experiment.runtime.get('auth_mode') == ACCESS_MODE and launch.get('schema') == LAUNCH_SCHEMA:
        native_path = text(launch.get('run_dir'), 'native acquisition path')
        require(re.fullmatch(r'/dev/shm/harbor-codex-[A-Za-z0-9_-]+/acquisition-[a-f0-9]{32}', native_path)
                and launch.get('retained_root') == str(directory), 'access release path binding mismatch')
        native_dir = Path(native_path)
    run_sha256 = experiment.run_sha256(arm, native_dir)
    require(isinstance(launch, dict) and launch.get('schema') == LAUNCH_SCHEMA
            and launch.get('run_dir') == str(native_dir) and launch.get('run_sha256') == run_sha256
            and launch.get('arm') == arm and launch.get('runtime') == experiment.runtime
            and launch.get('manifest_sha256') == experiment.manifest_sha256
            and launch.get('case_sha256') == experiment.case_sha256,
            'launch record does not bind this run, manifest, arm and runtime')
    records = list(experiment.inventories[arm].values())
    task_sha = digest(canonical(records))
    argv = array(launch.get('argv'), 'launch argv')
    local = experiment.runtime.get('auth_mode') == ACCESS_MODE
    executable_index = len(ACCESS_PYTHON_FLAGS) + 1 if local else 0
    require(len(argv) > executable_index, 'launch argv is incomplete')
    executable = text(argv[executable_index], 'recorded Harbor executable')
    command_prefix = [str(Path(executable).parent / 'python'), *ACCESS_PYTHON_FLAGS] if local else []
    require(Path(executable).is_absolute() and argv == experiment.argv(arm, native_dir, executable,
                                                                        command_prefix=command_prefix)
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
            baseline_receipt = parse_baseline_receipt(experiment, data)
            protected.append(Path(baseline_receipt['run_dir']).resolve())
            baseline_report = validate_baseline(experiment, baseline_receipt)
            baseline_trajectories = {row['trajectory_sha256'] for row in baseline_report['trials']}
        except (OSError, ValueError) as exc:
            errors.append(str(exc))
    status_and_exit = launch.get('status'), launch.get('exit_code')
    complete = status_and_exit == ('SUCCEEDED', 0) and type(status_and_exit[1]) is int
    partial = (local and status_and_exit[0] in {'FAILED', 'TIMED_OUT', 'INTERRUPTED'}
               and (status_and_exit[1] is None or type(status_and_exit[1]) is int))
    if (not (complete or partial) or launch.get('cleanup') != ('docker_sealed' if local else 'harbor_completed')
            or launch.get('harbor_version') != experiment.runtime['harbor_version']):
        errors.append('launch failed, did not finish or has unverified cleanup')
    if (launch.get('staged_before') != records or launch.get('staged_after') != records
            or (not local and staged_inventory(directory, staged_name(experiment, native_dir)) != records)
            or (local and ((directory / 'staged').exists() or (directory / 'staged').is_symlink()))):
        errors.append('staged task inputs were missing or changed')
    setup_trials = set()
    if experiment.runtime.get('auth_mode') == ACCESS_MODE:
        try:
            require(launch.get('harbor_install_sha256') == experiment.harbor_install_sha256,
                    'released Harbor installation identity mismatch')
            require(launch.get('docker_client_sha256') == experiment.docker_client_sha256
                    and launch.get('egress_image_id') == experiment.egress_image_id,
                    'released Docker runtime identity mismatch')
            require(launch.get('release_status') in ('COMPLETE', 'INCOMPLETE'), 'missing cohort release status')
            resources = launch.get('docker_sealed_resources')
            job = directory / 'jobs' / arm
            require(launch.get('docker_scope') == staged_name(experiment, native_dir) + '__'
                    and isinstance(resources, dict) and resources.keys() <= {
                        'container', 'trial_projects', 'network', 'volume', 'eligible_trials', 'started_trials'}
                    and all(type(count) is int and count >= 0 for key, count in resources.items()
                            if key not in ('eligible_trials', 'started_trials')), 'Docker seal receipt is incomplete')
            eligible = array(resources.get('eligible_trials'), 'sealed trial identities', nonempty=False)
            require(all(isinstance(item, str) and item.lower().startswith(launch['docker_scope'])
                        and len(relative_parts(item)) == 1 for item in eligible)
                    and eligible == sorted(set(eligible))
                    and len(eligible) <= resources.get('trial_projects', -1) <= experiment.trials[arm]
                    and 4 * len(eligible) <= resources.get('container', 0)
                    and all(path.parent.name in eligible for path in job.glob('*/result.json')),
                    'Docker seal does not bind every released result')
            setup_starts = array(resources.get('started_trials'), 'setup trial identities', nonempty=False)
            require(all(isinstance(item, str) and item.startswith(launch['docker_scope'])
                        and len(relative_parts(item)) == 1 and item == item.lower() for item in setup_starts)
                    and setup_starts == sorted(set(setup_starts))
                    and len(setup_starts) <= resources['trial_projects'], 'invalid trial start receipts')
            setup_trials = set(setup_starts)
            require(access_capture_hashes(directory) == launch.get('capture_sha256'), 'released captures changed')
            jobs = directory / 'jobs'
            require(not jobs.is_symlink() and (not jobs.exists() or all(path.name == arm for path in jobs.iterdir())),
                    'unexpected retained job scope')
        except (OSError, ValueError):
            errors.append('released Docker seal, captures or job scope could not be verified')
    adjudication_ref = None
    ignored_grades = 0
    report_options = {}
    if adjudication_path is not None:
        require(local and PRIVATE_DETECTOR in experiment.inventories[arm],
                'independent semantic grading requires a staged private detector')
        grade_path = resolve_input(adjudication_path)
        require(not grade_path.is_relative_to(directory), 'semantic cohort must be outside the sealed release')
        grading, adjudication_ref, ignored_grades = semantic_cohort(grade_path, experiment, arm, digest(raw))
        protected.append(grade_path)
        report_options['adjudications'] = grading
    reports, unexpected = trial_reports(experiment, arm, directory, native_dir, launch.get('job_sha256'), errors,
                                        **report_options)
    if report_options:
        ignored_grades += len(set(grading) - {row['trial_id'] for row in reports})
    expected = experiment.trials[arm]
    observed = sum(row['result_path'] is not None or row.get('result_withheld', False) for row in reports)
    if local:
        for row in reports:
            row['setup_started'] = row['trial_name'].lower() in setup_trials
            row['native_start_verified'] = row.get('native_completion', {}).get('verified') is True
            observed += row['setup_started'] and row['result_path'] is None and not row.get('result_withheld', False)
        for missing_result in sorted(setup_trials - {row['trial_name'].lower() for row in reports}):
            reports.append({'trial_name': missing_result, 'trial_id': None, 'result_path': None, 'result_sha256': None,
                            'setup_started': True, 'native_start_verified': False, 'valid': False,
                            'errors': ['setup started without released trial records']})
            observed += 1
    if observed > expected:
        errors.append('observed trial cohort exceeds scheduled size')
        observed = None
    for row in reports:
        if row.get('trajectory_sha256') in baseline_trajectories:
            row['valid'] = False
            row['errors'].append('native trajectory was reused from the baseline')
        if errors:
            row['valid'] = False
            row['errors'].append('run evidence is incomplete')
    valid = [row for row in reports if row['valid']]
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
    report = {
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
        'missing_trials': expected - observed if observed is not None else None,
        'valid_trials': len(valid),
        'invalid_trials': observed - len(valid) if observed is not None else None,
        'incident_failures': counts['incident_failure'],
        'task_completions': counts['task_completed'],
        'regression_failures': counts['regression_failed'],
        'trials': reports,
        'unexpected_results': unexpected,
        'run_errors': errors,
    }
    if experiment.runtime.get('auth_mode') == ACCESS_MODE:
        report['withheld_trials'] = sum(row.get('result_withheld', False) for row in reports)
        report['setup_starts'] = len(setup_trials) if not errors else None
        report['minimum_verified_subject_starts'] = sum(row['native_start_verified'] for row in reports) if not errors else 0
    if adjudication_ref is not None:
        report['adjudications'] = adjudication_ref
        report['ignored_adjudication_rows'] = ignored_grades
    return report, protected


def parse_baseline_receipt(experiment, raw):
    receipt = parse_json(raw, 'baseline receipt')
    require(isinstance(receipt, dict) and receipt.get('schema') == COLLECTION_SCHEMA
            and receipt.get('arm') == 'baseline' and receipt.get('status') == 'REPRODUCED'
            and receipt.get('manifest_sha256') == experiment.manifest_sha256,
            'treatment requires a REPRODUCED baseline receipt for the same manifest')
    directory = text(receipt.get('run_dir'), 'baseline run directory')
    require(Path(directory).is_absolute(), 'baseline run directory must be absolute')
    return receipt


def validate_baseline(experiment, receipt):
    grade = receipt.get('adjudications')
    if grade is not None:
        fields(grade, ('path', 'sha256', 'adjudicator'), 'baseline semantic cohort reference')
    actual, _ = assess(experiment, 'baseline', receipt['run_dir'], grade['path'] if grade else None)
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
    runner.add_argument('--codex-auth-file', type=Path)
    runner.add_argument('--expected-account-fd', type=int)
    collector.add_argument('--run', required=True, type=Path)
    collector.add_argument('--adjudications', type=Path)
    snap = sub.add_parser('snapshot')
    snap.add_argument('--repo', required=True)
    snap.add_argument('--commit', required=True)
    snap.add_argument('--output', required=True)
    snap.add_argument('--selection', type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == 'snapshot':
            selection = None if args.selection is None else read_object(args.selection, 'source selection')
            print(json.dumps(snapshot(args.repo, args.commit, args.output, selection), sort_keys=True))
        else:
            experiment = Experiment(args.manifest)
            if args.command == 'plan':
                print(json.dumps(plan(experiment), sort_keys=True, indent=2))
            elif args.command == 'run':
                prior = signal.signal(signal.SIGTERM, interrupt)
                try:
                    launch = run(experiment, args.arm, args.output, args.baseline,
                                 auth_file=args.codex_auth_file, account_fd=args.expected_account_fd)
                finally:
                    signal.signal(signal.SIGTERM, prior)
                summary = {'status': launch['status'], 'run_dir': launch['run_dir']}
                if 'release_status' in launch:
                    summary['release_status'] = launch['release_status']
                    summary['verified_native_trials'] = launch['verified_native_trials']
                print(json.dumps(summary))
                return int(launch['status'] != 'SUCCEEDED' or launch.get('release_status', 'COMPLETE') != 'COMPLETE'
                           or launch.get('verified_native_trials', experiment.trials[args.arm])
                           != experiment.trials[args.arm])
            else:
                result, protected = assess(experiment, args.arm, args.run, args.adjudications)
                output = new_output(experiment, args.output, outside=protected)
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
