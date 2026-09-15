from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILE = "two-wave-v0800-duration-scale-map-v1"
WORKFLOW = ROOT / ".github/workflows/public-compute.yml"
CONTROLLER = ROOT / ".github/workflows/controller-dispatch.yml"
BROKER = ROOT / "executor/two_wave_v0800_scale_map_broker.py"
MIRROR = ROOT / "executor/two_wave_v0800_scale_map_private_mirror.py"
PRODUCER = ROOT / "executor/two_wave_v0800_scale_map.py"
VERIFIER = ROOT / "executor/two_wave_v0800_scale_map_verifier.py"


class TwoWaveV0800ExecutorContractTest(unittest.TestCase):
    def test_sources_compile_without_importing_heavy_dependencies(self):
        for path in (BROKER, MIRROR, PRODUCER, VERIFIER):
            self.assertTrue(path.is_file(), str(path))
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    def test_standard_workflow_routes_exact_profile_through_all_phases(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn(f"- {PROFILE}", text)
        for phase in ("prepare", "compute", "cleanup", "publish"):
            self.assertIn(
                f"python3 executor/two_wave_v0800_scale_map_broker.py {phase} {PROFILE}",
                text,
            )
        self.assertIn("python3 executor/two_wave_v0800_scale_map_private_mirror.py", text)
        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("pull_request_target:", text)

    def test_bounded_issue_controller_routes_only_exact_two_wave_title(self):
        text = CONTROLLER.read_text(encoding="utf-8")
        self.assertIn(f"controller: {PROFILE}", text)
        self.assertIn(f"profile='{PROFILE}'", text)
        self.assertIn("ref='cloud-workspace-v1'", text)

    def test_broker_pins_consumed_development_identity_and_no_training(self):
        text = BROKER.read_text(encoding="utf-8")
        self.assertIn('DATA_SHA256 = "bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48"', text)
        self.assertIn('SOURCE_REF = "152ae1ef11a04bb3b434da25025794db7a706c81"', text)
        self.assertIn('"new_training": False', text)
        self.assertIn('"production_authority": False', text)
        self.assertIn('env.get("GITHUB_EVENT_NAME") != "workflow_dispatch"', text)

    def test_private_mirror_is_aggregate_only_and_success_only(self):
        text = MIRROR.read_text(encoding="utf-8")
        self.assertIn('TEXT_OUTPUTS = ("SUMMARY.json", "INPUT_RECEIPT.json")', text)
        self.assertNotIn("A_WAVES.csv", text)
        self.assertNotIn("SAME_SCALE_MATCHES.csv", text)
        self.assertIn('state.get("compute_success") is not True', text)
        self.assertIn('value.get("rho_winner") is not None', text)


if __name__ == "__main__":
    unittest.main()
