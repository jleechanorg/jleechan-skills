from pathlib import Path
from datetime import datetime,timedelta,timezone
import json,subprocess,sys,hashlib,os
repo=Path(os.environ['REPO_ROOT'])
root=Path(os.environ['ARTIFACT_ROOT'])
sys.path.insert(0,str(repo/'tests'))
from test_prw_metrics_web_export import metric,query,export
head='9ffb51e0c1e5e82808c9a00781ef8f00e4ac5bf5';base='1d02eaedf1ae5bb074cd650c151cd9231a7166e3'
for side,sha in [('before',base),('after',head)]:
 d=root/side;d.mkdir(exist_ok=True)
 for name in ['index.html','app.js','stats.js','styles.css']:
  (d/name).write_bytes(subprocess.check_output(['git','-C',str(repo),'show',sha+':web/prw-dashboard/'+name]))
rows=[];records=[]
for i,(steer,minutes) in enumerate([(0,30),(0,60),(2,90),(5,120),(None,45),(0,None),(1,None),(None,None)],1):
 opts={}
 if steer is not None:opts={'human_coverage_status':'OBSERVED_SCOPE_ONLY','raw_verified_human_message_count':steer+1,'verified_initial_human_message_count':1,'verified_followup_human_message_count':steer}
 rows.append(metric(i,**opts));r={'repo':'acme/app','number':i,'title':'Synthetic PR '+str(i)}
 if minutes is not None:
  start=datetime(2026,11,1,17,tzinfo=timezone.utc)
  r['stage_transitions']=[{'stage':'stage:1-coding','entered_at':start.isoformat()},{'stage':'stage:5-final-approval','entered_at':(start+timedelta(minutes=minutes)).isoformat()}]
 elif i==6:r['legacy_stage']='stage:1-coding'
 elif i==7:r['legacy_stage']='stage:5-final-approval'
 records.append(r)
summary={'status':'OK','data_through':'2026-11-09T21:25:21Z','generated_at':'2026-11-09T21:25:21Z'}
for name,metrics,recs in [('good',rows,records),('small',rows[:2],records[:2]),('missing',[metric(i) for i in range(1,9)],[])]:
 snap=export.build_snapshot(summary,query(metrics),recs,code_version=head)
 snap['fixture']='PR801 deterministic '+name+' case; acme/app, artificial timestamps and counts.'
 for side in ['before','after']:(root/side/(name+'.json')).write_text(json.dumps(snap,sort_keys=True,indent=2)+'\n')
(root/'fixture-inputs.json').write_text(json.dumps({'head':head,'base':base,'summary':summary,'metrics':rows,'records':records,'origin':'existing committed test_prw_metrics_web_export.metric/query helpers plus explicit 8-row deterministic scenario'},indent=2)+'\n')
print('Generated actual base/head static assets and identical synthetic snapshots per side.')
