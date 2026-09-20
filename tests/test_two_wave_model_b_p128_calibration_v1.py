"""Synthetic-only qualification of the frozen #635 probability primitives."""
from pathlib import Path
from dataclasses import replace
import sys
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "executor"))
import two_wave_model_b_p128_calibration_v1 as m


def fixture(n_per_cell=180):
    rng = np.random.default_rng(20260920)
    rows = []
    for state in m.STATES:
        for age in m.AGE_BINS:
            for j in range(n_per_cell):
                rows.append({"state": state, "age_bin": age,
                             "compression_score": float(rng.uniform()),
                             "context_relation": m.RELATIONS[j % 3]})
    df = pd.DataFrame(rows)
    df["known_index"] = np.arange(300, 300 + len(df))
    df["year"] = 2017
    for feature in m.local.FEATURES:
        df[feature] = rng.uniform(0.001, 0.99, len(df))
    beta = np.r_[np.linspace(-1.1, -0.2, 10), 0.3, 0.6, 0.25, 0.8, -0.2, 0.7]
    probability = expit(m.design(df, model_b=True) @ beta)
    y = rng.binomial(1, probability)
    return df, y


class ContextTests(unittest.TestCase):
    def test_monotone_flat_and_identity(self):
        up = np.exp(np.linspace(0, 0.2, 220))
        got = m.context_at(up, 170, "CURRENT_UP")
        phase, drift = m.context.parent_phase(up[43:171])
        self.assertEqual((got["phase"], got["drift"]), (phase, drift))
        self.assertEqual(got["relation"], "ALIGNED")
        self.assertEqual(m.context_at(up, 170, "CURRENT_DOWN")["relation"], "OPPOSED")
        self.assertEqual(m.context_at(np.ones(220), 170, "CURRENT_UP")["relation"], "NEUTRAL")

    def test_prefix_and_future_perturbation(self):
        prices = np.exp(np.linspace(0, 0.2, 300))
        expected = m.context_at(prices, 170, "CURRENT_UP")
        self.assertEqual(expected, m.context_at(prices[:171], 170, "CURRENT_UP"))
        changed = prices.copy()
        changed[171:] = np.nan
        changed[:43] *= 100000
        self.assertEqual(expected, m.context_at(changed, 170, "CURRENT_UP"))

    def test_unresolved_is_not_neutral(self):
        self.assertEqual(m.context_at(np.ones(180), 126, "CURRENT_UP")["reason"],
                         "INSUFFICIENT_HISTORY")
        for bad in (0, -1, np.nan, np.inf):
            prices = np.ones(180)
            prices[160] = bad
            got = m.context_at(prices, 170, "CURRENT_UP")
            self.assertEqual(got["relation"], m.UNRESOLVED)
            self.assertIsNone(got["drift"])

    def test_invalid_clock_or_state_is_rejected(self):
        for k in (-1, 180, 170.5, True):
            with self.assertRaises(ValueError):
                m.context_at(np.ones(180), k, "CURRENT_UP")
        with self.assertRaises(ValueError):
            m.context_at(np.ones(180), 170, "CURRENT_RANGE")


class DesignTests(unittest.TestCase):
    def test_exact_nested_dimensions_and_encoding(self):
        df, _ = fixture()
        a, b = m.design(df, model_b=False), m.design(df, model_b=True)
        self.assertEqual(a.shape, (1800, 12))
        self.assertEqual(b.shape, (1800, 16))
        np.testing.assert_array_equal(a, b[:, :12])
        np.testing.assert_array_equal(a[:, :10].sum(axis=1), np.ones(1800))
        self.assertEqual(b[1, 12], 1.0)
        self.assertEqual(b[2, 13], 1.0)
        self.assertEqual(b[901, 14], 1.0)
        self.assertEqual(b[902, 15], 1.0)
        self.assertEqual(a[0, 10], df.iloc[0].compression_score - 0.5)

    def test_unknown_cells_and_scores_fail_closed(self):
        df, _ = fixture()
        cases = [("state", "UP"), ("age_bin", "NEW_BIN"),
                 ("context_relation", "MISSING"), ("compression_score", np.nan),
                 ("compression_score", -0.1), ("compression_score", 1.01)]
        for column, bad in cases:
            damaged = df.copy()
            damaged.loc[0, column] = bad
            with self.subTest(column=column, value=bad), self.assertRaises(ValueError):
                m.design(damaged, model_b=True)


class FittingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows, cls.y = fixture()
        cls.fit_a, cls.fit_b = m.fit_pair(cls.rows, cls.y)

    def test_optimizer_converges_at_frozen_tolerance(self):
        for fit, dimension in ((self.fit_a, 12), (self.fit_b, 16)):
            self.assertEqual(len(fit.coefficients), dimension)
            self.assertEqual(fit.n, len(self.rows))
            self.assertLessEqual(fit.gradient_inf, 1e-9)
            self.assertLessEqual(fit.iterations, 200)
            self.assertTrue(np.isfinite(fit.objective))

    def test_independent_bfgs_objective_agreement(self):
        x = m.design(self.rows, model_b=True)
        y = self.y.astype(float)
        penalty = np.r_[np.zeros(10), np.repeat(0.001, 6)]
        def objective(beta):
            eta = x @ beta
            return np.logaddexp(0, eta).mean() - np.mean(y * eta) + (penalty * beta ** 2).sum() / 2
        def gradient(beta):
            return x.T @ (expit(x @ beta) - y) / len(y) + penalty * beta
        reference = minimize(objective, np.zeros(16), jac=gradient, method="BFGS",
                             options={"gtol": 1e-10, "maxiter": 1000})
        self.assertLess(np.max(np.abs(gradient(reference.x))), 1e-7)
        self.assertAlmostEqual(self.fit_b.objective, float(reference.fun), places=10)
        np.testing.assert_allclose(self.fit_b.coefficients, reference.x, atol=2e-5, rtol=0)

    def test_missing_context_is_exact_A_fallback(self):
        rows = self.rows.copy()
        rows.loc[::7, "context_relation"] = m.UNRESOLVED
        beta = list(self.fit_b.coefficients)
        beta[0] += 3.0  # Ensure zero context coefficients would not be a valid fallback.
        pa, pb = m.predict_pair(rows, self.fit_a, replace(self.fit_b, coefficients=tuple(beta)))
        missing = rows.context_relation == m.UNRESOLVED
        np.testing.assert_array_equal(pa[missing], pb[missing])
        self.assertTrue(np.any(pa[~missing] != pb[~missing]))
        zero_gain = m.paired_gains(self.y[missing], pa[missing], pb[missing])
        np.testing.assert_array_equal(zero_gain["brier"], np.zeros(missing.sum()))

    def test_aligned_only_has_no_artificial_added_effect(self):
        rows = self.rows.copy()
        rows["context_relation"] = "ALIGNED"
        a, b = m.fit_pair(rows, self.y)
        np.testing.assert_allclose(a.coefficients, b.coefficients[:12], atol=1e-12, rtol=0)
        np.testing.assert_array_equal(b.coefficients[12:], np.zeros(4))

    def test_support_failure_is_not_silently_refit(self):
        rows, y = fixture(50)
        self.assertFalse(m.training_support(rows, y)["passed"])
        with self.assertRaisesRegex(ValueError, "INSUFFICIENT_TRAINING"):
            m.fit_pair(rows, y)
        rows = self.rows.copy()
        rows.loc[0, "context_relation"] = m.UNRESOLVED
        with self.assertRaisesRegex(ValueError, "common support"):
            m.fit_pair(rows, self.y)

    def test_invalid_fit_and_nonconvergence_are_errors(self):
        x = m.design(self.rows, model_b=False)
        with self.assertRaises(ValueError):
            m.fit_logistic(x, np.zeros(len(x)))
        with self.assertRaises(ValueError):
            m.fit_logistic(x[:, :-1], self.y)
        with patch.object(m, "MAX_ITER", 0), self.assertRaisesRegex(RuntimeError, "converge"):
            m.fit_logistic(x, self.y)
        with self.assertRaises(ValueError):
            m.predict_pair(self.rows, self.fit_a, replace(self.fit_b, n=1))


