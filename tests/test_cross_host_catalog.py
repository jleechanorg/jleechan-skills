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
   for field in ['source','claude_destination','agents_destination','agents_target']:
    self.assertEqual(set(planned[field]),set(receipt['managed']))
    self.assertNotIn('retained',planned[field])
   self.assertEqual(planned['source']['alias'],'portable/skills/alias')
   for n in receipt['managed']:
    self.assertEqual(planned['claude_destination'][n],'.claude/skills/'+n)
    self.assertEqual(planned['agents_destination'][n],'.agents/skills/'+n)
    self.assertEqual(planned['agents_target'][n],'.claude/skills/'+n)
    self.assertEqual((home/planned['agents_destination'][n]).resolve(),home/planned['claude_destination'][n])
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
   for content,valid,sorted_ids in [(' {"id":"a"}\n{"id":"b"}\n',True,True),('{"id":"b"}\n{"id":"a"}\n',True,False),('{"id":"a"}\n{"id":"a"}\n',False,False),('[]\n',False,False),('\n',False,False),('{oops}\n',False,False),('',False,False)]:
    path.write_text(content)
    validate=subprocess.run([sys.executable,str(package/'validate_beads_issues_jsonl.py'),str(path)],capture_output=True)
    order=subprocess.run([sys.executable,str(package/'sort_beads_jsonl.py'),'--check',str(path)],capture_output=True)
    self.assertEqual(validate.returncode==0,valid);self.assertEqual(order.returncode==0,sorted_ids);self.assertEqual(path.read_text(),content)
 def test_whole_package_retirement_restores_owned_link_and_preserves_extensions(self):
  import shutil
  m=self.installer()
  with tempfile.TemporaryDirectory() as t:
   src,home=self.fixture(Path(t).resolve());first=m.install(src,home,'v1');live=home/'.claude/skills/example/SKILL.md';note=live.parent/'note.md';note.write_text('keep local');shutil.rmtree(src/'.claude/skills/example')
   second=m.install(src,home,'v2',first['managed']);self.assertFalse(live.exists());self.assertFalse((home/'.agents/skills/example').is_symlink());self.assertIn('example',second['retired_packages']);self.assertEqual(m.verify(home,'v2'),[])
   self.assertEqual(note.read_text(),'keep local');m.rollback(home,'v2');self.assertEqual(live.read_text(),'version one');self.assertEqual((home/'.agents/skills/example').resolve(),live.parent)
 def test_retain_transition_explicitly_hands_off_previous_management_without_writes(self):
  m=self.installer()
  with tempfile.TemporaryDirectory() as t:
   src,home=self.fixture(Path(t).resolve());first=m.install(src,home,'v1');live=home/'.claude/skills/example/SKILL.md';live.write_text('local operational variant');(src/'shared/retain-local.json').write_text('["example","retained"]')
   second=m.install(src,home,'v2',first['managed']);self.assertIn('example',second['retained_handoff']);self.assertNotIn('example',second['managed']);self.assertNotIn('example',second['retired_packages']);self.assertEqual(live.read_text(),'local operational variant');self.assertEqual((home/'.agents/skills/example').resolve(),live.parent)
 def test_retention_reason_records_match_excluded_live_destinations(self):
  m=self.installer();retained=json.loads((ROOT/'shared/retain-local.json').read_text());records={v['skill']:v for v in json.loads((ROOT/'shared/comparison-decisions.json').read_text())};mapping=m.live_targets(ROOT)
  for n,reason in retained.items():self.assertNotIn(n,mapping);self.assertEqual(records[n]['reason'],reason)
 def test_all_source_trees_reject_top_level_package_symlinks_without_mutation(self):
  m=self.installer()
  for tree in m.TREES:
   with self.subTest(tree=tree),tempfile.TemporaryDirectory() as t:
    base=Path(t).resolve();src,home=self.fixture(base);outside=base/'outside';outside.mkdir();(outside/'SKILL.md').write_text('outside reviewed source')
    (src/tree/'linked').symlink_to(outside,target_is_directory=True)
    with self.assertRaisesRegex(ValueError,'Linked source'):m.install(src,home,'v1')
    self.assertEqual(list(home.iterdir()),[])
    self.assertEqual((outside/'SKILL.md').read_text(),'outside reviewed source')
 def test_linked_source_tree_ancestors_are_rejected_without_mutation(self):
  m=self.installer()
  for name in ['.claude','portable','shared']:
   with self.subTest(tree=name),tempfile.TemporaryDirectory() as t:
    base=Path(t).resolve();src,home=self.fixture(base);outside=base/'outside';(src/name).rename(outside);(src/name).symlink_to(outside,target_is_directory=True)
    with self.assertRaisesRegex(ValueError,'Linked source'):m.install(src,home,'v1')
    self.assertEqual(list(home.iterdir()),[])
 def test_mixed_canonical_cmux_packages_keep_restore_reference_closure(self):
  import shutil,re
  m=self.installer()
  with tempfile.TemporaryDirectory() as t:
   src,home=self.fixture(Path(t).resolve())
   for name in ['cmux-backup','cmux-steer','cmux-restore']:shutil.copytree(ROOT/'portable/skills'/name,src/'portable/skills'/name)
   for name in ['cmux-backup','cmux-steer']:shutil.copytree(ROOT/'.claude/skills'/name,src/'.claude/skills'/name)
   mapping=m.live_targets(src);self.assertEqual(mapping['cmux-backup'],'.claude/skills/cmux-backup');self.assertEqual(mapping['cmux-steer'],'.claude/skills/cmux-steer');self.assertEqual(mapping['cmux-restore'],'portable/skills/cmux-restore')
   m.install(src,home,'v1');self.assertEqual(m.verify(home,'v1'),[]);restore=home/'.claude/skills/cmux-restore'
   refs=re.findall(r'\]\((\.\./[^)]+)\)',(restore/'SKILL.md').read_text());self.assertEqual(len(refs),2)
   for ref in refs:
    target=(restore/ref).resolve();self.assertTrue(target.is_file(),ref)
    self.assertEqual(target.read_bytes(),(ROOT/'portable/skills'/ref.removeprefix('../')).read_bytes())
 def test_fresh_and_existing_hosts_handle_retained_mirror_dependencies(self):
  import shutil,re
  m=self.installer()
  for existing in [False,True]:
   with self.subTest(existing=existing),tempfile.TemporaryDirectory() as t:
    src,home=self.fixture(Path(t).resolve())
    names=['cross-machine-ssh-tier','mac-remote','linux-remote','mac-mirror','linux-mirror']
    for name in names:shutil.copytree(ROOT/'.claude/skills'/name,src/'.claude/skills'/name)
    (src/'shared/retain-local.json').write_text(json.dumps(['retained','mac-mirror','linux-mirror']))
    if existing:
     for name in ['mac-mirror','linux-mirror']:
      root=home/'.claude/skills'/name;root.mkdir(parents=True);(root/'SKILL.md').write_text('existing host integration '+name)
      link=home/'.agents/skills'/name;link.parent.mkdir(parents=True,exist_ok=True);link.symlink_to(root,target_is_directory=True)
    m.install(src,home,'v1');self.assertEqual(m.verify(home,'v1'),[]);root=home/'.claude/skills/cross-machine-ssh-tier';body=(root/'SKILL.md').read_text()
    for ref in re.findall(r'\]\((\.\./[^)]+)\)',body):self.assertTrue((root/ref).is_file(),ref)
    self.assertIn('excluded from a fresh shared-catalog install',body)
    self.assertIn('only when its SKILL.md already exists',body)
    self.assertIn('mirror handoff is unavailable',body)
    for name in ['mac-mirror','linux-mirror']:
     target=home/'.claude/skills'/name/'SKILL.md'
     if existing:self.assertEqual(target.read_text(),'existing host integration '+name);self.assertEqual((home/'.agents/skills'/name).resolve(),target.parent)
     else:self.assertFalse(target.exists());self.assertFalse((home/'.agents/skills'/name).exists())

 def test_fresh_and_existing_review_integrations_are_explicit(self):
  import re
  m=self.installer()
  for existing in [False,True]:
   with self.subTest(existing=existing),tempfile.TemporaryDirectory() as t:
    h=Path(t).resolve()
    if existing:
     for n in ['advice','web-advice']:
      p=h/'.claude/skills'/n;p.mkdir(parents=True);(p/'SKILL.md').write_text('host-owned '+n)
      a=h/'.agents/skills'/n;a.parent.mkdir(parents=True,exist_ok=True);a.symlink_to(p,target_is_directory=True)
    m.install(ROOT,h,'review-dependencies')
    checked=[]
    for p in (h/'.claude/skills').glob('*/SKILL.md'):
     if p.parent.name in ['advice','web-advice']:continue
     text=p.read_text()
     if not re.search(r'(?:/advice|/web-advice|advice/SKILL)',text):continue
     checked.append(p.parent.name)
     self.assertIn('## Retained review integrations',text,p.parent.name)
     before=text.split('## Retained review integrations',1)[0]
     self.assertEqual(sum(line.startswith('```') for line in before.splitlines())%2,0,p.parent.name)
     self.assertIn('For a remote invocation, check',text,p.parent.name)
     self.assertIn('UNAVAILABLE',text,p.parent.name)
     self.assertIn('leave any dependent readiness or plan-approval gate unmet',text,p.parent.name)
    self.assertEqual(len(checked),15)
    for n in ['advice','web-advice']:
     p=h/'.claude/skills'/n/'SKILL.md'
     if existing:
      self.assertEqual(p.read_text(),'host-owned '+n)
      self.assertEqual((h/'.agents/skills'/n).resolve(),p.parent)
     else:self.assertFalse(p.exists())

if __name__=='__main__':unittest.main()
