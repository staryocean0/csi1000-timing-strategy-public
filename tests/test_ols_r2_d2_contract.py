from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path

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
        self.assertEqual(p["schema_id"], "ols_r2_d2_exit_overlay_profile@1.0")
        self.assertEqual(p["d1_authoritative_run"], "34964393250")
        self.assertFalse(p["optimization_performed"])
        self.assertFalse(p["production_authority"])
        self.assertEqual(
            p["overlay_rule"]["trigger"],
            "first_two_consecutive_fit_r2_declines_per_baseline_nonflat_same_direction_segment",
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

    def test_sources_parse_and_lock_frozen_d2_semantics(self):
        engine = ENGINE.read_text()
        broker = BROKER.read_text()
        verifier = VERIFIER.read_text()
        for path in (ENGINE, BROKER, VERIFIER):
            ast.parse(path.read_text())
        self.assertIn('events = trace["r2_two_down_event"]', engine)
        self.assertIn("overlay[event_idx + 1 : end + 1] = 0", engine)
        self.assertIn('D1_AUTHORITATIVE_RUN = "34964393250"', broker)
        self.assertIn('"parameter_search_performed": False', engine)
        self.assertIn('"production_authority": False', engine)
        self.assertIn("over[e + 1 : end + 1] = 0", verifier)
        self.assertNotIn("GridSearch", engine)
        self.assertNotIn("optuna", engine.lower())

    def test_contract_test_stays_stdlib_only(self):
        text = Path(__file__).read_text()
        self.assertNotIn("import numpy", text)
        self.assertNotIn("import pandas", text)
        self.assertNotIn("exec(source", text)


if __name__ == "__main__":
    unittest.main()
