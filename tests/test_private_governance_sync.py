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
        self.assertEqual(
            {row["target"] for row in mod.TARGETS},
            {"AGENTS.md", "docs/WORKFLOW.md"},
        )
        self.assertRegex(mod.PRIVATE_BASE_SHA, r"^[0-9a-f]{40}$")
        self.assertEqual(mod.PRIVATE_BRANCH, "sync/public-governance/two-repo-control-plane-hardening-v1")
        for row in mod.TARGETS:
            self.assertRegex(row["expected_private_blob"], r"^[0-9a-f]{40}$")
            source = ROOT / row["source"]
            self.assertTrue(source.is_file())
            text = source.read_text(encoding="utf-8")
            self.assertIn("Chat", text)
            self.assertIn("公库", text)
            self.assertIn("私库", text)
        mod.self_test()
        request = mod._load_request()
        self.assertEqual(request["phase"], "stage")
        self.assertEqual(request["targets"], ["AGENTS.md", "docs/WORKFLOW.md"])

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

    def test_merge_is_pr_scoped_and_never_force_updates_main_ref(self):
        text = SCRIPT.read_text(encoding="utf-8")
        lowered = text.lower()
        self.assertIn('f"repos/{PRIVATE_REPO}/pulls/{number}/merge"', text)
        self.assertIn('"branch": PRIVATE_BRANCH', text)
        self.assertNotIn('git/refs/heads/main', lowered)
        self.assertNotRegex(lowered, r"\bforce\s*=\s*true\b")
        self.assertNotRegex(lowered, r'["\']force["\']\s*:\s*true')
        self.assertIn('set(TARGET_NAMES)', text)
        self.assertTrue(REQUEST.is_file())


if __name__ == "__main__":
    unittest.main()
