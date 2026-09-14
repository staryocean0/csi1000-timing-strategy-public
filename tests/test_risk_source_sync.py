from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "executor/risk_source_sync.py"
SOURCE = ROOT / "governance/risk_source_sync/v1/run_study_v4.py"
REQUEST = ROOT / "governance/risk_source_sync/v1/request.json"
WORKFLOW = ROOT / ".github/workflows/public-risk-source-sync.yml"


def load_sync():
    spec = importlib.util.spec_from_file_location("risk_source_sync", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RiskSourceSyncTests(unittest.TestCase):
    def test_sync_contract_is_fixed(self):
        module = load_sync()
        self.assertEqual(module.PRIVATE_BRANCH, "sync/risk-v2/direct-members-v1")
        self.assertEqual(
            module.TARGET_PATH,
            "runtime/research/risk_tool_v2_severity_persistence_v1/run_study_v4.py",
        )
        module.self_test()

    def test_v4_reads_direct_signed_members_only(self):
        text = SOURCE.read_text(encoding="utf-8")
        compile(text, str(SOURCE), "exec")
        self.assertIn("direct_signed_outer_members_complete_canonical_v19_5m_set", text)
        self.assertIn("v3.selected_key(member.name)", text)
        self.assertIn('expected_meta = expected.get(member.name)', text)
        self.assertNotIn("candidate_names", text)
        self.assertNotIn('endswith(".tar")', text)
        self.assertNotIn("pnl", text.lower())

    def test_workflow_is_bounded_source_transport_only(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("push:", text)
        self.assertIn("governance/risk_source_sync/v1/request.json", text)
        self.assertNotIn("pull_request:", text)
        self.assertNotIn("inputs:", text)
        self.assertIn("private-research", text)
        self.assertTrue(REQUEST.is_file())


if __name__ == "__main__":
    unittest.main()
