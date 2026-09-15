from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load_module():
    path = ROOT / "executor" / "risk_phase1b_carrier_inventory_private_mirror.py"
    spec = importlib.util.spec_from_file_location("carrier_inventory_mirror", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = load_module()


class CarrierInventoryMirrorTests(unittest.TestCase):
    @staticmethod
    def safe_result():
        return {
            "schema_id": mod.RESULT_SCHEMA,
            "task_id": mod.TASK_ID,
            "status": "INVENTORY_COMPLETE_BINDING_UNRESOLVED",
            "source_release": {},
            "bundle": {},
            "candidate_counts": {
                "canonical_000688_2026_5m": 0,
                "canonical_000852_2026_5m": 0,
                "bar_receipt_metadata": 1,
                "working_lead_offset": 1,
            },
            "candidates": [
                {
                    "role": "bar_receipt_metadata",
                    "matched_suffix": "bar_receipts.csv",
                    "archive_path": "snapshot/meta/bar_receipts.csv",
                    "bytes": 12,
                    "sha256": "a" * 64,
                    "git_blob_sha1": "b" * 40,
                },
                {
                    "role": "working_lead_offset",
                    "matched_suffix": "5m_offset_0.parquet",
                    "archive_path": "snapshot/data/development/5m_offset_0.parquet",
                    "bytes": 25,
                    "sha256": "c" * 64,
                    "git_blob_sha1": "d" * 40,
                },
            ],
            "controls": {key: False for key in mod.CONTROL_KEYS},
        }

    def test_safe_identity_only_result_is_accepted(self):
        value = self.safe_result()
        self.assertIs(mod.validate_inventory(value), value)

    def test_semantic_flag_is_rejected(self):
        value = self.safe_result()
        value["controls"]["parquet_deserialization"] = True
        with self.assertRaisesRegex(mod.GateError, "inventory_mirror_semantic_or_authority_flag"):
            mod.validate_inventory(value)

    def test_scope_or_shape_broadening_is_rejected(self):
        value = self.safe_result()
        value["candidates"][0]["price"] = 1.0
        with self.assertRaisesRegex(mod.GateError, "inventory_mirror_candidate_shape_invalid"):
            mod.validate_inventory(value)

        value = self.safe_result()
        value["candidates"][0]["archive_path"] = "../escape.csv"
        with self.assertRaisesRegex(mod.GateError, "inventory_mirror_candidate_path_invalid"):
            mod.validate_inventory(value)

    def test_count_mismatch_is_rejected(self):
        value = self.safe_result()
        value["candidate_counts"]["bar_receipt_metadata"] = 2
        with self.assertRaisesRegex(mod.GateError, "inventory_mirror_count_mismatch"):
            mod.validate_inventory(value)


if __name__ == "__main__":
    unittest.main()
