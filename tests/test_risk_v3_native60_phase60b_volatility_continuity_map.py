from __future__ import annotations
import ast, hashlib, json, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PREREG=ROOT/"docs/research/RISK_TOOL_V3_NATIVE60_PHASE60B_VOLATILITY_CONTINUITY_MAP_PREREG_20260916.json"
PRODUCER=ROOT/"executor/risk_v3_native60_phase60b_volatility_continuity_map.py"
VERIFIER=ROOT/"executor/risk_v3_native60_phase60b_volatility_continuity_map_verifier.py"
BROKER=ROOT/"executor/risk_v3_native60_phase60b_volatility_continuity_map_broker.py"
MIRROR=ROOT/"executor/risk_v3_native60_phase60b_volatility_continuity_map_private_mirror.py"
WORKFLOW=ROOT/".github/workflows/public-compute.yml"
CONTROLLER=ROOT/".github/workflows/controller-dispatch.yml"
PROFILE="risk-v3-native60-phase60b-volatility-continuity-map-v1"
TITLE="controller: risk-v3-native60-phase60b-volatility-continuity-map-v1"
SHA="cc1fe933fa4339f937d01d8f1d39f7d0ba86d8d3903806008c97afcd9675973b"

class Native60Phase60BImplementationTests(unittest.TestCase):
    def test_prereg_immutable(self):
        self.assertEqual(hashlib.sha256(PREREG.read_bytes()).hexdigest(),SHA)

    def test_all_python_sources_parse_and_verifier_independent(self):
        for p in (PRODUCER,VERIFIER,BROKER,MIRROR):ast.parse(p.read_text())
        s=VERIFIER.read_text()
        self.assertNotIn("import risk_v3_native60_phase60b_volatility_continuity_map",s)
        self.assertIn("verifier_exact_compare_failed",s)
        self.assertIn('{"status":"passed"',s)

    def test_parent_archive_and_canonical_are_exactly_pinned(self):
        b=BROKER.read_text();ast.parse(b)
        for token in ('PARENT_RUN="35053098772-1"','PARENT_RESULT_BLOB="b96e80bd4c1f1ec7645b62b4ca3a012b92505c9e"','PARENT_RECEIPT_BLOB="760611e931b7e30181d569d8338fe04f4cbad114"','PARENT_RELEASE_ID=389624963','PARENT_ARCHIVE_BYTES=133785','PARENT_ARCHIVE_SHA256="797507b2ceed2f8458e109e8393ad6a8bc12bf92a00e1ad619cfd919535496a2"','CANON_BYTES=165623','CANON_SHA256="4414d08c6e256fcb7d151018b935d26363be04920990c7b1c56880c8ec7e0467"','CANON_MEMBER="study/NATIVE60_CANONICAL_60M.parquet"'):self.assertIn(token,b)
        self.assertNotIn("1m_official.parquet",b);self.assertNotIn("15m_offset_5.parquet",b)

    def test_producer_contract_and_pair_geometry(self):
        s=PRODUCER.read_text();ast.parse(s)
        self.assertIn('OBS=["body_abs_log","range_log","cc_abs_logret_within_day","intrabar_rv_1m"]',s)
        self.assertIn('for lag in (1,2,3)',s);self.assertIn('zip(SLOTS[:-1],SLOTS[1:])',s)
        v=json.loads(PREREG.read_text());exp=v["lag_persistence"]["expected_pair_counts"]
        self.assertEqual(exp["body_abs_log"],{"lag1":2181,"lag2":1454,"lag3":727})
        self.assertEqual(exp["cc_abs_logret_within_day"],{"lag1":1454,"lag2":727,"lag3":0})
        self.assertEqual(v["secondary_overnight_diagnostic"]["expected_pairs"],726)

    def test_mirror_is_aggregate_only_and_no_authority(self):
        m=MIRROR.read_text();ast.parse(m)
        self.assertIn("NATIVE60_PHASE60B_MAP.json",m);self.assertNotIn("NATIVE60_CANONICAL_60M.parquet",m);self.assertIn("native60b_mirror_row_level_forbidden",m)
        p=PRODUCER.read_text()
        for token in ('"next_phase_authorized":False','"continuity_pass_fail_claim":False','"observable_ranking":False','"production_authority":False','"choose_best_observable":False'):self.assertIn(token,p)

    def test_standard_control_plane_route_is_exact(self):
        w=WORKFLOW.read_text();c=CONTROLLER.read_text()
        self.assertIn(PROFILE,w);self.assertIn(TITLE,c)
        for phase in ("prepare","compute","cleanup","publish"):self.assertIn(f"risk_v3_native60_phase60b_volatility_continuity_map_broker.py {phase}",w)
        self.assertIn("risk_v3_native60_phase60b_volatility_continuity_map_private_mirror.py",w)

if __name__=="__main__":unittest.main()
