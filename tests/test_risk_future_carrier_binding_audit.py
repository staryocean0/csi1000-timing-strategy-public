from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXECUTOR = ROOT / "executor"
AUDIT = EXECUTOR / "risk_future_carrier_binding_audit.py"
VERIFIER = EXECUTOR / "risk_future_carrier_binding_audit_verifier.py"
BROKER = EXECUTOR / "risk_future_carrier_binding_audit_broker.py"
MIRROR = EXECUTOR / "risk_future_carrier_binding_audit_private_mirror.py"
PREREG = ROOT / "docs" / "research" / "RISK_TOOL_V2_FUTURE_CARRIER_BINDING_AUDIT_V1_PREREG_20260915.json"


class FutureCarrierBindingAuditStaticTest(unittest.TestCase):
    def test_prereg_freezes_pair_and_no_rescue_semantics(self):
        value = json.loads(PREREG.read_text())
        self.assertEqual(value["source"]["members"]["000688.SH"], "data/market/5m/000688.SH/2026.parquet")
        self.assertEqual(value["source"]["members"]["000852.SH"], "data/market/5m/000852.SH/2026.parquet")
        self.assertEqual(value["future_oos_anchor"]["consumed_parent_cutoff_inclusive"], "2026-09-11")
        self.assertEqual(value["future_oos_anchor"]["proposed_new_window_start_inclusive"], "2026-09-14")
        self.assertTrue(value["future_oos_anchor"]["current_snapshot_is_not_future_oos_evidence"])
        self.assertFalse(value["new_training"])
        self.assertFalse(value["production_authority"])

    def test_audit_reads_identity_columns_only(self):
        text = AUDIT.read_text()
        ast.parse(text, filename=AUDIT.name)
        self.assertIn('pq.read_table(path, columns=["symbol", time_field])', text)
        self.assertIn('"market_value_columns_read": False', text)
        self.assertIn('"row_level_data_exported": False', text)
        self.assertIn('FUTURE_START = "2026-09-14"', text)
        self.assertIn('FUTURE_END = "2027-03-31"', text)
        for forbidden in ("predict_frozen", "FROZEN_CALIBRATION", "evaluate_horizon", "bootstrap", "fit_platt"):
            self.assertNotIn(forbidden, text)

    def test_verifier_recomputes_pair_independently(self):
        text = VERIFIER.read_text()
        ast.parse(text, filename=VERIFIER.name)
        self.assertIn("def independently_inspect(", text)
        self.assertIn('pq.read_table(path, columns=["symbol", time_field])', text)
        self.assertIn('"status": "passed"', text)
        self.assertNotIn("risk_future_carrier_binding_audit import", text)

    def test_broker_stages_exact_pair_from_frozen_bundle(self):
        text = BROKER.read_text()
        ast.parse(text, filename=BROKER.name)
        self.assertIn('"000688.SH": "data/market/5m/000688.SH/2026.parquet"', text)
        self.assertIn('"000852.SH": "data/market/5m/000852.SH/2026.parquet"', text)
        self.assertIn('"risk-v2-future-carrier-binding-audit-v1"', text)
        self.assertIn('GITHUB_EVENT_NAME") != "workflow_dispatch"', text)
        self.assertIn("future_binding_member_not_unique", text)

    def test_private_mirror_is_bounded_and_fail_closed(self):
        text = MIRROR.read_text()
        ast.parse(text, filename=MIRROR.name)
        self.assertIn("256 * 1024", text)
        self.assertIn('"PAIR_BINDING_VALID_FOR_SOURCE_FAMILY"', text)
        self.assertIn('"PAIR_BINDING_INVALID"', text)
        self.assertIn("future_binding_mirror_control_violation", text)


if __name__ == "__main__":
    unittest.main()
