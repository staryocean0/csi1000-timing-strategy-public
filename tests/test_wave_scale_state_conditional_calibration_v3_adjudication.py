import hashlib
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ADJ=ROOT/'docs/research/TWO_WAVE_SCALE_STATE_CONDITIONAL_CALIBRATION_V3_LOYO_ADJUDICATION_20260918.json'
AGG=ROOT/'docs/research/TWO_WAVE_SCALE_STATE_CONDITIONAL_CALIBRATION_V3_LOYO_AGGREGATE_20260918.json'
LIN=ROOT/'docs/research/TWO_WAVE_RESEARCH_LINEAGE_20260916.json'
AUTH=ROOT/'docs/research/TWO_WAVE_SEGMENTATION_DOMINANCE_THREAD_AUTHORITY_20260917.json'

class CalibrationV3AdjudicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a=json.loads(ADJ.read_text()); cls.g=json.loads(AGG.read_text())
        cls.l=json.loads(LIN.read_text())['ordered_lineage']; cls.u=json.loads(AUTH.read_text())

    def test_public_aggregate_identity_and_no_panel_mapping(self):
        self.assertEqual(hashlib.sha256(AGG.read_bytes()).hexdigest(),'60a4b963d69bcb6776f6018fe1f6c210ca3e6fd74985bd9027cc6cb71cd3bfdc')
        self.assertNotIn('panel_id',AGG.read_text())
        self.assertFalse(self.g['full_192_fit_performed'])
        self.assertFalse(self.g['lag_selected_or_promoted'])

    def test_coverage_repaired_but_ambiguity_and_validity_block(self):
        k=self.a['key_findings']
        self.assertTrue(k['morphology_abstention_collapse_repaired'])
        self.assertEqual(k['supported_to_turning_by_lag']['0'],'64/75')
        self.assertEqual(k['developing_to_developing_by_lag']['0'],'45/61')
        self.assertEqual(k['true_ambiguous_recall_by_lag']['0'],'1/13')
        self.assertEqual(k['validity_invalid_recall_all_lags'],'7/19')
        self.assertEqual(k['validity_false_invalid_all_lags'],'8/173')

    def test_no_lag_promotion_or_full_fit(self):
        s=self.a['stop_rule']
        self.assertFalse(s['lag_selected_or_promoted']); self.assertFalse(s['full_192_fit_authorized'])
        self.assertFalse(s['full_192_fit_performed']); self.assertFalse(s['pnl_tuning'])
        self.assertEqual(s['next'],'PREREGISTER_CALIBRATION_V4_THREE_CLASS_AMBIGUITY_AND_BROADER_VALIDITY_FAMILY')

    def test_lineage_appends_without_rewriting_history(self):
        self.assertEqual(len(self.l),38)
        row=self.l[37]
        prior=json.dumps(self.l[:37],sort_keys=True,separators=(',',':')).encode()
        self.assertEqual(hashlib.sha256(prior).hexdigest(),row['history_guard_prior_37_sha256'])
        self.assertEqual((row['order'],row['issue']),(38,388))
        self.assertFalse(row['full_192_fit_performed']); self.assertFalse(row['lag_promoted'])

    def test_authority_stays_nonproduction(self):
        lane=next(x for x in self.u['active_lanes'] if x['issue']==353)
        self.assertEqual(lane['status'],'CALIBRATION_V3_DEVELOPMENT_OOF_NOT_READY_AMBIGUITY_VALIDITY_REVISION_REQUIRED')
        self.assertEqual(self.u['S2_progress']['next'],'PREREGISTER_CALIBRATION_V4_THREE_CLASS_AMBIGUITY_AND_BROADER_VALIDITY_FAMILY')
        self.assertFalse(self.u['S2_progress']['calibration_v3_lag_promoted'])
        self.assertFalse(self.u['S2_progress']['full_192_fit_performed'])
        self.assertFalse(self.u['authority']['production'])

if __name__=='__main__': unittest.main()
