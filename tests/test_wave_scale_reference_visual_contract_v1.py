import ast,json,math,sys,unittest
from datetime import date,timedelta
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'executor'))
import wave_scale_reference_sampling_v1 as s
import wave_scale_reference_verifier_v1 as v
import wave_scale_reference_visuals_v1 as g
PROTOCOL=ROOT/'docs/research/TWO_WAVE_SCALE_REFERENCE_PROTOCOL_20260917.json'


def days():
    out=[];d=date(2015,1,1);end=date(2020,12,31)
    while d<=end:
        if d.weekday()<5:out.append(d.isoformat())
        d+=timedelta(days=1)
    return out


def phases():
    out={}
    for offset in range(5):
        rows=[]
        for minute in range(-299+offset,-1,5):
            center=(minute+299)/299
            close=.5+.3*math.sin(math.pi*center)
            rows.append((minute,max(0.,close-.03),close,min(1.,close+.03)))
        out[f'offset{offset}']=rows
    return out


class ReferenceVisualContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.days=days();cls.full=s.select_primary_days(cls.days);cls.blind=s.blinded_inventory(cls.full)

    def test_independent_verifier_derives_same_sample(self):
        self.assertEqual(v.derive(self.days),self.full)
        result=v.verify_inventories(self.days,self.full,self.blind)
        self.assertEqual(result,{'status':'passed','panels':192,'quarters':24,'days_per_quarter':8})

    def test_inventory_tamper_fails(self):
        bad=[dict(x) for x in self.blind];bad[0]['future_audit_minutes']=61
        with self.assertRaises(ValueError):v.verify_inventories(self.days,self.full,bad)

    def test_shape_svg_is_deterministic_and_blind(self):
        panel=self.blind[0]['panel_id'];t=np.linspace(0,1,150)
        prices=np.exp(math.log(100)+.03*np.sin(math.pi*t))
        shape=s.normalize_log_shape(prices)['shape']
        a=g.render_shape_svg(panel,shape);b=g.render_shape_svg(panel,shape)
        self.assertEqual(a,b);self.assertTrue(v.verify_svg(a,panel,'shape'))
        self.assertNotIn('2020-',a);self.assertNotIn('0.03',a)

    def test_shape_svg_is_amplitude_invariant_after_normalization(self):
        panel=self.blind[1]['panel_id'];t=np.linspace(0,1,150);shape=np.sin(math.pi*t)
        a=s.normalize_log_shape(np.exp(math.log(100)+.002*shape))['shape']
        b=s.normalize_log_shape(np.exp(math.log(100)+.05*shape))['shape']
        self.assertEqual(g.render_shape_svg(panel,a),g.render_shape_svg(panel,b))

    def test_phase_svg_has_all_five_views_and_no_calendar_identity(self):
        panel=self.blind[2]['panel_id'];svg=g.render_phase_svg(panel,phases())
        self.assertTrue(v.verify_svg(svg,panel,'phase'))
        for offset in range(5):self.assertIn(f'offset{offset}',svg)
        self.assertNotRegex(svg,r'20\d{2}-\d{2}-\d{2}')

    def test_embedded_calendar_date_is_rejected_by_verifier(self):
        panel=self.blind[3]['panel_id']
        svg=f'<svg><text>{panel} 2020-12-31</text></svg>'
        with self.assertRaises(ValueError):v.verify_svg(svg,panel,'shape')

    def test_invalid_phase_contract_fails_closed(self):
        panel=self.blind[3]['panel_id'];p=phases();del p['offset4']
        with self.assertRaises(ValueError):g.render_phase_svg(panel,p)
        p=phases();p['offset0'][0]=(-299,.8,.5,.7)
        with self.assertRaises(ValueError):g.render_phase_svg(panel,p)

    def test_protocol_independently_verifies(self):
        protocol=json.loads(PROTOCOL.read_text())
        self.assertTrue(v.verify_protocol(protocol)['candidate_independent'])
        bad=json.loads(PROTOCOL.read_text());bad['numeric_state_thresholds']=.5
        with self.assertRaises(ValueError):v.verify_protocol(bad)

    def test_verifier_does_not_import_sampler_or_diagnostic(self):
        text=(ROOT/'executor/wave_scale_reference_verifier_v1.py').read_text()
        self.assertNotIn('wave_scale_reference_sampling_v1',text)
        self.assertNotIn('wave_scale_dominance_diagnostics',text)

    def test_visual_and_verifier_modules_have_no_file_network_process_io(self):
        forbidden={'open','read_csv','read_parquet','write_text','write_bytes','urlopen','request','run','Popen','system','exec','eval'}
        for name in ('wave_scale_reference_visuals_v1.py','wave_scale_reference_verifier_v1.py'):
            tree=ast.parse((ROOT/'executor'/name).read_text())
            for node in ast.walk(tree):
                if isinstance(node,ast.Call):
                    called=getattr(node.func,'id',getattr(node.func,'attr',''))
                    self.assertNotIn(called,forbidden,(name,called))

    def test_primary_packet_never_contains_failure_strata(self):
        text=json.dumps(self.blind).lower()
        for token in ('r3','r2','r1','residual','gap','blindspot'):
            self.assertNotIn(token,text)

if __name__=='__main__':unittest.main()
