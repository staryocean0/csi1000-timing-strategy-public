import json
import py_compile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_JSON = ROOT / "docs/research/TWO_WAVE_V0800_B1_STRICT_CONTINUITY_PROTOCOL.json"
PROTOCOL_MD = ROOT / "docs/research/TWO_WAVE_V0800_B1_STRICT_CONTINUITY_PROTOCOL.md"
PRODUCER = ROOT / "executor/two_wave_v0800_b1_strict_continuity.py"
VERIFIER = ROOT / "executor/two_wave_v0800_b1_strict_continuity_verifier.py"
BROKER = ROOT / "executor/two_wave_v0800_b1_strict_continuity_broker.py"
MIRROR = ROOT / "executor/two_wave_v0800_b1_strict_continuity_private_mirror.py"
WORKFLOW = ROOT / ".github/workflows/public-compute.yml"
CONTROLLER = ROOT / ".github/workflows/controller-dispatch.yml"
PROFILE = "two-wave-v0800-b1-strict-continuity-v1"
CONTROLLER_TITLE = "controller: two-wave-v0800-b1-strict-continuity-v1"


class TwoWaveV0800B1StrictContinuityTest(unittest.TestCase):
    def test_protocol_freezes_strict_continuity_and_no_authority(self):
        value = json.loads(PROTOCOL_JSON.read_text(encoding="utf-8"))
        self.assertEqual(value["continuity_policy"]["direction_eligible_pair_semantic"], "shared_anchor_strict_L-H-L-H-L")
        self.assertEqual(value["continuity_policy"]["same_scale_ledger_nearest_role"], "diagnostic_only")
        self.assertFalse(value["continuity_policy"]["skip_based_pair_direction_authority"])
        self.assertEqual(value["rho"]["candidate"], [1.25, 4 / 3, 2 ** 0.5, 1.5])
        self.assertEqual(value["rho"]["legacy_control"], 2.0)
        self.assertFalse(value["rho"]["winner_selection_allowed"])
        for key in ("morphology_acceptance", "direction_authority", "trade_authority", "production_authority"):
            self.assertFalse(value["authority"][key])
        self.assertIsNone(value["authority"]["rho_winner"])

    def test_sources_compile_without_importing_heavy_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            for source in (PRODUCER, VERIFIER, BROKER, MIRROR):
                py_compile.compile(str(source), cfile=str(Path(tmp) / (source.name + ".pyc")), doraise=True)

    def test_producer_uses_only_shared_anchor_pairs_and_no_outcome_objective(self):
        text = PRODUCER.read_text(encoding="utf-8")
        self.assertIn("candidate.wave.end_bar == current.start_bar", text)
        self.assertIn('"strict_shared_anchor": True', text)
        self.assertIn("spearman_log_duration_ratio_vs_path_rms_21", text)
        self.assertIn("spearman_log_channel_height_ratio_vs_path_rms_21", text)
        self.assertIn('"rho_winner": None', text)
        self.assertIn('"future_outcome_used": False', text)
        self.assertIn('"direction_authority": False', text)
        self.assertNotIn("forward_return", text)
        self.assertNotIn("transaction_cost", text)

    def test_verifier_reenumerates_exact_strict_pair_set(self):
        text = VERIFIER.read_text(encoding="utf-8")
        self.assertIn("expected_strict_keys", text)
        self.assertIn("got_keys != expected_keys", text)
        self.assertIn("nonshared_anchor_pair", text)
        self.assertIn("skip_based_authority_violation", text)
        self.assertIn("premature_rho_authority", text)

    def test_broker_pins_same_consumed_development_data(self):
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
        self.assertIn("skip_based_pair_direction_authority", text)
        self.assertNotIn("STRICT_PAIRS.csv", text)

    def test_human_protocol_blocks_v0800_c(self):
        text = PROTOCOL_MD.read_text(encoding="utf-8")
        self.assertIn("V0800-C is blocked", text)
        self.assertIn("single-scale", text)
        self.assertIn("shared-anchor", text)
        self.assertIn("No 2026 data", text)

    def test_standard_workflow_routes_exact_b1_profile_through_all_phases(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("pull_request_target:", text)
        self.assertIn(f"- {PROFILE}", text)
        broker = "executor/two_wave_v0800_b1_strict_continuity_broker.py"
        for phase in ("prepare", "compute", "cleanup", "publish"):
            self.assertIn(f"python3 {broker} {phase} {PROFILE}", text)
        self.assertIn("python3 executor/two_wave_v0800_b1_strict_continuity_private_mirror.py", text)
        self.assertEqual(text.count(f"python3 {broker} prepare {PROFILE}"), 1)
        self.assertEqual(text.count(f"python3 {broker} compute {PROFILE}"), 1)
        self.assertEqual(text.count(f"python3 {broker} cleanup {PROFILE}"), 1)
        self.assertEqual(text.count(f"python3 {broker} publish {PROFILE}"), 1)

    def test_controller_accepts_only_exact_b1_title_and_dispatches_standard_workflow(self):
        text = CONTROLLER.read_text(encoding="utf-8")
        self.assertIn(CONTROLLER_TITLE, text)
        self.assertIn(f"profile='{PROFILE}'", text)
        self.assertEqual(text.count(CONTROLLER_TITLE), 2)
        self.assertEqual(text.count(f"profile='{PROFILE}'"), 1)
        self.assertIn("actions/workflows/public-compute.yml/dispatches", text)
        self.assertIn("-f ref='cloud-workspace-v1'", text)
        self.assertNotIn("pull_request_target:", text)


if __name__ == "__main__":
    unittest.main()
