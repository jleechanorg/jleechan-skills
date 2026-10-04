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
   h=Path(t);old=h/'.agents/skills/browser';old.mkdir(parents=True);(old/'SKILL.md').write_text('local changes')
   receipt=m.install(ROOT,h,'test-v1')
   self.assertEqual((Path(receipt['backup'])/'agents/browser/SKILL.md').read_text(),'local changes')
   self.assertTrue((h/'.agents/skills/browser/SKILL.md').is_file())
   self.assertEqual((h/'.agents/skills/advice/SKILL.md').read_bytes(),(ROOT/'portable/skills/advice/SKILL.md').read_bytes())
   self.assertEqual(m.verify(h,'test-v1'),[])
   (h/'.agents/skills/browser/SKILL.md').write_text('tampered')
   self.assertTrue(m.verify(h,'test-v1'))
 def test_refuses_reused_release(self):
  spec=importlib.util.spec_from_file_location('catalog',ROOT/'scripts/install_shared_catalog.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  with tempfile.TemporaryDirectory() as t:
   m.install(ROOT,Path(t),'test-v1')
   with self.assertRaises(FileExistsError):m.install(ROOT,Path(t),'test-v1')
if __name__=='__main__':unittest.main()
