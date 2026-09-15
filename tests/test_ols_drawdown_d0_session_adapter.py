from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class OlsD0SessionAdapterTests(unittest.TestCase):
    def test_adapter_is_loader_only_and_uses_verified_bar_order(self):
        path = ROOT / "executor/ols_drawdown_d0_session_adapter.py"
        text = path.read_text()
        ast.parse(text)
        self.assertIn('day_index = z.groupby("trading_day", sort=False).cumcount()', text)
        self.assertIn('np.where(day_index < 24, "AM", "PM")', text)
        self.assertNotIn('.dt.hour', text)
        for forbidden in ("fit_r2", "FAST_MIN_R2", "FAST_MIN_SLOPE", "path_efficiency", "EXIT_MODES"):
            self.assertNotIn(forbidden, text)

    def test_broker_stages_adapter_without_changing_frozen_profile_identity(self):
        text = (ROOT / "executor/ols_drawdown_d0_broker.py").read_text()
        self.assertIn('"d0/ols_drawdown_d0_session_adapter.py"', text)
        self.assertIn('"ols_drawdown_d0_session_adapter.py"', text)
        self.assertIn('PROFILE_SHA256 = "adfa0789e195cd8eaf5b344d39eabbdcba2229cecad2df2f0da3852f013541a7"', text)
        self.assertIn('"new_training": False', text)
        self.assertIn('"production_authority": False', text)


if __name__ == "__main__":
    unittest.main()
