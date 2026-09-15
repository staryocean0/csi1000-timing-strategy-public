from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BROKER = ROOT / "executor/ols_drawdown_d0_broker.py"


class OlsD0PrivateTextMirrorTests(unittest.TestCase):
    def test_private_text_mirror_is_bounded_and_excludes_large_row_level_outputs(self):
        text = BROKER.read_text()
        ast.parse(text)
        expected = (
            "study/RESULTS.json",
            "study/mode_comparison.csv",
            "study/qualification_reset/drawdown_atlas.csv",
            "study/first_opposite_close/drawdown_atlas.csv",
            "study/two_opposite_closes/drawdown_atlas.csv",
            "study/prior_extreme_break/drawdown_atlas.csv",
            "study/frozen_midline_break/drawdown_atlas.csv",
        )
        for path in expected:
            self.assertIn(f'"{path}"', text)
        self.assertNotIn('"trace.csv"', text)
        self.assertNotIn('"drawdown_timeseries.csv"', text)
        self.assertIn("256 * 1024", text)
        self.assertIn('raw.decode("utf-8")', text)

    def test_mirror_runs_only_after_verified_private_publish(self):
        text = BROKER.read_text()
        publish = "rb.publish(PROFILE)"
        mirror = "_mirror_private_text_results()"
        self.assertIn(publish, text)
        self.assertIn(mirror, text)
        self.assertLess(text.rindex(publish), text.rindex(mirror))
        self.assertIn('state.get("compute_success")', text)
        self.assertIn('state.get("cleanup_complete")', text)
        self.assertIn("rb.require_private_api()", text)
        self.assertIn('state["branch"]', text)
        self.assertIn("ols_d0_private_text_mirror_readback_failed", text)


if __name__ == "__main__":
    unittest.main()
