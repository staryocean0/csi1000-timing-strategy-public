import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADJ = ROOT / "docs/research/TWO_WAVE_V0800_C_ADJUDICATION_20260915.json"
NOTE = ROOT / "docs/research/TWO_WAVE_V0800_C_ADJUDICATION_20260915.md"


class TwoWaveV0800CAdjudicationTest(unittest.TestCase):
    def test_verified_run_identity_is_frozen(self):
        value = json.loads(ADJ.read_text(encoding="utf-8"))
        source = value["source_run"]
        self.assertEqual(source["public_run_id"], "34961575435-1")
        self.assertEqual(source["public_source_sha"], "af9ba09bb2a3cc821ee89a7a2cf2ac29776debed")
        self.assertEqual(source["profile"], "two-wave-v0800-c-causal-prefix-replay-v1")
        self.assertEqual(source["receipt_status"], "passed")
        self.assertEqual(source["input_rows"], 70114)
        self.assertEqual(source["input_sha256"], "bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48")
        self.assertFalse(source["fresh_oos"])
        self.assertFalse(source["substitute_data_used"])
        self.assertFalse(source["year_2026_read"])

    def test_causal_gate_and_counts_are_locked(self):
        value = json.loads(ADJ.read_text(encoding="utf-8"))
        obs = value["verified_observations"]
        self.assertEqual(obs["bars_replayed"], 70114)
        self.assertEqual(obs["pivot_count"], 5471)
        self.assertEqual(obs["reset_count"], 164)
        self.assertEqual(obs["wave_count"], 2503)
        self.assertEqual(obs["strict_pair_count"], 2358)
        self.assertEqual(obs["max_pivot_confirmation_delay_bars"], 41)
        self.assertTrue(obs["append_only_event_ledgers"])
        self.assertEqual(obs["event_visibility"], "confirmation_bar_only")
        self.assertTrue(obs["prefix_replay_complete"])
        self.assertEqual(obs["independent_trusted_output_comparison"], "passed")
        self.assertEqual(obs["same_scale_counts"], {
            "1.25": 587,
            "1.3333333333333333": 772,
            "1.4142135623730951": 924,
            "1.5": 1084,
        })

    def test_c_does_not_choose_rho_or_authorize_direction(self):
        value = json.loads(ADJ.read_text(encoding="utf-8"))
        decision = value["adjudication"]
        self.assertTrue(decision["causal_prefix_gate_passed"])
        self.assertEqual(decision["candidate_rhos_remain_frozen"], [1.25, 4 / 3, 2 ** 0.5, 1.5])
        self.assertFalse(decision["legacy_rho_2_evaluated_in_c"])
        self.assertIsNone(decision["rho_winner"])
        self.assertFalse(decision["rho_selection_evidence_added_by_c"])
        authority = value["authority"]
        for key in (
            "direction_thresholds",
            "pair_state_publication",
            "future_outcome_used",
            "pnl_used",
            "positions_used",
            "trade_authority",
            "production_authority",
            "v0800_d_authorized",
        ):
            self.assertFalse(authority[key])

    def test_next_gate_is_rho_semantic_not_performance_search(self):
        value = json.loads(ADJ.read_text(encoding="utf-8"))
        gate = value["next_gate"]
        self.assertEqual(gate["name"], "V0800-C2_RHO_SEMANTIC_ADJUDICATION")
        self.assertFalse(gate["may_use_future_returns"])
        self.assertFalse(gate["may_use_pnl"])
        self.assertFalse(gate["may_open_2026"])
        self.assertFalse(gate["may_tune_tau_or_kappa"])

    def test_human_note_marks_confirmation_time_as_knowledge_time(self):
        text = NOTE.read_text(encoding="utf-8")
        self.assertIn("A pivot occurrence time is not a knowledge time", text)
        self.assertIn("rho_winner = null", text)
        self.assertIn("V0800-C2 rho semantic adjudication", text)
        self.assertIn("V0800-D remains explicitly blocked", text)


if __name__ == "__main__":
    unittest.main()
