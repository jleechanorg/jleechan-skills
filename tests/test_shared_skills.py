import importlib.util
import json
import os
from pathlib import Path
import stat
import tempfile
import shutil
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('shared', ROOT/'scripts/install_shared_skills.py')
shared = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shared)


class SharedSkillsTests(unittest.TestCase):
    def fixture(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name).resolve()
        home = root/'home'
        home.mkdir()
        for name in shared.source_manifest()['skills']:
            shutil.copytree(ROOT/'.claude/skills'/name, home/'.claude/skills'/name)
        return root, home

    def test_all_roots_share_source_and_preserve_preimages(self):
        root, home = self.fixture()
        old = home/'.codex/skills/4layer'
        old.mkdir(parents=True)
        (old/'local.md').write_text('local additions')
        plan = shared.plan(home, root/'undo')
        shared.apply(plan)
        targets = [(home/r/'skills/4layer').resolve() for r in shared.ROOTS]
        self.assertEqual(home/'.claude/skills/4layer', targets[0])
        self.assertFalse((home/'.claude/skills/4layer').is_symlink())
        self.assertEqual(1, len(set(targets)))
        self.assertEqual('local additions', (root/'undo/0/local.md').read_text())
        for name in plan['manifest']['skills']:
            for runtime in shared.ROOTS:
                self.assertTrue((home/runtime/'skills'/name).is_symlink())

    def test_drift_refuses_before_any_write(self):
        root, home = self.fixture()
        plan = shared.plan(home, root/'undo')
        dest = home/'.codex/skills/4layer'
        dest.mkdir(parents=True)
        (dest/'note').write_text('new local work')
        with self.assertRaises(ValueError):
            shared.apply(plan)
        self.assertFalse((root/'package').exists())

    def test_linked_discovery_ancestor_refused(self):
        root, home = self.fixture()
        (root/'outside').mkdir()
        (home/'.codex').symlink_to(root/'outside', target_is_directory=True)
        with self.assertRaises(ValueError):
            shared.plan(home, root/'undo')

    def test_tampered_plan_cannot_redirect_target(self):
        root, home = self.fixture()
        plan = shared.plan(home, root/'undo')
        plan['targets'][0]['path'] = str(root/'unrelated')
        with self.assertRaises(ValueError):
            shared.apply(plan)
        self.assertFalse((root/'package').exists())

    def test_live_source_drift_and_additions_preserved(self):
        root, home = self.fixture()
        extra = home/'.claude/skills/4layer/local.md'
        extra.write_text('retained addition')
        plan = shared.plan(home, root/'undo')
        extra.write_text('later edit')
        with self.assertRaises(ValueError):
            shared.apply(plan)
        self.assertFalse((root/'undo').exists())
        self.assertEqual('later edit', extra.read_text())

    def test_unreconciled_canonical_source_refused(self):
        root, home = self.fixture()
        (home/'.claude/skills/4layer/SKILL.md').write_text('local workflow')
        with self.assertRaises(ValueError):
            shared.plan(home, root/'undo')

    def test_private_storage_from_creation_preserves_preimage_modes(self):
        root, home = self.fixture()
        old = home/'.codex/skills/4layer'
        old.mkdir(parents=True, mode=0o750)
        local = old/'private.md'
        local.write_text('private preimage')
        local.chmod(0o640)
        expected_modes = (stat.S_IMODE(old.stat().st_mode), stat.S_IMODE(local.stat().st_mode))
        plan = shared.plan(home, root/'undo')
        original_dump = json.dump
        observed = []

        def inspect_before_write(value, stream, **kwargs):
            observed.append(stat.S_IMODE(os.fstat(stream.fileno()).st_mode))
            self.assertEqual(0o600, observed[-1])
            if (root/'undo').exists():
                self.assertEqual(0o700, stat.S_IMODE((root/'undo').stat().st_mode))
            return original_dump(value, stream, **kwargs)

        previous_umask = os.umask(0o022)
        try:
            with patch.object(shared.json, 'dump', inspect_before_write):
                shared.write_private_json(root/'plan.json', plan, exclusive=True)
                receipt_path = shared.apply(plan)
        finally:
            os.umask(previous_umask)
        self.assertTrue(observed)
        self.assertEqual(expected_modes, (
            stat.S_IMODE((root/'undo/0').stat().st_mode),
            stat.S_IMODE((root/'undo/0/private.md').stat().st_mode)))
        self.assertEqual('private preimage', (root/'undo/0/private.md').read_text())
        self.assertEqual(0o600, stat.S_IMODE(receipt_path.stat().st_mode))

    def test_private_json_exclusive_creation_and_stricter_modes(self):
        root, _ = self.fixture()
        path = root/'plan.json'
        shared.write_private_json(path, {'original': True}, exclusive=True)
        with self.assertRaises(FileExistsError):
            shared.write_private_json(path, {'replacement': True}, exclusive=True)
        self.assertEqual({'original': True}, json.loads(path.read_text()))
        path.chmod(0o200)
        shared.write_private_json(path, {'updated': True})
        self.assertEqual(0o200, stat.S_IMODE(path.stat().st_mode))

    def test_late_canonical_drift_rejected_before_success(self):
        root, home = self.fixture()
        plan = shared.plan(home, root/'undo')
        original_link = Path.symlink_to

        def mutate_completed_source(dest, target, target_is_directory=False):
            original_link(dest, target, target_is_directory=target_is_directory)
            if dest == home/'.agents/skills/four-layer':
                (home/'.claude/skills/4layer/SKILL.md').write_text('concurrent edit')

        with patch.object(Path, 'symlink_to', mutate_completed_source):
            with self.assertRaisesRegex(ValueError, 'Live source changed during apply'):
                shared.apply(plan)
        receipt = json.loads((root/'undo/receipt.json').read_text())
        self.assertEqual('applying', receipt['status'])
        self.assertEqual('concurrent edit', (home/'.claude/skills/4layer/SKILL.md').read_text())

    def test_late_indirect_link_rejected_before_success(self):
        root, home = self.fixture()
        plan = shared.plan(home, root/'undo')
        original_link = Path.symlink_to

        def redirect_completed_link(dest, target, target_is_directory=False):
            original_link(dest, target, target_is_directory=target_is_directory)
            if dest == home/'.agents/skills/pr-blocker-min-repro':
                earlier = home/'.codex/skills/4layer'
                earlier.unlink()
                original_link(earlier, home/'.agents/skills/4layer', target_is_directory=True)

        with patch.object(Path, 'symlink_to', redirect_completed_link):
            with self.assertRaisesRegex(ValueError, 'Direct link verification failed'):
                shared.apply(plan)
        receipt = json.loads((root/'undo/receipt.json').read_text())
        self.assertEqual('applying', receipt['status'])

    def test_success_reports_bounded_final_checks(self):
        root, home = self.fixture()
        receipt_path = shared.apply(shared.plan(home, root/'undo'))
        receipt = json.loads(receipt_path.read_text())
        self.assertEqual('bytes-and-direct-links-checked', receipt['status'])
        self.assertIn('non-atomic', receipt['verification_scope'])
        for entry in receipt['changed']:
            self.assertEqual(entry['target'], os.readlink(entry['path']))

    def test_late_reviewed_repository_drift_rejected(self):
        root, home = self.fixture()
        repository = root/'repository'
        for name in shared.source_manifest()['skills']:
            shutil.copytree(ROOT/'.claude/skills'/name, repository/'.claude/skills'/name)
        shutil.copyfile(ROOT/'shared-skills.json', repository/'shared-skills.json')
        original_link = Path.symlink_to

        def change_reviewed_source(dest, target, target_is_directory=False):
            original_link(dest, target, target_is_directory=target_is_directory)
            if dest == home/'.agents/skills/pr-blocker-min-repro':
                (repository/'.claude/skills/4layer/SKILL.md').write_text('repository drift')

        with patch.object(shared, 'REPO', repository):
            plan = shared.plan(home, root/'undo')
            with patch.object(Path, 'symlink_to', change_reviewed_source):
                with self.assertRaisesRegex(ValueError, 'Source inventory/hash mismatch'):
                    shared.apply(plan)
        receipt = json.loads((root/'undo/receipt.json').read_text())
        self.assertEqual('applying', receipt['status'])

    def test_partial_failure_preserves_pending_preimage(self):
        root, home = self.fixture()
        old = home/'.codex/skills/4layer'
        old.mkdir(parents=True)
        (old/'local.md').write_text('recoverable original')
        plan = shared.plan(home, root/'undo')
        with patch.object(Path, 'symlink_to', side_effect=OSError('injected link failure')):
            with self.assertRaisesRegex(OSError, 'injected link failure'):
                shared.apply(plan)
        receipt = json.loads((root/'undo/receipt.json').read_text())
        self.assertEqual('applying', receipt['status'])
        self.assertEqual('pending', receipt['changed'][0]['state'])
        self.assertFalse(old.exists())
        self.assertEqual('recoverable original', (root/'undo/0/local.md').read_text())
        (root/'undo/0').rename(old)
        self.assertEqual(plan['targets'][0]['before'], shared.snapshot(old))

    def test_manual_undo_restores_directories_links_and_absence(self):
        root, home = self.fixture()
        canonical = home/'.claude/skills/4layer'
        (canonical/'local.md').write_text('preserved canonical addition')
        canonical_before = shared.snapshot(home/'.claude/skills')
        release = root/'old-release'
        release.mkdir()
        (release/'SKILL.md').write_text('preserved release')
        old = home/'.codex/skills/4layer'
        old.parent.mkdir(parents=True)
        old.symlink_to(release, target_is_directory=True)
        custom = home/'.agents/skills/four-layer'
        custom.mkdir(parents=True)
        (custom/'local.md').write_text('preserved discovery directory')
        plan = shared.plan(home, root/'undo')
        receipt = json.loads(shared.apply(plan).read_text())
        for entry in reversed(receipt['changed']):
            dest, backup = Path(entry['path']), Path(entry['backup'])
            self.assertTrue(dest.is_symlink())
            self.assertEqual(entry['target'], os.readlink(dest))
            dest.unlink()
            if backup.exists() or backup.is_symlink():
                backup.rename(dest)
        for entry in plan['targets']:
            self.assertEqual(entry['before'], shared.snapshot(Path(entry['path'])))
        self.assertEqual(canonical_before, shared.snapshot(home/'.claude/skills'))
        self.assertEqual('preserved release', (release/'SKILL.md').read_text())
