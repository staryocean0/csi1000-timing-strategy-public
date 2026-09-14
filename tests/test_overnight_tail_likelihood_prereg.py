import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "docs" / "research" / "OVERNIGHT_CONTINUOUS_DRIVER_TAIL_LIKELIHOOD_V1_PREREG_20260914.json"
WORKFLOW = ROOT / ".github" / "workflows" / "public-compute.yml"
CONTROLLER = ROOT / ".github" / "workflows" / "controller-dispatch.yml"
IDENTITY = "overnight_continuous_driver_tail_likelihood_v1"
PROFILE_NAME = "overnight-continuous-tail-likelihood-dev-v1"


class OvernightTailLikelihoodPreregTests(unittest.TestCase):
    def load(self):
        return json.loads(PROTOCOL.read_text())

    def test_identity_is_result_free_and_non_rescue(self):
        p = self.load()
        self.assertEqual(p["schema_id"], "csi1000.overnight_continuous_driver_tail_likelihood_prereg@1.0")
        self.assertEqual(p["research_identity"], IDENTITY)
        self.assertEqual(p["stage"], "result_free_development_preregistration")
        self.assertEqual(set(p["feature_vector"]), {"global_risk_z", "china_offshore_z", "driver_coherence", "log_rvol20"})
        self.assertTrue(all(value is False for value in p["non_rescue_contract"].values()))
        self.assertFalse(p["current_layer2_risk_tool_authority_changed"])
        self.assertTrue(p["new_training"])
        self.assertFalse(p["production_authority"])

    def test_private_carrier_snapshot_and_blackbox_boundary_are_fixed(self):
        p = self.load()
        src = p["private_development_snapshot"]
        self.assertEqual(src["materialization_public_run_id"], "34837972995-1")
        self.assertEqual(src["receipt_git_blob_sha1"], "453ad4ad1a2defd8a032d05cc24742db727d323b")
        self.assertEqual(src["release_tag"], "public-research-run-34837972995-1")
        self.assertEqual(src["asset_name"], "results.tar.gz")
        self.assertEqual(src["asset_bytes"], 218006)
        self.assertEqual(src["asset_sha256"], "e1c716fc33fb0b5e50aabff0362f2de8d7bf94aff12ab83a715ea4dfb9384b06")
        self.assertEqual(src["allowed_calendar_window"], "2015-01-05..2020-12-31")
        self.assertEqual(src["forbidden_row_level_window"], "2021-01-01..2025-12-31")
        self.assertFalse(src["source_repository_runtime_access"])
        self.assertFalse(p["future_reusable_blackbox"]["authorized_now"])
        self.assertFalse(p["future_reusable_blackbox"]["reuse_is_independent_oos"])

    def test_target_model_calibration_and_abstention_are_frozen(self):
        p = self.load()
        self.assertEqual(p["target"]["fit_lower_quantile"], 0.10)
        self.assertEqual(p["target"]["fit_upper_quantile"], 0.90)
        self.assertEqual(p["time_splits"]["fit"], "2015-01-05..2018-12-31")
        self.assertEqual(p["time_splits"]["calibration"], "2019-01-02..2019-12-31")
        self.assertEqual(p["time_splits"]["development_holdout"], "2020-01-02..2020-12-31")
        self.assertEqual(p["model"]["family"], "multinomial_logistic_regression")
        self.assertEqual(p["model"]["parameterization"], "MID_reference_two_logit_softmax")
        self.assertEqual(p["model"]["l2_lambda"], 0.01)
        self.assertEqual(p["probability_calibration"]["method"], "single_temperature_scaling")
        self.assertEqual(p["abstention"]["score_threshold"], "calibration 80th percentile of directional_score")
        self.assertEqual(p["development_decision"]["enum"], ["DEV_PASS", "DEV_NO_PROGRESS", "DEV_INSUFFICIENT"])
        self.assertFalse(p["development_decision"]["automatic_repair_after_nonpass"])

    def test_preregistration_has_no_execution_route(self):
        workflow = WORKFLOW.read_text()
        controller = CONTROLLER.read_text()
        self.assertNotIn(PROFILE_NAME, workflow)
        self.assertNotIn(PROFILE_NAME, controller)
        self.assertFalse((ROOT / "executor" / "overnight_tail_likelihood_dev.py").exists())
        self.assertFalse((ROOT / "executor" / "overnight_tail_likelihood_broker.py").exists())


if __name__ == "__main__":
    unittest.main()
