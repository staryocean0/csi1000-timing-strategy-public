import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "executor"))
import wave_scale_state_conditional_calibration_v1 as c

PROTOCOL = ROOT / "docs/research/TWO_WAVE_SCALE_STATE_CONDITIONAL_CALIBRATION_PROTOCOL_20260917.json"
CHECKPOINT = ROOT / "docs/research/TWO_WAVE_SCALE_STATE_CONDITIONAL_CALIBRATION_SOURCE_CHECKPOINT_20260917.json"
LINEAGE = ROOT / "docs/research/TWO_WAVE_RESEARCH_LINEAGE_20260916.json"
AUTHORITY = ROOT / "docs/research/TWO_WAVE_SEGMENTATION_DOMINANCE_THREAD_AUTHORITY_20260917.json"


class CalibrationSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = json.loads(PROTOCOL.read_text())
        cls.c = json.loads(CHECKPOINT.read_text())
        cls.l = json.loads(LINEAGE.read_text())
        cls.a = json.loads(AUTHORITY.read_text())

    def test_frozen_input_hashes(self):
        f = self.p["frozen_inputs"]
        self.assertEqual(f["validity_diagnostics_sha256"], "5e7199a3ae42816751a353d7ca6d4fdbd11281e24666fa6de43e499fc42931e8")
        self.assertEqual(f["dominance_diagnostics_sha256"], "aed0b65305f06d36dfd679df4ee75feb48b246a40e3a5e39831cefedf2ee3baa")
        self.assertEqual(f["reference_labels_sha256"], "6fb36ee74413c9b7e95824a94a89bec74a493513668a36b3373c24518fc834be")
        self.assertEqual(f["full_inventory_sha256"], "32f6279610def838474fb0bc4596c33dfb41f88e4fb78e4a20d6b39942446206")

    def test_loyo_and_false_reject_cap_are_frozen(self):
        self.assertEqual(self.p["calendar_folds"]["years"], list(c.YEARS))
        self.assertEqual(self.p["calendar_folds"]["type"], "LEAVE_ONE_CALENDAR_YEAR_OUT")
        self.assertFalse(self.p["calendar_folds"]["calendar_used_as_feature"])
        self.assertEqual(self.p["binary_rule_family"]["false_reject_cap"], c.FALSE_REJECT_CAP)

    def test_feature_directions_match_source(self):
        self.assertEqual(self.p["validity"]["directions"], c.VALIDITY_DIRECTIONS)
        self.assertEqual(self.p["dominance"]["directions"], c.DOMINANCE_DIRECTIONS)
        self.assertNotIn("amplitude", json.dumps(self.p["validity"]).lower())
        self.assertNotIn("amplitude", json.dumps(self.p["dominance"]).lower())

    def test_morphology_objective_is_non_degenerate(self):
        self.assertEqual(self.p["morphology"]["objective"][:3], [
            "MAXIMIZE_CORRECT_DECISIONS", "MINIMIZE_WRONG_DECISIONS", "MINIMIZE_AMBIGUITY"
        ])

    def test_prior_27_lineage_is_unchanged(self):
        raw = json.dumps(self.l["ordered_lineage"][:27], sort_keys=True,
                         separators=(",", ":")).encode()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), self.c["prior_27_lineage_sha256"])
        self.assertEqual(self.c["prior_27_lineage_sha256"], "e51d6f64d014b762a538b4803705631db46a9e4372aec74da1fa479a1d725176")

    def test_order_28_records_not_fit_status(self):
        self.assertGreaterEqual(len(self.l["ordered_lineage"]), 28)
        row = self.l["ordered_lineage"][27]
        self.assertEqual((row["order"], row["issue"]), (28, 376))
        self.assertFalse(row["real_oof_fit_run"])
        self.assertFalse(row["numeric_thresholds_selected"])
        self.assertEqual(row["validity_diagnostics_sha256"], self.p["frozen_inputs"]["validity_diagnostics_sha256"])

    def test_authority_advances_only_to_source_ready(self):
        lane = next(x for x in self.a["active_lanes"] if x["issue"] == 353)
        self.assertIn(lane["status"], {"VALIDITY_MEASUREMENT_PASSED_CALIBRATION_ENGINE_SOURCE_READY_NOT_FIT","FIRST_REAL_LOYO_FAILED_DIAGNOSTIC_FAMILY_REVISION_REQUIRED","DIAGNOSTIC_FAMILY_V2_PROFILE_SOURCE_READY_NOT_RUN","V2_DEVELOPMENT_LOYO_NOT_READY_ABSTENTION_COLLAPSE_NO_FULL_FIT","FIXED_LAG_CONFIRMATION_PROFILE_SOURCE_READY_NOT_RUN","FIXED_LAG_DEVELOPMENT_LOYO_NOT_READY_OBJECTIVE_ABSTENTION_COLLAPSE_NO_LAG_PROMOTION","CALIBRATION_V3_SOURCE_READY_NOT_RUN","CALIBRATION_V3_DEVELOPMENT_OOF_NOT_READY_AMBIGUITY_VALIDITY_REVISION_REQUIRED"})
        s = self.a["S2_progress"]
        self.assertTrue(s["validity_diagnostics_measured"])
        self.assertFalse(s["calibration_real_oof_run"])
        self.assertIsNone(s["numeric_validity_thresholds"])
        self.assertIsNone(s["market_thresholds"])
        self.assertFalse(s["full_192_candidate_fit"])

    def test_checkpoint_preserves_no_authority(self):
        self.assertEqual(self.c["status"], "CALIBRATION_ENGINE_SOURCE_READY_REAL_OOF_NOT_RUN")
        self.assertFalse(self.c["real_oof_fit_run"])
        self.assertFalse(self.c["numeric_thresholds_selected"])
        self.assertFalse(self.c["production_authority"])
        self.assertEqual(self.c["synthetic_tests"], 12)

    def test_no_full_fit_or_readiness_claim(self):
        self.assertFalse(self.p["real_oof_fit_run"])
        self.assertFalse(self.p["full_192_candidate_fit_allowed_before_oof_adjudication"])
        self.assertTrue(self.p["fresh_oos_required_for_readiness"])
        self.assertFalse(self.p["production_authority"])


if __name__ == "__main__":
    unittest.main()
