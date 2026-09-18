import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "executor"))
import wave_scale_state_conditional_calibration_v3 as c

PROTOCOL = ROOT / "docs/research/TWO_WAVE_SCALE_STATE_CONDITIONAL_CALIBRATION_V3_PROTOCOL_20260918.json"
REG = ROOT / "docs/research/TWO_WAVE_SCALE_STATE_CONDITIONAL_CALIBRATION_V3_SOURCE_REGISTRATION_20260918.json"
LINEAGE = ROOT / "docs/research/TWO_WAVE_RESEARCH_LINEAGE_20260916.json"
AUTH = ROOT / "docs/research/TWO_WAVE_SEGMENTATION_DOMINANCE_THREAD_AUTHORITY_20260917.json"


class CalibrationV3SourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = json.loads(PROTOCOL.read_text())
        cls.r = json.loads(REG.read_text())
        cls.l = json.loads(LINEAGE.read_text())["ordered_lineage"]
        cls.a = json.loads(AUTH.read_text())

    def test_registration_engine_identity_and_not_run(self):
        self.assertEqual(self.r["issue"], 388)
        self.assertEqual(self.r["status"], "CALIBRATION_V3_SOURCE_READY_NOT_RUN")
        self.assertEqual(
            hashlib.sha256((ROOT / "executor/wave_scale_state_conditional_calibration_v3.py").read_bytes()).hexdigest(),
            self.r["engine_sha256"],
        )
        self.assertFalse(self.r["real_oof_run"])
        self.assertFalse(self.r["full_192_fit_performed"])
        self.assertFalse(self.r["lag_selected_or_promoted"])

    def test_prior_36_lineage_is_preserved(self):
        raw = json.dumps(self.l[:36], sort_keys=True, separators=(",", ":")).encode()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), self.r["prior_36_lineage_sha256"])
        self.assertEqual((self.l[36]["order"], self.l[36]["issue"]), (37, 388))
        self.assertEqual(self.l[36]["status"], "CALIBRATION_V3_SOURCE_READY_NOT_RUN")

    def test_protocol_uses_only_frozen_inputs(self):
        f = self.p["frozen_inputs"]
        self.assertEqual(f["fixed_lag_formal_run"], "35292230400-1")
        self.assertEqual(f["reference_labels_sha256"], "6fb36ee74413c9b7e95824a94a89bec74a493513668a36b3373c24518fc834be")
        self.assertEqual(f["dominance_v1_sha256"], "aed0b65305f06d36dfd679df4ee75feb48b246a40e3a5e39831cefedf2ee3baa")
        self.assertEqual(f["calendar_sha256"], "32f6279610def838474fb0bc4596c33dfb41f88e4fb78e4a20d6b39942446206")
        self.assertEqual(self.p["evaluation"]["lag_minutes"], [0,5,10,15,25])
        self.assertFalse(self.p["evaluation"]["lag_promotion_from_consumed_population"])

    def test_validity_semantics_are_one_sided(self):
        v = self.p["validity_v3"]
        self.assertEqual(v["semantics"], "ONE_SIDED_INVALID_GUARD")
        self.assertTrue(v["gate_features_legal_as_singles"])
        self.assertFalse(v["separate_valid_rule"])
        self.assertEqual(v["false_invalid_cap"], c.FALSE_INVALID_CAP)

    def test_morphology_objective_is_coverage_aware(self):
        m = self.p["morphology_v3"]
        self.assertEqual(m["axes"], "SAME_FIVE_V2_AXES_AND_ORIENTATIONS")
        self.assertFalse(m["features_added"])
        self.assertEqual(m["objective"][0], "MAXIMIZE_MIN_CLASS_RECALL_SUPPORTED_TURNING_VS_DEVELOPING_LEG")
        self.assertTrue(m["ambiguous_counts_as_miss_for_class_recall"])
        self.assertFalse(m["reference_ambiguous_used_for_fit"])

    def test_dominance_and_authority_not_promoted(self):
        self.assertEqual(self.p["dominance"]["family"], "V1_FROZEN_CONTROL_UNCHANGED")
        self.assertFalse(self.p["dominance"]["redesigned"])
        self.assertFalse(self.p["v3_real_oof_run"])
        self.assertFalse(self.p["production_authority"])
        lane = next(x for x in self.a["active_lanes"] if x["issue"] == 353)
        self.assertIn(lane["status"], {"CALIBRATION_V3_SOURCE_READY_NOT_RUN","CALIBRATION_V3_NOT_READY_AMBIGUITY_RECALL_COLLAPSE_VALIDITY_RECALL_LOW_NO_FULL_FIT","CALIBRATION_V4_SOURCE_READY_NOT_RUN","CALIBRATION_V4_NOT_READY_AMBIGUITY_RECALL_LOW_VALIDITY_RECALL_LOWER_NO_FULL_FIT","POST_V4_AUDIT_DIAGNOSTIC_FAMILY_REVISION_REQUIRED_BEFORE_ANY_CALIBRATION_V5"})
        self.assertIn(self.a["S2_progress"]["next"], {"MERGE_CALIBRATION_V3_THEN_RUN_FROZEN_FIXED_LAG_LOYO","RUN_THRESHOLD_FREE_AMBIGUITY_AND_VALIDITY_CAPACITY_AUDIT_BEFORE_V4_PREREGISTRATION","MERGE_CALIBRATION_V4_THEN_RUN_FROZEN_FIXED_LAG_LOYO","RUN_POST_V4_ERROR_AND_CAPACITY_AUDIT_BEFORE_ANY_V5_PREREGISTRATION","PREREGISTER_LABEL_BLIND_DIAGNOSTIC_FAMILY_V3_MULTISCALE_COMPETITION_AND_VALIDITY_SUBTYPE_EVIDENCE"})
        self.assertIn(self.a["S2_progress"]["calibration_v3_real_oof_run"], {False,"COMPLETED_DEVELOPMENT_OOF_NOT_READY"})


if __name__ == "__main__":
    unittest.main()
