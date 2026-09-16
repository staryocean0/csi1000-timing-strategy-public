"""Synthetic-only integration and negative tests. No market file/network access."""
from pathlib import Path
import sys
import tempfile
import unittest
import importlib.util
import json
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'executor'))
from wave_dual_gate_hierarchy_v1 import pivot_stream,base_inventory,hierarchy,shape,background,geometry
from wave_dual_gate_analysis_v1 import analyze,block_sample,inference_blocks,interval,entry_signals,gate_a,mechanism_adjusted
from wave_dual_gate_study_v1 import encode,write_results,load_market
from wave_dual_gate_verifier_v1 import verify_results,verify_original_kernels


def synthetic(n=3000):
    t=np.arange(n);rng=np.random.default_rng(20260916)
    p=np.exp(4.6+.008*np.sin(2*np.pi*t/16)+.01*np.sin(2*np.pi*t/45)+.03*np.sin(2*np.pi*t/150)+.03*np.sin(2*np.pi*t/550)+np.cumsum(rng.normal(0,.0003,n)))
    dates=[]
    for y in range(2015,2021):dates.extend(pd.date_range(f'{y}-01-05 09:35',periods=n//6,freq='5min'))
    return pd.DataFrame(dict(timestamp=dates,open=p,high=p*1.0002,low=p*.9998,close=p))


class HierarchyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.bars=synthetic();cls.base=base_inventory(cls.bars)

    def test_pivots_prefix_invariant(self):
        for t in (100,499,901,1600):
            prefix=base_inventory(self.bars.iloc[:t+1])
            expected=[p for p in self.base['pivots'] if p['known_from_bar']<=t]
            self.assertEqual(prefix['pivots'],expected)

    def test_ohlc_anchors_not_replaced_by_close(self):
        w=self.base['waves'][0]
        self.assertEqual(w['start_low'],self.bars.low.iloc[w['start_bar']])
        self.assertEqual(w['high'],self.bars.high.iloc[w['high_bar']])
        self.assertNotEqual(w['high'],self.bars.close.iloc[w['high_bar']])

    def test_shape_uses_frozen_height(self):
        w=self.base['waves'][0];f=shape(self.bars,w)
        phase=.5;p=np.log(self.bars.close.iloc[w['start_bar']:w['end_bar']+1].to_numpy())
        expected=(np.interp(.5,np.linspace(0,1,len(p)),p)-(.5*np.log(w['start_low'])+.5*np.log(w['end_low'])))/w['height_log']
        self.assertAlmostEqual(f['residual_q50'],expected)

    def test_shape_does_not_read_suffix(self):
        w=self.base['waves'][2];a=shape(self.bars,w)
        b=self.bars.copy();b.loc[w['known_from_bar']+1:,'close']=999999
        self.assertEqual(a,shape(b,w))

    def test_background_prefix_invariant(self):
        whole=hierarchy(self.base,1)
        for t in (500,800,1100,1800,2500):
            p=self.bars.iloc[:t+1];b=base_inventory(p);h=hierarchy(b,1)
            self.assertEqual(background(self.base,whole,self.bars.close.to_numpy(),t,16),background(b,h,p.close.to_numpy(),t,16))

    def test_source_node_delay_not_lost(self):
        for r in self.base['roots']:
            for p in r['nodes']:self.assertGreater(p['known_from_bar'],p['occurrence_bar'])

    def test_two_node_minimum_cannot_emit_two_interval_wave(self):
        nodes=[dict(index=i,occurrence_bar=i*16,known_from_bar=i*16+4,price=float(v)) for i,v in enumerate([100,103,100,103,100,103,100,103,100])]
        one,_=pivot_stream(nodes,1,24);two,_=pivot_stream(nodes,2,24)
        self.assertGreater(len(one),len(two))

    def test_invalid_ohlc_rejected(self):
        b=self.bars.copy();b.loc[0,'low']=b.loc[0,'high']+1
        with self.assertRaises(ValueError):base_inventory(b)

    def test_lookahead_node_rejected(self):
        with self.assertRaises(ValueError):pivot_stream([dict(index=0,occurrence_bar=4,known_from_bar=2,price=1.)])

    def test_duplicate_node_rejected(self):
        p=dict(index=0,occurrence_bar=0,known_from_bar=2,price=100.)
        with self.assertRaises(ValueError):pivot_stream([p,p])

    def test_reconstruction_when_resolved_or_stale_not_fabricated(self):
        h=hierarchy(self.base,1)
        for t in range(500,3000,20):
            out=background(self.base,h,self.bars.close.to_numpy(),t,2000)
            if 'reconstruction_error' in out:self.assertLess(out['reconstruction_error'],1e-12)
            if out['status']=='RESOLVED':self.assertLessEqual(out['period'],out['support_end']-out['support_start'])


class StatisticalTests(unittest.TestCase):
    def test_continuous_chain_merges_original_blocks(self):
        rows=[dict(decision_bar=i,mature_bar=i+1) for i in range(99)]
        self.assertEqual(len(set(inference_blocks(rows,np.arange(100)))),1)

    def test_boundary_purge_does_not_merge_entire_chain(self):
        rows=[dict(decision_bar=i,mature_bar=i+1) for i in range(99)]
        kept,blocks=block_sample(rows,np.arange(100))
        self.assertEqual(len(set(blocks)),5);self.assertEqual(len(kept),95);self.assertEqual(len(rows),99)

    def test_parent_groups_crossing_blocks_removed(self):
        rows=[dict(decision_bar=5,mature_bar=7,parent_id='x'),dict(decision_bar=21,mature_bar=25,parent_id='x'),dict(decision_bar=30,mature_bar=31,parent_id='y')]
        kept,_=block_sample(rows,np.arange(50));self.assertEqual(kept,rows[-1:])

    def test_insufficient_blocks_never_retains(self):
        self.assertIsNone(interval([1]*29,[str(i) for i in range(29)])['interval'])

    def test_block_interval_direction(self):
        out=interval([1]*30,[str(i) for i in range(30)])
        self.assertEqual(out['interval'],[1.,1.])

    def test_unclosed_entry_still_in_training_opportunities(self):
        out=entry_signals(np.arange(100.,120.),4)
        self.assertEqual(out,[(4,1)])

    def test_future_prefix_does_not_change_past_entry_decisions(self):
        p=synthetic().close.to_numpy();a=entry_signals(p[:500],16);b=entry_signals(p,16)
        self.assertEqual(a,[(t,s) for t,s in b if t<500])

    def test_no_common_mechanism_support_not_a_negative_result(self):
        result=mechanism_adjusted([],[])
        self.assertEqual(result['status'],'INSUFFICIENT_COMMON_SUPPORT')

    def test_empty_A_is_inconclusive(self):
        out,rows=gate_a([],np.arange(100));self.assertEqual(out['verdict'],'INCONCLUSIVE');self.assertFalse(rows)


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bars=synthetic();cls.report,cls.ledgers=analyze(cls.bars)

    def test_both_gates_and_sensitivity_delivered(self):
        self.assertTrue({'A','B','B_min_leg_2_sensitivity'}.issubset(self.report))
        self.assertEqual(self.report['counts']['base_waves'],168)
        self.assertEqual(self.report['T'],16)

    def test_nonfinite_values_become_null_not_invalid_json(self):
        self.assertEqual(json.loads(encode({'x':np.nan,'y':np.int64(2)})),{'x':None,'y':2})

    def test_training_metadata_honest(self):
        self.assertTrue(self.report['new_training']);self.assertFalse(self.report['authority']['production'])

    def test_no_statistical_support_stays_inconclusive(self):
        self.assertEqual(self.report['A']['verdict'],'INCONCLUSIVE');self.assertEqual(self.report['B']['verdict'],'INCONCLUSIVE')

    def test_reproducible_report(self):
        report,ledgers=analyze(self.bars)
        self.assertEqual(encode(report),encode(self.report));self.assertEqual(encode(ledgers),encode(self.ledgers))

    def test_verified_synthetic_end_to_end(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'study';write_results(out,self.report,self.ledgers)
            result=verify_results(self.bars,out,check_original=False)
            self.assertEqual(result['status'],'passed');self.assertGreater(result['prefixes_checked'],0)

    def test_tampered_results_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'study';write_results(out,self.report,self.ledgers)
            (out/'report.json').write_text('{}')
            with self.assertRaises(ValueError):verify_results(self.bars,out,check_original=False)

    def test_output_directory_not_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):write_results(Path(d),self.report,self.ledgers)

    def test_wrong_carrier_path_rejected_before_loading(self):
        with tempfile.TemporaryDirectory() as d:
            # Import of frozen loader occurs first; available in full runner only.
            if importlib.util.find_spec('two_wave_v0800_scale_map'):
                with self.assertRaises(ValueError):load_market(d)
            else:self.skipTest('frozen market loader not mounted in this source-only environment')

    @unittest.skipUnless(importlib.util.find_spec('two_wave_v0800_scale_map') and importlib.util.find_spec('wave_skeleton_context_v1'),'full original public modules required; enforced by market verifier')
    def test_original_kernel_differential(self):
        out=verify_original_kernels(self.bars,self.ledgers)
        self.assertEqual(out['base_waves_checked'],168)


class ExecutionBoundaryTests(unittest.TestCase):
    def test_fixed_runtime_scope(self):
        from wave_dual_gate_runtime_v1 import validate,COMMAND,VERIFY
        p=dict(command=COMMAND,verify_command=VERIFY,command_timeout_seconds=900,verification_timeout_seconds=900,new_training=True,production_authority=False)
        validate(p)
        for key,value in (('new_training',False),('production_authority',True),('command',['evil.py']),('command_timeout_seconds',999)):
            q=dict(p);q[key]=value
            with self.assertRaises(ValueError):validate(q)

    def test_broker_manifest_source_identity(self):
        import hashlib
        from unittest.mock import patch
        import wave_dual_gate_broker_v1 as broker
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);sources={}
            for name in broker.SOURCES:
                raw=b'# synthetic frozen source\n';(root/name).write_bytes(raw)
                sources[name]={'git_blob_sha1':hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest()}
            manifest=root/'manifest.json'
            manifest.write_text(json.dumps(dict(schema_id='csi1000.wave_dual_gate_execution@1.0',profile=broker.PROFILE,private_ref=broker.PRIVATE_REF,sources=sources,new_training=True,production_authority=False)))
            with patch.object(broker,'HERE',root),patch.object(broker,'MANIFEST',manifest):
                self.assertTrue(broker.load_profile()['new_training'])
                (root/broker.SOURCES[0]).write_text('changed')
                with self.assertRaises(ValueError):broker.load_profile()

    def test_statistical_same_source_reproduction_is_disclosed(self):
        import wave_dual_gate_verifier_v1 as verifier
        self.assertIn('not an independent statistical implementation',verifier.__doc__)


if __name__=='__main__':unittest.main()
