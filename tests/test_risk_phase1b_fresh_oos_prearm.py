from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "executor" / "risk_phase1b_fresh_oos_eval.py"
SPEC = importlib.util.spec_from_file_location("fresh_oos", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
fresh = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fresh)


class FreshOOSPrearmTests(unittest.TestCase):
    def test_protocol_constants_are_frozen(self):
        self.assertEqual(fresh.HORIZONS, (15, 30))
        self.assertEqual(fresh.SYMBOLS, ("000688.SH", "000852.SH"))
        self.assertEqual(fresh.WARMUP_YEAR, 2025)
        self.assertEqual(fresh.FRESH_YEAR, 2026)
        self.assertEqual(fresh.BOOTSTRAP_REPS, 5000)
        self.assertEqual(fresh.BOOTSTRAP_SEED, 20260914)
        self.assertEqual(fresh.FAMILY_SIZE, 6)
        self.assertAlmostEqual(fresh.BONFERRONI_LOWER_QUANTILE, 0.05 / 6.0)
        self.assertEqual(
            fresh.MODEL_FREEZE_SHA256,
            "b81cae6208d96890c0fd83d47e4ea8c8a81ba55b41c78f58db29e9160f173551",
        )
        self.assertEqual(
            fresh.CALIBRATION_FREEZE_SHA256,
            "75d553d411f66842be8716acbe96d56de036e060c4097cc06e9e6a2333fa3a9b",
        )

    def test_no_training_or_calibrator_fit_path_exists(self):
        source = MODULE_PATH.read_text()
        self.assertNotIn("def fit_ridge", source)
        self.assertNotIn("def fit_platt", source)
        self.assertNotIn("np.linalg.solve", source)

    def test_phase1_transition_and_age_bucket_semantics(self):
        self.assertEqual(fresh.transition("NORMAL", 0.8, True), "UNSAFE")
        self.assertEqual(fresh.transition("UNSAFE", 1.6, False), "UNSAFE")
        self.assertEqual(fresh.transition("UNSAFE", 1.2, False), "RECOVERING")
        self.assertEqual(fresh.transition("UNSAFE", 1.0, False), "NORMAL")
        self.assertEqual(fresh.transition("RECOVERING", 1.6, False), "UNSAFE")
        self.assertEqual(fresh.transition("RECOVERING", 1.2, False), "RECOVERING")
        self.assertEqual(fresh.transition("RECOVERING", 1.0, False), "NORMAL")
        self.assertEqual(fresh.age_bucket(1), "LT15")
        self.assertEqual(fresh.age_bucket(2), "LT15")
        self.assertEqual(fresh.age_bucket(3), "M15_25")
        self.assertEqual(fresh.age_bucket(6), "M30_40")
        self.assertEqual(fresh.age_bucket(9), "GE45")

    def test_frozen_prediction_only_applies_supplied_coefficients(self):
        rows = pd.DataFrame(
            {
                "symbol": ["000688.SH", "000852.SH"],
                "current_state": ["UNSAFE", "RECOVERING"],
                "age_bucket": ["LT15", "M15_25"],
                "shock_intensity": [2.0, 4.0],
                "vol_ratio": [1.2, 1.6],
            }
        )
        X, names = fresh.raw_design(rows, False)
        beta = np.linspace(0.05, 0.05 * X.shape[1], X.shape[1])
        model = {
            "names": names,
            "means": [0.0] * X.shape[1],
            "sds": [1.0] * X.shape[1],
            "beta": beta.tolist(),
            "challenger": False,
            "ridge_lambda": 0.01,
        }
        got = fresh.predict_frozen(model, rows)
        expected = np.clip(X @ beta, 0.0, 1.0)
        np.testing.assert_allclose(got, expected)

    def test_platt_is_apply_only(self):
        p = np.array([0.2, 0.5, 0.8])
        beta = [-0.04, 1.01]
        got = fresh.apply_platt(beta, p)
        z = np.log(p / (1.0 - p))
        expected = 1.0 / (1.0 + np.exp(-(-0.04 + 1.01 * z)))
        np.testing.assert_allclose(got, expected)

    @staticmethod
    def scored_frame(rows_per_symbol: int = 600) -> pd.DataFrame:
        rows = []
        for symbol_index, symbol in enumerate(fresh.SYMBOLS):
            for i in range(rows_per_symbol):
                y = (i + symbol_index) % 2
                day = f"2026-03-{(i % 20) + 1:02d}"
                row = {
                    "symbol": symbol,
                    "trading_day": day,
                    "normal_within_15m": y,
                    "normal_within_30m": y,
                }
                for horizon in fresh.HORIZONS:
                    row[f"p_B_raw_{horizon}m"] = 0.5
                    row[f"p_C_raw_{horizon}m"] = 0.8 if y else 0.2
                    row[f"p_B_cal_{horizon}m"] = 0.5
                    row[f"p_C_cal_{horizon}m"] = 0.75 if y else 0.25
                rows.append(row)
        return pd.DataFrame(rows)

    def test_support_gate_is_exact_single_year_gate(self):
        frame = self.scored_frame()
        support = fresh.support_gate(frame, 15)
        self.assertTrue(support["supported_horizon"])
        self.assertEqual(support["rows"], 1200)
        self.assertEqual(support["by_symbol_rows"], {"000688.SH": 600, "000852.SH": 600})
        self.assertTrue(all(support["checks"].values()))

        too_small = self.scored_frame(rows_per_symbol=400)
        support_small = fresh.support_gate(too_small, 15)
        self.assertFalse(support_small["supported_horizon"])
        self.assertFalse(support_small["checks"]["fresh_oos_rows_ge_1000"])

    def test_gain_signs_and_joint_day_bootstrap(self):
        frame = self.scored_frame()
        pooled = fresh.gains(frame, 15)
        self.assertGreater(pooled["raw_auroc_gain"], 0.0)
        self.assertGreater(pooled["calibrated_brier_gain"], 0.0)
        self.assertGreater(pooled["calibrated_logloss_gain"], 0.0)
        boot = fresh.bootstrap_family(frame, 15, repetitions=50, seed=fresh.BOOTSTRAP_SEED)
        self.assertTrue(boot["joint_symbols_within_cluster"])
        self.assertEqual(boot["family_size"], 6)
        self.assertEqual(boot["clusters"], 20)
        self.assertGreater(boot["metrics"]["raw_auroc_gain"]["lower"], 0.0)
        self.assertGreater(boot["metrics"]["calibrated_brier_gain"]["lower"], 0.0)
        self.assertGreater(boot["metrics"]["calibrated_logloss_gain"]["lower"], 0.0)

    def test_fresh_cohort_excludes_2025_and_does_not_cross_lunch(self):
        times = list(pd.date_range("2026-03-02 09:35", periods=24, freq="5min"))
        times += list(pd.date_range("2026-03-02 13:05", periods=24, freq="5min"))
        rows = []
        for i, stamp in enumerate(times):
            state = "NORMAL"
            shock = False
            if i == 22:
                state = "UNSAFE"
                shock = True
            elif i == 23:
                state = "UNSAFE"
            rows.append(
                {
                    "symbol": "000688.SH",
                    "trading_day": "2026-03-02",
                    "year": 2026,
                    "bar_end": stamp,
                    "session": "AM" if i < 24 else "PM",
                    "shock": shock,
                    "risk_state": state,
                    "shock_intensity": 3.5 if i == 22 else 1.0,
                    "vol_ratio": 1.4 if i in (22, 23) else 1.0,
                }
            )
        rows.append(
            {
                "symbol": "000688.SH",
                "trading_day": "2025-12-31",
                "year": 2025,
                "bar_end": pd.Timestamp("2025-12-31 14:55"),
                "session": "PM",
                "shock": True,
                "risk_state": "UNSAFE",
                "shock_intensity": 4.0,
                "vol_ratio": 1.6,
            }
        )
        cohort = fresh.build_fresh_cohort(pd.DataFrame(rows))
        self.assertEqual(set(cohort["year"]), {2026})
        target = cohort[(cohort["trading_day"] == "2026-03-02") & (cohort["bar_end"] == times[23])]
        self.assertEqual(len(target), 1)
        self.assertTrue(pd.isna(target.iloc[0]["normal_within_15m"]))
        self.assertTrue(pd.isna(target.iloc[0]["normal_within_30m"]))


if __name__ == "__main__":
    unittest.main()
