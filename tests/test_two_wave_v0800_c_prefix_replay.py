import json
import py_compile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_JSON = ROOT / "docs/research/TWO_WAVE_V0800_C_CAUSAL_PREFIX_REPLAY_PROTOCOL.json"
PROTOCOL_MD = ROOT / "docs/research/TWO_WAVE_V0800_C_CAUSAL_PREFIX_REPLAY_PROTOCOL.md"
PRODUCER = ROOT / "executor/two_wave_v0800_c_prefix_replay.py"
VERIFIER = ROOT / "executor/two_wave_v0800_c_prefix_replay_verifier.py"
BROKER = ROOT / "executor/two_wave_v0800_c_prefix_replay_broker.py"
MIRROR = ROOT / "executor/two_wave_v0800_c_prefix_replay_private_mirror.py"
PROFILE = "two-wave-v0800-c-causal-prefix-replay-v1"


class TwoWaveV0800CPrefixReplayTest(unittest.TestCase):
    def test_protocol_is_causality_only_and_rho_family_is_frozen(self):
        value = json.loads(PROTOCOL_JSON.read_text(encoding="utf-8"))
        self.assertEqual(value["study"], "V0800-C_CAUSAL_PREFIX_REPLAY")
        self.assertEqual(value["parent_adjudication"]["permission"], "causal_prefix_replay_only")
        self.assertEqual(value["candidate_rhos"], [1.25, 4 / 3, 2 ** 0.5, 1.5])
        self.assertFalse(value["legacy_rho_2_evaluated"])
        authority = value["authority"]
        self.assertIsNone(authority["rho_winner"])
        for key in ("rho_winner_selection", "direction_thresholds", "pair_state_publication", "future_outcome_used", "pnl_used", "positions_used", "trade_authority", "production_authority", "v0800_d_authorized"):
            self.assertFalse(authority[key])

    def test_sources_compile_without_importing_heavy_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            for source in (PRODUCER, VERIFIER, BROKER, MIRROR):
                py_compile.compile(str(source), cfile=str(Path(tmp) / (source.name + ".pyc")), doraise=True)

    def test_producer_state_machine_is_independent_from_reference_engine(self):
        text = PRODUCER.read_text(encoding="utf-8")
        self.assertIn("class PrefixReplayAEngine", text)
        self.assertIn("def step(self, i: int)", text)
        self.assertNotIn("TemporalMaturityAEngine", text)
        self.assertIn('"event_visibility": "confirmation_bar_only"', text)
        self.assertIn('"append_only_event_ledgers": True', text)
        for name in ("PIVOT_EVENTS.csv", "RESET_EVENTS.csv", "WAVE_EVENTS.csv", "STRICT_PAIR_EVENTS.csv"):
            self.assertIn(name, text)

    def test_producer_carries_rho_flags_without_direction_logic(self):
        text = PRODUCER.read_text(encoding="utf-8")
        for field in ("rho_1_25", "rho_4_3", "rho_sqrt2", "rho_1_5"):
            self.assertIn(field, text)
        for forbidden in ("internal_wave_descriptor", "classify_pair", "CANDIDATE_TAUS", "CANDIDATE_KAPPAS", "forward_return", "transaction_cost"):
            self.assertNotIn(forbidden, text)
        self.assertIn('"rho_winner": None', text)
        self.assertIn('"direction_thresholds_used": False', text)
        self.assertIn('"pair_state_publication": False', text)

    def test_verifier_uses_frozen_reference_engine_and_exact_event_comparison(self):
        text = VERIFIER.read_text(encoding="utf-8")
        self.assertIn("TemporalMaturityAEngine", text)
        self.assertIn("expected_tables", text)
        self.assertIn("compare_rows", text)
        self.assertIn("wave_post_confirmation_revision", text)
        self.assertIn("pair_not_emitted_at_current_wave_confirmation", text)
        self.assertIn('"prefix_equivalence_passed": True', text)
        self.assertIn('"same_scale_mismatches": 0', text)

    def test_broker_pins_consumed_development_data_and_dispatch_context(self):
        text = BROKER.read_text(encoding="utf-8")
        self.assertIn(PROFILE, text)
        self.assertIn("152ae1ef11a04bb3b434da25025794db7a706c81", text)
        self.assertIn("bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48", text)
        self.assertIn("DATA_BYTES = 3351411", text)
        self.assertIn("workflow_dispatch", text)
        self.assertIn('"new_training": False', text)
        self.assertIn('"production_authority": False', text)

    def test_mirror_is_aggregate_only_and_success_only(self):
        text = MIRROR.read_text(encoding="utf-8")
        self.assertIn('TEXT_OUTPUTS = ("SUMMARY.json", "INPUT_RECEIPT.json")', text)
        self.assertIn("compute_success", text)
        self.assertIn("cleanup_complete", text)
        for row_level in ("PIVOT_EVENTS.csv", "RESET_EVENTS.csv", "WAVE_EVENTS.csv", "STRICT_PAIR_EVENTS.csv"):
            self.assertNotIn(row_level, text)
        self.assertIn("v0800_d_authorized", text)

    def test_human_protocol_explains_event_delta_prefix_proof(self):
        text = PROTOCOL_MD.read_text(encoding="utf-8")
        self.assertIn("event deltas at every confirmation bar", text)
        self.assertIn("cumulative knowledge sets are identical after every bar prefix", text)
        self.assertIn("must not import or call", text)
        self.assertIn("does not choose a same-scale threshold", text)
        self.assertIn("does not classify direction", text)


if __name__ == "__main__":
    unittest.main()
