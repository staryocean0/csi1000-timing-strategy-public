from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXECUTOR = ROOT / "executor"
ENTRY = EXECUTOR / "risk_phase1b_fresh_oos_entry.py"
BROKER = EXECUTOR / "risk_phase1b_fresh_oos_broker.py"
EVALUATOR = EXECUTOR / "risk_phase1b_fresh_oos_eval.py"


class FreshOosPhysicalLoaderTest(unittest.TestCase):
    def test_entry_is_loader_only_and_delegates_to_frozen_evaluator(self):
        text = ENTRY.read_text()
        ast.parse(text, filename=ENTRY.name)
        self.assertIn('REQUIRED_CARRIER_COLUMNS = ("datetime", "symbol", "close")', text)
        self.assertIn("pq.ParquetFile(candidate)", text)
        self.assertIn("parquet.schema_arrow.names", text)
        self.assertIn("use_pandas_metadata=False", text)
        self.assertIn("to_pandas(ignore_metadata=True)", text)
        self.assertIn("ev.pd.read_parquet = _read_carrier_without_pandas_metadata", text)
        self.assertIn("ev.main()", text)
        self.assertIn("ev.pd.read_parquet = _ORIGINAL_READ_PARQUET", text)
        for forbidden in (
            "FRESH_ROWS_MIN",
            "BOOTSTRAP_REPS",
            "FROZEN_CALIBRATION",
            "evaluate_horizon",
            "fit_platt",
            "ridge_lambda",
        ):
            self.assertNotIn(forbidden, text)

    def test_broker_routes_only_compute_entry_and_stages_original_science(self):
        text = BROKER.read_text()
        ast.parse(text, filename=BROKER.name)
        self.assertIn('"fresh_oos/risk_phase1b_fresh_oos_entry.py"', text)
        self.assertIn('"risk_phase1b_fresh_oos_entry.py",', text)
        self.assertIn('"risk_phase1b_fresh_oos_eval.py",', text)
        self.assertIn('"risk_phase1b_fresh_oos_verifier.py",', text)
        self.assertIn('"fresh_oos/risk_phase1b_fresh_oos_verifier.py"', text)

    def test_scientific_evaluator_still_owns_all_frozen_rules(self):
        text = EVALUATOR.read_text()
        self.assertIn('CUTOFF_DAY = "2026-09-11"', text)
        self.assertIn("FRESH_ROWS_MIN = 1200", text)
        self.assertIn("BOOTSTRAP_REPS = 5000", text)
        self.assertIn("BOOTSTRAP_SEED = 20260914", text)
        self.assertIn("FROZEN_CALIBRATION = {", text)
        self.assertIn("def evaluate_horizon(", text)


if __name__ == "__main__":
    unittest.main()
