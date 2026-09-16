from __future__ import annotations
import ast, hashlib, json, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PREREG=ROOT/"docs/research/RISK_TOOL_V3_NATIVE15_PHASE_C1_STATE_MACHINE_CANDIDATES_PREREG_20260916.json"
PRODUCER=ROOT/"executor/risk_v3_native15_state_machine_candidates.py"
VERIFIER=ROOT/"executor/risk_v3_native15_state_machine_candidates_verifier.py"
BROKER=ROOT/"executor/risk_v3_native15_state_machine_candidates_broker.py"
MIRROR=ROOT/"executor/risk_v3_native15_state_machine_candidates_private_mirror.py"
WORKFLOW=ROOT/".github/workflows/public-compute.yml"
CONTROLLER=ROOT/".github/workflows/controller-dispatch.yml"
PROFILE="risk-v3-native15-state-machine-candidates-v1"
PREREG_SHA="ecee5f8fbb3bd070a4e2550b9b24078fd1e0d539a90a48db0cb1d613389d8750"

class Native15PhaseC1ContractTests(unittest.TestCase):
    def test_prereg_identity_and_grid(self):
        self.assertEqual(hashlib.sha256(PREREG.read_bytes()).hexdigest(),PREREG_SHA)
        p=json.loads(PREREG.read_text())
        self.assertEqual(p["data"]["development_window"]["years"],[2021,2022,2023])
        self.assertEqual(p["data"]["repeat_audit_years_reserved"],[2024,2025])
        self.assertEqual(p["data"]["fresh_year_reserved"],2026)
        g=p["candidate_grid"]
        self.assertEqual(g["rv_window_native_bars"],[3,4,5,6])
        self.assertEqual(g["bg_window_prior_primary_returns"],[16,24,32,48])
        self.assertEqual(g["shock_sigma"],[2.5,3.0,3.5,4.0])
        self.assertEqual(g["highvol_ratio"],[1.25,1.5,1.75])
        self.assertEqual(g["recovery_normal_ratio"],[1.05,1.1,1.2])
        self.assertEqual(g["candidate_count"],576)
        self.assertEqual(p["shortlist"]["max_candidates"],12)
        self.assertEqual(p["shortlist"]["minimum_passing_candidates_for_completion"],3)
        self.assertFalse(p["shortlist"]["authority"])
        self.assertTrue(all(v is False for v in p["controls"].values()))

    def test_sources_parse_and_verifier_is_independent(self):
        for path in (PRODUCER,VERIFIER,BROKER,MIRROR):
            ast.parse(path.read_text(),filename=str(path))
        v=VERIFIER.read_text()
        self.assertNotIn("import risk_v3_native15_state_machine_candidates",v)
        self.assertIn("native15_c1_candidate_map_recompute_mismatch",v)
        self.assertIn("candidate_count_mismatch",v)
        self.assertIn("NATIVE15_STATE_MACHINE_CANDIDATE_MAP_COMPLETE",v)

    def test_holdout_and_parent_pins(self):
        prod=PRODUCER.read_text(); broker=BROKER.read_text()
        self.assertIn('DEV_START="2021-01-01"',prod)
        self.assertIn('DEV_END="2023-12-31"',prod)
        self.assertIn('dataset.to_table(columns=["timestamp","trading_day","symbol","close"]',prod)
        self.assertIn('PARENT_REF="runs/public-research/34986321499-1"',broker)
        self.assertIn('PARENT_BLOB_SHA="3b3d6c42014fb733c565d4318e325648c2812ca8"',broker)
        self.assertIn('CARRIER_SHA256="d69e87662d9e525396ed776b754ff43fca58dd021df4a84f96b60a6a5e4864d6"',broker)
        self.assertIn('"repeat_audit_years_materialized":False',broker)
        self.assertIn('"fresh_year_materialized":False',broker)

    def test_no_installation_or_trading_authority(self):
        for path in (PRODUCER,BROKER,MIRROR):
            text=path.read_text()
            self.assertIn("production_authority",text)
        prod=PRODUCER.read_text()
        self.assertIn('"state_machine_installation":False',prod)
        self.assertIn('"strategy_routing":False',prod)
        self.assertIn('"pnl":False',prod)

    def test_standard_control_plane_route_is_exact(self):
        wf=WORKFLOW.read_text(); ctl=CONTROLLER.read_text()
        self.assertIn(f"          - {PROFILE}",wf)
        self.assertGreaterEqual(wf.count(PROFILE),7)
        self.assertIn(f"controller: {PROFILE}",ctl)
        self.assertGreaterEqual(ctl.count(PROFILE),2)
        self.assertIn("github.event.issue.number == 227",ctl)
        self.assertIn("two-wave-v0800-f-operational-state-stream-audit-v1",ctl)

if __name__=="__main__": unittest.main()
