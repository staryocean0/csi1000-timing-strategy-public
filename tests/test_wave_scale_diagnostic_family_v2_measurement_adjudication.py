import hashlib, json, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ADJ=ROOT/'docs/research/TWO_WAVE_SCALE_DIAGNOSTIC_FAMILY_V2_MEASUREMENT_ADJUDICATION_20260917.json'
LINEAGE=ROOT/'docs/research/TWO_WAVE_RESEARCH_LINEAGE_20260916.json'
AUTH=ROOT/'docs/research/TWO_WAVE_SEGMENTATION_DOMINANCE_THREAD_AUTHORITY_20260917.json'
RAW='a0b71c19591a83bf2ee7cc24eaecaea367d0d3b3772a0e41c03d7c361b5fa659'
RUN='35237394015-1'
PRIOR30='785e5e6179022bf483bb32b9b9386692c595c20f21e4978cc0017df34bf55ae6'
class Tests(unittest.TestCase):
 @classmethod
 def setUpClass(c):
  c.a=json.loads(ADJ.read_text()); c.l=json.loads(LINEAGE.read_text()); c.u=json.loads(AUTH.read_text())
 def test_identity(c):
  c.assertEqual(c.a['formal_run'],RUN); c.assertEqual(c.a['diagnostics_sha256'],RAW); c.assertEqual((c.a['panels'],c.a['phase_rows']),(192,960))
 def test_blind_scope(c):
  for k in ('reference_labels_visible_to_compute','reference_labels_joined','future_suffix_used','validity_state_assigned','morphology_state_assigned','ambiguity_region_selected','full_192_fit_performed','production_authority'): c.assertFalse(c.a[k])
  c.assertIsNone(c.a['numeric_thresholds'])
 def test_prior30(c):
  raw=json.dumps(c.l['ordered_lineage'][:30],sort_keys=True,separators=(',',':')).encode(); c.assertEqual(hashlib.sha256(raw).hexdigest(),PRIOR30)
 def test_order31(c):
  r=c.l['ordered_lineage'][30]; c.assertEqual((r['order'],r['formal_run'],r['diagnostics_sha256']),(31,RUN,RAW)); c.assertFalse(r['threshold_selected'])
 def test_authority(c):
  lane=next(x for x in c.u['active_lanes'] if x['issue']==353); s=c.u['S2_progress']; c.assertEqual(lane['status'],'DIAGNOSTIC_FAMILY_V2_MEASUREMENT_PASSED_CALIBRATION_SOURCE_NEXT'); c.assertTrue(s['diagnostic_family_v2_measured']); c.assertFalse(s['diagnostic_family_v2_labels_joined']); c.assertEqual(s['next'],'FREEZE_V2_CALIBRATION_SOURCE_BEFORE_ANY_LABEL_JOIN')
 def test_no_mapping(c):
  text=ADJ.read_text(); c.assertNotIn('panel_id',text); c.assertNotIn('reference_state',text)
if __name__=='__main__': unittest.main()
