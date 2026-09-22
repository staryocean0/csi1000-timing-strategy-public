from __future__ import annotations
import hashlib, json, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PREREG=ROOT/"docs/research/RISK_TOOL_V3_NATIVE60_PHASE60C1_STATE_SCORE_PREREG_20260922.json"
SHA="1c3c72747b8327c10a52cf007f4d696fd374370c001e89ec989d4241a598469c"

class Native60Phase60C1PreregTests(unittest.TestCase):
    def setUp(self):
        self.raw=PREREG.read_bytes()
        self.v=json.loads(self.raw)

    def test_identity_parent_and_holdouts(self):
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(),SHA)
        self.assertEqual(self.v["task_id"],"CSI1000-RISK-V3-NATIVE60-PHASE60C1-CAUSAL-STATE-SCORE-SELECTION-V1-20260922")
        p=self.v["parent_authority"]
        self.assertEqual(p["phase60a_run_id"],"35053098772-1")
        self.assertEqual(p["phase60b_run_id"],"35057818977-1")
        self.assertEqual(p["phase60b_required_status"],"NATIVE60_DESCRIPTIVE_MAP_COMPLETE")
        self.assertEqual(p["phase60b_result_git_blob_sha"],"287fbf999c95f34dd5b70029332d711dcc650ec2")
        self.assertEqual(p["phase60b_receipt_git_blob_sha"],"c279914d7ef5ae0ce4c3031b86eafcf8438e8e39")
        c=p["canonical_60m"]
        self.assertEqual((c["rows"],c["trading_days"],c["symbol"]),(2908,727,"000852.SH"))
        self.assertEqual(c["sha256"],"4414d08c6e256fcb7d151018b935d26363be04920990c7b1c56880c8ec7e0467")
        w=self.v["development_window"]
        self.assertEqual(w["years"],[2021,2022,2023])
        self.assertEqual(w["2024_2025_role"],"sealed_repeat_audit_holdout")
        self.assertEqual(w["2026_role"],"sealed")

    def test_causal_normalization_and_candidate_grid(self):
        n=self.v["causal_slot_normalization"]
        self.assertEqual((n["lookback_same_slot_observations"],n["minimum_prior_same_slot_observations"]),(60,40))
        self.assertTrue(n["current_observation_excluded_from_baseline"])
        self.assertEqual(set(self.v["candidate_base_scores"]),{"rv_rel","range_rel","body_rel","rv_range_geo"})
        m=self.v["native_bar_memory_variants"]
        self.assertEqual(set(m),{"raw","ewma50","ewma25"})
        self.assertEqual((m["raw"]["alpha"],m["ewma50"]["alpha"],m["ewma25"]["alpha"]),(1,0.5,0.25))
        self.assertEqual(self.v["candidate_count"],12)

    def test_pair_semantics_and_mechanism_gates_are_frozen(self):
        p=self.v["primary_pair_semantics"]
        self.assertEqual((p["lag1_pair_max_per_complete_day"],p["lag2_pair_max_per_complete_day"],p["lag3_pair_max_per_complete_day"]),(3,2,1))
        self.assertIn("same trading day",p["next_bar"])
        self.assertIn("cannot affect C1 selection",p["overnight"])
        self.assertEqual(p["primary_target"],"next_bar_intrabar_rv_1m")
        g=self.v["mechanism_gates"]
        self.assertEqual(g["minimum_scored_rows"],2700)
        self.assertEqual(g["lag1_spearman_overall_min"],0.25)
        self.assertEqual(g["lag1_spearman_each_year_min"],0.1)
        self.assertEqual(g["top_bottom_next_rv_mean_ratio_overall_min"],1.3)
        self.assertEqual(g["top_bottom_next_rv_mean_ratio_each_year_min"],1.1)
        self.assertTrue(g["next_rv_quartile_means_nondecreasing_overall"])
        self.assertEqual((g["q4_share_each_slot_min"],g["q4_share_each_slot_max"]),(0.1,0.4))

    def test_selection_is_deterministic_but_not_final_state_authority(self):
        s=self.v["selection_rule"]
        self.assertIn("every mechanism gate",s["eligible"])
        self.assertEqual(len(s["if_one_or_more"]),6)
        self.assertIn("not a final risk state",s["selected_score_authority"])
        self.assertEqual(self.v["allowed_statuses"],[
            "NATIVE60_STATE_SCORE_SELECTION_COMPLETE",
            "NATIVE60_STATE_SCORE_SELECTION_INSUFFICIENT",
            "NATIVE60_STATE_SCORE_SELECTION_NOT_READY",
        ])
        self.assertIn("separate task",self.v["next_phase_contract"]["on_complete"])
        self.assertTrue(all(x is False for x in self.v["controls"].values()))

    def test_result_surface_and_prereg_lifecycle(self):
        r=self.v["result_surface"]
        self.assertTrue(r["aggregate_only"])
        self.assertTrue(r["forbid_row_level_timestamps_prices_returns"])
        self.assertTrue(r["must_report_all_12_candidates"])
        self.assertTrue(r["must_report_gate_pass_fail_per_candidate"])
        self.assertTrue(r["must_report_selected_candidate_or_null"])
        self.assertTrue(r["empirical_conditional_probabilities_are_descriptive_not_calibrated"])
        f=self.v["preregistration_lifecycle"]
        self.assertTrue(f["implementation_after_prereg_merge_only"])
        self.assertFalse(f["execution_profile_registered_at_prereg"])
        self.assertFalse(f["controller_route_registered_at_prereg"])
        self.assertGreaterEqual(len(self.v["non_rescue"]),6)

if __name__=="__main__":
    unittest.main()
