from __future__ import annotations
import ast, hashlib, json, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PREREG=ROOT/"docs/research/RISK_TOOL_V3_NATIVE60_PHASE60A_PREREG_20260916.json"
PRODUCER=ROOT/"executor/risk_v3_native60_phase60a.py"
VERIFIER=ROOT/"executor/risk_v3_native60_phase60a_verifier.py"
BROKER=ROOT/"executor/risk_v3_native60_phase60a_broker.py"
MIRROR=ROOT/"executor/risk_v3_native60_phase60a_private_mirror.py"
WORKFLOW=ROOT/".github/workflows/public-compute.yml"
CONTROLLER=ROOT/".github/workflows/controller-dispatch.yml"
PROFILE="risk-v3-native60-phase60a-canonical-carrier-v1"
TITLE="controller: risk-v3-native60-phase60a-canonical-carrier-v1"
SHA="8e423b664520d272c041fd4f4734c541d59e76c5b2d0aa91e6a36f88e2eb1b69"

class Native60Phase60ATests(unittest.TestCase):
    def test_prereg_identity_source_and_topdown_geometry(self):
        raw=PREREG.read_bytes();self.assertEqual(hashlib.sha256(raw).hexdigest(),SHA)
        v=json.loads(raw)
        self.assertEqual(v["roadmap_authority"]["direction"],"60m -> 15m -> 5m")
        self.assertEqual(v["source"]["path"],"data/index/1m_official.parquet")
        self.assertEqual(v["source"]["sha256"],"c06f936a86df71d5192728c981929b362da27f952cc31d0afd7bd889a58037ae")
        self.assertEqual(v["source"]["bytes"],13245274)
        self.assertFalse(v["source"]["provider_60m_view_available"])
        self.assertEqual([x["wallclock"] for x in v["canonical_60m_geometry"]],["09:30-10:30","10:30-11:30","13:00-14:00","14:00-15:00"])
        self.assertTrue(v["membership"]["lunch_break_hard_boundary"])
        self.assertEqual(v["membership"]["complete_bucket_expected_1m_rows"],60)
        self.assertEqual(v["membership"]["complete_day_expected_1m_rows"],240)
        self.assertEqual(v["membership"]["complete_day_expected_60m_bars"],4)

    def test_holdouts_and_no_scientific_authority(self):
        v=json.loads(PREREG.read_text())
        d=v["development_materialization"]
        self.assertEqual(d["years"],[2021,2022,2023]);self.assertFalse(d["use_2024_2025_market_values"]);self.assertFalse(d["use_2026_market_values"])
        self.assertTrue(all(x is False for x in v["controls"].values()))
        self.assertEqual(v["result_contract"]["next_phase_if_valid"],"native60_phase60b_volatility_continuity_map_preregister_separately")

    def test_producer_uses_official_1m_predicate_pushdown_and_path_energy(self):
        s=PRODUCER.read_text();ast.parse(s)
        self.assertIn('inputs/"1m_official.parquet"',s)
        self.assertIn('ds.dataset(carrier,format="parquet")',s)
        self.assertIn('ds.field("trading_day")>=DEV_START',s)
        self.assertIn('ds.field("symbol")==SYMBOL',s)
        self.assertNotIn("5m_offset_0.parquet",s);self.assertNotIn("15m_offset_5.parquet",s)
        self.assertIn('"intrabar_rv_1m"',s);self.assertIn('"range_log"',s);self.assertIn('"body_abs_log"',s)
        self.assertIn('set(range(571,691))|set(range(781,901))',s)
        self.assertIn('set(range(570,690))|set(range(780,900))',s)

    def test_verifier_is_independent_and_exact(self):
        s=VERIFIER.read_text();ast.parse(s)
        self.assertNotIn("import risk_v3_native60_phase60a",s)
        self.assertIn("independently_recompute",s)
        self.assertIn("assert_frame_equal",s)
        self.assertIn("verifier_audit_exact_compare_failed",s)
        self.assertIn('ds.field("trading_day")>=DEV_START',s)

    def test_broker_and_mirror_are_bounded(self):
        b=BROKER.read_text();m=MIRROR.read_text();ast.parse(b);ast.parse(m)
        self.assertIn("data/index/1m_official.parquet",b)
        self.assertIn("c06f936a86df71d5192728c981929b362da27f952cc31d0afd7bd889a58037ae",b)
        self.assertIn("NATIVE60_PHASE60A_AUDIT.json",m)
        self.assertNotIn("NATIVE60_CANONICAL_60M.parquet",m)
        self.assertIn("row_level_forbidden",m)

    def test_standard_control_plane_route_is_exact(self):
        w=WORKFLOW.read_text();c=CONTROLLER.read_text()
        self.assertIn(PROFILE,w);self.assertIn(TITLE,c)
        self.assertIn("risk_v3_native60_phase60a_broker.py prepare",w)
        self.assertIn("risk_v3_native60_phase60a_broker.py compute",w)
        self.assertIn("risk_v3_native60_phase60a_broker.py cleanup",w)
        self.assertIn("risk_v3_native60_phase60a_broker.py publish",w)
        self.assertIn("risk_v3_native60_phase60a_private_mirror.py",w)

if __name__=="__main__":unittest.main()
