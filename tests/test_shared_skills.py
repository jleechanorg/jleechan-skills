import importlib.util
from pathlib import Path
import tempfile
import shutil
import unittest

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
