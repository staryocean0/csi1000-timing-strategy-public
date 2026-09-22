from __future__ import annotations
import ast, hashlib, json, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PREREG=ROOT/"docs/research/RISK_TOOL_V3_NATIVE60_PHASE60C1_STATE_SCORE_PREREG_20260922.json"
PRODUCER=ROOT/"executor/risk_v3_native60_phase60c1_state_score.py"
VERIFIER=ROOT/"executor/risk_v3_native60_phase60c1_state_score_verifier.py"
BROKER=ROOT/"executor/risk_v3_native60_phase60c1_state_score_broker.py"
MIRROR=ROOT/"executor/risk_v3_native60_phase60c1_state_score_private_mirror.py"
WORKFLOW=ROOT/".github/workflows/public-compute.yml"
CONTROLLER=ROOT/".github/workflows/controller-dispatch.yml"
PROFILE="risk-v3-native60-phase60c1-state-score-selection-v1"
TITLE="controller: "+PROFILE
SHA="1c3c72747b8327c10a52cf007f4d696fd374370c001e89ec989d4241a598469c"

class Native60Phase60C1ImplementationTests(unittest.TestCase):
    def test_prereg_immutable(self):
        self.assertEqual(hashlib.sha256(PREREG.read_bytes()).hexdigest(),SHA)

    def test_sources_parse_and_verifier_is_independent(self):
        for p in (PRODUCER,VERIFIER,BROKER,MIRROR):ast.parse(p.read_text())
        s=VERIFIER.read_text()
        self.assertNotIn("import risk_v3_native60_phase60c1_state_score",s)
        self.assertIn("verifier_exact_compare_failed",s)
        self.assertIn('{"status":"passed"',s)

    def test_broker_pins_phase60b_and_phase60a_canonical(self):
        b=BROKER.read_text()
        for token in (
            'PHASE60B_RUN="35057818977-1"',
            'PHASE60B_RESULT_BLOB="287fbf999c95f34dd5b70029332d711dcc650ec2"',
            'PHASE60B_RECEIPT_BLOB="c279914d7ef5ae0ce4c3031b86eafcf8438e8e39"',
            'PHASE60B_RELEASE_ID=389649468',
            'PHASE60A_RELEASE_ID=389624963',
            'CANON_BYTES=165623',
            'CANON_SHA256="4414d08c6e256fcb7d151018b935d26363be04920990c7b1c56880c8ec7e0467"',
            'CANON_MEMBER="study/NATIVE60_CANONICAL_60M.parquet"',
        ): self.assertIn(token,b)
        self.assertNotIn("1m_official.parquet",b)
        self.assertNotIn("15m_offset_5.parquet",b)

    def test_producer_implements_exact_12_candidate_score_grid(self):
        s=PRODUCER.read_text()
        self.assertIn('BASES=["rv_rel","range_rel","body_rel","rv_range_geo"]',s)
        self.assertIn('MEMORY={"raw":1.0,"ewma50":0.5,"ewma25":0.25}',s)
        self.assertIn("lookback_same_slot_observations",PREREG.read_text())
        self.assertIn('rolling(LOOKBACK,min_periods=MIN_PRIOR).median()',s)
        self.assertIn('for base in BASES:',s)
        self.assertIn('for mem,alpha in MEMORY.items():',s)
        self.assertIn('"candidate_count":len(candidates)',s)
        self.assertIn('"scientific_authority":"development_state_score_selection_only"',s)
        self.assertIn('"empirical_probabilities":"descriptive_not_calibrated"',s)
        self.assertIn('"production_authority":False',s)
        self.assertIn('"threshold_search":False',s)
        self.assertIn('"final_state_machine_installation":False',s)

    def test_selection_rule_and_holdouts_match_frozen_contract(self):
        v=json.loads(PREREG.read_text())
        self.assertEqual(v["candidate_count"],12)
        self.assertEqual(v["mechanism_gates"]["minimum_scored_rows"],2700)
        self.assertEqual(v["mechanism_gates"]["lag1_spearman_overall_min"],0.25)
        self.assertEqual(v["mechanism_gates"]["top_bottom_next_rv_mean_ratio_overall_min"],1.3)
        self.assertEqual(v["development_window"]["2024_2025_role"],"sealed_repeat_audit_holdout")
        self.assertEqual(v["development_window"]["2026_role"],"sealed")
        self.assertTrue(all(x is False for x in v["controls"].values()))

    def test_mirror_is_aggregate_only_and_state_authority_remains_closed(self):
        m=MIRROR.read_text()
        self.assertIn("NATIVE60_PHASE60C1_STATE_SCORE.json",m)
        self.assertNotIn("NATIVE60_CANONICAL_60M.parquet",m)
        self.assertIn("native60c1_mirror_row_level_forbidden",m)
        self.assertIn("development_state_score_selection_only",m)
        self.assertIn("descriptive_not_calibrated",m)

    def test_standard_control_plane_route_is_exact_and_secret_surface_unchanged(self):
        w=WORKFLOW.read_text();c=CONTROLLER.read_text()
        self.assertIn(PROFILE,w);self.assertIn(TITLE,c)
        for phase in ("prepare","compute","cleanup","publish"):
            self.assertIn(f"risk_v3_native60_phase60c1_state_score_broker.py {phase} {PROFILE}",w)
        self.assertIn("risk_v3_native60_phase60c1_state_score_private_mirror.py",w)
        self.assertEqual(w.count("FACTORLAB_PRIVATE_TOKEN"),2)

if __name__=="__main__":unittest.main()
