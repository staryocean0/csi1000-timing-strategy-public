import ast
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'executor'))
import wave_scale_fixed_lag_market_broker_v1 as broker

PROFILE = 'two-wave-scale-fixed-lag-confirmation-measurement-v1'
WORKFLOW_PARENT = '01f44fb699414a196a04d052f84257adaf97f0e8'
CONTROLLER_PARENT = 'f908ed048ed8367db2b292cc8b4de389d0e6ca64'


def blob_bytes(raw):
    return hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()


def blob(path):
    return blob_bytes(Path(path).read_bytes())


class FixedLagMarketTests(unittest.TestCase):
    def test_protocol_freezes_occurrence_and_knowledge_times(self):
        p = json.loads((ROOT / 'docs/research/TWO_WAVE_SCALE_FIXED_LAG_CONFIRMATION_PROTOCOL_20260918.json').read_text())
        self.assertEqual(p['lag_minutes'], [0, 5, 10, 15, 25])
        self.assertEqual(p['confirmation_contract']['lag_phase_bars'], [0, 1, 2, 3, 5])
        self.assertTrue(p['confirmation_contract']['candidate_event_must_be_at_or_before_occurrence'])
        self.assertFalse(p['confirmation_contract']['knowledge_time_future_data_used'])
        self.assertFalse(p['reference_labels_visible_to_compute'])
        self.assertFalse(p['threshold_selection_in_run'])
        self.assertFalse(p['post_measurement_gate']['lag_promotion_from_this_population'])

    def test_registration_preserves_prior33_without_lag_results(self):
        r = json.loads((ROOT / 'docs/research/TWO_WAVE_SCALE_FIXED_LAG_CONFIRMATION_REGISTRATION_20260918.json').read_text())
        self.assertEqual(r['status'], 'FIXED_LAG_CONFIRMATION_PROFILE_SOURCE_READY_NOT_RUN')
        self.assertFalse(r['lag_performance_inspected'])
        lineage = json.loads((ROOT / 'docs/research/TWO_WAVE_RESEARCH_LINEAGE_20260916.json').read_text())['ordered_lineage']
        raw = json.dumps(lineage[:33], sort_keys=True, separators=(',', ':')).encode()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), r['prior_33_lineage_sha256'])
        self.assertEqual((lineage[33]['order'], lineage[33]['issue']), (34, 386))

    def test_manifest_source_closure(self):
        m = json.loads((ROOT / 'docs/research/TWO_WAVE_SCALE_FIXED_LAG_CONFIRMATION_EXECUTION_MANIFEST_V1.json').read_text())
        self.assertEqual((m['schema_id'], m['profile']), ('csi1000.scale_fixed_lag_confirmation_execution@1.0', PROFILE))
        self.assertEqual(len(m['source_blobs']), 15)
        for name, expected in m['source_blobs'].items():
            self.assertEqual(blob(ROOT / 'executor' / name), expected, name)
        self.assertEqual(blob(ROOT / 'executor/wave_scale_fixed_lag_market_broker_v1.py'), m['broker_blob'])
        self.assertEqual(broker.load_manifest()['profile'], PROFILE)

    def test_entry_has_exact_five_lag_outputs(self):
        text = (ROOT / 'executor/wave_scale_fixed_lag_market_entry_v1.py').read_text()
        self.assertIn('fixed_lag_summary.json', text)
        self.assertNotIn('final_annotations', text)
        self.assertIn('LAG_MINUTES', text)

    def test_independent_verifier_does_not_import_fixed_lag_producer(self):
        tree = ast.parse((ROOT / 'executor/wave_scale_fixed_lag_market_verifier_v1.py').read_text())
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module)
        self.assertNotIn('wave_scale_fixed_lag_confirmation_v1', names)
        self.assertNotIn('wave_scale_fixed_lag_market_measurement_v1', names)

    def test_workflow_route_is_exact_append_and_secret_surface_unchanged(self):
        path = ROOT / '.github/workflows/public-compute.yml'
        text = path.read_text()
        self.assertEqual(text.count(PROFILE), 12)
        self.assertEqual(text.count('secrets.FACTORLAB_PRIVATE_TOKEN'), 2)
        text = text.replace(f'          - {PROFILE}\n', '')
        text = text.replace(f" || inputs.profile == '{PROFILE}'", '')
        for phase in ('prepare', 'compute', 'cleanup', 'publish'):
            branch = (
                "          elif [ '${{ inputs.profile }}' = '" + PROFILE + "' ]; then\n"
                + f'            python3 executor/wave_scale_fixed_lag_market_broker_v1.py {phase} {PROFILE}\n'
            )
            self.assertEqual(text.count(branch), 1)
            text = text.replace(branch, '')
        self.assertEqual(blob_bytes(text.encode()), WORKFLOW_PARENT)

    def test_controller_route_is_exact_append(self):
        text = (ROOT / '.github/workflows/controller-dispatch.yml').read_text()
        self.assertEqual(text.count(PROFILE), 3)
        text = text.replace(f"       github.event.issue.title == 'controller: {PROFILE}' ||\n", '')
        case = (
            f"            'controller: {PROFILE}')\n"
            + f"              profile='{PROFILE}'\n"
            + '              ;;\n'
        )
        self.assertEqual(text.count(case), 1)
        text = text.replace(case, '')
        self.assertEqual(blob_bytes(text.encode()), CONTROLLER_PARENT)

    def test_authority_advances_only_to_formal_measurement(self):
        a = json.loads((ROOT / 'docs/research/TWO_WAVE_SEGMENTATION_DOMINANCE_THREAD_AUTHORITY_20260917.json').read_text())
        lane = next(x for x in a['active_lanes'] if x['issue'] == 353)
        self.assertIn(lane['status'], {'FIXED_LAG_CONFIRMATION_PROFILE_SOURCE_READY_NOT_RUN','FIXED_LAG_DEVELOPMENT_LOYO_NOT_READY_OBJECTIVE_ABSTENTION_COLLAPSE_NO_LAG_PROMOTION','CALIBRATION_V3_SOURCE_READY_NOT_RUN','CALIBRATION_V3_NOT_READY_AMBIGUITY_RECALL_COLLAPSE_VALIDITY_RECALL_LOW_NO_FULL_FIT','CALIBRATION_V4_SOURCE_READY_NOT_RUN','CALIBRATION_V4_NOT_READY_AMBIGUITY_RECALL_LOW_VALIDITY_RECALL_LOWER_NO_FULL_FIT','POST_V4_AUDIT_DIAGNOSTIC_FAMILY_REVISION_REQUIRED_BEFORE_ANY_CALIBRATION_V5'})
        self.assertIn(a['S2_progress']['next'], {'MERGE_FIXED_LAG_PROFILE_THEN_FORMAL_LABEL_BLIND_MEASUREMENT','PREREGISTER_COVERAGE_CONSTRAINED_MORPHOLOGY_OBJECTIVE_V3_AND_VALIDITY_REVISION','MERGE_CALIBRATION_V3_THEN_RUN_FROZEN_FIXED_LAG_LOYO','RUN_THRESHOLD_FREE_AMBIGUITY_AND_VALIDITY_CAPACITY_AUDIT_BEFORE_V4_PREREGISTRATION','MERGE_CALIBRATION_V4_THEN_RUN_FROZEN_FIXED_LAG_LOYO','RUN_POST_V4_ERROR_AND_CAPACITY_AUDIT_BEFORE_ANY_V5_PREREGISTRATION','PREREGISTER_LABEL_BLIND_DIAGNOSTIC_FAMILY_V3_MULTISCALE_COMPETITION_AND_VALIDITY_SUBTYPE_EVIDENCE'})
        self.assertEqual(a['S2_progress']['fixed_lag_confirmation_performance_inspected'], lane['status'] != 'FIXED_LAG_CONFIRMATION_PROFILE_SOURCE_READY_NOT_RUN')
        self.assertFalse(a['S2_progress']['full_192_fit_performed'])


if __name__ == '__main__':
    unittest.main()
