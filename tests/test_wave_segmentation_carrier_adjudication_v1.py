import hashlib,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ADJ=ROOT/'docs/research/TWO_WAVE_SEGMENTATION_CARRIER_QUALIFICATION_ADJUDICATION_20260917.json'
LINEAGE=ROOT/'docs/research/TWO_WAVE_RESEARCH_LINEAGE_20260916.json'
AUTH=ROOT/'docs/research/TWO_WAVE_SEGMENTATION_DOMINANCE_THREAD_AUTHORITY_20260917.json'
S2=ROOT/'docs/research/TWO_WAVE_SCALE_DOMINANCE_MONITOR_PROTOCOL_20260917.json'

class CarrierAdjudicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a=json.loads(ADJ.read_text()); cls.l=json.loads(LINEAGE.read_text()); cls.auth=json.loads(AUTH.read_text())

    def test_decision_and_run_identity(self):
        self.assertEqual(self.a['decision'],'S1_CARRIER_CONSTRUCTION_AND_COMMON_SUPPORT_QUALIFIED')
        self.assertEqual(self.a['public_run_id'],'35191936364-1')
        self.assertEqual(self.a['workflow_run'],35191936364)
        self.assertEqual(self.a['workflow_event'],'workflow_dispatch')
        self.assertEqual(self.a['workflow_status'],'success')
        self.assertEqual(self.a['public_registration_merge'],'f1905aac67b422fdccb05e86eb6fbb79ca530a0b')

    def test_receipt_is_passed_and_verified(self):
        r=self.a['receipt']
        self.assertEqual((r['status'],r['delivery_status']),('passed','archive_uploaded_and_verified'))
        self.assertEqual(r['profile'],'two-wave-segmentation-carrier-qualification-v1')
        for key in ('manifest_sha256','report_sha256','archive_sha256'):
            self.assertEqual(len(r[key]),64)
        self.assertGreater(r['archive_bytes'],0)

    def test_all_six_files_are_schema_clean(self):
        p=self.a['input_population']
        self.assertEqual(len(p['files']),6); self.assertEqual(p['all_files_columns'],25)
        self.assertEqual(p['unexpected_clock_rows'],0); self.assertEqual(p['schema_or_ohlc_errors'],0)
        self.assertEqual((p['trading_days'],p['excluded_days_count'],p['complete_nonexcluded_days']),(1462,4,1458))
        self.assertEqual(sum(v for k,v in p['files'].items() if k.startswith('5m_')),338882)

    def test_supported_reconstruction_is_exact(self):
        r=self.a['reconstruction']
        self.assertEqual(r['compared_bars'],333978); self.assertEqual(r['exact_equal_bars'],333978)
        self.assertEqual(r['matched_bars'],333978); self.assertEqual(r['mismatched_bars'],0)
        self.assertEqual((r['max_abs_error'],r['max_rel_error']),(0.0,0.0))
        self.assertEqual(r['unsupported_total'],4904)
        self.assertEqual(r['compared_bars']+r['unsupported_total'],r['total_5m_rows'])

    def test_each_offset_accounts_for_every_row(self):
        for row in self.a['reconstruction']['offsets'].values():
            self.assertEqual(row['compared']+sum(row['unsupported'].values()),row['total'])
            self.assertEqual(row['exact'],row['compared'])

    def test_offset0_boundary_is_explicit_not_a_mismatch(self):
        u=self.a['reconstruction']['offsets']['0']['unsupported']
        self.assertEqual(u['SOURCE_MINUTE_NOT_EXPORTED'],2916)
        self.assertEqual(u['CAUSAL_FLAT_FILL'],616)
        self.assertEqual(u['EXCLUDED_DAY'],130)

    def test_common_physical_support_is_explicit(self):
        c=self.a['common_support']
        self.assertEqual(c['common_complete_eligible_days'],1458)
        self.assertEqual(c['minute_windows'],['09:34-11:26','13:04-14:56'])
        self.assertEqual(c['contract_common_minutes'],329508)
        self.assertEqual(c['exported_common_minute_rows'],329508)
        self.assertEqual(c['observed_unfilled_common_minutes']+c['causal_fill_common_minutes'],329508)

    def test_scope_does_not_promote_scientific_claims(self):
        i=self.a['interpretation']; au=self.a['authority']
        self.assertEqual(i['aliasing_conclusion'],'NOT_AUTHORIZED')
        self.assertEqual(i['scale_dominance_conclusion'],'NOT_AUTHORIZED')
        self.assertTrue(i['does_not_prove_segmentation_accuracy'])
        self.assertFalse(i['full_original_datahub_export_binary_equality_directly_tested'])
        self.assertFalse(any(au.values()))
        self.assertFalse(self.a['outcomes_used'])

    def test_prior_thirteen_lineage_rows_preserved(self):
        self.assertEqual(len(self.l['ordered_lineage']),14)
        raw=json.dumps(self.l['ordered_lineage'][:13],sort_keys=True,separators=(',',':')).encode()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),self.a['history_guard']['prior_13_lineage_sha256'])
        self.assertEqual(self.l['ordered_lineage'][-1]['order'],14)
        self.assertFalse(self.l['ordered_lineage'][-1]['R3_reclassified'])

    def test_authority_unblocks_S2_without_editing_original_protocol(self):
        lanes={x['issue']:x for x in self.auth['active_lanes']}
        self.assertIn('COMPLETED_QUALIFIED',lanes[352]['status'])
        self.assertIn('S1_SATISFIED',lanes[353]['status'])
        self.assertEqual(self.auth['S1_completion']['supported_reconstruction_mismatches'],0)
        s2=json.loads(S2.read_text())
        self.assertTrue(s2['blocked_on_issue352_for_market_evaluation'])
        self.assertEqual(self.auth['S1_completion']['block_for_issue353'],'SATISFIED')

if __name__=='__main__':unittest.main()
