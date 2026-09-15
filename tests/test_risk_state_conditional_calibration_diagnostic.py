import json,py_compile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];PROFILE="risk-v2-15m-state-conditional-calibration-diagnostic-v1";P=json.loads((ROOT/"docs/research/RISK_TOOL_V2_15M_STATE_CONDITIONAL_CALIBRATION_DIAGNOSTIC_V1_PREREG_20260915.json").read_text())
class StateConditionalCalibrationDiagnosticTest(unittest.TestCase):
    def test_target_and_streak_are_frozen(self):
        self.assertEqual(P["target"]["horizon_minutes"],15);self.assertEqual(P["target"]["current_bottleneck"],"weekly.calibration");self.assertEqual(P["target"]["streak_length"],12);self.assertEqual(P["data_scope"]["streak_labels"],[f"2023-W{i:02d}" for i in range(21,33)])
    def test_scope_is_diagnostic_only(self):
        self.assertTrue(P["interpretation"]["diagnostic_only"]);self.assertTrue(P["interpretation"]["no_new_acceptance_gate"]);self.assertTrue(P["interpretation"]["v3_verdict_remains_immutable"])
        for k in ("candidate_search","calibration_refit","tail_parameter_search","numeric_threshold_change","model_change","year_2026_read","pnl","strategy_routing","production_authority"):self.assertTrue(P["prohibitions"][k])
    def test_authority_parent_is_exact(self):
        a=P["authority_chain"];self.assertEqual(a["parent_summary"]["git_blob_sha1"],"ba8be4a8655283eda1e0534d3d26770b2662a3e9");self.assertEqual(a["parent_streak"]["git_blob_sha1"],"12106d5440fd6869ffa5c8a31a51766380bc0f76")
    def test_sources_compile_and_verifier_is_independent(self):
        for n in ("risk_state_conditional_calibration_diagnostic.py","risk_state_conditional_calibration_diagnostic_verifier.py","risk_state_conditional_calibration_diagnostic_broker.py","risk_state_conditional_calibration_diagnostic_private_mirror.py"):py_compile.compile(str(ROOT/"executor"/n),doraise=True)
        v=(ROOT/"executor/risk_state_conditional_calibration_diagnostic_verifier.py").read_text();self.assertNotIn("risk_state_conditional_calibration_diagnostic.py",v);self.assertIn("authority_metric_drift",v)
    def test_no_rescue_surface(self):
        src=(ROOT/"executor/risk_state_conditional_calibration_diagnostic.py").read_text().lower();self.assertNotIn("2026.parquet",src);self.assertNotIn("optimize",src);self.assertNotIn("grid",src);self.assertNotIn("fit(",src);self.assertNotIn("pnl",src)
    def test_mirror_is_text_only(self):
        m=(ROOT/"executor/risk_state_conditional_calibration_diagnostic_private_mirror.py").read_text();self.assertIn("MAX_BYTES",m);self.assertNotIn("parquet",m.lower())
    def test_standard_routes_registered(self):
        w=(ROOT/".github/workflows/public-compute.yml").read_text();c=(ROOT/".github/workflows/controller-dispatch.yml").read_text();self.assertIn(PROFILE,w);self.assertIn("controller: "+PROFILE,c)
if __name__=="__main__":unittest.main()
