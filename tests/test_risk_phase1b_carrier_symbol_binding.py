from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load_module():
    path = ROOT / "executor" / "risk_phase1b_carrier_symbol_binding.py"
    spec = importlib.util.spec_from_file_location("carrier_symbol_binding", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = load_module()


class CarrierSymbolBindingTests(unittest.TestCase):
    def test_symbol_filter_and_per_symbol_context_are_extracted_without_market_values(self):
        contract = {
            "schema_version": "synthetic",
            "symbols": ["000688.SH", "000852.SH"],
            "transforms": [
                {
                    "name": "symbol_slice",
                    "symbol_filter": "000852.SH",
                    "rows": 135682,
                    "min_day": "2015-01-05",
                    "max_day": "2026-08-21",
                    "sha256": "a" * 64,
                    "price_mean": 123.4,
                    "close": 456.7,
                }
            ],
            "per_symbol": {
                "000852.SH": {
                    "rows": 135682,
                    "sha256": "b" * 64,
                    "first_day": "2015-01-05",
                    "last_day": "2026-08-21",
                    "return_mean": 0.01,
                }
            },
            "filter_expression": "close > 1 and symbol == '000852.SH'",
        }
        occurrences, paths = mod.collect_symbol_metadata(contract)
        filtered = [row for row in occurrences if row["json_pointer"] == "/transforms/0/symbol_filter"]
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["symbol"], "000852.SH")
        self.assertEqual(filtered[0]["identity_context"]["rows"], 135682)
        self.assertEqual(filtered[0]["identity_context"]["min_day"], "2015-01-05")
        self.assertEqual(filtered[0]["identity_context"]["sha256"], "a" * 64)
        self.assertNotIn("price_mean", filtered[0]["identity_context"])
        self.assertNotIn("close", filtered[0]["identity_context"])

        keyed = [row for row in occurrences if row["json_pointer"] == "/per_symbol/000852.SH" and row["kind"] == "key"]
        self.assertEqual(len(keyed), 1)
        self.assertEqual(keyed[0]["identity_context"]["rows"], 135682)
        self.assertEqual(keyed[0]["identity_context"]["sha256"], "b" * 64)
        self.assertNotIn("return_mean", keyed[0]["identity_context"])

        self.assertIn("/transforms/0/symbol_filter", paths)
        self.assertIn("/filter_expression", paths)
        self.assertFalse(any("close > 1" in repr(row) for row in occurrences))

    def test_only_exact_symbol_tokens_are_exported(self):
        contract = {
            "note": "000852.SH is mentioned in free text",
            "symbol_filter": "000852.SH",
            "other": ["prefix-000688.SH", "399006.SZ"],
        }
        occurrences, _ = mod.collect_symbol_metadata(contract)
        exported = {(row["json_pointer"], row["symbol"]) for row in occurrences}
        self.assertIn(("/symbol_filter", "000852.SH"), exported)
        self.assertIn(("/other/1", "399006.SZ"), exported)
        self.assertFalse(any(symbol == "000688.SH" for _, symbol in exported))

    def test_identity_context_rejects_semantic_keys_floats_and_free_text(self):
        context = mod._identity_context(
            {
                "rows": 135682,
                "valid_count": 130000,
                "sha256": "c" * 64,
                "first_day": "2015-01-05",
                "source_path": "data/index/5m_offset_0.parquet",
                "source": "price derived market data",
                "close_count": 99,
                "price": 1,
                "score": 0.7,
                "row_ratio": 0.9,
            }
        )
        self.assertEqual(context["rows"], 135682)
        self.assertEqual(context["valid_count"], 130000)
        self.assertEqual(context["sha256"], "c" * 64)
        self.assertEqual(context["first_day"], "2015-01-05")
        self.assertEqual(context["source_path"], "data/index/5m_offset_0.parquet")
        self.assertNotIn("source", context)
        self.assertNotIn("close_count", context)
        self.assertNotIn("price", context)
        self.assertNotIn("score", context)
        self.assertNotIn("row_ratio", context)


if __name__ == "__main__":
    unittest.main()
