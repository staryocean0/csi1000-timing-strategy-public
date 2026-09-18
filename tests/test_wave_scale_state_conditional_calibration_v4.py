import ast,copy,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'executor'))
import wave_scale_state_conditional_calibration_v4 as c

def validity(v=.1):
 return {'close_jump_concentration':v,'close_range_concentration':v,'local_jump_isolation_ratio':1+10*v}
def morph(x=.5,y=.5):
 return {'reversal_completion_ratio_median':x,'delta_search_adjusted_bic_vs_one_leg_median':-x,
         'post_turn_fraction_median':x,'turn_edge_distance_fraction_median':y,'one_leg_background_count':5-x}
def dom(nd=False):
 return {'tortuosity_median':8. if nd else 2.,'norm_rmse_median':.2 if nd else .05,
         'delta_bic_median':5. if nd else -30.,'sse_improvement_median':.1 if nd else .65}
def rec(pid,year,state,v=.1,x=.5,y=.5,nd=False):
 return {'panel_id':pid,'year':year,'reference_state':state,'validity':validity(v),'morphology':morph(x,y),'dominance':dom(nd)}
def rows():
 out=[]
 for y in c.YEARS:
  out += [rec(f'{y}s',y,c.SUPPORTED,.1,.9,.9),rec(f'{y}d',y,c.DEVELOPING,.1,.1,.1),
          rec(f'{y}a',y,c.AMBIGUOUS,.1,.50,.50),rec(f'{y}i',y,c.DATA_INVALID,.95,.5,.5),
          rec(f'{y}nt',y,c.NOT_DOMINANT,.1,.9,.9,True),rec(f'{y}nd',y,c.NOT_DOMINANT,.1,.1,.1,True)]
 return out
class V4Tests(unittest.TestCase):
 def test_validity_features_are_exact_stable_trio(self):
  self.assertEqual(set(c.STABLE_VALIDITY_DIRECTIONS),{'close_jump_concentration','close_range_concentration','local_jump_isolation_ratio'})
 def test_validity_rule_family_single_or_pair_or_only(self):
  rs=list(c._validity_candidates([r['validity'] for r in rows()]))
  self.assertTrue(rs);self.assertTrue(all(r['op'] in {'NULL','SINGLE','OR'} for r in rs))
  self.assertTrue(all(len(r['conditions'])<=2 for r in rs))
 def test_year_robust_false_invalid_cap(self):
  fit=c.fit_validity_guard(rows())
  for m in fit['metrics']['per_year'].values(): self.assertLessEqual(m['false_invalid_rate'],.05+1e-15)
 def test_explicit_ambiguity_axes_are_fixed(self):
  self.assertEqual(c.AMBIGUITY_AXES,('delta_search_adjusted_bic_vs_one_leg_median','turn_edge_distance_fraction_median'))
 def test_ambiguity_component_respects_five_percent_cap(self):
  fit=c.fit_explicit_ambiguity(rows())
  for f in fit['fits'].values():
   self.assertEqual(f['fit_status'],'FITTED');self.assertLessEqual(f['metrics']['false_ambiguous_rate'],.05+1e-15)
 def test_explicit_ambiguity_can_fire(self):
  fit=c.fit_explicit_ambiguity(rows()); a=next(r for r in rows() if r['reference_state']==c.AMBIGUOUS)
  self.assertTrue(c.predict_explicit_ambiguity(a,fit))
 def test_oof_each_panel_once_and_no_full_fit(self):
  out=c.fit_loyo_development(rows());self.assertEqual(len(out['predictions']),len(rows()))
  self.assertEqual(len({p['panel_id'] for p in out['predictions']}),len(rows()));self.assertFalse(out['full_192_fit_performed'])
 def test_heldout_values_do_not_change_heldout_fold(self):
  base=c.fit_loyo_development(rows()); changed=copy.deepcopy(rows())
  for r in changed:
   if r['year']==2018:r['validity']['close_jump_concentration']=999.;r['morphology']['turn_edge_distance_fraction_median']=999.
  alt=c.fit_loyo_development(changed)
  a=next(f for f in base['fold_models'] if f['held_year']==2018);b=next(f for f in alt['fold_models'] if f['held_year']==2018)
  self.assertEqual(a,b)
 def test_no_file_network_random_pandas(self):
  tree=ast.parse((ROOT/'executor/wave_scale_state_conditional_calibration_v4.py').read_text()); forbidden={'pathlib','os','socket','requests','urllib','random','pandas'}
  for n in ast.walk(tree):
   if isinstance(n,ast.Import):self.assertTrue(all(a.name.split('.')[0] not in forbidden for a in n.names))
   elif isinstance(n,ast.ImportFrom) and n.module:self.assertNotIn(n.module.split('.')[0],forbidden)
if __name__=='__main__':unittest.main()
