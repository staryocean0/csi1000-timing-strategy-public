from __future__ import annotations
import json,py_compile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PROFILE='risk-v2-probability-reliability-output-contract-v1'
CONTRACT=ROOT/'docs/acceptance/risk_tool_v2/probability_reliability_output_contract_v1.json'
PREREG=ROOT/'docs/research/RISK_TOOL_V2_PROBABILITY_RELIABILITY_OUTPUT_CONTRACT_V1_PREREG_20260915.json'
PRODUCER=ROOT/'executor/risk_probability_reliability_output_contract_v1.py'
VERIFIER=ROOT/'executor/risk_probability_reliability_output_contract_v1_verifier.py'
BROKER=ROOT/'executor/risk_probability_reliability_output_contract_v1_broker.py'
MIRROR=ROOT/'executor/risk_probability_reliability_output_contract_v1_private_mirror.py'
WORKFLOW=ROOT/'.github/workflows/public-compute.yml';CONTROLLER=ROOT/'.github/workflows/controller-dispatch.yml'

class OutputContractTest(unittest.TestCase):
 def test_authority_inputs_and_no_rescue_are_frozen(self):
  p=json.loads(PREREG.read_text());self.assertEqual(p['inputs']['temporal_v3']['run'],'34930354449-1');self.assertEqual(p['inputs']['reliability']['run'],'34942554638-1');self.assertTrue(p['adjudication']['cannot_promote_15m_to_complete']);self.assertFalse(p['year_2026_read']);self.assertFalse(p['production_authority'])
 def test_band_thresholds_and_permissions_are_frozen(self):
  c=json.loads(CONTRACT.read_text());b=c['15m']['band_thresholds'];self.assertEqual(b['low_upper_exclusive'],0.5170330932673238);self.assertEqual(b['high_lower_inclusive'],0.7096666848299501)
  bands=c['15m']['bands'];self.assertEqual(list(bands),['UNSCORED','LOW','MID','HIGH']);self.assertEqual(bands['LOW']['absolute_probability_research_interpretation'],'not_authorized');self.assertFalse(bands['HIGH']['hard_probability_thresholding']);self.assertEqual(c['30m']['authority_state_must_equal'],'COMPLETE');self.assertFalse(c['global_prohibitions']['production_authority'])
 def test_sources_compile_and_verifier_is_independent(self):
  py_compile.compile(str(PRODUCER),doraise=True);py_compile.compile(str(VERIFIER),doraise=True);text=VERIFIER.read_text();self.assertNotIn('risk_probability_reliability_output_contract_v1 import',text)
 def test_broker_and_mirror_are_bounded(self):
  b=BROKER.read_text();m=MIRROR.read_text();self.assertIn('34930354449-1',b);self.assertIn('34942554638-1',b);self.assertIn('74df0b6b688d91f8f30c9dcdf3e16f9ddbe77204c9e702fe1d0476601ee3f5ca',b);self.assertIn('4993e226b4a5840d30b61dcc3aafd49b6996a38385c61a0acb2fe7bdd4e7a6d6',b);self.assertNotIn('parquet',b.lower());self.assertIn("FILES=('SUMMARY.json','OUTPUT_CONTRACT_RESULT.json','BAND_POLICY.csv')",m)
 def test_standard_route_registered(self):
  w=WORKFLOW.read_text();c=CONTROLLER.read_text();self.assertGreaterEqual(w.count(PROFILE),5);self.assertGreaterEqual(c.count(PROFILE),2);self.assertIn('risk_probability_reliability_output_contract_v1_broker.py',w);self.assertIn('risk_probability_reliability_output_contract_v1_private_mirror.py',w)

if __name__=='__main__':unittest.main()
