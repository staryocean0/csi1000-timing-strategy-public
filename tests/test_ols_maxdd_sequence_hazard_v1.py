import ast
import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "executor" / "ols_maxdd_sequence_hazard_v1_profile.json"
ENGINE = ROOT / "executor" / "ols_maxdd_sequence_hazard_v1.py"
VERIFIER = ROOT / "executor" / "ols_maxdd_sequence_hazard_v1_verifier.py"
BROKER = ROOT / "executor" / "ols_maxdd_sequence_hazard_v1_broker.py"
PROTOCOL = ROOT / "docs" / "research" / "layer3" / "ols_family" / "OLS_MAXDD_SEQUENCE_HAZARD_V1_PROTOCOL_20260916.md"
WORKFLOW = ROOT / ".github" / "workflows" / "ols-maxdd-sequence-hazard-v1.yml"
CONTROLLER = ROOT / ".github" / "workflows" / "ols-maxdd-sequence-hazard-v1-controller.yml"
EXPECTED_SHA = "71fe62797e9ec9f9f106e313b1adcbd5424915c9ed9d51ceb0a06319c8bf4282"


class SequenceHazardContractTest(unittest.TestCase):
    def test_profile_identity_and_no_authority(self):
        raw = PROFILE.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), EXPECTED_SHA)
        p = json.loads(raw.decode("utf-8"))
        self.assertEqual(p["primary_sequence_length"], 2)
        self.assertEqual(p["sensitivity_sequence_length"], 3)
        self.assertFalse(p["phase_c_reopen_authority_pre_result"])
        self.assertFalse(p["optimization_performed"])
        self.assertFalse(p["parameter_search_performed"])
        self.assertFalse(p["production_authority"])
        self.assertEqual(p["promotion_gate"]["min_family_expected_rho"], 0.25)
        self.assertEqual(p["promotion_gate"]["min_median_family_auc"], 0.6)

    def test_engine_freezes_episode_causal_unit_and_candidates(self):
        text = ENGINE.read_text(encoding="utf-8")
        ast.parse(text)
        self.assertIn('PRIMARY_SEQUENCE_LENGTH = 2', text)
        self.assertIn('SENSITIVITY_SEQUENCE_LENGTH = 3', text)
        self.assertIn('one_checkpoint_per_recovered_drawdown_episode', text)
        self.assertIn('remaining_episode_drawdown_extension', text)
        for name in ("seq_loss_burden","seq_mae_burden","seq_r2_collapse_burden","seq_pe_collapse_burden","seq_loss_acceleration","seq_r2_collapse_acceleration","seq_pe_collapse_acceleration","seq_participation_density","seq_direction_flip"):
            self.assertIn(name, text)
        self.assertNotIn("sklearn", text)
        self.assertNotIn("optuna", text)

    def test_protocol_and_gate_are_preregistered(self):
        text = PROTOCOL.read_text(encoding="utf-8")
        self.assertIn("PREREGISTERED BEFORE OUTCOME REVEAL", text)
        self.assertIn("one primary row", text)
        self.assertIn("rho >= 0.25 in at least 3 of 5", text)
        self.assertIn("median family AUC >= 0.60", text)
        self.assertIn("three-segment sensitivity", text)
        self.assertIn("must not search sequence lengths", text)

    def test_broker_and_verifier_contract(self):
        broker = BROKER.read_text(encoding="utf-8")
        verifier = VERIFIER.read_text(encoding="utf-8")
        ast.parse(broker); ast.parse(verifier)
        self.assertIn(EXPECTED_SHA, broker)
        self.assertIn('ols-maxdd-sequence-hazard-v1', broker)
        self.assertIn('ols-maxdd-sequence', broker)
        self.assertNotIn('episode_checkpoint_table.csv', broker)
        for name in ("RESULTS.json","candidate_summary.csv","year_stability.csv","seq3_sensitivity.csv","RESULTS.md"):
            self.assertIn(name, broker)
        self.assertIn('"status":"passed"', verifier.replace(" ", ""))
        self.assertIn('phase_c_reopen_authority', verifier)

    def test_bounded_executor_matches_standard_security_envelope(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        controller = CONTROLLER.read_text(encoding="utf-8")
        self.assertIn("group: csi1000-standard-executor", workflow)
        self.assertIn("environment: private-research", workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertEqual(workflow.count("secrets.FACTORLAB_PRIVATE_TOKEN"), 2)
        self.assertIn("Compute without private credentials", workflow)
        self.assertIn("Stop owned container before credentials return", workflow)
        self.assertIn("github.event.issue.user.login == github.repository_owner", controller)
        self.assertIn("controller: ols-maxdd-sequence-hazard-v1", controller)
        self.assertIn("actions: write", controller)


if __name__ == "__main__":
    unittest.main()
