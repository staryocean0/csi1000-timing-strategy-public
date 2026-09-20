"""Pre-outcome regression cases: failures keep the repair draft unqualified.

All frames below are synthetic; no private data or governed context is used.
"""
import copy
import hashlib
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "executor"))
import two_wave_model_b_p128_state_exit_v1 as producer
import two_wave_model_b_p128_state_exit_verifier_v1 as verifier


def synthetic_result(published=False):
    early = {
        "known_index": 500, "target_index": 492,
        "timestamp": pd.Timestamp("2016-01-04 10:00"), "knowledge_day": "2016-01-04",
        "year": 2016, "state": "CURRENT_UP", "carrier_state": "DIR_UP",
        "state_age": 5, "exact_label_age": 5, "age_bin": producer.AGE_BINS[1],
        "context_phase": "PARENT_UP", "context_relation": "ALIGNED", "context_g": 0.5,
        "context_resolved": True, "context_missing_reason": "",
    }
    early.update({feature: 0.1 for feature in producer.FEATURES})
    rows, predictions, fits = [early], pd.DataFrame(), []
    if published:
        known = dict(early, known_index=40000, target_index=39992, year=2018,
                     timestamp=pd.Timestamp("2018-06-01 10:00"), knowledge_day="2018-06-01")
        rows.append(known)
        predictions = pd.DataFrame([dict(known, compression_score=0.5, risk_band=3,
                                         p_A=0.5, p_B=0.5)])
        digest = hashlib.sha256(b"synthetic-prior-training-population").hexdigest()
        fits = [{"year": 2018, "resolved_fit_rows": 10000,
                 "reference_keys_sha256": digest, "training_keys_sha256": digest,
                 "training_labels_sha256": digest,
                 "A": {"coef": [0.0] * 12}, "B": {"coef": [0.0] * 16}}]
    frame = pd.DataFrame(rows)
    five = {r["known_index"]: r["state"] for r in rows}
    carriers = {r["known_index"]: r["carrier_state"] for r in rows}
    return {"decisions": frame, "predictions": predictions, "fits": fits,
            "components": SimpleNamespace(five_states=five, carriers=carriers),
            "five_states": five, "carriers": carriers}


