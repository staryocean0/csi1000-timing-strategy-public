import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/research/TWO_WAVE_V0800_E_ADJUDICATION_20260915.json"
NOTE = ROOT / "docs/research/TWO_WAVE_V0800_E_ADJUDICATION_20260915.md"


class TwoWaveV0800EAdjudicationTest(unittest.TestCase):
    def setUp(self):
        self.value = json.loads(DOC.read_text(encoding="utf-8"))

    def test_verified_e_run_and_manifest_are_frozen(self):
        run = self.value["source_run"]
        self.assertEqual(run["public_run_id"], "34971340135-1")
        self.assertEqual(run["public_source_sha"], "1bb6f89fab8ef34b726f6a77d15a6f3b11b50b31")
        self.assertEqual(run["profile"], "two-wave-v0800-e-morphology-visual-audit-v1")
        self.assertEqual(run["audit_manifest_sha256"], "c3260be7f72a12a5da0b33d1fb23deacd32d967d83e45f480d0363ca2e836ab5")
        self.assertTrue(run["transport_replay_manifest_identity_confirmed"])

    def test_audit_categories_partition_frozen_eligible_universe(self):
        pack = self.value["audit_pack"]
        self.assertEqual(pack["eligible_pair_count"], 924)
        self.assertEqual(pack["selected_case_count"], 59)
        self.assertEqual(sum(pack["category_available_counts"].values()), 924)
        self.assertTrue(pack["categories_partition_eligible_universe"])
        self.assertEqual(pack["only_shortage_cell"], "tau_sensitive/2020")
        self.assertEqual(pack["only_shortage_cell_available"], 1)
        self.assertFalse(pack["bars_after_confirmation_shown"])
        self.assertFalse(pack["future_outcome_used"])

    def test_operational_pair_is_semantic_nomination_not_performance_winner(self):
        pair = self.value["operational_semantic_pair"]
        self.assertEqual(pair["rho_symbolic"], "sqrt(2)")
        self.assertEqual(pair["tau"], 0.20)
        self.assertEqual(pair["kappa"], 2.00)
        self.assertEqual(pair["status"], "nominated_for_next_semantic_validation")
        self.assertEqual(pair["selection_basis"], "geometry_only_post_audit_adjudication")
        self.assertFalse(pair["statistical_winner_claimed"])
        self.assertFalse(pair["performance_winner_claimed"])
        guards = self.value["selection_guards"]
        for key in ("max_decisive_fraction_used", "min_uncertain_fraction_used", "state_balance_used", "future_returns_used", "pnl_used", "trading_metric_used", "automatic_parameter_search_authorized"):
            self.assertFalse(guards[key])
        self.assertTrue(guards["future_parameter_change_requires_new_preregistration"])

    def test_visual_boundary_examples_lock_semantic_rationale(self):
        examples = {x["pair_id"]: x for x in self.value["visual_adjudication"]["review_examples"]}
        self.assertAlmostEqual(examples["e16-a000159__e16-a000160"]["slope_magnitude_ratio"], 1.2569)
        self.assertAlmostEqual(examples["e151-a002368__e151-a002369"]["slope_magnitude_ratio"], 1.5005)
        self.assertAlmostEqual(examples["e4-a000072__e4-a000073"]["slope_magnitude_ratio"], 3.4836)
        self.assertAlmostEqual(examples["e153-a002392__e153-a002393"]["slope_magnitude_ratio"], 2.6759)
        self.assertAlmostEqual(examples["e24-a000252__e24-a000253"]["g_previous"], -0.1117)
        self.assertAlmostEqual(examples["e24-a000252__e24-a000253"]["g_current"], 0.1539)
        verdict = self.value["visual_adjudication"]
        for key in ("stable_consensus_geometry_coherent", "kappa_sensitive_geometry_coherent", "tau_sensitive_geometry_coherent", "sign_conflict_abstention_coherent", "persistent_uncertain_abstention_coherent"):
            self.assertTrue(verdict[key])
        self.assertFalse(verdict["morphology_definition_revision_required_before_nomination"])

    def test_authority_remains_closed_except_parameter_nomination(self):
        authority = self.value["authority"]
        self.assertTrue(authority["parameter_nomination"])
        for key in ("direction_acceptance", "state_publication_authority", "trade_authority", "production_authority", "future_outcome_used", "returns_used", "pnl_used", "positions_used"):
            self.assertFalse(authority[key])

    def test_next_gate_is_state_stream_semantics_only(self):
        gate = self.value["next_gate"]
        self.assertEqual(gate["name"], "V0800-F_OPERATIONAL_STATE_STREAM_AUDIT")
        for key in ("parameter_search_allowed", "future_returns_allowed", "pnl_allowed", "trade_simulation_allowed", "production_authority_allowed"):
            self.assertFalse(gate[key])
        note = NOTE.read_text(encoding="utf-8")
        self.assertIn("semantic nomination", note)
        self.assertIn("not selected because it maximizes decisiveness", note)
        self.assertIn("Any later change to `rho`, `tau`, or `kappa` requires a new preregistration", note)
        self.assertIn("V0800-F operational state-stream audit", note)


if __name__ == "__main__":
    unittest.main()
