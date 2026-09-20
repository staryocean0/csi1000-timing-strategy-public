from __future__ import annotations

import hashlib
import io
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "executor"))

import two_wave_local_state_exit_direction_asymmetry_broker_v1 as broker


class DirectionAsymmetryProfileTests(unittest.TestCase):
    def test_profile_and_parent_identity_are_frozen(self):
        self.assertEqual(
            broker.PROFILE_NAME,
            "two-wave-local-state-exit-direction-asymmetry-v1",
        )
        self.assertEqual(
            broker.PRIVATE_REF,
            "ae42b188d878f736c1fa2a2e193a635c5c911596",
        )
        self.assertEqual(broker.PARENT_RELEASE_ID, 392309871)
        self.assertEqual(broker.PARENT_ASSET_ID, 576094469)
        self.assertEqual(broker.PARENT_ASSET_NAME, "results.tar.gz")
        self.assertEqual(broker.PARENT_ASSET_BYTES, 2_059_472)
        self.assertEqual(
            broker.PARENT_ASSET_SHA256,
            "73141f57accfd02aa4607ebcd93843fed0b42905e5c06733671c5a010913f7c8",
        )
        self.assertEqual(
            broker.PARENT_MEMBER,
            "study/ISSUE624_SCORED_LEDGER.csv",
        )
        self.assertEqual(broker.PARENT_MEMBER_BYTES, 7_187_315)
        self.assertEqual(
            broker.PARENT_MEMBER_SHA256,
            "c1ef13cfc3b2bc5669955ff62a5200b6c56c6868b459421d7e621e5ed189f46f",
        )
        self.assertFalse(broker.PROFILE["new_training"])
        self.assertFalse(broker.PROFILE["production_authority"])

    def test_public_sources_match_hardcoded_hashes(self):
        self.assertEqual(
            broker.sha256(broker.PREREG),
            broker.PREREG_SHA256,
        )
        for name, expected in broker.SCRIPT_SHA256.items():
            self.assertEqual(broker.sha256(ROOT / "executor" / name), expected)
        broker._verify_public_sources()

    def test_commands_are_fixed_and_verifier_is_independent(self):
        self.assertEqual(
            broker.PROFILE["command"],
            [
                "two_wave_issue647/two_wave_local_state_exit_direction_asymmetry_v1.py",
                "--ledger",
                "/work/inputs/ISSUE624_SCORED_LEDGER.csv",
                "--out",
                "/results/study/ISSUE647_RESULT.json",
            ],
        )
        self.assertEqual(
            broker.PROFILE["verify_command"],
            [
                "two_wave_issue647/two_wave_local_state_exit_direction_asymmetry_verifier_v1.py",
                "--ledger",
                "/work/inputs/ISSUE624_SCORED_LEDGER.csv",
                "--result",
                "/results/study/ISSUE647_RESULT.json",
                "--prereg",
                "/work/two_wave_issue647/PREREG.json",
            ],
        )
        verifier = (
            ROOT
            / "executor"
            / "two_wave_local_state_exit_direction_asymmetry_verifier_v1.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn(
            "import two_wave_local_state_exit_direction_asymmetry_v1",
            verifier,
        )

    def test_workflow_registers_exact_standard_four_phase_route(self):
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
                "two_wave_local_state_exit_direction_asymmetry_broker_v1.py "
                f"{phase} {name}"
            )
            self.assertEqual(workflow.count(command), 1)
        self.assertIn("github.event_name == 'workflow_dispatch'", workflow)
        self.assertNotIn("pull_request_target:", workflow)

    def test_timeout_override_is_profile_local(self):
        self.assertEqual(broker.PROFILE["command_timeout_seconds"], 900)
        self.assertEqual(broker.PROFILE["verification_timeout_seconds"], 900)
        self.assertEqual(broker.HOST_TIMEOUT_SECONDS, 960)
        old_compute = broker.rb.COMPUTE_HOST_TIMEOUT_SECONDS
        old_verify = broker.rb.VALIDATE_HOST_TIMEOUT_SECONDS
        try:
            broker.configure_host_timeouts()
            self.assertEqual(broker.rb.COMPUTE_HOST_TIMEOUT_SECONDS, 960)
            self.assertEqual(broker.rb.VALIDATE_HOST_TIMEOUT_SECONDS, 960)
        finally:
            broker.rb.COMPUTE_HOST_TIMEOUT_SECONDS = old_compute
            broker.rb.VALIDATE_HOST_TIMEOUT_SECONDS = old_verify

    def test_parent_archive_extraction_is_single_member_and_fail_closed(self):
        payload = b"synthetic-ledger\n"
        digest = hashlib.sha256(payload).hexdigest()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            archive = root / "parent.tar.gz"
            with tarfile.open(archive, "w:gz") as tar:
                target = tarfile.TarInfo("study/ISSUE624_SCORED_LEDGER.csv")
                target.size = len(payload)
                tar.addfile(target, io.BytesIO(payload))
                extra = b"do-not-extract"
                other = tarfile.TarInfo("study/OTHER.csv")
                other.size = len(extra)
                tar.addfile(other, io.BytesIO(extra))
            destination = root / "ledger.csv"
            with mock.patch.object(
                broker,
                "PARENT_MEMBER_BYTES",
                len(payload),
            ), mock.patch.object(
                broker,
                "PARENT_MEMBER_SHA256",
                digest,
            ):
                broker._extract_parent_ledger(archive, destination)
            self.assertEqual(destination.read_bytes(), payload)
            self.assertFalse((root / "OTHER.csv").exists())

    def test_broker_requires_standard_dispatch_context(self):
        text = (
            ROOT
            / "executor"
            / "two_wave_local_state_exit_direction_asymmetry_broker_v1.py"
        ).read_text(encoding="utf-8")
        self.assertIn(
            'env.get("GITHUB_EVENT_NAME") != "workflow_dispatch"',
            text,
        )
        self.assertIn(
            'env.get("GITHUB_REF") != "refs/heads/cloud-workspace-v1"',
            text,
        )
        self.assertIn("rb.prepare(PROFILE_NAME, PROFILE)", text)
        self.assertIn("rb.compute()", text)
        self.assertIn("rb.cleanup()", text)
        self.assertIn("rb.publish(PROFILE)", text)


if __name__ == "__main__":
    unittest.main()
