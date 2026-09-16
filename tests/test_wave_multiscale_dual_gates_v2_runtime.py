import json
from pathlib import Path
import sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'executor'))
sys.path.insert(0,str(Path(__file__).resolve().parents[0]))
from test_wave_dual_gate_integration_v1 import synthetic
from wave_multiscale_dual_gates_v2 import analyze
from wave_multiscale_dual_gates_v2_entry import write_results
from wave_multiscale_dual_gates_v2_verifier import verify_results
from wave_multiscale_dual_gates_v2_runtime import validate,COMMAND,VERIFY

class MultiscaleV2RuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.bars=synthetic(3000);cls.report,cls.ledgers=analyze(cls.bars)
    def test_end_to_end_private_result_shape(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'study';write_results(out,self.report,self.ledgers);r=verify_results(self.bars,out)
            self.assertEqual(r['status'],'passed');self.assertGreater(r['independent']['prefixes'],0)
    def test_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'study';write_results(out,self.report,self.ledgers);(out/'report.json').write_text('{}')
            with self.assertRaises(ValueError):verify_results(self.bars,out)
    def test_runtime_exact_profile(self):
        p={'command':COMMAND,'verify_command':VERIFY,'command_timeout_seconds':900,'verification_timeout_seconds':900,'new_training':True,'production_authority':False};validate(p)
        for k,v in [('new_training',False),('production_authority',True),('command',['bad.py']),('command_timeout_seconds',901)]:
            q=dict(p);q[k]=v
            with self.assertRaises(ValueError):validate(q)
    def test_report_is_development_only(self):
        self.assertFalse(self.report['authority']['fresh_oos']);self.assertFalse(self.report['authority']['production'])
    def test_same_decomposition_drives_both_gates(self):
        self.assertIn('hierarchy',self.ledgers);self.assertGreater(len(self.ledgers['A_events']),0);self.assertGreater(len(self.ledgers['B_events']),0)
    def test_fidelity_precedes_acceptance(self):
        self.assertFalse(self.report['fidelity']['fidelity_A_pass']);self.assertFalse(self.report['A']['support_passed'])
        self.assertFalse(self.report['fidelity']['fidelity_B_pass']);self.assertFalse(self.report['B']['support_passed'])

if __name__=='__main__':unittest.main()
