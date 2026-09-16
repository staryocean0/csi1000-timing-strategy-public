import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/research/TWO_WAVE_V0800_G_ADJUDICATION_20260916.json"
NOTE = ROOT / "docs/research/TWO_WAVE_V0800_G_ADJUDICATION_20260916.md"


class TwoWaveV0800GAdjudicationTest(unittest.TestCase):
    def setUp(self):
        self.value = json.loads(DOC.read_text(encoding="utf-8"))

    def test_verified_run_and_input_identity_are_frozen(self):
        run = self.value["verified_run"]
        self.assertEqual(run["public_run_id"], "35043795953-1")
        self.assertEqual(run["public_source_sha"], "afd9de82f514dc101d273c685fa541ff847ed5ff")
        self.assertEqual(run["delivery_status"], "archive_uploaded_and_verified")
        self.assertEqual(run["summary_sha256"], "8454469af679113f92ba5283b5aad13ed8511c9b4eeeb203763c766cac3d16d2")
        identity = self.value["input"]
        self.assertEqual(identity["rows"], 70114)
        self.assertEqual(identity["bytes"], 3351411)
        self.assertEqual(identity["sha256"], "bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48")
        self.assertFalse(identity["substitute_data_used"])
        self.assertFalse(identity["year_2026_read"])

    def test_frozen_morphology_is_not_retuned(self):
        morphology = self.value["frozen_morphology"]
        self.assertEqual(morphology["rho_symbolic"], "sqrt(2)")
        self.assertEqual(morphology["tau"], 0.2)
        self.assertEqual(morphology["kappa"], 2.0)
        self.assertEqual(morphology["strict_event_count"], 2358)
        self.assertEqual(morphology["eligible_event_count"], 924)
        self.assertEqual(morphology["reset_count"], 164)
        self.assertFalse(morphology["parameter_change_authorized"])

    def test_primary_current_first_carrier_counts_are_result_locked(self):
        carrier = self.value["verified_primary_carrier"]
        self.assertEqual(carrier["semantics"], "current_first_until_next_strict_or_reset")
        self.assertEqual(carrier["first_carrier_bar_formula"], "confirmation_bar + 1")
        self.assertTrue(carrier["strict_event_supersedes_previous_carrier"])
        self.assertTrue(carrier["uncertain_clears_previous_carrier"])
        self.assertTrue(carrier["scale_mismatch_clears_previous_carrier"])
        self.assertTrue(carrier["reset_clears_previous_carrier"])
        self.assertEqual(carrier["decisive_event_count"], 180)
        self.assertEqual(carrier["carrier_source_event_count"], 180)
        self.assertEqual(carrier["carrier_bar_count"], 4403)
        self.assertEqual(carrier["carrier_bar_count_by_state"], {"DownTrend": 2024, "Range": 474, "UpTrend": 1905})
        self.assertEqual(carrier["minimum_carrier_lag_bars"], 1)
        self.assertEqual(carrier["maximum_carrier_age_bars"], 59)
        self.assertEqual(carrier["zero_length_decisive_event_count"], 0)
        self.assertEqual(carrier["right_censored_interval_count"], 0)

    def test_hold_until_next_eligible_is_rejected_as_stale(self):
        anti = self.value["anti_control"]
        self.assertEqual(anti["name"], "hold_until_next_eligible")
        self.assertFalse(anti["authority_candidate"])
        self.assertEqual(anti["carrier_bar_count"], 9785)
        self.assertEqual(anti["stale_or_extra_carried_bar_count"], 5382)
        self.assertEqual(anti["mismatch_events_ignored_with_active_carrier"], 222)
        self.assertEqual(anti["stale_or_extra_episode_count"], 88)
        self.assertEqual(anti["stale_or_extra_episode_length_bars"]["median"], 48.0)
        self.assertEqual(anti["stale_or_extra_episode_length_bars"]["max"], 259.0)
        decision = self.value["adjudication"]
        self.assertTrue(decision["hold_until_next_eligible_rejected_as_authority_semantics"])

    def test_adjudication_accepts_carrier_semantics_without_expiry_search(self):
        decision = self.value["adjudication"]
        self.assertTrue(decision["engineering_execution_verified"])
        self.assertTrue(decision["bar_time_carrier_semantics_accepted_for_research"])
        self.assertEqual(decision["accepted_carrier_semantics"], "current_first_until_next_strict_or_reset")
        self.assertFalse(decision["fixed_bar_expiry_added"])
        self.assertFalse(decision["fixed_bar_expiry_search_authorized"])
        self.assertFalse(decision["coverage_or_persistence_retuning_authorized"])
        note = NOTE.read_text(encoding="utf-8")
        self.assertIn("Eligible-only holding is materially stale", note)
        self.assertIn("No fixed expiry is added", note)
        self.assertIn("bar-time carrier semantic coherence for research", note)

    def test_authority_remains_closed_and_no_gate_auto_opens(self):
        boundary = self.value["scientific_boundary"]
        self.assertTrue(boundary["event_time_morphology_coherence_inherited_from_f"])
        self.assertTrue(boundary["bar_time_carrier_semantics_coherent_for_research"])
        for key in (
            "direction_acceptance",
            "state_publication_authority",
            "trade_authority",
            "production_authority",
            "future_outcome_used",
            "returns_used",
            "pnl_used",
            "positions_used",
            "parameter_search_used",
            "year_2026_read",
        ):
            self.assertFalse(boundary[key])
        next_gate = self.value["next_gate"]
        self.assertFalse(next_gate["automatically_opened"])
        self.assertFalse(next_gate["outcome_bearing_research_authorized_by_this_adjudication"])


if __name__ == "__main__":
    unittest.main()
