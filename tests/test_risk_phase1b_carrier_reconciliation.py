from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load_module():
    path = ROOT / "executor" / "risk_phase1b_carrier_inventory_broker.py"
    spec = importlib.util.spec_from_file_location("carrier_reconciliation", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = load_module()


class CarrierReconciliationTests(unittest.TestCase):
    @staticmethod
    def git_blob_sha1(path: Path) -> str:
        raw = path.read_bytes()
        return hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()

    @staticmethod
    def safe_result():
        return {
            "schema_id": mod.RECONCILIATION_SCHEMA,
            "task_id": mod.TASK_ID,
            "status": "SOURCE_CONTRACT_EVIDENCE_EXTRACTED",
            "source_contract": {
                "archive_path": "data/index/SOURCE_MANIFEST.json",
                "bytes": mod.SOURCE_CONTRACT_BYTES,
                "sha256": mod.SOURCE_CONTRACT_SHA256,
                "git_blob_sha1": "a" * 40,
            },
            "frozen_candidate": dict(mod.FROZEN_CANDIDATE),
            "user_receipt_constraints": {
                key: (dict(value) if isinstance(value, dict) else value)
                for key, value in mod.RECEIPT_CONSTRAINTS.items()
            },
            "match_flags": {
                "target_path_present": True,
                "target_sha256_present": True,
                "source_sha256_present": True,
            },
            "evidence": [
                {
                    "json_pointer": "/datasets/0",
                    "fields": {
                        "path": "data/index/5m_offset_0.parquet",
                        "rows": 135682,
                        "min_day": "2015-01-05",
                        "max_day": "2026-08-21",
                        "source_sha256": mod.FROZEN_CANDIDATE["source_sha256"],
                        "symbols": ["000688.SH", "000852.SH"],
                    },
                }
            ],
            "controls": {key: False for key in mod.CONTROL_KEYS},
        }

    def test_legacy_core_blobs_are_pinned(self):
        self.assertEqual(
            self.git_blob_sha1(ROOT / "executor" / "risk_phase1b_carrier_inventory_core_v1.py"),
            "8fa1dc9460981ced4f5a3a1e8c2a4ffbbaf4a683",
        )
        self.assertEqual(
            self.git_blob_sha1(ROOT / "executor" / "risk_phase1b_carrier_inventory_private_mirror_core_v1.py"),
            "ee3d4fe34a85bd1841907b5e7714e957f98fcc52",
        )

    def test_safe_identity_sidecar_is_accepted(self):
        value = self.safe_result()
        self.assertIs(mod.validate_reconciliation(value), value)

    def test_semantic_or_authority_flag_is_rejected(self):
        value = self.safe_result()
        value["controls"]["year_2026_semantic_read"] = True
        with self.assertRaisesRegex(mod.GateError, "reconciliation_semantic_or_authority_flag"):
            mod.validate_reconciliation(value)

    def test_semantic_evidence_key_is_rejected(self):
        value = self.safe_result()
        value["evidence"][0]["fields"]["close_price"] = 1
        with self.assertRaisesRegex(mod.GateError, "reconciliation_unsafe_evidence_key"):
            mod.validate_reconciliation(value)

    def test_sanitizer_keeps_identity_fields_and_drops_market_fields(self):
        raw = {
            "path": "data/index/5m_offset_0.parquet",
            "rows": 135682,
            "valid_rows": 130000,
            "first_day": "2015-01-05",
            "source_sha256": "b" * 64,
            "close_min": 123,
            "return_stats": {"count": 10},
            "label_count": 20,
            "price": 456,
        }
        clean = mod._sanitize(raw)
        self.assertEqual(clean["rows"], 135682)
        self.assertEqual(clean["valid_rows"], 130000)
        self.assertEqual(clean["first_day"], "2015-01-05")
        self.assertIn("source_sha256", clean)
        self.assertNotIn("close_min", clean)
        self.assertNotIn("return_stats", clean)
        self.assertNotIn("label_count", clean)
        self.assertNotIn("price", clean)

    def test_primary_v1_contract_is_unchanged(self):
        self.assertEqual(mod.PROFILE_NAME, "risk-v2-phase1b-carrier-inventory-v1")
        self.assertEqual(mod.RESULT_SCHEMA, "risk_tool_v2_phase1b_carrier_inventory@1.0")
        self.assertNotIn("SOURCE_MANIFEST.json", mod.EXPECTED_SUFFIXES)


if __name__ == "__main__":
    unittest.main()
