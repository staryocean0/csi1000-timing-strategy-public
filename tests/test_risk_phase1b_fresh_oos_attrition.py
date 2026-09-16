from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILE = "risk-v2-phase1b-fresh-oos-attrition-v1"
PREREG = ROOT / "docs/research/RISK_TOOL_V2_2026_FRESH_OOS_ATTRITION_V1_PREREG_20260915.json"


class RiskFreshOosAttritionTest(unittest.TestCase):
    def test_prereg_is_diagnostic_only_and_parent_is_frozen(self) -> None:
        value = json.loads(PREREG.read_text())
        self.assertEqual(value["profile"], PROFILE)
        self.assertEqual(value["parent_fresh_oos"]["run_id"], "34956326542-1")
        self.assertEqual(value["parent_fresh_oos"]["overall_status"], "INSUFFICIENT_2026_SUPPORT")
        self.assertTrue(value["parent_fresh_oos"]["verdict_immutable"])
        self.assertEqual(value["carrier"]["sha256"], "211448c914b547232bc536da7df94dc5ae279b8265a5cafe58409238485217d7")
        self.assertFalse(value["frozen_science"]["model_execution"])
        self.assertFalse(value["frozen_science"]["calibration_execution"])
        self.assertEqual(value["allowed_outputs"]["files"], ["ATTRITION.json"])
        for key in ("row_level_market_data", "market_values", "timestamps", "model_outputs", "probabilities"):
            self.assertFalse(value["allowed_outputs"][key])

    def test_runner_uses_frozen_pipeline_without_scoring(self) -> None:
        path = ROOT / "executor/risk_phase1b_fresh_oos_attrition.py"
        source = path.read_text()
        ast.parse(source)
        for name in ("normalize_carrier", "build_state_rows", "build_fresh_cohort", "support_gate"):
            self.assertIn(f"ev.{name}", source)
        for forbidden in ("score_cohort(", "predict_frozen(", "apply_platt(", "MODEL_FREEZE.json", "CALIBRATION_FREEZE.json"):
            self.assertNotIn(forbidden, source)
        for checkpoint in (
            "physical_projected", "temporal_window_usable", "normalized", "state_rows",
            "fresh_state_rows", "episode_starts", "fresh_cohort", "horizon_15_usable", "horizon_30_usable",
        ):
            self.assertIn(checkpoint, source)
        self.assertIn('"000688.SH": 0, "000852.SH": 754', source)
        self.assertIn('"000688.SH": 0, "000852.SH": 690', source)

    def test_verifier_is_independent_and_recomputes(self) -> None:
        source = (ROOT / "executor/risk_phase1b_fresh_oos_attrition_verifier.py").read_text()
        ast.parse(source)
        self.assertNotIn("import risk_phase1b_fresh_oos_attrition", source)
        for name in ("normalize_carrier", "build_state_rows", "build_fresh_cohort", "support_gate"):
            self.assertIn(f"ev.{name}", source)

    def test_broker_reuses_only_accepted_carrier_transport(self) -> None:
        source = (ROOT / "executor/risk_phase1b_fresh_oos_attrition_broker.py").read_text()
        ast.parse(source)
        self.assertIn("fresh._stage_carrier", source)
        self.assertNotIn("MODEL_RELEASE", source)
        self.assertNotIn("CALIBRATION_RELEASE", source)
        self.assertNotIn("_download_release_member", source)
        self.assertIn('"new_training": False', source)
        self.assertIn('"production_authority": False', source)

    def test_mirror_exports_only_bounded_json(self) -> None:
        source = (ROOT / "executor/risk_phase1b_fresh_oos_attrition_private_mirror.py").read_text()
        ast.parse(source)
        self.assertIn('FILE = "ATTRITION.json"', source)
        self.assertNotIn(".parquet", source)
        self.assertNotIn(".csv", source)

    def test_standard_routes_registered(self) -> None:
        workflow = (ROOT / ".github/workflows/public-compute.yml").read_text()
        controller = (ROOT / ".github/workflows/controller-dispatch.yml").read_text()
        self.assertIn(f"- {PROFILE}", workflow)
        self.assertGreaterEqual(workflow.count(PROFILE), 6)
        self.assertIn(f"controller: {PROFILE}", controller)
        self.assertGreaterEqual(controller.count(PROFILE), 2)

    def test_authority_map_keeps_lanes_distinct(self) -> None:
        text = (ROOT / "docs/research/RISK_TOOL_V2_AUTHORITY_WORKSTREAM_MAP_20260915.md").read_text(encoding="utf-8")
        for run in ("34956326542-1", "34930354449-1", "34942554638-1", "34945466654-1", "34954265620-1"):
            self.assertIn(run, text)
        self.assertIn("does **not** replace PRIVATE", text)
        self.assertIn("must not be post-hoc merged into one verdict", text)


if __name__ == "__main__":
    unittest.main()
