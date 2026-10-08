#!/usr/bin/env python3
"""Plan/apply selected shared packages; all local runtime links share one source."""
import argparse
import hashlib
import json
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ROOTS = ('.codex', '.agents')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_private_json(path, value, *, exclusive=False):
    # Set privacy at creation, rather than exposing data before a later chmod.
    # Opening an existing receipt retains any more restrictive existing mode.
    flags = os.O_WRONLY | os.O_CREAT | (os.O_EXCL if exclusive else os.O_TRUNC)
    flags |= getattr(os, 'O_NOFOLLOW', 0)
    with os.fdopen(os.open(path, flags, 0o600), 'w') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


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


def plan(home, undo):
    manifest = source_manifest()
    for p in (home, undo):
        unlinked_ancestors(p)
        if p.is_symlink():
            raise ValueError('Linked root refused')
    if not home.is_dir() or undo.exists():
        raise ValueError('Home must exist; undo must be new')
    if undo == home or undo in home.parents or any(
            part in ('.claude', '.codex', '.agents') for part in undo.parts):
        raise ValueError('Use a separate private undo directory')
    canonical = home / '.claude/skills'
    unlinked_ancestors(canonical / 'placeholder')
    # Activation never writes canonical content. Reconcile source updates separately.
    for name in manifest['skills']:
        live = canonical / name
        if live.is_symlink() or not (live / 'SKILL.md').is_file():
            raise ValueError(f'Missing or linked live canonical package: {name}')
        for rel, sha in manifest['files'].items():
            if Path(rel).parts[0] == name:
                target = canonical / rel
                unlinked_ancestors(target)
                if target.is_symlink() or not target.is_file() or digest(target) != sha:
                    raise ValueError(f'Reconcile reviewed source with live canonical file first: {rel}')
    targets = []
    for runtime in ROOTS:
        for name in manifest['skills']:
            dest = home / runtime / 'skills' / name
            unlinked_ancestors(dest)
            targets.append({'path': str(dest), 'name': name, 'before': snapshot(dest)})
    return {'format': 'shared-live-plan-v1', 'home': str(home),
            'canonical_before': {name: snapshot(canonical / name) for name in manifest['skills']},
            'undo': str(undo), 'manifest': manifest, 'targets': targets}


def apply(saved):
    # Reconstruct destinations from fixed roots and verified names, not plan-supplied paths.
    fresh = plan(Path(saved['home']), Path(saved['undo']))
    if saved != fresh:
        raise ValueError('Plan/source/destination drift; review a new plan')
    canonical = Path(saved['home']) / '.claude/skills'
    undo = Path(saved['undo'])
    # Private before a receipt or any original discovery entry is moved here.
    # Preimage permissions remain unchanged inside this restrictive directory.
    undo.mkdir(mode=0o700, parents=True)
    receipt = dict(saved, status='applying', changed=[])
    receipt_path = undo / 'receipt.json'
    write_private_json(receipt_path, receipt, exclusive=True)
    for i, entry in enumerate(saved['targets']):
        dest = Path(entry['path'])
        unlinked_ancestors(dest)
        if snapshot(dest) != entry['before']:
            raise ValueError('Destination changed during apply; preserve receipt for recovery')
        dest.parent.mkdir(parents=True, exist_ok=True)
        backup = undo / str(i)
        target = canonical / entry['name']
        if snapshot(target) != saved['canonical_before'][entry['name']]:
            raise ValueError('Live source changed during apply; preserve receipt for recovery')
        operation = {'path': str(dest), 'backup': str(backup), 'target': str(target), 'state': 'pending'}
        receipt['changed'].append(operation)
        write_private_json(receipt_path, receipt)
        if dest.exists() or dest.is_symlink():
            dest.rename(backup)
        dest.symlink_to(target, target_is_directory=True)
        operation['state'] = 'linked'
        write_private_json(receipt_path, receipt)
    if source_manifest() != saved['manifest']:
        raise ValueError('Reviewed source changed during apply; preserve receipt for recovery')
    for name in saved['manifest']['skills']:
        target = canonical / name
        unlinked_ancestors(target)
        if snapshot(target) != saved['canonical_before'][name]:
            raise ValueError('Live source changed during apply; preserve receipt for recovery')
    for entry in receipt['changed']:
        dest = Path(entry['path'])
        unlinked_ancestors(dest)
        if not dest.is_symlink() or os.readlink(dest) != entry['target']:
            raise ValueError('Direct link verification failed; preserve receipt for recovery')
    receipt['status'] = 'bytes-and-direct-links-checked'
    receipt['verification_scope'] = 'Sequential non-atomic observations; concurrent writers are not locked out'
    write_private_json(receipt_path, receipt)
    return receipt_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home', type=Path)
    parser.add_argument('--undo', type=Path)
    parser.add_argument('--plan', type=Path)
    parser.add_argument('--apply', type=Path)
    args = parser.parse_args()
    if args.apply:
        print(apply(json.loads(args.apply.read_text())))
    else:
        if not all((args.home, args.undo, args.plan)):
            parser.error('Provide --home --undo --plan, or --apply PLAN')
        value = plan(args.home, args.undo)
        write_private_json(args.plan, value, exclusive=True)
        print(args.plan)


if __name__ == '__main__':
    main()
