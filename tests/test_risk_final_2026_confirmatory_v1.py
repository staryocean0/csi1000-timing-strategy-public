from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "executor" / "risk_final_2026_confirmatory_v1.py"
SPEC = importlib.util.spec_from_file_location("risk_final_confirmatory", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
final = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(final)


class FinalRiskConfirmatoryTests(unittest.TestCase):
    @staticmethod
    def one_minute_day(symbol: str = "000688.SH", day: str = "2023-03-01") -> pd.DataFrame:
        am = pd.date_range(day + " 09:31", periods=120, freq="1min")
        pm = pd.date_range(day + " 13:01", periods=120, freq="1min")
        stamps = list(am) + list(pm)
        return pd.DataFrame({
            "symbol": symbol,
            "trading_day": [day] * 240,
            "timestamp": stamps,
            "close": np.arange(1.0, 241.0),
        })

    def test_frozen_contract_constants(self):
        self.assertEqual(final.TASK_ID, "CSI1000-RISK-V2-FINAL-2026-CONFIRMATORY-V1-20260915")
        self.assertEqual(final.TAIL_SELECTION_RUN, "34920654435-1")
        self.assertAlmostEqual(final.TAIL_ANCHOR_RATE, 0.2312353159391616)
        self.assertEqual(final.TAIL_LIMIT, 4.0)
        self.assertEqual(final.base.HORIZONS, (15, 30))
        self.assertEqual(final.base.BOOTSTRAP_REPS, 5000)
        self.assertEqual(final.base.BOOTSTRAP_SEED, 20260914)
        self.assertEqual(final.base.FAMILY_SIZE, 6)
        self.assertAlmostEqual(final.base.BONFERRONI_LOWER_QUANTILE, 0.05 / 6.0)
        self.assertEqual(final.MODEL_FREEZE_SHA256, "b81cae6208d96890c0fd83d47e4ea8c8a81ba55b41c78f58db29e9160f173551")
        self.assertEqual(final.CALIBRATION_FREEZE_SHA256, "74ecd25790123f026e29cba7bb84322aad8a385c10fe3d60ef0d75d52d1b1909")

    def test_synthesis_uses_each_fifth_close_and_session_boundaries(self):
        source = self.one_minute_day()
        got = final.synthesize_5m(source, "000688.SH", 2023)
        self.assertEqual(len(got), 48)
        self.assertEqual(got.groupby("trading_day").size().iloc[0], 48)
        self.assertEqual(got.iloc[0].timestamp, pd.Timestamp("2023-03-01 09:35"))
        self.assertEqual(got.iloc[0].close, 5.0)
        self.assertEqual(got.iloc[23].timestamp, pd.Timestamp("2023-03-01 11:30"))
        self.assertEqual(got.iloc[23].close, 120.0)
        self.assertEqual(got.iloc[24].timestamp, pd.Timestamp("2023-03-01 13:05"))
        self.assertEqual(got.iloc[24].close, 125.0)
        self.assertEqual(got.iloc[-1].timestamp, pd.Timestamp("2023-03-01 15:00"))
        self.assertEqual(got.iloc[-1].close, 240.0)

    def test_synthesis_rejects_incomplete_day(self):
        source = self.one_minute_day().iloc[:-1].copy()
        with self.assertRaisesRegex(RuntimeError, "one_minute_non_240_day"):
            final.synthesize_5m(source, "000688.SH", 2023)

    def test_equivalence_guard_rejects_close_mismatch(self):
        one = self.one_minute_day()
        native = final.synthesize_5m(one, "000688.SH", 2023)
        native.loc[10, "close"] += 0.01
        def fake_read(path):
            text = str(path)
            if "guard_1m" in text:
                return one.copy()
            return native.copy()
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(final.pd, "read_parquet", side_effect=fake_read):
            with self.assertRaisesRegex(RuntimeError, "equivalence_close_mismatch"):
                final.equivalence_guard(Path(tmp))

    def test_tail_transform_is_monotone_anchor_fixed_and_tail_compressing(self):
        p = np.array([0.001, 0.05, final.TAIL_ANCHOR_RATE, 0.8, 0.999])
        q = final.tail_compress(p)
        self.assertTrue(np.all(np.diff(q) > 0))
        self.assertAlmostEqual(q[2], final.TAIL_ANCHOR_RATE, places=12)
        a = np.log(final.TAIL_ANCHOR_RATE / (1.0 - final.TAIL_ANCHOR_RATE))
        z = np.log(p / (1.0 - p))
        zq = np.log(q / (1.0 - q))
        self.assertLess(abs(zq[0] - a), abs(z[0] - a))
        self.assertLess(abs(zq[-1] - a), abs(z[-1] - a))

    def test_only_15m_challenger_calibration_is_tail_transformed(self):
        cohort = pd.DataFrame({"marker": [1, 2, 3]})
        base_scored = pd.DataFrame({
            "p_C_cal_15m": [0.001, 0.5, 0.999],
            "p_C_cal_30m": [0.01, 0.5, 0.99],
            "p_B_cal_15m": [0.2, 0.4, 0.6],
            "p_B_cal_30m": [0.3, 0.5, 0.7],
        })
        with mock.patch.object(final.base, "score_cohort", return_value=base_scored.copy()):
            got = final.score_final_candidate(cohort, {}, {})
        np.testing.assert_allclose(got["p_C_cal_15m"], final.tail_compress(base_scored["p_C_cal_15m"].to_numpy()))
        np.testing.assert_allclose(got["p_C_cal_30m"], base_scored["p_C_cal_30m"])
        np.testing.assert_allclose(got["p_B_cal_15m"], base_scored["p_B_cal_15m"])
        np.testing.assert_allclose(got["p_B_cal_30m"], base_scored["p_B_cal_30m"])

    def test_no_fit_or_training_path_in_final_evaluator(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("def fit_ridge", source)
        self.assertNotIn("def fit_platt", source)
        self.assertNotIn("np.linalg.solve", source)
        self.assertNotIn("LogisticRegression", source)

    def test_machine_protocol_is_finite_and_no_retuning(self):
        protocol = json.loads((ROOT / "docs" / "research" / "RISK_TOOL_V2_FINAL_2026_CONFIRMATORY_V1.json").read_text(encoding="utf-8"))
        self.assertTrue(protocol["finite_endpoint"])
        self.assertFalse(protocol["fresh_oos_claim"])
        self.assertFalse(protocol["post_read_retuning_allowed"])
        self.assertFalse(protocol["new_training"])
        self.assertFalse(protocol["pnl"])
        self.assertFalse(protocol["production_authority"])
        self.assertEqual(protocol["horizons_minutes"], [15, 30])
        self.assertEqual(protocol["final_statuses"], [
            "LAYER2_CONFIRMATORY_FULL_VALIDATION",
            "LAYER2_CONFIRMATORY_PARTIAL_VALIDATION",
            "RISK_TOOL_V2_CLOSED_NOT_VALIDATED",
            "RISK_TOOL_V2_CLOSED_INSUFFICIENT_CONFIRMATORY_SUPPORT",
        ])


if __name__ == "__main__":
    unittest.main()
