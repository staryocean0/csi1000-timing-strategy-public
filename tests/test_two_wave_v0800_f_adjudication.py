import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/research/TWO_WAVE_V0800_F_ADJUDICATION_20260915.json"
NOTE = ROOT / "docs/research/TWO_WAVE_V0800_F_ADJUDICATION_20260915.md"


class TwoWaveV0800FAdjudicationTest(unittest.TestCase):
    def setUp(self):
        self.value = json.loads(DOC.read_text(encoding="utf-8"))

    def test_verified_f_run_and_input_identity_are_frozen(self):
        run = self.value["source_run"]
        self.assertEqual(run["public_run_id"], "34984126303-1")
        self.assertEqual(run["public_source_sha"], "c9e2d8bfcb0eeb3ec7a933e730cb72601a9798d0")
        self.assertEqual(run["profile"], "two-wave-v0800-f-operational-state-stream-audit-v1")
        self.assertEqual(run["runner_status"], "passed")
        self.assertEqual(run["trusted_independent_comparison"], "passed")
        self.assertEqual(run["private_delivery_status"], "archive_uploaded_and_verified")
        identity = self.value["input_identity"]
        self.assertEqual(identity["rows"], 70114)
        self.assertEqual(identity["bytes"], 3351411)
        self.assertEqual(identity["sha256"], "bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48")
        self.assertFalse(identity["substitute_data_used"])
        self.assertFalse(identity["year_2026_read"])

    def test_primary_stream_and_abstention_counts_are_result_locked(self):
        stream = self.value["primary_stream"]
        self.assertEqual(stream["strict_event_count"], 2358)
        self.assertEqual(stream["eligible_event_count"], 924)
        self.assertEqual(stream["scale_mismatch_count"], 1434)
        self.assertEqual(stream["scale_mismatch_label"], "NoStateScaleMismatch")
        self.assertEqual(stream["eligible_event_count"] + stream["scale_mismatch_count"], stream["strict_event_count"])
        states = stream["eligible_state_counts"]
        self.assertEqual(states, {"Range": 23, "UpTrend": 78, "DownTrend": 79, "Uncertain": 744})
        self.assertEqual(sum(states.values()), 924)
        self.assertEqual(stream["non_abstaining_eligible_count"], 180)
        self.assertTrue(stream["high_abstention_observed"])

    def test_primary_transitions_respect_shared_wave_semantics(self):
        transition = self.value["transition_adjudication"]
        self.assertEqual(transition["primary_within_epoch_transition_count"], 2221)
        self.assertEqual(transition["primary_direct_up_down_reversal_count"], 0)
        self.assertEqual(transition["primary_direct_trend_to_range_count"], 0)
        self.assertEqual(transition["primary_direct_range_to_trend_count"], 0)
        self.assertTrue(transition["shared_wave_descriptor_consistency_observed"])
        self.assertFalse(transition["direct_reversal_pathology_observed"])
        self.assertEqual(transition["trend_event_exit_counts"]["UpTrend"]["to_DownTrend"], 0)
        self.assertEqual(transition["trend_event_exit_counts"]["DownTrend"]["to_UpTrend"], 0)

    def test_eligible_only_false_continuity_is_explicit(self):
        diag = self.value["eligible_only_diagnostic"]
        gaps = diag["intervening_strict_event_count"]
        self.assertEqual(diag["within_epoch_transition_count"], 799)
        self.assertEqual(gaps["zero"], 376)
        self.assertEqual(gaps["one"], 150)
        self.assertEqual(gaps["two_or_more"], 273)
        self.assertEqual(gaps["zero"] + gaps["one"] + gaps["two_or_more"], 799)
        self.assertEqual(diag["eligible_links_with_at_least_one_intervening_strict_event"], 423)
        self.assertEqual(diag["direct_up_down_reversals_in_eligible_only_sequence"], 8)
        self.assertEqual(diag["eligible_only_reversals_with_zero_intervening_strict_events"], 0)
        self.assertEqual(diag["eligible_only_reversals_with_intervening_strict_events"], 8)
        self.assertFalse(diag["eligible_only_is_true_continuous_state_stream"])

    def test_persistence_stays_event_count_only(self):
        persistence = self.value["event_count_persistence"]
        self.assertTrue(persistence["not_bar_duration"])
        self.assertTrue(persistence["not_clock_duration"])
        runs = persistence["run_length_summary"]
        self.assertEqual(runs["UpTrend"]["max"], 2.0)
        self.assertEqual(runs["DownTrend"]["max"], 3.0)
        self.assertEqual(runs["NoStateScaleMismatch"]["max"], 11.0)

    def test_adjudication_opens_only_next_semantic_gate(self):
        adjudication = self.value["semantic_adjudication"]
        self.assertTrue(adjudication["primary_all_strict_event_stream_required"])
        self.assertTrue(adjudication["eligible_only_false_continuity_material"])
        self.assertTrue(adjudication["high_abstention_material"])
        self.assertFalse(adjudication["high_abstention_by_itself_requires_parameter_change"])
        self.assertFalse(adjudication["morphology_parameter_change_authorized"])
        self.assertFalse(adjudication["morphology_definition_revision_required_before_next_gate"])
        self.assertTrue(adjudication["event_time_state_machine_coherent_enough_for_next_gate"])
        gate = self.value["next_gate"]
        self.assertEqual(gate["name"], "V0800-G_BAR_TIME_CARRIER_EXPIRY_SEMANTICS")
        self.assertFalse(gate["bar_time_rule_predecided_by_f"])
        for key in ("parameter_search_allowed", "future_returns_allowed", "pnl_allowed", "trade_simulation_allowed", "production_authority_allowed"):
            self.assertFalse(gate[key])

    def test_authority_remains_closed(self):
        authority = self.value["authority"]
        self.assertTrue(authority["event_time_semantic_coherence_adjudicated"])
        self.assertTrue(authority["parameter_nomination_from_e_preserved"])
        for key in ("bar_time_state_authority", "direction_acceptance", "state_publication_authority", "trade_authority", "production_authority", "future_outcome_used", "returns_used", "pnl_used", "positions_used"):
            self.assertFalse(authority[key])
        frozen = self.value["frozen_semantics"]
        self.assertFalse(frozen["bar_time_state_defined"])
        self.assertEqual(frozen["between_event_state"], "undefined")
        self.assertFalse(frozen["carry_forward"])
        note = NOTE.read_text(encoding="utf-8")
        self.assertIn("eligible-only continuity is materially false", note)
        self.assertIn("F does **not** create a bar-time market state", note)
        self.assertIn("No carry-forward rule should be smuggled", note)


if __name__ == "__main__":
    unittest.main()
