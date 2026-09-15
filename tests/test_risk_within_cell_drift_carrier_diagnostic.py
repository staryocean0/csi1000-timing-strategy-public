import json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PROFILE="risk-v2-15m-within-cell-drift-carrier-diagnostic-v1"
PREREG=json.loads((ROOT/"docs/research/RISK_TOOL_V2_15M_WITHIN_CELL_DRIFT_CARRIER_DIAGNOSTIC_V1_PREREG_20260915.json").read_text())

class WithinCellCarrierDiagnosticTest(unittest.TestCase):
    def test_parent_and_scope_are_frozen(self):
        self.assertEqual(PREREG["authority_chain"]["state_conditional_run"],"34935354211-1")
        self.assertEqual(PREREG["authority_chain"]["state_summary"]["sha256"],"534892118a09008657c3a742ffd6c22f285a851f1bf1763eefb0a58536169777")
        self.assertEqual(PREREG["scope"]["horizon_minutes"],15);self.assertFalse(PREREG["scope"]["year_2026_read"])
        self.assertEqual([x["name"] for x in PREREG["frozen_carriers"]],["shock_intensity","vol_ratio","raw_severity_increment"])
    def test_non_rescue_contract(self):
        for v in PREREG["prohibitions"].values(): self.assertTrue(v)
        self.assertTrue(PREREG["descriptive_method"]["no_best_carrier_selection"]);self.assertTrue(PREREG["descriptive_method"]["no_significance_gate"])
        self.assertTrue(PREREG["interpretation"]["v3_verdict_immutable"]);self.assertTrue(PREREG["interpretation"]["diagnostic_cannot_promote_15m_to_complete"])
    def test_sources_compile_and_verifier_is_independent(self):
        prod=(ROOT/"executor/risk_within_cell_drift_carrier_diagnostic.py").read_text();ver=(ROOT/"executor/risk_within_cell_drift_carrier_diagnostic_verifier.py").read_text()
        compile(prod,"producer","exec");compile(ver,"verifier","exec")
        self.assertNotIn("risk_within_cell_drift_carrier_diagnostic.py",ver);self.assertNotIn("producer.",ver)
        for text in (prod,ver):
            self.assertIn("composition_component",text);self.assertIn("within_bin_component",text);self.assertNotIn("2026.parquet",text)
    def test_broker_and_mirror_are_bounded(self):
        b=(ROOT/"executor/risk_within_cell_drift_carrier_diagnostic_broker.py").read_text();m=(ROOT/"executor/risk_within_cell_drift_carrier_diagnostic_private_mirror.py").read_text()
        self.assertIn('PROFILE_NAME="'+PROFILE+'"',b);self.assertIn('PARENT_BRANCH="runs/public-research/34935354211-1"',b);self.assertIn('GITHUB_EVENT_NAME")!="workflow_dispatch"',b)
        self.assertIn("MAX_BYTES",m);self.assertNotIn("parquet",m.lower())
        for name in PREREG["outputs"]: self.assertIn(name,m)
    def test_standard_route_registered(self):
        w=(ROOT/".github/workflows/public-compute.yml").read_text();c=(ROOT/".github/workflows/controller-dispatch.yml").read_text()
        self.assertIn(PROFILE,w);self.assertIn("controller: "+PROFILE,c)

if __name__=="__main__":unittest.main()
