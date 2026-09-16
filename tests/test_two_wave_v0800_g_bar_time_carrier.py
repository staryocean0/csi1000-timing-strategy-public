import ast
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "docs/research/TWO_WAVE_V0800_G_BAR_TIME_CARRIER_SEMANTICS_PROTOCOL.json"
NOTE = ROOT / "docs/research/TWO_WAVE_V0800_G_BAR_TIME_CARRIER_SEMANTICS_PROTOCOL.md"
PRODUCER = ROOT / "executor/two_wave_v0800_g_bar_time_carrier.py"
VERIFIER = ROOT / "executor/two_wave_v0800_g_bar_time_carrier_verifier.py"
BROKER = ROOT / "executor/two_wave_v0800_g_bar_time_carrier_broker.py"
MIRROR = ROOT / "executor/two_wave_v0800_g_bar_time_carrier_private_mirror.py"
WORKFLOW = ROOT / ".github/workflows/public-compute.yml"
CONTROLLER = ROOT / ".github/workflows/controller-dispatch.yml"
PROFILE = "two-wave-v0800-g-bar-time-carrier-semantics-v1"
CONTROLLER_TITLE = "controller: two-wave-v0800-g-bar-time-carrier-semantics-v1"


class TwoWaveV0800GBarTimeCarrierTest(unittest.TestCase):
    def setUp(self):
        self.protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))

    def test_sources_parse_without_runtime_imports(self):
        for path in (PRODUCER, VERIFIER, BROKER, MIRROR):
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    def test_parent_and_morphology_are_frozen(self):
        parent = self.protocol["parent_adjudication"]
        self.assertEqual(parent["merge_commit"], "5b356a53fcfc8dd2d8e4b4b69eb18735e2b8b74d")
        self.assertEqual(parent["verified_f_run"], "34984126303-1")
        self.assertTrue(parent["f_event_time_state_machine_coherent_for_next_gate"])
        self.assertFalse(parent["f_bar_time_state_authority"])
        frozen = self.protocol["frozen_morphology"]
        self.assertEqual(frozen["rho_symbolic"], "sqrt(2)")
        self.assertAlmostEqual(frozen["tau"], 0.20)
        self.assertAlmostEqual(frozen["kappa"], 2.00)
        self.assertEqual(frozen["expected_strict_pair_count"], 2358)
        self.assertEqual(frozen["expected_eligible_pair_count"], 924)
        self.assertEqual(frozen["expected_reset_count"], 164)
        self.assertFalse(frozen["parameter_search_allowed"])

    def test_bar_open_knowledge_time_and_current_first_invalidation_are_frozen(self):
        coordinate = self.protocol["bar_time_coordinate"]
        self.assertEqual(coordinate["carrier_semantics"], "state_known_before_bar_begins")
        self.assertTrue(coordinate["event_confirmed_at_close_of_bar"])
        self.assertTrue(coordinate["same_confirmation_bar_is_not_carried"])
        self.assertEqual(coordinate["first_possible_carrier_bar_formula"], "confirmation_bar + 1")
        candidate = self.protocol["primary_carrier_candidate"]
        self.assertEqual(candidate["name"], "current_first_until_next_strict_or_reset")
        self.assertEqual(candidate["carrier_states"], ["Range", "UpTrend", "DownTrend"])
        self.assertEqual(candidate["event_states_that_clear_without_new_carrier"], ["Uncertain", "NoStateScaleMismatch"])
        self.assertIsNone(candidate["fixed_bar_expiry"])
        self.assertFalse(candidate["fixed_bar_expiry_search_allowed"])
        self.assertFalse(candidate["publication_authority"])

    def test_producer_builds_carrier_after_confirmation_and_clears_on_new_evidence(self):
        text = PRODUCER.read_text(encoding="utf-8")
        self.assertIn("PrefixReplayAEngine", text)
        self.assertIn('if len(events) != 2358', text)
        self.assertIn('!= 924', text)
        self.assertIn('if len(resets) != 164', text)
        self.assertIn('age = i - int(current["confirmation_bar"])', text)
        self.assertIn('if age <= 0', text)
        self.assertIn('no_state_reason = "Uncertain"', text)
        self.assertIn('no_state_reason = "NoStateScaleMismatch"', text)
        self.assertIn('no_state_reason = "Reset"', text)
        self.assertIn('"first_carrier_bar_formula": "confirmation_bar + 1"', text)
        self.assertIn('"strict_event_supersedes_previous_carrier": True', text)
        self.assertIn('"fixed_bar_expiry_used": False', text)
        self.assertIn('"bar_time_publication_authority": False', text)
        self.assertIn('"trade_authority": False', text)
        self.assertIn('"production_authority": False', text)

    def test_verifier_is_independent_and_exact_at_bar_level(self):
        text = VERIFIER.read_text(encoding="utf-8")
        self.assertIn("TemporalMaturityAEngine", text)
        self.assertNotIn("from two_wave_v0800_g_bar_time_carrier import", text)
        self.assertIn('REQUIRED = {"BAR_CARRIER.csv", "SUMMARY.json", "INPUT_RECEIPT.json"}', text)
        self.assertIn('fail("carrier_shape_mismatch")', text)
        self.assertIn('fail("same_or_future_bar_carrier")', text)
        self.assertIn('fail("carrier_does_not_begin_next_bar")', text)
        self.assertIn('"exact_bar_carrier_match": True', text)
        self.assertIn('"hold_until_next_eligible_is_diagnostic_only": True', text)

    def test_hold_until_next_eligible_is_anti_control_only(self):
        anti = self.protocol["counterfactual_diagnostics"]["hold_until_next_eligible"]
        self.assertEqual(anti["status"], "anti_control_only_not_authority_candidate")
        self.assertFalse(anti["may_influence_primary_rule"])
        self.assertEqual(self.protocol["counterfactual_diagnostics"]["fixed_bar_expiry_grid"]["status"], "not_evaluated")
        producer = PRODUCER.read_text(encoding="utf-8")
        self.assertIn("ignore_scale_mismatch=True", producer)
        self.assertIn('"authority_candidate": False', producer)

    def test_broker_is_pinned_but_not_routed_in_source_only_phase(self):
        text = BROKER.read_text(encoding="utf-8")
        self.assertIn(f'PROFILE_NAME = "{PROFILE}"', text)
        self.assertIn('SOURCE_REF = "152ae1ef11a04bb3b434da25025794db7a706c81"', text)
        self.assertIn('DATA_BYTES = 3351411', text)
        self.assertIn('bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48', text)
        self.assertIn('GITHUB_EVENT_NAME") != "workflow_dispatch"', text)
        self.assertIn('GITHUB_REF") != "refs/heads/cloud-workspace-v1"', text)
        self.assertIn('"new_training": False', text)
        self.assertIn('"production_authority": False', text)
        workflow = WORKFLOW.read_text(encoding="utf-8")
        controller = CONTROLLER.read_text(encoding="utf-8")
        self.assertNotIn(PROFILE, workflow)
        self.assertNotIn(CONTROLLER_TITLE, controller)

    def test_private_mirror_is_aggregate_only_and_fail_closed(self):
        text = MIRROR.read_text(encoding="utf-8")
        self.assertIn('TEXT_OUTPUTS = ("SUMMARY.json", "INPUT_RECEIPT.json")', text)
        self.assertNotIn('TEXT_OUTPUTS = ("BAR_CARRIER.csv"', text)
        self.assertIn('"state_known_before_bar_begins"', text)
        self.assertIn('"confirmation_bar + 1"', text)
        self.assertIn('"bar_time_publication_authority"', text)
        self.assertIn('"post_run_adjudication_required"', text)
        self.assertIn('"authority_candidate"', text)

    def test_scope_remains_non_outcome_and_non_authoritative(self):
        forbidden = self.protocol["forbidden"]
        for key in (
            "year_2026", "future_returns", "pnl", "positions", "transaction_costs",
            "trade_simulation", "strategy_routing", "parameter_tuning", "coverage_optimization",
            "persistence_optimization", "fixed_expiry_search", "direction_acceptance",
            "state_publication_authority", "trade_authority", "production_authority",
        ):
            self.assertTrue(forbidden[key])
        self.assertIsNone(self.protocol["automatic_acceptance_rule"])
        self.assertTrue(self.protocol["post_run_adjudication_required"])
        note = NOTE.read_text(encoding="utf-8")
        self.assertIn("confirmation_bar + 1", note)
        self.assertIn("hold-until-next-eligible", note)
        self.assertIn("No fixed-bar expiry grid", note)


if __name__ == "__main__":
    unittest.main()
