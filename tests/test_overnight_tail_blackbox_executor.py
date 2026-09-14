import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXECUTOR = ROOT / "executor"
PROFILE = EXECUTOR / "overnight_tail_blackbox_profile.json"
PROTOCOL = ROOT / "docs/research/OVERNIGHT_CONTINUOUS_DRIVER_TAIL_LIKELIHOOD_V1_REUSABLE_BLACKBOX_PREREG_20260914.json"
WORKFLOW = ROOT / ".github/workflows/public-compute.yml"
CONTROLLER = ROOT / ".github/workflows/controller-dispatch.yml"
PROFILE_NAME = "overnight-continuous-tail-likelihood-blackbox-v1"


class OvernightTailBlackboxExecutorTests(unittest.TestCase):
    def test_profile_pins_parent_and_reviewed_public_sources(self):
        p = json.loads(PROFILE.read_text())
        self.assertEqual(p["profile_name"], PROFILE_NAME)
        self.assertFalse(p["new_training"])
        self.assertFalse(p["production_authority"])
        self.assertEqual(p["parent_model"], {
            "ref": "runs/public-research/34847445307-1",
            "path": "research/public-runs/34847445307-1-overnight-tail-frozen-model.json",
            "git_blob_sha1": "2a97f89fa75a575b03352a48498a8e7a1049cca6",
        })
        self.assertEqual(p["parent_dev_report"]["required_decision"], "DEV_PASS")
        expected = {
            "overnight_tail_blackbox_stage_public.py": "053208edae1f89decf654d3865b12f7b8270c425",
            "overnight_tail_blackbox_query.py": "4ddaa8fa7edc4ee99eb486ecb39cfe0c3dc7caea",
            "verify_overnight_tail_blackbox_query.py": "cc67334dc218dd7a5b83253fecd3a772de41a867",
            "docs/research/OVERNIGHT_CONTINUOUS_DRIVER_TAIL_LIKELIHOOD_V1_REUSABLE_BLACKBOX_PREREG_20260914.json": "baa128d8e8978afccf34c7792f90439179a77377",
        }
        self.assertEqual({k: v["git_blob_sha1"] for k, v in p["public_source_files"].items()}, expected)

    def test_public_stage_is_credential_separated_and_exact_source_only(self):
        text = (EXECUTOR / "overnight_tail_blackbox_stage_public.py").read_text()
        self.assertIn("private_token_must_not_reach_public_blackbox_stage", text)
        self.assertIn("raw.githubusercontent.com", text)
        self.assertIn("git_blob_sha1", text)
        self.assertNotIn("csi1000-timing-strategy-private", text)
        protocol = json.loads(PROTOCOL.read_text())
        self.assertEqual(len(protocol["blackbox_source"]["files"]), 5)

    def test_broker_has_no_external_network_and_only_reads_pinned_parent(self):
        text = (EXECUTOR / "overnight_tail_blackbox_broker.py").read_text()
        self.assertIn(PROFILE_NAME, text)
        self.assertIn("verify_stage", text)
        self.assertIn("fetch_private_json", text)
        self.assertIn("parent_dev_report", text)
        self.assertIn("parent_model", text)
        self.assertIn('SOURCE_REPO = "staryocean0/factorlab-overnight-open-lab"', text)
        self.assertNotIn("raw.githubusercontent.com", text)
        self.assertNotIn("urllib.request", text)
        self.assertNotIn("extractall", text)

    def test_query_persists_only_low_bandwidth_receipt(self):
        text = (EXECUTOR / "overnight_tail_blackbox_query.py").read_text()
        self.assertIn('"decision": decision', text)
        self.assertIn('"internal_metrics_persisted": False', text)
        self.assertIn('"public_detail_release": False', text)
        self.assertIn('"reused_period_is_independent_oos": False', text)
        self.assertIn('print(receipt["decision"]', text)
        self.assertNotIn("predictions.csv", text)
        self.assertNotIn("metrics.json", text)
        self.assertNotIn("yearly_report", text.lower())

    def test_validator_recomputes_and_exact_compares_receipt(self):
        text = (EXECUTOR / "verify_overnight_tail_blackbox_query.py").read_text()
        self.assertIn("query.evaluate", text)
        self.assertIn("actual != expected", text)
        self.assertIn('"decision": actual["decision"]', text)
        for forbidden in ("log_loss", "brier", "auc", "active_count", "year_counts", "probabilities"):
            self.assertNotIn(forbidden, text)

    def test_broker_safe_mirror_has_exact_receipt_surface(self):
        text = (EXECUTOR / "overnight_tail_blackbox_broker.py").read_text()
        self.assertIn("overnight-tail-blackbox.json", text)
        self.assertIn("internal_metrics_persisted", text)
        self.assertIn("public_detail_release", text)
        self.assertIn("reused_period_is_independent_oos", text)
        self.assertIn("production_authority", text)
        self.assertIn("blackbox_result_surface", text)

    def test_workflow_and_controller_route_exact_profile_only(self):
        workflow = WORKFLOW.read_text()
        controller = CONTROLLER.read_text()
        self.assertIn(PROFILE_NAME, workflow)
        self.assertIn(PROFILE_NAME, controller)
        self.assertIn("Stage fixed public Overnight BLACKBOX inputs without private credentials", workflow)
        for phase in ("prepare", "compute", "cleanup", "publish"):
            self.assertIn(f"overnight_tail_blackbox_broker.py {phase} {PROFILE_NAME}", workflow)
        self.assertIn("controller: " + PROFILE_NAME, controller)
        self.assertNotIn("\n  push:", workflow)


if __name__ == "__main__":
    unittest.main()
