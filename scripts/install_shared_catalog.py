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
    canonical = {p.name: '.claude/skills/' + p.name for p in (root / '.claude/skills').iterdir()
                 if (p / 'SKILL.md').is_file() and not p.name.startswith(('.', '_'))}
    retained = json.loads((root / 'shared/retain-local.json').read_text())
    canonical = {n: rel for n, rel in canonical.items() if n not in retained}
    agents = dict(canonical)
    for tree in ('portable/skills', 'shared/aliases'):
        for p in (root / tree).iterdir():
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
    return errors

def install(source, home, release, baseline=None):
    source, home = Path(source).resolve(), Path(home).absolute()
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
    actions, managed, updates = [], {}, []
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
    undo.mkdir(parents=True, mode=0o700)
    os.chmod(undo, 0o700)
    receipt = {'format': 'shared-live-catalog-v2', 'release': release,
               'backup': str(undo), 'managed': managed, 'actions': actions}
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
                if target.is_file() and not target.is_symlink() and hashlib.sha256(target.read_bytes()).hexdigest() == action['sha256']:
                    if action['saved']:
                        shutil.copy2(action['saved'], target)
                    else:
                        target.unlink()
        receipt['status'] = 'failed'; save(); raise
    receipt['status'] = 'live-bytes-and-links-verified'; save()
    return receipt

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--home', type=Path, default=Path.home())
    parser.add_argument('--release', required=True)
    parser.add_argument('--verify', action='store_true')
    parser.add_argument('--baseline-receipt', type=Path, help='Reviewed prior live receipt; refuses local divergence')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if args.verify:
        errors = verify(args.home, args.release)
        print(json.dumps({'errors': errors}));return bool(errors)
    if args.dry_run:
        print(json.dumps({k: sorted(v) for k, v in targets(args.source).items()}, indent=2));return 0
    baseline = json.loads(args.baseline_receipt.read_text())['managed'] if args.baseline_receipt else None
    receipt = install(args.source, args.home, args.release, baseline)
    print(json.dumps({k: v for k, v in receipt.items() if k != 'actions'}, indent=2))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
