import json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];PROFILE='risk-v2-15m-probability-validity-guard-v1';P=json.loads((ROOT/'docs/research/RISK_TOOL_V2_15M_PROBABILITY_VALIDITY_GUARD_V1_PREREG_20260915.json').read_text())
class GuardTest(unittest.TestCase):
    def test_parent_and_scope_frozen(self):
        self.assertEqual(P['parent_authority']['run'],'34926868278-1');self.assertEqual(P['parent_authority']['sha256'],'455a0f0d61993a933016e111aa1386eaf4ddf3ec6aeb9e28c109f08a559fd060');self.assertFalse(P['scope']['year_2026_read'])
    def test_guard_is_pit_and_antitrivial(self):
        self.assertTrue(P['guard_rule']['history_uses_only_prior_completed_evaluable_endpoints']);self.assertTrue(P['guard_rule']['current_endpoint_metrics_forbidden']);self.assertEqual(P['anti_trivial_abstention_gate']['probability_mode_coverage_min'],.70);self.assertEqual(P['anti_trivial_abstention_gate']['minimum_hard_year_probability_mode_coverage_min'],.50)
    def test_candidate_family_and_audit_split_frozen(self):
        self.assertEqual([x['id'] for x in P['candidate_family']],['control','g4','g8','g13']);self.assertEqual(P['scope']['repeat_audit_years'],[2024,2025]);self.assertTrue(P['selection']['uses_only_selection_years'])
    def test_non_rescue(self):
        self.assertTrue(all(P['prohibitions'].values()));self.assertTrue(P['interpretation']['current_v3_authority_immutable']);self.assertTrue(P['interpretation']['failed_guard_cannot_promote_15m'])
    def test_sources_compile_and_verifier_independent(self):
        prod=(ROOT/'executor/risk_probability_validity_guard_v1.py').read_text();ver=(ROOT/'executor/risk_probability_validity_guard_v1_verifier.py').read_text();compile(prod,'producer','exec');compile(ver,'verifier','exec');self.assertNotIn('risk_probability_validity_guard_v1.py',ver);self.assertNotIn('2026.parquet',prod+ver)
    def test_broker_and_mirror_bounded(self):
        b=(ROOT/'executor/risk_probability_validity_guard_v1_broker.py').read_text();m=(ROOT/'executor/risk_probability_validity_guard_v1_private_mirror.py').read_text();self.assertIn('PARENT_BYTES=170908',b);self.assertIn("PARENT_BLOB='478f73c1fb9ac9c91d670e67733623e1450da953'",b);self.assertNotIn('parquet',b.lower()+m.lower())
    def test_standard_route_registered(self):
        w=(ROOT/'.github/workflows/public-compute.yml').read_text();c=(ROOT/'.github/workflows/controller-dispatch.yml').read_text();self.assertIn(PROFILE,w);self.assertIn('controller: '+PROFILE,c)
if __name__=='__main__':unittest.main()
