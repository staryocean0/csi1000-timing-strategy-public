import ast,json,math,sys,unittest
from datetime import date,timedelta
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'executor'))
import wave_scale_reference_sampling_v1 as r
PROTOCOL=ROOT/'docs/research/TWO_WAVE_SCALE_REFERENCE_PROTOCOL_20260917.json'


def synthetic_days():
    out=[]
    d=date(2015,1,1)
    end=date(2020,12,31)
    while d<=end:
        if d.weekday()<5:
            out.append(d.isoformat())
        d+=timedelta(days=1)
    return out


def annotation(state='CURRENT_SCALE_SUPPORTED',reason='COHERENT_BROAD_TURN'):
    panel='a'*20
    review={'state':state,'reason':reason,'compatible_segmentations':[[[-80,-70]]]}
    return {'panel_id':panel,'pass_a':dict(review),'pass_b':dict(review),
            'final_state':state,'final_reason':reason,
            'future_audit':{'revealed_after_freeze':False,'retrospective_disagreement':None}}


class ReferenceSamplingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.days=synthetic_days();cls.rows=r.select_primary_days(cls.days)
        cls.protocol=json.loads(PROTOCOL.read_text())
    def test_exact_primary_sample_size_and_balance(self):
        self.assertEqual(len(self.rows),192)
        quarters={q:0 for q in {r.quarter_id(x) for x in self.days}}
        years={y:0 for y in r.YEARS}
        for row in self.rows:
            quarters[row['quarter']]+=1;years[int(row['quarter'][:4])]+=1
        self.assertEqual(set(quarters.values()),{8})
        self.assertEqual(set(years.values()),{32})

    def test_selection_is_input_order_invariant(self):
        self.assertEqual(self.rows,r.select_primary_days(list(reversed(self.days))))

    def test_anchor_and_panel_identity_are_deterministic(self):
        for row in self.rows:
            self.assertIn(row['anchor'],r.ANCHORS)
            self.assertEqual(row['anchor'],r.anchor_clock(row['day']))
            self.assertEqual(row['panel_id'],r.blind_id(row['day'],row['anchor']))
            self.assertRegex(row['panel_id'],r'^[0-9a-f]{20}$')

    def test_blinded_inventory_has_no_date_or_quarter(self):
        blind=r.blinded_inventory(self.rows)
        self.assertEqual(len(blind),192)
        payload=json.dumps(blind,sort_keys=True)
        for row in self.rows:
            self.assertNotIn(row['day'],payload);self.assertNotIn(row['quarter'],payload)
        self.assertEqual(set(blind[0]),{'panel_id','contexts_trading_minutes','future_audit_minutes'})

    def test_blinded_review_order_is_deterministic_and_not_source_order(self):
        a=r.blinded_inventory(self.rows);b=r.blinded_inventory(list(reversed(self.rows)))
        self.assertEqual(a,b)
        self.assertNotEqual([x['panel_id'] for x in a],[x['panel_id'] for x in self.rows])

    def test_shape_normalization_removes_amplitude_not_geometry(self):
        t=np.linspace(0,1,101)
        shape=np.where(t<=.5,2*t,2*(1-t))
        a=r.normalize_log_shape(np.exp(math.log(100)+.002*shape))
        b=r.normalize_log_shape(np.exp(math.log(100)+.05*shape))
        np.testing.assert_allclose(a['shape'],b['shape'],rtol=0,atol=1e-11)
        self.assertTrue(a['numeric_amplitude_hidden']);self.assertTrue(b['numeric_amplitude_hidden'])

    def test_exact_constant_shape_is_explicitly_degenerate(self):
        out=r.normalize_log_shape([100.]*10)
        self.assertTrue(out['shape_degenerate']);self.assertEqual(set(out['shape']),{0.0})

    def test_relative_axis_is_trailing_and_causal(self):
        self.assertEqual(r.relative_axis(5),[-4,-3,-2,-1,0])
        self.assertEqual(r.CONTEXT_MINUTES,(150,300));self.assertEqual(r.FUTURE_AUDIT_MINUTES,60)

    def test_bad_day_population_fails_closed(self):
        with self.assertRaises(ValueError):r.select_primary_days(self.days+[self.days[0]])
        without_2015q1=[x for x in self.days if not x.startswith(('2015-01','2015-02','2015-03'))]
        with self.assertRaises(ValueError):r.select_primary_days(without_2015q1)
        with self.assertRaises(ValueError):r.quarter_id('2021-01-04')

    def test_pass_B_can_confirm_or_downgrade_only(self):
        base=annotation();self.assertEqual(r.validate_annotation(base),base)
        down=annotation();down['pass_b']={'state':'AMBIGUOUS_MULTI_SCALE','reason':'MULTIPLE_COMPATIBLE_SEGMENTATIONS','compatible_segmentations':[]}
        down['final_state']='AMBIGUOUS_MULTI_SCALE';down['final_reason']='MULTIPLE_COMPATIBLE_SEGMENTATIONS'
        self.assertEqual(r.validate_annotation(down),down)
        bad=annotation('INSUFFICIENT_SUPPORT','INSUFFICIENT_GEOMETRIC_INFORMATION')
        bad['pass_b']={'state':'CURRENT_SCALE_SUPPORTED','reason':'COHERENT_BROAD_TURN','compatible_segmentations':[]}
        bad['final_state']='CURRENT_SCALE_SUPPORTED';bad['final_reason']='COHERENT_BROAD_TURN'
        with self.assertRaises(ValueError):r.validate_annotation(bad)

    def test_future_audit_cannot_exist_before_reveal(self):
        row=annotation();row['future_audit']['retrospective_disagreement']=True
        with self.assertRaises(ValueError):r.validate_annotation(row)
        row['future_audit']['revealed_after_freeze']=True
        self.assertEqual(r.validate_annotation(row),row)

    def test_turn_intervals_are_relative_and_bounded(self):
        row=annotation();row['pass_a']['compatible_segmentations']=[[[-299,-250],[-30,-20]]]
        row['pass_b']['compatible_segmentations']=[[[-299,-250],[-30,-20]]]
        self.assertEqual(r.validate_annotation(row),row)
        for bad in ([[[-301,-250]]],[[[-20,-30]]],[[[-20,1]]]):
            row=annotation();row['pass_a']['compatible_segmentations']=bad
            with self.assertRaises(ValueError):r.validate_annotation(row)

    def test_protocol_matches_frozen_source_constants(self):
        p=self.protocol
        self.assertEqual(p['primary_sample']['expected_panels'],192)
        self.assertEqual(p['primary_sample']['days_per_quarter'],r.PER_QUARTER)
        self.assertEqual(tuple(p['primary_sample']['anchors_shanghai']),r.ANCHORS)
        self.assertEqual(tuple(p['causal_context']['trailing_trading_minutes']),r.CONTEXT_MINUTES)
        self.assertEqual(tuple(p['reference_states']),r.REFERENCE_STATES)
        self.assertEqual(tuple(p['reason_codes']),r.REASON_CODES)

    def test_protocol_blocks_candidate_outcomes_and_threshold_selection(self):
        p=self.protocol
        for key in ('candidate_outputs_visible','diagnostic_scores_visible','PnL_or_outcomes_visible'):
            self.assertFalse(p['blind_packet'][key])
        self.assertFalse(p['failure_derived_audit_strata']['included_in_primary_sample'])
        self.assertFalse(p['failure_derived_audit_strata']['used_for_threshold_calibration'])
        self.assertFalse(p['post_reference_measurement']['threshold_selection_in_same_run'])
        self.assertIsNone(p['numeric_state_thresholds'])

    def test_source_has_no_detector_import_or_io(self):
        path=ROOT/'executor/wave_scale_reference_sampling_v1.py';text=path.read_text()
        self.assertNotIn('wave_scale_dominance_diagnostics',text)
        self.assertNotIn('wave_recognizer_r',text)
        tree=ast.parse(text);forbidden={'open','read_csv','read_parquet','write_text','write_bytes','urlopen','request','run','Popen','system','exec','eval'}
        for node in ast.walk(tree):
            if isinstance(node,ast.Call):
                name=getattr(node.func,'id',getattr(node.func,'attr',''))
                self.assertNotIn(name,forbidden,name)

if __name__=='__main__':unittest.main()
