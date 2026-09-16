import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
ADJ = ROOT / "docs/research/TWO_WAVE_DUAL_GATE_ADJUDICATION_20260916.json"


class DualGateAdjudicationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = json.loads(ADJ.read_text(encoding="utf-8"))

    def test_authoritative_run_identity(self):
        self.assertEqual(self.doc["public_run"], "35065802258-1")
        self.assertEqual(self.doc["public_source_sha"], "e9ec03919df6fd45b47709249915c0007c9660c2")
        self.assertEqual(self.doc["profile"], "two-wave-dual-gates-v1")
        self.assertEqual(self.doc["transport"]["status"], "passed")

    def test_input_identity_and_base_counts(self):
        self.assertEqual(self.doc["data"]["rows"], 70114)
        self.assertEqual(self.doc["base_wave_reconstruction"], {
            "bars": 70114, "pivots": 5471, "waves": 2503, "resets": 164
        })
        self.assertIn("NOT_FRESH_OOS", self.doc["data"]["role"])

    def test_A_is_inconclusive_not_accepted(self):
        gate = self.doc["gate_A_small_to_large"]
        self.assertEqual(gate["verdict"], "INCONCLUSIVE_POSITIVE_POINT_ESTIMATES")
        self.assertFalse(gate["support_passed"])
        self.assertEqual(gate["walk_forward_scored_events"], 32)
        self.assertEqual(gate["positives"], 10)
        self.assertEqual(gate["independent_blocks_after_purge"], 3)
        self.assertGreater(gate["pooled"]["A0_parent_only_brier"], gate["pooled"]["A2_plus_internal_shape_brier"])
        self.assertGreater(gate["pooled"]["A0_parent_only_logloss"], gate["pooled"]["A2_plus_internal_shape_logloss"])

    def test_A_background_coverage_is_explicit(self):
        gate = self.doc["gate_A_small_to_large"]
        background = gate["preformation_same_scale_background"]
        self.assertEqual(background["unknown"] + background["up"] + background["down"], 924)
        self.assertEqual(gate["attrition"]["scale_mismatch"], 1434)
        self.assertEqual(gate["attrition"]["settled"], 161)

    def test_B_is_zero_coverage_not_negative_science(self):
        gate = self.doc["gate_B_large_to_small"]
        self.assertEqual(gate["verdict"], "INCONCLUSIVE_ZERO_RESOLVED_CONTEXT")
        self.assertFalse(gate["support_passed"])
        self.assertEqual(gate["evaluation_closed_trades"], 949)
        self.assertEqual(gate["background_groups"]["INSUFFICIENT_HIERARCHY"] + gate["background_groups"]["NO_ROOT"], 949)
        self.assertEqual(gate["resolved_cycle_contexts"], 0)
        self.assertEqual(gate["selected_trades"], 0)
        self.assertEqual(gate["coverage"], 0.0)

    def test_no_authority_and_next_action(self):
        self.assertFalse(self.doc["overall_adjudication"]["accepted_directional_rule"])
        self.assertFalse(self.doc["overall_adjudication"]["accepted_large_to_small_filter"])
        self.assertIn("CONTINUE_A_AS_PRIMARY_RESEARCH_DIRECTION", self.doc["overall_adjudication"]["decision"])
        self.assertTrue(all(value is False for value in self.doc["authority"].values()))


if __name__ == "__main__":
    unittest.main()
