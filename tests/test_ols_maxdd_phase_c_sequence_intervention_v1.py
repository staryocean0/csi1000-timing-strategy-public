import ast
import hashlib
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PROFILE=ROOT/"executor"/"ols_maxdd_phase_c_sequence_intervention_v1_profile.json"
ENGINE=ROOT/"executor"/"ols_maxdd_phase_c_sequence_intervention_v1.py"
VERIFIER=ROOT/"executor"/"ols_maxdd_phase_c_sequence_intervention_v1_verifier.py"
BROKER=ROOT/"executor"/"ols_maxdd_phase_c_sequence_intervention_v1_broker.py"
PROTOCOL=ROOT/"docs"/"research"/"layer3"/"ols_family"/"OLS_MAXDD_PHASE_C_SEQUENCE_INTERVENTION_PROTOCOL_20260916.md"
WORKFLOW=ROOT/".github"/"workflows"/"ols-maxdd-phase-c-sequence-intervention-v1.yml"
CONTROLLER=ROOT/".github"/"workflows"/"ols-maxdd-phase-c-sequence-intervention-v1-controller.yml"
EXPECTED_SHA="54ecb5c86a94ef931cc89770dbe9432cf7d7e0cd29baf601d2b98d5195920414"

class PhaseCContractTest(unittest.TestCase):
    def test_profile_identity_and_frozen_variants(self):
        raw=PROFILE.read_bytes(); self.assertEqual(hashlib.sha256(raw).hexdigest(),EXPECTED_SHA); p=json.loads(raw.decode())
        self.assertEqual(p["pe_collapse_trigger"],0.3); self.assertEqual(len(p["primary_variants"]),9)
        self.assertFalse(p["optimization_performed"]); self.assertFalse(p["parameter_search_performed"]); self.assertFalse(p["phase_d_authority_pre_result"]); self.assertFalse(p["production_authority"])
        self.assertEqual(p["decision_gate"]["min_maxdd_improvement"],0.2); self.assertEqual(p["decision_gate"]["min_return_retention"],0.8)
    def test_protocol_is_preregistered_and_maxdd_first(self):
        t=PROTOCOL.read_text(encoding="utf-8"); self.assertIn("PREREGISTERED BEFORE INTERVENTION OUTCOME REVEAL",t); self.assertIn("seq_pe_collapse_burden >= 0.30",t); self.assertIn("relative MaxDD depth improvement >= 20%",t); self.assertIn("gross-return retention >= 80%",t); self.assertIn("No same-run threshold",t)
    def test_engine_and_verifier_contract(self):
        e=ENGINE.read_text(encoding="utf-8"); v=VERIFIER.read_text(encoding="utf-8"); b=BROKER.read_text(encoding="utf-8"); ast.parse(e); ast.parse(v); ast.parse(b)
        self.assertIn("PE_TRIGGER = 0.30",e); self.assertIn("half_next_segment",e); self.assertIn("block_next_segment",e); self.assertIn("block_until_baseline_recovery",e); self.assertIn("phase_d_authority",e)
        self.assertIn(EXPECTED_SHA,b); self.assertIn('"status":"passed"',v.replace(" ","")); self.assertIn("phase_d_authority",v)
    def test_bounded_executor_security_envelope(self):
        w=WORKFLOW.read_text(encoding="utf-8"); c=CONTROLLER.read_text(encoding="utf-8")
        self.assertIn("group: csi1000-standard-executor",w); self.assertIn("environment: private-research",w); self.assertIn("persist-credentials: false",w); self.assertEqual(w.count("secrets.FACTORLAB_PRIVATE_TOKEN"),2); self.assertIn("Compute without private credentials",w); self.assertIn("Stop owned container before credentials return",w)
        self.assertIn("github.event.issue.user.login == github.repository_owner",c); self.assertIn("controller: ols-maxdd-phase-c-sequence-intervention-v1",c)

if __name__=="__main__": unittest.main()
