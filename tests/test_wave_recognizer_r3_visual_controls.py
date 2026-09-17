"""Pre-real evidence completeness: component-leg floors, not total wave duration."""
from pathlib import Path
import sys,tempfile,unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'executor'))
from wave_recognizer_r3_v1 import analyze
from wave_recognizer_r3_v1_entry import write_results
from wave_recognizer_r3_v1_verifier import verify
from wave_recognizer_r3_v1_visuals import _r2_floor_cases,write_pack

def wave(key,start,up,down):
 return dict(wave_id=key,start_bar=start,high_bar=start+up,end_bar=start+up+down,duration=up+down)

class R3VisualControlTests(unittest.TestCase):
 def test_two_four_bar_legs_select_full_eight_bar_wave(self):
  selected=_r2_floor_cases({'waves':[wave('synthetic-eight',10,4,4)]})
  self.assertEqual(len(selected),1)
  self.assertEqual(selected[0]['up_leg_bars'],4)
  self.assertEqual(selected[0]['down_leg_bars'],4)
  self.assertEqual(selected[0]['kind'],'R2_MIN_LEG_LEG_CONTROL')

 def test_either_component_leg_floor_but_not_longer_legs(self):
  rows=[wave('up-floor',10,4,20),wave('down-floor',40,18,4),wave('no-floor',70,5,5)]
  selected=_r2_floor_cases({'waves':rows})
  self.assertEqual({r['wave_id'] for r in selected},{'up-floor','down-floor'})

 def test_deterministic_bounded_selection_ignores_input_order(self):
  rows=[wave(str(i),i*20,4,8) for i in range(20)]
  forward=_r2_floor_cases({'waves':rows});reverse=_r2_floor_cases({'waves':list(reversed(rows))})
  self.assertEqual(forward,reverse);self.assertEqual(len(forward),8)
  self.assertEqual([r['id'] for r in forward],sorted(r['id'] for r in forward))

 def test_independent_verifier_rejects_jointly_empty_plan_and_pack(self):
  c=np.tile(np.array([100.,101.,102.,103.,104.,103.,102.,101.]),80)
  bars=pd.DataFrame(dict(timestamp=pd.date_range('2015-01-05 09:35',periods=len(c),freq='5min'),open=c,high=c*1.0005,low=c*.9995,close=c))
  report,candidate,base,r1,r2=analyze(bars)
  self.assertTrue(_r2_floor_cases(r2),'fixture must contain genuine component-floor waves')
  with tempfile.TemporaryDirectory() as d:
   out=Path(d)/'study';write_results(out,report)
   # Mimic the historical silent omission in BOTH renderer and plan. The
   # independently derived component-leg requirement must still reject it.
   with patch('wave_recognizer_r3_v1_visuals._r2_floor_cases',return_value=[]):
    write_pack(out/'visuals',bars,candidate,base,r2)
    with self.assertRaisesRegex(ValueError,'missing R2 component-leg control'):verify(bars,out)

if __name__=='__main__':unittest.main()
