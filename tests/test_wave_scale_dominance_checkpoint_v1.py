import hashlib,json,math,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'executor'))
from wave_scale_dominance_synthetic_v1 import run_suite
CP=ROOT/'docs/research/TWO_WAVE_SCALE_DOMINANCE_SYNTHETIC_CHECKPOINT_20260917.json'
RESULT=ROOT/'docs/research/TWO_WAVE_SCALE_DOMINANCE_SYNTHETIC_RESULT_20260917.json'
LINEAGE=ROOT/'docs/research/TWO_WAVE_RESEARCH_LINEAGE_20260916.json'
AUTH=ROOT/'docs/research/TWO_WAVE_SEGMENTATION_DOMINANCE_THREAD_AUTHORITY_20260917.json'


def blob(path):
    raw=Path(path).read_bytes()
    return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()


class DominanceCheckpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c=json.loads(CP.read_text());cls.r=json.loads(RESULT.read_text())

    def test_status_is_source_synthetic_only(self):
        self.assertEqual(self.c['status'],'SYNTHETIC_DIAGNOSTIC_IMPLEMENTED_NO_MARKET_THRESHOLDS')
        self.assertIsNone(self.c['classification_thresholds'])
        self.assertIsNone(self.c['real_market_run'])
        self.assertEqual(self.c['real_market_reference_labels'],'NOT_YET_FROZEN')

    def test_source_identities_are_pinned(self):
        for name,sha in self.c['source_blobs'].items():
            self.assertEqual(blob(ROOT/name),sha,name)

    def test_bic_floor_is_documented_as_numeric_only(self):
        n=self.c['numerical_stability']
        self.assertEqual(n['bic_rmse_floor'],1e-12)
        self.assertEqual(n['bic_variance_floor'],1e-24)
        self.assertEqual(n['role'],'NUMERIC_ONLY_NOT_MARKET_THRESHOLD')

    def test_stored_result_reproduces(self):
        fresh=run_suite()
        def same(a,b):
            if isinstance(a,dict):
                self.assertEqual(set(a),set(b))
                for k in a:same(a[k],b[k])
            elif isinstance(a,list):
                self.assertEqual(len(a),len(b))
                for x,y in zip(a,b):same(x,y)
            elif isinstance(a,float):
                self.assertTrue(math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-12),(a,b))
            else:self.assertEqual(a,b)
        same(self.r,fresh)

    def test_prior_fourteen_lineage_rows_preserved(self):
        line=json.loads(LINEAGE.read_text());self.assertGreaterEqual(len(line['ordered_lineage']),15)
        raw=json.dumps(line['ordered_lineage'][:14],sort_keys=True,separators=(',',':')).encode()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),self.c['prior_14_lineage_sha256'])
        self.assertEqual(line['ordered_lineage'][14]['order'],15)
        self.assertEqual(line['ordered_lineage'][14]['issue'],353)

    def test_thread_progress_preserves_synthetic_checkpoint_without_market_thresholds(self):
        a=json.loads(AUTH.read_text());lanes={x['issue']:x for x in a['active_lanes']}
        self.assertEqual(lanes[353]['checkpoint'],'docs/research/TWO_WAVE_SCALE_DOMINANCE_SYNTHETIC_CHECKPOINT_20260917.json')
        self.assertEqual(lanes[353]['reference_issue'],359)
        self.assertEqual(a['S2_progress']['market_thresholds'],None)
        self.assertIn(a['S2_progress']['real_market_reference_labels'],('NOT_YET_FROZEN','FROZEN_192_AFTER_PASS_B'))
        self.assertFalse(a['S2_progress']['future_suffix_revealed'])

    def test_diagnostic_does_not_search_pivots_or_authorize_routing(self):
        self.assertEqual(self.c['diagnostic_role'],'SUPPLIED_CAUSAL_MORPHOLOGY_HYPOTHESIS_SUPPORT_NOT_PIVOT_SEARCH')
        self.assertFalse(self.c['R4_selected']);self.assertFalse(self.c['one_minute_strategy_admitted'])
        self.assertFalse(self.c['router_pnl']);self.assertFalse(self.c['production_authority'])
        self.assertFalse(self.c['outcomes_used'])

    def test_result_has_no_final_market_state(self):
        self.assertIsNone(self.r['market_run'])
        for row in self.r['cases'].values():
            for key in ('diagnostic','prefix_diagnostic','full_diagnostic'):
                if key in row:self.assertEqual(row[key]['dominance_state'],'UNASSIGNED_THRESHOLD_FREE')

    def test_legacy_R3_status_remains_failed(self):
        a=json.loads(AUTH.read_text())
        self.assertIn('FAILED',a['historical_status']['R3'])
        self.assertFalse(a['historical_status']['retroactive_relabeling'])

if __name__=='__main__':unittest.main()
