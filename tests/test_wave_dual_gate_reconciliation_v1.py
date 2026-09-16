"""Final pre-market reconciliation tests; synthetic evidence only."""
import sys
from pathlib import Path
import unittest
from unittest.mock import patch
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'executor'))
from wave_dual_gate_audit_v1 import economics,verify_probabilities,verify_trade_sequence
from wave_dual_gate_analysis_v1 import analyze,event_rows
from wave_dual_gate_hierarchy_v1 import base_inventory,hierarchy
from test_wave_dual_gate_integration_v1 import synthetic

class ReconciliationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bars=synthetic();cls.report,cls.ledgers=analyze(cls.bars)
    def test_formation_precedes_first_wave(self):
        by={w['wave_id']:i for i,w in enumerate(self.ledgers['base']['waves'])}
        for r in self.ledgers['events']:
            i=by[r['wave_id']];a=self.ledgers['base']['waves'][i-1]
            self.assertEqual(r['formation_cutoff_bar'],a['start_bar']-1)
    def test_coarser_parent_required(self):
        b=base_inventory(self.bars);h=hierarchy(b,2)
        fake=dict(period=1,direction='UP')
        with patch('wave_dual_gate_analysis_v1.parent_context',return_value=fake):
            rows,_=event_rows(self.bars,b,h)
        self.assertTrue(any(r['status']=='PARENT_NOT_COARSER' for r in rows))
        self.assertFalse(any(r['status']=='SETTLED' for r in rows))
    def test_calendar_cost_and_returns_conserved(self):
        o=np.exp(np.linspace(4.6,4.8,101));days=np.arange(101)
        g=np.log(o[85]/o[2])
        row=dict(entry_bar=2,exit_bar=85,selected=True,side=1,net_bps=g*10000-4,gross_log_return=g,duration=83)
        out=economics([row],o,days,8)
        self.assertAlmostEqual(out['baseline_net_bps'],row['net_bps'])
        self.assertAlmostEqual(out['filtered_net_bps'],row['net_bps'])
        self.assertTrue(out['cross_block_trades_preserved'])
        self.assertGreater(len(out['calendar_blocks']),1)
    def test_filtered_actual_adjacency_not_baseline_flags(self):
        o=np.array([100,99,98,99,100,99,98,99],float)
        rows=[]
        for en,ex,side,sel in [(0,1,1,True),(2,3,-1,False),(4,5,1,True)]:
            g=side*np.log(o[ex]/o[en])
            rows.append(dict(entry_bar=en,exit_bar=ex,side=side,selected=sel,duration=ex-en,gross_log_return=g,net_bps=g*10000-4))
        out=economics(rows,o,np.arange(len(o)),2)
        self.assertEqual(out['actual_filtered_adjacent_pairs'],1)
        self.assertEqual(out['actual_filtered_two_sided_fast_loss_rate'],0.)
    def test_independent_probabilities(self):
        n=verify_probabilities(self.ledgers['events'],self.ledgers['oof'])
        self.assertEqual(n,len(self.ledgers['oof']))
    def test_independent_trade_exits(self):
        self.assertEqual(verify_trade_sequence(self.bars,self.ledgers,self.report['T']),2*len(self.ledgers['trades']))
    def test_altered_exit_fails(self):
        import copy
        value=copy.deepcopy(self.ledgers);value['trades'][0]['exit_bar']+=1
        with self.assertRaises(ValueError):verify_trade_sequence(self.bars,value,self.report['T'])
    def test_calendar_economics_exists_both_settings(self):
        self.assertIn('calendar_economics',self.report['B'])
        self.assertIn('calendar_economics',self.report['B_min_leg_2_sensitivity'])

if __name__=='__main__':unittest.main()
