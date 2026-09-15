import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADJ = ROOT / "docs/research/TWO_WAVE_V0800_E_POST_AUDIT_ADJUDICATION.json"
NOTE = ROOT / "docs/research/TWO_WAVE_V0800_E_POST_AUDIT_ADJUDICATION.md"
WORKFLOW = ROOT / ".github/workflows/public-compute.yml"
CONTROLLER = ROOT / ".github/workflows/controller-dispatch.yml"


class TwoWaveV0800EPostAuditAdjudicationTest(unittest.TestCase):
    def test_evidence_identity_is_exact(self):
        value = json.loads(ADJ.read_text(encoding="utf-8"))
        evidence = value["source_evidence"]
        self.assertEqual(evidence["science_run_id"], "34967434004-1")
        self.assertEqual(evidence["transport_replay_run_id"], "34971340135-1")
        self.assertEqual(evidence["audit_manifest_sha256"], "c3260be7f72a12a5da0b33d1fb23deacd32d967d83e45f480d0363ca2e836ab5")
        self.assertEqual(evidence["selected_case_count"], 59)
        self.assertEqual(evidence["eligible_same_scale_pair_count"], 924)
        self.assertEqual(evidence["bars_read"], 70114)

    def test_frozen_operational_semantics(self):
        value = json.loads(ADJ.read_text(encoding="utf-8"))
        semantics = value["frozen_semantics"]
        self.assertEqual(semantics["pair_continuity"], "shared_anchor_strict_L-H-L-H-L")
        self.assertEqual(semantics["knowledge_time"], "current_A_wave_confirmation_bar")
        self.assertEqual(semantics["operational_rho_symbolic"], "sqrt(2)")
        self.assertEqual(semantics["tau"], 0.20)
        self.assertEqual(semantics["kappa"], 1.50)
        self.assertTrue(semantics["bottom_channel_authority"])

    def test_selection_is_semantic_not_outcome_or_decisiveness_search(self):
        value = json.loads(ADJ.read_text(encoding="utf-8"))
        audit = value["visual_semantic_adjudication"]
        self.assertEqual(audit["tau_0_20"].split("_")[0], "accepted")
        self.assertEqual(audit["kappa_1_50"], "accepted_as_similar_slope_tolerance")
        self.assertFalse(audit["selection_used_future_outcomes"])
        self.assertFalse(audit["selection_used_returns"])
        self.assertFalse(audit["selection_used_pnl"])
        self.assertFalse(audit["selection_used_decisiveness_maximization"])

    def test_authority_is_layer2_descriptive_only(self):
        authority = json.loads(ADJ.read_text(encoding="utf-8"))["authority"]
        self.assertTrue(authority["layer2_descriptive_morphology_semantic_acceptance"])
        self.assertTrue(authority["layer2_descriptive_state_publication_authority"])
        for key in (
            "predictive_signal_authority",
            "future_outcome_validation_complete",
            "layer3_consumption_authority",
            "trade_authority",
            "position_authority",
            "production_strategy_authority",
            "year_2026_used",
        ):
            self.assertFalse(authority[key])

    def test_state_rule_and_outside_universe_fail_closed(self):
        rule = json.loads(ADJ.read_text(encoding="utf-8"))["state_rule"]
        self.assertEqual(rule["range"], "both abs(g) <= 0.20")
        self.assertIn("<= 1.50", rule["uptrend"])
        self.assertIn("<= 1.50", rule["downtrend"])
        self.assertEqual(rule["outside_eligible_pair_universe"], "no directional state publication")

    def test_human_note_keeps_prediction_and_trading_closed(self):
        text = NOTE.read_text(encoding="utf-8")
        self.assertIn("does **not** claim predictive value", text)
        self.assertIn("Layer2 descriptive state publication only", text)
        self.assertIn("Layer3 strategy consumption", text)
        self.assertIn("future-information validation", text)
        self.assertIn("must not be described as fresh OOS", text)

    def test_adjudication_registers_no_new_execution_route(self):
        marker = "two-wave-v0800-e-post-audit-adjudication"
        self.assertNotIn(marker, WORKFLOW.read_text(encoding="utf-8"))
        self.assertNotIn(marker, CONTROLLER.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
