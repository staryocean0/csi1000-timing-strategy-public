import ast
import hashlib
import json
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'executor'))
import wave_scale_diagnostic_family_v2 as pure
import wave_scale_diagnostic_family_market_verifier_v2 as verifier
import wave_scale_diagnostic_family_market_broker_v2 as broker
from tests.segmentation_carrier_registration_support import (
    DIAG_V2_PROFILE, strip_diag_v2_workflow, strip_diag_v2_controller,
)


def blob_bytes(raw):
    return hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()


def blob(path):
    return blob_bytes(Path(path).read_bytes())


def synthetic_prices(kind):
    base = 100.0
    if kind == 'sustained':
        pre = np.linspace(base, base * 1.001, 50)
        return np.r_[pre, pre[-1] * 1.03, np.linspace(pre[-1] * 1.0301, pre[-1] * 1.031, 20)]
    if kind == 'spike':
        pre = np.linspace(base, base * 1.001, 50)
        return np.r_[pre, pre[-1] * 1.03, np.linspace(pre[-1] * 1.0001, pre[-1] * 1.001, 20)]
    raise ValueError(kind)


def phase_rows(prices):
    rel = np.arange(-5 * (len(prices) - 1), 1, 5)
    return [(int(r), float(p)) for r, p in zip(rel, prices)]


