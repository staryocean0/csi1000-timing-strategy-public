from __future__ import annotations
import hashlib, json, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PREREG=ROOT/"docs/research/RISK_TOOL_V3_NATIVE60_PHASE60B_VOLATILITY_CONTINUITY_MAP_PREREG_20260916.json"
SHA="cc1fe933fa4339f937d01d8f1d39f7d0ba86d8d3903806008c97afcd9675973b"

class Native60Phase60BPreregTests(unittest.TestCase):
    def setUp(self):
        self.raw=PREREG.read_bytes(); self.v=json.loads(self.raw)

    def test_raw_identity_parent_and_holdouts(self):
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(),SHA)
        p=self.v["parent_authority"]; c=p["canonical_parquet"]
        self.assertEqual(p["public_research_run_id"],"35053098772-1")
        self.assertEqual(p["required_status"],"NATIVE60_CANONICAL_CARRIER_VALID")
        self.assertTrue(p["must_use_parent_parquet_directly"]); self.assertTrue(p["rebuild_from_1m_forbidden"])
        self.assertEqual((c["bytes"],c["rows"],c["trading_days"],c["bars_per_day"]),(165623,2908,727,4))
        self.assertEqual(c["sha256"],"4414d08c6e256fcb7d151018b935d26363be04920990c7b1c56880c8ec7e0467")
        self.assertEqual(c["timestamp_convention"],"end_labeled")
        self.assertEqual(self.v["scope"]["years"],[2021,2022,2023]); self.assertEqual(self.v["scope"]["holdout_years_sealed"],[2024,2025,2026])

    def test_observables_quantiles_and_structural_cc(self):
        obs={x["name"]:x for x in self.v["observables"]["primary"]}
        self.assertEqual(list(obs),["body_abs_log","range_log","cc_abs_logret_within_day","intrabar_rv_1m"])
        self.assertEqual(obs["cc_abs_logret_within_day"]["finite_expected"],2181)
        self.assertEqual(obs["cc_abs_logret_within_day"]["am1_policy"],"structural_null_not_imputed")
        self.assertTrue(self.v["observables"]["parallel_no_winner_selection"])
        q=self.v["quantile_contract"]
        self.assertEqual(q["grid"],[0.1,0.25,0.5,0.75,0.9,0.95,0.99]); self.assertEqual(q["method"],"linear")
        self.assertEqual(q["state_rules"],{"high":"x >= q75","low":"x <= q25","mid":"q25 < x < q75"})
        self.assertEqual(q["tail_rules"],{"q90_high":"x >= q90","q95_high":"x >= q95"})

    def test_lag_transition_and_episode_geometry(self):
        lag=self.v["lag_persistence"]
        self.assertEqual(lag["lags_bars"],[1,2,3]); self.assertEqual(lag["primary_boundary"],"same_trading_day_only")
        self.assertEqual(lag["expected_pair_counts"]["body_abs_log"],{"lag1":2181,"lag2":1454,"lag3":727})
        self.assertEqual(lag["expected_pair_counts"]["cc_abs_logret_within_day"],{"lag1":1454,"lag2":727,"lag3":0})
        self.assertEqual(lag["lag1_transition_expected_pair_counts"]["cc_abs_logret_within_day"],{"AM1->AM2":0,"AM2->PM1":727,"PM1->PM2":727})
        self.assertEqual(lag["cross_lunch_transition_explicit"],"AM2->PM1")
        ep=self.v["tail_episode_map"]; self.assertEqual(ep["thresholds"],["q90","q95"])
        self.assertTrue(ep["overnight_continuation_forbidden"]); self.assertTrue(ep["no_acceptance_gate"])

    def test_compression_and_secondary_overnight_are_descriptive_only(self):
        c=self.v["compression_diagnostics"]
        self.assertEqual(c["low_body_definition"],"body_abs_log <= global q50(body_abs_log)")
        self.assertEqual(c["wide_range_definition"],"range_log >= global q90(range_log)")
        self.assertEqual(c["high_path_energy_definition"],"intrabar_rv_1m >= global q90(intrabar_rv_1m)")
        self.assertTrue(c["no_winner_selection"]); self.assertEqual(c["pairwise_tail_overlap"]["thresholds"],["q90","q95"])
        o=self.v["secondary_overnight_diagnostic"]
        self.assertTrue(o["enabled"]); self.assertEqual(o["expected_pairs"],726)
        self.assertEqual(o["authority"],"secondary_descriptive_only"); self.assertTrue(o["excluded_from_primary_persistence"])

    def test_exact_technical_gates_no_authority_and_prereg_time_freeze(self):
        t=self.v["technical_acceptance"]
        self.assertTrue(all(t.values()))
        self.assertEqual(t["cc_finite_rows_eq_2181"],True); self.assertEqual(t["cc_am1_structural_null_rows_eq_727"],True)
        self.assertTrue(all(x is False for x in self.v["controls"].values()))
        r=self.v["result_contract"]
        self.assertEqual(r["technical_valid_status"],"NATIVE60_DESCRIPTIVE_MAP_COMPLETE")
        self.assertFalse(r["next_phase_authorized"]); self.assertTrue(r["no_observable_ranking"]); self.assertTrue(r["no_pass_fail_continuity_claim"])
        self.assertEqual(self.v["publication"]["verifier_success_token"],"passed")
        freeze=self.v["execution_freeze"]
        self.assertFalse(freeze["execution_profile_registered_at_prereg"])
        self.assertFalse(freeze["controller_route_registered_at_prereg"])
        self.assertTrue(freeze["implementation_after_prereg_merge_only"])
        self.assertFalse(freeze["row_level_read_before_prereg_freeze"])

if __name__=="__main__": unittest.main()