class ModelBAcceptanceRegressions(unittest.TestCase):
    def test_producer_rejects_early_decision_change_without_predictions(self):
        full = synthetic_result()
        changed = copy.deepcopy(full)
        changed["decisions"].loc[0, "state_age"] = 99
        ok, _ = producer._snapshot_equal(producer._snapshot(full), producer._snapshot(changed), 10000)
        self.assertFalse(ok, "An early decision mutation must not pass an empty-prediction audit.")

    def test_verifier_rejects_early_decision_change_without_predictions(self):
        full = synthetic_result()
        changed = copy.deepcopy(full)
        changed["decisions"].loc[0, "state_age"] = 99
        ok, _ = verifier.snapshot_equal(verifier.snapshot(full), verifier.snapshot(changed), 10000)
        self.assertFalse(ok)

    def test_producer_rejects_missing_published_fit(self):
        full = synthetic_result(published=True)
        changed = copy.deepcopy(full)
        changed["fits"] = []
        ok, _ = producer._snapshot_equal(producer._snapshot(full), producer._snapshot(changed), 50000)
        self.assertFalse(ok)

    def test_verifier_rejects_missing_published_fit(self):
        full = synthetic_result(published=True)
        changed = copy.deepcopy(full)
        changed["fits"] = []
        ok, _ = verifier.snapshot_equal(verifier.snapshot(full), verifier.snapshot(changed), 50000)
        self.assertFalse(ok)

    def test_producer_rejects_changed_training_row_identity(self):
        full = synthetic_result(published=True)
        changed = copy.deepcopy(full)
        changed["fits"][0]["training_keys_sha256"] = hashlib.sha256(b"different-toy-rows").hexdigest()
        ok, _ = producer._snapshot_equal(producer._snapshot(full), producer._snapshot(changed), 50000)
        self.assertFalse(ok)

    def test_verifier_rejects_changed_training_row_identity(self):
        full = synthetic_result(published=True)
        changed = copy.deepcopy(full)
        changed["fits"][0]["training_keys_sha256"] = hashlib.sha256(b"different-toy-rows").hexdigest()
        ok, _ = verifier.snapshot_equal(verifier.snapshot(full), verifier.snapshot(changed), 50000)
        self.assertFalse(ok)

    @staticmethod
    def _failed_support_fixture():
        import numpy as np
        n = 10050
        known = np.arange(100, 100 + n)
        dec = pd.DataFrame({
            "known_index": known,
            "target_index": known - 8,
            "timestamp": pd.to_datetime("2017-01-03") + pd.to_timedelta(known, unit="m"),
            "knowledge_day": ["2017-01-03"] * n,
            "year": [2017] * n,
            "state": ["CURRENT_UP"] * n,
            "carrier_state": ["DIR_UP"] * n,
            "state_age": [1] * n,
            "exact_label_age": [1] * n,
            "age_bin": [producer.AGE_BINS[0]] * n,
            "context_phase": ["PARENT_UP"] * n,
            "context_relation": ["ALIGNED"] * n,
            "context_g": [0.5] * n,
            "context_resolved": [True] * n,
            "context_missing_reason": [""] * n,
        })
        for feature in producer.FEATURES:
            dec[feature] = 0.1
        test = dec.iloc[:1].copy()
        test["known_index"] = 20000
        test["target_index"] = 19992
        test["year"] = 2018
        test["knowledge_day"] = "2018-01-02"
        dec = pd.concat([dec, test], ignore_index=True)
        carriers = {i: "DIR_UP" for i in range(0, 20100)}
        return dec, carriers

    def test_producer_stops_before_optimizer_on_failed_training_cells(self):
        from unittest.mock import patch
        dec, carriers = self._failed_support_fixture()
        component = producer.Components(dec, {}, carriers, 0)
        def scored(_reference, rows):
            return rows.assign(compression_score=0.5, risk_band=3), {}
        with patch.object(producer, "build_components", return_value=component),              patch.object(producer, "_first_native_index", return_value=20000),              patch.object(producer, "_score", side_effect=scored),              patch.object(producer, "fit_logistic", side_effect=AssertionError("optimizer_called")):
            with self.assertRaises(producer.InsufficientSupportError):
                producer.prediction_stream(pd.DataFrame())

    def test_verifier_stops_before_optimizer_on_failed_training_cells(self):
        from unittest.mock import patch
        dec, carriers = self._failed_support_fixture()
        def scored(_reference, rows):
            return rows.assign(compression_score=0.5, risk_band=3), {}
        with patch.object(verifier, "components", return_value=(dec, {}, carriers, 0)),              patch.object(verifier, "first_index", return_value=20000),              patch.object(verifier.base624, "_score_with_training", side_effect=scored),              patch.object(verifier, "fit", side_effect=AssertionError("optimizer_called")):
            with self.assertRaises(verifier.InsufficientSupportError):
                verifier.prediction_stream(pd.DataFrame())

    def test_analyze_converts_support_stop_to_frozen_verdict(self):
        from unittest.mock import patch
        stop = producer.InsufficientSupportError("training_cells", {"year": 2018})
        with patch.object(producer, "prediction_stream", side_effect=stop):
            result = producer.analyze(pd.DataFrame())
        self.assertEqual(
            result["decision"]["verdict"],
            "MODEL_B_P128_STATE_EXIT_INCREMENT_INSUFFICIENT_SUPPORT",
        )
        self.assertFalse(result["support"]["passed"])
        self.assertEqual(result["meta"]["stage"], "training_cells")

    def test_verifier_source_checks_full_envelope_and_all_ledger_columns(self):
        source = Path(verifier.__file__).read_text(encoding="utf-8")
        for fragment in (
            'list(disk.columns) != list(evaldf.columns)',
            'exact["meta"]',
            'exact["baseline_identity"]',
            'exact["coverage"]',
            'exact["relation_support"]',
            'exact["authority"]',
            '"support_stop_top_level_fields"',
            '"exact_top_level_fields"',
        ):
            self.assertIn(fragment, source)
