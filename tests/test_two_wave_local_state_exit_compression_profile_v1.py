from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "executor"))

import two_wave_local_state_exit_compression_broker_v1 as broker


class Issue624ProfileTests(unittest.TestCase):
    def test_profile_identity_is_frozen(self):
        self.assertEqual(
            broker.PROFILE_NAME,
            "two-wave-local-state-exit-compression-v1",
        )
        self.assertEqual(
            broker.PRIVATE_REF,
            "22ab2e181407fb1d0a9a71e61d880819fe1baec8",
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
        self.assertEqual(broker.DATA_BYTES, 3_351_411)
        self.assertEqual(
            broker.ORIGINAL_PREREG_SHA256,
            "2d434584b6456499811acbb8b57a19db6a772a801f45e8fcd34e5278a23eca3d",
        )
        self.assertEqual(
            broker.AMENDMENT_SHA256,
            "638cb071e182241825a62b2ce74aa93df349553feb72b77fe741d7b633fc948a",
        )
        profile = broker.profile()
        self.assertFalse(profile["new_training"])
        self.assertFalse(profile["production_authority"])
        self.assertEqual(profile["manifest_sha256"], broker.AMENDMENT_SHA256)

    def test_staged_script_allowlist_is_exact(self):
        self.assertEqual(
            broker.SCRIPT_NAMES,
            (
                "run_two_wave_local_state_exit_compression_v1.py",
                "two_wave_local_state_exit_compression_v1.py",
                "two_wave_local_state_exit_compression_verifier_v1.py",
                "two_wave_delayed_causal_wrapper_v1.py",
                "two_wave_current_band_recognizer_v1.py",
            ),
        )

    def test_commands_are_fixed_and_use_independent_verifier(self):
        profile = broker.profile()
        self.assertEqual(
            profile["command"],
            [
                "two_wave_issue624/run_two_wave_local_state_exit_compression_v1.py",
                "--data",
                "/work/inputs/5m_offset_0.parquet",
                "--out",
                "/results/study",
            ],
        )
        self.assertEqual(
            profile["verify_command"],
            [
                "two_wave_issue624/two_wave_local_state_exit_compression_verifier_v1.py",
                "--data",
                "/work/inputs/5m_offset_0.parquet",
                "--results",
                "/results/study",
            ],
        )
        verifier = (
            ROOT / "executor" / "two_wave_local_state_exit_compression_verifier_v1.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn(
            "import two_wave_local_state_exit_compression_v1",
            verifier,
        )

    def test_workflow_registers_exact_four_phase_route(self):
        workflow = (ROOT / ".github/workflows/public-compute.yml").read_text(
            encoding="utf-8"
        )
        name = broker.PROFILE_NAME
        self.assertEqual(
            workflow.count(f"          - {name}\n"),
            1,
        )
        self.assertEqual(
            workflow.count(f" || inputs.profile == '{name}'"),
            2,
        )
        for phase in ("prepare", "compute", "cleanup", "publish"):
            command = (
                "python3 executor/"
                "two_wave_local_state_exit_compression_broker_v1.py "
                f"{phase} {name}"
            )
            self.assertEqual(workflow.count(command), 1)
        self.assertIn("github.event_name == 'workflow_dispatch'", workflow)
        self.assertNotIn("pull_request_target:", workflow)

    def test_broker_requires_standard_dispatch_context(self):
        text = (
            ROOT / "executor" / "two_wave_local_state_exit_compression_broker_v1.py"
        ).read_text(encoding="utf-8")
        self.assertIn('env.get("GITHUB_EVENT_NAME") != "workflow_dispatch"', text)
        self.assertIn('env.get("GITHUB_REF") != "refs/heads/cloud-workspace-v1"', text)
        self.assertIn("rb.prepare(PROFILE_NAME, fixed)", text)
        self.assertIn("rb.compute()", text)
        self.assertIn("rb.cleanup()", text)
        self.assertIn("rb.publish(fixed)", text)


if __name__ == "__main__":
    unittest.main()
