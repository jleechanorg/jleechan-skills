"""Explicit reviewed corrections must retract metadata without inventing automation."""
import copy
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from scripts.native_usage_collector import _apply_replay_annotation, collect_native_history, load_normalized_history
from scripts.prw_metrics import aggregate_native_human_steering
from scripts.prw_metrics_queries import run_query


class HumanRetractions(unittest.TestCase):
    cutoff = '2026-11-09T00:00:00Z'
    def correction(self):
        return {'event_id': 'selected', 'actor_kind': 'unknown', 'human_origin': 'unknown',
                'quality_label': 'unknown', 'message_kind': None, 'human_nudge_eligible': None,
                'score': None, 'score_source': None, 'episode_id': None, 'episode_role': None,
                'pr_binding': None, 'context_pr_decision': 'unassigned_no_single_pr',
                'context_associated_pr': None, 'effective_associated_pr': None,
                'association_method': None, 'review_id': 'review-correction'}
    def stale(self):
        return {'record_type': 'human', 'provider': 'anthropic', 'event_id': 'selected',
                'timestamp': '2026-11-08T10:00:00Z', 'actor_kind': 'human',
                'origin_status': 'verified_human', 'message_kind': 'continuation/followthrough_nudge',
                'human_nudge_eligible': True, 'quality_label': 'bad', 'score': -1,
                'score_source': 'old-review', 'episode_id': 'ep', 'episode_role': 'followup',
                'pr_binding': {'pr': 'example/repo#5'}, 'repository': 'example/repo',
                'git_branch': 'topic', 'context_associated_pr': 'example/repo#5',
                'effective_associated_pr': 'example/repo#5', 'association_method': 'context_override'}

    def test_explicit_unknown_and_null_retract_but_omissions_preserve(self):
        before = self.stale(); untouched = copy.deepcopy(before)
        _apply_replay_annotation(untouched, {'event_id': 'selected', 'review_id': 'new'})
        self.assertEqual(untouched, dict(before, review_id='new'))
        for origin in ({'actor_kind': 'unknown'}, {'human_origin': 'unknown'},
                       {'human_origin': 'unverified_candidate'}):
            record = copy.deepcopy(before); annotation = self.correction()
            annotation.pop('actor_kind'); annotation.pop('human_origin'); annotation.update(origin)
            _apply_replay_annotation(record, annotation)
            self.assertEqual(record.get('actor_kind'), 'unknown')
            self.assertEqual(record['origin_status'], 'unverified_candidate')
            for field in ('pr_binding', 'score', 'score_source', 'episode_id', 'episode_role',
                          'message_kind', 'human_nudge_eligible', 'association_method'):
                self.assertNotIn(field, record)
            self.assertEqual(record['quality_label'], 'unknown')
            self.assertIsNone(record['effective_associated_pr'])

    def test_fresh_and_replay_share_retraction_including_alias_lookup(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); native=root/'native'; native.mkdir()
            row={'type':'user','timestamp':'2026-11-08T10:00:00Z','uuid':'selected',
                 'promptId':'alias-selected','userType':'human','sessionId':'session',
                 'message':{'role':'user','content':'synthetic prompt'}}
            (native/'session.jsonl').write_text(json.dumps(row)+'\n')
            annotations=root/'annotations.jsonl'
            annotations.write_text(json.dumps(dict(self.correction(),event_id='alias-selected'))+'\n')
            fresh=collect_native_history([native],cutoff=datetime.fromisoformat(self.cutoff.replace("Z", "+00:00")),annotation_path=annotations)
            export=root/'export.jsonl'; export.write_text(json.dumps(dict(self.stale(),event_id_aliases=['alias-selected']))+'\n')
            replay=load_normalized_history(export,self.cutoff,annotation_path=annotations)
            for result in (fresh,replay):
                record=result['human_records'][0]
                self.assertEqual(record.get('actor_kind'),'unknown')
                self.assertEqual(record['origin_status'],'unverified_candidate')
                self.assertNotIn('pr_binding',record)
                self.assertEqual(result['stats']['human_verified'],0)
                self.assertEqual(result['stats']['automated_excluded_messages'],0)
                self.assertEqual(result['stats']['human_candidates'],1)

    def test_correct_every_copy_before_dedup_and_query_keeps_unknown(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); annotations=root/'annotations.jsonl'
            # Last exact-ID annotation wins, replacing a previous positive label.
            annotations.write_text(json.dumps({'event_id':'selected','actor_kind':'human'})+'\n'+json.dumps(self.correction())+'\n')
            export=root/'export.jsonl'; export.write_text((json.dumps(self.stale())+'\n')*2)
            replay=load_normalized_history(export,self.cutoff,annotation_path=annotations)
            self.assertTrue(all(r['origin_status']=='unverified_candidate' for r in replay['human_records']))
            prs=[{'repo':'example/repo','number':5,'headRefName':'topic','state':'OPEN',
                  'createdAt':'2026-11-01T00:00:00Z'}]
            summary=aggregate_native_human_steering(replay['human_records'],prs,
                window_start='2026-10-26T00:00:00Z',window_end=self.cutoff)
            self.assertEqual(summary['coverage']['verified_messages'],0)
            self.assertEqual(summary['coverage']['candidate_messages'],1)
            self.assertEqual(summary['coverage']['unassigned_candidates'],1)
            self.assertEqual(summary['coverage']['deduplicated_records'],1)
            self.assertEqual(summary['coverage']['automated_excluded_messages'],0)
            self.assertEqual(summary['per_pr'][0]['coverage_status'],'UNKNOWN')
            result=run_query(events_path=[],pr_snapshots_path=prs,human_summary_path=summary,snapshot_at_utc=self.cutoff)
            row=result['pr_metrics'][0]
            for field in ('raw_verified_human_message_count','verified_initial_human_message_count',
                          'verified_followup_human_message_count','reviewed_followup_episode_count'):
                self.assertIsNone(row[field])
            unrelated=dict(self.stale(),event_id='unrelated')
            export.write_text(json.dumps(unrelated)+'\n')
            unmodified=load_normalized_history(export,self.cutoff,annotation_path=annotations)['human_records'][0]
            self.assertEqual(unmodified,unrelated)


if __name__=='__main__':
    unittest.main()
