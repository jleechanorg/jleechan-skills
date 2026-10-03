#!/usr/bin/env python3
"""Plan/apply selected shared packages; all local runtime links share one source."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil

REPO = Path(__file__).resolve().parents[1]
ROOTS = ('.claude', '.codex', '.agents')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def unlinked_ancestors(path):
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError('Absolute non-traversing path required')
    if any(p.is_symlink() for p in path.parents):
        raise ValueError('Linked ancestor refused')


def snapshot(path):
    if path.is_symlink():
        return {'link': os.readlink(path)}
    if not path.exists():
        return {'absent': True}
    if not path.is_dir():
        raise ValueError(f'Unexpected non-directory: {path}')
    entries = {}
    for p in sorted(path.rglob('*')):
        rel = str(p.relative_to(path))
        if p.is_symlink():
            entries[rel] = {'link': os.readlink(p)}
        elif p.is_file():
            entries[rel] = {'sha256': digest(p)}
        elif p.is_dir():
            entries[rel] = {'directory': True}
        else:
            raise ValueError('Special file refused')
    return {'entries': entries}


def source_manifest():
    manifest = json.loads((REPO / 'shared-skills.json').read_text())
    if manifest['format'] != 'jleechan-shared-skills-v1':
        raise ValueError('Unknown format')
    names = manifest['skills']
    if not names or len(names) != len(set(names)) or any(
            not n or Path(n).name != n or n in ('.', '..') for n in names):
        raise ValueError('Invalid selected names')
    actual = {}
    for name in names:
        root = REPO / '.claude/skills' / name
        if root.is_symlink() or not (root / 'SKILL.md').is_file():
            raise ValueError('Missing or linked source')
        for p in root.rglob('*'):
            if p.is_symlink():
                raise ValueError('Linked source refused')
            if p.is_file():
                actual[str(p.relative_to(REPO / '.claude/skills'))] = digest(p)
    if actual != manifest['files']:
        raise ValueError('Source inventory/hash mismatch')
    return manifest


def plan(home, package, undo):
    manifest = source_manifest()
    for p in (home, package, undo):
        unlinked_ancestors(p)
        if p.is_symlink():
            raise ValueError('Linked root refused')
    if not home.is_dir() or package.exists() or undo.exists():
        raise ValueError('Home must exist; package and undo must be new')
    if package == home or undo == home or package in undo.parents or undo in package.parents:
        raise ValueError('Overlapping package/undo refused')
    for p in (package, undo):
        if any(part in ROOTS for part in p.parts):
            raise ValueError('Use separate versioned package and undo roots')
    targets = []
    for runtime in ROOTS:
        for name in manifest['skills']:
            dest = home / runtime / 'skills' / name
            unlinked_ancestors(dest)
            targets.append({'path': str(dest), 'name': name, 'before': snapshot(dest)})
    return {'format': 'shared-plan-v1', 'home': str(home), 'package': str(package),
            'undo': str(undo), 'manifest': manifest, 'targets': targets}


def apply(saved):
    # Reconstruct destinations from fixed roots and verified names, not plan-supplied paths.
    fresh = plan(Path(saved['home']), Path(saved['package']), Path(saved['undo']))
    if saved != fresh:
        raise ValueError('Plan/source/destination drift; review a new plan')
    package, undo = Path(saved['package']), Path(saved['undo'])
    package.mkdir(parents=True)
    for name in saved['manifest']['skills']:
        shutil.copytree(REPO / '.claude/skills' / name, package / 'skills' / name)
    (package / 'manifest.json').write_text(json.dumps(saved['manifest'], indent=2)+'\n')
    for rel, sha in saved['manifest']['files'].items():
        if digest(package / 'skills' / rel) != sha:
            raise ValueError('Staged package changed')
    undo.mkdir(parents=True)
    receipt = dict(saved, status='applying', changed=[])
    receipt_path = undo / 'receipt.json'
    receipt_path.write_text(json.dumps(receipt, indent=2)+'\n')
    for i, entry in enumerate(saved['targets']):
        dest = Path(entry['path'])
        unlinked_ancestors(dest)
        if snapshot(dest) != entry['before']:
            raise ValueError('Destination changed during apply; preserve receipt for recovery')
        dest.parent.mkdir(parents=True, exist_ok=True)
        backup = undo / str(i)
        target = package / 'skills' / entry['name']
        operation = {'path': str(dest), 'backup': str(backup), 'target': str(target), 'state': 'pending'}
        receipt['changed'].append(operation)
        receipt_path.write_text(json.dumps(receipt, indent=2)+'\n')
        if dest.exists() or dest.is_symlink():
            dest.rename(backup)
        dest.symlink_to(target, target_is_directory=True)
        operation['state'] = 'linked'
        receipt_path.write_text(json.dumps(receipt, indent=2)+'\n')
    for entry in receipt['changed']:
        if Path(entry['path']).resolve() != Path(entry['target']).resolve():
            raise ValueError('Link verification failed')
    receipt['status'] = 'bytes-and-links-verified'
    receipt_path.write_text(json.dumps(receipt, indent=2)+'\n')
    return receipt_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home', type=Path)
    parser.add_argument('--package', type=Path)
    parser.add_argument('--undo', type=Path)
    parser.add_argument('--plan', type=Path)
    parser.add_argument('--apply', type=Path)
    args = parser.parse_args()
    if args.apply:
        print(apply(json.loads(args.apply.read_text())))
    else:
        if not all((args.home, args.package, args.undo, args.plan)):
            parser.error('Provide --home --package --undo --plan, or --apply PLAN')
        value = plan(args.home, args.package, args.undo)
        with args.plan.open('x') as stream:
            json.dump(value, stream, indent=2)
            stream.write('\n')
        print(args.plan)


if __name__ == '__main__':
    main()
