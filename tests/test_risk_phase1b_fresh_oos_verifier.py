from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


evalmod = load("fresh_eval", ROOT / "executor" / "risk_phase1b_fresh_oos_eval.py")
ver = load("fresh_verify", ROOT / "executor" / "risk_phase1b_fresh_oos_verifier.py")


class FreshOOSVerifierTests(unittest.TestCase):
    @staticmethod
    def scored_frame(rows_per_symbol: int = 600) -> pd.DataFrame:
        rows = []
        for symbol_index, symbol in enumerate(evalmod.SYMBOLS):
            for i in range(rows_per_symbol):
                y = (i + symbol_index) % 2
                day = f"2026-04-{(i % 20) + 1:02d}"
                row = {
                    "symbol": symbol,
                    "trading_day": day,
                    "year": 2026,
                    "current_state": "RECOVERING" if i % 3 else "UNSAFE",
                    "age_bucket": ("LT15", "M15_25", "M30_40", "GE45")[i % 4],
                    "shock_intensity": 2.0 + (i % 7) * 0.2,
                    "vol_ratio": 1.15 + (i % 5) * 0.05,
                    "normal_within_15m": y,
                    "normal_within_30m": y,
                }
                for horizon in evalmod.HORIZONS:
                    row[f"p_B_raw_{horizon}m"] = 0.5
                    row[f"p_C_raw_{horizon}m"] = 0.8 if y else 0.2
                    row[f"p_B_cal_{horizon}m"] = 0.5
                    row[f"p_C_cal_{horizon}m"] = 0.75 if y else 0.25
                rows.append(row)
        return pd.DataFrame(rows)

    def test_verifier_protocol_constants_match_evaluator(self):
        self.assertEqual(ver.TASK_ID, evalmod.TASK_ID)
        self.assertEqual(ver.SYMBOLS, evalmod.SYMBOLS)
        self.assertEqual(ver.HORIZONS, evalmod.HORIZONS)
        self.assertEqual(ver.BOOTSTRAP_REPS, evalmod.BOOTSTRAP_REPS)
        self.assertEqual(ver.BOOTSTRAP_SEED, evalmod.BOOTSTRAP_SEED)
        self.assertEqual(ver.FAMILY_SIZE, evalmod.FAMILY_SIZE)
        self.assertAlmostEqual(ver.BONFERRONI_LOWER_QUANTILE, evalmod.BONFERRONI_LOWER_QUANTILE)
        self.assertEqual(ver.MODEL_FREEZE_SHA256, evalmod.MODEL_FREEZE_SHA256)
        self.assertEqual(ver.CALIBRATION_FREEZE_SHA256, evalmod.CALIBRATION_FREEZE_SHA256)

    def test_verifier_has_no_fit_path(self):
        source = (ROOT / "executor" / "risk_phase1b_fresh_oos_verifier.py").read_text()
        self.assertNotIn("def fit_ridge", source)
        self.assertNotIn("def fit_platt", source)
        self.assertNotIn("np.linalg.solve", source)

    def test_support_and_gain_recomputation_matches_evaluator(self):
        frame = self.scored_frame()
        for horizon in evalmod.HORIZONS:
            self.assertEqual(ver.support_gate(frame, horizon), evalmod.support_gate(frame, horizon))
            left = ver.gains(frame, horizon)
            right = evalmod.gains(frame, horizon)
            ver.compare_tree(left, right)

    def test_joint_day_bootstrap_matches_evaluator(self):
        frame = self.scored_frame()
        for horizon in evalmod.HORIZONS:
            left = ver.bootstrap_family(frame, horizon, repetitions=40, seed=20260914)
            right = evalmod.bootstrap_family(frame, horizon, repetitions=40, seed=20260914)
            ver.compare_tree(left, right)

    def test_frozen_score_verifier_accepts_exact_and_rejects_tamper(self):
        frame = self.scored_frame(rows_per_symbol=4)
        model = {"models": {}}
        calibration = {"fits": {}}
        for horizon in evalmod.HORIZONS:
            model["models"][str(horizon)] = {}
            calibration["fits"][str(horizon)] = {"audit": {"B": [0.0, 1.0], "C": [0.0, 1.0]}}
            for label, challenger in (("B", False), ("C", True)):
                X, names = evalmod.raw_design(frame, challenger)
                beta = np.linspace(0.001, 0.001 * X.shape[1], X.shape[1])
                frozen = {
                    "names": names,
                    "means": [0.0] * X.shape[1],
                    "sds": [1.0] * X.shape[1],
                    "beta": beta.tolist(),
                    "challenger": challenger,
                    "ridge_lambda": 0.01,
                }
                model["models"][str(horizon)][label] = frozen
            b = evalmod.predict_frozen(model["models"][str(horizon)]["B"], frame)
            c = evalmod.predict_frozen(model["models"][str(horizon)]["C"], frame)
            frame[f"p_B_raw_{horizon}m"] = b
            frame[f"p_C_raw_{horizon}m"] = c
            frame[f"p_B_cal_{horizon}m"] = evalmod.apply_platt([0.0, 1.0], b)
            frame[f"p_C_cal_{horizon}m"] = evalmod.apply_platt([0.0, 1.0], c)

        ver.verify_frozen_scores(frame, model, calibration)
        frame.loc[0, "p_C_raw_15m"] += 1e-4
        with self.assertRaisesRegex(RuntimeError, "frozen_score_mismatch:p_C_raw_15m"):
            ver.verify_frozen_scores(frame, model, calibration)

    def test_summary_comparison_rejects_changed_scientific_value(self):
        expected = {
            "status": "FRESH_OOS_NOT_VALIDATED",
            "metric": {"point": 0.01, "lower": -0.02},
            "production_authority": False,
        }
        got = {
            "status": "FRESH_OOS_NOT_VALIDATED",
            "metric": {"point": 0.01, "lower": -0.01},
            "production_authority": False,
        }
        with self.assertRaisesRegex(RuntimeError, "summary_numeric_mismatch"):
            ver.compare_tree(got, expected)


if __name__ == "__main__":
    unittest.main()
