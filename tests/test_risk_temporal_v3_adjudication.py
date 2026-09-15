import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREREG = json.loads((ROOT / "docs/research/RISK_TOOL_V2_TEMPORAL_V3_ADJUDICATION_PREREG_20260915.json").read_text())
PROFILE = "risk-v2-temporal-stability-v3-adjudication"


class TemporalV3AdjudicationTest(unittest.TestCase):
    def test_input_is_exact_prior_authority_metrics(self):
        metrics = PREREG["parent_metrics"]
        self.assertEqual(PREREG["parent_metrics_authority_run"], "34926868278-1")
        self.assertEqual(metrics["bytes"], 170908)
        self.assertEqual(metrics["git_blob_sha1"], "478f73c1fb9ac9c91d670e67733623e1450da953")
        self.assertEqual(metrics["sha256"], "455a0f0d61993a933016e111aa1386eaf4ddf3ec6aeb9e28c109f08a559fd060")

    def test_scope_is_metric_only_and_non_rescue(self):
        rules = PREREG["adjudication_rules"]
        self.assertFalse(rules["metrics_recomputed"])
        self.assertFalse(rules["market_data_read"])
        self.assertFalse(rules["model_outputs_recomputed"])
        self.assertFalse(rules["model_or_calibration_change"])
        self.assertFalse(rules["numeric_threshold_change"])
        self.assertTrue(rules["v2_result_34926868278_1_remains_immutable"])
        self.assertTrue(rules["result_is_consumed_data_proxy_not_fresh_oos"])

    def test_profile_is_frozen_v3(self):
        self.assertEqual(PREREG["acceptance_profile"]["profile_id"], "risk-tool-v2-temporal-stability-hierarchical-v3")
        self.assertEqual(PREREG["acceptance_profile"]["ordering_negative_streak_condition"], "ordering_gain < 0")
        self.assertEqual(PREREG["acceptance_profile"]["ordering_zero_gain_role"], "neutral_breaks_negative_streak")

    def test_broker_is_exact_and_dispatch_only(self):
        broker = (ROOT / "executor/risk_temporal_v3_adjudication_broker.py").read_text()
        self.assertIn('PROFILE_NAME = "' + PROFILE + '"', broker)
        self.assertIn('PARENT_BLOB = "478f73c1fb9ac9c91d670e67733623e1450da953"', broker)
        self.assertIn('PARENT_BYTES = 170908', broker)
        self.assertIn('PARENT_SHA256 = "455a0f0d61993a933016e111aa1386eaf4ddf3ec6aeb9e28c109f08a559fd060"', broker)
        self.assertIn('GITHUB_EVENT_NAME") != "workflow_dispatch"', broker)

    def test_producer_does_not_recompute_market_or_model(self):
        src = (ROOT / "executor/risk_temporal_v3_adjudication.py").read_text().lower()
        for forbidden in ("parquet", "build_state_rows", "build_primary_cohort", "predict(", "platt(", "bootstrap("):
            self.assertNotIn(forbidden, src)
        self.assertIn("metrics_recomputed", src)

    def test_private_mirror_is_text_only(self):
        mirror = (ROOT / "executor/risk_temporal_v3_adjudication_private_mirror.py").read_text()
        self.assertIn("ACCEPTANCE_RESULT_V3.json", mirror)
        self.assertIn("SUMMARY.json", mirror)
        self.assertNotIn("parquet", mirror.lower())

    def test_standard_routes_registered(self):
        workflow = (ROOT / ".github/workflows/public-compute.yml").read_text()
        controller = (ROOT / ".github/workflows/controller-dispatch.yml").read_text()
        self.assertIn(PROFILE, workflow)
        self.assertIn("controller: " + PROFILE, controller)


if __name__ == "__main__": unittest.main()