class DiagnosticFamilyMarketV2Tests(unittest.TestCase):
    def test_protocol_is_label_blind_and_threshold_free(self):
        p = json.loads((ROOT / 'docs/research/TWO_WAVE_SCALE_DIAGNOSTIC_FAMILY_MARKET_PROTOCOL_V2_20260917.json').read_text())
        self.assertEqual((p['research_issue'], p['profile']), (381, DIAG_V2_PROFILE))
        self.assertFalse(p['reference_labels_visible_to_compute'])
        self.assertFalse(p['threshold_selection_in_run'])
        self.assertIsNone(p['numeric_thresholds'])

    def test_entry_outputs_only_raw_v2_evidence(self):
        text = (ROOT / 'executor/wave_scale_diagnostic_family_market_entry_v2.py').read_text()
        self.assertIn("OUTPUTS = {'diagnostic_family_v2.jsonl', 'diagnostic_family_v2_summary.json'}", text)
        self.assertNotIn('final_annotations', text)
        self.assertNotIn('reference_labels.json', text)

    def test_producer_has_no_label_loader_or_threshold_selector(self):
        text = (ROOT / 'executor/wave_scale_diagnostic_family_market_measurement_v2.py').read_text()
        for forbidden in ('final_annotations', 'pass_a_sealed', 'fit_loyo', 'numeric_threshold =', 'threshold ='):
            self.assertNotIn(forbidden, text)
        self.assertIn('measure_validity_v2', text)
        self.assertIn('measure_morphology_v2', text)

    def test_independent_verifier_imports_neither_v2_producer_nor_v2_pure_module(self):
        tree = ast.parse((ROOT / 'executor/wave_scale_diagnostic_family_market_verifier_v2.py').read_text())
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module)
        self.assertNotIn('wave_scale_diagnostic_family_v2', names)
        self.assertNotIn('wave_scale_diagnostic_family_market_measurement_v2', names)

    def test_independent_jump_extension_matches_pure_formula(self):
        prices = synthetic_prices('sustained')
        rel = np.arange(-len(prices) + 1, 1)
        a = pure.close_jump_v2(prices, rel)
        b = verifier.jump_extension(prices, rel)
        self.assertEqual(set(a), set(b))
        for key in a:
            if isinstance(a[key], dict):
                self.assertEqual(set(a[key]), set(b[key]))
                for sub in a[key]:
                    av, bv = a[key][sub], b[key][sub]
                    if av is None or bv is None:
                        self.assertIs(av, bv)
                    else:
                        self.assertAlmostEqual(av, bv, places=13)
            elif isinstance(a[key], float):
                self.assertAlmostEqual(a[key], b[key], places=13)
            else:
                self.assertEqual(a[key], b[key])

    def test_independent_morphology_phase_matches_pure_formula(self):
        up = np.linspace(100, 108, 31)
        down = np.linspace(108, 100, 31)[1:]
        rows = phase_rows(np.r_[up, down])
        a = pure.measure_morphology_phase_v2(rows)
        b = verifier.morph_phase(rows)
        self.assertEqual(set(a), set(b))
        for key in a:
            if isinstance(a[key], float):
                self.assertAlmostEqual(a[key], b[key], places=10)
            else:
                self.assertEqual(a[key], b[key])

    def test_execution_manifest_source_closure(self):
        m = json.loads((ROOT / 'docs/research/TWO_WAVE_SCALE_DIAGNOSTIC_FAMILY_MARKET_EXECUTION_MANIFEST_V2.json').read_text())
        self.assertEqual((m['schema_id'], m['profile']), ('csi1000.scale_diagnostic_family_market_execution@2.0', DIAG_V2_PROFILE))
        self.assertEqual(len(m['source_blobs']), 14)
        for name, expected in m['source_blobs'].items():
            self.assertEqual(blob(ROOT / 'executor' / name), expected, name)
        self.assertEqual(blob(ROOT / 'executor/wave_scale_diagnostic_family_market_broker_v2.py'), m['broker_blob'])

    def test_broker_manifest_loads(self):
        self.assertEqual(broker.load_manifest()['profile'], DIAG_V2_PROFILE)

    def test_route_and_secret_surface(self):
        w = (ROOT / '.github/workflows/public-compute.yml').read_text()
        c = (ROOT / '.github/workflows/controller-dispatch.yml').read_text()
        self.assertEqual(w.count(DIAG_V2_PROFILE), 12)
        self.assertEqual(c.count(DIAG_V2_PROFILE), 3)
        self.assertEqual(w.count('secrets.FACTORLAB_PRIVATE_TOKEN'), 2)

    def test_v2_route_strips_to_exact_parent_control_plane(self):
        w = (ROOT / '.github/workflows/public-compute.yml').read_text()
        c = (ROOT / '.github/workflows/controller-dispatch.yml').read_text()
        self.assertEqual(blob_bytes(strip_diag_v2_workflow(w).encode()), 'dfac40c0fb6e46e35a4749f756a3e64d25fd7ac5')
        self.assertEqual(blob_bytes(strip_diag_v2_controller(c).encode()), 'd687138361f1faf67cfefff7a5f45e1fa14c5f2f')

    def test_registration_preserves_prior29_and_not_run_status(self):
        r = json.loads((ROOT / 'docs/research/TWO_WAVE_SCALE_DIAGNOSTIC_FAMILY_V2_REGISTRATION_20260917.json').read_text())
        self.assertEqual(r['status'], 'DIAGNOSTIC_FAMILY_V2_PROFILE_SOURCE_READY_NOT_RUN')
        self.assertIsNone(r['formal_run'])
        self.assertFalse(r['reference_labels_visible_to_compute'])
        self.assertFalse(r['full_192_fit_performed'])
        lineage = json.loads((ROOT / 'docs/research/TWO_WAVE_RESEARCH_LINEAGE_20260916.json').read_text())['ordered_lineage']
        raw = json.dumps(lineage[:29], sort_keys=True, separators=(',', ':')).encode()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), '4d6c79682edb493353867de9a78c34864742ce5064ffb9f08eb042633d4765cf')
        self.assertEqual((lineage[29]['order'], lineage[29]['issue']), (30, 381))

    def test_authority_is_source_ready_not_measured(self):
        a = json.loads((ROOT / 'docs/research/TWO_WAVE_SEGMENTATION_DOMINANCE_THREAD_AUTHORITY_20260917.json').read_text())
        lane = next(x for x in a['active_lanes'] if x['issue'] == 353)
        self.assertIn(lane['status'], {'DIAGNOSTIC_FAMILY_V2_PROFILE_SOURCE_READY_NOT_RUN','V2_DEVELOPMENT_LOYO_NOT_READY_ABSTENTION_COLLAPSE_NO_FULL_FIT','FIXED_LAG_CONFIRMATION_PROFILE_SOURCE_READY_NOT_RUN','FIXED_LAG_DEVELOPMENT_LOYO_NOT_READY_OBJECTIVE_ABSTENTION_COLLAPSE_NO_LAG_PROMOTION','CALIBRATION_V3_SOURCE_READY_NOT_RUN','CALIBRATION_V3_NOT_READY_AMBIGUITY_RECALL_COLLAPSE_VALIDITY_RECALL_LOW_NO_FULL_FIT'})
        self.assertEqual(a['S2_progress']['diagnostic_family_v2_measured'], lane['status'] != 'DIAGNOSTIC_FAMILY_V2_PROFILE_SOURCE_READY_NOT_RUN')
        self.assertIsNone(a['S2_progress']['diagnostic_family_v2_thresholds'])
        self.assertFalse(a['S2_progress']['full_192_fit_performed'])


if __name__ == '__main__':
    unittest.main()
