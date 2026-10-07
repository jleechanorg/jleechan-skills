"""Integration tests run only a fake dot transport and temporary coordinator state."""
import json,os,subprocess,tempfile,unittest,time,signal
from pathlib import Path
WORKER=Path(os.environ.get('COORDINATOR_TEST_WORKER',Path(__file__).resolve().parents[1]/'.claude/skills/agy-dot-coordinator/scripts/agy-dot-coordinator-worker.sh'))
class CoordinatorTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(prefix='coordinator-test-',dir='/tmp');self.p=Path(self.tmp.name);self.state=self.p/'state';self.state.mkdir();self.log=self.p/'calls';self.msg=self.p/'message'
  self.fake=self.p/'fake-dot';self.fake.write_text('#!/bin/bash\nset -eu\nprintf "%s\\n" "$3" >> "$CALLS"\nif [[ "$3" == read ]]; then echo "$READ_TEXT"; exit 0; fi\ncp "$4" "$MESSAGE"\nprintf "%s\\n" "$RECEIPT"\nexit "$SEND_RC"\n');self.fake.chmod(0o755)
  self.cfg=self.p/'config.json';self.cfg.write_text(json.dumps({'rotation':['alpha','beta']}));self.priorities=self.p/'priorities';self.priorities.write_text('Example workstream first, subject to latest user instruction.')
  self.env=os.environ.copy();self.env.update(COORDINATOR_STATE_DIR=str(self.state),COORDINATOR_LOCK_FILE=str(self.p/'lock'),COORDINATOR_DOT_SCRIPT=str(self.fake),COORDINATOR_PRIORITIES_FILE=str(self.priorities),DOT_CONFIG_FILE=str(self.cfg),CALLS=str(self.log),MESSAGE=str(self.msg),READ_TEXT='Idle',RECEIPT='DOT_SENT_VERIFIED',SEND_RC='0',COORDINATOR_CHANGE_ID='',COORDINATOR_CHANGE_SUMMARY='',COORDINATOR_URGENT='0',COORDINATOR_FULL_ROLLUP='0')
 def tearDown(self):self.tmp.cleanup()
 def run_worker(self,*args):
  r=subprocess.run(['/bin/bash',str(WORKER),'--no-poll',*args],env=self.env,cwd=self.p,capture_output=True,text=True,timeout=8);self.last=r;return r
 def seed(self,**fields):(self.state/'state_alpha.json').write_text(json.dumps(fields))
 def saved(self):return json.loads((self.state/'state_alpha.json').read_text())
 def calls(self):return self.log.read_text().splitlines() if self.log.exists() else []
 def event(self,urgent=False):self.env.update(COORDINATOR_CHANGE_ID='task:revision1:ready',COORDINATOR_CHANGE_SUMMARY='Existing owner reports dependency ready',COORDINATOR_URGENT=str(int(urgent)))
 def test_requested_rollup_prompt_and_receipt(self):
  self.event();self.assertEqual(self.run_worker('--account','alpha','--full-rollup').returncode,0);self.assertEqual(self.calls(),['read','send']);self.assertIn('Scope: rollup',self.msg.read_text());self.assertIn('Example workstream',self.msg.read_text());self.assertIn('Do not reopen cancelled work',self.msg.read_text());self.assertEqual(self.saved()['last_status'],'SUCCESS')
 def test_no_request_ignores_rollup_timestamp(self):
  self.seed(last_rollup_epoch=int(time.time()),last_sent_epoch=0);self.run_worker('--account','alpha','--force');self.assertEqual(self.calls(),[])
 def test_legacy_receipt_preserves_delta_cooldown(self):
  self.event();self.seed(last_sent_epoch=int(time.time()),last_status='SUCCESS');self.run_worker('--account','alpha');self.assertEqual(self.calls(),['read'])
 def test_legacy_global_receipt_preserves_delta_cooldown(self):
  self.event();(self.state/'state.json').write_text(json.dumps({'last_sent_epoch':int(time.time()),'last_status':'SUCCESS'}));self.run_worker('--account','alpha');self.assertEqual(self.calls(),['read'])
 def test_active_skips_even_force(self):
  self.event()
  self.env['READ_TEXT']='Working';self.run_worker('--account','alpha','--force');self.assertEqual(self.calls(),['read']);self.assertFalse(self.msg.exists())
 def test_new_change_is_scoped(self):
  self.event();self.run_worker('--account','alpha');self.assertIn('Scope: change',self.msg.read_text());self.assertEqual(self.saved()['delivered_change_ids'],['task:revision1:ready'])
 def test_duplicate_change_no_profile_read(self):
  self.event();self.seed(delivered_change_ids=['task:revision1:ready']);self.run_worker('--account','alpha','--force');self.assertEqual(self.calls(),[])
 def test_urgent_preserves_rollup_timestamp(self):
  self.event(True);now=int(time.time());self.seed(last_rollup_epoch=now,last_sent_epoch=now);self.env['READ_TEXT']='Working';self.run_worker('--account','alpha');self.assertEqual(self.calls(),['read','send']);self.assertIn('Scope: incident',self.msg.read_text());self.assertEqual(self.saved()['last_rollup_epoch'],now)
 def test_duplicate_urgent_no_read(self):
  self.event(True);self.seed(delivered_change_ids=['task:revision1:ready']);self.run_worker('--account','alpha');self.assertEqual(self.calls(),[])
 def test_unverified_receipt_hold(self):
  self.event()
  self.env.update(RECEIPT='DOT_SEND_UNVERIFIED composer_left=0',SEND_RC='4');self.run_worker('--account','alpha');self.assertTrue(self.saved()['delivery_unverified']);self.assertEqual(self.saved()['last_sent_epoch'],0);before=self.calls();self.run_worker('--account','alpha','--force');self.assertEqual(self.calls(),before)
 def test_zero_empty_composer_is_unverified(self):
  self.event()
  self.env['RECEIPT']='composer_left=0';self.run_worker('--account','alpha');self.assertTrue(self.saved()['delivery_unverified'])
 def test_nonzero_with_receipt_is_unverified(self):
  self.event()
  self.env['SEND_RC']='4';self.run_worker('--account','alpha');self.assertTrue(self.saved()['delivery_unverified'])
 def test_receipt_substring_is_unverified(self):
  self.event()
  self.env['RECEIPT']='prefix DOT_SENT_VERIFIED';self.run_worker('--account','alpha');self.assertTrue(self.saved()['delivery_unverified'])
 def test_draft_hold_does_not_count_delivery(self):
  self.event()
  self.env.update(RECEIPT='DOT_DRAFT_PRESENT',SEND_RC='3');self.run_worker('--account','alpha');self.assertEqual(self.saved()['last_status'],'SKIPPED_COMPOSER_BUSY');self.assertEqual(self.saved()['last_sent_epoch'],0)
 def test_corrupt_state_fails_closed(self):
  self.event()
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
  self.event()
  self.env.update(RECEIPT='DOT_DRAFT_PRESENT\nDOT_SEND_UNVERIFIED composer_left=0',SEND_RC='4');self.run_worker('--account','alpha');self.assertTrue(self.saved()['delivery_unverified']);self.assertNotEqual(self.saved()['last_status'],'SKIPPED_COMPOSER_BUSY')
 def test_crash_during_transport_prevents_resend(self):
  self.event()
  self.fake.write_text('#!/bin/bash\nprintf "%s\\n" "$3" >> "$CALLS"\nif [[ "$3" == read ]]; then echo Idle; exit 0; fi\nkill -TERM "$(cat "$PIDFILE")"\nexit 0\n');self.env['PIDFILE']=str(self.p/'pid')
  proc=subprocess.Popen(['/bin/bash',str(WORKER),'--no-poll','--account','alpha'],env=self.env,cwd=self.p,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True);(self.p/'pid').write_text(str(proc.pid));proc.communicate(timeout=5);self.assertTrue(self.saved()['delivery_unverified']);before=self.calls();self.run_worker('--account','alpha');self.assertEqual(self.calls(),before);self.assertIn('unresolved delivery hold',self.last.stdout)
 def test_receipt_saved_before_polling(self):
  self.event()
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
 def test_no_signal_quiet_even_after_24_hours(self):
  self.seed(last_sent_epoch=1,last_rollup_epoch=1);self.run_worker('--account','alpha');self.assertEqual(self.calls(),[])
 def test_requested_rollup_has_no_daily_or_cooldown_barrier(self):
  self.event();self.seed(last_sent_epoch=int(time.time()),last_rollup_epoch=int(time.time()));r=self.run_worker('--account','alpha','--full-rollup');self.assertEqual(r.returncode,0);self.assertEqual(self.calls(),['read','send']);self.assertIn('Scope: rollup',self.msg.read_text())
 def test_rollup_request_id_deduplicates(self):
  self.event();self.run_worker('--account','alpha','--full-rollup');self.assertEqual(self.saved()['delivered_change_ids'],['task:revision1:ready']);before=self.calls();self.run_worker('--account','alpha','--full-rollup');self.assertEqual(self.calls(),before)
 def test_new_requested_rollup_same_day_is_allowed(self):
  self.event();self.run_worker('--account','alpha','--full-rollup');self.env['COORDINATOR_CHANGE_ID']='request:second';self.run_worker('--account','alpha','--full-rollup');self.assertEqual(self.calls().count('send'),2)
 def test_rollup_defers_active_owner(self):
  self.event();self.env['READ_TEXT']='Working';self.run_worker('--account','alpha','--full-rollup','--force');self.assertEqual(self.calls(),['read'])
 def test_rollup_needs_explicit_request_identity(self):
  self.assertEqual(self.run_worker('--account','alpha','--full-rollup').returncode,2);self.assertEqual(self.calls(),[])
 def test_urgent_is_not_full_review(self):
  self.event(True);self.assertEqual(self.run_worker('--account','alpha','--full-rollup').returncode,2);self.assertEqual(self.calls(),[])
 def test_dedup_eviction_allows_replay_of_old_id(self):
  # Seed128 historical verified IDs, then deliver129th and replay evicted1st.
  self.event();ids=['event:'+str(i) for i in range(128)];self.seed(delivered_change_ids=ids)
  self.env['COORDINATOR_CHANGE_ID']='event:128';self.run_worker('--account','alpha','--full-rollup');self.assertEqual(self.saved()['delivered_change_ids'],ids[1:]+['event:128'])
  self.env['COORDINATOR_CHANGE_ID']='event:0';self.run_worker('--account','alpha','--full-rollup');self.assertEqual(self.calls().count('send'),2);self.assertEqual(len(self.saved()['delivered_change_ids']),128)
 def test_deferred_event_resumes_with_same_id(self):
  self.event();self.env['READ_TEXT']='Working';self.run_worker('--account','alpha');self.assertFalse((self.state/'state_alpha.json').exists())
  self.env['READ_TEXT']='Idle';self.run_worker('--account','alpha');self.assertEqual(self.calls(),['read','read','send']);self.assertEqual(self.saved()['delivered_change_ids'],['task:revision1:ready'])
 def test_force_overrides_only_delta_cooldown(self):
  self.event();self.seed(last_sent_epoch=int(time.time()));self.run_worker('--account','alpha');self.assertEqual(self.calls(),['read'])
  self.run_worker('--account','alpha','--force');self.assertEqual(self.calls(),['read','read','send']);self.assertEqual(self.saved()['delivered_change_ids'],['task:revision1:ready'])
 def test_new_account_does_not_inherit_peer_cooldown(self):
  self.event();self.run_worker('--account','alpha');self.run_worker('--account','beta');self.assertEqual(self.calls(),['read','send','read','send'])
  self.assertEqual(json.loads((self.state/'state_beta.json').read_text())['last_status'],'SUCCESS')
 def test_consolidated_state_migration_preserves_unverified_hold(self):
  self.event()
  (self.state/'state.json').write_text(json.dumps({'accounts':{'alpha':{'last_sent_epoch':0,'delivery_unverified':True,'delivered_change_ids':[]}}}))
  self.run_worker('--account','alpha','--force');self.assertEqual(self.calls(),[]);self.assertTrue(self.saved()['delivery_unverified'])
 def test_consolidated_state_migration_preserves_delivered_ledger(self):
  self.event()
  (self.state/'state.json').write_text(json.dumps({'accounts':{'alpha':{'last_sent_epoch':int(time.time())-3600,'delivery_unverified':False,'delivered_change_ids':['task:revision1:ready']}}}))
  self.run_worker('--account','alpha','--force');self.assertEqual(self.calls(),[]);self.assertIn('task:revision1:ready',self.saved()['delivered_change_ids'])
 def test_legacy_global_state_does_not_impose_cooldown_on_peer(self):
  self.event()
  (self.state/'state.json').write_text(json.dumps({'last_sent_epoch':int(time.time()),'last_status':'SUCCESS'}))
  self.run_worker('--account','alpha');self.assertEqual(self.calls(),['read'])
  self.run_worker('--account','beta');self.assertEqual(self.calls(),['read','read','send'])
 def test_corrupt_consolidated_state_fails_closed(self):
  self.event();(self.state/'state.json').write_text('{');self.run_worker('--account','alpha','--force');self.assertEqual(self.calls(),[])
 def test_unverifiable_config_does_not_assign_legacy_state(self):
  (self.state/'state.json').write_text(json.dumps({'last_sent_epoch':int(time.time()),'last_status':'SUCCESS'}))
  if self.cfg.exists(): self.cfg.unlink()
  self.run_worker('--account','beta');self.assertFalse((self.state/'state_beta.json').exists())
 def test_malformed_accounts_list_fails_closed(self):
  self.event();(self.state/'state.json').write_text(json.dumps({'accounts':[]}));self.run_worker('--account','alpha','--force');self.assertEqual(self.calls(),[])
 def test_legacy_migration_prefers_default_account_over_rotation(self):
  self.event()
  self.cfg.write_text(json.dumps({'default_account':'beta','rotation':['alpha','beta']}))
  (self.state/'state.json').write_text(json.dumps({'last_sent_epoch':0,'delivery_unverified':True,'delivered_change_ids':[]}))
  self.run_worker('--account','beta','--force');self.assertEqual(self.calls(),[])
  self.run_worker('--account','alpha','--force');self.assertEqual(self.calls(),['read','send'])
 def test_invalid_default_account_falls_back_to_rotation(self):
  self.event()
  self.cfg.write_text(json.dumps({'default_account':'ghost','rotation':['alpha','beta']}))
  (self.state/'state.json').write_text(json.dumps({'last_sent_epoch':0,'delivery_unverified':True,'delivered_change_ids':[]}))
  self.run_worker('--account','alpha','--force');self.assertEqual(self.calls(),[])
  self.run_worker('--account','beta','--force');self.assertEqual(self.calls(),['read','send'])
 def test_non_string_default_account_falls_back_to_rotation(self):
  self.event()
  self.cfg.write_text(json.dumps({'default_account':123,'rotation':['alpha','beta']}))
  (self.state/'state.json').write_text(json.dumps({'last_sent_epoch':0,'delivery_unverified':True,'delivered_change_ids':[]}))
  self.run_worker('--account','alpha','--force');self.assertEqual(self.calls(),[])
  self.run_worker('--account','beta','--force');self.assertEqual(self.calls(),['read','send'])
 def test_legacy_hold_with_missing_config_refuses_execution(self):
  self.event()
  if self.cfg.exists(): self.cfg.unlink()
  (self.state/'state.json').write_text(json.dumps({'last_sent_epoch':0,'delivery_unverified':True,'delivered_change_ids':[]}))
  r=self.run_worker('--account','alpha','--force');self.assertEqual(r.returncode,2);self.assertEqual(self.calls(),[])
if __name__=='__main__':unittest.main(verbosity=2)
