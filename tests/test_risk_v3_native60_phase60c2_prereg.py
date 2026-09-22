from __future__ import annotations
import hashlib,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PREREG=ROOT/"docs/research/RISK_TOOL_V3_NATIVE60_PHASE60C2_STATE_HYSTERESIS_PREREG_20260922.json"
SHA="5a00ecfcd72ab5a83161b427870ad7aa20eb268710872449eaf31e8f422aeed4"

class Native60Phase60C2PreregTests(unittest.TestCase):
    def setUp(self):
        self.raw=PREREG.read_bytes();self.v=json.loads(self.raw)

    def test_identity_parent_and_selected_score_are_frozen(self):
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(),SHA)
        self.assertEqual(self.v["task_id"],"CSI1000-RISK-V3-NATIVE60-PHASE60C2-STATE-THRESHOLD-HYSTERESIS-V1-20260922")
        p=self.v["parent_authority"]
        self.assertEqual(p["phase60c1_run_id"],"35707010735-1")
        self.assertEqual(p["phase60c1_required_status"],"NATIVE60_STATE_SCORE_SELECTION_COMPLETE")
        self.assertEqual(p["phase60c1_result_git_blob_sha"],"526ab0f40eee4edfa4763eb9aec78f70a12db1e8")
        self.assertEqual(p["phase60c1_receipt_git_blob_sha"],"79d7565d9e93891c8c10178ad9393abc5a4260d7")
        self.assertEqual(p["selected_score"]["candidate_id"],"rv_rel__raw")
        self.assertEqual(p["selected_score"]["alpha"],1.0)

    def test_score_semantics_cannot_change(self):
        s=self.v["frozen_score_semantics"]
        self.assertEqual((s["lookback_same_slot_observations"],s["minimum_prior_same_slot_observations"]),(60,40))
        self.assertTrue(s["current_observation_excluded"])
        self.assertEqual(s["smoothing"],"none")
        self.assertTrue(s["modification_forbidden"])

    def test_threshold_grid_and_state_machine_are_exact(self):
        g=self.v["threshold_grid"]
        self.assertEqual(g["unsafe_entry_score"],[1.25,1.5,1.75])
        self.assertEqual(g["normal_exit_score"],[0.9,1.0,1.1])
        self.assertEqual(g["candidate_count"],9)
        self.assertTrue(g["no_additions_after_preregistration"])
        m=self.v["causal_state_machine"]
        self.assertIn("score >= U",m["normal_rule"])
        self.assertIn("RECOVERING",m["unsafe_rule"])
        self.assertIn("across lunch and overnight",m["carry_policy"])
        self.assertIn("cannot determine C2 selection",m["overnight_selection_policy"])

    def test_mechanism_gates_and_holdouts(self):
        g=self.v["mechanism_gates"]
        self.assertEqual(g["minimum_scored_rows"],2700)
        self.assertEqual((g["unsafe_share_overall_min"],g["unsafe_share_overall_max"]),(0.05,0.3))
        self.assertEqual((g["unsafe_normal_next_rv_mean_ratio_overall_min"],g["unsafe_normal_next_rv_mean_ratio_each_year_min"]),(1.3,1.1))
        self.assertEqual(g["next_rv_mean_ordering_overall"],"UNSAFE > RECOVERING > NORMAL")
        self.assertEqual(g["same_day_unsafe_to_unsafe_or_recovering_probability_min"],0.4)
        w=self.v["development_window"]
        self.assertEqual(w["years"],[2021,2022,2023])
        self.assertIn("sealed_repeat_audit_holdout",w["2024_2025_role"])
        self.assertEqual(w["2026_role"],"sealed")

    def test_selection_authority_and_lifecycle_are_closed(self):
        self.assertEqual(self.v["selection_rule"]["selected_state_authority"],"development state-definition candidate only; it is not holdout-validated, calibrated probability, trading, or production authority")
        self.assertIn("2024-2025",self.v["next_phase_contract"]["on_complete"])
        self.assertTrue(all(x is False for x in self.v["controls"].values()))
        r=self.v["result_surface"]
        self.assertTrue(r["aggregate_only"]);self.assertTrue(r["must_report_all_9_candidates"])
        f=self.v["preregistration_lifecycle"]
        self.assertTrue(f["implementation_after_prereg_merge_only"])
        self.assertFalse(f["execution_profile_registered_at_prereg"])
        self.assertFalse(f["controller_route_registered_at_prereg"])
        self.assertGreaterEqual(len(self.v["non_rescue"]),7)

if __name__=="__main__":unittest.main()
