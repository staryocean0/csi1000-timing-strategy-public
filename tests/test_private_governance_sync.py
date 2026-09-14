from __future__ import annotations

import importlib.util
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "executor/private_governance_sync.py"
WORKFLOW = ROOT / ".github/workflows/public-governance-sync.yml"


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
        for row in mod.TARGETS:
            self.assertRegex(row["expected_private_blob"], r"^[0-9a-f]{40}$")
            source = ROOT / row["source"]
            self.assertTrue(source.is_file())
            text = source.read_text(encoding="utf-8")
            self.assertIn("Chat", text)
            self.assertIn("公库", text)
            self.assertIn("私库", text)
        mod.self_test()

    def test_workflow_is_manual_and_has_no_arbitrary_inputs(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertNotRegex(text, r"(?m)^\s*(push|pull_request|pull_request_target):")
        self.assertNotIn("inputs:", text)
        self.assertIn("refs/heads/cloud-workspace-v1", text)
        self.assertIn("private-research", text)

    def test_sync_does_not_merge_or_force_update_private_main(self):
        text = SCRIPT.read_text(encoding="utf-8")
        lowered = text.lower()
        self.assertIn('f"repos/{PRIVATE_REPO}/pulls"', text)
        self.assertNotIn('/merge', lowered)
        self.assertNotIn('git/refs/heads/main', lowered)
        self.assertNotRegex(lowered, r"\bforce\s*=\s*true\b")
        self.assertNotRegex(lowered, r'["\']force["\']\s*:\s*true')


if __name__ == "__main__":
    unittest.main()
