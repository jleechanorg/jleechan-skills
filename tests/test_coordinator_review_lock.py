"""Deprecated review entrypoint cannot create holds or execute a command."""
import os, pathlib, subprocess, tempfile, unittest
SCRIPT = pathlib.Path(__file__).resolve().parents[1] / '.claude/skills/dot-coordinator/scripts/review-with-coordinator-lock.py'
class RetiredReview(unittest.TestCase):
 def test_review_helper_cannot_create_hold_or_run_command(self):
  with tempfile.TemporaryDirectory() as d:
   path=pathlib.Path(d)/'lock'
   result=subprocess.run(['python3',str(SCRIPT),'--','true'],env={**os.environ,'COORDINATOR_LOCK_FILE':str(path)},capture_output=True,text=True)
   self.assertEqual(result.returncode,2)
   self.assertFalse(path.exists())
   self.assertIn('retired',result.stderr)
if __name__=='__main__':unittest.main()
