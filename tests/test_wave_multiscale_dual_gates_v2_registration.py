import json
from pathlib import Path
import sys,unittest,yaml
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'executor'))
class RegistrationV2Tests(unittest.TestCase):
    def test_manifest_matches_frozen_sources(self):
        from wave_multiscale_dual_gates_v2_broker import load_profile
        p=load_profile();self.assertTrue(p['new_training']);self.assertFalse(p['production_authority'])
    def test_standard_workflow_exact_profile(self):
        doc=yaml.load((ROOT/'.github/workflows/public-compute.yml').read_text(encoding='utf-8'),Loader=yaml.BaseLoader)
        self.assertEqual(set(doc['on']),{'workflow_dispatch'})
        opts=doc['on']['workflow_dispatch']['inputs']['profile']['options'];self.assertEqual(opts.count('two-wave-multiscale-dual-gates-v2'),1)
        steps=[s for s in doc['jobs']['execute']['steps'] if 'wave_multiscale_dual_gates_v2_broker.py' in s.get('run','')]
        self.assertEqual(len(steps),4)
        text=(ROOT/'.github/workflows/public-compute.yml').read_text(encoding='utf-8');self.assertEqual(text.count('secrets.FACTORLAB_PRIVATE_TOKEN'),2)
    def test_controller_exact_title(self):
        text=(ROOT/'.github/workflows/controller-dispatch.yml').read_text(encoding='utf-8')
        self.assertEqual(text.count("controller: two-wave-multiscale-dual-gates-v2"),2)
        self.assertIn("profile='two-wave-multiscale-dual-gates-v2'",text)
    def test_protocol_freezes_financial_translation(self):
        p=json.loads((ROOT/'docs/research/TWO_WAVE_MULTISCALE_DUAL_GATES_V2_PROTOCOL_20260916.json').read_text())
        self.assertFalse(p['mathematical_carrier']['target_period_bands_imposed']);self.assertFalse(p['mathematical_carrier']['FFT_or_linear_filter_used'])
        self.assertTrue(p['B']['period_ratio_2_to_3_is_not_a_filter_parameter']);self.assertFalse(p['authority']['trade_authority'])
if __name__=='__main__':unittest.main()
