import importlib.util,json,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class CatalogTests(unittest.TestCase):
 def test_browser_runtime_route(self):
  s=(ROOT/'.claude/skills/browser-control/SKILL.md').read_text()
  self.assertIn('Supported runtime browser API',s)
  self.assertIn('Do not bypass tab ownership locks',s)
  self.assertIn('CLI authorization does not create a connection',s)
 def test_install_backup_and_verification(self):
  spec=importlib.util.spec_from_file_location('catalog',ROOT/'scripts/install_shared_catalog.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  with tempfile.TemporaryDirectory() as t:
   h=Path(t).resolve();old=h/'.agents/skills/browser';old.mkdir(parents=True);(old/'SKILL.md').write_text('local changes')
   receipt=m.install(ROOT,h,'test-v1')
   self.assertEqual((Path(receipt['backup'])/'agents/browser/SKILL.md').read_text(),'local changes')
   self.assertTrue((h/'.agents/skills/browser/SKILL.md').is_file())
   self.assertEqual((h/'.agents/skills/design/SKILL.md').read_bytes(),(ROOT/'.claude/skills/design/SKILL.md').read_bytes())
   self.assertFalse((h/'.claude/skills/advice').exists())
   self.assertEqual(m.verify(h,'test-v1'),[])
   (h/'.agents/skills/browser/SKILL.md').write_text('tampered')
   self.assertTrue(m.verify(h,'test-v1'))
 def test_live_update_preserves_extensions_and_refuses_local_edits(self):
  spec=importlib.util.spec_from_file_location('catalog',ROOT/'scripts/install_shared_catalog.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  with tempfile.TemporaryDirectory() as t:
   base=Path(t).resolve();h=base/'home';src=base/'source';h.mkdir()
   for tree in ['.claude/skills/example','portable/skills','shared/aliases']:(src/tree).mkdir(parents=True)
   (src/'shared/retain-local.json').write_text('[]')
   skill=src/'.claude/skills/example/SKILL.md';skill.write_text('version one')
   first=m.install(src,h,'v1');live=h/'.claude/skills/example/SKILL.md'
   self.assertFalse(live.parent.is_symlink())
   self.assertEqual((h/'.agents/skills/example').resolve(),live.parent)
   extension=live.parent/'local-note.md';extension.write_text('keep user extension')
   skill.write_text('version two')
   with self.assertRaisesRegex(ValueError,'Local content conflict'):m.install(src,h,'v2')
   self.assertEqual(live.read_text(),'version one')
   self.assertFalse(m.release_path(h,'v2').exists())
   second=m.install(src,h,'v2',first['managed'])
   self.assertEqual(live.read_text(),'version two')
   self.assertEqual(extension.read_text(),'keep user extension')
   self.assertEqual((Path(second['backup'])/'files/example/SKILL.md').read_text(),'version one')
   live.write_text('new user edit');skill.write_text('version three')
   with self.assertRaisesRegex(ValueError,'Local content conflict'):m.install(src,h,'v3',second['managed'])
   self.assertEqual(live.read_text(),'new user edit')
   self.assertFalse((h/'.local/share/jleechan-shared-skills').exists())
 def test_snapshot_canonical_is_refused_before_mutation(self):
  spec=importlib.util.spec_from_file_location('catalog',ROOT/'scripts/install_shared_catalog.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  with tempfile.TemporaryDirectory() as t:
   h=Path(t).resolve();p=h/'.claude/skills/design';p.parent.mkdir(parents=True);p.symlink_to(ROOT/'.claude/skills/design',target_is_directory=True)
   with self.assertRaisesRegex(ValueError,'linked canonical'):m.install(ROOT,h,'v1')
   self.assertTrue(p.is_symlink())
   self.assertFalse(m.release_path(h,'v1').exists())
 def test_failed_activation_restores_links_and_preimages(self):
  from unittest.mock import patch
  spec=importlib.util.spec_from_file_location('catalog',ROOT/'scripts/install_shared_catalog.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  with tempfile.TemporaryDirectory() as t:
   base=Path(t).resolve();h=base/'home';src=base/'source';h.mkdir()
   for tree in ['.claude/skills/example','portable/skills','shared/aliases']:(src/tree).mkdir(parents=True)
   (src/'shared/retain-local.json').write_text('[]');(src/'.claude/skills/example/SKILL.md').write_text('reviewed source')
   old=h/'.agents/skills/example';old.mkdir(parents=True);(old/'SKILL.md').write_text('local consumer')
   with patch.object(m,'verify',return_value=['injected verification failure']):
    with self.assertRaisesRegex(ValueError,'injected verification failure'):m.install(src,h,'failed')
   self.assertFalse(old.is_symlink());self.assertEqual((old/'SKILL.md').read_text(),'local consumer')
   self.assertFalse((h/'.claude/skills/example/SKILL.md').exists())
   self.assertEqual(json.loads((m.release_path(h,'failed')/'receipt.json').read_text())['status'],'failed')
 def test_failed_activation_preserves_concurrent_live_edit(self):
  from unittest.mock import patch
  spec=importlib.util.spec_from_file_location('catalog',ROOT/'scripts/install_shared_catalog.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  with tempfile.TemporaryDirectory() as t:
   base=Path(t).resolve();h=base/'home';src=base/'source';h.mkdir()
   for tree in ['.claude/skills/example','portable/skills','shared/aliases']:(src/tree).mkdir(parents=True)
   (src/'shared/retain-local.json').write_text('[]');(src/'.claude/skills/example/SKILL.md').write_text('reviewed source')
   live=h/'.claude/skills/example/SKILL.md'
   def changed_then_failed(*args):live.write_text('newer user edit');return ['concurrent failure']
   with patch.object(m,'verify',side_effect=changed_then_failed):
    with self.assertRaisesRegex(ValueError,'concurrent failure'):m.install(src,h,'failed-edit')
   self.assertEqual(live.read_text(),'newer user edit')
 def test_linked_discovery_root_is_refused_without_mutation(self):
  spec=importlib.util.spec_from_file_location('catalog',ROOT/'scripts/install_shared_catalog.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  with tempfile.TemporaryDirectory() as t:
   base=Path(t).resolve();h=base/'home';h.mkdir();outside=base/'outside';outside.mkdir()
   (h/'.agents').symlink_to(outside,target_is_directory=True)
   with self.assertRaisesRegex(ValueError,'symlinked discovery root'):m.install(ROOT,h,'linked-root')
   self.assertEqual(list(outside.iterdir()),[]);self.assertFalse(m.release_path(h,'linked-root').exists())
 def test_refuses_reused_release(self):
  spec=importlib.util.spec_from_file_location('catalog',ROOT/'scripts/install_shared_catalog.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  with tempfile.TemporaryDirectory() as t:
   m.install(ROOT,Path(t),'test-v1')
   with self.assertRaises(FileExistsError):m.install(ROOT,Path(t),'test-v1')
if __name__=='__main__':unittest.main()
