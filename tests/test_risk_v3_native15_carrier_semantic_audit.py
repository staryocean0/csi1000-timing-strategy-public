from __future__ import annotations

import ast
import hashlib
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXEC = ROOT / "executor"
DOC = ROOT / "docs" / "research" / "RISK_TOOL_V3_NATIVE15_PHASE_A_PREREG_20260915.json"
RUNNER = EXEC / "risk_v3_native15_carrier_semantic_audit.py"
BROKER = EXEC / "risk_v3_native15_carrier_semantic_audit_broker.py"
VERIFIER = EXEC / "risk_v3_native15_carrier_semantic_audit_verifier.py"
MIRROR = EXEC / "risk_v3_native15_carrier_semantic_audit_private_mirror.py"
WORKFLOW = ROOT / ".github" / "workflows" / "public-compute.yml"
CONTROLLER = ROOT / ".github" / "workflows" / "controller-dispatch.yml"
PROFILE = "risk-v3-native15-carrier-semantic-audit-v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Native15AuditTests(unittest.TestCase):
    def test_sources_parse_without_runtime_dependencies(self):
        for path in (RUNNER, BROKER, VERIFIER, MIRROR):
            ast.parse(path.read_text(), filename=str(path))

    def test_prereg_hash_and_semantics_are_frozen(self):
        prereg = json.loads(DOC.read_text())
        self.assertEqual(prereg["profile"], PROFILE)
        self.assertEqual(prereg["semantic_rule"]["native_15m_means_base_kline_interval_minutes"], 15)
        self.assertTrue(prereg["semantic_rule"]["not_v2_5m_forecast_horizon"])
        self.assertFalse(prereg["boundaries"]["threshold_search"])
        self.assertFalse(prereg["boundaries"]["model_fit"])
        self.assertFalse(prereg["boundaries"]["year_2026_threshold_or_model_training"])
        src = RUNNER.read_text()
        match = re.search(r'^PREREG_SHA256 = "([0-9a-f]{64})"$', src, re.MULTILINE)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), sha256(DOC))

    def test_runner_reads_only_time_and_symbol_semantics(self):
        src = RUNNER.read_text()
        self.assertIn('parquet.read(columns=[time_field, "symbol"], use_pandas_metadata=False)', src)
        for token in ("RV_WINDOW", "BG_WINDOW", "SHOCK_SIGMA", "HIGHVOL_RATIO", "RECOVERY_NORMAL_RATIO"):
            self.assertNotIn(token, src)
        self.assertNotIn('columns=[time_field, "symbol", "close"]', src)
        self.assertIn('"market_values_read": False', src)
        self.assertIn('"threshold_search": False', src)
        self.assertIn('"year_2026_threshold_or_model_training": False', src)

    def test_broker_verifier_mirror_and_standard_route_are_bounded(self):
        broker = BROKER.read_text()
        verifier = VERIFIER.read_text()
        mirror = MIRROR.read_text()
        workflow = WORKFLOW.read_text()
        controller = CONTROLLER.read_text()
        self.assertIn("data/index/15m_offset_5.parquet", broker)
        self.assertIn("data/index/SOURCE_MANIFEST.json", broker)
        self.assertIn("pq.ParquetFile(c)", verifier)
        self.assertIn('pqf.read(columns=[tf[0],"symbol"],use_pandas_metadata=False)', verifier)
        self.assertNotIn("import risk_v3_native15_carrier_semantic_audit", verifier)
        self.assertIn("NATIVE15_CARRIER_SEMANTIC_AUDIT.json", mirror)
        self.assertIn(PROFILE, workflow)
        self.assertIn("controller: " + PROFILE, controller)
        for text in (broker, mirror):
            self.assertNotIn("production_authority=True", text)


if __name__ == "__main__":
    unittest.main()
