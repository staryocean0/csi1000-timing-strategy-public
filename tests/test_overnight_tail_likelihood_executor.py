import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXECUTOR = ROOT / "executor"
WORKFLOW = ROOT / ".github/workflows/public-compute.yml"
CONTROLLER = ROOT / ".github/workflows/controller-dispatch.yml"
PROFILE = EXECUTOR / "overnight_tail_likelihood_profile.json"
PREREG = ROOT / "docs/research/OVERNIGHT_CONTINUOUS_DRIVER_TAIL_LIKELIHOOD_V1_PREREG_20260914.json"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class OvernightTailLikelihoodExecutorTests(unittest.TestCase):
    def test_training_profile_is_exact_and_private_snapshot_is_fixed(self):
        p = json.loads(PROFILE.read_text())
        self.assertEqual(p["profile_name"], "overnight-continuous-tail-likelihood-dev-v1")
        self.assertTrue(p["new_training"])
        self.assertFalse(p["production_authority"])
        source = p["carrier_source"]
        self.assertEqual(source["receipt_ref"], "runs/public-research/34837972995-1")
        self.assertEqual(source["receipt_git_blob_sha1"], "453ad4ad1a2defd8a032d05cc24742db727d323b")
        self.assertEqual(source["release_tag"], "public-research-run-34837972995-1")
        self.assertEqual(source["asset_bytes"], 218006)
        self.assertEqual(source["asset_sha256"], "e1c716fc33fb0b5e50aabff0362f2de8d7bf94aff12ab83a715ea4dfb9384b06")

    def test_broker_is_bounded_and_never_uses_external_source_runtime(self):
        text = (EXECUTOR / "overnight_tail_likelihood_broker.py").read_text()
        self.assertIn("overnight-continuous-tail-likelihood-dev-v1", text)
        self.assertIn('MATERIALIZATION_RUN_ID = "34837972995-1"', text)
        self.assertIn("public-research-run-{MATERIALIZATION_RUN_ID}", text)
        self.assertIn("blackbox_row_file_exposed", text)
        self.assertNotIn("factorlab-overnight-open-lab", text)
        self.assertNotIn("raw.githubusercontent.com", text)
        self.assertNotIn("urllib.request", text)
        self.assertNotIn("extractall", text)
        self.assertIn("range(2015, 2021)", text)

    def test_old_generic_broker_still_rejects_training(self):
        generic = load_module("generic_research_broker_tail_test", EXECUTOR / "research_broker.py")
        profile = json.loads((EXECUTOR / "research_profiles.json").read_text())["profiles"]["handoff-verify-v1"]
        with self.assertRaises(generic.GateError):
            generic.validate_profile({**profile, "new_training": True})

    def test_preregistered_science_is_immutable_input(self):
        p = json.loads(PROFILE.read_text())
        frozen = json.loads(PREREG.read_text())
        self.assertEqual(frozen["research_identity"], "overnight_continuous_driver_tail_likelihood_v1")
        self.assertEqual(frozen["time_splits"]["blackbox"], "not_authorized_by_this_protocol")
        self.assertFalse(frozen["future_reusable_blackbox"]["authorized_now"])
        self.assertFalse(frozen["production_authority"])
        protocol_meta = p["public_source_files"]["docs/research/OVERNIGHT_CONTINUOUS_DRIVER_TAIL_LIKELIHOOD_V1_PREREG_20260914.json"]
        self.assertEqual(protocol_meta["git_blob_sha1"], "3e786f15f052ef5576c0957d3ebfa33d80c4cfc4")
        self.assertEqual(protocol_meta["sha256"], "cb153fa7f4642cf859ffc6fbf40011823bc314258a5ff704ecb02953f2fd26fd")

    def test_entry_reports_training_without_changing_production_authority(self):
        text = (EXECUTOR / "overnight_tail_likelihood_entry.py").read_text()
        self.assertIn('value["new_training"] = True', text)
        self.assertIn('value.get("production_authority") is not False', text)
        self.assertIn("_original_compute", text)
        self.assertIn("_original_publish", text)

    def test_workflow_and_controller_route_only_reviewed_training_profile(self):
        workflow = WORKFLOW.read_text()
        controller = CONTROLLER.read_text()
        profile = "overnight-continuous-tail-likelihood-dev-v1"
        self.assertIn(profile, workflow)
        self.assertIn(profile, controller)
        for phase in ("prepare", "compute", "cleanup", "publish"):
            self.assertIn(f"overnight_tail_likelihood_entry.py {phase} {profile}", workflow)
        self.assertIn("controller: overnight-continuous-tail-likelihood-dev-v1", controller)
        self.assertNotIn("\n  push:", workflow)


if __name__ == "__main__":
    unittest.main()
