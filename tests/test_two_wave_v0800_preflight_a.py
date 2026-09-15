import json
import py_compile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AMENDMENT = ROOT / "docs/research/TWO_WAVE_V0800_PREFLIGHT_AMENDMENT_A.json"
ENTRY = ROOT / "executor/two_wave_v0800_scale_map_entry.py"
VERIFY_ENTRY = ROOT / "executor/two_wave_v0800_scale_map_verifier_entry.py"
BROKER = ROOT / "executor/two_wave_v0800_scale_map_broker.py"


class TwoWaveV0800PreflightATest(unittest.TestCase):
    def test_amendment_is_prerun_and_non_authoritative(self):
        value = json.loads(AMENDMENT.read_text())
        self.assertEqual(value["status"], "PRERUN_CLARIFICATION_BEFORE_FIRST_REAL_V0800_B_EXECUTION")
        self.assertFalse(value["scientific_scope_change"])
        self.assertEqual(value["clarifications"]["primary_duration_unit"], "bar_intervals_between_pivot_occurrence_bars")
        self.assertEqual(value["clarifications"]["inclusive_observation_count_relation"], "span_rows = d + 1")
        self.assertEqual(value["rho_diagnostics"]["candidate_rho"], [1.25, 4 / 3, 2 ** 0.5, 1.5])
        self.assertEqual(value["rho_diagnostics"]["legacy_control_rho"], 2.0)
        self.assertFalse(value["rho_diagnostics"]["legacy_control_can_win"])
        self.assertIsNone(value["authority"]["rho_winner"])
        self.assertFalse(value["authority"]["morphology_acceptance"])

    def test_entry_and_verifier_compile_without_importing_heavy_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            for source in (ENTRY, VERIFY_ENTRY):
                py_compile.compile(str(source), cfile=str(Path(tmp) / (source.name + ".pyc")), doraise=True)

    def test_entry_separates_candidate_and_legacy_control(self):
        text = ENTRY.read_text(encoding="utf-8")
        self.assertIn("DIAGNOSTIC_RHOS = CANDIDATE_RHOS + (LEGACY_RHO_CONTROL,)", text)
        self.assertIn('value["candidate_rhos"] = list(CANDIDATE_RHOS)', text)
        self.assertIn('value["legacy_control_can_win"] = False', text)
        self.assertIn('value["duration_unit"] = "bar_intervals_between_pivot_occurrence_bars"', text)
        self.assertNotIn("rho_winner =", text)

    def test_verifier_checks_legacy_without_promoting_it(self):
        text = VERIFY_ENTRY.read_text(encoding="utf-8")
        self.assertIn("legacy_control_authority_violation", text)
        self.assertIn("legacy_control_statistics_missing", text)
        self.assertIn("inclusive_duration_histogram_mismatch", text)
        self.assertIn("base_structural_verifier_failed", text)

    def test_broker_must_route_through_preflight_entrypoints(self):
        text = BROKER.read_text(encoding="utf-8")
        # This test is expected to turn green only after the broker is updated.
        self.assertIn("two_wave_v0800_scale_map_entry.py", text)
        self.assertIn("two_wave_v0800_scale_map_verifier_entry.py", text)
        self.assertIn("TWO_WAVE_V0800_PREFLIGHT_AMENDMENT_A.json", text)


if __name__ == "__main__":
    unittest.main()
