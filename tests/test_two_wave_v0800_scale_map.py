import py_compile
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "executor/two_wave_v0800_scale_map.py"
VERIFIER = ROOT / "executor/two_wave_v0800_scale_map_verifier.py"
BROKER = ROOT / "executor/two_wave_v0800_scale_map_broker.py"
PROTOCOL = ROOT / "docs/research/TWO_WAVE_BACKWARD_SAME_SCALE_A_CHANNEL_V0800_PROTOCOL.md"


class TwoWaveV0800ScaleMapTest(unittest.TestCase):
    def test_data_runner_and_verifier_compile_without_importing_heavy_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            for source in (RUNNER, VERIFIER, BROKER):
                py_compile.compile(str(source), cfile=str(Path(tmp) / (source.name + ".pyc")), doraise=True)

    def test_runner_freezes_v043_causal_kernel_and_no_outcome_objective(self):
        text = RUNNER.read_text(encoding="utf-8")
        self.assertIn("MIN_LEG = 4", text)
        self.assertIn("MAX_UNFINISHED_LEG = 48", text)
        self.assertIn("confirmation_delay_bars", text)
        self.assertIn("same_scale", text)
        self.assertIn("year_2026_read\": False", text)
        self.assertIn("future_outcome_used\": False", text)
        self.assertIn("rho_winner\": None", text)
        self.assertNotIn("forward_return", text)
        self.assertNotIn("transaction_cost", text)

    def test_verifier_enforces_backward_nearest_same_scale(self):
        text = VERIFIER.read_text(encoding="utf-8")
        self.assertIn("predecessor_not_backward", text)
        self.assertIn("nearest_eligible_predecessor_violated", text)
        self.assertIn("same_scale_relation_invalid", text)
        self.assertIn("premature_winner_or_future_year_read", text)

    def test_broker_is_fixed_to_historical_two_wave_development_identity(self):
        text = BROKER.read_text(encoding="utf-8")
        self.assertIn("152ae1ef11a04bb3b434da25025794db7a706c81", text)
        self.assertIn("bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48", text)
        self.assertIn("DATA_BYTES = 3351411", text)
        self.assertIn("workflow_dispatch", text)
        self.assertIn("production_authority\": False", text)

    def test_protocol_keeps_first_real_run_on_scale_semantics(self):
        text = PROTOCOL.read_text(encoding="utf-8")
        self.assertIn("V0800-B — duration/scale-band map", text)
        self.assertIn("No return, PnL, future horizon, or trading label", text)
        self.assertIn("A-phase only", text)
        self.assertIn("lower boundary is authoritative", text)


if __name__ == "__main__":
    unittest.main()
