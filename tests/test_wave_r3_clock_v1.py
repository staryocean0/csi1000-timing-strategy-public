"""#345 source-only synthetic checks. No market data, credentials or execution."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'executor'))
from wave_r3_clock_probe_v1 import observe_frozen,replay,action,reset_bar_predicates,snapshot
from wave_r3_clock_audit_v1 import summarize,latency_rows
from wave_r3_clock_checks_v1 import check_trace,check_subset_counts
from wave_recognizer_r3_v1 import analyze,MatureCounterRearmEngine


def bars(values):
    c=np.asarray(values,float)
    return pd.DataFrame(dict(timestamp=pd.date_range('2015-01-05',periods=len(c),freq='5min'),
                             open=c,high=c+0.1,low=c-0.1,close=c))

def waves_path():
    t=np.arange(700)
    return bars(100+3*np.sin(t/8)+.6*np.sin(t/31))


def first_reset(values):
    b=bars(values);observed,rows=observe_frozen(b)
    check_trace(b,observed,rows)
    r=next(row for row in rows if action(row)=='RESET')
    return r,reset_bar_predicates(r,b.close.to_numpy(float))


class ClockProbeTests(unittest.TestCase):
    def test_original_detector_blob_is_unchanged(self):
        raw=(ROOT/'executor/wave_recognizer_r3_v1.py').read_bytes()
        actual=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        self.assertEqual(actual,'2815b9a74f45066040e042fdf5670e64af469f5c')

    def test_every_state_and_ledger_matches_on_random_ties(self):
        for seed in range(5):
            b=bars(200+np.random.default_rng(seed).choice([-1.,0.,1.],700).cumsum())
            result,rows=observe_frozen(b)
            self.assertEqual(check_trace(b,result,rows)['trace_rows'],700)

    def test_early_counter_subscale_rejection_and_rearm(self):
        b=bars(list(range(100,111))+[90,100,101,99,100,98,100,101,99,100,101,102])
        result,rows=observe_frozen(b);check_trace(b,result,rows)
        self.assertEqual(action(rows[15]),'SUBSCALE_REJECT_REARM')
        self.assertEqual(rows[15]['post']['pending_counter'],None)
        self.assertEqual(rows[16]['post']['pending_counter'],16)
        self.assertEqual(action(rows[20]),'ACCEPT_MATURE_COUNTER')

    def test_reset_skips_same_bar_progress_without_applying_it(self):
        row,p=first_reset(list(range(100,111))+[110]*48+[111])
        self.assertEqual(row['bar_index'],59)
        self.assertTrue(p['same_bar_candidate_progress'])
        self.assertEqual(p['classification'],'RESET_PREEMPTS_SAME_BAR_CANDIDATE_PROGRESS')
        self.assertIsNone(row['post']['candidate'])

    def test_reset_can_skip_mature_eligible_counter(self):
        row,p=first_reset(list(range(100,111))+[110]*44+[100]+[105]*4)
        self.assertEqual(p['pending_age'],4)
        self.assertEqual(p['occurrence_gap'],45)
        self.assertTrue(p['same_bar_eligible_maturity'])
        self.assertEqual(p['classification'],'RESET_PREEMPTS_ELIGIBLE_COUNTER_MATURITY')
        self.assertEqual(row['post']['maturities_n'],row['pre']['maturities_n'])

    def test_counter_supersession_is_not_candidate_progress(self):
        row,p=first_reset(list(range(100,111))+list(range(109,60,-1)))
        self.assertEqual(p['progress_age'],49)
        self.assertTrue(p['same_bar_counter_update'])
        self.assertFalse(p['same_bar_candidate_progress'])
        self.assertEqual(p['classification'],'TIMEOUT_WITH_COUNTER_SUPERSESSION_ON_RESET_BAR')

    def test_counter_not_yet_mature_is_separate_class(self):
        row,p=first_reset(list(range(100,111))+[110]*46+[100,105,105])
        self.assertEqual(p['pending_age'],2)
        self.assertEqual(p['classification'],'TIMEOUT_WITH_COUNTER_NOT_YET_MATURE')

    def test_no_counter_is_not_maturity(self):
        row,p=first_reset(list(range(100,111))+[110]*49)
        self.assertIsNone(p['pending_age'])
        self.assertEqual(p['classification'],'TIMEOUT_WITH_NO_PENDING_COUNTER')

    def test_monotone_and_flat_not_forced_into_cycles(self):
        for values in (np.arange(100.,260.),np.arange(260.,100.,-1),np.full(160,100.)):
            b=bars(values);result,rows=observe_frozen(b);check_trace(b,result,rows)
            self.assertEqual(result[0],[])

    def test_prefix_states_and_all_ledgers(self):
        b=waves_path();full,rows=observe_frozen(b)
        for t in (0,1,25,111,299,599):
            part,short=observe_frozen(b.iloc[:t+1]);self.assertEqual(short,rows[:t+1])
            self.assertEqual(part[1],[p for p in full[1] if p['confirmation_bar']<=t])
            self.assertEqual(part[3],[p for p in full[3] if p['maturity_bar']<=t])
            self.assertEqual(part[4],[p for p in full[4] if p['maturity_bar']<=t])

    def test_future_suffix_cannot_change_old_snapshots(self):
        b=waves_path();c=b.copy();c.loc[350:,['open','high','low','close']]*=2
        self.assertEqual(observe_frozen(b)[1][:350],observe_frozen(c)[1][:350])

    def test_before_and_at_reset_prefix(self):
        b=bars(list(range(100,111))+[110]*48+[111,110,109]);full,rows=observe_frozen(b)
        for t in (58,59):
            engine=MatureCounterRearmEngine(b.iloc[:t+1]);engine.run()
            self.assertEqual(snapshot(engine),rows[t]['post'])

    def test_independent_replay_calls_no_producer(self):
        with patch.object(MatureCounterRearmEngine,'run',side_effect=AssertionError('producer called')):
            self.assertEqual(len(replay([100,101,102,103,104])['rows']),5)

    def test_trace_tamper_detected(self):
        b=waves_path();result,rows=observe_frozen(b);bad=copy.deepcopy(rows)
        bad[30]['post']['raw_counter']=-1
        with self.assertRaises(ValueError):check_trace(b,result,bad)

    def test_joint_event_and_trace_omission_detected(self):
        b=waves_path();result,rows=observe_frozen(b);parts=list(copy.deepcopy(result));parts[1].pop()
        with self.assertRaises(ValueError):check_trace(b,parts,rows[:-1])

    def test_empty_paths_rejected(self):
        with self.assertRaises(ValueError):replay([])
        with self.assertRaises(ValueError):observe_frozen(bars([]))

    def test_overbudget_paths_rejected(self):
        with self.assertRaises(ValueError):replay([100.]*70115)
        with self.assertRaises(ValueError):observe_frozen(bars([100.]*70115))

    def test_nonfinite_prices_rejected(self):
        with self.assertRaises(ValueError):replay([100.,float('nan')])
        with self.assertRaises(ValueError):observe_frozen(bars([100.,float('inf')]))

    def test_floor_control_selection_is_nonvacuous(self):
        b=bars(200+np.random.default_rng(42).choice([-1.,0.,1.],1000).cumsum())
        parent,c,base,r1,r2=analyze(b);_,rows=observe_frozen(b)
        summary=summarize(b,parent,c,base,r1,r2,rows)
        self.assertEqual(len(summary['R2_floor_controls']),8)
        for control in summary['R2_floor_controls']:
            self.assertEqual(min(control['up_leg_bars'],control['down_leg_bars']),4)
            self.assertEqual(len(control['R2_pivot_roles_under_R3']),3)

    def test_debug_observer_restores_process_trace(self):
        self.assertIsNone(sys.gettrace());observe_frozen(waves_path());self.assertIsNone(sys.gettrace())


class ClockDiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.b=waves_path();cls.parent,cls.c,cls.base,cls.r1,cls.r2=analyze(cls.b)
        cls.observed,cls.rows=observe_frozen(cls.b)
        cls.summary=summarize(cls.b,cls.parent,cls.c,cls.base,cls.r1,cls.r2,cls.rows)

    def test_every_wave_has_event_level_latency_identity(self):
        entries=latency_rows(self.c);self.assertTrue(entries)
        self.assertEqual(len(entries),len(self.c['waves']))
        for r in entries:self.assertEqual(r['confirmation_delay'],r['occurrence_separation']+r['counter_survival'])

    def test_invalid_latency_counter_gap_rejected(self):
        c=copy.deepcopy(self.c);w=c['waves'][0]
        m=next(x for x in c['maturities'] if x['maturity_bar']==w['known_from_bar'])
        m['counter_occurrence_bar']=w['end_bar']+1
        with self.assertRaises(ValueError):latency_rows(c)

    def test_duplicate_maturity_key_rejected(self):
        c=copy.deepcopy(self.c);c['maturities'].append(c['maturities'][0])
        with self.assertRaises(ValueError):latency_rows(c)

    def test_independent_subset_and_gap_accounting(self):
        check_subset_counts(self.summary,self.base,self.r1,self.c,len(self.b))

    def test_subset_tamper_rejected(self):
        s=copy.deepcopy(self.summary);s['R1_recovery']['exact_92_subset_recovered']+=1
        with self.assertRaises(ValueError):check_subset_counts(s,self.base,self.r1,self.c,len(self.b))

    def test_joint_frequency_has_no_dropped_waves(self):
        a=self.summary['final_low_latency']
        self.assertEqual(sum(r['count'] for r in a['joint_frequency']),len(self.c['waves']))

    def test_joint_short_low_is_bounded_by_both_margins(self):
        for x in self.summary['joint_short_low_amplitude']['counts'].values():
            self.assertLessEqual(x['joint_count'],x['low_amplitude_count'])
            self.assertLessEqual(x['joint_count'],x['short_count'])
            self.assertGreaterEqual(x['joint_count'],0)

    def test_no_formal_mechanism_or_authority_promotion(self):
        s=self.summary
        self.assertFalse(s['R3_readiness_passed']);self.assertFalse(s['R4_selected'])
        self.assertFalse(s['one_minute_admitted']);self.assertFalse(s['visual_manual_acceptance'])
        self.assertFalse(any(s['authority'].values()))

    def test_incomplete_trace_rejected(self):
        with self.assertRaises(ValueError):summarize(self.b,self.parent,self.c,self.base,self.r1,self.r2,self.rows[:-1])

    def test_protocol_keeps_parent_population_and_new_diagnostic_frozen(self):
        p=json.loads((ROOT/'executor/wave_r3_clock_protocol_v1.json').read_text())
        self.assertEqual(sum(p['fixed_residuals'].values()),588)
        self.assertEqual(p['controls']['R1_exact_new_subset'],92)
        self.assertEqual(p['joint_diagnostic']['duration_max'],21)
        self.assertEqual(p['joint_diagnostic']['amplitude_max'],0.006026317779015855)
        self.assertFalse(p['R4_selected']);self.assertFalse(p['R3_readiness_passed'])

if __name__=='__main__':unittest.main()
