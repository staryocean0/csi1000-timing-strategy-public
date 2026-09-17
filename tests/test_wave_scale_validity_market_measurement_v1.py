import ast
import json
from pathlib import Path
import sys
import unittest
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "executor"))
import wave_scale_validity_diagnostics_v1 as d
import wave_scale_validity_market_measurement_v1 as m
import wave_scale_validity_market_verifier_v1 as v


class ValidityMarketMeasurementTests(unittest.TestCase):
    def test_protocol_is_label_blind_and_threshold_free(self):
        p = json.loads((ROOT / "docs/research/TWO_WAVE_SCALE_VALIDITY_MARKET_PROTOCOL_20260917.json").read_text())
        self.assertEqual((p["research_issue"], p["parent_issue"]), (376, 353))
        self.assertFalse(p["reference_labels_visible_to_compute"])
        self.assertFalse(p["threshold_selection_in_run"])
        self.assertIsNone(p["numeric_validity_thresholds"])
        self.assertEqual(p["fixed_reference"]["final_reference_labels_sha256"],
                         "6fb36ee74413c9b7e95824a94a89bec74a493513668a36b3373c24518fc834be")

    def test_measurement_module_has_no_file_io_or_label_loader(self):
        text = (ROOT / "executor/wave_scale_validity_market_measurement_v1.py").read_text()
        tree = ast.parse(text)
        forbidden = {"open", "read_parquet", "read_csv", "urlopen", "request", "system", "Popen", "exec", "eval"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                self.assertNotIn(getattr(node.func, "id", getattr(node.func, "attr", "")), forbidden)
        self.assertNotIn("final_annotations", text)
        self.assertNotIn("pass_a_sealed", text)

    def test_entry_output_contract_contains_only_validity_rows_and_summary(self):
        text = (ROOT / "executor/wave_scale_validity_market_entry_v1.py").read_text()
        self.assertIn("OUTPUTS={'validity_diagnostics.jsonl','validity_summary.json'}", text)
        self.assertNotIn("reference_labels.json", text)
        self.assertNotIn("full_inventory.json", text)

    def test_independent_verifier_does_not_import_producer_or_diagnostic_module(self):
        tree = ast.parse((ROOT / "executor/wave_scale_validity_market_verifier_v1.py").read_text())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import): imported.update(alias.name for alias in node.names)
            if isinstance(node, ast.ImportFrom) and node.module: imported.add(node.module)
        self.assertNotIn("wave_scale_validity_market_measurement_v1", imported)
        self.assertNotIn("wave_scale_validity_diagnostics_v1", imported)

    def test_independent_one_minute_formula_matches_pure_diagnostic(self):
        y = np.r_[np.zeros(40), np.ones(40) * 0.03]
        prices = np.exp(np.log(100.0) + y)
        rel = np.arange(-79, 1)
        a = d.close_jump_diagnostics(prices, rel)
        b = v.one_minute(prices, rel)
        self.assertEqual(set(a), set(b))
        for key in a:
            if isinstance(a[key], float): self.assertAlmostEqual(a[key], b[key], places=12)
            else: self.assertEqual(a[key], b[key])
    def test_independent_phase_formula_matches_pure_diagnostic(self):
        close = np.linspace(100.0, 101.0, 20)
        rows = []
        for i, c in enumerate(close):
            high = c * (1.03 if i == 10 else 1.0)
            rows.append((i * 5, c, c, high))
        a = d.phase_discontinuity_diagnostics(rows)
        b = v.phase_measure(rows)
        self.assertEqual(set(a), set(b))
        for key in a:
            if isinstance(a[key], float): self.assertAlmostEqual(a[key], b[key], places=12)
            else: self.assertEqual(a[key], b[key])

    def test_manifest_is_scope_only_no_label_join(self):
        files = {"validity_diagnostics.jsonl": b"{}\n", "validity_summary.json": b"{}\n"}
        value = json.loads(m.result_manifest(files))
        self.assertEqual(value["schema_id"], "csi1000.scale_validity_market_manifest@1.0")
        self.assertFalse(value["reference_labels_visible_to_compute"])
        self.assertFalse(value["threshold_selected"])
        self.assertFalse(value["production_authority"])

    def test_protocol_feature_definitions_are_fixed_before_market_run(self):
        p = json.loads((ROOT / "docs/research/TWO_WAVE_SCALE_VALIDITY_MARKET_PROTOCOL_20260917.json").read_text())
        f = p["validity_feature_contract"]
        self.assertIn("max_abs_dlog_close", f["one_minute_close_jump_concentration"])
        self.assertIn("next10", f["jump_persistence_ratio"])
        self.assertIn("+/-5", f["phase_jump_location_agreement"])
        self.assertFalse(f["validity_state_assignment"])


if __name__ == "__main__":
    unittest.main()
