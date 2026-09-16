"""Static standard-run registration and private readback boundaries."""
import json
from pathlib import Path
import sys
import unittest
import yaml
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'executor'))
class RegistrationTests(unittest.TestCase):
    def test_actual_source_manifest(self):
        from wave_dual_gate_broker_v1 import load_profile
        self.assertTrue(load_profile()['new_training'])
    def test_standard_workflow_exclusive_steps(self):
        doc=yaml.load((ROOT/'.github/workflows/public-compute.yml').read_text(encoding='utf-8'),Loader=yaml.BaseLoader)
        self.assertEqual(set(doc['on']),{'workflow_dispatch'})
        self.assertEqual(doc['on']['workflow_dispatch']['inputs']['profile']['options'].count('two-wave-dual-gates-v1'),1)
        steps=[s for s in doc['jobs']['execute']['steps'] if 'wave_dual_gate_broker_v1.py' in s.get('run','')]
        self.assertEqual(len(steps),4)
        for phase in ('prepare','compute','cleanup','publish'):
            step=next(s for s in steps if 'wave_dual_gate_broker_v1.py '+phase+' ' in s['run'])
            self.assertIn("elif [ '${{ inputs.profile }}' = 'two-wave-dual-gates-v1' ]; then",step['run'])
            if phase in ('compute','cleanup'):self.assertNotIn('env',step)
        self.assertEqual(sum('FACTORLAB_PRIVATE_TOKEN' in s.get('env',{}) for s in doc['jobs']['execute']['steps']),2)
    def test_protocol_market_scope(self):
        p=json.loads((ROOT/'executor/wave_dual_gate_protocol_v1.json').read_text())
        self.assertFalse(p['production_authority']);self.assertTrue(p['new_training'])
        self.assertEqual(p['data']['years'],[2015,2020]);self.assertFalse(p['market_results_seen_before_freeze'])
