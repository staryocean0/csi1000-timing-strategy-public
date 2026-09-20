import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "executor"))

import two_wave_model_b_p128_state_exit_broker_v1 as broker


class ModelBP128ProfileTests(unittest.TestCase):
    def test_profile_identity_is_frozen(self):
        self.assertEqual(
            broker.PROFILE_NAME,
            "two-wave-model-b-p128-state-exit-v1",
        )
        self.assertEqual(
            broker.PRIVATE_REF,
            "2815f50b5a1b2925f0e0118b0af0d578605ee882",
        )
        self.assertEqual(
            broker.PREREG_SHA256,
            "31784bcc4d4613347b1cda2e68f332e6d02703b9fcec3f07fc92834df875f508",
        )
        profile = broker.profile()
        self.assertTrue(profile["new_training"])
        self.assertFalse(profile["production_authority"])
    def test_source_manifest_matches_allowlist(self):
        manifest = json.loads(broker.MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(set(manifest["sources"]), set(broker.SCRIPT_NAMES))
        self.assertEqual(manifest["profile"], broker.PROFILE_NAME)
        self.assertEqual(
            manifest["private_result_base"],
            broker.PRIVATE_REF,
        )

    def test_commands_are_fixed_and_verifier_is_independent(self):
        profile = broker.profile()
        self.assertEqual(
            profile["command"],
            [
                "two_wave_issue635/run_two_wave_model_b_p128_state_exit_v1.py",
                "--data", "/work/inputs/5m_offset_0.parquet",
                "--out", "/results/study",
                "--prereg", "/work/two_wave_issue635/PREREG.json",
            ],
        )
        self.assertEqual(
            profile["verify_command"],
            [
                "two_wave_issue635/two_wave_model_b_p128_state_exit_verifier_v1.py",
                "--data", "/work/inputs/5m_offset_0.parquet",
                "--results", "/results/study",
                "--prereg", "/work/two_wave_issue635/PREREG.json",
            ],
        )
        verifier = (
            ROOT / "executor/two_wave_model_b_p128_state_exit_verifier_v1.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn(
            "import two_wave_model_b_p128_state_exit_v1",
            verifier,
        )

    def test_workflow_registers_exact_four_phase_route(self):
        workflow = (
            ROOT / ".github/workflows/public-compute.yml"
        ).read_text(encoding="utf-8")
        name = broker.PROFILE_NAME
        self.assertEqual(workflow.count(f"          - {name}\n"), 1)
        self.assertEqual(
            workflow.count(f" || inputs.profile == '{name}'"),
            2,
        )
        for phase in ("prepare", "compute", "cleanup", "publish"):
            command = (
                "python3 executor/"
                "two_wave_model_b_p128_state_exit_broker_v1.py "
                f"{phase} {name}"
            )
            self.assertEqual(workflow.count(command), 1)
        self.assertIn("github.event_name == 'workflow_dispatch'", workflow)
        self.assertNotIn("pull_request_target:", workflow)

    def test_issue635_timeouts_fit_standard_workflow_budget(self):
        profile = broker.profile()
        self.assertEqual(profile["command_timeout_seconds"], 900)
        self.assertEqual(profile["verification_timeout_seconds"], 900)
        self.assertEqual(broker.ISSUE635_HOST_TIMEOUT_SECONDS, 960)
        old_compute = broker.rb.COMPUTE_HOST_TIMEOUT_SECONDS
        old_verify = broker.rb.VALIDATE_HOST_TIMEOUT_SECONDS
        try:
            broker.configure_host_timeouts()
            self.assertEqual(broker.rb.COMPUTE_HOST_TIMEOUT_SECONDS, 960)
            self.assertEqual(broker.rb.VALIDATE_HOST_TIMEOUT_SECONDS, 960)
        finally:
            broker.rb.COMPUTE_HOST_TIMEOUT_SECONDS = old_compute
            broker.rb.VALIDATE_HOST_TIMEOUT_SECONDS = old_verify
        workflow = (ROOT / ".github/workflows/public-compute.yml").read_text()
        self.assertIn("timeout-minutes: 35", workflow)

    def test_broker_requires_standard_dispatch_context(self):
        text = (
            ROOT / "executor/two_wave_model_b_p128_state_exit_broker_v1.py"
        ).read_text(encoding="utf-8")
        self.assertIn(
            'env.get("GITHUB_EVENT_NAME") != "workflow_dispatch"',
            text,
        )
        self.assertIn(
            'env.get("GITHUB_REF") != "refs/heads/cloud-workspace-v1"',
            text,
        )
        self.assertIn("rb.prepare(PROFILE_NAME, fixed)", text)
        self.assertIn("rb.compute()", text)
        self.assertIn("rb.cleanup()", text)
        self.assertIn("rb.publish(fixed)", text)


if __name__ == "__main__":
    unittest.main()
