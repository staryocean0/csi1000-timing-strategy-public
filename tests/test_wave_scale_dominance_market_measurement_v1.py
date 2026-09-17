import ast,json,math,sys,unittest
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'executor'))
import wave_scale_dominance_market_measurement_v1 as m
from wave_scale_dominance_synthetic_v1 import clean_scale,fast_same_range,monotone_unfinished,mixed_scales


def rows(case):
    p=case['prices'];return [(-5*(len(p)-1-i),float(v)) for i,v in enumerate(p)]

class MarketMeasurementTests(unittest.TestCase):
    def test_clean_scale_recovers_supplied_peak_without_threshold(self):
        a=m.measure_phase(rows(clean_scale(.002)));b=m.measure_phase(rows(clean_scale(.05)))
        self.assertEqual((a['shape'],a['best_turn_index']),('PEAK',30));self.assertEqual((b['shape'],b['best_turn_index']),('PEAK',30))
        self.assertLess(a['delta_search_adjusted_bic_vs_background'],0);self.assertLess(b['delta_search_adjusted_bic_vs_background'],0)
    def test_amplitude_does_not_change_turn_geometry(self):
        a=m.measure_phase(rows(clean_scale(.002)));b=m.measure_phase(rows(clean_scale(.05)))
        for k in ('best_turn_index','best_turn_relative_minute','shape','eligible_knots'):self.assertEqual(a[k],b[k])
    def test_fast_same_range_is_raw_evidence_not_state(self):
        r=m.measure_phase(rows(fast_same_range()));self.assertGreater(r['tortuosity'],8);self.assertGreater(r['delta_search_adjusted_bic_vs_background'],0)
    def test_monotone_is_no_reversal_even_if_piecewise_searches(self):
        r=m.measure_phase(rows(monotone_unfinished()));self.assertEqual(r['shape'],'NO_REVERSAL');self.assertAlmostEqual(r['tortuosity'],1)
    def test_mixed_case_keeps_intermediate_residual_structure(self):
        r=m.measure_phase(rows(mixed_scales()));self.assertEqual(r['shape'],'PEAK');self.assertGreater(r['tortuosity'],5);self.assertGreater(r['normalized_rmse_to_log_range'],0)
    def test_search_penalty_is_frozen_formula(self):
        r=m.measure_phase(rows(clean_scale(.05)));self.assertAlmostEqual(r['search_penalty'],2*math.log(r['eligible_knots']),places=13)
        self.assertGreaterEqual(r['best_second_adjusted_bic_gap'],0)
    def test_panel_has_five_phases_and_no_state_assignment(self):
        rr=rows(clean_scale(.03));p=m.measure_panel('0'*20,{f'offset{i}':rr for i in range(5)})
        self.assertEqual(p['phase_count'],5);self.assertEqual(p['dominance_state'],'UNASSIGNED_THRESHOLD_FREE');self.assertFalse(p['threshold_selected'])
        self.assertEqual(p['phase_stability']['shape_agreement_max'],5);self.assertEqual(p['phase_stability']['turn_relative_minute_range'],0)
    def test_protocol_freezes_no_labels_no_thresholds(self):
        p=json.loads((ROOT/'docs/research/TWO_WAVE_SCALE_DOMINANCE_MARKET_PROTOCOL_20260917.json').read_text())
        self.assertEqual(p['research_issue'],372);self.assertFalse(p['reference_labels_visible_to_compute']);self.assertFalse(p['threshold_selection_in_run']);self.assertIsNone(p['numeric_state_thresholds'])
        self.assertEqual(p['fixed_reference']['final_reference_labels_sha256'],'6fb36ee74413c9b7e95824a94a89bec74a493513668a36b3373c24518fc834be')
    def test_measurement_module_has_no_io_network_or_label_loader(self):
        text=(ROOT/'executor/wave_scale_dominance_market_measurement_v1.py').read_text();tree=ast.parse(text)
        forbidden={'open','read_parquet','read_csv','urlopen','request','system','Popen','exec','eval'}
        for node in ast.walk(tree):
            if isinstance(node,ast.Call):self.assertNotIn(getattr(node.func,'id',getattr(node.func,'attr','')),forbidden)
        self.assertNotIn('final_annotations',text);self.assertNotIn('pass_a_sealed',text)
    def test_workflow_and_controller_route_exact_profile(self):
        profile='two-wave-scale-dominance-diagnostic-measurement-v1';w=(ROOT/'.github/workflows/public-compute.yml').read_text();c=(ROOT/'.github/workflows/controller-dispatch.yml').read_text()
        self.assertEqual(w.count(profile),12);self.assertEqual(c.count(profile),3);self.assertEqual(w.count('secrets.FACTORLAB_PRIVATE_TOKEN'),2)
    def test_independent_verifier_preserves_nonfinite_outlier_semantics(self):
        import wave_scale_dominance_market_verifier_v1 as v
        self.assertEqual(v.outlier(np.asarray([0.,0.,0.,1.])),(None,True))
        self.assertEqual(v.outlier(np.zeros(4)),(None,False))

    def test_output_contract_is_diagnostics_only(self):
        e=(ROOT/'executor/wave_scale_dominance_market_entry_v1.py').read_text();self.assertIn("OUTPUTS={'diagnostics.jsonl','diagnostic_summary.json'}",e)
        self.assertNotIn('reference_labels.json',e);self.assertNotIn('full_inventory.json',e)

if __name__=='__main__':unittest.main()
