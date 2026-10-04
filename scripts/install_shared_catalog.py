#!/usr/bin/env python3
"""Update live canonical Claude packages with reversible consumer links.

Only skills are managed. Existing commands, credentials, settings, plugins,
archives, and host-only skill names are preserved. Canonical Claude packages
and curated cross-runtime derivatives remain distinct.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import uuid

TREES = ('.claude/skills', 'portable/skills', 'shared/aliases')
NOISE = {'__pycache__', '.pytest_cache', '.DS_Store'}

def hashes(root):
    result = {}
    for tree in TREES:
        for path in sorted((root / tree).rglob('*')):
            if any(part in NOISE for part in path.relative_to(root).parts):
                continue
            if path.is_symlink():
                raise ValueError(f'Source symlinks are not portable: {path}')
            if path.is_file():
                result[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result

def targets(root):
    root = Path(root).absolute()
    packages = {}
    # Check every source boundary before following SKILL.md or choosing a variant.
    for tree in TREES:
        directory = root / tree
        for boundary in [directory, *directory.parents]:
            if (boundary == root or root in boundary.parents) and boundary.is_symlink():
                raise ValueError(f'Linked source tree refused: {boundary}')
        entries = list(directory.iterdir())
        for package in entries:
            if package.is_symlink():
                raise ValueError(f'Linked source package refused: {package}')
        packages[tree] = entries
    canonical = {p.name: '.claude/skills/' + p.name for p in packages['.claude/skills']
                 if (p / 'SKILL.md').is_file() and not p.name.startswith(('.', '_'))}
    retained = json.loads((root / 'shared/retain-local.json').read_text())
    canonical = {n: rel for n, rel in canonical.items() if n not in retained}
    agents = dict(canonical)
    for tree in ('portable/skills', 'shared/aliases'):
        for p in packages[tree]:
            if (p / 'SKILL.md').is_file():
                agents[p.name] = tree + '/' + p.name
    return {'claude': canonical, 'agents': agents}

def release_path(home, release):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', release):
        raise ValueError('release must be one safe directory name')
    return home / '.local/state/jleechan-shared-skills' / release

def live_targets(root):
    mapping = targets(root)
    # Existing Claude names own their workflow. Portable variants never silently
    # replace same-name canonical instructions; aliases fill only missing names.
    retained = json.loads((root / 'shared/retain-local.json').read_text())
    merged = dict(mapping['claude'])
    for name, rel in mapping['agents'].items():
        if name not in retained:
            merged.setdefault(name, rel)
    return merged

def verify(home, release):
    receipt = json.loads((release_path(home, release) / 'receipt.json').read_text())
    errors = []
    canonical = home / '.claude/skills'
    for name, files in receipt['managed'].items():
        root = canonical / name
        if root.is_symlink():
            errors.append(f'canonical package must be live: {name}')
        for rel, sha in files.items():
            p = root / rel
            if not p.is_file() or p.is_symlink() or hashlib.sha256(p.read_bytes()).hexdigest() != sha:
                errors.append(f'live content mismatch: {name}/{rel}')
        link = home / '.agents/skills' / name
        if not link.is_symlink() or link.resolve() != root.resolve():
            errors.append(f'discovery mismatch: agents/{name}')
    for relative in receipt.get('retired', {}):
        p = canonical / relative
        if p.exists() or p.is_symlink():
            errors.append(f'retired managed file remains live: {relative}')
    for name in receipt.get('retired_packages', []):
        p = home / '.agents/skills' / name
        if p.exists() or p.is_symlink():
            errors.append(f'retired consumer remains live: {name}')
    return errors

def install(source, home, release, baseline=None):
    source, home = Path(source).absolute(), Path(home).absolute()
    if home.is_symlink():
        raise ValueError('Linked home refused')
    home = home.resolve()
    undo = release_path(home, release)
    if any(p.is_symlink() for p in [undo, *undo.parents]):
        raise ValueError('Linked undo path refused')
    if undo.exists():
        raise FileExistsError(undo)
    mapping = live_targets(source)
    previous = baseline or {}
    actions, managed, updates, removals, retired_consumers = [], {}, [], [], []
    retired_files = {}
    retained = json.loads((source / 'shared/retain-local.json').read_text())
    retired_names = sorted(set(previous) - set(mapping) - set(retained))
    # Validate every selected preimage before any mutation. A reviewed previous
    # receipt authorizes updating owned bytes, never divergent local additions.
    for runtime in ('.claude', '.agents'):
        root = home / runtime / 'skills'
        if any(p.is_symlink() for p in [home, root, *root.parents]):
            raise ValueError(f'Review symlinked discovery root: {root}')
    for name, rel in mapping.items():
        dest = home / '.claude/skills' / name
        if dest.is_symlink():
            raise ValueError(f'Reconcile linked canonical package first: {name}')
        files = {}
        for src in sorted((source / rel).rglob('*')):
            if any(part in NOISE for part in src.relative_to(source / rel).parts):
                continue
            if src.is_symlink():
                raise ValueError(f'Linked source refused: {src}')
            if not src.is_file():
                continue
            relative = str(src.relative_to(source / rel))
            target = dest / relative
            if target.is_symlink() or any(p.is_symlink() for p in target.parents):
                raise ValueError(f'Linked live file refused: {name}/{relative}')
            sha = hashlib.sha256(src.read_bytes()).hexdigest()
            old = hashlib.sha256(target.read_bytes()).hexdigest() if target.is_file() else None
            if target.exists() and not target.is_file():
                raise ValueError(f'Non-file live conflict: {name}/{relative}')
            if old is not None and old != sha and previous.get(name, {}).get(relative) != old:
                raise ValueError(f'Local content conflict: {name}/{relative}')
            files[relative] = sha
            if old != sha:
                updates.append((src, target, old))
        managed[name] = files
        for relative, old in previous.get(name, {}).items():
            if relative in files:
                continue
            path = Path(relative)
            if path.is_absolute() or '..' in path.parts:
                raise ValueError('Unsafe baseline path')
            retired_files[name + '/' + relative] = old
            target = dest / path
            if target.is_symlink() or any(p.is_symlink() for p in target.parents):
                raise ValueError(f'Linked retired file refused: {name}/{relative}')
            if target.exists():
                if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != old:
                    raise ValueError(f'Local retired content conflict: {name}/{relative}')
                removals.append((target, old))
    for name in retired_names:
        if Path(name).name != name or name in {'.', '..'}:
            raise ValueError('Unsafe baseline package name')
        dest = home / '.claude/skills' / name
        if dest.is_symlink() or any(p.is_symlink() for p in dest.parents):
            raise ValueError(f'Linked retired package refused: {name}')
        for relative, old in previous[name].items():
            path = Path(relative)
            if path.is_absolute() or '..' in path.parts:
                raise ValueError('Unsafe baseline path')
            retired_files[name + '/' + relative] = old
            target = dest / path
            if target.is_symlink() or any(p.is_symlink() for p in target.parents):
                raise ValueError(f'Linked retired file refused: {name}/{relative}')
            if target.exists():
                if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != old:
                    raise ValueError(f'Local retired content conflict: {name}/{relative}')
                removals.append((target, old))
        link = home / '.agents/skills' / name
        if link.exists() or link.is_symlink():
            if not link.is_symlink() or os.readlink(link) != str(dest):
                raise ValueError(f'Local retired consumer conflict: {name}')
            retired_consumers.append((link, dest))
    undo.mkdir(parents=True, mode=0o700)
    os.chmod(undo, 0o700)
    receipt = {'format': 'shared-live-catalog-v2', 'release': release,
               'backup': str(undo), 'managed': managed, 'actions': actions,
               'retired_packages': retired_names,
               'retained_handoff': {n: previous[n] for n in previous if n in retained},
               'retired': retired_files}
    def save():
        (undo / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    save()
    try:
        for src, target, old in updates:
            current = hashlib.sha256(target.read_bytes()).hexdigest() if target.is_file() else None
            if current != old or target.is_symlink():
                raise ValueError(f'Concurrent live edit: {target}')
            saved = None
            if old is not None:
                saved = undo / 'files' / target.relative_to(home / '.claude/skills')
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, saved)
            actions.append({'file': str(target), 'saved': str(saved) if saved else None,
                            'sha256': hashlib.sha256(src.read_bytes()).hexdigest()})
            save()
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
        for target, old in removals:
            if target.is_symlink() or not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != old:
                raise ValueError(f'Concurrent retired edit: {target}')
            saved = undo / 'files' / target.relative_to(home / '.claude/skills')
            saved.parent.mkdir(parents=True, exist_ok=True)
            actions.append({'file': str(target), 'saved': str(saved), 'sha256': None})
            save()
            target.rename(saved)
        for link, target in retired_consumers:
            if not link.is_symlink() or os.readlink(link) != str(target):
                raise ValueError(f'Concurrent retired consumer edit: {link}')
            saved = undo / 'agents' / link.name
            saved.parent.mkdir(parents=True, exist_ok=True)
            actions.append({'link': str(link), 'target': str(target), 'saved': str(saved), 'retired': True})
            save()
            link.rename(saved)
        root = home / '.agents/skills'
        root.mkdir(parents=True, exist_ok=True)
        for name in sorted(mapping):
            link = root / name; target = home / '.claude/skills' / name
            if link.is_symlink() and link.resolve() == target.resolve():
                continue
            saved = undo / 'agents' / name
            action = {'link': str(link), 'target': str(target), 'saved': None}
            if link.exists() or link.is_symlink():
                saved.parent.mkdir(parents=True, exist_ok=True)
                link.rename(saved); action['saved'] = str(saved)
            actions.append(action); save()
            link.symlink_to(target, target_is_directory=True)
        errors = verify(home, release)
        if errors:
            raise ValueError('; '.join(errors))
    except BaseException:
        for action in reversed(actions):
            if 'link' in action:
                link = Path(action['link'])
                if link.is_symlink() and os.readlink(link) == action['target']:
                    link.unlink()
                if action['saved'] and not (link.exists() or link.is_symlink()):
                    Path(action['saved']).rename(link)
            else:
                target = Path(action['file'])
                if action['sha256'] is None:
                    if not (target.exists() or target.is_symlink()) and Path(action['saved']).is_file():
                        shutil.copy2(action['saved'], target)
                    continue
                if target.is_file() and not target.is_symlink() and hashlib.sha256(target.read_bytes()).hexdigest() == action['sha256']:
                    if action['saved']:
                        shutil.copy2(action['saved'], target)
                    else:
                        target.unlink()
        receipt['status'] = 'failed'; save(); raise
    receipt['status'] = 'live-bytes-and-links-verified'; save()
    return receipt

def rollback(home, release):
    """Restore a successful release only when all affected postimages still match."""
    home = Path(home).absolute()
    if home.is_symlink():
        raise ValueError('Linked home refused')
    home = home.resolve()
    undo = release_path(home, release)
    if any(p.is_symlink() for p in [undo, *undo.parents]):
        raise ValueError('Linked undo path refused')
    receipt = json.loads((undo / 'receipt.json').read_text())
    if receipt['status'] != 'live-bytes-and-links-verified':
        raise ValueError('Only a successful active release can be rolled back')
    for action in receipt['actions']:
        target = Path(action.get('link', action.get('file')))
        expected_root = home / ('.agents/skills' if 'link' in action else '.claude/skills')
        if not target.is_relative_to(expected_root) or '..' in target.parts or any(p.is_symlink() for p in target.parents):
            raise ValueError('Unsafe rollback target')
        saved = Path(action['saved']) if action['saved'] else None
        if saved and (not saved.is_relative_to(undo) or '..' in saved.parts or any(p.is_symlink() for p in saved.parents) or not (saved.exists() or saved.is_symlink())):
            raise ValueError('Unsafe or missing rollback preimage')
        if 'link' in action:
            matches = (not (target.exists() or target.is_symlink()) if action.get('retired')
                       else target.is_symlink() and os.readlink(target) == action['target'])
        elif action['sha256'] is None:
            matches = not (target.exists() or target.is_symlink())
        else:
            matches = target.is_file() and not target.is_symlink() and hashlib.sha256(target.read_bytes()).hexdigest() == action['sha256']
        if not matches:
            raise ValueError(f'Later local edit prevents rollback: {target}')
    # Retain the removed postimages and original receipt for a recoverable undo.
    postimages = undo / 'rollback-postimages'
    if postimages.exists():
        raise FileExistsError(postimages)
    receipt['status'] = 'rolling-back'
    receipt['rollback_actions'] = []
    (undo / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    for index, action in enumerate(reversed(receipt['actions'])):
        target = Path(action.get('link', action.get('file')))
        saved = Path(action['saved']) if action['saved'] else None
        if 'link' in action:
            matches = (not (target.exists() or target.is_symlink()) if action.get('retired')
                       else target.is_symlink() and os.readlink(target) == action['target'])
        elif action['sha256'] is None:
            matches = not (target.exists() or target.is_symlink())
        else:
            matches = target.is_file() and not target.is_symlink() and hashlib.sha256(target.read_bytes()).hexdigest() == action['sha256']
        if not matches or any(p.is_symlink() for p in target.parents):
            raise ValueError(f'Concurrent local edit prevents rollback: {target}')
        receipt['rollback_actions'].append({'target': str(target), 'postimage': str(postimages / str(index)), 'saved': str(saved) if saved else None})
        (undo / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
        if target.exists() or target.is_symlink():
            postimages.mkdir(exist_ok=True)
            target.rename(postimages / str(index))
        if saved:
            if 'link' in action:
                if saved.is_symlink():
                    target.symlink_to(os.readlink(saved), target_is_directory=True)
                elif saved.is_file():
                    shutil.copy2(saved, target)
                else:
                    shutil.copytree(saved, target, symlinks=True)
            else:
                shutil.copy2(saved, target)
    receipt['status'] = 'rolled-back'
    (undo / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--home', type=Path, default=Path.home())
    parser.add_argument('--release', required=True)
    parser.add_argument('--verify', action='store_true')
    parser.add_argument('--rollback', action='store_true', help='Restore unchanged postimages from a successful release')
    parser.add_argument('--baseline-receipt', type=Path, help='Reviewed prior live receipt; refuses local divergence')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if sum([args.verify, args.rollback, args.dry_run]) > 1:
        parser.error('--verify, --rollback and --dry-run are mutually exclusive')
    if args.rollback:
        receipt = rollback(args.home, args.release)
        print(json.dumps({'status': receipt['status'], 'backup': receipt['backup']}));return 0
    if args.verify:
        errors = verify(args.home, args.release)
        print(json.dumps({'errors': errors}));return bool(errors)
    if args.dry_run:
        mapping = live_targets(args.source)
        print(json.dumps({'source': mapping,
                          'claude_destination': {n: '.claude/skills/' + n for n in mapping},
                          'agents_destination': {n: '.agents/skills/' + n for n in mapping},
                          'agents_target': {n: '.claude/skills/' + n for n in mapping}}, indent=2));return 0
    baseline = json.loads(args.baseline_receipt.read_text())['managed'] if args.baseline_receipt else None
    receipt = install(args.source, args.home, args.release, baseline)
    print(json.dumps({k: v for k, v in receipt.items() if k != 'actions'}, indent=2))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
