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
 def test_live_aliases_resolve_canonical_dependencies(self):
  import re
  spec=importlib.util.spec_from_file_location('catalog',ROOT/'scripts/install_shared_catalog.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  with tempfile.TemporaryDirectory() as t:
   h=Path(t).resolve();m.install(ROOT,h,'aliases')
   for name in ['browser','linux','mac','playwright','er','es','harness','history','ms','p','parallel']:
    skill=h/'.claude/skills'/name/'SKILL.md';text=skill.read_text()
    references=re.findall(r'\((\.\./[^)]+/SKILL\.md)\)',text)
    if name=='harness':references=['../harness-engineering/SKILL.md']
    self.assertTrue(references,name)
    for ref in references:self.assertTrue((skill.parent/ref).is_file(),(name,ref))
    self.assertEqual((h/'.agents/skills'/name).resolve(),skill.parent)
 def test_browserclaw_does_not_export_generated_nested_skills(self):
  package=ROOT/'.claude/skills/browserclaw'
  active=[str(p.relative_to(package)) for p in package.rglob('SKILL.md')
          if not any(part.startswith('.') for part in p.relative_to(package).parts)]
  self.assertEqual(sorted(active),['SKILL.md'])
 def test_refuses_reused_release(self):
  spec=importlib.util.spec_from_file_location('catalog',ROOT/'scripts/install_shared_catalog.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  with tempfile.TemporaryDirectory() as t:
   m.install(ROOT,Path(t),'test-v1')
   with self.assertRaises(FileExistsError):m.install(ROOT,Path(t),'test-v1')
class ReviewRegressionTests(unittest.TestCase):
 def installer(self):
  import os
  path=Path(os.environ.get('CATALOG_INSTALLER_PATH',ROOT/'scripts/install_shared_catalog.py'))
  spec=importlib.util.spec_from_file_location('review_catalog',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
 def fixture(self,base):
  src=base/'source';home=base/'home';home.mkdir()
  for tree in ['.claude/skills/example','portable/skills/alias','portable/skills/retained','shared/aliases']:(src/tree).mkdir(parents=True)
  (src/'shared/retain-local.json').write_text('["retained"]')
  (src/'.claude/skills/example/SKILL.md').write_text('version one')
  for name in ['alias','retained']:(src/'portable/skills'/name/'SKILL.md').write_text(name)
  return src,home
 def test_dry_run_matches_actual_canonical_and_consumer_destinations(self):
  import subprocess,sys
  m=self.installer()
  with tempfile.TemporaryDirectory() as t:
   src,home=self.fixture(Path(t).resolve())
   output=subprocess.check_output([sys.executable,m.__file__,'--source',str(src),'--home',str(home),'--release','v1','--dry-run'],text=True)
   planned=json.loads(output);receipt=m.install(src,home,'v1')
   self.assertEqual(set(planned['claude']),set(receipt['managed']))
   self.assertEqual(set(planned['agents']),set(receipt['managed']))
   self.assertNotIn('retained',planned['agents'])
   for n in receipt['managed']:self.assertEqual(planned['agents'][n],'.claude/skills/'+n)
 def test_retired_managed_nested_skill_is_inactive_and_recoverable(self):
  m=self.installer()
  with tempfile.TemporaryDirectory() as t:
   src,home=self.fixture(Path(t).resolve());old=src/'.claude/skills/example/skills/nested/SKILL.md';old.parent.mkdir(parents=True);old.write_text('old nested skill')
   first=m.install(src,home,'v1');live=home/'.claude/skills/example/skills/nested/SKILL.md';extension=live.parent/'local-note.md';extension.write_text('user extension');old.unlink()
   second=m.install(src,home,'v2',first['managed']);self.assertFalse(live.exists());self.assertEqual(m.verify(home,'v2'),[])
   self.assertEqual((Path(second['backup'])/'files/example/skills/nested/SKILL.md').read_text(),'old nested skill')
   live.write_text('new user skill');self.assertTrue(m.verify(home,'v2'))
   with self.assertRaisesRegex(ValueError,'Later local edit'):m.rollback(home,'v2')
   self.assertEqual(live.read_text(),'new user skill');live.unlink();m.rollback(home,'v2')
   self.assertEqual(live.read_text(),'old nested skill');self.assertEqual(extension.read_text(),'user extension')
 def test_changed_retired_file_refuses_whole_update_before_mutation(self):
  m=self.installer()
  with tempfile.TemporaryDirectory() as t:
   src,home=self.fixture(Path(t).resolve());old=src/'.claude/skills/example/obsolete.md';old.write_text('owned old file');first=m.install(src,home,'v1')
   (home/'.claude/skills/example/obsolete.md').write_text('local changed file');old.unlink();(src/'.claude/skills/example/SKILL.md').write_text('version two')
   with self.assertRaisesRegex(ValueError,'Local retired content conflict'):m.install(src,home,'v2',first['managed'])
   self.assertEqual((home/'.claude/skills/example/SKILL.md').read_text(),'version one');self.assertFalse(m.release_path(home,'v2').exists())
 def test_successful_rollback_preserves_extensions_and_later_edits(self):
  m=self.installer()
  with tempfile.TemporaryDirectory() as t:
   src,home=self.fixture(Path(t).resolve());consumer=home/'.agents/skills/example';consumer.mkdir(parents=True);(consumer/'SKILL.md').write_text('local consumer')
   regular=consumer.parent/'alias';regular.write_text('local regular consumer')
   first=m.install(src,home,'v1');live=home/'.claude/skills/example/SKILL.md';note=live.parent/'note.md';note.write_text('keep extension');(src/'.claude/skills/example/SKILL.md').write_text('version two');second=m.install(src,home,'v2',first['managed'])
   live.write_text('later edit')
   with self.assertRaisesRegex(ValueError,'Later local edit'):m.rollback(home,'v2')
   self.assertEqual(live.read_text(),'later edit');self.assertTrue(consumer.is_symlink())
   live.write_text('version two');m.rollback(home,'v2');self.assertEqual(live.read_text(),'version one');m.rollback(home,'v1')
   self.assertFalse(consumer.is_symlink());self.assertEqual((consumer/'SKILL.md').read_text(),'local consumer');self.assertEqual(regular.read_text(),'local regular consumer');self.assertFalse(live.exists());self.assertEqual(note.read_text(),'keep extension')
 def test_beads_export_checkers_are_complete_read_only_and_fail_closed(self):
  import subprocess,sys
  package=ROOT/'.claude/skills/beads-issue-tracking/scripts'
  with tempfile.TemporaryDirectory() as t:
   path=Path(t)/'issues.jsonl'
   for content,valid,sorted_ids in [(' {"id":"a"}\n{"id":"b"}\n',True,True),('{"id":"b"}\n{"id":"a"}\n',True,False),('{"id":"a"}\n{"id":"a"}\n',False,False),('[]\n',False,False),('\n',False,False),('{oops}\n',False,False)]:
    path.write_text(content)
    validate=subprocess.run([sys.executable,str(package/'validate_beads_issues_jsonl.py'),str(path)],capture_output=True)
    order=subprocess.run([sys.executable,str(package/'sort_beads_jsonl.py'),'--check',str(path)],capture_output=True)
    self.assertEqual(validate.returncode==0,valid);self.assertEqual(order.returncode==0,sorted_ids);self.assertEqual(path.read_text(),content)
if __name__=='__main__':unittest.main()
