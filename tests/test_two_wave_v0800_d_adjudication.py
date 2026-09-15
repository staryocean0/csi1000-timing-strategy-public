import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/research/TWO_WAVE_V0800_D_ADJUDICATION_20260915.json"
NOTE = ROOT / "docs/research/TWO_WAVE_V0800_D_ADJUDICATION_20260915.md"


class TwoWaveV0800DAdjudicationTest(unittest.TestCase):
    def setUp(self):
        self.value = json.loads(DOC.read_text(encoding="utf-8"))

    def test_verified_run_and_input_identity_are_frozen(self):
        run = self.value["source_run"]
        self.assertEqual(run["public_run_id"], "34963875542-1")
        self.assertEqual(run["public_source_sha"], "a0f7b665ec5c5754ef5d2c21a3bab99f9383a883")
        self.assertEqual(run["runner_status"], "passed")
        self.assertEqual(run["trusted_independent_comparison"], "passed")
        data = self.value["input_identity"]
        self.assertEqual(data["rows"], 70114)
        self.assertEqual(data["bytes"], 3351411)
        self.assertEqual(data["sha256"], "bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48")
        self.assertFalse(data["substitute_data_used"])
        self.assertFalse(data["year_2026_read"])

    def test_universe_and_grid_are_result_locked(self):
        universe = self.value["frozen_universe"]
        self.assertEqual(universe["strict_pair_count"], 2358)
        self.assertEqual(universe["eligible_same_scale_pair_count"], 924)
        self.assertEqual(universe["operational_rho_symbolic"], "sqrt(2)")
        grid = self.value["grid"]
        self.assertEqual(grid["taus"], [0.05, 0.10, 0.15, 0.20])
        self.assertEqual(grid["kappas"], [1.25, 1.50, 2.00])
        self.assertEqual(grid["combinations"], 12)
        self.assertEqual(len(grid["overall"]), 12)
        for result in grid["overall"].values():
            self.assertEqual(result["DownTrend"] + result["Range"] + result["Uncertain"] + result["UpTrend"], 924)

    def test_key_morphology_observations_are_locked(self):
        overall = self.value["grid"]["overall"]
        self.assertEqual(overall["tau=0.10|kappa=2.00"]["DownTrend"], 83)
        self.assertEqual(overall["tau=0.10|kappa=2.00"]["UpTrend"], 83)
        self.assertEqual(overall["tau=0.15|kappa=2.00"]["DownTrend"], 81)
        self.assertEqual(overall["tau=0.15|kappa=2.00"]["UpTrend"], 81)
        self.assertEqual(self.value["observations"]["range_counts_by_tau"], {"0.05": 2, "0.10": 6, "0.15": 14, "0.20": 23})
        self.assertTrue(self.value["observations"]["global_up_down_near_symmetry"])
        self.assertFalse(self.value["observations"]["predictive_validity_claimed"])

    def test_no_parameter_winner_or_direction_authority_is_installed(self):
        selection = self.value["selection_policy"]
        self.assertIsNone(selection["tau_winner"])
        self.assertIsNone(selection["kappa_winner"])
        self.assertFalse(selection["automatic_selection_used"])
        self.assertTrue(selection["forbid_max_decisive_fraction_as_winner_rule"])
        self.assertTrue(selection["forbid_min_uncertain_as_winner_rule"])
        self.assertTrue(selection["forbid_state_balance_as_winner_rule"])
        self.assertTrue(selection["forbid_returns_or_pnl_selection"])
        authority = self.value["authority"]
        for key in ("direction_acceptance", "state_publication_authority", "trade_authority", "production_authority", "future_outcome_used", "returns_used", "pnl_used", "positions_used"):
            self.assertFalse(authority[key])

    def test_next_gate_is_visual_morphology_only(self):
        gate = self.value["next_gate"]
        self.assertEqual(gate["name"], "V0800-E_MORPHOLOGY_VISUAL_AUDIT")
        self.assertFalse(gate["future_bars_after_confirmation_allowed"])
        self.assertFalse(gate["future_returns_allowed"])
        self.assertFalse(gate["automatic_parameter_promotion_allowed"])
        self.assertTrue(gate["deterministic_year_stratified_sampling_required"])
        note = NOTE.read_text(encoding="utf-8")
        self.assertIn("must not be promoted merely because it has the largest decisive fraction", note)
        self.assertIn("No bar after the pair's confirmation bar may be shown", note)
        self.assertIn("stable consensus", note)
        self.assertIn("persistent-Uncertain", note)


if __name__ == "__main__":
    unittest.main()
