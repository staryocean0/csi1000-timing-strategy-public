from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "executor"))

import two_wave_t0_causal_c1_compression_interaction_broker_v1 as broker


class Issue615ProfileTests(unittest.TestCase):
    def test_profile_identity_is_frozen(self):
        self.assertEqual(
            broker.PRIVATE_REF,
            "7688ba57206dd29fbef88d8e57475255718471fe",
        )
        self.assertEqual(
            broker.SOURCE_REPO,
            "staryocean0/factorlab-two-wave-strategy-lab",
        )
        self.assertEqual(
            broker.SOURCE_REF,
            "152ae1ef11a04bb3b434da25025794db7a706c81",
        )
        self.assertEqual(
            broker.DATA_SHA256,
            "bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48",
        )
        self.assertEqual(broker.DATA_BYTES, 3351411)
        p = broker.profile()
        self.assertFalse(p["new_training"])
        self.assertFalse(p["production_authority"])

    def test_workflow_registers_all_four_phases(self):
        workflow = (ROOT / ".github/workflows/public-compute.yml").read_text()
        name = broker.PROFILE_NAME
        self.assertIn(f"- {name}", workflow)
        for phase in ("prepare", "compute", "cleanup", "publish"):
            command = (
                "python3 executor/"
                "two_wave_t0_causal_c1_compression_interaction_broker_v1.py "
                f"{phase} {name}"
            )
            self.assertIn(command, workflow)
        self.assertIn("github.event_name == 'workflow_dispatch'", workflow)

    def test_verifier_is_independent_of_issue615_study_module(self):
        text = (
            ROOT
            / "executor"
            / "two_wave_t0_causal_c1_compression_interaction_verifier_v1.py"
        ).read_text()
        self.assertNotIn(
            "import two_wave_t0_causal_c1_compression_interaction_v1", text
        )
        self.assertIn("BOOT_REPS = 5000", text)
        self.assertIn("BOOT_SEED = 20260919", text)

    def test_runner_does_not_publish_machine_absolute_path(self):
        text = (
            ROOT
            / "executor"
            / "run_two_wave_t0_causal_c1_compression_interaction_v1.py"
        ).read_text()
        self.assertIn('"data_ref":', text)
        self.assertNotIn('"data_path": str(data)', text)


if __name__ == "__main__":
    unittest.main()
