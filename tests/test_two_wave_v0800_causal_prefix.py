from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILE = "two-wave-v0800-causal-prefix-v1"
PROTOCOL = ROOT / "docs/research/TWO_WAVE_V0800_C_CAUSAL_PREFIX_PROTOCOL.json"
PRODUCER = ROOT / "executor/two_wave_v0800_causal_prefix.py"
VERIFIER = ROOT / "executor/two_wave_v0800_causal_prefix_verifier.py"
BROKER = ROOT / "executor/two_wave_v0800_causal_prefix_broker.py"
MIRROR = ROOT / "executor/two_wave_v0800_causal_prefix_private_mirror.py"
WORKFLOW = ROOT / ".github/workflows/public-compute.yml"
CONTROLLER = ROOT / ".github/workflows/controller-dispatch.yml"


class TwoWaveV0800CausalPrefixContractTest(unittest.TestCase):
    def test_protocol_freezes_causal_replay_without_direction_or_rho_selection(self):
        value = json.loads(PROTOCOL.read_text(encoding="utf-8"))
        self.assertEqual(value["schema_id"], "csi1000.two_wave_v0800_causal_prefix_protocol@1.0")
        self.assertEqual(value["prefix_checkpoints"]["fixed_stride_rows"], 4096)
        self.assertEqual(value["prefix_checkpoints"]["event_wave_ordinal_stride"], 256)
        self.assertEqual(value["same_scale"]["candidate_rho"], [1.25, 4/3, 2**0.5, 1.5])
        self.assertFalse(value["same_scale"]["rho_selection_allowed"])
        self.assertIsNone(value["authority"]["rho_winner"])
        self.assertIsNone(value["authority"]["direction_winner"])
        self.assertFalse(value["authority"]["morphology_acceptance"])
        self.assertFalse(value["authority"]["trade_authority"])

    def test_sources_compile_without_importing_pandas_in_lightweight_ci(self):
        for path in (PRODUCER, VERIFIER, BROKER, MIRROR):
            self.assertTrue(path.is_file(), str(path))
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    def test_broker_pins_exact_consumed_data_and_dispatch_context(self):
        text = BROKER.read_text(encoding="utf-8")
        self.assertIn('PROFILE_NAME = "two-wave-v0800-causal-prefix-v1"', text)
        self.assertIn('SOURCE_REF = "152ae1ef11a04bb3b434da25025794db7a706c81"', text)
        self.assertIn('DATA_SHA256 = "bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48"', text)
        self.assertIn('env.get("GITHUB_EVENT_NAME") != "workflow_dispatch"', text)
        self.assertIn('"new_training": False', text)
        self.assertIn('"production_authority": False', text)

    def test_producer_has_frozen_checkpoint_rules_and_no_economic_objective(self):
        text = PRODUCER.read_text(encoding="utf-8")
        self.assertIn("FIXED_ROW_STRIDE = 4096", text)
        self.assertIn("EVENT_WAVE_STRIDE = 256", text)
        self.assertIn('"rho_winner": None', text)
        self.assertIn('"future_outcome_used": False', text)
        self.assertIn('"pnl_used": False', text)
        self.assertNotIn("future_return", text)

    def test_verifier_is_independent_of_producer_module(self):
        text = VERIFIER.read_text(encoding="utf-8")
        self.assertNotIn("from two_wave_v0800_causal_prefix import", text)
        self.assertIn("class IndependentTemporalMaturityEngine", text)
        self.assertIn('fail("summary_recompute_mismatch")', text)

    def test_private_mirror_is_aggregate_only(self):
        text = MIRROR.read_text(encoding="utf-8")
        self.assertIn('TEXT_OUTPUTS = ("SUMMARY.json", "INPUT_RECEIPT.json")', text)
        self.assertNotIn("CHECKPOINT_AUDIT.csv", text)
        self.assertNotIn("LEDGER_HASHES.json", text)
        self.assertIn('value.get("rho_winner") is not None', text)

    def test_standard_routes_are_registered(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        controller = CONTROLLER.read_text(encoding="utf-8")
        self.assertIn(f"- {PROFILE}", workflow)
        for phase in ("prepare", "compute", "cleanup", "publish"):
            self.assertIn(f"python3 executor/two_wave_v0800_causal_prefix_broker.py {phase} {PROFILE}", workflow)
        self.assertIn("python3 executor/two_wave_v0800_causal_prefix_private_mirror.py", workflow)
        self.assertIn(f"controller: {PROFILE}", controller)
        self.assertIn(f"profile='{PROFILE}'", controller)


if __name__ == "__main__":
    unittest.main()
