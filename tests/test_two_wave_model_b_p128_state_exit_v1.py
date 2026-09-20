import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "executor"))

import two_wave_model_b_p128_state_exit_v1 as m


class ModelBP128ImplementationTests(unittest.TestCase):
    def _fit_frame(self):
        rows = []
        rng = np.random.default_rng(20260920)
        for state in m.DIRECTIONAL_STATES:
            for age in m.AGE_BINS:
                for relation in m.RELATIONS:
                    for i in range(80):
                        score = (i + 0.5) / 80
                        p = 0.15 + 0.35 * score
                        if state == "CURRENT_DOWN":
                            p += 0.05
                        if relation == "OPPOSED":
                            p += 0.08
                        elif relation == "NEUTRAL":
                            p += 0.02
                        y = int(rng.random() < min(p, 0.9))
                        rows.append({
                            "state": state,
                            "age_bin": age,
                            "context_relation": relation,
                            "compression_score": score,
                            "y8": y,
                        })
        return pd.DataFrame(rows)

    def test_context_is_current_only_and_unresolved_is_explicit(self):
        close = np.exp(np.linspace(4.0, 4.2, 200))
        early = m._context(close, 100, "CURRENT_UP")
        self.assertFalse(early["context_resolved"])
        self.assertEqual(early["context_relation"], m.UNRESOLVED)
        self.assertEqual(early["context_missing_reason"], "INSUFFICIENT_128_HISTORY")
        flat = m._context(np.full(200, 100.0), 150, "CURRENT_UP")
        self.assertTrue(flat["context_resolved"])
        self.assertEqual(flat["context_phase"], "PARENT_RANGE")
        self.assertEqual(flat["context_relation"], "NEUTRAL")

    def test_design_budget_and_reference_category(self):
        df = pd.DataFrame([
            {"state": "CURRENT_UP", "age_bin": m.AGE_BINS[0], "compression_score": 0.7, "context_relation": "ALIGNED"},
            {"state": "CURRENT_UP", "age_bin": m.AGE_BINS[0], "compression_score": 0.7, "context_relation": "NEUTRAL"},
            {"state": "CURRENT_DOWN", "age_bin": m.AGE_BINS[1], "compression_score": 0.2, "context_relation": "OPPOSED"},
        ])
        xa, pa = m._design(df, "A")
        xb, pb = m._design(df, "B")
        self.assertEqual(xa.shape, (3, 12))
        self.assertEqual(xb.shape, (3, 16))
        self.assertTrue(np.all(pa[:10] == 0))
        self.assertTrue(np.all(pb[:10] == 0))
        self.assertEqual(float(xb[0, 12:].sum()), 0.0)
        self.assertEqual(xb[1, 12], 1.0)
        self.assertEqual(xb[2, 15], 1.0)

    def test_newton_fit_is_deterministic_and_symmetric(self):
        df = self._fit_frame()
        a1 = m.fit_logistic(df, "A")
        a2 = m.fit_logistic(df, "A")
        b1 = m.fit_logistic(df, "B")
        b2 = m.fit_logistic(df, "B")
        self.assertTrue(a1["converged"])
        self.assertTrue(b1["converged"])
        np.testing.assert_array_equal(a1["coef"], a2["coef"])
        np.testing.assert_array_equal(b1["coef"], b2["coef"])
        self.assertLessEqual(a1["grad_inf"], m.GRAD_TOL)
        self.assertLessEqual(b1["grad_inf"], m.GRAD_TOL)

    def test_training_cell_support_is_fail_closed(self):
        df = self._fit_frame()
        support = m._training_cell_support(df)
        self.assertTrue(all(x["passed"] for x in support))
        bad = df[~((df.state == "CURRENT_UP") & (df.age_bin == m.AGE_BINS[0]))].copy()
        support = m._training_cell_support(bad)
        target = [x for x in support if x["state"] == "CURRENT_UP" and x["age_bin"] == m.AGE_BINS[0]][0]
        self.assertFalse(target["passed"])

    def test_labels_use_only_carrier_exit(self):
        carriers = {i: "DIR_UP" for i in range(30)}
        self.assertEqual(m._label8(carriers, 5, "DIR_UP"), 0)
        carriers[12] = "DIR_RANGE"
        self.assertEqual(m._label8(carriers, 5, "DIR_UP"), 1)

    def test_gate_does_not_allow_one_direction_only(self):
        pooled = {"relative_brier_gain": 0.02}
        yearly = [{"brier_gain": 0.01}] * 3
        state = {"CURRENT_UP": {"brier_gain": 0.01}, "CURRENT_DOWN": {"brier_gain": 0.01}}
        cohorts = [{"brier_gain": 0.01}] * 8
        common = {"brier_gain": 0.01}
        rel = {"A": {"ece": 0.02}, "B": {"ece": 0.02}}
        boot = {
            "pooled_brier_gain": {"low": 0.001},
            "pooled_logloss_gain": {"low": 0.001},
            "CURRENT_UP_brier_gain": {"low": -0.001},
            "CURRENT_DOWN_brier_gain": {"low": 0.001},
        }
        decision = m._gate(
            pooled, yearly, state, cohorts, common, rel, boot,
            {"passed": True}, True, True
        )
        self.assertEqual(
            decision["verdict"],
            "MODEL_B_P128_STATE_EXIT_INCREMENT_NOT_SUPPORTED",
        )

    def test_verifier_source_is_independent_of_new_producer(self):
        text = (
            ROOT / "executor/two_wave_model_b_p128_state_exit_verifier_v1.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("import two_wave_model_b_p128_state_exit_v1", text)
        self.assertIn("def prediction_stream", text)
        self.assertIn("def causal", text)


if __name__ == "__main__":
    unittest.main()
