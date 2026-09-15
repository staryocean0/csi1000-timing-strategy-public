from __future__ import annotations

import json
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "executor" / "ols_r2_d2_exit_overlay_profile.json"
ENGINE = ROOT / "executor" / "ols_r2_d2_exit_overlay.py"
BROKER = ROOT / "executor" / "ols_r2_d2_exit_overlay_broker.py"
VERIFIER = ROOT / "executor" / "ols_r2_d2_exit_overlay_verifier.py"
WORKFLOW = ROOT / ".github" / "workflows" / "public-compute.yml"
CONTROLLER = ROOT / ".github" / "workflows" / "controller-dispatch.yml"


class OlsR2D2ContractTests(unittest.TestCase):
    def test_profile_is_frozen_and_nonproduction(self):
        p = json.loads(PROFILE.read_text())
        self.assertEqual(p["schema_id"], "ols_r2_d2_exit_overlay_profile@1.1")
        self.assertEqual(p["d1_authoritative_run"], "34964393250")
        self.assertEqual(p["d1_result_branch"], "runs/public-research/34964393250-1")
        self.assertEqual(p["d1_result_blob"], "f35ae2ff402c90b54d318b49bd678c5398a60493")
        self.assertFalse(p["optimization_performed"])
        self.assertFalse(p["production_authority"])
        self.assertEqual(
            p["overlay_rule"]["trigger"],
            "first_same_window_two_consecutive_fit_r2_declines_per_baseline_nonflat_same_direction_segment",
        )
        self.assertEqual(p["overlay_rule"]["execution"], "warning_at_close_t_flat_from_next_executable_bar")
        self.assertEqual(p["overlay_rule"]["lockout"], "remain_flat_until_original_baseline_segment_ends")

    def test_standard_route_only(self):
        workflow = WORKFLOW.read_text()
        controller = CONTROLLER.read_text()
        profile = "ols-r2-d2-exit-overlay-v1"
        self.assertIn(f"- {profile}", workflow)
        for phase in ("prepare", "compute", "cleanup", "publish"):
            self.assertIn(f"ols_r2_d2_exit_overlay_broker.py {phase} {profile}", workflow)
        self.assertIn(f"controller: {profile}", controller)
        self.assertEqual(workflow.count("secrets.FACTORLAB_PRIVATE_TOKEN"), 2)

    def test_engine_has_no_parameter_search_or_production_authority(self):
        text = ENGINE.read_text()
        broker = BROKER.read_text()
        verifier = VERIFIER.read_text()
        self.assertIn('"parameter_search_performed": False', text)
        self.assertIn('"production_authority": False', text)
        self.assertIn('events = trace["r2_two_down_same_window"]', text)
        self.assertIn('D1_RESULT_BLOB = "f35ae2ff402c90b54d318b49bd678c5398a60493"', broker)
        self.assertIn("same_window_guard_modes_passed", broker)
        self.assertIn("windows[i] == windows[i - 1] == windows[i - 2]", verifier)
        self.assertNotIn("GridSearch", text)
        self.assertNotIn("optuna", text.lower())

    def test_overlay_waits_until_next_bar_and_locks_out(self):
        source = ENGINE.read_text()
        start = source.index("def _segment_bounds")
        stop = source.index("def _side_exit_audit")
        ns = {"np": np, "pd": pd}
        exec(source[start:stop], ns)
        frame = pd.DataFrame(
            {
                "executable_position": [1, 1, 1, 1, 0, -1, -1, -1],
                "segment_id": [1, 1, 1, 1, 0, 2, 2, 2],
                "r2_two_down_same_window": [False, False, True, True, False, False, True, False],
                "strategy_return": [0.01] * 8,
                "timestamp": [str(i) for i in range(8)],
                "authority_window_bars": [12, 12, 12, 12, np.nan, 24, 24, 24],
                "fit_r2": [0.9, 0.8, 0.7, 0.6, np.nan, 0.8, 0.7, 0.6],
                "path_efficiency": [0.5] * 8,
            }
        )
        overlay, rows = ns["_apply_overlay"](frame)
        self.assertEqual(overlay.tolist(), [1, 1, 1, 0, 0, -1, -1, 0])
        self.assertEqual(len(rows), 2)
        self.assertTrue(rows[0]["effective_overlay_exit"])
        self.assertTrue(all(row["same_window_three_bar_guard"] for row in rows))


if __name__ == "__main__":
    unittest.main()
