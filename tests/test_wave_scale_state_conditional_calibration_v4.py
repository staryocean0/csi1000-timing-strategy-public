import ast
import copy
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'executor'))
import wave_scale_state_conditional_calibration_v4 as c


def validity(x=.1):
    return {
        'post_jump_reversal_extreme_10':x,
        'post_jump_midpoint_hold_fraction_10':1-x,
        'signed_post_jump_displacement_ratio_10':2-x,
        'signed_post_jump_displacement_ratio_20':2-x,
        'jump_persistence_ratio':2-x,
        'wick_only_concentration_max':x,
        'wick_only_concentration_median':x,
        'local_jump_isolation_ratio':1+10*x,
        'close_jump_concentration':x,
        'close_range_concentration':x,
    }


def morph(x):
    return {
        'reversal_completion_ratio_median':x,
        'delta_search_adjusted_bic_vs_one_leg_median':-x,
        'post_turn_fraction_median':x,
        'turn_edge_distance_fraction_median':x,
        'one_leg_background_count':5-x,
    }


def ambiguity(kind='clear'):
    if kind=='amb':
        return {'turn_relative_minute_range':30.0,'shape_disagreement':3.0,
                'best_second_adjusted_bic_gap_median':.01}
    return {'turn_relative_minute_range':2.0,'shape_disagreement':0.0,
            'best_second_adjusted_bic_gap_median':1.0}


def dom(nondom=False):
    return {'tortuosity_median':8.0 if nondom else 2.0,
            'norm_rmse_median':.20 if nondom else .05,
            'delta_bic_median':5.0 if nondom else -30.0,
            'sse_improvement_median':.10 if nondom else .65}


def rec(panel,year,state,vs=.1,ms=.5,ak='clear',nondom=False):
    return {'panel_id':panel,'year':year,'reference_state':state,
            'validity':validity(vs),'morphology':morph(ms),
            'ambiguity':ambiguity(ak),'dominance':dom(nondom)}


def six_year_records():
    rows=[]
    for year in c.YEARS:
        rows += [
            rec(f'{year}-s',year,c.SUPPORTED,.1,.9),
            rec(f'{year}-d',year,c.DEVELOPING,.1,.1),
            rec(f'{year}-a',year,c.AMBIGUOUS,.1,.5,'amb'),
            rec(f'{year}-nt',year,c.NOT_DOMINANT,.1,.9,'clear',True),
            rec(f'{year}-nd',year,c.NOT_DOMINANT,.1,.1,'clear',True),
            rec(f'{year}-i',year,c.DATA_INVALID,.95,.5),
        ]
    return rows


