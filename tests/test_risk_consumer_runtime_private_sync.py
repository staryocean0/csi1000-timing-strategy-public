from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "executor/risk_consumer_runtime_private_sync.py"
REQUEST = ROOT / "governance/private_sync/v1/risk_tool_v2/runtime_consumer_request.json"
WORKFLOW = ROOT / ".github/workflows/public-risk-consumer-runtime-sync.yml"
SMOKE = ROOT / "governance/private_sync/v1/risk_tool_v2/test_risk_probability_reliability_consumer_integration_v1.py"


def load_module():
    spec = importlib.util.spec_from_file_location("risk_consumer_runtime_sync", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RiskConsumerRuntimePrivateSyncTests(unittest.TestCase):
    def test_contract_is_exact_and_stage_request_is_frozen(self) -> None:
        mod = load_module()
        self.assertEqual(mod.SYNC_ID, "risk-v2-consumer-runtime-import-20260915-v1")
        self.assertEqual(mod.PRIVATE_BASE_SHA, "67effb80f51228f6129dca5c4f7971a0bb6c7f15")
        self.assertEqual(mod.PRIVATE_BRANCH, "sync/public-runtime/risk-v2-consumer-runtime-import-20260915-v1")
        self.assertEqual(
            [row["target"] for row in mod.TARGETS],
            [
                "runtime/src/factor_lab/market_state/risk_probability_reliability_consumer_v1.py",
                "runtime/tests/unit/test_risk_probability_reliability_consumer_integration_v1.py",
            ],
        )
        self.assertEqual(
            [row["expected_public_blob"] for row in mod.TARGETS],
            [
                "bfe25858f30b007505519ebd262f8396c508f519",
                "90c41e566457806c673ccb3ac3f0b8d150a6db51",
            ],
        )
        request = json.loads(REQUEST.read_text(encoding="utf-8"))
        self.assertEqual(request["phase"], "stage")
        self.assertEqual(request["sync_id"], mod.SYNC_ID)
        self.assertEqual(request["private_base_sha"], mod.PRIVATE_BASE_SHA)
        self.assertEqual(request["targets"], [row["target"] for row in mod.TARGETS])
        mod.self_test()

    def test_merge_is_non_force_and_exact_scope(self) -> None:
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('compare/{PRIVATE_BASE_SHA}...{head_sha}', text)
        self.assertIn('{"sha": head_sha, "force": False}', text)
        self.assertNotIn('"force": True', text)
        self.assertIn('row.get("status") != "added"', text)
        self.assertNotIn("/pulls", text)

    def test_workflow_is_fixed_and_smoke_has_no_private_token(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("push:", text)
        self.assertIn("runtime_consumer_request.json", text)
        self.assertNotIn("inputs:", text)
        self.assertIn("python3 executor/risk_consumer_runtime_private_sync.py", text)
        self.assertIn("FACTORLAB_PRIVATE_TOKEN: ${{ secrets.FACTORLAB_PRIVATE_TOKEN }}", text)
        self.assertIn("FACTORLAB_PRIVATE_TOKEN: ''", text)
        self.assertIn("python3 -m unittest discover", text)
        self.assertNotIn("pip install", text)

    def test_smoke_is_stdlib_and_contains_no_strategy_execution(self) -> None:
        text = SMOKE.read_text(encoding="utf-8")
        compile(text, str(SMOKE), "exec")
        self.assertIn("import unittest", text)
        self.assertNotIn("import pytest", text)
        self.assertIn("consume(low, \"probability_context\")", text)
        self.assertIn("consume(thirty, \"strategy_routing\")", text)
        lowered = text.lower()
        for forbidden in ("pnl", "backtest", "position_size", "order_submit", "broker_api"):
            self.assertNotIn(forbidden, lowered)


if __name__ == "__main__":
    unittest.main()
