import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADJ = ROOT / "docs/research/TWO_WAVE_V0800_B1_ADJUDICATION_20260915.json"
NOTE = ROOT / "docs/research/TWO_WAVE_V0800_B1_ADJUDICATION_20260915.md"


class TwoWaveV0800B1AdjudicationTest(unittest.TestCase):
    def test_source_run_and_input_identity_are_frozen(self):
        value = json.loads(ADJ.read_text(encoding="utf-8"))
        source = value["source_run"]
        self.assertEqual(source["public_run_id"], "34957977925-1")
        self.assertEqual(source["public_source_sha"], "3c6641fa976159b3528355296f33a8944d124c0f")
        self.assertEqual(source["profile"], "two-wave-v0800-b1-strict-continuity-v1")
        self.assertEqual(source["input_rows"], 70114)
        self.assertEqual(source["input_sha256"], "bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48")
        self.assertFalse(source["year_2026_read"])
        self.assertFalse(source["fresh_oos"])

    def test_verified_observations_are_result_locked(self):
        value = json.loads(ADJ.read_text(encoding="utf-8"))
        obs = value["verified_observations"]
        self.assertEqual(obs["wave_count"], 2503)
        self.assertEqual(obs["strict_pair_count"], 2358)
        self.assertAlmostEqual(obs["strict_pair_fraction_of_all_waves"], 0.9420695165801038)
        self.assertAlmostEqual(obs["spearman_log_duration_ratio_vs_path_rms_21"], -0.015261953047538357)
        self.assertAlmostEqual(obs["spearman_log_channel_height_ratio_vs_path_rms_21"], 0.033830969951624594)

    def test_no_rho_winner_or_amplitude_gate_is_installed(self):
        value = json.loads(ADJ.read_text(encoding="utf-8"))
        decision = value["adjudication"]
        self.assertEqual(decision["strict_shared_anchor_continuity"], "accepted_as_only_direction_eligible_pair_semantic_for_v0800")
        self.assertEqual(decision["same_scale_ledger_nearest"], "diagnostic_only")
        self.assertFalse(decision["skip_based_pair_direction_authority"])
        self.assertTrue(decision["duration_remains_primary_scale_coordinate"])
        self.assertFalse(decision["normalized_path_rms_can_select_rho"])
        self.assertFalse(decision["channel_height_ratio_gate_added"])
        self.assertIsNone(decision["rho_winner"])
        self.assertEqual(decision["candidate_rhos_remain_frozen"], [1.25, 4 / 3, 2 ** 0.5, 1.5])

    def test_v0800_c_is_causality_only(self):
        value = json.loads(ADJ.read_text(encoding="utf-8"))
        gate = value["v0800_c_permission"]
        self.assertTrue(gate["allowed"])
        self.assertEqual(gate["scope"], "causal_prefix_replay_only")
        self.assertFalse(gate["rho_winner_selection"])
        self.assertFalse(gate["direction_thresholds"])
        self.assertFalse(gate["pair_state_publication"])
        self.assertFalse(gate["future_outcome"])
        self.assertFalse(gate["pnl"])
        self.assertFalse(gate["positions"])
        self.assertFalse(gate["trade_authority"])
        self.assertFalse(gate["production_authority"])
        self.assertFalse(gate["year_2026_read"])

    def test_human_note_explains_normalization_limitation(self):
        text = NOTE.read_text(encoding="utf-8")
        self.assertIn("normalizes time to 21 points", text)
        self.assertIn("amplitude by each wave's channel height", text)
        self.assertIn("not an admissible empirical selector for rho", text)
        self.assertIn("B1 itself does not authorize V0800-D", text)


if __name__ == "__main__":
    unittest.main()
