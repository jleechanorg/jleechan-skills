"""Integration tests run only a fake dot transport and temporary coordinator state."""
import json,os,subprocess,tempfile,unittest,time,signal
from pathlib import Path
WORKER=Path(os.environ.get('COORDINATOR_TEST_WORKER',Path(__file__).resolve().parents[1]/'.claude/skills/agy-dot-coordinator/scripts/agy-dot-coordinator-worker.sh'))
class CoordinatorTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(prefix='coordinator-test-',dir='/tmp');self.p=Path(self.tmp.name);self.state=self.p/'state';self.state.mkdir();self.log=self.p/'calls';self.msg=self.p/'message'
  self.fake=self.p/'fake-dot';self.fake.write_text('#!/bin/bash\nset -eu\nprintf "%s\\n" "$3" >> "$CALLS"\nif [[ "$3" == read ]]; then echo "$READ_TEXT"; exit 0; fi\ncp "$4" "$MESSAGE"\nprintf "%s\\n" "$RECEIPT"\nexit "$SEND_RC"\n');self.fake.chmod(0o755)
  self.cfg=self.p/'config.json';self.cfg.write_text(json.dumps({'rotation':['alpha','beta']}));self.priorities=self.p/'priorities';self.priorities.write_text('Example workstream first, subject to latest user instruction.')
  self.env=os.environ.copy();self.env.update(COORDINATOR_STATE_DIR=str(self.state),COORDINATOR_LOCK_FILE=str(self.p/'lock'),COORDINATOR_DOT_SCRIPT=str(self.fake),COORDINATOR_PRIORITIES_FILE=str(self.priorities),DOT_CONFIG_FILE=str(self.cfg),CALLS=str(self.log),MESSAGE=str(self.msg),READ_TEXT='Idle',RECEIPT='DOT_SENT_VERIFIED',SEND_RC='0',COORDINATOR_CHANGE_ID='',COORDINATOR_CHANGE_SUMMARY='',COORDINATOR_URGENT='0')
 def tearDown(self):self.tmp.cleanup()
 def run_worker(self,*args):
  r=subprocess.run(['/bin/bash',str(WORKER),'--no-poll',*args],env=self.env,cwd=self.p,capture_output=True,text=True,timeout=8);self.last=r;return r
 def seed(self,**fields):(self.state/'state_alpha.json').write_text(json.dumps(fields))
 def saved(self):return json.loads((self.state/'state_alpha.json').read_text())
 def calls(self):return self.log.read_text().splitlines() if self.log.exists() else []
 def event(self,urgent=False):self.env.update(COORDINATOR_CHANGE_ID='task:revision1:ready',COORDINATOR_CHANGE_SUMMARY='Existing owner reports dependency ready',COORDINATOR_URGENT=str(int(urgent)))
 def test_daily_prompt_and_receipt(self):
  self.assertEqual(self.run_worker('--account','alpha').returncode,0);self.assertEqual(self.calls(),['read','send']);self.assertIn('Scope: rollup',self.msg.read_text());self.assertIn('Example workstream',self.msg.read_text());self.assertIn('Do not reopen cancelled work',self.msg.read_text());self.assertEqual(self.saved()['last_status'],'SUCCESS')
 def test_repeat_daily_does_not_read_profile(self):
  self.seed(last_rollup_epoch=int(time.time()),last_sent_epoch=0);self.run_worker('--account','alpha','--force');self.assertEqual(self.calls(),[])
 def test_legacy_receipt_seeds_daily_cap(self):
  self.seed(last_sent_epoch=int(time.time()),last_status='SUCCESS');self.run_worker('--account','alpha');self.assertEqual(self.calls(),[])
 def test_active_skips_even_force(self):
  self.env['READ_TEXT']='Working';self.run_worker('--account','alpha','--force');self.assertEqual(self.calls(),['read']);self.assertFalse(self.msg.exists())
 def test_new_change_is_scoped(self):
  self.event();self.run_worker('--account','alpha');self.assertIn('Scope: change',self.msg.read_text());self.assertEqual(self.saved()['delivered_change_ids'],['task:revision1:ready'])
 def test_duplicate_change_no_profile_read(self):
  self.event();self.seed(delivered_change_ids=['task:revision1:ready']);self.run_worker('--account','alpha','--force');self.assertEqual(self.calls(),[])
 def test_urgent_bypasses_active_and_cooldown_not_daily(self):
  self.event(True);now=int(time.time());self.seed(last_rollup_epoch=now,last_sent_epoch=now);self.env['READ_TEXT']='Working';self.run_worker('--account','alpha');self.assertEqual(self.calls(),['read','send']);self.assertIn('Scope: incident',self.msg.read_text());self.assertEqual(self.saved()['last_rollup_epoch'],now)
 def test_duplicate_urgent_no_read(self):
  self.event(True);self.seed(delivered_change_ids=['task:revision1:ready']);self.run_worker('--account','alpha');self.assertEqual(self.calls(),[])
 def test_unverified_receipt_hold(self):
  self.env.update(RECEIPT='DOT_SEND_UNVERIFIED composer_left=0',SEND_RC='4');self.run_worker('--account','alpha');self.assertTrue(self.saved()['delivery_unverified']);self.assertEqual(self.saved()['last_sent_epoch'],0);before=self.calls();self.run_worker('--account','alpha','--force');self.assertEqual(self.calls(),before)
 def test_zero_empty_composer_is_unverified(self):
  self.env['RECEIPT']='composer_left=0';self.run_worker('--account','alpha');self.assertTrue(self.saved()['delivery_unverified'])
 def test_nonzero_with_receipt_is_unverified(self):
  self.env['SEND_RC']='4';self.run_worker('--account','alpha');self.assertTrue(self.saved()['delivery_unverified'])
 def test_receipt_substring_is_unverified(self):
  self.env['RECEIPT']='prefix DOT_SENT_VERIFIED';self.run_worker('--account','alpha');self.assertTrue(self.saved()['delivery_unverified'])
 def test_draft_hold_does_not_count_delivery(self):
  self.env.update(RECEIPT='DOT_DRAFT_PRESENT',SEND_RC='3');self.run_worker('--account','alpha');self.assertEqual(self.saved()['last_status'],'SKIPPED_COMPOSER_BUSY');self.assertEqual(self.saved()['last_sent_epoch'],0)
 def test_corrupt_state_fails_closed(self):
  (self.state/'state_alpha.json').write_text('{');self.run_worker('--account','alpha');self.assertNotIn('send',self.calls())
 def test_changes_require_single_recipient(self):
  self.event();self.assertEqual(self.run_worker().returncode,2);self.assertEqual(self.calls(),[])
 def test_invalid_account_rejected(self):
  self.assertEqual(self.run_worker('--account','../escape').returncode,2);self.assertEqual(self.calls(),[])
 def test_missing_accounts_do_not_guess(self):
  self.cfg.write_text('{}');self.assertEqual(self.run_worker().returncode,2);self.assertEqual(self.calls(),[])
 def test_model_sender_rejected(self):
  self.assertEqual(self.run_worker('--use-agy').returncode,2);self.assertEqual(self.calls(),[])
 def test_lock_contention_does_not_invoke_transport(self):
  import fcntl
  with open(self.p/'lock','w') as f:
   fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);self.run_worker('--account','alpha');self.assertEqual(self.calls(),[])
 def test_busy_retry_then_uncertain_is_held(self):
  self.env.update(RECEIPT='DOT_DRAFT_PRESENT\nDOT_SEND_UNVERIFIED composer_left=0',SEND_RC='4');self.run_worker('--account','alpha');self.assertTrue(self.saved()['delivery_unverified']);self.assertNotEqual(self.saved()['last_status'],'SKIPPED_COMPOSER_BUSY')
 def test_crash_during_transport_prevents_resend(self):
  self.fake.write_text('#!/bin/bash\nprintf "%s\\n" "$3" >> "$CALLS"\nif [[ "$3" == read ]]; then echo Idle; exit 0; fi\nkill -TERM "$(cat "$PIDFILE")"\nexit 0\n');self.env['PIDFILE']=str(self.p/'pid')
  proc=subprocess.Popen(['/bin/bash',str(WORKER),'--no-poll','--account','alpha'],env=self.env,cwd=self.p,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True);(self.p/'pid').write_text(str(proc.pid));proc.communicate(timeout=5);self.assertTrue(self.saved()['delivery_unverified']);before=self.calls();self.run_worker('--account','alpha');self.assertEqual(self.calls(),before);self.assertIn('No new meaningful change',self.last.stdout)
 def test_receipt_saved_before_polling(self):
  proc=subprocess.Popen(['/bin/bash',str(WORKER),'--account','alpha'],env=self.env,cwd=self.p,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
  try:
   deadline=time.monotonic()+4
   while time.monotonic()<deadline:
    try:
     if self.saved().get('last_status')=='SUCCESS':break
    except (FileNotFoundError,json.JSONDecodeError):pass
    time.sleep(0.02)
   self.assertEqual(self.saved()['last_status'],'SUCCESS');self.assertFalse(self.saved()['delivery_unverified'])
  finally:
   # Stop only this isolated test process and its sleep child; never a real worker.
   os.killpg(proc.pid,signal.SIGTERM);proc.communicate(timeout=3)
  before=self.calls();self.run_worker('--account','alpha');self.assertEqual(self.calls(),before)
if __name__=='__main__':unittest.main(verbosity=2)
