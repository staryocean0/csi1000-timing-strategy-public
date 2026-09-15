import ast
import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "executor" / "ols_maxdd_reentry_identification_v1_profile.json"
PRODUCER = ROOT / "executor" / "ols_maxdd_reentry_identification_v1.py"
VERIFIER = ROOT / "executor" / "ols_maxdd_reentry_identification_v1_verifier.py"
BROKER = ROOT / "executor" / "ols_maxdd_reentry_identification_v1_broker.py"
WORKFLOW = ROOT / ".github" / "workflows" / "public-compute.yml"
CONTROLLER = ROOT / ".github" / "workflows" / "controller-dispatch.yml"
EXPECTED_SHA = "2b4b8e43a70f521cbd9909470084ce1a6940b2e9db5fac834fcb37aa7c7cd93c"
PROFILE_NAME = "ols-maxdd-reentry-identification-v1"


class OlsMaxddPhaseBTests(unittest.TestCase):
    def test_profile_is_frozen_and_nonproduction(self):
        raw = PROFILE.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), EXPECTED_SHA)
        p = json.loads(raw.decode())
        self.assertEqual(p["schema_id"], "ols_maxdd_reentry_identification_profile@1.0")
        self.assertEqual(p["phase_a_authoritative_run"], "34978764073-1")
        self.assertFalse(p["production_authority"])
        self.assertFalse(p["optimization_performed"])
        self.assertFalse(p["parameter_search_performed"])
        self.assertFalse(p["phase_c_authority_pre_result"])
        self.assertEqual(p["promotion_gate"]["min_family_expected_rho"], 0.25)
        self.assertEqual(p["promotion_gate"]["min_families_rho_pass"], 3)
        self.assertEqual(p["promotion_gate"]["min_families_positive_sign"], 4)
        self.assertEqual(p["promotion_gate"]["min_median_family_auc"], 0.60)
        self.assertEqual(p["promotion_gate"]["min_family_year_positive_fraction"], 0.70)

    def test_sources_parse_and_lock_causal_semantics(self):
        for path in (PRODUCER, VERIFIER, BROKER):
            ast.parse(path.read_text(encoding="utf-8"))
        text = PRODUCER.read_text(encoding="utf-8")
        self.assertIn("decision_i = start - 1", text)
        self.assertIn('"underwater_reentry"', text)
        self.assertIn('"future_drawdown_extension"', text)
        self.assertIn('"false_confidence_r2"', text)
        self.assertIn('"churn_damage_r2"', text)
        self.assertIn('"phase_c_authority"', text)
        self.assertNotIn("overlay", text.lower())
        verifier = VERIFIER.read_text(encoding="utf-8")
        self.assertIn('"status": "passed"', verifier)
        self.assertIn("underwater_reentry", verifier)

    def test_broker_is_bounded_and_does_not_mirror_row_level_table(self):
        text = BROKER.read_text(encoding="utf-8")
        self.assertIn("PROFILE_SHA256 = \"" + EXPECTED_SHA + "\"", text)
        self.assertIn("candidate_summary.csv", text)
        self.assertIn("year_stability.csv", text)
        self.assertNotIn('"study/segment_entry_table.csv"', text)
        self.assertIn("256 * 1024", text)

    def test_standard_route_is_exact(self):
        wf = WORKFLOW.read_text(encoding="utf-8")
        ctl = CONTROLLER.read_text(encoding="utf-8")
        self.assertEqual(wf.count("          - " + PROFILE_NAME), 1)
        self.assertGreaterEqual(wf.count("inputs.profile == '" + PROFILE_NAME + "'"), 2)
        for phase in ("prepare", "compute", "cleanup", "publish"):
            self.assertIn("ols_maxdd_reentry_identification_v1_broker.py " + phase + " " + PROFILE_NAME, wf)
        self.assertIn("controller: " + PROFILE_NAME, ctl)
        self.assertIn("profile='" + PROFILE_NAME + "'", ctl)
        self.assertEqual(wf.count("secrets.FACTORLAB_PRIVATE_TOKEN"), 2)


if __name__ == "__main__":
    unittest.main()
