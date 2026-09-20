from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
STUDY_PATH = ROOT / "executor/two_wave_local_state_exit_compression_v1.py"
RUNNER_PATH = ROOT / "executor/run_two_wave_local_state_exit_compression_v1.py"
VERIFIER_PATH = ROOT / "executor/two_wave_local_state_exit_compression_verifier_v1.py"
AMENDMENT = ROOT / "docs/research/TWO_WAVE_LOCAL_STATE_EXIT_COMPRESSION_PREREG_AMENDMENT_A_20260920.md"


def load_study():
    spec = importlib.util.spec_from_file_location("issue624_study", STUDY_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LocalStateExitCompressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.study = load_study()

    @staticmethod
    def future_maps(*, exact_first: str | None = None, carrier_change: tuple[int, str] | None = None):
        five = {0: "CURRENT_UP"}
        carrier = {0: "DIR_UP"}
        for j in range(1, 17):
            five[j] = "CURRENT_UP"
            carrier[j] = "DIR_UP"
        if exact_first is not None:
            five[1] = exact_first
        if carrier_change is not None:
            delay, state = carrier_change
            for j in range(delay, 17):
                carrier[j] = state
        return five, carrier

    def test_low_gate_does_not_mechanically_trigger_structural_exit(self):
        five, carrier = self.future_maps(exact_first="LOW_AMPLITUDE_VETO")
        out = self.study._future_outcomes(
            five,
            carrier,
            k=0,
            exact_state="CURRENT_UP",
            carrier_state="DIR_UP",
        )
        self.assertEqual(out["structural_exit_next8"], 0)
        self.assertEqual(out["structural_exit_next16"], 0)
        self.assertEqual(out["exact_label_exit_next8"], 1)
        self.assertEqual(out["technical_first_exit"], 1)
        self.assertEqual(out["first_exact_exit_state"], "LOW_AMPLITUDE_VETO")

    def test_finer_gate_does_not_mechanically_trigger_structural_exit(self):
        five, carrier = self.future_maps(exact_first="FINER_SCALE_OUT_OF_BAND")
        out = self.study._future_outcomes(
            five,
            carrier,
            k=0,
            exact_state="CURRENT_UP",
            carrier_state="DIR_UP",
        )
        self.assertEqual(out["structural_exit_next8"], 0)
        self.assertEqual(out["exact_label_exit_next8"], 1)
        self.assertEqual(out["technical_first_exit"], 1)

    def test_range_is_structural_exit_without_direction_forecast(self):
        five, carrier = self.future_maps(carrier_change=(5, "DIR_RANGE"))
        out = self.study._future_outcomes(
            five,
            carrier,
            k=0,
            exact_state="CURRENT_UP",
            carrier_state="DIR_UP",
        )
        self.assertEqual(out["structural_exit_next8"], 1)
        self.assertEqual(out["first_structural_exit_delay"], 5)
        self.assertEqual(out["first_structural_exit_state"], "DIR_RANGE")
        self.assertEqual(out["slap_next8"], 0)

    def test_opposite_direction_is_structural_exit_and_face_slap(self):
        five, carrier = self.future_maps(carrier_change=(3, "DIR_DOWN"))
        out = self.study._future_outcomes(
            five,
            carrier,
            k=0,
            exact_state="CURRENT_UP",
            carrier_state="DIR_UP",
        )
        self.assertEqual(out["structural_exit_next8"], 1)
        self.assertEqual(out["first_structural_exit_delay"], 3)
        self.assertEqual(out["first_structural_exit_state"], "DIR_DOWN")
        self.assertEqual(out["slap_next8"], 1)

    def test_age_bins_are_frozen(self):
        expected = {
            1: "A1_1_4",
            4: "A1_1_4",
            5: "A2_5_8",
            8: "A2_5_8",
            9: "A3_9_16",
            16: "A3_9_16",
            17: "A4_17_32",
            32: "A4_17_32",
            33: "A5_33_PLUS",
            100: "A5_33_PLUS",
        }
        for age, label in expected.items():
            self.assertEqual(self.study._age_bin(age), label)

    def test_reverse_percentile_is_label_free_and_monotone(self):
        train = np.array([1.0, 2.0, 3.0, 4.0])
        test = np.array([1.0, 2.5, 4.0])
        score = self.study._reverse_percentiles(train, test)
        self.assertGreater(score[0], score[1])
        self.assertGreater(score[1], score[2])

    def test_dependency_and_non_recursive_boundaries_are_explicit(self):
        runner = RUNNER_PATH.read_text(encoding="utf-8")
        verifier = VERIFIER_PATH.read_text(encoding="utf-8")
        study = STUDY_PATH.read_text(encoding="utf-8")
        amendment = AMENDMENT.read_text(encoding="utf-8")

        self.assertIn("EXPECTED_RECOGNIZER_SHA256", runner)
        self.assertIn("EXPECTED_WRAPPER_SHA256", runner)
        self.assertIn("FROZEN_BEFORE_OUTCOME_EXECUTION", amendment)
        self.assertIn("LOW/FINER", amendment)
        self.assertNotIn("import two_wave_local_state_exit_compression_v1", verifier)

        forbidden_import_fragments = (
            "two_wave_c1_",
            "two_wave_c2_",
            "P128",
            "P256",
        )
        for fragment in forbidden_import_fragments:
            self.assertNotIn(fragment, study)


if __name__ == "__main__":
    unittest.main()