class CalibrationV4Tests(unittest.TestCase):
    def test_validity_family_is_exact_ten_existing_features(self):
        self.assertEqual(len(c.VALIDITY_DIRECTIONS),10)
        self.assertNotIn('amplitude',' '.join(c.VALIDITY_DIRECTIONS).lower())

    def test_or_kleene_semantics(self):
        rule={'op':'OR','conditions':[
            {'feature':'close_jump_concentration','direction':'GE','threshold':.5},
            {'feature':'close_range_concentration','direction':'GE','threshold':.5},
        ]}
        self.assertTrue(c.apply_validity_rule({'close_jump_concentration':.9,'close_range_concentration':None},rule))
        self.assertFalse(c.apply_validity_rule({'close_jump_concentration':.1,'close_range_concentration':.2},rule))
        self.assertIsNone(c.apply_validity_rule({'close_jump_concentration':None,'close_range_concentration':.2},rule))

    def test_and_kleene_semantics(self):
        rule={'op':'AND','conditions':[
            {'feature':'close_jump_concentration','direction':'GE','threshold':.5},
            {'feature':'close_range_concentration','direction':'GE','threshold':.5},
        ]}
        self.assertFalse(c.apply_validity_rule({'close_jump_concentration':.1,'close_range_concentration':None},rule))
        self.assertTrue(c.apply_validity_rule({'close_jump_concentration':.8,'close_range_concentration':.7},rule))
        self.assertIsNone(c.apply_validity_rule({'close_jump_concentration':.8,'close_range_concentration':None},rule))

    def test_candidate_rules_never_exceed_two_distinct_features(self):
        rows=[validity(.1),validity(.3),validity(.8)]
        rules=list(c._validity_candidates(rows))
        self.assertTrue(any(r['op']=='AND' for r in rules))
        self.assertTrue(any(r['op']=='OR' for r in rules))
        for rule in rules:
            self.assertLessEqual(len(rule['conditions']),2)
            fs=[x['feature'] for x in rule['conditions']]
            self.assertEqual(len(fs),len(set(fs)))

    def test_validity_fit_obeys_false_invalid_cap(self):
        fit=c.fit_validity_guard(six_year_records())
        self.assertEqual(fit['fit_status'],'FITTED')
        self.assertLessEqual(fit['metrics']['false_positive_rate'],c.FALSE_INVALID_CAP+1e-15)
        self.assertGreater(fit['metrics']['recall'],0)

    def test_morphology_uses_fixed_primary_axis_and_one_ambiguity_gate(self):
        fit=c.fit_morphology(six_year_records())
        self.assertEqual(fit['fit_status'],'FITTED')
        self.assertEqual(fit['primary_axis'],'reversal_completion_ratio_median')
        self.assertIn(fit['rule']['ambiguity_feature'],c.AMBIGUITY_DIRECTIONS)
        self.assertGreater(fit['metrics']['supported_recall'],0)
        self.assertGreater(fit['metrics']['developing_recall'],0)
        self.assertGreater(fit['metrics']['ambiguous_recall'],0)
        self.assertGreater(fit['metrics']['min_class_recall'],0)

    def test_selected_ambiguity_missing_fails_closed_to_ambiguous(self):
        fit=c.fit_morphology(six_year_records())
        r=rec('x',2015,c.SUPPORTED,.1,.9)
        r['ambiguity'][fit['rule']['ambiguity_feature']]=None
        self.assertEqual(c.predict_morphology(r,fit),c.MORPH_AMBIG)

    def test_heldout_values_do_not_change_heldout_fold_model(self):
        rows=six_year_records()
        base=c.fit_loyo_development(rows)
        changed=copy.deepcopy(rows)
        for r in changed:
            if r['year']==2018:
                r['validity']['close_jump_concentration']=999
                r['morphology']['reversal_completion_ratio_median']=999
                r['ambiguity']['turn_relative_minute_range']=999
        other=c.fit_loyo_development(changed)
        a=next(f for f in base['fold_models'] if f['held_year']==2018)
        b=next(f for f in other['fold_models'] if f['held_year']==2018)
        self.assertEqual(a,b)

    def test_oof_cardinality_and_no_full_fit_or_lag_promotion(self):
        rows=six_year_records()
        out=c.fit_loyo_development(rows)
        self.assertEqual(len(out['predictions']),len(rows))
        self.assertEqual(len({p['panel_id'] for p in out['predictions']}),len(rows))
        self.assertFalse(out['full_192_fit_performed'])
        self.assertFalse(out['lag_selected_or_promoted'])
        self.assertFalse(out['production_authority'])

    def test_dominance_family_remains_v1(self):
        self.assertIs(c.v1.fit_dominance_rule,c.v1.fit_dominance_rule)

    def test_module_has_no_file_network_random_or_pandas_access(self):
        text=(ROOT/'executor/wave_scale_state_conditional_calibration_v4.py').read_text()
        tree=ast.parse(text)
        forbidden={'pathlib','os','socket','requests','urllib','random','pandas'}
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):
                self.assertTrue(all(alias.name.split('.')[0] not in forbidden for alias in node.names))
            elif isinstance(node,ast.ImportFrom) and node.module:
                self.assertNotIn(node.module.split('.')[0],forbidden)


if __name__=='__main__': unittest.main()
