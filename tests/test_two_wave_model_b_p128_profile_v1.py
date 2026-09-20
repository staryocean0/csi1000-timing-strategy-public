import base64
import json
import os
import sys
import unittest
from unittest import mock
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

    def test_issue635_timeout_repair_stays_inside_standard_step_budget(self):
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
        self.assertIn("      - name: Compute without private credentials", workflow)
        self.assertIn("        timeout-minutes: 35", workflow)

    def test_private_receipt_training_flag_is_corrected_and_read_back(self):
        receipt = {
            "public_run_id": "123-1",
            "profile": broker.PROFILE_NAME,
            "new_training": False,
        }

        class FakeAPI:
            def __init__(self):
                self.content = base64.b64encode(
                    (json.dumps(receipt, indent=2) + "\n").encode()
                ).decode()
                self.sha = "oldsha"
                self.put_payload = None

            def request(self, path, payload=None, method="GET"):
                if method == "PUT":
                    self.put_payload = payload
                    self.content = payload["content"]
                    self.sha = "newsha"
                    return {}
                return {"content": self.content, "sha": self.sha}

        api = FakeAPI()
        env = {"GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "1"}
        with mock.patch.dict(os.environ, env, clear=False), mock.patch.object(
            broker.rb, "require_private_api", return_value=api
        ):
            broker.correct_private_receipt_new_training()
        corrected = json.loads(base64.b64decode(api.content))
        self.assertIs(corrected["new_training"], True)
        self.assertEqual(api.put_payload["branch"], "runs/public-research/123-1")
        self.assertEqual(api.put_payload["sha"], "oldsha")

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
