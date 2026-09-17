import ast
import math
from pathlib import Path
import sys
import unittest
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "executor"))
import wave_scale_validity_diagnostics_v1 as v


def prices(log_path):
    return np.exp(math.log(100.0) + np.asarray(log_path, float))


def phase(close, shift=0, wick_index=None, wick_size=0.0):
    close = np.asarray(close, float)
    rows = []
    for i, c in enumerate(close):
        low = c
        high = c
        if wick_index == i:
            high = c * math.exp(wick_size)
        rows.append((shift + i * 5, low, c, high))
    return rows


def five_phases(close, event_shifts=(0, 1, 2, 3, 4)):
    return {f"offset{i}": phase(close, shift=event_shifts[i]) for i in range(5)}


class ValidityDiagnosticsTests(unittest.TestCase):
    def test_single_jump_has_high_concentration(self):
        y = np.r_[np.zeros(50), np.ones(50) * 0.04]
        r = v.close_jump_diagnostics(prices(y), np.arange(-99, 1))
        self.assertAlmostEqual(r["close_jump_concentration"], 1.0, places=12)
        self.assertAlmostEqual(r["close_range_concentration"], 1.0, places=12)
        self.assertEqual(r["largest_close_jump_relative_minute"], -49)
    def test_sustained_jump_and_spike_have_different_persistence(self):
        sustained = np.r_[np.zeros(40), np.ones(40) * 0.04]
        spike = np.zeros(80); spike[40] = 0.04
        a = v.close_jump_diagnostics(prices(sustained), np.arange(-79, 1))
        b = v.close_jump_diagnostics(prices(spike), np.arange(-79, 1))
        self.assertGreater(a["jump_persistence_ratio"], 0.9)
        self.assertLess(abs(b["jump_persistence_ratio"]), 0.1)

    def test_smooth_path_has_low_jump_concentration(self):
        y = 0.03 * np.sin(np.linspace(0, math.pi, 120))
        r = v.close_jump_diagnostics(prices(y), np.arange(-119, 1))
        self.assertLess(r["close_jump_concentration"], 0.03)

    def test_multiplicative_price_level_does_not_change_ratios(self):
        y = np.r_[np.zeros(40), np.ones(40) * 0.03]
        x = prices(y)
        a = v.close_jump_diagnostics(x, np.arange(-79, 1))
        b = v.close_jump_diagnostics(x * 7.0, np.arange(-79, 1))
        for key in ("close_jump_concentration", "close_range_concentration", "jump_persistence_ratio"):
            self.assertAlmostEqual(a[key], b[key], places=12)

    def test_near_constant_is_explicit(self):
        r = v.close_jump_diagnostics(np.ones(20) * 100.0, np.arange(-19, 1))
        self.assertTrue(r["near_constant"])
        self.assertIsNone(r["close_jump_concentration"])
        self.assertIsNone(r["close_range_concentration"])
    def test_wick_only_outlier_is_measured_without_state_assignment(self):
        close = np.linspace(100.0, 101.0, 20)
        rows = phase(close, wick_index=10, wick_size=0.08)
        r = v.phase_discontinuity_diagnostics(rows)
        self.assertGreater(r["wick_only_concentration"], 0.8)

    def test_phase_location_agreement_with_natural_five_minute_tolerance(self):
        close = np.r_[np.ones(20) * 100.0, np.ones(20) * 104.0]
        phases = five_phases(close, (0, 1, 2, 3, 4))
        r = v.measure_validity(close, np.arange(-39, 1), phases)
        self.assertEqual(r["phase_stability"]["largest_jump_location_agreement_within_5m"], 5)
        self.assertEqual(r["validity_state"], "UNASSIGNED_THRESHOLD_FREE")
        self.assertFalse(r["threshold_selected"])

    def test_wick_summary_uses_all_five_phases(self):
        close = np.linspace(100.0, 102.0, 20)
        phases = {f"offset{i}": phase(close, shift=i, wick_index=8, wick_size=0.01 * (i + 1))
                  for i in range(5)}
        r = v.measure_validity(close, np.arange(-19, 1), phases)
        q = r["phase_stability"]["wick_only_concentration"]
        self.assertLess(q["min"], q["max"])
        self.assertGreater(q["median"], 0.0)

    def test_short_post_jump_support_is_not_backfilled(self):
        y = np.zeros(20); y[-2:] = 0.04
        r = v.close_jump_diagnostics(prices(y), np.arange(-19, 1))
        self.assertLess(r["jump_post_support"], 3)
        self.assertIsNone(r["jump_persistence_ratio"])
    def test_bad_phase_schema_rejected(self):
        close = np.linspace(100.0, 101.0, 10)
        with self.assertRaises(ValueError):
            v.measure_validity(close, np.arange(-9, 1), {"offset0": phase(close)})
        bad = phase(close); bad[3] = (15, 102.0, 101.0, 100.0)
        with self.assertRaises(ValueError):
            v.phase_discontinuity_diagnostics(bad)

    def test_relative_axis_must_be_strictly_increasing(self):
        with self.assertRaises(ValueError):
            v.close_jump_diagnostics([100, 101, 102], [0, 0, 1])

    def test_pure_module_has_no_file_or_network_io(self):
        tree = ast.parse((ROOT / "executor/wave_scale_validity_diagnostics_v1.py").read_text())
        forbidden = {"open", "read_parquet", "read_csv", "write_text", "write_bytes", "urlopen", "request", "Popen", "system"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = getattr(node.func, "id", getattr(node.func, "attr", ""))
                self.assertNotIn(name, forbidden)

    def test_no_labels_or_threshold_constants_in_module(self):
        text = (ROOT / "executor/wave_scale_validity_diagnostics_v1.py").read_text().lower()
        for token in ("data_invalid_edge", "current_scale_supported", "current_scale_not_dominant", "reference_label"):
            self.assertNotIn(token, text)


if __name__ == "__main__":
    unittest.main()
