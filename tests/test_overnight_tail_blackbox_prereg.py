import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "docs/research/OVERNIGHT_CONTINUOUS_DRIVER_TAIL_LIKELIHOOD_V1_REUSABLE_BLACKBOX_PREREG_20260914.json"


class OvernightTailBlackboxPreregTests(unittest.TestCase):
    def load(self):
        return json.loads(PROTOCOL.read_text())

    def test_identity_and_parent_model_are_fixed(self):
        p = self.load()
        self.assertEqual(p["schema_id"], "csi1000.overnight_continuous_driver_tail_likelihood_reusable_blackbox_prereg@1.0")
        self.assertEqual(p["research_identity"], "overnight_continuous_driver_tail_likelihood_reusable_blackbox_v1")
        self.assertEqual(p["stage"], "result_free_reusable_blackbox_preregistration")
        parent = p["parent_development_artifact"]
        self.assertEqual(parent["public_run_id"], "34847445307-1")
        self.assertEqual(parent["standard_receipt_git_blob_sha1"], "43dd71065d6854fbe545376ec7a8a7f4f6ff7c91")
        self.assertEqual(parent["dev_report_git_blob_sha1"], "4d96922fb86355054dfec64ea621d76e75f75365")
        self.assertEqual(parent["dev_decision"], "DEV_PASS")
        self.assertEqual(parent["frozen_model_git_blob_sha1"], "2a97f89fa75a575b03352a48498a8e7a1049cca6")
        self.assertEqual(parent["frozen_model_result_sha256"], "b5807e248ce142c54857929287fc0a040f3558eac13117de473377ab14b4f396")
        self.assertFalse(parent["production_authority"])

    def test_blackbox_source_set_is_exact_and_metadata_only_preregistered(self):
        p = self.load()
        source = p["blackbox_source"]
        self.assertEqual(source["ref"], "9905c2f8942ad0a2faf106d42c1b62fd6127e646")
        self.assertFalse(source["row_values_inspected_during_preregistration"])
        expected = {
            "data/development/csi1000_open_pit_panel.parquet": ("e850bfee1846eb51b9c825e1324bc5182265950d", 248701),
            "data/v6a_external_sources_2015_2025/hkma_usdcny_cross.parquet": ("0880cd72fb2673c43ecb9fdb45f8709a90e56529", 89181),
            "data/v6a_external_sources_2015_2025/sgx_a50_holiday_endpoints.parquet": ("6bbcc1a1330b3679f3635bd5de7fe2616c447cb5", 21838),
            "data/v6a_external_sources_2015_2025/sgx_a50_ordinary_preauction_endpoints.parquet": ("c6a2d814ba6761c9c33cdec2014567fadd3043b4", 465381),
            "data/v6a_external_sources_2015_2025/source_assertions.json": ("cbbb7eff173443eafb7476fe681916208823b249", 244),
        }
        self.assertEqual(set(source["files"]), set(expected))
        for path, (sha, size) in expected.items():
            self.assertEqual(source["files"][path], {"git_blob_sha1": sha, "bytes": size})
        self.assertTrue(all(source["required_source_assertions"].values()))

    def test_model_application_is_frozen_without_refit_or_recalibration(self):
        p = self.load()
        frozen = p["frozen_model_application"]
        self.assertEqual(frozen["feature_vector"], ["global_risk_z", "china_offshore_z", "driver_coherence", "log_rvol20"])
        self.assertIn("no refit", frozen["feature_means_and_population_sds"])
        self.assertIn("no recomputation", frozen["tail_cutoffs"])
        self.assertIn("no refit", frozen["two_logit_coefficients"])
        self.assertIn("no recalibration", frozen["temperature"])
        self.assertIn("no reselection", frozen["directional_margin_threshold"])
        self.assertFalse(frozen["holdout_or_blackbox_information_may_modify_model"])

    def test_blackbox_decision_and_output_surface_are_closed(self):
        p = self.load()
        self.assertEqual(p["decision_contract"]["enum"], ["PASS", "FAIL", "INSUFFICIENT"])
        self.assertFalse(p["decision_contract"]["automatic_repair_or_successor_after_nonpass"])
        self.assertFalse(p["decision_contract"]["hidden_behavior_may_guide_future_design"])
        output = p["blackbox_output_contract"]
        self.assertFalse(output["public_detail_release"])
        self.assertFalse(output["internal_metrics_persisted"])
        self.assertFalse(output["row_level_outputs"])
        self.assertEqual(output["stdout"], "decision token only")
        forbidden = " ".join(output["forbidden_persisted_or_printed_information"])
        for token in ("metric", "probabilities", "counts", "year", "gate", "failure", "rescue"):
            self.assertIn(token, forbidden)
        self.assertFalse(p["post_query_governance"]["automatic_next_query"])
        self.assertFalse(p["post_query_governance"]["automatic_successor"])
        self.assertFalse(p["post_query_governance"]["2021_2025_reuse_after_query_is_independent_oos"])
        self.assertFalse(p["production_authority"])

    def test_blackbox_window_and_sufficiency_are_frozen(self):
        p = self.load()
        window = p["blackbox_window"]
        self.assertEqual(window["start"], "2021-01-01")
        self.assertEqual(window["end"], "2025-12-31")
        self.assertFalse(window["reused_period_is_independent_oos"])
        suff = p["internal_evidence_sufficiency"]
        self.assertEqual(suff["pooled_complete_cases_min"], 900)
        self.assertEqual(suff["pooled_each_tail_cases_min"], 40)
        self.assertEqual(suff["each_calendar_year_complete_cases_min"], 150)
        self.assertEqual(suff["each_calendar_year_each_tail_cases_min"], 5)
        gates = p["internal_validation_gates"]
        self.assertEqual(gates["pooled_log_loss_relative_improvement_vs_frozen_fit_prior_min"], 0.01)
        self.assertEqual(gates["pooled_multiclass_brier_relative_improvement_vs_frozen_fit_prior_min"], 0.01)
        self.assertEqual(gates["pooled_down_one_vs_rest_auc_min"], 0.55)
        self.assertEqual(gates["pooled_up_one_vs_rest_auc_min"], 0.55)
        self.assertEqual(gates["active_decisions_min"], 60)
        self.assertEqual(gates["active_each_direction_min"], 15)


if __name__ == "__main__":
    unittest.main()
