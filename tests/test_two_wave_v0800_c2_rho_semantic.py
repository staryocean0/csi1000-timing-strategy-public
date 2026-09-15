import json
import math
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADJ = ROOT / "docs/research/TWO_WAVE_V0800_C2_RHO_SEMANTIC_ADJUDICATION_20260915.json"
NOTE = ROOT / "docs/research/TWO_WAVE_V0800_C2_RHO_SEMANTIC_ADJUDICATION_20260915.md"


class TwoWaveV0800C2RhoSemanticTest(unittest.TestCase):
    def test_scale_lattice_and_half_octave_rule_are_frozen(self):
        value = json.loads(ADJ.read_text(encoding="utf-8"))
        scale = value["scale_coordinate"]
        self.assertEqual(scale["name"], "log2_duration")
        self.assertEqual(scale["level_lattice"], "dyadic")
        self.assertEqual(scale["adjacent_level_center_ratio"], 2.0)
        rule = value["same_level_rule"]
        self.assertEqual(rule["maximum_half_width_octaves"], 0.5)
        self.assertAlmostEqual(rule["equivalent_duration_ratio_limit"], math.sqrt(2.0))
        self.assertEqual(rule["integer_band_function"], "[ceil(N/sqrt(2)), floor(N*sqrt(2))]")
        self.assertEqual(rule["illustrative_bands"], {"5": [4, 7], "10": [8, 14], "20": [15, 28]})

    def test_operational_rho_is_semantic_not_empirical_winner(self):
        value = json.loads(ADJ.read_text(encoding="utf-8"))
        decision = value["adjudication"]
        self.assertAlmostEqual(decision["operational_rho"], math.sqrt(2.0))
        self.assertEqual(decision["operational_rho_symbolic"], "sqrt(2)")
        self.assertEqual(decision["selection_type"], "semantic_convention_not_empirical_winner")
        for key in ("selected_by_support", "selected_by_path_rms", "selected_by_returns", "selected_by_pnl", "selected_by_2026"):
            self.assertFalse(decision[key])
        self.assertFalse(decision["amplitude_gate_added"])
        self.assertEqual(decision["legacy_rho_2_role"], "historical_control_only_not_operational")

    def test_candidate_family_is_unchanged_but_semantic_authority_is_unique(self):
        value = json.loads(ADJ.read_text(encoding="utf-8"))
        self.assertEqual(value["frozen_candidate_family"], [1.25, 4 / 3, math.sqrt(2), 1.5])
        authority = value["authority"]
        self.assertTrue(authority["rho_semantic_authority"])
        self.assertTrue(authority["v0800_d_preregistration_allowed"])
        self.assertFalse(authority["v0800_d_execution_authorized"])
        for key in ("direction_thresholds", "pair_state_publication", "future_outcome_used", "pnl_used", "positions_used", "trade_authority", "production_authority"):
            self.assertFalse(authority[key])

    def test_human_note_keeps_direction_execution_closed(self):
        text = NOTE.read_text(encoding="utf-8")
        self.assertIn("unique half-octave boundary", text)
        self.assertIn("semantic convention", text)
        self.assertIn("rho=sqrt(2)", text)
        self.assertIn("V0800-D execution remains blocked", text)
        self.assertIn("No amplitude gate is added", text)


if __name__ == "__main__":
    unittest.main()
