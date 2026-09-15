from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "executor/private_governance_sync.py"
WORKFLOW = ROOT / ".github/workflows/public-governance-sync.yml"
REQUEST = ROOT / "governance/private_sync/v1/request.json"


def load_sync_module():
    spec = importlib.util.spec_from_file_location("private_governance_sync", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PrivateGovernanceSyncTests(unittest.TestCase):
    def test_contract_is_fixed_and_sources_exist(self):
        mod = load_sync_module()
        self.assertIn("two-repo-control-plane-hardening-v1", mod.CONTRACTS)
        self.assertIn("layer3-ols-family-import-20260915-v1", mod.CONTRACTS)
        legacy = mod.CONTRACTS["two-repo-control-plane-hardening-v1"]
        self.assertEqual(
            {row["target"] for row in legacy["targets"]},
            {"AGENTS.md", "docs/WORKFLOW.md"},
        )
        self.assertRegex(str(legacy["private_base_sha"]), r"^[0-9a-f]{40}$")
        self.assertEqual(legacy["private_branch"], "sync/public-governance/two-repo-control-plane-hardening-v1")
        for row in legacy["targets"]:
            self.assertRegex(row["expected_private_blob"], r"^[0-9a-f]{40}$")
            source = ROOT / row["source"]
            self.assertTrue(source.is_file())
            text = source.read_text(encoding="utf-8")
            self.assertIn("Chat", text)
            self.assertIn("公库", text)
            self.assertIn("私库", text)
        mod.self_test()
        request, contract = mod._load_request()
        self.assertEqual(request["phase"], "merge")
        self.assertEqual(request["sync_id"], "layer3-ols-family-import-20260915-v1")
        self.assertEqual(request["private_base_sha"], contract["private_base_sha"])
        self.assertEqual(request["targets"], [row["target"] for row in contract["targets"]])

    def test_workflow_only_accepts_manual_or_fixed_request_push(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("push:", text)
        self.assertIn("cloud-workspace-v1", text)
        self.assertIn("governance/private_sync/v1/request.json", text)
        self.assertNotIn("pull_request:", text)
        self.assertNotIn("pull_request_target:", text)
        self.assertNotIn("inputs:", text)
        self.assertIn("private-research", text)

    def test_merge_is_exact_compare_then_non_force_fast_forward(self):
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('private_base_sha = str(contract["private_base_sha"])', text)
        self.assertIn('f"repos/{PRIVATE_REPO}/compare/{private_base_sha}...{head_sha}"', text)
        self.assertIn('expected_names = {row["target"] for row in contract["targets"]}', text)
        self.assertIn('f"repos/{PRIVATE_REPO}/git/refs/heads/{PRIVATE_BASE_BRANCH}"', text)
        self.assertIn('{"sha": head_sha, "force": False}', text)
        self.assertNotIn('"force": True', text)
        self.assertNotIn("/pulls", text)
        self.assertTrue(REQUEST.is_file())


if __name__ == "__main__":
    unittest.main()
