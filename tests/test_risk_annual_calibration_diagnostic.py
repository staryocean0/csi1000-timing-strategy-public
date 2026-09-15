import json
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PROFILE="risk-v2-15m-annual-calibration-diagnostic-v1"
class AnnualCalibrationDiagnosticTest(unittest.TestCase):
    def test_sources_compile_and_no_candidate_search(self):
        for name in ("risk_annual_calibration_diagnostic.py","risk_annual_calibration_diagnostic_verifier.py","risk_annual_calibration_diagnostic_broker.py","risk_annual_calibration_diagnostic_private_mirror.py"):
            text=(ROOT/"executor"/name).read_text();compile(text,name,"exec")
        p=json.loads((ROOT/"docs/research/RISK_TOOL_V2_15M_ANNUAL_CALIBRATION_DIAGNOSTIC_PREREG_20260915.json").read_text())
        self.assertTrue(p["decision_boundary"]["no_candidate_calibrator_search"]);self.assertTrue(p["decision_boundary"]["no_clipping_parameter_search"]);self.assertTrue(p["decision_boundary"]["no_acceptance_threshold_change"])
        self.assertFalse(p["scope"]["year_2026_read"])
    def test_parent_bottleneck_is_locked(self):
        p=json.loads((ROOT/"docs/research/RISK_TOOL_V2_15M_ANNUAL_CALIBRATION_DIAGNOSTIC_PREREG_20260915.json").read_text())
        self.assertEqual(p["parent_temporal_run"],"34919074188-1");self.assertEqual(p["parent_current_bottleneck"],"annual.calibration");self.assertEqual(p["known_failed_logloss_years_from_parent"],[2016,2019,2021])
    def test_mirror_is_bounded_text_only(self):
        m=(ROOT/"executor/risk_annual_calibration_diagnostic_private_mirror.py").read_text()
        for name in ("SUMMARY.json","ANNUAL_CALIBRATION_DIAGNOSTICS.csv","INPUT_DATA_RECEIPT.json","MODEL_INPUT_RECEIPT.json"):self.assertIn(name,m)
        self.assertNotIn(".parquet",m);self.assertIn('state.get("compute_success") is not True',m)
    def test_standard_route_registered(self):
        w=(ROOT/".github/workflows/public-compute.yml").read_text();c=(ROOT/".github/workflows/controller-dispatch.yml").read_text()
        self.assertIn(PROFILE,w);self.assertIn("python3 executor/risk_annual_calibration_diagnostic_broker.py",w);self.assertIn("python3 executor/risk_annual_calibration_diagnostic_private_mirror.py",w)
        self.assertIn("controller: "+PROFILE,c);self.assertIn("profile='"+PROFILE+"'",c)
if __name__=="__main__":unittest.main()
