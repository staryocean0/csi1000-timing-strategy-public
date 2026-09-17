"""Source/protocol and history preservation for the user-directed reframe."""
import hashlib,json,math,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'executor'))
from wave_measurement_audit_s0 import run_suite
PROTOCOL=ROOT/'docs/research/TWO_WAVE_SEGMENTATION_MEASUREMENT_PROTOCOL_20260917.json'


def blob(path):
    raw=path.read_bytes()
    return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()


class MeasurementContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.p=json.loads(PROTOCOL.read_text())

    def test_frozen_parent_sources_documents_and_control_plane(self):
        for name,sha in self.p['frozen_source_blobs'].items():
            path=ROOT/name if '/' in name else ROOT/'executor'/name
            self.assertEqual(blob(path),sha,name)

    def test_new_experiment_source_identity(self):
        for name,sha in self.p['new_source_git_blobs'].items():
            self.assertEqual(blob(ROOT/name),sha,name)

    def test_original_eleven_lineage_entries_unchanged(self):
        l=json.loads((ROOT/'docs/research/TWO_WAVE_RESEARCH_LINEAGE_20260916.json').read_text())
        raw=json.dumps(l['ordered_lineage'][:11],sort_keys=True,separators=(',',':')).encode()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),self.p['legacy']['original_11_lineage_entries_sha256'])
        self.assertEqual(l['ordered_lineage'][11]['issue'],350)
        self.assertFalse(l['ordered_lineage'][11]['R4_selected'])

    def test_goal_is_graphical_not_a_fixed_passband(self):
        self.assertEqual(self.p['representation'],'RECURSIVE_CONFIRMED_LOW_NODE_SKELETONS_NOT_IDEAL_FIXED_BANDS')
        self.assertIn('NOT_PREDEFINED_TARGET_PASSBAND',self.p['T0_21_role'])
        self.assertIsNone(self.p['legacy']['new_gate_numeric_thresholds'])

    def test_new_evaluation_keeps_denominator_and_independence(self):
        p=self.p['prospective_contract']
        self.assertTrue(p['all_windows_denominator_required'])
        self.assertTrue(p['candidate_independent_reference_required'])
        self.assertTrue(p['abstention_fraction_and_duration_always_reported'])
        self.assertFalse(p['amplitude_only_exemption'])
        self.assertTrue(p['future_suffix_cannot_change_published_state'])

    def test_six_metadata_products_do_not_claim_binary_qualification(self):
        m=self.p['external_metadata'];self.assertEqual(len(m['products']),6)
        self.assertFalse(m['parquet_bytes_or_rows_read'])
        self.assertEqual(m['construction_equivalence'],'NOT_YET_VERIFIED')
        self.assertFalse(m['new_upload_needed_now'])
        rows={x['source_product']:x['row_count'] for x in m['products']}
        self.assertEqual(rows['1m_official.parquet'],350561)
        self.assertEqual(rows['5m_offset_0.parquet'],70114)
        for i in range(1,5):self.assertLess(rows[f'5m_offset_{i}.parquet'],70114)
        for x in m['products']:self.assertEqual(len(x['sha256']),64)

    def test_stored_synthetic_report_reproduces_with_numeric_tolerance(self):
        stored=json.loads((ROOT/'docs/research/TWO_WAVE_MEASUREMENT_S0_RESULT_20260917.json').read_text())
        def same(a,b):
            if isinstance(a,dict):
                self.assertEqual(set(a),set(b))
                for k in a:same(a[k],b[k])
            elif isinstance(a,list):
                self.assertEqual(len(a),len(b))
                for x,y in zip(a,b):same(x,y)
            elif isinstance(a,float):self.assertTrue(math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-10))
            else:self.assertEqual(a,b)
        same(stored,run_suite())

    def test_no_standard_dispatch_or_authority_added(self):
        self.assertEqual((ROOT/'.github/workflows/public-compute.yml').read_text().count('secrets.FACTORLAB_PRIVATE_TOKEN'),2)
        self.assertFalse(self.p['R4_selected'])
        self.assertFalse(self.p['one_minute_strategy_admitted'])
        self.assertFalse(self.p['private_CLOUD_CURRENT_modified'])
        self.assertFalse(self.p['production_authority'])
        self.assertTrue(self.p['no_research_market_run_this_stage'])

    def test_no_retroactive_promotion_of_failed_R3(self):
        self.assertEqual(self.p['legacy']['R3_under_legacy_gate'],'FAILED')
        self.assertFalse(self.p['legacy']['retroactive_pass'])
        a=json.loads((ROOT/'docs/research/TWO_WAVE_R3_CLOCK_AUDIT_ADJUDICATION_20260917.json').read_text())
        self.assertEqual(a['decision'],'EVIDENCE_AUDIT_COMPLETED_R3_REMAINS_NOT_READY')

    def test_dedicated_ci_no_skips_and_no_market_route(self):
        w=(ROOT/'.github/workflows/wave-measurement-s0-tests.yml').read_text()
        self.assertIn('result.testsRun >= 35',w);self.assertIn('not result.skipped',w)
        self.assertNotIn('workflow_dispatch:',w);self.assertNotIn('FACTORLAB_PRIVATE_TOKEN',w)

if __name__=='__main__':unittest.main()
