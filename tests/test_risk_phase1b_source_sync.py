from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUEST = ROOT / "governance/risk_phase1b_source_v1/request.json"
WORKFLOW = ROOT / ".github/workflows/risk-phase1b-source-sync.yml"
SYNC = ROOT / "executor/risk_phase1b_source_sync.py"


def git_blob_sha1(raw: bytes) -> str:
    return hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()


class Phase1bSourceSyncTests(unittest.TestCase):
    def test_request_is_exact_and_sources_match_identity(self):
        request = json.loads(REQUEST.read_text())
        self.assertEqual(request["schema_id"], "csi1000.risk_phase1b_source_sync_request@1.1")
        self.assertEqual(request["sync_id"], "risk-v2-phase1b-ordering-calibration-v1")
        self.assertEqual(request["phase"], "stage")
        self.assertEqual(request["private_base_sha"], "c45c0f991d9d6872bf312bbf0e1f220b98958d75")
        self.assertEqual(request["target_branch"], "research/frozen/risk-v2-phase1b-ordering-calibration-v1")
        self.assertEqual(len(request["files"]), 3)
        self.assertEqual(
            {row["target"] for row in request["files"]},
            {
                "runtime/research/risk_tool_v2_phase1b_ordering_calibration_v1/run_study.py",
                "runtime/research/risk_tool_v2_phase1b_ordering_calibration_v1/verify_study.py",
                "docs/research/RISK_TOOL_V2_PHASE1B_ORDERING_CALIBRATION_PROTOCOL_20260914.json",
            },
        )
        for row in request["files"]:
            raw = (ROOT / row["source"]).read_bytes()
            self.assertEqual(len(raw), row["bytes"])
            self.assertEqual(git_blob_sha1(raw), row["git_blob_sha1"])

    def test_workflow_is_control_plane_only(self):
        text = WORKFLOW.read_text()
        self.assertIn("governance/risk_phase1b_source_v1/request.json", text)
        self.assertIn("risk_phase1b_source_sync.py --self-test", text)
        self.assertIn("risk_phase1b_source_sync.py", text)
        self.assertNotIn("docker", text.lower())
        self.assertNotIn("public-compute.yml", text)
        self.assertNotIn("risk_phase1b_platt.py --", text)
        self.assertNotIn("run_study.py", text)

    def test_sync_code_is_fixed_scope_and_no_research_execution(self):
        text = SYNC.read_text()
        self.assertIn('PRIVATE_BASE_SHA = "c45c0f991d9d6872bf312bbf0e1f220b98958d75"', text)
        self.assertIn('PRIVATE_BRANCH = "research/frozen/risk-v2-phase1b-ordering-calibration-v1"', text)
        self.assertIn("verify_exact_compare", text)
        self.assertIn("verify_branch_files", text)
        self.assertNotIn("subprocess", text)
        self.assertNotIn("docker", text.lower())


if __name__ == "__main__":
    unittest.main()
