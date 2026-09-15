from __future__ import annotations
import ast, hashlib, json, re, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
EXEC=ROOT/"executor"
DOC=ROOT/"docs"/"research"/"RISK_TOOL_V3_NATIVE15_PHASE_B_DESCRIPTIVE_MAP_PREREG_20260915.json"
RUNNER=EXEC/"risk_v3_native15_descriptive_risk_map.py"
BROKER=EXEC/"risk_v3_native15_descriptive_risk_map_broker.py"
VERIFIER=EXEC/"risk_v3_native15_descriptive_risk_map_verifier.py"
MIRROR=EXEC/"risk_v3_native15_descriptive_risk_map_private_mirror.py"
WORKFLOW=ROOT/".github"/"workflows"/"public-compute.yml"
CONTROLLER=ROOT/".github"/"workflows"/"controller-dispatch.yml"
PROFILE="risk-v3-native15-descriptive-risk-map-v1"

def sha256(path:Path)->str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

class Native15PhaseBTests(unittest.TestCase):
    def test_sources_parse_without_runtime_dependencies(self):
        for path in (RUNNER,BROKER,VERIFIER,MIRROR): ast.parse(path.read_text(),filename=str(path))

    def test_prereg_freezes_development_map_and_holdouts(self):
        p=json.loads(DOC.read_text())
        self.assertEqual(p["profile"],PROFILE)
        self.assertEqual(p["data_window"]["development_years"],[2021,2022,2023])
        self.assertEqual(p["data_window"]["repeat_audit_years_untouched"],[2024,2025])
        self.assertEqual(p["data_window"]["fresh_year_untouched"],2026)
        self.assertEqual(p["native_scale"]["base_interval_minutes"],15)
        self.assertEqual(p["native_scale"]["session_offset_minutes"],5)
        self.assertTrue(p["interpretation"]["no_parameter_winner"])
        for key in ("threshold_optimization","window_search","state_machine_installation","model_fit","calibration","use_2024_2025_market_values","use_2026_market_values","strategy_routing","position_sizing","pnl","production_authority","copy_v2_constants_as_native15_authority"):
            self.assertFalse(p["hard_boundaries"][key])
        src=RUNNER.read_text(); m=re.search(r'PREREG_SHA256="([0-9a-f]{64})"',src)
        self.assertIsNotNone(m); self.assertEqual(m.group(1),sha256(DOC))

    def test_runner_is_native15_descriptive_only(self):
        src=RUNNER.read_text()
        self.assertIn('columns=["timestamp","trading_day","symbol","close"]',src)
        self.assertIn('(ds.field("trading_day")>=DEV_START)&(ds.field("trading_day")<=DEV_END)',src)
        self.assertIn('DEV_START="2021-01-01"',src); self.assertIn('DEV_END="2023-12-31"',src)
        self.assertIn('TAIL_Q=[0.90,0.95,0.99]',src); self.assertIn('ACF_LAGS=[1,2,3,4,5,6,7,8]',src)
        self.assertIn('"primary_return_pairs":',DOC.read_text())
        for token in ("RV_WINDOW","BG_WINDOW","SHOCK_SIGMA","HIGHVOL_RATIO","RECOVERY_NORMAL_RATIO","sklearn","fit(","predict_proba"):
            self.assertNotIn(token,src)

    def test_verifier_independently_recomputes_map(self):
        src=VERIFIER.read_text()
        self.assertNotIn("risk_v3_native15_descriptive_risk_map.py",src)
        self.assertNotIn("import risk_v3_native15_descriptive_risk_map",src)
        self.assertIn("recompute_result",src); self.assertIn("descriptive_map_recompute_mismatch",src)
        self.assertIn('dataset.to_table(columns=["timestamp","trading_day","symbol","close"],filter=filt)',src)

    def test_broker_pins_phase_a_and_fixed_carrier(self):
        src=BROKER.read_text()
        self.assertIn('PARENT_REF="runs/public-research/34982948347-1"',src)
        self.assertIn('PARENT_BLOB_SHA="f92fd121990caefc97cde7037ea5dad72541981c"',src)
        self.assertIn('PARENT_STATUS="NATIVE15_CARRIER_SEMANTICS_VALID"',src)
        self.assertIn('CARRIER_SHA256="d69e87662d9e525396ed776b754ff43fca58dd021df4a84f96b60a6a5e4864d6"',src)
        self.assertIn('"new_training":False',src); self.assertIn('"production_authority":False',src); self.assertIn("verify_parent(api)",src)

    def test_mirror_and_standard_routes_are_bounded(self):
        mirror=MIRROR.read_text(); workflow=WORKFLOW.read_text(); controller=CONTROLLER.read_text()
        self.assertIn("NATIVE15_DESCRIPTIVE_RISK_MAP.json",mirror); self.assertIn("row_level_forbidden",mirror)
        self.assertIn(PROFILE,workflow); self.assertIn("controller: "+PROFILE,controller)
        self.assertIn("risk_v3_native15_descriptive_risk_map_broker.py",workflow)
        self.assertIn("risk_v3_native15_descriptive_risk_map_private_mirror.py",workflow)

if __name__=="__main__": unittest.main()
