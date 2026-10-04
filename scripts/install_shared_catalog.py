#!/usr/bin/env python3
"""Install a versioned shared skill catalog with reversible discovery links.

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
    base = home / '.local/share/jleechan-shared-skills'
    return base / release

def verify(home, release):
    root = release_path(home, release)
    manifest = json.loads((root / 'catalog.json').read_text())
    errors = []
    if hashes(root) != manifest['files']:
        errors.append('installed package hashes differ')
    for runtime, entries in manifest['targets'].items():
        for name, rel in entries.items():
            link = home / ('.' + runtime) / 'skills' / name
            if not link.is_symlink() or link.resolve() != root / rel:
                errors.append(f'discovery mismatch: {runtime}/{name}')
    return errors

def install(source, home, release):
    source, home = Path(source).resolve(), Path(home).absolute()
    destination = release_path(home, release)
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(destination)
    expected = hashes(source)
    mapping = targets(source)
    # Fail before mutation if discovery roots redirect somewhere unexpected.
    for runtime in mapping:
        root = home / ('.' + runtime) / 'skills'
        if (home / ('.' + runtime)).is_symlink() or root.is_symlink():
            raise ValueError(f'Review symlinked discovery root before installing: {root}')
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = destination.parent / ('.staging-' + uuid.uuid4().hex)
    backup = destination.parent / ('undo-' + release + '-' + uuid.uuid4().hex[:8])
    staging.mkdir(mode=0o700)
    backup.mkdir(mode=0o700)
    actions = []
    try:
        for tree in TREES:
            shutil.copytree(source / tree, staging / tree, ignore=shutil.ignore_patterns(*NOISE))
        if hashes(staging) != expected:
            raise ValueError('staging verification failed')
        manifest = {'format': 'jleechan-shared-skills-v1', 'release': release,
                    'files': expected, 'targets': mapping}
        (staging / 'catalog.json').write_text(json.dumps(manifest, indent=2) + '\n')
        staging.rename(destination)
        for runtime, entries in mapping.items():
            root = home / ('.' + runtime) / 'skills'
            root.mkdir(parents=True, exist_ok=True)
            for name, rel in sorted(entries.items()):
                link = root / name
                saved = backup / runtime / name
                action = {'link': str(link), 'target': str(destination / rel), 'saved': None}
                if link.exists() or link.is_symlink():
                    saved.parent.mkdir(parents=True, exist_ok=True)
                    action['old_link_target'] = os.readlink(link) if link.is_symlink() else None
                    link.rename(saved)
                    action['saved'] = str(saved)
                actions.append(action)
                link.symlink_to(destination / rel, target_is_directory=True)
        errors = verify(home, release)
        if errors:
            raise ValueError('; '.join(errors))
    except BaseException:
        # Restore only links still owned by this installation; do not overwrite
        # changes another process may have made while installation was running.
        for action in reversed(actions):
            link = Path(action['link'])
            if link.is_symlink() and os.readlink(link) == action['target']:
                link.unlink()
            if action['saved'] and not (link.exists() or link.is_symlink()):
                Path(action['saved']).rename(link)
        (backup / 'failed-actions.json').write_text(json.dumps(actions, indent=2))
        raise
    receipt = {'release': release, 'destination': str(destination), 'backup': str(backup),
               'counts': {k: len(v) for k, v in mapping.items()}, 'actions': actions}
    (backup / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--home', type=Path, default=Path.home())
    parser.add_argument('--release', required=True)
    parser.add_argument('--verify', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if args.verify:
        errors = verify(args.home, args.release)
        print(json.dumps({'errors': errors}));return bool(errors)
    if args.dry_run:
        print(json.dumps({k: sorted(v) for k, v in targets(args.source).items()}, indent=2));return 0
    receipt = install(args.source, args.home, args.release)
    print(json.dumps({k: v for k, v in receipt.items() if k != 'actions'}, indent=2))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
