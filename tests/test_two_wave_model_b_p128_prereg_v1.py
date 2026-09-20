import hashlib
import json
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "executor"))
import two_wave_postdelay_persistence_v1 as context


class ModelBP128PreregTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = json.loads((ROOT / "docs/research/TWO_WAVE_MODEL_B_P128_STATE_EXIT_PREREG_20260920.json").read_text())

    def test_legacy_sources_are_unchanged(self):
        for name, expected in self.spec["frozen_sources_sha256"].items():
            self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), expected)

    def test_context_identity_is_explicit_and_single(self):
        c = self.spec["context"]
        self.assertEqual(c["id"], "P128_RAW_PRICE_CURRENT_PHASE")
        self.assertEqual(c["window_bars"], 128)
        self.assertEqual(c["additional_candidates"], [])
        self.assertFalse(c["equivalent_to_C1"])
        self.assertFalse(c["explicit_bandpass"])
        self.assertEqual(c["threshold"], context.TAU_PARENT)

    def test_frozen_target_and_development_identity(self):
        self.assertEqual(self.spec["baseline"]["scored_rows"], 29713)
        self.assertEqual(self.spec["target"]["primary"], "structural_exit_next8")
        self.assertFalse(self.spec["target"]["low_finer_primary"])
        self.assertFalse(self.spec["data"]["fresh_oos"])
        self.assertEqual(self.spec["training"]["label_maturity"], "known_index + 8 < first_native_index_of_test_year")
        self.assertEqual(self.spec["training"]["test_years"], [2018, 2019, 2020])

    def test_finite_symmetric_model_budget_and_frozen_gate(self):
        self.assertEqual(self.spec["models"]["A_parameters"], 12)
        self.assertEqual(self.spec["models"]["B_parameters"], 16)
        self.assertEqual(self.spec["models"]["ridge_lambda"], 0.001)
        self.assertFalse(self.spec["models"]["hyperparameter_search"])
        self.assertEqual(self.spec["information_gate"]["pooled_relative_brier_gain_min"], 0.01)
        self.assertTrue(self.spec["training"]["same_AB_fit_rows"])
        self.assertTrue(self.spec["training"]["new_training"])
        self.assertFalse(any(self.spec["authority"].values()))

    def test_context_primitive_prefix_and_future_suffix(self):
        close = np.exp(4 + 0.001 * np.arange(400) + 0.03 * np.sin(np.arange(400) / 17))
        for k in [127, 188, 299]:
            prefix = close[:k+1].copy()
            changed = close.copy()
            changed[k+1:] *= np.exp(np.linspace(0.3, -0.2, len(close)-k-1))
            original = context.parent_phase(close[k-127:k+1])
            self.assertEqual(original, context.parent_phase(prefix[-128:]))
            self.assertEqual(original, context.parent_phase(changed[k-127:k+1]))

    def test_flat_is_valid_range_invalid_is_not_neutral(self):
        self.assertEqual(context.parent_phase(np.full(128, 100.0)), ("PARENT_RANGE", 0.0))
        with self.assertRaises(ValueError):
            context.parent_phase(np.r_[np.ones(127), np.nan])


if __name__ == "__main__":
    unittest.main()
