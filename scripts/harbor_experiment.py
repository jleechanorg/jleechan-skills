#!/usr/bin/env python3
"""Export immutable historical inputs for Harbor skill experiments."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def inventory(root):
    records = []
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError('symlinks are unsupported')
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError('non-regular files are unsupported')
        records.append({'path': path.relative_to(root).as_posix(), 'sha256': digest(path.read_bytes()),
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


def main(argv=None):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    snap = sub.add_parser('snapshot')
    snap.add_argument('--repo', required=True)
    snap.add_argument('--commit', required=True)
    snap.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'snapshot':
            print(json.dumps(snapshot(args.repo, args.commit, args.output), sort_keys=True))
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
