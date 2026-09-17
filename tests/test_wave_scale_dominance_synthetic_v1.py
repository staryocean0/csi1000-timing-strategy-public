import ast, math, unittest
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'executor'))
import wave_scale_dominance_diagnostics_v1 as d
import wave_scale_dominance_synthetic_v1 as s


class ScaleDominanceSyntheticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r=s.run_suite(); cls.c=cls.r['cases']

    def test_suite_is_synthetic_and_threshold_free(self):
        self.assertEqual(self.r['data_role'],'DETERMINISTIC_SYNTHETIC_ONLY')
        self.assertIsNone(self.r['market_run'])
        self.assertIsNone(self.r['numeric_dominance_thresholds'])
        self.assertIsNone(self.r['persistence_or_hysteresis_thresholds'])
        self.assertFalse(self.r['R4_selected']);self.assertFalse(self.r['router_pnl'])

    def test_low_and_high_amplitude_clean_waves_share_geometry(self):
        lo=self.c['low_amplitude_clean']['diagnostic']; hi=self.c['high_amplitude_clean']['diagnostic']
        self.assertEqual(self.c['low_amplitude_clean']['reference_label'],'CURRENT_SCALE_SUPPORTED')
        self.assertEqual(self.c['high_amplitude_clean']['reference_label'],'CURRENT_SCALE_SUPPORTED')
        self.assertAlmostEqual(lo['tortuosity'],2.0);self.assertAlmostEqual(hi['tortuosity'],2.0)
        self.assertEqual(lo['piecewise']['shape'],'PEAK');self.assertEqual(hi['piecewise']['shape'],'PEAK')
        self.assertGreater(lo['piecewise']['fractional_sse_improvement'],.999999)
        self.assertGreater(hi['piecewise']['fractional_sse_improvement'],.999999)

    def test_same_range_fast_structure_is_not_confused_with_amplitude(self):
        clean=self.c['high_amplitude_clean']['diagnostic']; fast=self.c['same_range_fast']['diagnostic']
        self.assertAlmostEqual(clean['log_range'],fast['log_range'],places=12)
        self.assertAlmostEqual(clean['tortuosity'],2.0);self.assertAlmostEqual(fast['tortuosity'],12.0)
        self.assertLess(clean['piecewise']['sse_ratio_to_background'],1e-12)
        self.assertGreater(fast['piecewise']['sse_ratio_to_background'],.9)
        self.assertEqual(self.c['same_range_fast']['reference_label'],'FASTER_STRUCTURE_GENERATOR')

    def test_monotone_path_is_developing_not_forced_wave(self):
        x=self.c['monotone_unfinished']['diagnostic']
        self.assertIsNone(x['piecewise']);self.assertEqual(x['background_selected'],'ONE_LEG_TREND')
        self.assertAlmostEqual(x['tortuosity'],1.0)
        self.assertEqual(x['reason'],'DEVELOPING_OR_INSUFFICIENT_MORPHOLOGY_HYPOTHESIS')

    def test_nonsinusoidal_valid_wave_can_have_structured_residual(self):
        x=self.c['nonsinusoidal_valid']['diagnostic']['piecewise']
        self.assertLess(x['sse_ratio_to_background'],.1)
        self.assertGreater(x['residual_lag1'],.9)
        self.assertEqual(self.c['nonsinusoidal_valid']['reference_label'],'CURRENT_SCALE_SUPPORTED_NON_SINUSOIDAL')

    def test_mixed_scales_are_intermediate_evidence_not_auto_state(self):
        x=self.c['mixed_scales']['diagnostic']
        self.assertGreater(x['tortuosity'],self.c['high_amplitude_clean']['diagnostic']['tortuosity'])
        self.assertGreater(x['piecewise']['sse_ratio_to_background'],.1)
        self.assertLess(x['piecewise']['sse_ratio_to_background'],.9)
        self.assertEqual(x['dominance_state'],'UNASSIGNED_THRESHOLD_FREE')

    def test_jump_is_visible_as_outlier_evidence(self):
        x=self.c['jump_outlier']['diagnostic']['piecewise']
        self.assertGreater(x['robust_outlier_score'],50)
        self.assertEqual(self.c['jump_outlier']['reference_label'],'AMBIGUOUS_OUTLIER_GENERATOR')

    def test_near_constant_is_explicit(self):
        x=self.c['near_constant']['diagnostic']
        self.assertTrue(x['near_constant']);self.assertIsNone(x['piecewise'])
        self.assertEqual(self.c['near_constant']['reference_label'],'INSUFFICIENT_SUPPORT_NEAR_CONSTANT')

    def test_scale_transition_degrades_without_rewriting_prefix(self):
        row=self.c['scale_transition']; pre=row['prefix_diagnostic']; full=row['full_diagnostic']
        self.assertLess(pre['piecewise']['sse_ratio_to_background'],1e-12)
        self.assertGreater(full['piecewise']['sse_ratio_to_background'],.8)
        self.assertGreater(full['tortuosity'],pre['tortuosity'])
        case=s.scale_transition(); replay=d.diagnose(case['prices'][:case['prefix_length']],turn_index=case['turn_index'])
        self.assertEqual(pre,replay)

    def test_offsets_are_sensitivity_only(self):
        rows=self.r['offset_probe']['offsets']
        self.assertEqual([x['offset'] for x in rows],list(range(5)))
        ratios=[x['diagnostic']['piecewise']['sse_ratio_to_background'] for x in rows]
        self.assertGreater(max(ratios)-min(ratios),1e-3)
        for x in rows:
            self.assertEqual(x['diagnostic']['dominance_state'],'UNASSIGNED_THRESHOLD_FREE')
            self.assertEqual(x['diagnostic']['aliasing_conclusion'],'NOT_AUTHORIZED')

    def test_known_from_requires_exact_prefix_end(self):
        x=s.clean_scale(.02)['prices']
        with self.assertRaises(ValueError):d.diagnose(x,turn_index=s.TURN,known_from=len(x)-2)

    def test_turn_requires_support_on_both_sides(self):
        x=s.clean_scale(.02)['prices']
        for turn in (0,1,len(x)-2,len(x)-1):
            with self.assertRaises(ValueError):d.diagnose(x,turn_index=turn)

    def test_invalid_prices_fail_closed(self):
        for x in ([1,0,2],[1,float('nan'),2],[1,float('inf'),2]):
            with self.assertRaises(ValueError):d.diagnose(x,turn_index=None)

    def test_bic_numeric_floor_is_stable_below_machine_noise(self):
        t=d._design_time(21); design=d.np.column_stack([d.np.ones(21),t])
        y=4.0+0.2*t
        exact=d._fit('EXACT',y,design)
        perturbed=y.copy();perturbed[3]+=1e-15
        tiny=d._fit('TINY',perturbed,design)
        self.assertLessEqual(exact.sse/21,d.BIC_VARIANCE_FLOOR)
        self.assertLessEqual(tiny.sse/21,d.BIC_VARIANCE_FLOOR)
        self.assertEqual(exact.bic,tiny.bic)

    def test_modules_have_no_file_network_or_process_calls(self):
        forbidden={'open','read_csv','read_parquet','write_text','write_bytes','urlopen','request','Popen','run','system','exec','eval'}
        for name in ('wave_scale_dominance_diagnostics_v1.py','wave_scale_dominance_synthetic_v1.py'):
            tree=ast.parse((ROOT/'executor'/name).read_text())
            for node in ast.walk(tree):
                if isinstance(node,ast.Call):
                    called=getattr(node.func,'id',getattr(node.func,'attr',''))
                    self.assertNotIn(called,forbidden,(name,called))

    def test_no_case_outputs_a_final_dominance_state(self):
        for row in self.c.values():
            for key in ('diagnostic','prefix_diagnostic','full_diagnostic'):
                if key in row:self.assertEqual(row[key]['dominance_state'],'UNASSIGNED_THRESHOLD_FREE')

if __name__=='__main__':unittest.main()
