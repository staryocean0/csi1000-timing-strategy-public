import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "executor"))
from tests.segmentation_carrier_registration_support import strip_validity_workflow, strip_validity_controller
import wave_scale_validity_market_broker_v1 as broker

PROFILE = "two-wave-scale-validity-diagnostic-measurement-v1"
MANIFEST = ROOT / "docs/research/TWO_WAVE_SCALE_VALIDITY_MARKET_EXECUTION_MANIFEST_V1.json"
PROTOCOL = ROOT / "docs/research/TWO_WAVE_SCALE_VALIDITY_MARKET_PROTOCOL_20260917.json"
REGISTRATION = ROOT / "docs/research/TWO_WAVE_SCALE_VALIDITY_MARKET_REGISTRATION_20260917.json"
WORKFLOW = ROOT / ".github/workflows/public-compute.yml"
CONTROLLER = ROOT / ".github/workflows/controller-dispatch.yml"
PARENT_WORKFLOW = "da1b6d3916b35155493bedefd28c911c52dc8a54"
PARENT_CONTROLLER = "2c6f10057ab1b0bffcf639cd1f244c0c283ebb54"


def blob_bytes(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def blob(path):
    return blob_bytes(path.read_bytes())

class ValidityMarketRegistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = json.loads(MANIFEST.read_text())
        cls.r = json.loads(REGISTRATION.read_text())

    def test_registration_scope(self):
        self.assertEqual((self.r["issue"], self.r["status"]), (376, "PROFILE_SOURCE_READY_NOT_RUN"))
        self.assertIsNone(self.r["formal_run"])
        self.assertFalse(self.r["reference_labels_visible_to_compute"])
        self.assertFalse(self.r["validity_state_assigned"])
        self.assertFalse(self.r["threshold_selection_in_run"])
        self.assertIsNone(self.r["numeric_validity_thresholds"])

    def test_prior_26_lineage_is_unchanged(self):
        value = json.loads((ROOT / "docs/research/TWO_WAVE_RESEARCH_LINEAGE_20260916.json").read_text())
        raw = json.dumps(value["ordered_lineage"][:26], sort_keys=True, separators=(",", ":")).encode()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), self.r["prior_26_lineage_sha256"])
        self.assertEqual(value["ordered_lineage"][26]["issue"], 376)
        self.assertFalse(value["ordered_lineage"][26]["threshold_selected"])

    def test_manifest_source_closure(self):
        self.assertEqual(self.m["profile"], PROFILE)
        self.assertEqual(len(self.m["source_blobs"]), 10)
        for name, expected in self.m["source_blobs"].items():
            self.assertEqual(blob(ROOT / "executor" / name), expected, name)
        self.assertEqual(blob(ROOT / "executor/wave_scale_validity_market_broker_v1.py"), self.m["broker_blob"])
        self.assertEqual(blob(ROOT / "executor/wave_segmentation_carrier_stage_public.py"), self.m["stage_blob"])
        self.assertEqual(blob(PROTOCOL), self.m["protocol_blob"])

    def test_dependency_surface_frozen(self):
        for name, expected in self.m["dependency_blobs"].items():
            self.assertEqual(blob(ROOT / "executor" / name), expected, name)
        self.assertEqual(self.m["command"], ["scale_validity_measurement/wave_scale_validity_market_entry_v1.py"])
        self.assertEqual(self.m["verify_command"], ["scale_validity_measurement/wave_scale_validity_market_verifier_v1.py"])

    def test_route_is_exact_append_to_parent(self):
        self.assertEqual(blob_bytes(strip_validity_workflow(WORKFLOW.read_text()).encode()), PARENT_WORKFLOW)
        self.assertEqual(blob_bytes(strip_validity_controller(CONTROLLER.read_text()).encode()), PARENT_CONTROLLER)

    def test_profile_occurrences_and_secret_surface(self):
        w = WORKFLOW.read_text(); c = CONTROLLER.read_text()
        self.assertEqual(w.count(PROFILE), 12)
        self.assertEqual(c.count(PROFILE), 3)
        self.assertEqual(w.count("secrets.FACTORLAB_PRIVATE_TOKEN"), 2)

    def test_authority_is_registered_not_run(self):
        a = json.loads((ROOT / "docs/research/TWO_WAVE_SEGMENTATION_DOMINANCE_THREAD_AUTHORITY_20260917.json").read_text())
        lane = next(x for x in a["active_lanes"] if x["issue"] == 353)
        self.assertIn(lane["status"], {"VALIDITY_DIAGNOSTIC_PROFILE_SOURCE_READY_NOT_RUN","VALIDITY_MEASUREMENT_PASSED_CALIBRATION_ENGINE_SOURCE_READY_NOT_FIT","FIRST_REAL_LOYO_FAILED_DIAGNOSTIC_FAMILY_REVISION_REQUIRED","DIAGNOSTIC_FAMILY_V2_PROFILE_SOURCE_READY_NOT_RUN","V2_DEVELOPMENT_LOYO_NOT_READY_ABSTENTION_COLLAPSE_NO_FULL_FIT","FIXED_LAG_CONFIRMATION_PROFILE_SOURCE_READY_NOT_RUN","FIXED_LAG_DEVELOPMENT_LOYO_NOT_READY_OBJECTIVE_ABSTENTION_COLLAPSE_NO_LAG_PROMOTION","CALIBRATION_V3_SOURCE_READY_NOT_RUN","CALIBRATION_V3_NOT_READY_AMBIGUITY_RECALL_COLLAPSE_VALIDITY_RECALL_LOW_NO_FULL_FIT","CALIBRATION_V4_SOURCE_READY_NOT_RUN","CALIBRATION_V4_NOT_READY_AMBIGUITY_RECALL_LOW_VALIDITY_RECALL_LOWER_NO_FULL_FIT","POST_V4_AUDIT_DIAGNOSTIC_FAMILY_REVISION_REQUIRED_BEFORE_ANY_CALIBRATION_V5"})
        if lane["status"] == "VALIDITY_DIAGNOSTIC_PROFILE_SOURCE_READY_NOT_RUN":
            self.assertFalse(a["S2_progress"]["validity_diagnostics_measured"])
        else:
            self.assertTrue(a["S2_progress"]["validity_diagnostics_measured"])
        self.assertIsNone(a["S2_progress"]["numeric_validity_thresholds"])
        self.assertIsNone(a["S2_progress"]["market_thresholds"])

    def test_broker_manifest_loads(self):
        self.assertEqual(broker.load_manifest()["profile"], PROFILE)


if __name__ == "__main__":
    unittest.main()
