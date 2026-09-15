import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PROFILE="risk-v2-15m-annual-calibration-drift-diagnostic-v1"

class CalibrationDriftDiagnosticContractTest(unittest.TestCase):
    def test_prereg_is_diagnostic_only_and_frozen(self):
        p=json.loads((ROOT/"docs/research/RISK_TOOL_V2_15M_ANNUAL_CALIBRATION_DRIFT_DIAGNOSTIC_20260915.json").read_text())
        self.assertEqual(p["status"],"frozen_before_finer_decomposition_read")
        self.assertEqual(p["parent_bottleneck"],"annual.calibration")
        self.assertEqual(p["horizon_minutes"],15)
        self.assertFalse(p["year_2026_read"])
        self.assertEqual(p["fixed_decomposition"]["calibrated_C_probability_band_edges"],[0.0,0.05,0.1,0.2,0.4,0.6,0.8,0.9,0.95,1.0])
        self.assertTrue(p["interpretation_rules"]["diagnostic_only"])
        self.assertFalse(p["interpretation_rules"]["no_acceptance_state_change"] is False)
        self.assertTrue(p["interpretation_rules"]["future_candidate_requires_new_profile_id_and_new_pre_result_freeze"])
    def test_code_has_no_fit_or_2026_path(self):
        runner=(ROOT/"executor/risk_15m_annual_calibration_drift_diagnostic.py").read_text()
        verifier=(ROOT/"executor/risk_15m_annual_calibration_drift_verifier.py").read_text()
        broker=(ROOT/"executor/risk_15m_annual_calibration_drift_broker.py").read_text()
        mirror=(ROOT/"executor/risk_15m_annual_calibration_drift_private_mirror.py").read_text()
        for name,text in (("runner",runner),("verifier",verifier),("broker",broker),("mirror",mirror)):
            compile(text,name,"exec")
        self.assertNotIn("fit_ridge(",runner);self.assertNotIn("fit_platt(",runner)
        self.assertNotIn("2026.parquet",runner);self.assertNotIn("2026.parquet",broker)
        self.assertIn('HORIZON = 15',runner)
        self.assertIn('SYMBOL = "000852.SH"',runner)
        self.assertIn('PARENT_RUN_REF="runs/public-research/34919074188-1"',broker)
    def test_mirror_is_bounded_text_only(self):
        text=(ROOT/"executor/risk_15m_annual_calibration_drift_private_mirror.py").read_text()
        for name in ("DIAGNOSTIC_SUMMARY.json","YEAR_DECOMPOSITION.csv","CELL_DECOMPOSITION.csv","PROBABILITY_BAND_DECOMPOSITION.csv","INPUT_DATA_RECEIPT.json","MODEL_INPUT_RECEIPT.json"):
            self.assertIn(name,text)
        self.assertNotIn(".parquet",text)
        self.assertIn('state.get("compute_success") is not True',text)
    def test_workflow_controller_register_exact_profile(self):
        workflow=(ROOT/".github/workflows/public-compute.yml").read_text();controller=(ROOT/".github/workflows/controller-dispatch.yml").read_text()
        self.assertIn(PROFILE,workflow);self.assertIn("python3 executor/risk_15m_annual_calibration_drift_broker.py",workflow)
        self.assertIn("python3 executor/risk_15m_annual_calibration_drift_private_mirror.py",workflow)
        self.assertIn("controller: "+PROFILE,controller);self.assertIn("profile='"+PROFILE+"'",controller)

if __name__=="__main__":unittest.main()
