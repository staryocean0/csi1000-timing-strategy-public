import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'executor'))
from wave_recognizer_r1_residual_probe_v1 import replay,reset_evidence,episode_partition,reference_scope


def locked(final=103.0):
    # Candidate high at20; opposite minimum at21, then a large enclosed oscillation.
    x=[100,101,102,103,104,103,102,101,100,102,104,106,108]
    x += [108.25+(i-13)*.25 for i in range(13,21)]
    x += [90.0]
    x += [96.0+(4/3)*(6-abs((i-22)%12-6)) for i in range(22,69)]
    x += [final]
    return x


class SyntheticClockTests(unittest.TestCase):
    def test_lock_exists_despite_large_inner_oscillation(self):
        x=locked();r=replay(x);e=reset_evidence(x,r)[-1]
        self.assertEqual(e['reason'],'EARLY_COUNTER_LOCK')
        self.assertEqual(e['reset_bar'],69)
        self.assertEqual(e['progress_age'],49)
        self.assertEqual(e['counter_gap'],1)
        self.assertGreater(e['observed_sign_changes'],6)
    def test_internal_swings_are_not_one_bar_noise(self):
        x=locked(); piv=[i for i in range(23,68) if (x[i]>x[i-1] and x[i]>x[i+1]) or (x[i]<x[i-1] and x[i]<x[i+1])]
        self.assertGreaterEqual(len(piv),6)
        self.assertTrue(all(b-a>=4 for a,b in zip(piv,piv[1:])))
    def test_same_bar_new_extreme_can_be_skipped(self):
        x=locked(120);e=reset_evidence(x,replay(x))[-1]
        self.assertEqual(e['reason'],'SAME_BAR_EVIDENCE_SKIPPED')
        self.assertTrue(e['skipped_new_candidate'])
        self.assertFalse(e['skipped_valid_confirmation'])
    def test_same_bar_opposite_confirmation_can_be_skipped(self):
        x=locked(80);e=reset_evidence(x,replay(x))[-1]
        self.assertTrue(e['skipped_valid_confirmation'])
        self.assertFalse(e['skipped_new_candidate'])
    def test_before_timeout_is_not_reset(self):
        r=replay(locked()[:-1]);self.assertEqual(r['resets'],[])
    def test_counter_never_refreshes_progress_anchor(self):
        r=replay(locked())
        self.assertEqual(r['rows'][68]['progress_anchor'],20)
        self.assertEqual(r['rows'][68]['counter_age'],47)
    def test_prefix_invariance(self):
        x=locked()+[101,100,102,104,101,95,98,103];r=replay(x)
        for t in (0,4,10,21,30,68,69,len(x)-1):
            p=replay(x[:t+1])
            self.assertEqual(p['rows'],r['rows'][:t+1])
            self.assertEqual(p['pivots'],[v for v in r['pivots'] if v['confirmation_bar']<=t])
            self.assertEqual(p['resets'],[v for v in r['resets'] if v['bar_index']<=t])
    def test_future_suffix_cannot_change_past(self):
        a=replay(locked()+[80,120,75]);b=replay(locked()+[100,99,101])
        self.assertEqual(a['rows'][:70],b['rows'][:70])
    def test_normal_confirmations_never_have_short_occurrence_span(self):
        r=replay([100+i%9 for i in range(150)])
        for row in r['rows']:
            if row['action']=='CONFIRM':
                self.assertTrue(row['same_bar_valid_confirmation'])
    def test_monotone_does_not_reset_active_candidate(self):
        r=replay(range(100,260));self.assertEqual(r['resets'],[])
    def test_plateau_without_opposite_counter(self):
        x=list(range(100,121))+[120]*49;r=replay(x)
        self.assertEqual(reset_evidence(x,r)[-1]['reason'],'NO_OPPOSITE_COUNTER')
    def test_partition_conserves_all_bars(self):
        v=episode_partition(10,29,20,[False]*20+[True]*20)
        self.assertEqual(v['before_reset_bars']+v['reset_bar']+v['after_reset_bars'],v['bars'])
        self.assertEqual(v['old_blind_bars']+v['newly_blind_bars'],v['bars'])
        self.assertEqual(v['newly_blind_bars'],10)
    def test_partition_rejects_outside_reset(self):
        with self.assertRaises(ValueError):episode_partition(10,29,30,[False]*40)
    def test_invalid_prices_fail_closed(self):
        for x in ([],[100,0],[100,float('nan')],[100,float('inf')]):
            with self.assertRaises(ValueError):replay(x)
    def test_no_candidate_or_outcome_promotion(self):
        s=reference_scope();self.assertFalse(s['R2_selected']);self.assertFalse(any(s['authority'].values()))
    def test_input_not_mutated(self):
        x=locked();original=copy.deepcopy(x);replay(x);self.assertEqual(original,x)


if __name__=='__main__':unittest.main()