class MaturityTests(unittest.TestCase):
    def test_strict_cross_year_boundary_and_poisoned_future_labels(self):
        rows = pd.DataFrame({"known_index": np.arange(90, 100),
                             "context_relation": [m.UNRESOLVED] + ["ALIGNED"] * 9})
        labels = pd.DataFrame({"known_index": np.arange(91, 100),
                               "structural_exit_next8": [1] + ["FUTURE_POISON"] * 8})
        selected, y, receipt = m.select_mature_prior(rows, labels, cutoff=100)
        self.assertEqual(selected.known_index.tolist(), [91])
        self.assertEqual(y.tolist(), [1.0])
        self.assertEqual(receipt["purged_prior_n"], 8)
        self.assertEqual(receipt["mature_prior_n"], 2)
        self.assertEqual(receipt["mature_missing_context_n"], 1)
        self.assertEqual(receipt["max_training_label_index"], 99)

    def test_missing_mature_label_and_bad_clock_are_errors(self):
        rows = pd.DataFrame({"known_index": [90, 91], "context_relation": ["ALIGNED"] * 2})
        labels = pd.DataFrame({"known_index": [90], "structural_exit_next8": [0]})
        with self.assertRaisesRegex(ValueError, "missing mature"):
            m.select_mature_prior(rows, labels, cutoff=100)
        with self.assertRaises(ValueError):
            m.select_mature_prior(rows.iloc[::-1], labels, cutoff=100)
        with self.assertRaisesRegex(ValueError, "non-prior"):
            m.select_mature_prior(rows, labels, cutoff=91)
        with self.assertRaises(ValueError):
            m.select_mature_prior(rows, pd.concat([labels, labels]), cutoff=100)

    def test_label_pollution_cannot_change_prior_fits_or_label_free_CDF(self):
        rows, y = fixture()
        cutoff = int(rows.known_index.max()) + 1
        later = rows.iloc[:12].copy()
        later["year"], later["known_index"] = 2018, np.arange(cutoff, cutoff + 12)
        decisions = pd.concat([rows, later], ignore_index=True)
        train, test, meta = m.score_fold(decisions, 2018)
        labels = rows[["known_index"]].copy()
        labels["structural_exit_next8"] = y
        selected, target, receipt = m.select_mature_prior(train, labels, cutoff=cutoff)
        contaminated = labels.copy()
        contaminated["structural_exit_next8"] = contaminated.structural_exit_next8.astype(float)
        contaminated.loc[contaminated.known_index + 8 >= cutoff, "structural_exit_next8"] = np.nan
        selected2, target2, receipt2 = m.select_mature_prior(train, contaminated, cutoff=cutoff)
        self.assertEqual(meta["train_n"], len(rows))  # CDF did not lose last eight prior rows.
        self.assertEqual(receipt["training_n"], len(rows) - 8)
        self.assertEqual(receipt, receipt2)
        pd.testing.assert_frame_equal(selected, selected2)
        np.testing.assert_array_equal(target, target2)
        self.assertEqual(m.fit_pair(selected, target), m.fit_pair(selected2, target2))
        changed = decisions.copy()
        changed.loc[changed.known_index >= cutoff + 6, list(m.local.FEATURES)] *= 100
        train2, test2, meta2 = m.score_fold(changed, 2018)
        pd.testing.assert_frame_equal(train, train2)
        pd.testing.assert_frame_equal(test.iloc[:6], test2.iloc[:6])
        self.assertEqual(meta, meta2)
