import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PROFILE="risk-v2-temporal-stability-2015-2025-v1"

class TemporalStabilityAuditContractTest(unittest.TestCase):
    def test_scripts_compile_and_scope_is_frozen(self):
        for name in ("risk_temporal_stability_2015_2025.py","risk_temporal_stability_2015_2025_verifier.py","risk_temporal_stability_2015_2025_broker.py","risk_temporal_stability_private_mirror.py"):
            text=(ROOT/"executor"/name).read_text();compile(text,name,"exec")
        runner=(ROOT/"executor/risk_temporal_stability_2015_2025.py").read_text()
        self.assertIn("HARD_YEARS = tuple(y for y in YEARS if y != 2020)",runner)
        self.assertIn('SYMBOL = "000852.SH"',runner)
        self.assertNotIn("2026.parquet",runner)
        self.assertNotIn("fit_ridge(",runner);self.assertNotIn("fit_platt(",runner)
    def test_prereg_remains_bound_to_original_v1_profile(self):
        pre=json.loads((ROOT/"docs/research/RISK_TOOL_V2_TEMPORAL_STABILITY_2015_2025_PREREG_20260915.json").read_text())
        v1=json.loads((ROOT/"docs/acceptance/risk_tool_v2/temporal_stability_profile_hierarchical_v1.json").read_text())
        self.assertEqual(pre["active_acceptance_profile"],v1["profile_id"])
        self.assertEqual(v1["profile_id"],"risk-tool-v2-temporal-stability-hierarchical-v1")
        self.assertEqual(pre["warmup_year"],2020)
        self.assertFalse(pre["scope"]["year_2026_read"])
    def test_mirror_is_text_only_and_success_only(self):
        text=(ROOT/"executor/risk_temporal_stability_private_mirror.py").read_text()
        for name in ("SUMMARY.json","TEMPORAL_METRICS.csv","ACCEPTANCE_RESULT.json","INPUT_DATA_RECEIPT.json","MODEL_INPUT_RECEIPT.json"):self.assertIn(name,text)
        self.assertIn('state.get("compute_success") is not True',text)
        self.assertNotIn(".parquet",text)
    def test_workflow_and_controller_register_exact_profile(self):
        workflow=(ROOT/".github/workflows/public-compute.yml").read_text();controller=(ROOT/".github/workflows/controller-dispatch.yml").read_text()
        self.assertIn(PROFILE,workflow);self.assertIn("python3 executor/risk_temporal_stability_2015_2025_broker.py",workflow)
        self.assertIn("python3 executor/risk_temporal_stability_private_mirror.py",workflow)
        self.assertIn("controller: "+PROFILE,controller);self.assertIn("profile='"+PROFILE+"'",controller)

if __name__=="__main__":unittest.main()
