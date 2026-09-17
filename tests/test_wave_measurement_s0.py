"""Constructed proofs plus frozen-R3 controls, never real-market acceptance."""
import ast
import hashlib
import json
from pathlib import Path
import sys
import unittest
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'executor'))
import wave_measurement_audit_s0 as s


class MeasurementCounterexampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report=s.run_suite(); cls.f=cls.report['findings']

    def test_counter_updates_are_not_reversals(self):
        r=self.f['counter_updates']
        self.assertEqual(r['counter_updates_before_reset'],48)
        self.assertEqual(r['direction_changes_after_peak'],0)
        self.assertEqual(r['candidate_age'],49)
        self.assertEqual(r['pending_age'],1)

    def test_one_reversal_control_triggers_frozen_reset(self):
        r=self.f['counter_updates']
        self.assertEqual(r['first_reset'],59)
        self.assertEqual(r['resets'],1)

    def test_amplitude_change_does_not_relabel_time_scale(self):
        r=self.f['amplitude']
        self.assertTrue(r['same_event_positions'])
        self.assertGreater(r['completed_waves'],0)
        self.assertEqual(r['low_durations'],r['high_durations'])
        self.assertEqual(set(r['low_durations']),{40})
        self.assertGreater(r['high_range']/r['low_range'],100)

    def test_wicks_do_not_change_close_selected_event_clocks(self):
        r=self.f['wicks']
        self.assertTrue(r['same_event_positions']);self.assertTrue(r['geometry_changed'])
        self.assertLess(r['narrow_ohlc_range'],.006026317779015855)
        self.assertGreater(r['wide_ohlc_range'],.01809810178917548)

    def test_large_unfinished_motion_is_not_forced_into_a_cycle(self):
        r=self.f['unfinished']
        self.assertEqual(r['completed_waves'],0);self.assertEqual(r['resets'],0)
        self.assertTrue(r['live_candidate_present'])
        self.assertEqual(r['completed_cycle_coverage'],0.)

    def test_range_duration_is_a_confound_without_any_reversal(self):
        r=self.f['range_duration']
        self.assertEqual(r['direction_changes'],0)
        self.assertAlmostEqual(r['long_log_range']/r['short_log_range'],10)

    def test_equal_ohlc_does_not_determine_intrabar_order(self):
        r=self.f['ohlc_information_loss']
        self.assertTrue(r['native_paths_differ']);self.assertTrue(r['offset0_ohlc_equal'])
        self.assertFalse(r['offset2_ohlc_equal'])

    def test_ohlc_is_first_max_min_last_not_a_filter(self):
        np.testing.assert_array_equal(s.ohlc_groups([100,102,97,105,101]),[[100,105,97,101]])

    def test_coarse_close_retains_high_frequency_alias_amplitude(self):
        r=self.f['alias']
        self.assertGreater(r['native_frequency'],r['coarse_sample_frequency']/2)
        for q in r['offsets']:
            self.assertAlmostEqual(q['fitted_amplitude'],1.,places=11)
            self.assertLess(q['exact_alias_identity_max_error'],1e-10)

    def test_apparent_period_stable_across_all_offsets_despite_alias(self):
        self.assertEqual([r['offset'] for r in self.f['alias']['offsets']],list(range(5)))
        self.assertEqual({r['apparent_period_coarse_bars'] for r in self.f['alias']['offsets']},{20})
        self.assertAlmostEqual(self.f['alias']['native_period'],1/.21)

    def test_offset_phase_is_not_claimed_invariant(self):
        n=np.arange(1005);x=100+np.sin(2*np.pi*.21*n)
        a=s.ohlc_groups(x)[:199,3];b=s.ohlc_groups(x,offset=1)[:199,3]
        self.assertGreater(float(np.max(np.abs(a-b))),.5)

    def test_nonlinear_low_nodes_can_carry_a_slow_envelope(self):
        r=self.f['skeleton']
        self.assertTrue(r['all_selected_nodes_are_local_minima'])
        self.assertLess(r['slow_envelope_max_error'],1e-10)
        self.assertEqual(r['low_nodes'],100);self.assertEqual(r['nodes_before'],400)
        self.assertGreater(min(r['native_carrier_and_sidebands']),r['lower_envelope_frequency'])

    def test_exact_reconstruction_cannot_identify_the_right_skeleton(self):
        self.assertEqual(len(self.f['skeleton']['two_different_skeleton_reconstruction_errors']),2)
        self.assertTrue(all(x<1e-10 for x in self.f['skeleton']['two_different_skeleton_reconstruction_errors']))

    def test_occurrence_coverage_not_live_knowledge(self):
        r=self.f['coverage_clocks']
        self.assertEqual(r['retrospective_covered_bars_before_cutoff'],11)
        self.assertEqual(r['completed_cycles_known_by_cutoff_covered_bars'],0)

    def test_mathematical_and_project_controls_are_explicitly_separate(self):
        self.assertEqual(self.f['skeleton']['kind'],'ANALYTIC_NONLINEAR_ENVELOPE_NOT_PROJECT_REPLAY')
        self.assertEqual(self.f['counter_updates']['kind'],'FROZEN_R3_SYNTHETIC')

    def test_no_market_conclusion_or_new_candidate(self):
        self.assertIsNone(self.report['market_run'])
        self.assertEqual(self.report['real_R3_residual_aliasing'],'UNDETERMINED')
        for key in ('new_detector_selected','new_readiness_gate_selected','R3_promoted',
                    'one_minute_strategy_admitted','production_authority'):
            self.assertFalse(self.report[key])

    def test_empty_or_multidimensional_or_overbudget_rejected(self):
        for values in ([],np.ones((2,3)),np.ones(s.MAX_POINTS+1)):
            with self.assertRaises(ValueError):s.vector(values)

    def test_invalid_prices_rejected(self):
        for v in (0.,-1.,float('nan'),float('inf')):
            with self.assertRaises(ValueError):s.vector([100.,v])

    def test_invalid_offsets_and_width_rejected(self):
        for width,offset in ((1,0),(65,0),(5,-1),(5,5),(True,0),(5,1.5)):
            with self.assertRaises(ValueError):s.ohlc_groups([100.]*20,width,offset)

    def test_partial_groups_not_fabricated(self):
        self.assertEqual(s.ohlc_groups([100.]*12).shape,(2,4))
        with self.assertRaises(ValueError):s.ohlc_groups([100.]*4)

    def test_zero_changes_and_ties(self):
        self.assertEqual(s.direction_changes([1,1,2,2,3]),0)
        self.assertEqual(s.direction_changes([1,2,2,1,1,2]),2)
        self.assertEqual(s.direction_changes([2,2,2]),0)

    def test_no_future_suffix_changes_finalized_ohlc_groups(self):
        x=np.arange(100.,150.);y=x.copy();y[30:]+=100
        np.testing.assert_array_equal(s.ohlc_groups(x)[:6],s.ohlc_groups(y)[:6])

    def test_frozen_detector_prefix_clocks_preserved(self):
        b=s.bars(100+.2*s.triangle())
        full=s.MatureCounterRearmEngine(b).run()
        for t in (59,139,239):
            p=s.MatureCounterRearmEngine(b.iloc[:t+1]).run()
            self.assertEqual(p[1],[v for v in full[1] if v['confirmation_bar']<=t])
            self.assertEqual(p[3],[v for v in full[3] if v['maturity_bar']<=t])

    def test_invalid_wicks_rejected(self):
        for w in (-.01,.2,float('nan')):
            with self.assertRaises(ValueError):s.bars([100.]*10,w)

    def test_module_has_no_loading_writing_or_dispatch_calls(self):
        tree=ast.parse((ROOT/'executor/wave_measurement_audit_s0.py').read_text())
        forbidden={'open','read_parquet','read_csv','write_text','write_bytes','exec','eval',
                   'system','Popen','urlopen','request','main'}
        for node in ast.walk(tree):
            if isinstance(node,ast.Call):
                name=getattr(node.func,'id',getattr(node.func,'attr',''))
                self.assertNotIn(name,forbidden)


if __name__=='__main__':unittest.main()
