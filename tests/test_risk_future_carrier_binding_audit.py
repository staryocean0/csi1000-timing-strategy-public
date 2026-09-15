from __future__ import annotations

import ast
import hashlib
import importlib.util
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
AMEND = ROOT / "docs" / "research" / "RISK_TOOL_V2_FUTURE_CARRIER_BINDING_AUDIT_V1_AMENDMENT_20260915.json"
AMEND_SHA = "7972fbc0a13671cf182cdb0c7c3b4ce6d10588c63cbe34c9e6871f300626f371"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


audit = load_module(AUDIT, "future_binding_audit")


class FutureCarrierBindingAuditStaticTest(unittest.TestCase):
    def test_original_prereg_is_preserved_and_amendment_records_failed_assumption(self):
        original = json.loads(PREREG.read_text())
        amendment = json.loads(AMEND.read_text())
        self.assertEqual(hashlib.sha256(AMEND.read_bytes()).hexdigest(), AMEND_SHA)
        self.assertEqual(original["source"]["members"]["000688.SH"], "data/market/5m/000688.SH/2026.parquet")
        self.assertEqual(amendment["triggering_failed_run"]["public_run_id"], "34968368325-1")
        self.assertEqual(amendment["triggering_failed_run"]["failure_code"], "future_binding_member_not_unique:000688.SH")
        self.assertFalse(amendment["triggering_failed_run"]["semantic_market_read_occurred"])
        self.assertEqual(amendment["prior_authoritative_inventory"]["canonical_000688_2026_5m_members"], 0)
        self.assertEqual(amendment["prior_authoritative_inventory"]["canonical_000852_2026_5m_members"], 0)
        self.assertEqual(amendment["corrected_binding"]["source_contract"]["path"], "data/index/SOURCE_MANIFEST.json")
        self.assertTrue(amendment["future_oos_anchor"]["current_snapshot_is_not_future_oos_evidence"])

    def test_audit_is_manifest_only(self):
        text = AUDIT.read_text()
        ast.parse(text, filename=AUDIT.name)
        for forbidden in ("pyarrow", "pandas", "read_parquet", "read_table", "ParquetFile"):
            self.assertNotIn(forbidden, text)
        self.assertIn('"parquet_deserialization": False', text)
        self.assertIn('FUTURE_START = "2026-09-14"', text)
        self.assertIn('FUTURE_END = "2027-03-31"', text)

    def test_broker_stages_exact_source_contract_not_nonexistent_pair(self):
        text = BROKER.read_text()
        ast.parse(text, filename=BROKER.name)
        self.assertIn('SOURCE_CONTRACT_SUFFIX = "data/index/SOURCE_MANIFEST.json"', text)
        self.assertIn('SOURCE_CONTRACT_SHA256 = "c46f2da6c3df016ca054e183e37267dc472097450fcdd6644c22aa0084c15749"', text)
        self.assertIn('"SOURCE_MANIFEST.json"', text)
        self.assertNotIn('"data/market/5m/000688.SH/2026.parquet"', text)
        self.assertNotIn('"data/market/5m/000852.SH/2026.parquet"', text)
        self.assertNotIn("future_binding_member_not_unique", text)

    def test_verifier_is_independent_and_manifest_only(self):
        text = VERIFIER.read_text()
        ast.parse(text, filename=VERIFIER.name)
        self.assertIn("def independently_build(", text)
        self.assertIn('"status": "passed"', text)
        self.assertNotIn("risk_future_carrier_binding_audit import", text)
        for forbidden in ("pyarrow", "pandas", "read_parquet", "read_table"):
            self.assertNotIn(forbidden, text)

    def test_synthetic_source_family_binding(self):
        amendment = json.loads(AMEND.read_text())
        corrected = amendment["corrected_binding"]
        manifest = {
            "symbols": ["000016.SH", "000852.SH", "000688.SH"],
            "canonical_1m_parent_dataset_version": corrected["canonical_1m_parent_dataset_version"],
            "artifacts": {
                "5m_offset_0.parquet": {
                    "sha256": corrected["source_artifact"]["sha256"],
                    "rows": corrected["source_artifact"]["rows"],
                }
            },
            "views": [
                {
                    "name": "irrelevant",
                    "audit": {
                        "symbols": {
                            "000688.SH": {"rows": 1, "first_trading_day": "2026-01-01", "last_trading_day": "2026-01-01", "trading_day_count": 1, "expected_trading_day_count": 1, "day_count_ready": True},
                            "000852.SH": {"rows": 1, "first_trading_day": "2026-01-01", "last_trading_day": "2026-01-01", "trading_day_count": 1, "expected_trading_day_count": 1, "day_count_ready": True},
                        }
                    },
                },
                {"name": "5m_offset_0", "audit": {"symbols": corrected["target_symbols"]}},
            ],
        }
        self.assertEqual(audit._matching_views(manifest, corrected["target_symbols"]), [1])

    def test_private_mirror_is_bounded_and_fail_closed(self):
        text = MIRROR.read_text()
        ast.parse(text, filename=MIRROR.name)
        self.assertIn("256 * 1024", text)
        self.assertIn('"SOURCE_FAMILY_BINDING_VALID"', text)
        self.assertIn("future_binding_mirror_control_violation", text)


if __name__ == "__main__":
    unittest.main()
